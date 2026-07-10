import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app
from routers import analysis

client = TestClient(app)


def test_recalculate_one_returns_combined():
    combined = {"result": {"ticker": "AAPL", "status": "completed", "fair_value": 180.0,
                           "screener": {"quality_score": 8.4}}, "fv_failed": False}
    with patch("routers.analysis._run_one", new=AsyncMock(return_value=combined)):
        resp = client.post("/api/ticker/AAPL/recalculate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["fair_value"] == 180.0
    assert body["screener"]["quality_score"] == 8.4


def test_recalculate_all_starts_job():
    from models import DatabaseRow
    rows = [DatabaseRow(ticker="AAPL"), DatabaseRow(ticker="MSFT")]
    # `_run_job` drives the real batch orchestrator (live yfinance + Sheets
    # writes) — it must never actually run in a unit test, so it is patched
    # out here regardless of what asyncio.create_task does with it.
    with patch("routers.analysis.read_database", new=AsyncMock(return_value=rows)), \
         patch("routers.analysis._run_job", new=AsyncMock()) as run_job:
        resp = client.post("/api/recalculate-all")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2 and "job_id" in body
    assert body["job_id"] in analysis._jobs
    assert analysis._jobs[body["job_id"]]["total"] == 2
    run_job.assert_called_once()
    analysis._jobs.pop(body["job_id"], None)
    analysis._cancel_events.pop(body["job_id"], None)


def test_recalculate_all_empty_database():
    with patch("routers.analysis.read_database", new=AsyncMock(return_value=[])):
        resp = client.post("/api/recalculate-all")
    assert resp.json().get("error")
