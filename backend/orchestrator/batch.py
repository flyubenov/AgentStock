from __future__ import annotations
import asyncio, os
from collections.abc import AsyncGenerator
from valuation import engine
from services.sheets import upsert_result

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))


async def run_batch(
    tickers: list[str],
    job_id: str,
    cancel_event: asyncio.Event,
) -> AsyncGenerator[dict, None]:
    """Process tickers in groups of BATCH_SIZE, yield SSE events."""
    total = len(tickers)
    completed = 0
    failed = 0

    yield {"type": "job_start", "job_id": job_id, "total": total}

    groups = [tickers[i : i + BATCH_SIZE] for i in range(0, len(tickers), BATCH_SIZE)]

    for group in groups:
        if cancel_event.is_set():
            break

        group_tasks = {t: asyncio.create_task(engine.run(t)) for t in group}

        for ticker, task in group_tasks.items():
            yield {"type": "ticker_start", "ticker": ticker}
            try:
                result = await task
                if result.status == "failed":
                    failed += 1
                else:
                    completed += 1
                    try:
                        await upsert_result(result)
                    except Exception as e:
                        result.errors.append(f"sheets_write: {e}")
                yield {"type": "ticker_done", "ticker": ticker, "result": result.model_dump()}
            except Exception as e:
                failed += 1
                yield {"type": "ticker_error", "ticker": ticker, "error": str(e)}

    status = "cancelled" if cancel_event.is_set() else "completed"
    yield {"type": "job_done", "job_id": job_id, "completed": completed, "failed": failed, "status": status}
