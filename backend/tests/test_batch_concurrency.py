"""Recalculate-All flow-control guards.

The old run_batch fired a whole group of tickers at once and then awaited them in
submission order, so (a) it dumped ~100 blocking yfinance fetches on Yahoo per group
with no pacing (progressive rate-limit throttling), and (b) one slow/stuck ticker at
the head of a group blocked the emission of every finished ticker behind it — the UI
counter froze even while work was happening. These tests pin the replacement:
bounded concurrency, completion-order emission, per-ticker timeout, and pacing.
"""
import asyncio
import pytest
from orchestrator import batch


def _ok(ticker: str) -> dict:
    return {"result": {"ticker": ticker, "status": "completed",
                       "screener": {"status": "completed"}}, "fv_failed": False}


@pytest.mark.asyncio
async def test_run_batch_respects_concurrency_limit(monkeypatch):
    monkeypatch.setattr(batch, "MAX_CONCURRENCY", 2)
    monkeypatch.setattr(batch, "PACING_SECONDS", 0.0)
    current = 0
    max_seen = 0

    async def fake_run_one(ticker):
        nonlocal current, max_seen
        current += 1
        max_seen = max(max_seen, current)
        await asyncio.sleep(0.05)
        current -= 1
        return _ok(ticker)

    monkeypatch.setattr(batch, "_run_one", fake_run_one)
    tickers = [f"T{i}" for i in range(6)]
    events = [e async for e in batch.run_batch(tickers, "job", asyncio.Event())]
    done = [e for e in events if e["type"] == "ticker_done"]
    assert len(done) == 6                     # every ticker still processed
    assert max_seen <= 2                       # never more than the limit in flight


@pytest.mark.asyncio
async def test_run_batch_emits_in_completion_order(monkeypatch):
    """A fast ticker submitted AFTER a slow one must be reported first — this is the
    head-of-line-blocking fix that stops the progress counter from freezing."""
    monkeypatch.setattr(batch, "MAX_CONCURRENCY", 2)
    monkeypatch.setattr(batch, "PACING_SECONDS", 0.0)
    delays = {"SLOW": 0.2, "FAST": 0.02}

    async def fake_run_one(ticker):
        await asyncio.sleep(delays.get(ticker, 0.0))
        return _ok(ticker)

    monkeypatch.setattr(batch, "_run_one", fake_run_one)
    events = [e async for e in batch.run_batch(["SLOW", "FAST"], "job", asyncio.Event())]
    done_order = [e["ticker"] for e in events if e["type"] == "ticker_done"]
    assert done_order == ["FAST", "SLOW"]


@pytest.mark.asyncio
async def test_run_batch_emits_ticker_start_before_done(monkeypatch):
    """ticker_start drives the live 'now evaluating' indicator; each must precede
    its ticker_done."""
    monkeypatch.setattr(batch, "PACING_SECONDS", 0.0)

    async def fake_run_one(ticker):
        return _ok(ticker)

    monkeypatch.setattr(batch, "_run_one", fake_run_one)
    events = [e async for e in batch.run_batch(["AAA", "BBB"], "job", asyncio.Event())]
    starts = sorted(e["ticker"] for e in events if e["type"] == "ticker_start")
    assert starts == ["AAA", "BBB"]
    for t in ("AAA", "BBB"):
        si = next(i for i, e in enumerate(events)
                  if e["type"] == "ticker_start" and e["ticker"] == t)
        di = next(i for i, e in enumerate(events)
                  if e["type"] == "ticker_done" and e["ticker"] == t)
        assert si < di


@pytest.mark.asyncio
async def test_run_batch_times_out_a_wedged_ticker(monkeypatch):
    """A hung fetch (a stuck socket holding a pool thread) must not freeze the batch:
    the ticker fails fast via PER_TICKER_TIMEOUT and the run completes."""
    monkeypatch.setattr(batch, "PER_TICKER_TIMEOUT", 0.05)
    monkeypatch.setattr(batch, "PACING_SECONDS", 0.0)

    async def hung_run_one(ticker):
        await asyncio.sleep(10)
        return _ok(ticker)

    monkeypatch.setattr(batch, "_run_one", hung_run_one)
    events = [e async for e in batch.run_batch(["HUNG"], "job", asyncio.Event())]
    kinds = [e["type"] for e in events]
    assert "ticker_error" in kinds
    assert kinds[-1] == "job_done"
    assert [e for e in events if e["type"] == "job_done"][0]["failed"] == 1


@pytest.mark.asyncio
async def test_run_batch_cancel_before_start_processes_nothing(monkeypatch):
    monkeypatch.setattr(batch, "PACING_SECONDS", 0.0)

    async def fake_run_one(ticker):
        return _ok(ticker)

    monkeypatch.setattr(batch, "_run_one", fake_run_one)
    ev = asyncio.Event()
    ev.set()
    events = [e async for e in batch.run_batch(["AAA", "BBB"], "job", ev)]
    job_done = [e for e in events if e["type"] == "job_done"][0]
    assert job_done["status"] == "cancelled"
    assert not any(e["type"] == "ticker_done" for e in events)


@pytest.mark.asyncio
async def test_pacing_delay_widens_under_rate_limit_pressure(monkeypatch):
    """The inter-ticker pacing must stretch while yfinance rate-limit pressure is
    observed — the adaptive-slowdown valve that stops progressive throttling."""
    monkeypatch.setattr(batch, "PACING_SECONDS", 0.5)
    monkeypatch.setattr(batch, "PACING_PRESSURE_MULT", 6.0)
    monkeypatch.setattr(batch, "rate_limit_pressure", lambda: False)
    assert batch._pacing_delay() == pytest.approx(0.5)
    monkeypatch.setattr(batch, "rate_limit_pressure", lambda: True)
    assert batch._pacing_delay() == pytest.approx(3.0)
