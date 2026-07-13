import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest


def test_yf_executor_is_bounded_and_not_the_default():
    """yfinance work runs on a dedicated, size-bounded pool — never the shared
    default asyncio executor. This is what stops a rate-limited batch (whose
    retry backoff sleeps hold worker threads) from starving FastAPI/Starlette and
    freezing the whole server."""
    from services.yf_pool import _EXECUTOR, YF_MAX_WORKERS

    assert isinstance(_EXECUTOR, ThreadPoolExecutor)
    assert _EXECUTOR._max_workers == YF_MAX_WORKERS
    assert YF_MAX_WORKERS >= 1


@pytest.mark.asyncio
async def test_saturated_yf_pool_leaves_default_executor_responsive():
    """Regression guard for the whole-server freeze: even with every yfinance
    worker blocked, work submitted to the default executor still runs promptly."""
    from services.yf_pool import run_yf, YF_MAX_WORKERS

    release = threading.Event()

    def block():
        release.wait(timeout=10)
        return "blocked"

    # Occupy every worker in the dedicated yfinance pool.
    yf_tasks = [asyncio.create_task(run_yf(block)) for _ in range(YF_MAX_WORKERS)]
    await asyncio.sleep(0.2)  # let them all grab a worker
    try:
        loop = asyncio.get_event_loop()
        t0 = time.time()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: "ok"), timeout=2.0
        )
        assert result == "ok"
        assert time.time() - t0 < 2.0
    finally:
        release.set()
        await asyncio.gather(*yf_tasks)


@pytest.mark.asyncio
async def test_fetch_ticker_info_runs_on_the_yf_pool():
    """The info fetch must go through the dedicated pool wrapper, not the default
    executor directly."""
    from unittest.mock import patch
    import services.yahoo as yahoo

    seen = {}

    async def fake_run_yf(fn, *args):
        seen["fn"] = fn
        seen["args"] = args
        return {"symbol": "AAPL"}

    with patch("services.yahoo.run_yf", side_effect=fake_run_yf):
        out = await yahoo.fetch_ticker_info("aapl")

    assert out == {"symbol": "AAPL"}
    assert seen["fn"] is yahoo._fetch_sync
    assert seen["args"] == ("AAPL",)


def test_rate_limit_backoff_is_bounded():
    """Worst-case total backoff for a single fetch must stay small (a few seconds),
    never regressing to the 48s that let a rate-limited batch wedge the pool."""
    from services import yahoo, statements

    def total_backoff(base: float, retries: int) -> float:
        # sleeps happen on attempts 0..retries-2 (the last attempt doesn't sleep)
        return sum(base * (attempt + 1) for attempt in range(retries - 1))

    assert total_backoff(yahoo._RATE_LIMIT_BACKOFF, yahoo._RATE_LIMIT_RETRIES) <= 12.0
    assert total_backoff(statements._BACKOFF, statements._RETRIES) <= 12.0


def test_fetch_sync_backoff_sleeps_are_capped(monkeypatch):
    """Drive the actual retry loop under a simulated rate-limit and assert the real
    sleep calls never exceed the bounded schedule."""
    import services.yahoo as yahoo

    yahoo._fetch_sync.cache_clear()
    sleeps: list[float] = []
    monkeypatch.setattr(yahoo.time, "sleep", lambda s: sleeps.append(s))

    class _RateLimited(Exception):
        pass

    def always_rate_limited(_ticker):
        raise _RateLimited("Too Many Requests: rate limited")

    monkeypatch.setattr(yahoo.yf, "Ticker", lambda t: (_ for _ in ()).throw(_RateLimited("rate limit")))

    with pytest.raises(Exception):
        yahoo._fetch_sync("ZZZZ")

    yahoo._fetch_sync.cache_clear()
    assert sum(sleeps) <= 12.0
    assert max(sleeps, default=0) <= 8.0
