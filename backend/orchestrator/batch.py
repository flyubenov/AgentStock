from __future__ import annotations
import asyncio, os
from collections.abc import AsyncGenerator
from valuation.engine import run as engine_run
from screener.engine import run as screener_run
from risk_reward.engine import run as risk_reward_run
from services.sheets import upsert_result
from services.screener_sheets import upsert_screener_result
from services.risk_reward_sheets import upsert_risk_reward_result
from services.yf_pool import rate_limit_pressure
from models import TickerResult

# How many tickers evaluate at once. Kept small on purpose: each ticker fans ~10
# blocking yfinance fetches onto the bounded yf_pool, so a high number just trips
# Yahoo's per-IP rate limit and the whole run slows to a crawl and then freezes.
MAX_CONCURRENCY = int(os.getenv("RECALC_CONCURRENCY", "3"))
# Base delay a worker waits after finishing a ticker before taking the next, so a
# large run paces itself instead of hammering Yahoo. Widened automatically while
# rate-limit pressure is observed (see _pacing_delay).
PACING_SECONDS = float(os.getenv("RECALC_PACING_SECONDS", "0.4"))
PACING_PRESSURE_MULT = float(os.getenv("RECALC_PACING_PRESSURE_MULT", "6.0"))
# Hard ceiling on a single ticker so one wedged fetch (a hung socket holding a pool
# thread) can never freeze the whole batch — it fails fast and the run moves on.
PER_TICKER_TIMEOUT = float(os.getenv("RECALC_TICKER_TIMEOUT", "120"))


def _pacing_delay() -> float:
    """Inter-ticker pacing, stretched while Yahoo is throttling us."""
    return PACING_SECONDS * (PACING_PRESSURE_MULT if rate_limit_pressure() else 1.0)


async def _run_one(ticker: str) -> dict:
    """Run all three pipelines for one ticker; upsert FV first (so the Database row
    exists for the Q/R mirrors), then the screener, then risk-reward. No pipeline's
    failure aborts another — each is gathered with return_exceptions and its write is
    independently guarded."""
    fv_task = asyncio.create_task(engine_run(ticker))
    sc_task = asyncio.create_task(screener_run(ticker))
    rr_task = asyncio.create_task(risk_reward_run(ticker))
    fv_res, sc_res, rr_res = await asyncio.gather(
        fv_task, sc_task, rr_task, return_exceptions=True)

    errors = []
    fv_dump = None
    if isinstance(fv_res, Exception):
        errors.append(f"fair_value: {fv_res}")
    else:
        fv_dump = fv_res.model_dump()
        # Persist to the Database when the FV succeeded, or when a guard DECLINED a
        # real company: it still carries identity + a valid Quality Score, so it must
        # get a Database row (blank Fair Value) to appear in the grid and receive the
        # column-Q score mirror. True failures (no data — the ticker never resolved,
        # so there is no price) are skipped.
        #
        # The test is identity, not tier name. This was keyed to the literal
        # "PRE_PROFIT", which silently assumed every decline rewrites stock_type to
        # that string. The pre-profit guard does; the sub-floor EV/Sales guard and the
        # non-positive-composite clamp deliberately keep the real tier. Those declines
        # skipped the upsert, leaving Sheets holding the very fair value the guard had
        # just rejected — ASTS kept serving $1.15 after the engine declined it, and no
        # amount of recalculating could clear it. A stale row is worse than a blank one.
        if fv_res.status != "failed" or fv_res.current_price is not None:
            try:
                await upsert_result(fv_res)
            except Exception as e:
                errors.append(f"sheets_write: {e}")

    sc_dump = None
    if isinstance(sc_res, Exception):
        errors.append(f"screener: {sc_res}")
    else:
        sc_dump = sc_res.model_dump()
        if sc_res.status != "failed":
            try:
                await upsert_screener_result(sc_res)
            except Exception as e:
                errors.append(f"screener_write: {e}")

    # Risk-Reward: a third, fully isolated pipeline. Only a "completed" result is
    # persisted — a "failed" (no data) or "insufficient_data" (coverage floor) result
    # is attached to the payload but never written, so the mirror column stays blank
    # rather than showing a fabricated ratio.
    rr_dump = None
    if isinstance(rr_res, Exception):
        errors.append(f"risk_reward: {rr_res}")
    else:
        rr_dump = rr_res.model_dump()
        if rr_res.status == "completed":
            try:
                await upsert_risk_reward_result(rr_res)
            except Exception as e:
                errors.append(f"risk_reward_write: {e}")

    if fv_dump is None:
        fv_dump = TickerResult(ticker=ticker.upper(), status="failed", errors=errors).model_dump()
    else:
        fv_dump.setdefault("errors", []).extend(errors)
    fv_dump["screener"] = sc_dump
    fv_dump["risk_reward"] = rr_dump
    fv_failed = fv_dump.get("status") == "failed"
    return {"result": fv_dump, "fv_failed": fv_failed}


async def _run_one_guarded(ticker: str) -> dict:
    """_run_one with a hard timeout so a hung yfinance call can't wedge the batch.
    On timeout asyncio raises TimeoutError, which the worker turns into a
    ticker_error — the ticker fails fast and the run keeps going."""
    return await asyncio.wait_for(_run_one(ticker), PER_TICKER_TIMEOUT)


async def run_batch(tickers: list[str], job_id: str,
                    cancel_event: asyncio.Event) -> AsyncGenerator[dict, None]:
    """Evaluate tickers through a small fixed pool of workers, emitting each result
    the moment it finishes (completion order, not submission order).

    The previous design fired a whole group at once and awaited them in submission
    order: it stampeded Yahoo with no pacing (progressive rate-limit throttling) and
    let one slow/stuck ticker at the head of a group block the emission of every
    finished ticker behind it, freezing the progress counter. Bounded concurrency +
    adaptive pacing + completion-order emission + a per-ticker timeout fix both."""
    total = len(tickers)
    completed = 0
    failed = 0
    yield {"type": "job_start", "job_id": job_id, "total": total}

    work: asyncio.Queue[str] = asyncio.Queue()
    for t in tickers:
        work.put_nowait(t)
    events: asyncio.Queue = asyncio.Queue()
    n_workers = max(1, min(MAX_CONCURRENCY, total)) if total else 0

    async def worker() -> None:
        while True:
            try:
                ticker = work.get_nowait()
            except asyncio.QueueEmpty:
                return
            if cancel_event.is_set():
                continue  # drain the remaining queue without processing
            await events.put(("ticker_start", ticker, None))
            try:
                out = await _run_one_guarded(ticker)
                await events.put(("ticker_done", ticker, out))
            except Exception as e:
                await events.put(("ticker_error", ticker, str(e)))
            if not cancel_event.is_set():
                await asyncio.sleep(_pacing_delay())

    workers = [asyncio.create_task(worker()) for _ in range(n_workers)]

    async def _sentinel() -> None:
        await asyncio.gather(*workers)
        await events.put(("__done__", None, None))

    sentinel = asyncio.create_task(_sentinel())

    while True:
        kind, ticker, payload = await events.get()
        if kind == "__done__":
            break
        if kind == "ticker_start":
            yield {"type": "ticker_start", "ticker": ticker}
        elif kind == "ticker_done":
            out = payload
            sc = out["result"].get("screener")
            sc_failed = sc is None or sc.get("status") == "failed"
            if out["fv_failed"] and sc_failed:
                failed += 1
            else:
                completed += 1
            yield {"type": "ticker_done", "ticker": ticker, "result": out["result"]}
        elif kind == "ticker_error":
            failed += 1
            yield {"type": "ticker_error", "ticker": ticker, "error": payload}

    await sentinel
    status = "cancelled" if cancel_event.is_set() else "completed"
    yield {"type": "job_done", "job_id": job_id, "completed": completed,
           "failed": failed, "status": status}
