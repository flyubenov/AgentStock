import asyncio
import pytest
from unittest.mock import patch, AsyncMock
from models import TickerResult
from orchestrator import batch


@pytest.mark.asyncio
async def test_run_batch_emits_lifecycle_events():
    fake = TickerResult(ticker="AAPL", status="completed", fair_value=100.0)
    with patch.object(batch, "engine") as eng, \
         patch.object(batch, "upsert_result", new=AsyncMock()):
        eng.run = AsyncMock(return_value=fake)
        events = []
        async for ev in batch.run_batch(["AAPL"], "job-1", asyncio.Event()):
            events.append(ev["type"])
    assert events[0] == "job_start"
    assert "ticker_done" in events
    assert events[-1] == "job_done"
