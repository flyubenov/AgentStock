import asyncio
import pytest
from routers import analysis


@pytest.mark.asyncio
async def test_run_job_counts_failed_vs_completed(monkeypatch):
    async def fake_run_batch(tickers, job_id, cancel_event):
        yield {"type": "job_start", "job_id": job_id, "total": 2}
        yield {"type": "ticker_done", "ticker": "AAA",
               "result": {"ticker": "AAA", "status": "completed"}}
        yield {"type": "ticker_done", "ticker": "BBB",
               "result": {"ticker": "BBB", "status": "failed"}}
        yield {"type": "job_done", "job_id": job_id, "completed": 1, "failed": 1, "status": "completed"}

    monkeypatch.setattr(analysis, "run_batch", fake_run_batch)
    job_id = "test-job"
    analysis._jobs[job_id] = {"status": "running", "total": 2, "completed": 0,
                              "failed": 0, "results": [], "invalid": []}
    await analysis._run_job(job_id, ["AAA", "BBB"], asyncio.Event())
    job = analysis._jobs[job_id]
    assert job["completed"] == 1
    assert job["failed"] == 1
    assert job["status"] == "completed"
    analysis._jobs.pop(job_id, None)
