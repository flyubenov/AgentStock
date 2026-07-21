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
    assert result.stock_type == "MEGA_CAP"  # AAPL at $3T is a mega-cap (>$1T tier)
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


_IREN_INFO = {
    "symbol": "IREN", "shortName": "IREN Limited", "currentPrice": 41.14,
    "marketCap": 8_000_000_000, "sharesOutstanding": 200_000_000,
    "freeCashflow": -1_130_000_000, "operatingCashflow": -50_000_000,
    "ebitda": 147_000_000, "totalRevenue": 501_000_000,
    "trailingEps": 0.77, "forwardEps": 0.90, "bookValue": 7.5,
    "trailingPE": 53.0, "forwardPE": 30.0, "revenueGrowth": 0.0,
    "enterpriseToEbitda": 20.0, "enterpriseToRevenue": 16.0,
    "sector": "Technology", "industry": "Software",
    "totalDebt": 300_000_000, "totalCash": 500_000_000,
}
_IREN_CF = {"free_cash_flow": -1_130_000_000, "operating_cash_flow": 246_000_000,
            "capital_expenditure": -1_370_000_000}
_IREN_HIST = {"multiple": 16.8, "ebitda": 286_000_000, "revenue_growth": 1.677}


@pytest.mark.asyncio
async def test_run_iren_reroutes_to_completed_fair_value():
    with patch("valuation.engine.fetch_ticker_info", return_value=_IREN_INFO), \
         patch("valuation.engine.fetch_ticker_cashflow", return_value=_IREN_CF), \
         patch("valuation.engine.fetch_ev_ebitda_history", return_value=_IREN_HIST):
        result = await engine.run("IREN")
    assert result.status == "completed"
    assert result.stock_type == "MID_CAP"
    assert result.fair_value is not None
    # 2026-07-21 growth-band regression canary ("IREN must not re-explode"). Pre-band,
    # IREN's optimistic ev_ebitda scenario was pinned AT realistic (44.44 == 44.44 — the
    # opt==realistic collapse the band exists to fix), giving a composite of $37.73. The
    # band legitimately opens the bull leg (167.7% statement growth saturates the ramp:
    # optimistic 44.44 -> 77.0), lifting the composite to $43.15 — a bounded, modest move
    # (~+14%, in line with the spec's measured live-IREN effect of +15.0%), not the
    # unbounded-percentile explosion ($1,536) the design doc rejected. Still well below any
    # explosion-magnitude ceiling.
    assert 20 < result.fair_value < 60
    assert "ev_ebitda" in result.fair_value_breakdown
    assert "dcf" not in result.fair_value_breakdown
