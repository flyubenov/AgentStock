import pytest
from valuation import engine


def _large_cap_fin(**over):
    fin = {
        "ticker": "AAPL", "company_name": "Apple Inc.", "current_price": 190.0,
        "sector": "Technology", "industry": "Consumer Electronics", "long_business_summary": "",
        "market_cap": 3_000_000_000_000, "shares_outstanding": 15_000_000_000,
        "fcf_ttm": 99_000_000_000, "operating_cashflow": 120_000_000_000,
        "net_debt": 0, "ebitda_ttm": 130_000_000_000, "revenue_ttm": 391_000_000_000,
        "eps_ttm": 6.6, "book_value_per_share": 4.0,
        "dividend_rate": 1.0, "dividend_yield": 0.005, "payout_ratio": 0.15,
        "return_on_equity": 1.4, "trailing_pe": 28.0, "revenue_growth": 0.05,
        "earnings_growth": 0.08, "ev_ebitda": 24.0, "ev_sales": 8.0,
        "interest_expense": 0, "effective_tax_rate": 0.15, "cost_of_equity": 0.10,
    }
    fin.update(over)
    return fin


def test_build_scenarios_capped():
    s = engine.build_scenarios({"earnings_growth": 0.56, "revenue_growth": 0.10})
    assert s["realistic"] == 0.20             # base capped at 0.20
    assert s["optimistic"] == pytest.approx(0.20)   # optimistic ceiling now 20%
    assert s["pessimistic"] == pytest.approx(0.16)


def test_build_scenarios_floor():
    s = engine.build_scenarios({"earnings_growth": -0.5, "revenue_growth": None})
    assert s["realistic"] == 0.02
    assert s["pessimistic"] == 0.02


def test_build_scenarios_distorted_earnings_uses_full_revenue_growth():
    # Revenue growing while GAAP earnings negative (one-off charge, e.g. ETN):
    # the bounded-horizon DCF/EV growth now reads the real revenue line under the
    # normal 20% cap, not the 3.9% DDM ceiling.
    s = engine.build_scenarios({"earnings_growth": -0.094, "revenue_growth": 0.168})
    assert s["realistic"] == pytest.approx(0.168)
    assert s["optimistic"] == pytest.approx(0.20)        # 0.168 + 0.05, capped at 0.20
    assert s["pessimistic"] == pytest.approx(0.128)


def test_build_scenarios_distorted_earnings_ddm_cap_keeps_sustainable_ceiling():
    # The DDM/perpetuity copy of the scenarios (distorted_cap=SUSTAINABLE_CEIL)
    # stays capped so Gordon growth can't overshoot the discount rate (ABBV).
    s = engine.build_scenarios({"earnings_growth": -0.46, "revenue_growth": 0.124},
                               distorted_cap=engine.SUSTAINABLE_CEIL)
    assert s["realistic"] == pytest.approx(engine.SUSTAINABLE_CEIL)
    assert s["optimistic"] == pytest.approx(engine.SUSTAINABLE_CEIL + 0.05)
    assert s["pessimistic"] == 0.02


def test_build_scenarios_genuine_decline_not_normalized():
    # Revenue AND earnings both falling -> a real decline, NOT an accounting
    # distortion: must stay on the floored path, not the revenue cap.
    s = engine.build_scenarios({"earnings_growth": -0.20, "revenue_growth": -0.05})
    assert s["realistic"] == 0.02


def test_build_scenarios_positive_earnings_unchanged():
    # Positive earnings growth must be untouched (guards MSFT/AMAT/KLAC path).
    s = engine.build_scenarios({"earnings_growth": 0.08, "revenue_growth": 0.05})
    assert s["realistic"] == pytest.approx(0.08)


def test_pick_ev_uses_ebitda_when_margin_healthy():
    weights = {"ev_ebitda": 0.20, "ev_sales": 0.20}
    fin = {"ebitda_ttm": 100, "revenue_ttm": 1000}  # 10% margin > 8%
    out = engine.pick_ev_multiple(weights, fin)
    assert out["ev_ebitda"] == pytest.approx(0.40)
    assert out["ev_sales"] == 0.0


def test_pick_ev_uses_sales_when_margin_thin():
    weights = {"ev_ebitda": 0.20, "ev_sales": 0.20}
    fin = {"ebitda_ttm": 50, "revenue_ttm": 1000}  # 5% margin < 8%
    out = engine.pick_ev_multiple(weights, fin)
    assert out["ev_sales"] == pytest.approx(0.40)
    assert out["ev_ebitda"] == 0.0


def test_pick_ev_no_fold_when_only_one_weighted():
    weights = {"ev_ebitda": 0.30, "ev_sales": 0.0}
    fin = {"ebitda_ttm": 10, "revenue_ttm": 1000}  # thin margin, but ev_sales not weighted
    out = engine.pick_ev_multiple(weights, fin)
    assert out["ev_ebitda"] == 0.30
    assert out["ev_sales"] == 0.0


def test_evaluate_large_cap_blend():
    fin = _large_cap_fin()
    result = engine.evaluate(fin)
    assert result["status"] == "completed"
    assert result["stock_type"] == "LARGE_CAP"
    assert result["fair_value"] is not None and result["fair_value"] > 0
    # breakdown weights renormalize to ~1.0
    total_w = sum(b["weight"] for b in result["fair_value_breakdown"].values())
    assert total_w == pytest.approx(1.0)
    # composite is the weight-internal blend of the breakdown values (consistency guard)
    blend = sum(b["weight"] * b["fair_value"] for b in result["fair_value_breakdown"].values())
    assert result["fair_value"] == pytest.approx(blend, rel=1e-6)
    # LARGE_CAP weights only EV/EBITDA among the EV multiples (no EV/Sales)
    bd = result["fair_value_breakdown"]
    assert "ev_sales" not in bd
    assert "ev_ebitda" in bd


def test_evaluate_mid_cap_blend():
    # Same profile as the large-cap fixture but a $20B cap -> MID_CAP default.
    # Lower EBITDA margin to force pick_ev_multiple to select ev_sales (distinct from LARGE_CAP).
    fin = _large_cap_fin(market_cap=20_000_000_000, ebitda_ttm=20_000_000_000)
    result = engine.evaluate(fin)
    assert result["stock_type"] == "MID_CAP"
    assert result["status"] == "completed"
    total_w = sum(b["weight"] for b in result["fair_value_breakdown"].values())
    assert total_w == pytest.approx(1.0)
    # MID_CAP keeps a small EV/Sales weight (distinct from LARGE_CAP)
    assert "ev_sales" in result["fair_value_breakdown"]


def test_evaluate_price_vs_fair_value_pct():
    fin = _large_cap_fin(current_price=100.0)
    result = engine.evaluate(fin)
    expected = round((result["fair_value"] - 100.0) / 100.0 * 100, 2)
    assert result["price_vs_fair_value_pct"] == expected


def test_evaluate_insufficient_data_is_failed():
    fin = {"ticker": "ZZZ", "sector": "Technology", "shares_outstanding": None,
           "current_price": 10.0, "company_name": "Zilch"}
    result = engine.evaluate(fin)
    assert result["status"] == "failed"
    assert "insufficient data for any model" in result["errors"]


def test_evaluate_sotp_flagged_approx():
    # Conglomerate weights sotp + nav + ev_ebitda
    fin = _large_cap_fin(industry="Conglomerates", book_value_per_share=20.0)
    result = engine.evaluate(fin)
    assert result["stock_type"] == "CONGLOMERATE"
    assert result["fair_value_breakdown"]["sotp"]["is_approx"] is True


def test_evaluate_pre_profit_guard_fires():
    # Deeply FCF-negative AND operations consume cash (OCF < 0) -> genuine burn,
    # declined as PRE_PROFIT (not a capex investor).
    fin = _large_cap_fin(market_cap=16_000_000_000, fcf_ttm=-1_130_000_000,
                         revenue_ttm=757_000_000, operating_cashflow=-200_000_000)
    result = engine.evaluate(fin)
    assert result["status"] == "failed"
    assert result["stock_type"] == "PRE_PROFIT"
    assert result["fair_value"] is None
    assert result["price_vs_fair_value_pct"] is None
    assert "Negative free cash flow" in result["errors"][0]


def test_evaluate_negative_fcf_reroutes_when_cash_generative():
    # IREN pattern: FCF deeply negative from a capex build, but EBITDA > 0 and OCF > 0
    # (operations self-fund) -> reroute onto EV/EBITDA (0.85) + P/E (0.15), not decline.
    fin = _large_cap_fin(market_cap=16_000_000_000, fcf_ttm=-1_130_000_000,
                         revenue_ttm=757_000_000, operating_cashflow=246_000_000,
                         ebitda_ttm=286_000_000, eps_ttm=0.77, forward_eps=0.90)
    result = engine.evaluate(fin)
    assert result["status"] == "completed"
    assert result["stock_type"] == "MID_CAP"
    assert "dcf" not in result["fair_value_breakdown"]
    assert "ev_ebitda" in result["fair_value_breakdown"]
    assert result["fair_value_breakdown"]["ev_ebitda"]["weight"] == pytest.approx(0.85)
    if "pe" in result["fair_value_breakdown"]:
        assert result["fair_value_breakdown"]["pe"]["weight"] == pytest.approx(0.15)


def test_evaluate_negative_fcf_declines_when_ebitda_nonpositive():
    # OCF > 0 but EBITDA <= 0 -> no operating-profit anchor for a multiple -> decline.
    fin = _large_cap_fin(market_cap=16_000_000_000, fcf_ttm=-1_130_000_000,
                         revenue_ttm=757_000_000, operating_cashflow=246_000_000,
                         ebitda_ttm=-50_000_000)
    result = engine.evaluate(fin)
    assert result["status"] == "failed"
    assert result["stock_type"] == "PRE_PROFIT"


def test_evaluate_pre_profit_guard_not_fired_when_fcf_positive():
    fin = _large_cap_fin(market_cap=16_000_000_000)  # positive fcf_ttm
    result = engine.evaluate(fin)
    assert result["status"] == "completed"
    assert result["stock_type"] == "MID_CAP"


def test_evaluate_pre_profit_guard_skips_financial():
    # FINANCIAL has dcf weight 0, so the guard must not fire even when FCF<0.
    fin = _large_cap_fin(sector="Financial Services",
                         fcf_ttm=-1_000_000_000, revenue_ttm=500_000_000)
    result = engine.evaluate(fin)
    assert result["stock_type"] == "FINANCIAL"


def test_evaluate_capex_distorted_positive_fcf_reroutes_off_dcf():
    # AMZN pattern: FCF positive but a negligible fraction of EBITDA (heavy capex).
    # fcf/revenue is +1% (above the -25% decline floor, so NOT declined), but
    # fcf/ebitda is ~5% (< 15%), so the DCF is rerouted onto EV/EBITDA + P/E.
    fin = _large_cap_fin(fcf_ttm=7_695_000_000, ebitda_ttm=155_860_000_000,
                         revenue_ttm=742_000_000_000, eps_ttm=7.0)
    result = engine.evaluate(fin)
    assert result["status"] == "completed"
    assert "dcf" not in result["fair_value_breakdown"]     # DCF anchored to the residual is dropped
    assert "ev_ebitda" in result["fair_value_breakdown"]


def test_evaluate_capex_reroute_not_fired_for_healthy_conversion():
    # Positive FCF that is a healthy share of EBITDA (99/130 = 0.76) -> normal DCF path.
    fin = _large_cap_fin()
    result = engine.evaluate(fin)
    assert "dcf" in result["fair_value_breakdown"]


def test_evaluate_distorted_earnings_drops_pe_leg():
    # DIVIDEND with distorted GAAP earnings (earnings_growth<0, revenue_growth>0):
    # the P/E leg must be excluded and the remaining models renormalize.
    fin = _large_cap_fin(sector="Healthcare", dividend_yield=0.04, payout_ratio=0.6,
                         earnings_growth=-0.30, revenue_growth=0.05)
    result = engine.evaluate(fin)
    assert result["stock_type"] == "DIVIDEND"
    assert "pe" not in result["fair_value_breakdown"]
    total_w = sum(b["weight"] for b in result["fair_value_breakdown"].values())
    assert total_w == pytest.approx(1.0, abs=1e-3)


def test_evaluate_pe_kept_when_earnings_healthy():
    # Positive earnings growth -> P/E leg retained in the blend.
    fin = _large_cap_fin(sector="Healthcare", dividend_yield=0.04, payout_ratio=0.6,
                         earnings_growth=0.08, revenue_growth=0.05)
    result = engine.evaluate(fin)
    assert result["stock_type"] == "DIVIDEND"
    assert "pe" in result["fair_value_breakdown"]


def test_evaluate_forward_tier_keeps_pe_when_distorted():
    # A forward tier (LARGE_CAP) with distorted GAAP earnings keeps its forward-P/E
    # leg: forward P/E is robust to a one-off trailing charge. Regression: ETN,
    # whose forward-P/E recovery leg was being thrown away.
    fin = _large_cap_fin(earnings_growth=-0.094, revenue_growth=0.168,
                         forward_pe=26.0, trailing_pe=40.0)
    result = engine.evaluate(fin)
    assert result["stock_type"] == "LARGE_CAP"
    assert "pe" in result["fair_value_breakdown"]


def test_evaluate_distorted_ddm_leg_stays_on_sustainable_ceiling():
    # The raised revenue growth must NOT leak into the DDM perpetuity: the DDM leg
    # values off the SUSTAINABLE_CEIL-capped scenarios so Gordon growth stays
    # bounded (ABBV regression — naive removal of the cap doubled the DDM leg).
    from valuation import models as m
    fin = _large_cap_fin(sector="Healthcare", dividend_yield=0.04, payout_ratio=0.6,
                         dividend_rate=6.0, earnings_growth=-0.46, revenue_growth=0.124)
    result = engine.evaluate(fin)
    assert result["stock_type"] == "DIVIDEND"
    ddm_growth = engine.build_scenarios(fin, distorted_cap=engine.SUSTAINABLE_CEIL)
    expected = m.calc_ddm(fin, ddm_growth)["fair_value"]
    assert result["fair_value_breakdown"]["ddm"]["fair_value"] == pytest.approx(round(expected, 2))


def _growth_fin(**over):
    # revenue_growth>0.10, eps>0, no dividend -> GROWTH; rich forward P/E and EV/EBITDA.
    fin = _large_cap_fin(
        sector="Technology", industry="Semiconductors",
        market_cap=300_000_000_000,  # sub-$1T so the mega-cap ceiling keeps it GROWTH
        revenue_growth=0.12, earnings_growth=0.30,
        dividend_rate=0, dividend_yield=0, payout_ratio=0,
        trailing_pe=55.0, forward_pe=35.0, ev_ebitda=45.0,
        fcf_ttm=5_000_000_000, ebitda_ttm=9_000_000_000, revenue_ttm=29_000_000_000,
    )
    fin.update(over)
    return fin


def test_evaluate_growth_uses_forward_pe_leg():
    from valuation import models as m
    fin = _growth_fin()
    result = engine.evaluate(fin)
    assert result["stock_type"] == "GROWTH"
    pe_leg = m.calc_pe(fin, forward=True)["fair_value"]
    assert result["fair_value_breakdown"]["pe"]["fair_value"] == pytest.approx(round(pe_leg, 2))
    # forward-based leg is strictly richer than the mature-capped production leg
    assert pe_leg > m.calc_pe(fin)["fair_value"]


def test_evaluate_growth_uses_uncompressed_ev_ebitda():
    from valuation import models as m
    fin = _growth_fin()
    result = engine.evaluate(fin)
    growth = engine.build_scenarios(fin)
    expected = m.calc_ev_ebitda(fin, growth, compress=False)["fair_value"]
    assert result["fair_value_breakdown"]["ev_ebitda"]["fair_value"] == pytest.approx(round(expected, 2))
    # uncompressed leg exceeds the compressed production leg for this high-FCF name
    assert expected > m.calc_ev_ebitda(fin, growth)["fair_value"]


def test_evaluate_large_cap_uses_forward_pe():
    # LARGE_CAP is now a forward tier: the P/E leg uses forward P/E (PEG-capped),
    # not the mature trailing cap, when a forward P/E is present.
    from valuation import models as m
    fin = _large_cap_fin(forward_pe=40.0, trailing_pe=35.0)  # eg 0.08 -> PEG cap 16x
    result = engine.evaluate(fin)
    assert result["stock_type"] == "LARGE_CAP"
    expected = m.calc_pe(fin, forward=True)["fair_value"]
    assert result["fair_value_breakdown"]["pe"]["fair_value"] == pytest.approx(round(expected, 2))
    assert expected != pytest.approx(m.calc_pe(fin)["fair_value"])  # genuinely differs from mature


def test_evaluate_forward_tier_uses_historical_ev_ebitda():
    # When a historical median multiple is supplied, a forward tier values
    # EV/EBITDA off it (uncompressed) rather than the current trailing multiple.
    from valuation import models as m
    fin = _large_cap_fin(ev_ebitda=40.0, ev_ebitda_hist=12.0)
    result = engine.evaluate(fin)
    assert result["stock_type"] == "LARGE_CAP"
    growth = engine.build_scenarios(fin)
    expected = m.calc_ev_ebitda(fin, growth, hist_multiple=12.0, compress=False)["fair_value"]
    assert result["fair_value_breakdown"]["ev_ebitda"]["fair_value"] == pytest.approx(round(expected, 2))


def test_evaluate_forward_tier_uses_historical_ev_ebitda_base():
    # NFLX regression: the historical median is built from statement EBITDA, so the
    # forward-tier leg must project the supplied statement base (ev_ebitda_hist_base),
    # not info['ebitda']. Mixing the two (base 14B, multiple from ~30B) halved the leg.
    from valuation import models as m
    fin = _large_cap_fin(ebitda_ttm=14_000_000_000, ev_ebitda=22.0,
                         ev_ebitda_hist=10.0, ev_ebitda_hist_base=30_000_000_000)
    result = engine.evaluate(fin)
    assert result["stock_type"] == "LARGE_CAP"
    growth = engine.build_scenarios(fin)
    expected = m.calc_ev_ebitda(fin, growth, hist_multiple=10.0,
                                hist_ebitda_base=30_000_000_000, compress=False)["fair_value"]
    assert result["fair_value_breakdown"]["ev_ebitda"]["fair_value"] == pytest.approx(round(expected, 2))
    # and it genuinely exceeds the old mixed-basis leg (info ebitda x hist multiple)
    mixed = m.calc_ev_ebitda(fin, growth, hist_multiple=10.0, compress=False)["fair_value"]
    assert expected > mixed


def test_evaluate_non_forward_tier_ignores_historical_ev_ebitda():
    # CYCLICAL is not a forward tier: a stray historical multiple is ignored and
    # the current trailing multiple (compressed) is used.
    from valuation import models as m
    fin = _large_cap_fin(sector="Energy", ev_ebitda=10.0, ev_ebitda_hist=3.0)
    result = engine.evaluate(fin)
    assert result["stock_type"] == "CYCLICAL"
    growth = engine.build_scenarios(fin)
    expected = m.calc_ev_ebitda(fin, growth)["fair_value"]  # current multiple, compressed
    assert result["fair_value_breakdown"]["ev_ebitda"]["fair_value"] == pytest.approx(round(expected, 2))


def test_build_scenarios_statement_growth_fallback_when_info_broken():
    # info revenueGrowth is the broken 0 and earnings_growth is None, so the
    # statement fallback supplies growth. IREN: +167.7% -> capped at 20%.
    s = engine.build_scenarios({"revenue_growth": 0, "earnings_growth": None,
                                "revenue_growth_stmt": 1.677})
    assert s["realistic"] == 0.20


def test_build_scenarios_statement_growth_ignored_when_info_valid():
    # A valid nonzero info growth must win; the statement fallback never fires.
    s = engine.build_scenarios({"revenue_growth": 0.05, "earnings_growth": None,
                                "revenue_growth_stmt": 1.677})
    assert s["realistic"] == pytest.approx(0.05)


def test_growth_cap_below_threshold_is_base():
    assert engine._growth_cap(0.10) == pytest.approx(0.20)
    assert engine._growth_cap(0.20) == pytest.approx(0.20)


def test_growth_cap_ramps_linearly():
    assert engine._growth_cap(0.30) == pytest.approx(0.2125)
    assert engine._growth_cap(0.40) == pytest.approx(0.225)
    assert engine._growth_cap(0.50) == pytest.approx(0.2375)


def test_growth_cap_saturates_at_ceiling():
    assert engine._growth_cap(0.60) == pytest.approx(0.25)
    assert engine._growth_cap(0.70) == pytest.approx(0.25)
    assert engine._growth_cap(1.68) == pytest.approx(0.25)   # IREN-shape backstop


def test_cap_eligible_fcf_positive():
    assert engine._cap_eligible({"fcf_ttm": 100.0}) is True


def test_cap_eligible_burner_excluded():
    # FCF < 0 and OCF < 0 -> genuine cash burn, not eligible
    assert engine._cap_eligible(
        {"fcf_ttm": -50.0, "ebitda_ttm": -10.0, "ocf_ttm": -20.0}) is False


def test_cap_eligible_capex_reroute_shape():
    # FCF < 0 but EBITDA > 0 and OCF > 0 (IREN-like) -> eligible via the OCF branch
    assert engine._cap_eligible(
        {"fcf_ttm": -50.0, "ebitda_ttm": 100.0, "ocf_ttm": 80.0}) is True


def test_cap_eligible_ocf_info_fallback():
    # ocf_ttm absent -> falls back to operating_cashflow (info)
    assert engine._cap_eligible(
        {"fcf_ttm": -50.0, "ebitda_ttm": 100.0, "operating_cashflow": 80.0}) is True


def test_cap_eligible_no_cashflow_data_not_eligible():
    assert engine._cap_eligible({"earnings_growth": 0.5}) is False
