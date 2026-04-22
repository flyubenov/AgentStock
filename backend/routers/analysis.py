from __future__ import annotations
import asyncio, json, uuid
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from models import AnalyseRequest
from services.yahoo import validate_ticker
from services.sheets import read_tickers
from services.batch_service import submit_batch_job
from orchestrator.batch import run_batch

router = APIRouter()

_jobs: dict[str, dict] = {}
_cancel_events: dict[str, asyncio.Event] = {}


@router.post("/analyse")
async def start_analysis(request: AnalyseRequest):
    tickers: list[str] = []

    if request.tickers:
        tickers.extend([t.strip().upper() for t in request.tickers if t.strip()])

    if request.sheets_url and not request.tickers:
        try:
            sheet_tickers = await read_tickers()
            tickers.extend([t.upper() for t in sheet_tickers if t not in tickers])
        except Exception as e:
            if not tickers:
                return {"error": f"No tickers provided and Sheets read failed: {e}"}

    if not tickers:
        return {"error": "No tickers provided"}

    valid_results = await asyncio.gather(*[validate_ticker(t) for t in tickers])
    valid_tickers = [t for t, ok in zip(tickers, valid_results) if ok]
    invalid_tickers = [t for t, ok in zip(tickers, valid_results) if not ok]

    if not valid_tickers:
        return {"error": "No valid tickers found", "invalid": invalid_tickers}

    job_id = str(uuid.uuid4())

    if request.mode == "batch":
        try:
            result = await submit_batch_job(job_id, valid_tickers)
            return {
                "job_id": job_id,
                "mode": "batch",
                "total": len(valid_tickers),
                "invalid": invalid_tickers,
                "failed_prefetch": result.get("failed_prefetch", []),
            }
        except ValueError as e:
            return {"error": str(e)}

    # Live mode (SSE)
    cancel_event = asyncio.Event()
    _cancel_events[job_id] = cancel_event
    _jobs[job_id] = {
        "status": "running",
        "total": len(valid_tickers),
        "completed": 0,
        "failed": 0,
        "results": [],
        "invalid": invalid_tickers,
    }
    asyncio.create_task(_run_job(job_id, valid_tickers, cancel_event))
    return {"job_id": job_id, "mode": "live", "total": len(valid_tickers), "invalid": invalid_tickers}


async def _run_job(job_id: str, tickers: list[str], cancel_event: asyncio.Event):
    job = _jobs[job_id]
    async for event in run_batch(tickers, job_id, cancel_event):
        if event["type"] == "ticker_done":
            job["completed"] += 1
            job["results"].append(event["result"])
        elif event["type"] == "ticker_error":
            job["failed"] += 1
        elif event["type"] == "job_done":
            job["status"] = event["status"]


@router.get("/stream/{job_id}")
async def stream_job(job_id: str):
    if job_id not in _jobs:
        return {"error": "Job not found"}

    async def event_generator():
        last_sent = 0
        while True:
            job = _jobs.get(job_id)
            if not job:
                break
            results = job["results"]
            for result in results[last_sent:]:
                yield {"event": "ticker_done", "data": json.dumps(result)}
                last_sent += 1
            yield {
                "event": "status",
                "data": json.dumps({
                    "job_id": job_id,
                    "status": job["status"],
                    "total": job["total"],
                    "completed": job["completed"],
                    "failed": job["failed"],
                }),
            }
            if job["status"] in ("completed", "failed", "cancelled"):
                break
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


@router.post("/cancel/{job_id}")
async def cancel_job(job_id: str):
    if job_id in _cancel_events:
        _cancel_events[job_id].set()
        if job_id in _jobs:
            _jobs[job_id]["status"] = "cancelled"
        return {"cancelled": True}
    return {"error": "Job not found"}
