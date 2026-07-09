import pytest
from screener.models import StatementSeries, ScreenerMetrics, ScreenerResult, ScreenerInputs
from screener.metrics import cagr, series_cagr, price_cagr, pct


def test_statement_series_lookups():
    s = StatementSeries.from_dict({"years": [2025, 2024, 2023],
                                   "rows": {"Total Revenue": [100.0, 90.0, None]}})
    assert s.latest("Total Revenue") == 100.0
    assert s.value("Total Revenue", 1) == 90.0
    assert s.value("Total Revenue", 2) is None
    assert s.value("Missing", 0) is None
    assert s.series("Total Revenue") == [100.0, 90.0, None]


def test_statement_series_from_none():
    assert StatementSeries.from_dict(None) is None


def test_models_default_to_none():
    m = ScreenerMetrics()
    assert m.roic_ttm is None and m.revenue_cagr_3y is None
    r = ScreenerResult(ticker="AAPL")
    assert r.quality_score is None and r.status == "completed" and r.errors == []


def test_cagr_basic_and_guards():
    assert cagr(100.0, 133.1, 3) == pytest.approx(0.10, abs=1e-4)
    assert cagr(0, 100.0, 3) is None       # non-positive start
    assert cagr(100.0, -5.0, 3) is None    # non-positive end
    assert cagr(100.0, 110.0, 0) is None   # zero years


def test_series_cagr_uses_available_span():
    # 5 points, span 3 -> compare index0 vs index3 over 3 years
    s = [161.05, 146.41, 133.1, 121.0, 110.0]
    assert series_cagr(s, 3) == pytest.approx(0.10, abs=1e-4)
    # only 3 points, span 5 -> falls back to 2-year span
    assert series_cagr([121.0, 110.0, 100.0], 5) == pytest.approx(0.10, abs=1e-4)
    assert series_cagr([100.0], 3) is None
    assert series_cagr([None, 100.0, 121.0], 2) is None  # latest missing


def test_price_cagr_and_pct():
    months = [float(100 * (1.10 ** (i / 12))) for i in range(37)]  # 36 mo -> +10%/yr
    assert price_cagr(months, 3) == pytest.approx(0.10, abs=1e-3)
    assert price_cagr([100.0], 3) is None
    assert pct(0.153) == pytest.approx(15.3)
    assert pct(None) is None


def _mk_inputs(**over):
    income = StatementSeries(
        years=[2025, 2024, 2023, 2022],
        rows={
            "EBIT": [200.0, 180.0, 150.0, 120.0],
            "Tax Rate For Calcs": [0.21, 0.21, 0.21, 0.21],
            "Net Income": [160.0, 150.0, 130.0, 100.0],
            "Total Revenue": [1000.0, 900.0, 800.0, 700.0],
            "Interest Expense": [10.0, 10.0, 10.0, 10.0],
            "Gross Profit": [500.0, 450.0, 400.0, 350.0],
            "Operating Income": [220.0, 190.0, 160.0, 130.0],
            "Diluted EPS": [3.2, 3.0, 2.6, 2.0],
            "Diluted Average Shares": [50.0, 51.0, 52.0, 53.0],
        },
    )
    balance = StatementSeries(
        years=[2025, 2024, 2023, 2022],
        rows={
            "Invested Capital": [1000.0, 950.0, 900.0, 850.0],
            "Tangible Book Value": [800.0, 750.0, 700.0, 650.0],
            "Net Debt": [-50.0, 0.0, 50.0, 100.0],
            "Ordinary Shares Number": [50.0, 51.0, 52.0, 53.0],
        },
    )
    cashflow = StatementSeries(
        years=[2025, 2024, 2023, 2022],
        rows={
            "Free Cash Flow": [150.0, 130.0, 110.0, 90.0],
            "Operating Cash Flow": [200.0, 180.0, 160.0, 140.0],
            "Capital Expenditure": [-50.0, -50.0, -50.0, -50.0],
            "Stock Based Compensation": [20.0, 20.0, 20.0, 20.0],
            "Repurchase Of Capital Stock": [-30.0, -30.0, -30.0, -30.0],
            "Cash Dividends Paid": [-10.0, -10.0, -10.0, -10.0],
        },
    )
    info = {"beta": 1.0, "totalDebt": 100.0, "totalCash": 150.0, "ebitda": 250.0,
            "marketCap": 5000.0, "operatingMargins": 0.22, "grossMargins": 0.50,
            "heldPercentInsiders": 0.03, "trailingPE": 25.0, "forwardPE": 20.0,
            "trailingPegRatio": 1.5, "priceToSalesTrailing12Months": 5.0,
            "enterpriseValue": 4950.0, "revenueGrowth": 0.11, "sector": "Technology"}
    info.update(over.pop("info", {}))
    return ScreenerInputs(ticker="T", info=info, income=income, balance=balance,
                          cashflow=cashflow, price_monthly=tuple(), risk_free=0.045, **over)


def test_roic_and_wacc():
    from screener.metrics import compute_metrics, roic, wacc as wacc_fn
    # NOPAT = 200*(1-0.21)=158; /1000 = 15.8%
    assert roic(200.0, 0.21, 1000.0) == pytest.approx(0.158, abs=1e-4)
    assert roic(200.0, 0.21, 0) is None
    inp = _mk_inputs()
    # WACC in (0, 1); equity-heavy so near cost of equity = 0.045 + 1.0*0.05 = 0.095
    w = wacc_fn(inp, 0.21)
    assert 0.05 < w < 0.12


def test_compute_section_ii_iii():
    from screener.metrics import compute_metrics
    m = compute_metrics(_mk_inputs())
    assert m.roic_ttm == pytest.approx(15.8, abs=0.1)         # percent
    assert m.roic_5y_avg is not None
    assert m.rote == pytest.approx(160.0 / 800.0 * 100, abs=0.1)
    assert m.net_debt_ebitda == pytest.approx(-50.0 / 250.0, abs=1e-4)  # net cash -> negative
    assert m.ocf_capex == pytest.approx(200.0 / 50.0, abs=1e-4)
    assert m.roic_wacc_spread is not None


def test_compute_section_i_iv_v():
    from screener.metrics import compute_metrics
    m = compute_metrics(_mk_inputs())
    # Section I
    assert m.revenue_cagr_3y == pytest.approx(
        ((1000.0 / 700.0) ** (1 / 3) - 1) * 100, abs=0.1)
    assert m.eps_cagr_3y is not None
    assert m.fcf_cagr_3y is not None
    assert m.fcf_margin == pytest.approx(150.0 / 1000.0 * 100, abs=0.1)
    assert m.op_margin == pytest.approx(22.0, abs=0.1)
    assert m.gross_margin == pytest.approx(50.0, abs=0.1)
    # Section IV
    assert m.shares_cagr_3y is not None and m.shares_cagr_3y < 0  # buyback
    assert m.sbc_pct_rev == pytest.approx(20.0 / 1000.0 * 100, abs=0.1)
    assert m.earnings_quality == pytest.approx(200.0 / 160.0, abs=1e-3)
    assert m.insider_ownership == pytest.approx(3.0, abs=0.1)
    assert m.shareholder_yield == pytest.approx((30.0 + 10.0) / 5000.0 * 100, abs=0.1)
    # Section V reference
    assert m.trailing_pe == 25.0 and m.forward_pe == 20.0 and m.peg == 1.5
    assert m.fcf_yield == pytest.approx(150.0 / 4950.0 * 100, abs=0.1)
    # raw cap-rule inputs
    assert m.net_income == 160.0 and m.revenue_growth == pytest.approx(11.0, abs=0.1)


def test_fcf_margin_uses_annual_revenue_not_ttm():
    from screener.metrics import compute_metrics
    # Annual statement Total Revenue = 1000; Yahoo TTM totalRevenue = 2000.
    # FCF (150) is an annual figure, so the denominator must be the annual 1000.
    m = compute_metrics(_mk_inputs(info={"totalRevenue": 2000.0}))
    assert m.fcf_margin == pytest.approx(150.0 / 1000.0 * 100, abs=0.1)
    assert m.fcf_margin != pytest.approx(150.0 / 2000.0 * 100, abs=0.1)
