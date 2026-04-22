from __future__ import annotations
from fastapi import APIRouter, HTTPException
from services.batch_service import get_batch_status, cancel_batch_job, fetch_and_aggregate_results, read_job_file

router = APIRouter()


@router.get("/jobs/{job_id}/status")
async def job_status(job_id: str):
    result = await get_batch_status(job_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/jobs/{job_id}/results")
async def job_results(job_id: str):
    job = read_job_file(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == "processing":
        raise HTTPException(status_code=202, detail="Batch still processing")
    try:
        ticker_results = await fetch_and_aggregate_results(job_id)
        return {
            "job_id": job_id,
            "ticker_results": [r.model_dump() for r in ticker_results],
            "failed_prefetch": job.failed_prefetch,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str):
    cancelled = await cancel_batch_job(job_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"cancelled": True}
