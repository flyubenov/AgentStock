import pytest
from unittest.mock import patch
from valuation import engine
from models import TickerResult

_INFO = {
    "symbol": "AAPL", "shortName": "Apple Inc.", "currentPrice": 190.0,
    "marketCap": 3_000_000_000_000, "sharesOutstanding": 15_000_000_000,
    "freeCashflow": 99_000_000_000, "operatingCashflow": 120_000_000_000,
    "ebitda": 130_000_000_000, "totalRevenue": 391_000_000_000,
    "trailingEps": 6.6, "bookValue": 4.0, "dividendRate": 1.0,
    "payoutRatio": 0.15, "returnOnEquity": 1.4, "trailingPE": 28.0,
    "revenueGrowth": 0.05, "earningsGrowth": 0.08,
    "enterpriseToEbitda": 24.0, "enterpriseToRevenue": 8.0,
    "sector": "Technology", "industry": "Consumer Electronics",
}


@pytest.mark.asyncio
async def test_run_returns_completed_ticker_result():
    with patch("valuation.engine.fetch_ticker_info", return_value=_INFO), \
         patch("valuation.engine.fetch_ticker_cashflow", return_value=None):
        result = await engine.run("AAPL")
    assert isinstance(result, TickerResult)
    assert result.status == "completed"
    assert result.stock_type == "LARGE_CAP"
    assert result.fair_value is not None
    assert result.last_evaluated is not None


@pytest.mark.asyncio
async def test_run_yfinance_failure_is_failed():
    with patch("valuation.engine.fetch_ticker_info", side_effect=ValueError("boom")):
        result = await engine.run("BADX")
    assert result.status == "failed"
    assert result.errors == ["yfinance data unavailable"]


@pytest.mark.asyncio
async def test_run_uses_real_fcf_from_cashflow():
    cf_low = {"free_cash_flow": 20_000_000_000, "operating_cash_flow": None, "capital_expenditure": None}
    with patch("valuation.engine.fetch_ticker_info", return_value=_INFO), \
         patch("valuation.engine.fetch_ticker_cashflow", return_value=None):
        baseline = (await engine.run("AAPL")).fair_value
    with patch("valuation.engine.fetch_ticker_info", return_value=_INFO), \
         patch("valuation.engine.fetch_ticker_cashflow", return_value=cf_low):
        lowered = (await engine.run("AAPL")).fair_value
    # real FCF (20B) is below the info-dict FCF (99B), so DCF + EV/EBITDA conversion drop
    assert lowered < baseline
