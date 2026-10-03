import asyncio
from unittest.mock import patch, AsyncMock
import pytest
from fastapi.testclient import TestClient
from main import app
import landing.cache as cache_mod
import routers.landing as landing_router


def _list(known: dict[str, str] | None):
    """Patch the SEC list: a dict of canonical ticker -> title, or None = unavailable."""
    async def lookup(t):
        if known is None:
            return False, None
        return (True, known[t]) if t in known else (False, None)
    return (patch("routers.landing.lookup", new=lookup),
            patch("routers.landing.list_available", new=AsyncMock(return_value=known is not None)))

client = TestClient(app)

MAX = 3


@pytest.fixture(autouse=True)
def _isolated_landing_cache():
    """The router now serves through landing.cache (a module-level, process-lifetime
    cache), so each test needs its own clean slate — otherwise a ticker cached by an
    earlier test (e.g. AAPL, reused across several tests below) would short-circuit
    the very _run_one_guarded patch these tests assert against. Also stands in for
    the fast-layer's quote/risk-reward-input fetches so a cold ticker's cache fill
    never reaches the real network in this router-level test file (that refresh path
    is covered on its own in test_landing_cache.py)."""
    cache_mod._slow.clear()
    cache_mod._fast.clear()
    cache_mod._locks.clear()
    cache_mod._lock_refs.clear()
    with patch("landing.cache.fetch_risk_reward_inputs",
               new=AsyncMock(side_effect=RuntimeError("no network in tests"))), \
         patch("landing.cache.fetch_quote",
               new=AsyncMock(side_effect=RuntimeError("no network in tests"))):
        yield
    cache_mod._slow.clear()
    cache_mod._fast.clear()
    cache_mod._locks.clear()
    cache_mod._lock_refs.clear()


@pytest.fixture(autouse=True)
def _reset_landing_limiter():
    landing_router._limiter.clear()
    yield
    landing_router._limiter.clear()


def _ok(ticker: str) -> dict:
    return {"result": {"ticker": ticker, "company_name": f"{ticker} Inc.",
                       "current_price": 100.0, "stock_type": "MEGA_CAP",
                       "fair_value": 110.0, "price_vs_fair_value_pct": 10.0,
                       "fair_value_breakdown": {"dcf": {"fair_value": 110.0, "weight": 1.0}},
                       "status": "completed", "errors": [],
                       "screener": None, "risk_reward": None}}


def test_a_single_ticker_comes_back_mapped():
    with patch("routers.landing.validate_ticker", new=AsyncMock(return_value=True)), \
         patch("landing.cache._run_one_readonly", new=AsyncMock(side_effect=lambda t: _ok(t))):
        resp = client.post("/api/landing/analyze", json={"tickers": ["aapl"]})
    body = resp.json()
    assert [r["ticker"] for r in body["results"]] == ["AAPL"]
    assert body["results"][0]["fair_value"]["value"] == 110.0


# --- Review Focus 4: too many tickers, empty input, unresolvable ticker ---
def test_more_than_three_tickers_are_rejected_before_any_engine_runs():
    run = AsyncMock(side_effect=lambda t: _ok(t))
    validate = AsyncMock(return_value=True)
    with patch("landing.cache._run_one_readonly", new=run), \
         patch("routers.landing.validate_ticker", new=validate):
        resp = client.post("/api/landing/analyze",
                           json={"tickers": ["A", "B", "C", "D"]})
    assert resp.json()["error"] == "Up to 3 tickers per analysis run."
    assert run.await_count == 0
    assert validate.await_count == 0


def test_an_empty_request_is_rejected():
    resp = client.post("/api/landing/analyze", json={"tickers": ["  ", ""]})
    assert resp.json()["error"] == "Enter at least one ticker."


def test_an_unresolvable_ticker_is_reported_not_run():
    run = AsyncMock(side_effect=lambda t: _ok(t))
    with patch("routers.landing.validate_ticker", new=AsyncMock(return_value=False)), \
         patch("landing.cache._run_one_readonly", new=run):
        resp = client.post("/api/landing/analyze", json={"tickers": ["ZZZZ"]})
    body = resp.json()
    assert body["invalid"] == ["ZZZZ"]
    assert body["results"] == []
    assert run.await_count == 0


def test_duplicates_are_collapsed():
    run = AsyncMock(side_effect=lambda t: _ok(t))
    with patch("routers.landing.validate_ticker", new=AsyncMock(return_value=True)), \
         patch("landing.cache._run_one_readonly", new=run):
        resp = client.post("/api/landing/analyze", json={"tickers": ["AAPL", "aapl"]})
    assert len(resp.json()["results"]) == 1
    assert run.await_count == 1


def test_one_failing_ticker_does_not_sink_the_others():
    async def flaky(t):
        if t == "BAD":
            raise RuntimeError("yahoo down")
        return _ok(t)

    with patch("routers.landing.validate_ticker", new=AsyncMock(return_value=True)), \
         patch("landing.cache._run_one_readonly", new=AsyncMock(side_effect=flaky)):
        resp = client.post("/api/landing/analyze", json={"tickers": ["AAPL", "BAD"]})
    body = resp.json()
    tickers = {r["ticker"]: r for r in body["results"]}
    assert tickers["AAPL"]["fair_value"]["value"] == 110.0
    assert tickers["BAD"]["errors"]
    assert tickers["BAD"]["quality"] is None
    # Controller addition 1: exception text must never reach a public page.
    assert "yahoo down" not in resp.text
    assert "RuntimeError" not in resp.text


# --- Fix round 1: a hung yfinance call must not wedge the whole request ---
def test_a_timed_out_ticker_does_not_sink_the_others():
    async def guarded(t):
        if t == "SLOW":
            raise asyncio.TimeoutError()
        return _ok(t)

    with patch("routers.landing.validate_ticker", new=AsyncMock(return_value=True)), \
         patch("landing.cache._run_one_readonly", new=AsyncMock(side_effect=guarded)):
        resp = client.post("/api/landing/analyze", json={"tickers": ["AAPL", "SLOW"]})
    body = resp.json()
    tickers = {r["ticker"]: r for r in body["results"]}
    assert tickers["AAPL"]["fair_value"]["value"] == 110.0
    assert tickers["SLOW"]["errors"] == ["Something went wrong calculating this ticker."]
    assert tickers["SLOW"]["quality"] is None
    assert "TimeoutError" not in resp.text


# --- Deployment spec §5.2: a per-IP brake on the live, expensive endpoint ---

def _post(ip: str):
    return client.post("/api/landing/analyze", json={"tickers": []},
                       headers={"x-forwarded-for": ip})


def test_one_ip_is_limited_with_a_readable_429_and_another_is_not(monkeypatch):
    monkeypatch.setattr(landing_router._limiter, "limit", 2)
    first, second, third = (_post("203.0.113.7") for _ in range(3))
    assert first.status_code == 200 and second.status_code == 200
    assert third.status_code == 429
    assert third.json() == {"results": [], "invalid": [],
                            "error": landing_router.RATE_LIMIT_MESSAGE}
    assert _post("198.51.100.9").status_code == 200


def test_a_forged_forwarded_for_prefix_does_not_dodge_the_landing_limit(monkeypatch):
    monkeypatch.setattr(landing_router._limiter, "limit", 2)
    codes = [client.post("/api/landing/analyze", json={"tickers": []},
                         headers={"x-forwarded-for": f"10.0.0.{i}, 203.0.113.7"}).status_code
             for i in range(3)]
    assert codes == [200, 200, 429]


def test_a_limited_request_never_reaches_the_engines(monkeypatch):
    monkeypatch.setattr(landing_router._limiter, "limit", 0)
    with patch("routers.landing.get_analysis", new=AsyncMock()) as ga,          patch("routers.landing.validate_ticker", new=AsyncMock(return_value=True)) as vt:
        resp = client.post("/api/landing/analyze", json={"tickers": ["AAPL"]})
    assert resp.status_code == 429
    ga.assert_not_awaited()
    vt.assert_not_awaited()


def test_the_default_limit_is_twenty_per_minute():
    assert landing_router._limiter.limit == 20
    assert landing_router._limiter.window_seconds == 60


def test_ticker_check_knows_a_listed_ticker():
    a, b = _list({"BRK.B": "BERKSHIRE HATHAWAY INC"})
    with a, b:
        r = client.get("/api/landing/ticker/brk-b")
    assert r.json() == {"ticker": "BRK.B", "known": True, "name": "BERKSHIRE HATHAWAY INC"}


def test_ticker_check_rejects_an_unlisted_ticker():
    a, b = _list({"NVDA": "NVIDIA CORP"})
    with a, b:
        r = client.get("/api/landing/ticker/XYZQ")
    assert r.json() == {"ticker": "XYZQ", "known": False, "name": None}


def test_ticker_check_rejects_a_malformed_ticker():
    a, b = _list({"NVDA": "NVIDIA CORP"})
    with a, b:
        r = client.get("/api/landing/ticker/a,b")
    assert r.json() == {"ticker": None, "known": False, "name": None}


def test_ticker_check_lets_a_valid_shape_through_when_the_list_is_down():
    a, b = _list(None)
    with a, b:
        r = client.get("/api/landing/ticker/NVDA")
    assert r.json() == {"ticker": "NVDA", "known": True, "name": None}


def test_ticker_check_is_rate_limited(monkeypatch):
    monkeypatch.setattr(landing_router._limiter, "limited", lambda key: True)
    r = client.get("/api/landing/ticker/NVDA")
    assert r.status_code == 429
