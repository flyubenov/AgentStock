import pytest
from unittest.mock import patch, AsyncMock
import asyncio
from orchestrator import batch
from models import TickerResult
from screener.models import ScreenerResult


@pytest.mark.asyncio
async def test_run_batch_emits_combined_result():
    fv = TickerResult(ticker="AAPL", status="completed", fair_value=180.0,
                      company_name="Apple", current_price=190.0)
    sc = ScreenerResult(ticker="AAPL", status="completed", quality_score=8.4)
    with patch("orchestrator.batch.engine_run", new=AsyncMock(return_value=fv)), \
         patch("orchestrator.batch.screener_run", new=AsyncMock(return_value=sc)), \
         patch("orchestrator.batch.upsert_result", new=AsyncMock()) as up_fv, \
         patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()) as up_sc:
        events = [e async for e in batch.run_batch(["AAPL"], "job1", asyncio.Event())]
    done = [e for e in events if e["type"] == "ticker_done"]
    assert len(done) == 1
    assert done[0]["result"]["fair_value"] == 180.0
    assert done[0]["result"]["screener"]["quality_score"] == 8.4
    up_fv.assert_awaited_once()
    up_sc.assert_awaited_once()


@pytest.mark.asyncio
async def test_pre_profit_fv_is_persisted_to_database():
    # A PRE_PROFIT FV is status="failed" but must still be upserted so the ticker
    # gets a Database row (blank Fair Value) and the column-Q score mirror.
    fv = TickerResult(ticker="NBIS", status="failed", stock_type="PRE_PROFIT",
                      company_name="Nebius", current_price=100.0)
    sc = ScreenerResult(ticker="NBIS", status="completed", quality_score=7.0)
    with patch("orchestrator.batch.engine_run", new=AsyncMock(return_value=fv)), \
         patch("orchestrator.batch.screener_run", new=AsyncMock(return_value=sc)), \
         patch("orchestrator.batch.upsert_result", new=AsyncMock()) as up_fv, \
         patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()) as up_sc:
        events = [e async for e in batch.run_batch(["NBIS"], "job1", asyncio.Event())]
    up_fv.assert_awaited_once()   # persisted despite status="failed"
    up_sc.assert_awaited_once()
    done = [e for e in events if e["type"] == "ticker_done"]
    assert done[0]["result"]["screener"]["quality_score"] == 7.0


@pytest.mark.asyncio
async def test_true_fv_failure_is_not_persisted():
    # A genuine failure (no data, no stock_type) must NOT be written to the Database.
    fv = TickerResult(ticker="ZZZZ", status="failed")
    sc = ScreenerResult(ticker="ZZZZ", status="failed")
    with patch("orchestrator.batch.engine_run", new=AsyncMock(return_value=fv)), \
         patch("orchestrator.batch.screener_run", new=AsyncMock(return_value=sc)), \
         patch("orchestrator.batch.upsert_result", new=AsyncMock()) as up_fv, \
         patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()):
        [e async for e in batch.run_batch(["ZZZZ"], "job1", asyncio.Event())]
    up_fv.assert_not_awaited()


@pytest.mark.asyncio
async def test_screener_failure_does_not_block_fv():
    fv = TickerResult(ticker="AAPL", status="completed", fair_value=180.0)
    with patch("orchestrator.batch.engine_run", new=AsyncMock(return_value=fv)), \
         patch("orchestrator.batch.screener_run", new=AsyncMock(side_effect=ValueError("boom"))), \
         patch("orchestrator.batch.upsert_result", new=AsyncMock()), \
         patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()):
        events = [e async for e in batch.run_batch(["AAPL"], "job1", asyncio.Event())]
    done = [e for e in events if e["type"] == "ticker_done"]
    assert done[0]["result"]["fair_value"] == 180.0
    assert done[0]["result"]["screener"] is None


@pytest.mark.asyncio
async def test_fv_raises_still_emits_full_result_and_screener():
    """Mirror image of screener-failure test: FV pipeline raises, screener succeeds.
    The emitted result must still be a full TickerResult dump (+ screener key)."""
    sc = ScreenerResult(ticker="AAPL", status="completed", quality_score=8.4)
    with patch("orchestrator.batch.engine_run", new=AsyncMock(side_effect=ValueError("boom"))), \
         patch("orchestrator.batch.screener_run", new=AsyncMock(return_value=sc)), \
         patch("orchestrator.batch.upsert_result", new=AsyncMock()) as up_fv, \
         patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()) as up_sc:
        events = [e async for e in batch.run_batch(["AAPL"], "job1", asyncio.Event())]
    done = [e for e in events if e["type"] == "ticker_done"]
    result = done[0]["result"]
    # Full TickerResult key set is present (not a hand-rolled partial dict).
    assert "fair_value" in result
    assert "fair_value_breakdown" in result
    assert result["ticker"] == "AAPL"
    assert result["status"] == "failed"
    assert any("boom" in e for e in result["errors"])
    # Screener was not blocked by the FV failure.
    assert result["screener"]["quality_score"] == 8.4
    up_fv.assert_not_awaited()  # FV failed to produce a result -> no FV upsert
    up_sc.assert_awaited_once()


@pytest.mark.asyncio
async def test_both_failed_counts_as_failed():
    """Both pipelines return (not raise) status=failed -> ticker counts as failed,
    and neither upsert runs (upsert only happens on non-failed status)."""
    fv = TickerResult(ticker="AAPL", status="failed")
    sc = ScreenerResult(ticker="AAPL", status="failed")
    with patch("orchestrator.batch.engine_run", new=AsyncMock(return_value=fv)), \
         patch("orchestrator.batch.screener_run", new=AsyncMock(return_value=sc)), \
         patch("orchestrator.batch.upsert_result", new=AsyncMock()) as up_fv, \
         patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()) as up_sc:
        events = [e async for e in batch.run_batch(["AAPL"], "job1", asyncio.Event())]
    job_done = [e for e in events if e["type"] == "job_done"][0]
    assert job_done["failed"] == 1
    assert job_done["completed"] == 0
    up_fv.assert_not_awaited()
    up_sc.assert_not_awaited()


@pytest.mark.asyncio
async def test_fv_ok_screener_failed_counts_as_completed():
    """Preserved 'both must fail' semantics: a good FV with a failed screener
    still counts as completed."""
    fv = TickerResult(ticker="AAPL", status="completed", fair_value=180.0)
    sc = ScreenerResult(ticker="AAPL", status="failed")
    with patch("orchestrator.batch.engine_run", new=AsyncMock(return_value=fv)), \
         patch("orchestrator.batch.screener_run", new=AsyncMock(return_value=sc)), \
         patch("orchestrator.batch.upsert_result", new=AsyncMock()), \
         patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()):
        events = [e async for e in batch.run_batch(["AAPL"], "job1", asyncio.Event())]
    job_done = [e for e in events if e["type"] == "job_done"][0]
    assert job_done["completed"] == 1
    assert job_done["failed"] == 0
