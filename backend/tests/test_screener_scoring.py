import pytest
from screener.scoring import score_high, score_low, leverage_score, PROFILES, base_profile, apply_nudge, section_scores, score, MIN_SCORED_SUBSCORES
from screener.models import ScreenerMetrics


def test_score_high_bands():
    bands = [(20, 10), (15, 8.5), (10, 6.5), (5, 4), (0, 2)]
    assert score_high(25, bands, 0) == 10
    assert score_high(15, bands, 0) == 8.5
    assert score_high(3, bands, 0) == 2
    assert score_high(-1, bands, 0) == 0
    assert score_high(None, bands, 0) is None


def test_score_low_bands():
    bands = [(2, 10), (5, 8), (10, 6), (15, 3.5), (20, 1.5)]
    assert score_low(1, bands, 0) == 10
    assert score_low(5, bands, 0) == 8
    assert score_low(25, bands, 0) == 0
    assert score_low(None, bands, 0) is None


def test_leverage_score_is_sector_relative():
    # utility pivot 4.5: at 4.5 -> 7 (comfortable); at 7 -> 2
    assert leverage_score(-1, 4.5) == 10          # net cash
    assert leverage_score(4.5, 4.5) == 7
    assert leverage_score(7.0, 4.5) == 2
    # tech pivot 2.5: 4.5 is deep in penalty
    assert leverage_score(4.5, 2.5) == 2
    assert leverage_score(3.0, 2.5) == 4.5
    assert leverage_score(None, 2.5) is None
    assert leverage_score(3.0, None) is None      # financials skip


def test_profiles_weights_sum_to_one():
    for name, p in PROFILES.items():
        assert abs(sum(p["w"]) - 1.0) < 1e-9, name


def test_base_profile_mapping_and_default():
    assert base_profile("Technology") == "TECH_GROWTH"
    assert base_profile("communication services") == "BALANCED"
    assert base_profile("Utilities") == "DEFENSIVE_INCOME"
    assert base_profile("Financial Services") == "FINANCIALS"
    assert base_profile("Real Estate") == "REIT"
    assert base_profile(None) == "BALANCED"
    assert base_profile("Nonsense Sector") == "BALANCED"


def test_growth_override_nudge():
    # BALANCED + high revenue CAGR + net cash -> TECH_GROWTH
    m = ScreenerMetrics(revenue_cagr_3y=18.0, net_debt=-100.0)
    assert apply_nudge("BALANCED", m) == "TECH_GROWTH"
    # not enough growth -> stays BALANCED
    assert apply_nudge("BALANCED", ScreenerMetrics(revenue_cagr_3y=8.0, net_debt=-100.0)) == "BALANCED"


def test_special_profile_data_fit_fallback():
    # FINANCIALS/REIT label but operates like a normal company (material positive
    # EBITDA, normal leverage < 4, a real operating-margin signal) -> BALANCED.
    normal = ScreenerMetrics(ebitda=500.0, net_debt_ebitda=1.0, op_margin=20.0)
    assert apply_nudge("FINANCIALS", normal) == "BALANCED"
    assert apply_nudge("REIT", normal) == "BALANCED"
    # A real bank: no meaningful EBITDA signal -> stays FINANCIALS.
    assert apply_nudge("FINANCIALS", ScreenerMetrics(ebitda=None)) == "FINANCIALS"
    # High leverage (>= 4) does not trigger the fallback.
    assert apply_nudge("REIT", ScreenerMetrics(ebitda=500.0, net_debt_ebitda=6.0,
                                               op_margin=20.0)) == "REIT"


def _strong():
    return ScreenerMetrics(
        revenue_cagr_3y=18, eps_cagr_3y=18, fcf_cagr_3y=16, fcf_margin=22,
        op_margin=28, op_margin_trajectory=3, gross_margin=65,
        roic_ttm=22, roic_5y_avg=20, roic_wacc_spread=12, rote=26,
        net_debt_ebitda=1.0, net_debt_fcf=2.0, ocf_capex=6,
        shares_cagr_3y=-2, sbc_pct_rev=1.5, earnings_quality=1.3,
        insider_ownership=12, shareholder_yield=7,
    )


def test_strong_company_high_sections():
    s = section_scores(_strong(), "BALANCED")
    assert s["I"] > 8 and s["II"] > 8 and s["III"] > 7 and s["IV"] > 7


def test_section_renormalizes_over_available():
    m = ScreenerMetrics(roic_ttm=22)  # only one Section II metric present
    s = section_scores(m, "BALANCED")
    assert s["II"] == 10.0            # mean over the single available sub-score
    assert s["I"] is None             # nothing in Section I


def test_dual_check_uses_ebitda_when_fcf_noise():
    # capex cycle: Net Debt/FCF terrible, Net Debt/EBITDA healthy (<2.5)
    m = ScreenerMetrics(net_debt_ebitda=1.2, net_debt_fcf=9.0, ocf_capex=2.0)
    s_dual = section_scores(m, "BALANCED")
    # without dual-check the awful ND/FCF would drag III far lower; assert it's protected
    assert s_dual["III"] >= 6.0


def test_financials_section_iii_ignores_leverage():
    # FINANCIALS pivots are None -> leverage sub-scores are None; only OCF/CapEx
    # remains. (Section III weight is 0.0 for FINANCIALS, so this never affects the
    # composite — but the sub-score should still reflect just the scorable metric.)
    m = ScreenerMetrics(net_debt_ebitda=1.0, net_debt_fcf=2.0, ocf_capex=5.0)
    s = section_scores(m, "FINANCIALS")
    assert s["III"] == 10.0  # OCF/CapEx 5.0 -> 10; leverage metrics excluded


def test_score_strong_company_high():
    m = ScreenerMetrics(
        revenue_cagr_3y=18, eps_cagr_3y=18, fcf_cagr_3y=16, fcf_margin=22,
        op_margin=28, op_margin_trajectory=3, gross_margin=65,
        roic_ttm=22, roic_5y_avg=20, roic_wacc_spread=12, rote=26,
        net_debt_ebitda=1.0, net_debt_fcf=2.0, ocf_capex=6,
        shares_cagr_3y=-2, sbc_pct_rev=1.5, earnings_quality=1.3,
        insider_ownership=12, shareholder_yield=7,
        net_income=100, fcf=100, sector="Technology",
    )
    q, sections, profile, _ = score(m, "Technology")
    assert profile == "TECH_GROWTH"
    assert 8.0 <= q <= 10.0
    assert set(sections) == {"I", "II", "III", "IV"}


def test_insufficient_data_returns_none():
    m = ScreenerMetrics(roic_ttm=20, rote=25)  # only 2 sub-scores
    q, _, _, _ = score(m, "Technology")
    assert q is None


def test_unprofitable_blends_sections_with_growth_and_runway():
    strong = dict(
        revenue_cagr_3y=25, eps_cagr_3y=25, fcf_cagr_3y=20, fcf_margin=30,
        op_margin=30, op_margin_trajectory=4, gross_margin=70,
        roic_ttm=30, roic_5y_avg=28, roic_wacc_spread=20, rote=30,
        net_debt_ebitda=0.5, net_debt_fcf=1.0, ocf_capex=8,
        shares_cagr_3y=-3, sbc_pct_rev=1, earnings_quality=1.5,
        insider_ownership=15, shareholder_yield=8,
    )
    # elite unprofitable (strong Rule of 40, no cash burn -> infinite runway):
    # blended up but held at the 8.0 unprofitable ceiling.
    elite = ScreenerMetrics(**strong, net_income=-10, fcf=50,
                            revenue_growth=25, total_cash=100000)
    q_e, _, _, bd_e = score(elite, "Technology")
    assert 7.0 <= q_e <= 8.0
    assert bd_e["pre_profit"]["applied"] is True
    assert bd_e["pre_profit"]["capped"] is True
    # imminent liquidity risk (< 12 months runway) hard-caps at 5.0 even when the
    # backward-looking sections are pristine.
    danger = ScreenerMetrics(**strong, net_income=-100, fcf=-200,
                             revenue_growth=5, total_cash=100)
    q_d, _, _, bd_d = score(danger, "Technology")
    assert q_d <= 5.0
    assert bd_d["pre_profit"]["capped"] is True
    # the blend leaves the final between the raw section composite and the
    # pre-profit growth score (sections still matter, they are not overridden).
    assert q_e > q_d


def test_rule_of_40_uses_operating_margin_and_caps_growth():
    from screener.scoring import _rule_of_40
    # Heavy-capex hyper-growth (NBIS-like): FCF margin is deeply negative from capex,
    # but operating margin is modest and growth is capped -> Rule of 40 stays healthy.
    m = ScreenerMetrics(revenue_growth=684.0, op_margin=-32.0, fcf_margin=-695.0)
    assert _rule_of_40(m) == pytest.approx(100.0 - 32.0)   # min(684,100) + op_margin
    # FCF margin is used only when operating margin is unavailable.
    assert _rule_of_40(ScreenerMetrics(revenue_growth=30.0, fcf_margin=15.0)) == pytest.approx(45.0)
    # A genuinely failing name: low growth, deep operating loss -> well under 40.
    assert _rule_of_40(ScreenerMetrics(revenue_growth=5.0, op_margin=-40.0)) == pytest.approx(-35.0)


def test_heavy_capex_hypergrowth_not_punished_to_failure():
    # NBIS-like: FCF-negative (capex phase) but elite growth + long runway. The raw
    # FCF margin (-695%) must not collapse the Rule of 40 and force the <5 floor;
    # the elite branch should lift the score to >= 7.0.
    m = ScreenerMetrics(
        revenue_cagr_3y=240, eps_cagr_3y=-29, fcf_cagr_3y=None, fcf_margin=-695,
        op_margin=-32, op_margin_trajectory=50, gross_margin=72,
        roic_ttm=0.6, roic_5y_avg=-4, roic_wacc_spread=-6, rote=1.8,
        net_debt_ebitda=-11.6, net_debt_fcf=-0.12, ocf_capex=0.09,
        shares_cagr_3y=-12, sbc_pct_rev=15.7, earnings_quality=4.7,
        insider_ownership=3.7, shareholder_yield=0,
        net_income=82.5, fcf=-3.68e9, revenue_growth=684, total_cash=9.37e9,
        sector="Communication Services",
    )
    q, _, profile, bd = score(m, "Communication Services")
    assert profile == "BALANCED"
    # The raw section composite is ~4.3 (poor capital efficiency); the elite growth
    # + long runway blend lifts it into the mid-6s — clearly above the composite but
    # no longer a suspicious 7.0 floor that ignores the weak fundamentals.
    assert 5.5 <= q <= 6.8
    assert q > bd["fundamentals_composite"]
    assert bd["pre_profit"]["applied"] is True
    assert bd["pre_profit"]["rule_of_40"] == pytest.approx(67.9, abs=0.5)
    assert bd["pre_profit"]["runway_months"] == pytest.approx(30.6, abs=1.0)


def test_score_clamped_and_rounded():
    m = ScreenerMetrics(roic_ttm=0, roic_5y_avg=0, roic_wacc_spread=-10, rote=0,
                        revenue_cagr_3y=-5, eps_cagr_3y=-5, fcf_cagr_3y=-5,
                        fcf_margin=-5, op_margin=-5, gross_margin=5,
                        net_debt_ebitda=10, net_debt_fcf=20, ocf_capex=0.2,
                        shares_cagr_3y=10, sbc_pct_rev=30, earnings_quality=0.2,
                        insider_ownership=0, shareholder_yield=-2,
                        net_income=1, fcf=1, sector="Technology")
    q, _, _, _ = score(m, "Technology")
    assert q >= 1.0 and round(q, 1) == q
