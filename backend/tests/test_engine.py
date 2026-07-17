import pytest
from valuation import engine
from valuation import models as m


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
    # A $100B-$1T name is LARGE_CAP (the >$1T mega tier is covered separately).
    fin = _large_cap_fin(market_cap=500_000_000_000)
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


def test_evaluate_mega_cap_blend():
    # The default fixture is a $3T name -> MEGA_CAP: same forward-tier mechanics as
    # LARGE_CAP but leaning slightly more on DCF and less on P/E. Like LARGE_CAP it
    # carries no EV/Sales leg (pick_ev_multiple folds it into EV/EBITDA at healthy margin).
    result = engine.evaluate(_large_cap_fin())
    assert result["status"] == "completed"
    assert result["stock_type"] == "MEGA_CAP"
    assert result["fair_value"] is not None and result["fair_value"] > 0
    bd = result["fair_value_breakdown"]
    assert "ev_sales" not in bd
    assert "ev_ebitda" in bd
    # P/E carries less weight here than under LARGE_CAP (.10 vs .15 pre-renormalization).
    large = engine.evaluate(_large_cap_fin(market_cap=500_000_000_000))
    assert bd["pe"]["weight"] < large["fair_value_breakdown"]["pe"]["weight"]


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


def test_evaluate_declines_when_composite_nonpositive():
    # A negative composite is not a valuation — decline rather than surface it.
    # Regression: INTC emitted a completed fair value of -$2.59.
    #
    # This must exercise the CLAMP, not the pre-profit guard. The original fixture was a
    # cash-burner that reached the clamp only because the guard's -25% FCF-margin floor
    # let it through; once the guard became sign-based it swallowed that fixture and this
    # test passed via PRE_PROFIT, testing nothing. A FINANCIAL carries dcf weight 0 so
    # the guard can never fire, and FCF is positive here regardless — the negative book
    # value drives the P/B + RIM legs (0.35/0.45 of the tier) negative on its own.
    # The stock_type/error assertions pin which path declined, so this can't rot silently.
    fin = _large_cap_fin(
        ticker="NEG", company_name="Negative Bank", current_price=20.0,
        sector="Financial Services", industry="Banks - Diversified",
        long_business_summary="The bank accepts deposits and originates loans.",
        market_cap=50_000_000_000, shares_outstanding=100_000_000,
        revenue_ttm=1_000_000_000, fcf_ttm=50_000_000,   # positive: guard cannot fire
        ebitda_ttm=200_000_000, eps_ttm=-1.0, book_value_per_share=-5.0,
        return_on_equity=-0.2, revenue_growth=0.05, net_debt=0,
        dividend_rate=0, dividend_yield=0, payout_ratio=0,
    )
    result = engine.evaluate(fin)
    assert result["stock_type"] == "FINANCIAL"        # not PRE_PROFIT: the clamp declined it
    assert "composite fair value non-positive" in result["errors"][0]
    assert result["fair_value"] is None
    assert result["status"] == "failed"
    assert result["price_vs_fair_value_pct"] is None


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
    # A forward tier (here MEGA_CAP: the $3T fixture with 16.8% growth clears the
    # GROWTH mega-cap ceiling into the size default) with distorted GAAP earnings keeps
    # its forward-P/E leg: forward P/E is robust to a one-off trailing charge. Regression:
    # ETN, whose forward-P/E recovery leg was being thrown away.
    fin = _large_cap_fin(earnings_growth=-0.094, revenue_growth=0.168,
                         forward_pe=26.0, trailing_pe=40.0)
    result = engine.evaluate(fin)
    assert result["stock_type"] == "MEGA_CAP"
    assert result["stock_type"] in engine.FORWARD_TIERS
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
    fin = _large_cap_fin(forward_pe=40.0, trailing_pe=35.0,  # eg 0.08 -> PEG cap 16x
                         market_cap=500_000_000_000)
    result = engine.evaluate(fin)
    assert result["stock_type"] == "LARGE_CAP"
    expected = m.calc_pe(fin, forward=True)["fair_value"]
    assert result["fair_value_breakdown"]["pe"]["fair_value"] == pytest.approx(round(expected, 2))
    assert expected != pytest.approx(m.calc_pe(fin)["fair_value"])  # genuinely differs from mature


def test_evaluate_forward_tier_uses_historical_ev_ebitda():
    # When a historical median multiple is supplied, a forward tier values
    # EV/EBITDA off it (uncompressed) rather than the current trailing multiple.
    from valuation import models as m
    fin = _large_cap_fin(ev_ebitda=40.0, ev_ebitda_hist=12.0, market_cap=500_000_000_000)
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
                         ev_ebitda_hist=10.0, ev_ebitda_hist_base=30_000_000_000,
                         market_cap=500_000_000_000)
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


def _hypergrower_fin(**over):
    fin = {"fcf_ttm": 3.9e9, "ebitda_ttm": 4.8e9, "ocf_ttm": 4.0e9,
           "revenue_growth_stmt": 0.70, "revenue_growth": 0.59,
           "earnings_growth": 1.13}
    fin.update(over)
    return fin


def test_build_scenarios_elevated_cap_for_eligible_hypergrower():
    # statement growth 0.70 -> cap saturates at the 0.25 ceiling
    s = engine.build_scenarios(_hypergrower_fin())
    assert s["realistic"] == pytest.approx(0.25)
    assert s["optimistic"] == pytest.approx(0.25)     # capped at the elevated ceiling


def test_build_scenarios_statement_growth_preferred_over_info():
    # info 0.30 would give 0.2125; statement 0.70 wins -> 0.25
    s = engine.build_scenarios(_hypergrower_fin(revenue_growth_stmt=0.70, revenue_growth=0.30))
    assert s["realistic"] == pytest.approx(0.25)


def test_build_scenarios_info_growth_when_stmt_absent():
    # no statement growth -> info 0.40 -> _growth_cap(0.40) = 0.225
    s = engine.build_scenarios(
        _hypergrower_fin(revenue_growth_stmt=None, revenue_growth=0.40, earnings_growth=1.0))
    assert s["realistic"] == pytest.approx(0.225)


def test_build_scenarios_ceiling_backstop_on_absurd_growth():
    s = engine.build_scenarios(_hypergrower_fin(revenue_growth_stmt=3.0))
    assert s["realistic"] == pytest.approx(0.25)      # 300% growth still capped


def test_build_scenarios_ineligible_burner_stays_base():
    # FCF < 0 and OCF < 0 -> not eligible -> cap stays 0.20 despite 70% growth
    s = engine.build_scenarios(
        _hypergrower_fin(fcf_ttm=-1e8, ebitda_ttm=-1e7, ocf_ttm=-2e7, revenue_growth_stmt=0.70))
    assert s["realistic"] == pytest.approx(0.20)


def test_build_scenarios_ddm_path_not_elevated_for_hypergrower():
    # DDM copy (distorted_cap=SUSTAINABLE_CEIL) must NOT receive the elevated cap
    s = engine.build_scenarios(_hypergrower_fin(), distorted_cap=engine.SUSTAINABLE_CEIL)
    assert s["realistic"] <= 0.20


def test_build_scenarios_distorted_earnings_not_elevated():
    # eg < 0, rg > 0 -> distorted: raw pre-capped at distorted_cap (0.20), so even an
    # eligible hyper-grower does not get the elevated cap
    s = engine.build_scenarios(
        _hypergrower_fin(earnings_growth=-0.09, revenue_growth=0.70, revenue_growth_stmt=0.70))
    assert s["realistic"] == pytest.approx(0.20)


def _growth_evalfin(**over):
    fin = {"ticker": "TST", "company_name": "Test", "current_price": 100.0,
           "market_cap": 150e9, "shares_outstanding": 3e8, "revenue_ttm": 6e9,
           "ebitda_ttm": 4.8e9, "ev_ebitda": 25.0, "ev_sales": 10.0,
           "fcf_ttm": 3.9e9, "ocf_ttm": 4.0e9, "net_debt": 1e9, "eps_ttm": 11.0,
           "trailing_pe": 39.0, "forward_pe": 20.0, "forward_eps": 21.0,
           "earnings_growth": 1.0, "dividend_yield": 0.0,
           "sector": "Communication Services", "industry": "Advertising Agencies",
           "return_on_equity": 0.3, "book_value_per_share": 10.0}
    fin.update(over)
    return fin


def test_evaluate_hypergrower_fv_exceeds_slow_growth_twin():
    fast = engine.evaluate(_growth_evalfin(revenue_growth=0.59, revenue_growth_stmt=0.70))
    slow = engine.evaluate(_growth_evalfin(revenue_growth=0.11, revenue_growth_stmt=0.11))
    assert fast["stock_type"] == "GROWTH"
    assert slow["stock_type"] == "GROWTH"
    # Same everything except the cap (0.25 vs 0.20) -> fast fair value is strictly higher
    assert fast["fair_value"] > slow["fair_value"]


def test_evaluate_payment_network_avoids_book_value_methods():
    # A Visa-shaped payment network must not be valued on P/B + RIM (book value is
    # trivial vs earning power). It routes to GROWTH and uses DCF/EV/PE legs instead.
    fin = _growth_evalfin(
        sector="Financial Services", industry="Credit Services",
        long_business_summary=("operates a transaction processing network that enables "
                               "settlement of payment transactions"),
        revenue_growth=0.171, revenue_growth_stmt=0.11)
    d = engine.evaluate(fin)
    assert d["stock_type"] == "GROWTH"
    assert "pb" not in d["fair_value_breakdown"]
    assert "rim" not in d["fair_value_breakdown"]


# --- FINANCIAL cost-of-equity gate -------------------------------------------
def _bank_fin(**over):
    fin = {"ticker": "BNK", "company_name": "Test Bank",
           "sector": "Financial Services", "industry": "Banks - Diversified",
           "current_price": 100.0, "book_value_per_share": 100.0,
           "return_on_equity": 0.15, "eps_ttm": 15.0, "trailing_pe": 10.0}
    fin.update(over)
    return fin


def _dividend_fin(**over):
    fin = {"ticker": "DIV", "company_name": "Div Co",
           "sector": "Consumer Defensive", "industry": "Beverages - Non-Alcoholic",
           "current_price": 50.0, "book_value_per_share": 10.0,
           "return_on_equity": 0.30, "eps_ttm": 2.5, "trailing_pe": 20.0,
           "dividend_rate": 1.5, "dividend_yield": 0.03, "payout_ratio": 0.6,
           "fcf_ttm": 3.0e9, "shares_outstanding": 1e9, "net_debt": 0}
    fin.update(over)
    return fin


def test_evaluate_financial_discounts_book_legs_at_financial_coe():
    fin = _bank_fin()
    growth = engine.build_scenarios(fin)
    exp_pb = m.calc_pb({**fin, "cost_of_equity": m.FINANCIAL_COE})["fair_value"]
    exp_rim = m.calc_rim({**fin, "cost_of_equity": m.FINANCIAL_COE}, growth)["fair_value"]
    out = engine.evaluate(fin)
    assert out["stock_type"] == "FINANCIAL"
    bd = out["fair_value_breakdown"]
    assert bd["pb"]["fair_value"] == pytest.approx(round(exp_pb, 2))
    assert bd["rim"]["fair_value"] == pytest.approx(round(exp_rim, 2))


def test_evaluate_financial_lifts_book_legs_vs_flat_coe():
    # ROE 0.15 > COE -> the lower FINANCIAL_COE raises both book legs vs the flat 0.10.
    fin = _bank_fin()
    growth = engine.build_scenarios(fin)
    base_pb = m.calc_pb({**fin, "cost_of_equity": m.DISCOUNT_RATE})["fair_value"]
    base_rim = m.calc_rim({**fin, "cost_of_equity": m.DISCOUNT_RATE}, growth)["fair_value"]
    bd = engine.evaluate(fin)["fair_value_breakdown"]
    assert bd["pb"]["fair_value"] > round(base_pb, 2)
    assert bd["rim"]["fair_value"] > round(base_rim, 2)


def test_evaluate_does_not_mutate_caller_fin():
    fin = _bank_fin()
    engine.evaluate(fin)
    assert fin.get("cost_of_equity") is None


def test_evaluate_respects_preset_cost_of_equity():
    fin = _bank_fin(cost_of_equity=0.09)
    exp_pb = m.calc_pb({**fin})["fair_value"]   # uses the pre-set 0.09, not 0.085
    bd = engine.evaluate(fin)["fair_value_breakdown"]
    assert bd["pb"]["fair_value"] == pytest.approx(round(exp_pb, 2))


def test_evaluate_overrides_flat_default_coe():
    # extract_financials hardcodes cost_of_equity = DISCOUNT_RATE (0.10) as the flat
    # default; a FINANCIAL name carrying that default must still be re-discounted at
    # FINANCIAL_COE (regression: the live pipeline never sends None, so an is-None-only
    # gate left RIM stuck at 0.10).
    fin = _bank_fin(cost_of_equity=m.DISCOUNT_RATE)
    growth = engine.build_scenarios(fin)
    exp_pb = m.calc_pb({**fin, "cost_of_equity": m.FINANCIAL_COE})["fair_value"]
    exp_rim = m.calc_rim({**fin, "cost_of_equity": m.FINANCIAL_COE}, growth)["fair_value"]
    bd = engine.evaluate(fin)["fair_value_breakdown"]
    assert bd["pb"]["fair_value"] == pytest.approx(round(exp_pb, 2))
    assert bd["rim"]["fair_value"] == pytest.approx(round(exp_rim, 2))


def test_evaluate_non_financial_pb_keeps_flat_coe():
    # A DIVIDEND name has a P/B leg (0.10 weight) but must NOT get FINANCIAL_COE.
    fin = _dividend_fin()
    out = engine.evaluate(fin)
    assert out["stock_type"] == "DIVIDEND"
    exp_pb = m.calc_pb({**fin})["fair_value"]   # default DISCOUNT_RATE
    assert out["fair_value_breakdown"]["pb"]["fair_value"] == pytest.approx(round(exp_pb, 2))


def test_evaluate_distorted_roe_bank_pb_leg_is_guarded():
    # ROE 0.45 (thin-book artifact, ALL-like): the P/B leg is clipped to the
    # ROE_PB_CAP_MULT x FINANCIAL_COE cap, strictly below the un-guarded value.
    fin = _bank_fin(return_on_equity=0.45, eps_ttm=45.0)
    guarded = engine.evaluate(fin)["fair_value_breakdown"]["pb"]["fair_value"]
    g = min(m.TERMINAL_GROWTH, m.FINANCIAL_COE - 0.01)
    bvps = fin["book_value_per_share"]
    capped_pb = (m.ROE_PB_CAP_MULT * m.FINANCIAL_COE - g) / (m.FINANCIAL_COE - g)
    unguarded_pb = (0.45 - g) / (m.FINANCIAL_COE - g)
    assert guarded == pytest.approx(round(bvps * capped_pb * m.MOS, 2))
    assert guarded < round(bvps * unguarded_pb * m.MOS, 2)


def _snps_fin(**over):
    # SNPS-shaped (Synopsys mid-2025, just after the ~$35B Ansys deal closed): forward
    # EPS ($17.26) is ~3.9x trailing ($4.39) because trailing FCF/earnings carry the
    # full deal cost but only a stub of Ansys's earnings. Classifies GROWTH (forward tier).
    fin = {
        "ticker": "SNPS", "company_name": "Synopsys, Inc.", "current_price": 425.27,
        "sector": "Technology", "industry": "Software - Infrastructure",
        "long_business_summary": "",
        "market_cap": 81_400_000_000, "shares_outstanding": 191_500_000,
        "fcf_ttm": 1_349_000_000, "operating_cashflow": 1_500_000_000,
        "net_debt": 8_358_000_000, "ebitda_ttm": 1_696_000_000,
        "revenue_ttm": 6_700_000_000,
        "eps_ttm": 4.39, "forward_eps": 17.26, "book_value_per_share": 40.0,
        "dividend_rate": 0.0, "dividend_yield": 0.0, "payout_ratio": 0.0,
        "return_on_equity": 0.10, "trailing_pe": 96.87, "forward_pe": 24.64,
        "revenue_growth": 0.419, "earnings_growth": -0.30,
        "ev_ebitda": 40.0, "ev_sales": 10.0,
        "interest_expense": 300_000_000, "effective_tax_rate": 0.15, "cost_of_equity": 0.10,
    }
    fin.update(over)
    return fin


def test_evaluate_dominant_acquisition_rebases_and_caps_dcf():
    # A severe post-acquisition earnings trough: the trailing-FCF DCF ($181) is the low
    # outlier. Rebase it onto forward run-rate owner earnings, capped at the forward-P/E
    # leg so the rebased DCF can't run above that trustworthy forward anchor.
    trough = _snps_fin()
    r = engine.evaluate(trough)
    b = r["fair_value_breakdown"]
    assert r["stock_type"] == "GROWTH"
    # rebased DCF lands exactly at the forward-P/E leg (cap binds — the raw rebase ~$500
    # exceeds the ~$383 anchor).
    assert b["dcf"]["fair_value"] == pytest.approx(b["pe"]["fair_value"], abs=0.01)
    # the rebase lifted the DCF leg well above what the trailing-FCF base would give.
    unrebased = m.calc_dcf(trough, engine.build_scenarios(trough))["fair_value"]
    assert b["dcf"]["fair_value"] > unrebased
    # and it lifts the whole composite out of the artificially-low trailing read.
    assert r["fair_value"] > engine.evaluate(_snps_fin(forward_eps=1.0))["fair_value"]


def test_evaluate_no_rebase_without_trough():
    # A forward-tier name whose forward EPS is close to trailing (no trough) keeps the
    # trailing-FCF DCF base — the rebase must not fire on ordinary growth names.
    control = _snps_fin(forward_eps=4.8, trailing_pe=25.0, forward_pe=24.0)
    r = engine.evaluate(control)
    b = r["fair_value_breakdown"]
    # DCF stays on the trailing-FCF base (rebase did not fire) -> equals the unrebased leg.
    unrebased = m.calc_dcf(control, engine.build_scenarios(control))["fair_value"]
    assert b["dcf"]["fair_value"] == pytest.approx(round(unrebased, 2))


def test_pre_profit_guard_is_sign_based_not_magnitude_based():
    # A -5% FCF margin sits above the old -25% decline floor, so the guard used to skip
    # and let a DCF built on NEGATIVE free cash flow into the blend. A DCF of negative
    # cash flows is negative by construction regardless of burn depth -> the guard must
    # trigger on the sign, not the magnitude. OCF < 0 and EBITDA <= 0 -> genuine burn.
    fin = _large_cap_fin(market_cap=16_000_000_000, fcf_ttm=-38_000_000,
                         revenue_ttm=757_000_000, operating_cashflow=-20_000_000,
                         ebitda_ttm=-10_000_000)
    result = engine.evaluate(fin)
    assert result["status"] == "failed"
    assert result["stock_type"] == "PRE_PROFIT"
    assert result["fair_value"] is None


def test_early_growth_drops_dcf_leg_when_fcf_negative():
    # TEM pattern: EARLY_GROWTH is *defined* by unprofitability (revenue growth > 20%
    # AND eps/ebitda <= 0), yet carried a 0.35 DCF weight that is guaranteed negative
    # for every name in the tier — dragging the composite below zero and declining a
    # name the tier's own EV/Sales leg can value. Drop the DCF, keep the valuation.
    fin = _large_cap_fin(market_cap=9_470_000_000, shares_outstanding=174_500_000,
                         current_price=52.78, revenue_ttm=1_364_000_000,
                         fcf_ttm=-245_000_000, operating_cashflow=-218_000_000,
                         ebitda_ttm=-185_000_000, eps_ttm=-1.72, forward_eps=-0.08,
                         net_debt=679_000_000, revenue_growth=0.361, ev_sales=6.94)
    result = engine.evaluate(fin)
    assert result["stock_type"] == "EARLY_GROWTH"
    assert result["status"] == "completed"
    assert "dcf" not in result["fair_value_breakdown"]
    assert "ev_sales" in result["fair_value_breakdown"]
    assert result["fair_value"] > 0


def test_early_growth_keeps_dcf_leg_when_fcf_positive():
    # Regression: an EARLY_GROWTH name that is FCF-positive (eps still <= 0) keeps its
    # DCF — the drop is conditional on the burn, not on the tier.
    fin = _large_cap_fin(market_cap=9_470_000_000, shares_outstanding=174_500_000,
                         current_price=52.78, revenue_ttm=1_364_000_000,
                         fcf_ttm=200_000_000, operating_cashflow=220_000_000,
                         ebitda_ttm=180_000_000, eps_ttm=-1.72,
                         net_debt=679_000_000, revenue_growth=0.361, ev_sales=6.94)
    result = engine.evaluate(fin)
    assert result["stock_type"] == "EARLY_GROWTH"
    assert "dcf" in result["fair_value_breakdown"]


def _early_growth_fin(**over):
    """TEM/NBIS-shaped: revenue growth > 20% with eps/ebitda <= 0 -> EARLY_GROWTH.
    earnings_growth is None (a loss-maker has no meaningful earnings-growth reading), so
    build_scenarios sources the rate from revenue growth — the path the cap acts on."""
    fin = _large_cap_fin(market_cap=9_470_000_000, shares_outstanding=174_500_000,
                         current_price=52.78, revenue_ttm=1_364_000_000,
                         fcf_ttm=-245_000_000, operating_cashflow=-218_000_000,
                         ebitda_ttm=-185_000_000, eps_ttm=-1.72, forward_eps=-0.08,
                         net_debt=679_000_000, revenue_growth=0.361, ev_sales=6.94,
                         earnings_growth=None)
    fin.update(over)
    return fin


def test_early_growth_cap_ramps_with_growth_to_its_own_ceiling():
    # EARLY_GROWTH earns a tier-scoped, growth-coupled cap. The ramp keeps the existing
    # shallow slope (+1pp of cap per 8pp of growth), so a moderate grower barely moves
    # and only a hyper-grower reaches the ceiling — the credit is coupled to the growth,
    # not granted by the tier.
    assert engine._growth_cap(0.361, engine.EG_CAP_CEIL) == pytest.approx(0.220, abs=1e-3)  # TEM
    assert engine._growth_cap(6.839, engine.EG_CAP_CEIL) == pytest.approx(0.35)   # NBIS
    assert engine._growth_cap(1.40, engine.EG_CAP_CEIL) == pytest.approx(0.35)    # saturates at 140%
    # unchanged for every other tier: same slope, original ceiling
    assert engine._growth_cap(6.839) == pytest.approx(0.25)


def test_early_growth_hyper_grower_earns_elevated_cap():
    s = engine.build_scenarios(_early_growth_fin(revenue_growth=6.839),
                               stock_type="EARLY_GROWTH")
    assert s["realistic"] == pytest.approx(0.35)


def test_early_growth_moderate_grower_barely_moves():
    # TEM at 36% growth earns only 2pp above base — the shallow slope self-discriminates.
    s = engine.build_scenarios(_early_growth_fin(revenue_growth=0.361),
                               stock_type="EARLY_GROWTH")
    assert s["realistic"] == pytest.approx(0.220, abs=1e-3)


def test_early_growth_small_revenue_base_is_denied_the_elevated_cap():
    # A tiny-revenue name prints hyper-growth on arithmetic ($1M -> $5M = 400%). Without
    # demonstrated scale it stays on the flat base — mirroring the screener's
    # RULE_OF_40_GROWTH_CAP guard against a tiny-base rate dominating.
    s = engine.build_scenarios(_early_growth_fin(revenue_growth=4.0,
                                                 revenue_ttm=5_000_000),
                               stock_type="EARLY_GROWTH")
    assert s["realistic"] == pytest.approx(0.20)


def test_elevated_early_growth_cap_does_not_leak_to_other_tiers():
    # A cash-generative hyper-grower outside EARLY_GROWTH keeps the 0.25 ceiling.
    fin = _large_cap_fin(revenue_growth=6.839, earnings_growth=None)
    assert engine.build_scenarios(fin, stock_type="GROWTH")["realistic"] == pytest.approx(0.25)
    assert engine.build_scenarios(fin)["realistic"] == pytest.approx(0.25)


def _pre_commercial_fin(**over):
    """ASTS-shaped: hyper-growth off a sub-floor revenue base, burning cash, with no
    other leg left standing — EV/Sales alone carries the valuation."""
    fin = _early_growth_fin(market_cap=21_350_000_000, shares_outstanding=299_000_000,
                            current_price=55.01, revenue_ttm=84_900_000,
                            fcf_ttm=-1_193_000_000, operating_cashflow=-800_000_000,
                            ebitda_ttm=-316_000_000, revenue_growth=19.52,
                            ev_sales=251.4)
    fin.update(over)
    return fin


def test_sole_ev_sales_leg_below_revenue_floor_is_declined():
    # The model already declares a sub-floor revenue base uninformative about growth
    # (_eg_cap_eligible). It cannot then turn around and let that same base carry 100%
    # of the valuation. ASTS: $84.9M of lumpy contract revenue against a $21.4B market
    # cap priced a pre-commercial satellite business at $1.15 (-98%) — false precision
    # about a business the trailing statements cannot see.
    r = engine.evaluate(_pre_commercial_fin())
    assert r["status"] == "failed"
    assert r["fair_value"] is None
    assert "revenue" in r["errors"][0]


def test_sole_ev_sales_leg_above_revenue_floor_still_values():
    # NBIS-shaped: EV/Sales alone is fine once the base clears the floor — the floor is
    # the whole distinction, not the leg count.
    r = engine.evaluate(_pre_commercial_fin(revenue_ttm=877_900_000, ev_sales=24.3))
    assert r["status"] == "completed"
    assert set(r["fair_value_breakdown"]) == {"ev_sales"}
    assert r["fair_value"] > 0


def test_sub_floor_revenue_keeps_valuing_when_another_leg_survives():
    # The guard is about EV/Sales being the SOLE anchor. A sub-floor name that still has
    # an independent leg (AMBA keeps a DCF, IDR a P/E) is corroborated — leave it alone.
    r = engine.evaluate(_pre_commercial_fin(fcf_ttm=40_000_000, ebitda_ttm=30_000_000,
                                            operating_cashflow=45_000_000))
    assert r["status"] == "completed"
    assert set(r["fair_value_breakdown"]) > {"ev_sales"}


def test_early_growth_cap_does_not_reach_the_ddm_perpetuity():
    # The DDM passes distorted_cap=SUSTAINABLE_CEIL; Gordon growth must never take the
    # elevated cap or it would overshoot the discount rate.
    s = engine.build_scenarios(_early_growth_fin(revenue_growth=6.839, earnings_growth=-0.1),
                               distorted_cap=engine.SUSTAINABLE_CEIL,
                               stock_type="EARLY_GROWTH")
    assert s["realistic"] <= engine.SUSTAINABLE_CEIL
