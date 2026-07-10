import asyncio
import pytest
from unittest.mock import patch, AsyncMock
from models import TickerResult
from screener.models import ScreenerResult
from orchestrator import batch


@pytest.mark.asyncio
async def test_run_batch_emits_lifecycle_events():
    fake = TickerResult(ticker="AAPL", status="completed", fair_value=100.0)
    fake_screener = ScreenerResult(ticker="AAPL", status="completed")
    with patch.object(batch, "engine_run", new=AsyncMock(return_value=fake)), \
         patch.object(batch, "screener_run", new=AsyncMock(return_value=fake_screener)), \
         patch.object(batch, "upsert_result", new=AsyncMock()), \
         patch.object(batch, "upsert_screener_result", new=AsyncMock()):
        events = []
        async for ev in batch.run_batch(["AAPL"], "job-1", asyncio.Event()):
            events.append(ev["type"])
    assert events[0] == "job_start"
    assert "ticker_done" in events
    assert events[-1] == "job_done"
