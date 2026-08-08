import pytest
from unittest.mock import patch
from risk_reward import engine
from risk_reward.models import RiskRewardInputs


def _inputs(info):
    return RiskRewardInputs(ticker="X", info=info, company_name="X Corp", price=100.0,
                            high_52w=130.0, ma_200=110.0, ma_50=105.0, rsi=35.0, volatility=0.30)


_RICH = {"pegRatio": 1.1, "revenueGrowth": 0.22, "returnOnEquity": 0.19,
         "targetMeanPrice": 130.0, "debtToEquity": 60.0, "operatingMargins": 0.20,
         "currentRatio": 1.8, "beta": 1.1}


@pytest.mark.asyncio
async def test_completed_result_has_ratio_and_tier():
    with patch("risk_reward.engine.fetch_risk_reward_inputs", return_value=_inputs(_RICH)):
        res = await engine.run("X")
    assert res.status == "completed"
    assert res.ratio is not None and res.tier is not None
    assert res.reward_score is not None and res.risk_score is not None
    assert res.raw_snapshot.get("current_price") == 100.0
    assert res.company_name == "X Corp"


@pytest.mark.asyncio
async def test_insufficient_data_when_thin():
    # only one reward source (peg) and one risk source (beta) resolve
    with patch("risk_reward.engine.fetch_risk_reward_inputs",
               return_value=RiskRewardInputs(ticker="X", info={"pegRatio": 1.1, "beta": 1.1},
                   company_name=None, price=None, high_52w=None, ma_200=None,
                   ma_50=None, rsi=None, volatility=None)):
        res = await engine.run("X")
    assert res.status == "insufficient_data"
    assert res.ratio is None


@pytest.mark.asyncio
async def test_failed_when_inputs_none():
    with patch("risk_reward.engine.fetch_risk_reward_inputs", return_value=None):
        res = await engine.run("X")
    assert res.status == "failed"
    assert res.errors
