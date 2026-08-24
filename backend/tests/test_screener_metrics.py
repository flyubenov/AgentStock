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


def test_wacc_caps_inflated_beta():
    from screener.metrics import wacc as wacc_fn, BETA_CEILING
    # A stale/aggressive beta (3.0) is capped at 2.0 for the cost-of-equity hurdle.
    high = wacc_fn(_mk_inputs(info={"beta": 3.0}), 0.21)
    capped = wacc_fn(_mk_inputs(info={"beta": BETA_CEILING}), 0.21)
    assert high == pytest.approx(capped, abs=1e-9)
    # A normal beta (1.0) is untouched — below the ceiling.
    normal = wacc_fn(_mk_inputs(info={"beta": 1.0}), 0.21)
    assert normal < capped


def test_wacc_floors_implausibly_cheap_captive_debt():
    from screener.metrics import wacc as wacc_fn
    # Ford-shaped: huge finance-arm debt at a ~0.5% implied cost (interest booked against
    # finance revenue, not the Interest Expense line) dominating a small equity base.
    inp = _mk_inputs(info={"beta": 1.85, "totalDebt": 163_000.0, "marketCap": 57_000.0})
    inp.income.rows["Interest Expense"] = [1_000.0, 1_000.0, 1_000.0, 1_000.0]  # ~0.6% of debt
    w = wacc_fn(inp, 0.21)
    # Without the fix this collapses to ~4%; the cost-of-debt floor + 0.50 debt-weight cap
    # keep it a defensible industrial hurdle well above the risk-free rate.
    assert w > 0.08


def test_wacc_debt_weight_capped_at_half():
    from screener.metrics import wacc as wacc_fn
    # Debt-weight would be 0.74; capped to 0.50 so match-funded debt can't dominate the hurdle.
    heavy = _mk_inputs(info={"beta": 1.85, "totalDebt": 163_000.0, "marketCap": 57_000.0})
    heavy.income.rows["Interest Expense"] = [1_000.0] * 4
    # Hand-computed expected WACC with both guards applied:
    #   cost_equity = 0.045 + 1.85*0.05 = 0.1375
    #   cost_debt floored = max((1000/163000)*(1-0.21), 0.045*(1-0.21))
    #                     = max(0.004847, 0.03555) = 0.03555
    #   debt-weight capped at 0.50 (raw would be 163000/220000 = 0.7409)
    #   WACC = 0.5*0.1375 + 0.5*0.03555 = 0.086525
    # This would fail against the pre-fix formula (~0.039, uncapped 0.74 debt weight
    # dragged toward the unfloored ~0.0048 cost of debt).
    assert wacc_fn(heavy, 0.21) == pytest.approx(0.086525, abs=1e-4)
    # Same company but with the debt weight already <= 0.50 (double the equity): the cap
    # doesn't bind, so the only lift comes from the cost-of-debt floor. The capped
    # (heavy) WACC should still exceed what an uncapped 0.74 debt weight would give,
    # confirming the cap is actually reducing the debt weight's drag.
    lighter = _mk_inputs(info={"beta": 1.85, "totalDebt": 163_000.0, "marketCap": 200_000.0})
    lighter.income.rows["Interest Expense"] = [1_000.0] * 4
    assert wacc_fn(lighter, 0.21) is not None
    uncapped_debt_weight_wacc = 0.74 * 0.03555 + 0.26 * 0.1375
    assert wacc_fn(heavy, 0.21) > uncapped_debt_weight_wacc


def test_wacc_low_debt_name_untouched_by_captive_fix():
    from screener.metrics import wacc as wacc_fn
    # TSLA-shaped: also an automaker but debt-weight ~0.01 -> neither guard binds -> identical
    # to the pre-fix value. Compare against a hand-computed equity-dominated WACC.
    inp = _mk_inputs(info={"beta": 1.0, "totalDebt": 100.0, "marketCap": 5000.0,
                           "sector": "Consumer Cyclical"})
    w = wacc_fn(inp, 0.21)
    # equity weight ~0.98 * cost_equity(0.045+1.0*0.05=0.095) dominates -> ~0.093-0.095
    assert w == pytest.approx(0.0937, abs=0.002)


def test_wacc_financials_excluded_from_captive_fix():
    from screener.metrics import wacc as wacc_fn
    # A bank legitimately carries a high debt weight and low implied cost of debt; the fix
    # must NOT touch it (keeps Quality's roic_wacc_spread for banks unchanged).
    bank = _mk_inputs(info={"beta": 1.0, "totalDebt": 100_000.0, "marketCap": 90_000.0,
                            "sector": "Financial Services"})
    bank.income.rows["Interest Expense"] = [200.0] * 4  # low implied cost
    no_fix = _mk_inputs(info={"beta": 1.0, "totalDebt": 100_000.0, "marketCap": 90_000.0,
                              "sector": "Financial Services"})
    no_fix.income.rows["Interest Expense"] = [200.0] * 4
    # Recompute the pre-fix formula by hand to prove no floor/cap was applied:
    rf, erp = 0.045, 0.05
    ce = rf + 1.0 * erp
    cd = (200.0 / 100_000.0) * (1 - 0.21)
    total = 100_000.0 + 90_000.0
    expected = (90_000.0 / total) * ce + (100_000.0 / total) * cd
    assert wacc_fn(bank, 0.21) == pytest.approx(expected, abs=1e-9)


def test_wacc_normal_name_unchanged_regression():
    from screener.metrics import wacc as wacc_fn
    # The default _mk_inputs (Technology, debt-weight ~0.02, cost_debt ~0.079*(1-tax)) is a
    # normal name: cost-of-debt floor may nudge but the debt weight is tiny, so WACC stays
    # in its established band (guards the existing test_roic_and_wacc expectation).
    w = wacc_fn(_mk_inputs(), 0.21)
    assert 0.05 < w < 0.12


def test_roic_ex_goodwill_computed_from_tangible_capital():
    from screener.metrics import compute_metrics
    # Add goodwill & intangibles to the balance sheet: tangible IC = 1000 - 600 = 400,
    # so ROIC ex-goodwill = 200*(1-0.21)/400 = 39.5%, and the goodwill share = 0.6.
    inp = _mk_inputs()
    inp.balance.rows["Goodwill And Other Intangible Assets"] = [600.0, 570.0, 540.0, 510.0]
    m = compute_metrics(inp)
    assert m.roic_ex_goodwill == pytest.approx(200.0 * 0.79 / 400.0 * 100, abs=0.1)
    assert m.roic_ex_goodwill > m.roic_ttm            # tangible base is smaller
    assert m.goodwill_intangible_share == pytest.approx(0.6, abs=1e-3)
    assert m.roic_5y_ex_goodwill is not None
    # No goodwill reported -> the ex-goodwill metrics stay None (no material acquisition).
    m0 = compute_metrics(_mk_inputs())
    assert m0.roic_ex_goodwill is None and m0.goodwill_intangible_share is None


def test_fcf_margin_uses_annual_revenue_not_ttm():
    from screener.metrics import compute_metrics
    # Annual statement Total Revenue = 1000; Yahoo TTM totalRevenue = 2000.
    # FCF (150) is an annual figure, so the denominator must be the annual 1000.
    m = compute_metrics(_mk_inputs(info={"totalRevenue": 2000.0}))
    assert m.fcf_margin == pytest.approx(150.0 / 1000.0 * 100, abs=0.1)
    assert m.fcf_margin != pytest.approx(150.0 / 2000.0 * 100, abs=0.1)


def test_op_margin_prefers_statement_over_broken_info():
    from screener.metrics import compute_metrics
    # IREN-shaped: info operatingMargins is broken (-64.5%) but the statement is
    # healthy (Operating Income 220 / Total Revenue 1000 = +22%). Trust the statement.
    m = compute_metrics(_mk_inputs(info={"operatingMargins": -0.645}))
    assert m.op_margin == pytest.approx(22.0, abs=0.1)


def test_op_margin_falls_back_to_info_without_statement():
    from screener.metrics import compute_metrics
    from screener.models import ScreenerInputs
    inp = ScreenerInputs(ticker="X",
                         info={"operatingMargins": 0.15, "totalRevenue": 1000.0},
                         income=None, balance=None, cashflow=None,
                         price_monthly=tuple(), risk_free=0.045)
    m = compute_metrics(inp)
    assert m.op_margin == pytest.approx(15.0, abs=0.1)


def test_revenue_growth_yoy_from_statement():
    from screener.metrics import compute_metrics
    # Two most-recent statement revenues: 1000 vs 900 -> +11.1% YoY (percent).
    m = compute_metrics(_mk_inputs())
    assert m.revenue_growth_yoy == pytest.approx((1000.0 / 900.0 - 1) * 100, abs=0.1)


def test_revenue_growth_yoy_none_with_one_point():
    from screener.metrics import compute_metrics
    inp = _mk_inputs()
    inp.income.rows["Total Revenue"] = [1000.0]  # only one year available
    m = compute_metrics(inp)
    assert m.revenue_growth_yoy is None


def test_earnings_quality_undefined_when_net_income_negative():
    # OCF / NI is meaningless for a loss-maker: two negatives divide into a flattering
    # positive (TEM: OCF -218M / NI -245M = +0.89, which scored 6/10 as "healthy
    # accrual quality"), and an OCF-positive loss-maker — genuinely the *better*
    # case — divides into a negative that scores as the worst. Undefined, not scored.
    from screener.metrics import compute_metrics
    inp = _mk_inputs()
    inp.income.rows["Net Income"] = [-245.0, 150.0, 130.0, 100.0]
    inp.cashflow.rows["Operating Cash Flow"] = [-218.0, 180.0, 160.0, 140.0]
    m = compute_metrics(inp)
    assert m.earnings_quality is None


def test_earnings_quality_still_computed_when_net_income_positive():
    from screener.metrics import compute_metrics
    m = compute_metrics(_mk_inputs())
    assert m.earnings_quality == pytest.approx(200.0 / 160.0, abs=1e-3)


def _series(rows):
    return StatementSeries(years=[2025, 2024, 2023, 2022], rows=rows)


def _inputs_for_series():
    income = _series({
        "EBIT": [200, 180, 150, 120], "Tax Rate For Calcs": [0.21] * 4,
        "Net Income": [160, 150, 130, 100], "Total Revenue": [1000, 900, 800, 700],
        "Gross Profit": [500, 450, 400, 350],
        "Operating Income": [220, 190, 160, 130]})
    balance = _series({"Invested Capital": [1000, 950, 900, 850],
                       "Tangible Book Value": [800, 750, 700, 650]})
    info = {"symbol": "T", "sector": "Technology", "beta": 1.1,
            "marketCap": 1_000_000, "totalDebt": 0.0}
    return ScreenerInputs(ticker="T", info=info, income=income, balance=balance,
                          cashflow=None, price_monthly=(), risk_free=0.043)


def test_stores_roic_and_rote_series_percent_scaled_latest_first():
    from screener.metrics import compute_metrics
    m = compute_metrics(_inputs_for_series())
    # 4 years present -> 4 observations; latest first
    assert len(m.roic_series) == 4
    # ROIC yr0 = 200*(1-0.21)/1000 = 0.158 -> 15.8%
    assert m.roic_series[0] == pytest.approx(15.8, abs=0.05)
    assert m.roic_series[0] > m.roic_series[-1]  # improving, latest first
    # ROTE yr0 = 160/800 = 20%
    assert len(m.rote_series) == 4
    assert m.rote_series[0] == pytest.approx(20.0, abs=0.05)
    assert m.rote_5y_avg == pytest.approx(sum(m.rote_series) / len(m.rote_series), abs=1e-6)


def test_stores_margin_series_and_gross_trajectory():
    from screener.metrics import compute_metrics
    m = compute_metrics(_inputs_for_series())
    # gross margin yr0 = 500/1000 = 50%
    assert m.gross_margin_series[0] == pytest.approx(50.0, abs=0.05)
    # op margin yr0 = 220/1000 = 22%
    assert m.op_margin_series[0] == pytest.approx(22.0, abs=0.05)
    # trajectory = latest(50) - oldest(350/700=50) = 0pp here
    assert m.gross_margin_trajectory == pytest.approx(0.0, abs=0.05)
