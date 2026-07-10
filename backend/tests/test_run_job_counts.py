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


@pytest.mark.asyncio
async def test_run_job_counts_ticker_failed_only_when_both_pipelines_fail(monkeypatch):
    """_run_job must apply the same both-failed rule as orchestrator.batch.run_batch.

    A ticker whose Fair Value failed but whose screener succeeded is NOT a failure:
    the two evaluations are independent.
    """
    async def fake_run_batch(tickers, job_id, cancel_event):
        yield {"type": "job_start", "job_id": job_id, "total": 3}
        # FV failed, screener succeeded -> completed (a good screener rescues it)
        yield {"type": "ticker_done", "ticker": "AAA",
               "result": {"ticker": "AAA", "status": "failed",
                          "screener": {"status": "completed", "quality_score": 8.4}}}
        # FV succeeded, screener failed -> completed
        yield {"type": "ticker_done", "ticker": "BBB",
               "result": {"ticker": "BBB", "status": "completed",
                          "screener": {"status": "failed"}}}
        # both failed -> failed
        yield {"type": "ticker_done", "ticker": "CCC",
               "result": {"ticker": "CCC", "status": "failed",
                          "screener": {"status": "failed"}}}
        yield {"type": "job_done", "job_id": job_id, "completed": 2, "failed": 1, "status": "completed"}

    monkeypatch.setattr(analysis, "run_batch", fake_run_batch)
    job_id = "test-job-both-failed"
    analysis._jobs[job_id] = {"status": "running", "total": 3, "completed": 0,
                              "failed": 0, "results": [], "invalid": []}
    try:
        await analysis._run_job(job_id, ["AAA", "BBB", "CCC"], asyncio.Event())
        job = analysis._jobs[job_id]
        assert job["completed"] == 2
        assert job["failed"] == 1
    finally:
        analysis._jobs.pop(job_id, None)


@pytest.mark.asyncio
async def test_run_job_treats_missing_screener_key_as_failed(monkeypatch):
    """A ticker_done result with no "screener" key (screener raised) still counts
    as failed when FV also failed — guards the .get("screener") is None branch."""
    async def fake_run_batch(tickers, job_id, cancel_event):
        yield {"type": "ticker_done", "ticker": "AAA",
               "result": {"ticker": "AAA", "status": "failed", "screener": None}}
        yield {"type": "job_done", "job_id": job_id, "completed": 0, "failed": 1, "status": "completed"}

    monkeypatch.setattr(analysis, "run_batch", fake_run_batch)
    job_id = "test-job-no-screener"
    analysis._jobs[job_id] = {"status": "running", "total": 1, "completed": 0,
                              "failed": 0, "results": [], "invalid": []}
    try:
        await analysis._run_job(job_id, ["AAA"], asyncio.Event())
        assert analysis._jobs[job_id]["failed"] == 1
    finally:
        analysis._jobs.pop(job_id, None)
