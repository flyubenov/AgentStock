import pytest
from unittest.mock import patch, AsyncMock
import asyncio
from orchestrator import batch
from models import TickerResult
from screener.models import ScreenerResult
from risk_reward.models import RiskRewardResult


@pytest.mark.asyncio
async def test_risk_reward_attached_to_payload():
    fv = TickerResult(ticker="AAPL", status="completed", fair_value=180.0, current_price=190.0)
    sc = ScreenerResult(ticker="AAPL", status="completed", quality_score=8.4)
    rr = RiskRewardResult(ticker="AAPL", status="completed", ratio=1.85,
                          tier="Reward-Favored", reward_score=4.1, risk_score=2.2)
    with patch("orchestrator.batch.engine_run", new=AsyncMock(return_value=fv)), \
         patch("orchestrator.batch.screener_run", new=AsyncMock(return_value=sc)), \
         patch("orchestrator.batch.risk_reward_run", new=AsyncMock(return_value=rr)), \
         patch("orchestrator.batch.upsert_result", new=AsyncMock()), \
         patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()), \
         patch("orchestrator.batch.upsert_risk_reward_result", new=AsyncMock()) as up_rr:
        out = await batch._run_one("AAPL")
    assert out["result"]["risk_reward"]["ratio"] == 1.85
    assert out["result"]["risk_reward"]["tier"] == "Reward-Favored"
    assert out["result"]["screener"]["quality_score"] == 8.4  # unaffected
    up_rr.assert_awaited_once()


@pytest.mark.asyncio
async def test_risk_reward_failure_is_isolated():
    # RR raising must not fail FV, must not fail the screener, and must not set fv_failed.
    fv = TickerResult(ticker="AAPL", status="completed", fair_value=180.0, current_price=190.0)
    sc = ScreenerResult(ticker="AAPL", status="completed", quality_score=8.4)
    with patch("orchestrator.batch.engine_run", new=AsyncMock(return_value=fv)), \
         patch("orchestrator.batch.screener_run", new=AsyncMock(return_value=sc)), \
         patch("orchestrator.batch.risk_reward_run", new=AsyncMock(side_effect=ValueError("rr down"))), \
         patch("orchestrator.batch.upsert_result", new=AsyncMock()), \
         patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()), \
         patch("orchestrator.batch.upsert_risk_reward_result", new=AsyncMock()) as up_rr:
        out = await batch._run_one("AAPL")
    assert out["fv_failed"] is False
    assert out["result"]["fair_value"] == 180.0
    assert out["result"]["screener"]["quality_score"] == 8.4
    assert out["result"]["risk_reward"] is None
    assert any("risk_reward" in e for e in out["result"]["errors"])
    up_rr.assert_not_awaited()  # never upsert a failed pipeline


@pytest.mark.asyncio
async def test_insufficient_data_rr_is_not_upserted():
    # A coverage-floor N/A (status="insufficient_data") is attached but NOT persisted.
    fv = TickerResult(ticker="ZZ", status="completed", fair_value=10.0, current_price=9.0)
    sc = ScreenerResult(ticker="ZZ", status="completed", quality_score=5.0)
    rr = RiskRewardResult(ticker="ZZ", status="insufficient_data")
    with patch("orchestrator.batch.engine_run", new=AsyncMock(return_value=fv)), \
         patch("orchestrator.batch.screener_run", new=AsyncMock(return_value=sc)), \
         patch("orchestrator.batch.risk_reward_run", new=AsyncMock(return_value=rr)), \
         patch("orchestrator.batch.upsert_result", new=AsyncMock()), \
         patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()), \
         patch("orchestrator.batch.upsert_risk_reward_result", new=AsyncMock()) as up_rr:
        out = await batch._run_one("ZZ")
    assert out["result"]["risk_reward"]["status"] == "insufficient_data"
    up_rr.assert_not_awaited()
