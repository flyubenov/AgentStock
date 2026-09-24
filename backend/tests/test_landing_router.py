import asyncio
from unittest.mock import patch, AsyncMock
import pytest
from fastapi.testclient import TestClient
from main import app
import landing.cache as cache_mod

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
    with patch("landing.cache.fetch_risk_reward_inputs",
               new=AsyncMock(side_effect=RuntimeError("no network in tests"))), \
         patch("landing.cache.fetch_quote",
               new=AsyncMock(side_effect=RuntimeError("no network in tests"))):
        yield
    cache_mod._slow.clear()
    cache_mod._fast.clear()
    cache_mod._locks.clear()


def _ok(ticker: str) -> dict:
    return {"result": {"ticker": ticker, "company_name": f"{ticker} Inc.",
                       "current_price": 100.0, "stock_type": "MEGA_CAP",
                       "fair_value": 110.0, "price_vs_fair_value_pct": 10.0,
                       "fair_value_breakdown": {"dcf": {"fair_value": 110.0, "weight": 1.0}},
                       "status": "completed", "errors": [],
                       "screener": None, "risk_reward": None}}


def test_a_single_ticker_comes_back_mapped():
    with patch("routers.landing.validate_ticker", new=AsyncMock(return_value=True)), \
         patch("landing.cache._run_one_guarded", new=AsyncMock(side_effect=lambda t: _ok(t))):
        resp = client.post("/api/landing/analyze", json={"tickers": ["aapl"]})
    body = resp.json()
    assert [r["ticker"] for r in body["results"]] == ["AAPL"]
    assert body["results"][0]["fair_value"]["value"] == 110.0


# --- Review Focus 4: too many tickers, empty input, unresolvable ticker ---
def test_more_than_three_tickers_are_rejected_before_any_engine_runs():
    run = AsyncMock(side_effect=lambda t: _ok(t))
    validate = AsyncMock(return_value=True)
    with patch("landing.cache._run_one_guarded", new=run), \
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
         patch("landing.cache._run_one_guarded", new=run):
        resp = client.post("/api/landing/analyze", json={"tickers": ["ZZZZ"]})
    body = resp.json()
    assert body["invalid"] == ["ZZZZ"]
    assert body["results"] == []
    assert run.await_count == 0


def test_duplicates_are_collapsed():
    run = AsyncMock(side_effect=lambda t: _ok(t))
    with patch("routers.landing.validate_ticker", new=AsyncMock(return_value=True)), \
         patch("landing.cache._run_one_guarded", new=run):
        resp = client.post("/api/landing/analyze", json={"tickers": ["AAPL", "aapl"]})
    assert len(resp.json()["results"]) == 1
    assert run.await_count == 1


def test_one_failing_ticker_does_not_sink_the_others():
    async def flaky(t):
        if t == "BAD":
            raise RuntimeError("yahoo down")
        return _ok(t)

    with patch("routers.landing.validate_ticker", new=AsyncMock(return_value=True)), \
         patch("landing.cache._run_one_guarded", new=AsyncMock(side_effect=flaky)):
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
         patch("landing.cache._run_one_guarded", new=AsyncMock(side_effect=guarded)):
        resp = client.post("/api/landing/analyze", json={"tickers": ["AAPL", "SLOW"]})
    body = resp.json()
    tickers = {r["ticker"]: r for r in body["results"]}
    assert tickers["AAPL"]["fair_value"]["value"] == 110.0
    assert tickers["SLOW"]["errors"] == ["Something went wrong calculating this ticker."]
    assert tickers["SLOW"]["quality"] is None
    assert "TimeoutError" not in resp.text
