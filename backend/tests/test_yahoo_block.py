import pytest
from unittest.mock import patch
from services.yahoo import format_financial_block, extract_financials

_MOCK_INFO = {
    "symbol": "AAPL",
    "shortName": "Apple Inc.",
    "currentPrice": 189.45,
    "marketCap": 2_900_000_000_000,
    "trailingPE": 28.5,
    "forwardPE": 24.2,
    "pegRatio": 1.8,
    "trailingEps": 6.64,
    "earningsGrowth": 0.123,
    "totalRevenue": 391_000_000_000,
    "revenueGrowth": 0.041,
    "grossMargins": 0.452,
    "operatingMargins": 0.295,
    "freeCashflow": 99_000_000_000,
    "returnOnEquity": 1.47,
    "debtToEquity": 187.0,
    "fiftyTwoWeekHigh": 220.19,
    "fiftyTwoWeekLow": 164.08,
    "beta": 1.24,
    "dividendYield": 0.005,
    "heldPercentInstitutions": 0.61,
    "recommendationKey": "buy",
    "targetMeanPrice": 215.0,
    "twoHundredDayAverage": 175.0,
}


@pytest.mark.asyncio
async def test_format_financial_block_returns_string():
    with patch("services.yahoo._fetch_sync", return_value=_MOCK_INFO):
        block = await format_financial_block("AAPL")
    assert isinstance(block, str)
    assert "AAPL" in block
    assert "$189.45" in block
    assert "28.50" in block  # trailingPE


@pytest.mark.asyncio
async def test_format_financial_block_returns_none_on_exception():
    with patch("services.yahoo._fetch_sync", side_effect=ValueError("not found")):
        block = await format_financial_block("BADINPUT")
    assert block is None


@pytest.mark.asyncio
async def test_format_financial_block_handles_none_fields():
    sparse_info = {"symbol": "AAPL", "shortName": "Apple", "currentPrice": 100.0}
    with patch("services.yahoo._fetch_sync", return_value=sparse_info):
        block = await format_financial_block("AAPL")
    assert block is not None
    assert "N/A" in block


def test_extract_financials_adds_valuation_fields():
    info = {
        "symbol": "AAPL",
        "shortName": "Apple Inc.",
        "currentPrice": 189.45,
        "operatingCashflow": 120_000_000_000,
        "freeCashflow": 99_000_000_000,
        "enterpriseToEbitda": 24.3,
        "enterpriseToRevenue": 8.1,
        "ebitda": 130_000_000_000,
        "totalRevenue": 391_000_000_000,
    }
    fin = extract_financials(info)
    assert fin["operating_cashflow"] == 120_000_000_000
    assert fin["ev_ebitda"] == 24.3
    assert fin["ev_sales"] == 8.1
    assert fin["cost_of_equity"] == 0.10


from services.yahoo import real_fcf


def test_real_fcf_prefers_statement_fcf():
    cf = {"free_cash_flow": 71.0, "operating_cash_flow": 136.0, "capital_expenditure": -65.0}
    assert real_fcf(cf, 37.0) == 71.0


def test_real_fcf_falls_back_to_ocf_plus_capex():
    cf = {"free_cash_flow": None, "operating_cash_flow": 136.0, "capital_expenditure": -65.0}
    assert real_fcf(cf, 37.0) == pytest.approx(71.0)  # 136 + (-65)


def test_real_fcf_falls_back_to_info_when_no_cashflow():
    assert real_fcf(None, 37.0) == 37.0
    empty = {"free_cash_flow": None, "operating_cash_flow": None, "capital_expenditure": None}
    assert real_fcf(empty, 37.0) == 37.0
