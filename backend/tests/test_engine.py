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


def test_build_scenarios_distorted_earnings_uses_capped_revenue():
    # Revenue growing while GAAP earnings negative (e.g. ABBV) -> distortion:
    # source growth from revenue, capped at SUSTAINABLE_CEIL.
    s = engine.build_scenarios({"earnings_growth": -0.46, "revenue_growth": 0.124})
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
    # Deeply FCF-negative, DCF-anchored (MID_CAP) -> declined as PRE_PROFIT.
    fin = _large_cap_fin(market_cap=16_000_000_000,
                         fcf_ttm=-1_130_000_000, revenue_ttm=757_000_000)
    result = engine.evaluate(fin)
    assert result["status"] == "failed"
    assert result["stock_type"] == "PRE_PROFIT"
    assert result["fair_value"] is None
    assert result["price_vs_fair_value_pct"] is None
    assert "Negative free cash flow" in result["errors"][0]


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
