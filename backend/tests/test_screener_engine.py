import pytest
from unittest.mock import patch
from screener import data
from screener.models import ScreenerInputs


_INFO = {"symbol": "AAPL", "shortName": "Apple Inc.", "sector": "Technology",
         "beta": 1.1, "marketCap": 3_000_000_000_000, "totalDebt": 100.0,
         "totalCash": 60.0, "ebitda": 130.0, "operatingMargins": 0.32}


@pytest.mark.asyncio
async def test_fetch_inputs_assembles_all_sources():
    stmt = {"years": [2025, 2024, 2023, 2022], "rows": {"Total Revenue": [4, 3, 2, 1]}}
    with patch("screener.data.fetch_ticker_info", return_value=_INFO), \
         patch("screener.data.fetch_income_stmt", return_value=stmt), \
         patch("screener.data.fetch_balance_sheet", return_value=stmt), \
         patch("screener.data.fetch_cashflow_annual", return_value=stmt), \
         patch("screener.data.fetch_treasury_10y", return_value=0.045), \
         patch("screener.data.fetch_price_monthly", return_value=(1.0, 2.0)):
        inp = await data.fetch_screener_inputs("AAPL")
    assert isinstance(inp, ScreenerInputs)
    assert inp.info["symbol"] == "AAPL"
    assert inp.income.latest("Total Revenue") == 4
    assert inp.risk_free == 0.045
    assert inp.price_monthly == (1.0, 2.0)


@pytest.mark.asyncio
async def test_fetch_inputs_none_when_info_fails():
    with patch("screener.data.fetch_ticker_info", side_effect=ValueError("boom")):
        assert await data.fetch_screener_inputs("BADX") is None
