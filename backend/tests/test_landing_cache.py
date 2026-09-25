import asyncio
import time
from unittest.mock import patch, AsyncMock

import pytest

import landing.cache as cache
from risk_reward.models import RiskRewardInputs

# No module-level `pytestmark = pytest.mark.asyncio` here: pytest.ini's
# asyncio_mode = auto already collects the async def tests below without it, and this
# file also has two plain (non-async) unit tests -- a module-wide asyncio mark warns
# on those ("marked with @pytest.mark.asyncio but it is not an async function").


@pytest.fixture(autouse=True)
def _isolated_cache():
    cache._slow.clear()
    cache._fast.clear()
    cache._locks.clear()
    cache._lock_refs.clear()
    yield
    cache._slow.clear()
    cache._fast.clear()
    cache._locks.clear()
    cache._lock_refs.clear()


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


def _failed_run(ticker: str) -> dict:
    """What _run_one_guarded actually returns for a dead ticker or a Yahoo outage --
    it does not raise, it completes with a status="failed" dump and fv_failed=True,
    and (the genuine-failure case) no current_price: the ticker never resolved at
    all, so there is no price -- batch.py's own words for this discriminator."""
    return {
        "result": {
            "ticker": ticker, "company_name": None, "current_price": None,
            "stock_type": None, "fair_value": None, "price_vs_fair_value_pct": None,
            "fair_value_breakdown": {}, "status": "failed",
            "errors": ["yfinance data unavailable"], "screener": None, "risk_reward": None,
        },
        "fv_failed": True,
    }


def _declined_run(ticker: str, price: float = 42.0) -> dict:
    """What _run_one_guarded returns for a real company one of valuation/engine.py's
    guards declined to value (pre-profit guard / sub-floor EV-Sales guard /
    non-positive-composite clamp): fv_failed=True and status="failed", but with a
    real current_price, company_name, screener and risk_reward attached -- this is
    NOT a "no data" failure, and must not be negative-cached like one."""
    return {
        "result": {
            "ticker": ticker, "company_name": f"{ticker} Inc.", "current_price": price,
            "stock_type": "PRE_PROFIT", "fair_value": None, "price_vs_fair_value_pct": None,
            "fair_value_breakdown": {}, "status": "failed",
            "errors": ["pre-profit: growth insufficient to support a valuation"],
            "screener": {"ticker": ticker, "quality_score": 62.0, "status": "completed"},
            "risk_reward": {"ticker": ticker, "ratio": 1.1, "tier": "Balanced",
                             "metric_scores": {}, "status": "completed", "errors": []},
        },
        "fv_failed": True,
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
    # trailingPegRatio, not forwardPE, drives "valuation" here: yfinance commonly
    # ships trailingPegRatio without pegRatio, and "peg" is the *first* source in the
    # valuation fallback chain (config.py: ["peg", "earnings_yield", "ps_yield"]), so
    # a fixture that omits both peg keys (as this one once did) never actually
    # exercises the key production most often reads.
    inp = _inputs("AAA", price=cached_price, forward_pe=20.0, high_52w=120.0,
                  ma_200=90.0, rsi_val=55.0, volatility=0.3, beta=1.0,
                  extra_info={"trailingPegRatio": 1.2})

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

    # valuation resolves via "peg" (trailingPegRatio): raw = trailingPegRatio, and it
    # rescales by `ratio` same as forwardPE would.
    assert scores["valuation"]["source"] == "peg"
    assert scores["valuation"]["raw"] == pytest.approx(1.2 * ratio)

    # discount and trend are recomputed from the fresh price against the still-cached
    # 52-week high / 200-day MA.
    assert scores["discount"]["raw"] == pytest.approx((120.0 - fresh_price) / 120.0)
    assert scores["trend"]["raw"] == pytest.approx((fresh_price - 90.0) / 90.0)

    # rsi, volatility and beta are real series statistics -- untouched by a price refresh.
    assert scores["rsi"]["raw"] == pytest.approx(55.0)
    assert scores["volatility"]["raw"] == pytest.approx(0.3)
    assert scores["beta"]["raw"] == pytest.approx(1.0)


# --- 9b (extra). _rescale_inputs itself: all four price-derived keys, non-mutating ---
def test_rescale_inputs_covers_all_four_price_derived_keys_and_does_not_mutate():
    inp = RiskRewardInputs(
        ticker="AAA", info={
            "forwardPE": 20.0, "priceToSalesTrailing12Months": 5.0,
            "pegRatio": 1.5, "trailingPegRatio": 1.8, "beta": 1.0,
        },
        company_name="AAA Co", price=100.0, high_52w=120.0, ma_200=90.0,
        ma_50=None, rsi=55.0, volatility=0.3,
    )

    refreshed = cache._rescale_inputs(inp, 150.0)
    ratio = 1.5

    assert refreshed.info["forwardPE"] == pytest.approx(20.0 * ratio)
    assert refreshed.info["priceToSalesTrailing12Months"] == pytest.approx(5.0 * ratio)
    assert refreshed.info["pegRatio"] == pytest.approx(1.5 * ratio)
    assert refreshed.info["trailingPegRatio"] == pytest.approx(1.8 * ratio)
    assert refreshed.info["beta"] == pytest.approx(1.0)  # not price-derived: untouched
    assert refreshed.price == 150.0

    # The original snapshot must be untouched -- a fast refresh must not mutate the
    # slow layer's cached RiskRewardInputs out from under it.
    assert inp.price == 100.0
    assert inp.info["forwardPE"] == 20.0
    assert inp.info["pegRatio"] == 1.5
    assert inp.info["trailingPegRatio"] == 1.8


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


# --- 12 (fix round 2, finding 1). A *genuine* no-data failure is not pinned for the
# slow TTL -- current_price is None, so it's retried on SLOW_NEGATIVE_TTL instead. ---
async def test_a_genuine_failure_is_retried_after_the_slow_negative_ttl_not_three_days(monkeypatch):
    run = AsyncMock(side_effect=lambda t: _failed_run(t))
    fake_time = [0.0]
    monkeypatch.setattr(cache, "_now", lambda: fake_time[0])

    with _patched(run=run):
        first = await cache.get_analysis("DEAD")
        # Still inside the negative-cache window -- must not retry yet.
        fake_time[0] += cache.SLOW_NEGATIVE_TTL - 1
        await cache.get_analysis("DEAD")
        assert run.await_count == 1

        # Past the negative TTL, nowhere near the full 3-day slow TTL -- a genuine
        # failure must be retried here, not left pinned as truth until SLOW_TTL.
        fake_time[0] += 2
        second = await cache.get_analysis("DEAD")

    assert run.await_count == 2
    assert first["status"] == "failed"
    assert second["status"] == "failed"


# --- 12b (fix round 3, finding 1). A *declined-but-real* ticker (fv_failed=True, but
# current_price populated -- a legitimate valuation guard, not a data failure) keeps
# the full SLOW_TTL, not the negative cache. ---
async def test_a_declined_but_real_ticker_keeps_the_full_slow_ttl(monkeypatch):
    run = AsyncMock(side_effect=lambda t: _declined_run(t, price=42.0))
    fake_time = [0.0]
    monkeypatch.setattr(cache, "_now", lambda: fake_time[0])

    # quote pinned to the same 42.0: this test is about the *slow* layer's negative
    # cache, not the fast layer's own (separately tested) refresh cadence.
    with _patched(run=run, quote=AsyncMock(return_value=42.0)):
        first = await cache.get_analysis("PREPROFIT")
        # Well past what the negative cache would allow, still short of SLOW_TTL --
        # a decline that cannot change until the fundamentals do must NOT re-run here.
        fake_time[0] += cache.SLOW_NEGATIVE_TTL * 10
        second = await cache.get_analysis("PREPROFIT")
        assert run.await_count == 1

        # Past the full SLOW_TTL, it does retry, same as any other cached result.
        fake_time[0] += cache.SLOW_TTL
        await cache.get_analysis("PREPROFIT")

    assert run.await_count == 2
    assert first["status"] == "failed"
    assert first["current_price"] == 42.0
    assert second["current_price"] == 42.0
    # The screener/risk_reward attached to a legitimate decline must still be served,
    # not discarded because the fair-value leg alone reports "failed".
    assert first["screener"] is not None
    assert first["risk_reward"] is not None


# --- 13 (fix round 2, finding 3). A fast-refresh failure serves stale even if its own
# cache entry vanished mid-await (e.g. LRU-evicted by a concurrent request for a
# different ticker) -- the KeyError-on-move_to_end regression. ---
async def test_failed_fast_refresh_survives_its_own_entry_vanishing_mid_await():
    run = AsyncMock(side_effect=lambda t: _ok_run(t, price=100.0))
    inputs_fetch = AsyncMock(side_effect=lambda t: _inputs(t, price=100.0))
    fake_time = [0.0]

    with patch("landing.cache._now", lambda: fake_time[0]):
        with _patched(run=run, inputs_fetch=inputs_fetch, quote=AsyncMock(return_value=130.0)):
            await cache.get_analysis("AAA")
            fake_time[0] += cache.FAST_TTL + 1
            first = await cache.get_analysis("AAA")  # establishes a known fast entry

        assert first["current_price"] == 130.0

        async def vanish_then_fail(t):
            # Simulate a *different* ticker's concurrent get_analysis LRU-evicting
            # this entry (a different per-ticker lock, so nothing prevents this race)
            # while our own refresh is still in flight.
            cache._fast.pop("AAA", None)
            raise RuntimeError("yahoo down")

        fake_time[0] += cache.FAST_TTL + 1
        with _patched(run=run, inputs_fetch=inputs_fetch,
                      quote=AsyncMock(side_effect=vanish_then_fail)):
            second = await cache.get_analysis("AAA")  # must not raise KeyError

    assert second["current_price"] == first["current_price"] == 130.0
    assert second["risk_reward"] == first["risk_reward"]
    assert "AAA" in cache._fast  # correctly re-established, not left missing


# --- 14 (fix round 2, finding 9). A failed fast refresh's negative-cache backoff
# actually holds: a view inside FAST_NEGATIVE_TTL does not retry the failing quote
# again; one just past it does. ---
async def test_failed_fast_refresh_backs_off_for_the_negative_ttl_then_retries():
    run = AsyncMock(side_effect=lambda t: _ok_run(t, price=100.0))
    inputs_fetch = AsyncMock(side_effect=lambda t: _inputs(t, price=100.0))
    fake_time = [0.0]

    with patch("landing.cache._now", lambda: fake_time[0]):
        with _patched(run=run, inputs_fetch=inputs_fetch, quote=AsyncMock(return_value=130.0)):
            await cache.get_analysis("AAA")
            fake_time[0] += cache.FAST_TTL + 1
            await cache.get_analysis("AAA")  # establishes a real fast entry (130.0)

        # The fast layer now expires and the refresh fails -- this stamps a fresh ts
        # with failed=True per finding 9.
        fake_time[0] += cache.FAST_TTL + 1
        failing_quote = AsyncMock(side_effect=RuntimeError("yahoo down"))
        with _patched(run=run, inputs_fetch=inputs_fetch, quote=failing_quote):
            await cache.get_analysis("AAA")
        assert failing_quote.await_count == 1

        # Still inside the negative-cache backoff window -- must not retry yet, even
        # though the entry's ts is long past what FAST_TTL alone would allow.
        fake_time[0] += cache.FAST_NEGATIVE_TTL - 1
        with _patched(run=run, inputs_fetch=inputs_fetch, quote=failing_quote):
            await cache.get_analysis("AAA")
        assert failing_quote.await_count == 1

        # Past the negative-cache backoff -- retries.
        fake_time[0] += 2
        with _patched(run=run, inputs_fetch=inputs_fetch, quote=failing_quote):
            await cache.get_analysis("AAA")
        assert failing_quote.await_count == 2
