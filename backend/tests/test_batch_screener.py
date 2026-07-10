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
