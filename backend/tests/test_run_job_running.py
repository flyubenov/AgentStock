"""_run_job maintains the live 'now evaluating' set from ticker_start / ticker_done
so the Progress UI can show which tickers are in flight and prove the run isn't stuck.
"""
import asyncio
import pytest
from routers import analysis


@pytest.mark.asyncio
async def test_run_job_tracks_and_clears_running(monkeypatch):
    seen_running_snapshots = []

    async def fake_run_batch(tickers, job_id, cancel_event):
        yield {"type": "job_start", "job_id": job_id, "total": 2}
        yield {"type": "ticker_start", "ticker": "AAA"}
        seen_running_snapshots.append(list(analysis._jobs[job_id]["running"]))
        yield {"type": "ticker_start", "ticker": "BBB"}
        seen_running_snapshots.append(list(analysis._jobs[job_id]["running"]))
        yield {"type": "ticker_done", "ticker": "AAA",
               "result": {"ticker": "AAA", "status": "completed",
                          "screener": {"status": "completed"}}}
        seen_running_snapshots.append(list(analysis._jobs[job_id]["running"]))
        yield {"type": "ticker_done", "ticker": "BBB",
               "result": {"ticker": "BBB", "status": "completed",
                          "screener": {"status": "completed"}}}
        yield {"type": "job_done", "job_id": job_id,
               "completed": 2, "failed": 0, "status": "completed"}

    monkeypatch.setattr(analysis, "run_batch", fake_run_batch)
    job_id = "test-running"
    analysis._jobs[job_id] = {"status": "running", "total": 2, "completed": 0,
                              "failed": 0, "results": [], "invalid": [], "running": []}
    try:
        await analysis._run_job(job_id, ["AAA", "BBB"], asyncio.Event())
        assert seen_running_snapshots[0] == ["AAA"]
        assert seen_running_snapshots[1] == ["AAA", "BBB"]
        assert seen_running_snapshots[2] == ["BBB"]         # AAA cleared on done
        assert analysis._jobs[job_id]["running"] == []       # emptied at job_done
    finally:
        analysis._jobs.pop(job_id, None)


@pytest.mark.asyncio
async def test_run_job_clears_running_on_ticker_error(monkeypatch):
    async def fake_run_batch(tickers, job_id, cancel_event):
        yield {"type": "ticker_start", "ticker": "AAA"}
        yield {"type": "ticker_error", "ticker": "AAA", "error": "boom"}
        yield {"type": "job_done", "job_id": job_id,
               "completed": 0, "failed": 1, "status": "completed"}

    monkeypatch.setattr(analysis, "run_batch", fake_run_batch)
    job_id = "test-running-err"
    analysis._jobs[job_id] = {"status": "running", "total": 1, "completed": 0,
                              "failed": 0, "results": [], "invalid": [], "running": []}
    try:
        await analysis._run_job(job_id, ["AAA"], asyncio.Event())
        assert analysis._jobs[job_id]["failed"] == 1
        assert analysis._jobs[job_id]["running"] == []
    finally:
        analysis._jobs.pop(job_id, None)
