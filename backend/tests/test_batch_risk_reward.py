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


# The public landing page runs the same engines but must never write to the analyst
# app's Database: an anonymous visitor creating or overwriting rows is the defect.
def _all_three_ok():
    fv = TickerResult(ticker="AAPL", status="completed", fair_value=180.0, current_price=190.0)
    sc = ScreenerResult(ticker="AAPL", status="completed", quality_score=8.4)
    rr = RiskRewardResult(ticker="AAPL", status="completed", ratio=1.85,
                          tier="Reward-Favored", reward_score=4.1, risk_score=2.2)
    return fv, sc, rr


@pytest.mark.asyncio
async def test_readonly_run_returns_the_full_result_and_writes_nothing():
    fv, sc, rr = _all_three_ok()
    with patch("orchestrator.batch.engine_run", new=AsyncMock(return_value=fv)), \
         patch("orchestrator.batch.screener_run", new=AsyncMock(return_value=sc)), \
         patch("orchestrator.batch.risk_reward_run", new=AsyncMock(return_value=rr)), \
         patch("orchestrator.batch.upsert_result", new=AsyncMock()) as up_fv, \
         patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()) as up_sc, \
         patch("orchestrator.batch.upsert_risk_reward_result", new=AsyncMock()) as up_rr:
        out = await batch._run_one_readonly("AAPL")
    assert out["result"]["fair_value"] == 180.0
    assert out["result"]["screener"]["quality_score"] == 8.4
    assert out["result"]["risk_reward"]["ratio"] == 1.85
    up_fv.assert_not_awaited()
    up_sc.assert_not_awaited()
    up_rr.assert_not_awaited()
    # And so no save-failure message can reach the public payload.
    assert not any("write" in e for e in out["result"]["errors"])


@pytest.mark.asyncio
async def test_the_analyst_app_run_still_writes_all_three():
    fv, sc, rr = _all_three_ok()
    with patch("orchestrator.batch.engine_run", new=AsyncMock(return_value=fv)), \
         patch("orchestrator.batch.screener_run", new=AsyncMock(return_value=sc)), \
         patch("orchestrator.batch.risk_reward_run", new=AsyncMock(return_value=rr)), \
         patch("orchestrator.batch.upsert_result", new=AsyncMock()) as up_fv, \
         patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()) as up_sc, \
         patch("orchestrator.batch.upsert_risk_reward_result", new=AsyncMock()) as up_rr:
        await batch._run_one_guarded("AAPL")
    up_fv.assert_awaited_once()
    up_sc.assert_awaited_once()
    up_rr.assert_awaited_once()


def test_the_landing_cache_is_wired_to_the_readonly_run():
    # A revert of cache.py's import to _run_one_guarded would restore the writes and
    # pass every cache test (they patch the name), so pin the binding itself.
    from landing import cache
    assert cache._run_one_readonly is batch._run_one_readonly
    assert not hasattr(cache, "_run_one_guarded")
