import pytest
from unittest.mock import patch
from screener import data, engine
from screener.models import ScreenerInputs, ScreenerResult, StatementSeries


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


def _full_inputs():
    def series(rows):
        return StatementSeries(years=[2025, 2024, 2023, 2022], rows=rows)
    income = series({
        "EBIT": [200, 180, 150, 120], "Tax Rate For Calcs": [0.21]*4,
        "Net Income": [160, 150, 130, 100], "Total Revenue": [1000, 900, 800, 700],
        "Interest Expense": [10]*4, "Gross Profit": [500, 450, 400, 350],
        "Operating Income": [220, 190, 160, 130], "Diluted EPS": [3.2, 3.0, 2.6, 2.0],
        "Diluted Average Shares": [50, 51, 52, 53]})
    balance = series({"Invested Capital": [1000, 950, 900, 850],
                      "Tangible Book Value": [800, 750, 700, 650],
                      "Net Debt": [-50, 0, 50, 100], "Ordinary Shares Number": [50, 51, 52, 53]})
    cash = series({"Free Cash Flow": [150, 130, 110, 90], "Operating Cash Flow": [200, 180, 160, 140],
                   "Capital Expenditure": [-50]*4, "Stock Based Compensation": [20]*4,
                   "Repurchase Of Capital Stock": [-30]*4, "Cash Dividends Paid": [-10]*4})
    info = {"symbol": "AAPL", "shortName": "Apple Inc.", "sector": "Technology",
            "beta": 1.0, "marketCap": 5000, "totalDebt": 100, "totalCash": 150,
            "ebitda": 250, "operatingMargins": 0.22, "grossMargins": 0.50,
            "heldPercentInsiders": 0.03, "trailingPE": 25, "forwardPE": 20,
            "trailingPegRatio": 1.5, "priceToSalesTrailing12Months": 5.0,
            "enterpriseValue": 4950, "revenueGrowth": 0.11, "totalRevenue": 1000,
            "freeCashflow": 150}
    return ScreenerInputs(ticker="AAPL", info=info, income=income, balance=balance,
                          cashflow=cash, price_monthly=tuple(), risk_free=0.045)


@pytest.mark.asyncio
async def test_run_completed():
    with patch("screener.engine.fetch_screener_inputs", return_value=_full_inputs()):
        r = await engine.run("AAPL")
    assert isinstance(r, ScreenerResult)
    assert r.status == "completed"
    assert r.company_name == "Apple Inc."
    assert r.quality_score is not None
    assert r.sector_profile == "TECH_GROWTH"
    assert r.last_evaluated is not None
    assert "roic_ttm" in r.metrics


@pytest.mark.asyncio
async def test_run_failed_when_no_inputs():
    with patch("screener.engine.fetch_screener_inputs", return_value=None):
        r = await engine.run("BADX")
    assert r.status == "failed"
    assert r.quality_score is None and r.errors
