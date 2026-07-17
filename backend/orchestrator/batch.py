from __future__ import annotations
import asyncio, os
from collections.abc import AsyncGenerator
from valuation.engine import run as engine_run
from screener.engine import run as screener_run
from services.sheets import upsert_result
from services.screener_sheets import upsert_screener_result
from models import TickerResult

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))


async def _run_one(ticker: str) -> dict:
    """Run both pipelines for one ticker; upsert FV first (so the Database row
    exists for the Q mirror), then the screener. Neither failure aborts the other."""
    fv_task = asyncio.create_task(engine_run(ticker))
    sc_task = asyncio.create_task(screener_run(ticker))
    fv_res, sc_res = await asyncio.gather(fv_task, sc_task, return_exceptions=True)

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

    if fv_dump is None:
        fv_dump = TickerResult(ticker=ticker.upper(), status="failed", errors=errors).model_dump()
    else:
        fv_dump.setdefault("errors", []).extend(errors)
    fv_dump["screener"] = sc_dump
    fv_failed = fv_dump.get("status") == "failed"
    return {"result": fv_dump, "fv_failed": fv_failed}


async def run_batch(tickers: list[str], job_id: str,
                    cancel_event: asyncio.Event) -> AsyncGenerator[dict, None]:
    total = len(tickers)
    completed = 0
    failed = 0
    yield {"type": "job_start", "job_id": job_id, "total": total}

    groups = [tickers[i:i + BATCH_SIZE] for i in range(0, len(tickers), BATCH_SIZE)]
    for group in groups:
        if cancel_event.is_set():
            break
        tasks = {t: asyncio.create_task(_run_one(t)) for t in group}
        for ticker, task in tasks.items():
            yield {"type": "ticker_start", "ticker": ticker}
            try:
                out = await task
                sc = out["result"].get("screener")
                sc_failed = sc is None or sc.get("status") == "failed"
                if out["fv_failed"] and sc_failed:
                    failed += 1
                else:
                    completed += 1
                yield {"type": "ticker_done", "ticker": ticker, "result": out["result"]}
            except Exception as e:
                failed += 1
                yield {"type": "ticker_error", "ticker": ticker, "error": str(e)}

    status = "cancelled" if cancel_event.is_set() else "completed"
    yield {"type": "job_done", "job_id": job_id, "completed": completed,
           "failed": failed, "status": status}
