import asyncio
import time
from unittest.mock import patch, AsyncMock

import pytest

import landing.cache as cache
from risk_reward.models import RiskRewardInputs

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _isolated_cache():
    cache._slow.clear()
    cache._fast.clear()
    cache._locks.clear()
    yield
    cache._slow.clear()
    cache._fast.clear()
    cache._locks.clear()


def _ok_run(ticker: str, price: float = 100.0, fair_value: float = 110.0) -> dict:
    pct = round((fair_value - price) / price * 100, 2) if price else None
    return {
        "result": {
            "ticker": ticker, "company_name": f"{ticker} Inc.", "current_price": price,
            "stock_type": "MEGA_CAP", "fair_value": fair_value,
            "price_vs_fair_value_pct": pct,
            "fair_value_breakdown": {"dcf": {"fair_value": fair_value, "weight": 1.0}},
            "status": "completed", "errors": [],
            "screener": None,
            "risk_reward": {"ticker": ticker, "ratio": 1.5, "tier": "Balanced",
                             "metric_scores": {}, "status": "completed", "errors": []},
        },
        "fv_failed": False,
    }


def _inputs(ticker: str = "AAA", price: float = 100.0, forward_pe: float | None = 20.0,
           high_52w: float | None = 120.0, ma_200: float | None = 90.0,
           rsi_val: float | None = 55.0, volatility: float | None = 0.3,
           beta: float | None = 1.0, extra_info: dict | None = None) -> RiskRewardInputs:
    info = {"forwardPE": forward_pe, "beta": beta}
    if extra_info:
        info.update(extra_info)
    return RiskRewardInputs(
        ticker=ticker, info=info, company_name=f"{ticker} Co", price=price,
        high_52w=high_52w, ma_200=ma_200, ma_50=None, rsi=rsi_val, volatility=volatility,
    )


def _patched(run=None, inputs_fetch=None, quote=None):
    run = run if run is not None else AsyncMock(side_effect=lambda t: _ok_run(t))
    inputs_fetch = inputs_fetch if inputs_fetch is not None else AsyncMock(side_effect=lambda t: _inputs(t))
    quote = quote if quote is not None else AsyncMock(return_value=100.0)
    return patch.multiple(
        cache,
        _run_one_guarded=run,
        fetch_risk_reward_inputs=inputs_fetch,
        fetch_quote=quote,
    )


# --- 1. Second call within the slow TTL does not re-run the engines ---
async def test_second_call_within_slow_ttl_does_not_rerun_engines():
    run = AsyncMock(side_effect=lambda t: _ok_run(t))
    with _patched(run=run):
        first = await cache.get_analysis("AAA")
        second = await cache.get_analysis("AAA")

    assert run.await_count == 1
    assert second["fair_value"] == first["fair_value"]
    assert second["stock_type"] == first["stock_type"]
    assert second["company_name"] == first["company_name"]


# --- 2. A slow entry past its TTL does re-run ---
async def test_slow_entry_past_ttl_reruns_engines(monkeypatch):
    run = AsyncMock(side_effect=lambda t: _ok_run(t))
    fake_time = [1_000.0]
    monkeypatch.setattr(cache, "_now", lambda: fake_time[0])

    with _patched(run=run):
        await cache.get_analysis("AAA")
        fake_time[0] += cache.SLOW_TTL + 1
        await cache.get_analysis("AAA")

    assert run.await_count == 2


# --- 3. A fast entry past its TTL refreshes price and Reward/Risk only ---
async def test_fast_entry_past_ttl_refreshes_price_and_reward_risk_only(monkeypatch):
    run = AsyncMock(side_effect=lambda t: _ok_run(t, price=100.0, fair_value=110.0))
    inputs_fetch = AsyncMock(side_effect=lambda t: _inputs(t, price=100.0, forward_pe=20.0))
    quote = AsyncMock(return_value=150.0)
    fake_time = [0.0]
    monkeypatch.setattr(cache, "_now", lambda: fake_time[0])

    with _patched(run=run, inputs_fetch=inputs_fetch, quote=quote):
        first = await cache.get_analysis("AAA")
        fake_time[0] += cache.FAST_TTL + 1
        second = await cache.get_analysis("AAA")

    # The slow layer (fundamentals) never re-ran for the fast refresh.
    assert run.await_count == 1
    # The fast refresh did happen: one quote call for the TTL expiry (cold-fill
    # seeds the fast layer from the same snapshot, with no quote call of its own).
    assert quote.await_count == 1
    assert second["current_price"] == 150.0
    assert first["current_price"] == 100.0
    # Reward/Risk actually moved (recomputed from the rescaled inputs), not just echoed.
    assert second["risk_reward"] != first["risk_reward"]


# --- 4. % vs Price is recomputed from the fresh price, not served stale ---
async def test_pct_vs_price_recomputed_from_fresh_price(monkeypatch):
    run = AsyncMock(side_effect=lambda t: _ok_run(t, price=100.0, fair_value=120.0))
    inputs_fetch = AsyncMock(side_effect=lambda t: _inputs(t, price=100.0))
    quote = AsyncMock(return_value=80.0)
    fake_time = [0.0]
    monkeypatch.setattr(cache, "_now", lambda: fake_time[0])

    with _patched(run=run, inputs_fetch=inputs_fetch, quote=quote):
        first = await cache.get_analysis("AAA")
        fake_time[0] += cache.FAST_TTL + 1
        second = await cache.get_analysis("AAA")

    expected = round((120.0 - 80.0) / 80.0 * 100, 2)
    assert second["price_vs_fair_value_pct"] == expected
    assert second["price_vs_fair_value_pct"] != first["price_vs_fair_value_pct"]


# --- 5. A failed fast refresh serves the stale entry ---
async def test_failed_fast_refresh_serves_stale(monkeypatch):
    run = AsyncMock(side_effect=lambda t: _ok_run(t, price=100.0))
    inputs_fetch = AsyncMock(side_effect=lambda t: _inputs(t, price=100.0))
    fake_time = [0.0]
    monkeypatch.setattr(cache, "_now", lambda: fake_time[0])

    # Cold-fill (seeds the fast layer from the run's own price, no quote call yet),
    # then one real, successful fast refresh to establish a known fast-layer value.
    with _patched(run=run, inputs_fetch=inputs_fetch,
                  quote=AsyncMock(return_value=130.0)):
        await cache.get_analysis("AAA")
        fake_time[0] += cache.FAST_TTL + 1
        first = await cache.get_analysis("AAA")

    assert first["current_price"] == 130.0

    # Now the fast layer expires again and the refresh itself fails outright.
    fake_time[0] += cache.FAST_TTL + 1
    with _patched(run=run, inputs_fetch=inputs_fetch,
                  quote=AsyncMock(side_effect=RuntimeError("yahoo down"))):
        second = await cache.get_analysis("AAA")  # must not raise

    assert second["current_price"] == first["current_price"] == 130.0
    assert second["risk_reward"] == first["risk_reward"]


# --- 6. LRU eviction ---
async def test_lru_eviction_keeps_the_recently_read_entry():
    with _patched():
        await cache.get_analysis("T0")
        for i in range(1, cache.MAX_ENTRIES):
            await cache.get_analysis(f"T{i}")
        # Read T0 again before overflowing -- it becomes the most-recently-used.
        await cache.get_analysis("T0")
        # One more distinct ticker overflows capacity.
        await cache.get_analysis(f"T{cache.MAX_ENTRIES}")

    assert cache.cache_stats()["slow"] == cache.MAX_ENTRIES
    assert "T0" in cache._slow          # survived: it was re-read
    assert "T1" not in cache._slow      # least-recently-read: evicted


# --- 7. Seeding never raises ---
async def test_seed_never_raises_and_leaves_cache_empty_on_total_failure():
    run = AsyncMock(side_effect=RuntimeError("boom"))
    inputs_fetch = AsyncMock(side_effect=RuntimeError("boom"))

    with _patched(run=run, inputs_fetch=inputs_fetch):
        await cache.seed(["AAA", "BBB"])  # must not raise

    assert cache.cache_stats() == {"slow": 0, "fast": 0}


# --- 8 (extra). Concurrent cold requests for the same ticker single-flight ---
async def test_concurrent_cold_requests_do_not_double_run():
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_run(t):
        started.set()
        await release.wait()
        return _ok_run(t)

    run = AsyncMock(side_effect=slow_run)

    with _patched(run=run):
        task1 = asyncio.create_task(cache.get_analysis("AAA"))
        await started.wait()
        task2 = asyncio.create_task(cache.get_analysis("AAA"))
        await asyncio.sleep(0)  # let task2 reach and block on the per-ticker lock
        release.set()
        r1, r2 = await asyncio.gather(task1, task2)

    assert run.await_count == 1
    assert r1["fair_value"] == r2["fair_value"]


# --- 9 (extra). Price-derived info is rescaled exactly; series stats are not ---
async def test_fast_refresh_rescales_price_derived_info_only():
    cached_price = 100.0
    fresh_price = 150.0
    ratio = fresh_price / cached_price
    inp = _inputs("AAA", price=cached_price, forward_pe=20.0, high_52w=120.0,
                  ma_200=90.0, rsi_val=55.0, volatility=0.3, beta=1.0)

    run = AsyncMock(side_effect=lambda t: _ok_run(t, price=cached_price))
    inputs_fetch = AsyncMock(return_value=inp)
    quote = AsyncMock(return_value=fresh_price)
    fake_time = [0.0]

    with patch("landing.cache._now", lambda: fake_time[0]):
        with _patched(run=run, inputs_fetch=inputs_fetch, quote=quote):
            await cache.get_analysis("AAA")
            fake_time[0] += cache.FAST_TTL + 1
            result = await cache.get_analysis("AAA")

    scores = result["risk_reward"]["metric_scores"]

    # valuation resolves via earnings_yield here (no pegRatio present): raw = 1/forwardPE.
    # forwardPE rescales by `ratio`, so the raw halves-and-a-bit (1/(20*1.5)).
    assert scores["valuation"]["source"] == "earnings_yield"
    assert scores["valuation"]["raw"] == pytest.approx(1.0 / (20.0 * ratio))

    # discount and trend are recomputed from the fresh price against the still-cached
    # 52-week high / 200-day MA.
    assert scores["discount"]["raw"] == pytest.approx((120.0 - fresh_price) / 120.0)
    assert scores["trend"]["raw"] == pytest.approx((fresh_price - 90.0) / 90.0)

    # rsi, volatility and beta are real series statistics -- untouched by a price refresh.
    assert scores["rsi"]["raw"] == pytest.approx(55.0)
    assert scores["volatility"]["raw"] == pytest.approx(0.3)
    assert scores["beta"]["raw"] == pytest.approx(1.0)


# --- 10 (fix round 1). The fast layer's quote comes from fetch_quote, never the
# @lru_cache'd fetch_ticker_info -- this is the test that would have caught the
# frozen-price bug the coordinator flagged. ---
async def test_fast_refresh_uses_fetch_quote_not_fetch_ticker_info(monkeypatch):
    run = AsyncMock(side_effect=lambda t: _ok_run(t, price=100.0))
    inputs_fetch = AsyncMock(side_effect=lambda t: _inputs(t, price=100.0))
    quote = AsyncMock(return_value=140.0)
    ticker_info = AsyncMock(return_value={"currentPrice": 999.0})  # must never be seen
    fake_time = [0.0]
    monkeypatch.setattr(cache, "_now", lambda: fake_time[0])

    with patch("landing.cache.fetch_ticker_info", new=ticker_info, create=True):
        with _patched(run=run, inputs_fetch=inputs_fetch, quote=quote):
            await cache.get_analysis("AAA")
            fake_time[0] += cache.FAST_TTL + 1
            result = await cache.get_analysis("AAA")

    assert quote.await_count == 1
    assert ticker_info.await_count == 0
    assert result["current_price"] == 140.0


# --- 11 (fix round 1). Nothing memoizes the fast-layer quote between refreshes:
# two TTL-boundary refreshes with a changed underlying quote return two different
# prices. ---
async def test_successive_fast_refreshes_are_not_memoized():
    run = AsyncMock(side_effect=lambda t: _ok_run(t, price=100.0))
    inputs_fetch = AsyncMock(side_effect=lambda t: _inputs(t, price=100.0))
    prices = iter([111.0, 222.0])
    quote = AsyncMock(side_effect=lambda t: next(prices))
    fake_time = [0.0]

    with patch("landing.cache._now", lambda: fake_time[0]):
        with _patched(run=run, inputs_fetch=inputs_fetch, quote=quote):
            await cache.get_analysis("AAA")  # cold-fill: seeds fast from the run's own price
            fake_time[0] += cache.FAST_TTL + 1
            first_refresh = await cache.get_analysis("AAA")
            fake_time[0] += cache.FAST_TTL + 1
            second_refresh = await cache.get_analysis("AAA")

    assert first_refresh["current_price"] == 111.0
    assert second_refresh["current_price"] == 222.0
    assert first_refresh["current_price"] != second_refresh["current_price"]
