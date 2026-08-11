import pytest
from unittest.mock import patch
from risk_reward import data
from risk_reward.models import RiskRewardInputs

_CLOSES = tuple(float(x) for x in range(1, 261))  # 260 rising closes


@pytest.mark.asyncio
async def test_assembles_inputs_and_indicators():
    info = {"symbol": "AAPL", "shortName": "Apple", "currentPrice": 260.0,
            "fiftyTwoWeekHigh": 300.0}
    with patch("risk_reward.data.fetch_ticker_info", return_value=info), \
         patch("risk_reward.data.fetch_price_daily", return_value=_CLOSES), \
         patch("risk_reward.data.fetch_income_stmt", return_value=None):
        inp = await data.fetch_risk_reward_inputs("AAPL")
    assert isinstance(inp, RiskRewardInputs)
    assert inp.price == 260.0 and inp.high_52w == 300.0
    assert inp.ma_200 is not None and inp.ma_50 is not None
    assert inp.rsi == 100.0            # strictly rising series
    assert inp.volatility is not None


@pytest.mark.asyncio
async def test_price_and_high_fall_back_to_history():
    with patch("risk_reward.data.fetch_ticker_info", return_value={"symbol": "X"}), \
         patch("risk_reward.data.fetch_price_daily", return_value=_CLOSES), \
         patch("risk_reward.data.fetch_income_stmt", return_value=None):
        inp = await data.fetch_risk_reward_inputs("X")
    assert inp.price == 260.0          # last close
    assert inp.high_52w == 260.0       # max close


@pytest.mark.asyncio
async def test_returns_none_when_info_fetch_fails():
    with patch("risk_reward.data.fetch_ticker_info", side_effect=RuntimeError("boom")):
        inp = await data.fetch_risk_reward_inputs("X")
    assert inp is None


@pytest.mark.asyncio
async def test_statement_growth_and_margin_populated_from_income_stmt():
    # Synthetic income_stmt: Total Revenue [latest, prior] -> +67.7% YoY;
    # Operating Income/Total Revenue -> a positive margin.
    income = {"years": [2025, 2024],
              "rows": {"Total Revenue": [167.7, 100.0],
                       "Operating Income": [7.38, 3.0]}}
    with patch("risk_reward.data.fetch_ticker_info", return_value={"symbol": "IREN"}), \
         patch("risk_reward.data.fetch_price_daily", return_value=_CLOSES), \
         patch("risk_reward.data.fetch_income_stmt", return_value=income):
        inp = await data.fetch_risk_reward_inputs("IREN")
    assert inp.revenue_growth_stmt == pytest.approx(0.677)
    assert inp.operating_margin_stmt == pytest.approx(7.38 / 167.7)


@pytest.mark.asyncio
async def test_statement_growth_and_margin_none_when_statement_unavailable():
    with patch("risk_reward.data.fetch_ticker_info", return_value={"symbol": "X"}), \
         patch("risk_reward.data.fetch_price_daily", return_value=_CLOSES), \
         patch("risk_reward.data.fetch_income_stmt", return_value=None):
        inp = await data.fetch_risk_reward_inputs("X")
    assert inp.revenue_growth_stmt is None
    assert inp.operating_margin_stmt is None
