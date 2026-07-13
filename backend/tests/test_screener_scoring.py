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


def test_operating_loss_blends_growth_and_runway():
    base = dict(
        revenue_cagr_3y=60, gross_margin=70, op_margin_trajectory=5, rote=6,
        net_debt_ebitda=0.5, net_debt_fcf=1.0, ocf_capex=3,
        shares_cagr_3y=-1, sbc_pct_rev=5, earnings_quality=1.1,
        insider_ownership=8, shareholder_yield=0,
    )
    # elite operating loss: strong Rule of 40 and positive FCF (no cash burn) -> blended up
    elite = ScreenerMetrics(**base, op_margin=-8, net_income=-10, fcf=50,
                            revenue_growth=60, total_cash=1_000_000)
    q_e, _, _, bd_e = score(elite, "Technology")
    assert bd_e["pre_profit"]["applied"] is True
    # imminent liquidity risk: operating loss + < 12 months runway -> hard-capped 5.0
    danger = ScreenerMetrics(**base, op_margin=-8, net_income=-100, fcf=-200,
                             revenue_growth=5, total_cash=100)
    q_d, _, _, bd_d = score(danger, "Technology")
    assert q_d <= 5.0
    assert bd_d["pre_profit"]["capped"] is True
    assert q_e > q_d


def test_profitable_company_with_negative_fcf_not_treated_as_burn():
    # SOFI-like: an operationally profitable lender whose FCF is negative (loan-book
    # growth). It must NOT be routed through the cash-burn / runway branch, so no
    # false imminent-liquidity cap fires.
    m = ScreenerMetrics(
        revenue_cagr_3y=32, op_margin=18, gross_margin=83, rote=6,
        shares_cagr_3y=11, sbc_pct_rev=7, insider_ownership=1.4, shareholder_yield=0,
        ocf_capex=-15,
        net_income=481e6, fcf=-4e9, revenue_growth=42, total_cash=3.5e9,
        sector="Financial Services",
    )
    q, _, profile, bd = score(m, "Financial Services")
    assert profile == "FINANCIALS"
    assert bd["pre_profit"] is None                 # not cash-burning
    assert "sector_adjustment" in bd                # FCF/OCF metrics excluded
    assert q == pytest.approx(bd["fundamentals_composite"], abs=0.05)


def test_financials_exclude_fcf_and_ocf_metrics_from_sections():
    # FCF/OCF metrics are structurally distorted for a lender and must not drag the
    # sections down — the same principle as the Section III leverage exclusion.
    m = ScreenerMetrics(revenue_cagr_3y=30, op_margin=18, gross_margin=83,
                        fcf_margin=-110, fcf_cagr_3y=-50, earnings_quality=-7.8,
                        shares_cagr_3y=0, sbc_pct_rev=5, insider_ownership=5,
                        shareholder_yield=0, rote=6)
    s_fin = section_scores(m, "FINANCIALS")
    s_bal = section_scores(m, "BALANCED")
    assert s_fin["I"] > s_bal["I"]     # excluding the -110% FCF margin lifts Section I
    assert s_fin["IV"] > s_bal["IV"]   # excluding the -7.8 earnings quality lifts Section IV


def test_rule_of_40_prefers_statement_yoy_growth():
    from screener.scoring import _rule_of_40
    # Statement YoY wins over the broken info revenue_growth (IREN: 0.0 broken).
    m = ScreenerMetrics(revenue_growth_yoy=167.7, revenue_growth=0.0,
                        revenue_cagr_3y=50.0, op_margin=4.4)
    assert _rule_of_40(m) == pytest.approx(100.0 + 4.4)   # 167.7 capped at 100 + margin
    # Falls back to info revenue_growth when yoy is missing.
    m2 = ScreenerMetrics(revenue_growth=30.0, revenue_cagr_3y=50.0, op_margin=10.0)
    assert _rule_of_40(m2) == pytest.approx(40.0)
    # Falls back to 3y CAGR when both are missing.
    m3 = ScreenerMetrics(revenue_cagr_3y=25.0, op_margin=10.0)
    assert _rule_of_40(m3) == pytest.approx(35.0)


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


def test_heavy_capex_distortion_detection():
    from screener.scoring import _heavy_capex_distortion
    # AMZN-like: healthy EBITDA, positive but tiny FCF, positive op margin.
    amzn = ScreenerMetrics(ebitda=155.9e9, fcf=7.7e9, op_margin=13.1)
    assert _heavy_capex_distortion(amzn) is True
    # healthy converter: FCF a large share of EBITDA -> not distorted
    assert _heavy_capex_distortion(ScreenerMetrics(ebitda=100.0, fcf=60.0, op_margin=20.0)) is False
    # operating loss is a genuine pre-profit burn, handled elsewhere -> not this path
    assert _heavy_capex_distortion(ScreenerMetrics(ebitda=100.0, fcf=1.0, op_margin=-5.0)) is False
    # no EBITDA signal -> not applicable
    assert _heavy_capex_distortion(ScreenerMetrics(ebitda=None, fcf=1.0)) is False


def test_heavy_capex_excludes_fcf_metrics_and_lifts_sections():
    # A heavy-capex reinvestor: the depressed FCF margin (Section I) and OCF/CapEx
    # (Section III) must not drag the score; excluding them lifts both sections.
    base = dict(
        revenue_cagr_3y=12, op_margin=13, op_margin_trajectory=8, gross_margin=50,
        fcf_margin=1.1, fcf_cagr_3y=None, net_debt_ebitda=0.6, net_debt_fcf=12.0,
        ocf_capex=1.06,
    )
    heavy = ScreenerMetrics(**base, ebitda=155.9e9, fcf=7.7e9)
    normal = ScreenerMetrics(**base)  # no ebitda/fcf -> not flagged
    s_heavy = section_scores(heavy, "BALANCED")
    s_normal = section_scores(normal, "BALANCED")
    assert s_heavy["I"] > s_normal["I"]      # excluding the 1.1% FCF margin lifts Section I
    assert s_heavy["III"] > s_normal["III"]  # excluding OCF/CapEx lifts Section III


def test_heavy_capex_breakdown_and_no_false_cap():
    # End-to-end: an AMZN-like profitable heavy-capex name gets the capex adjustment
    # recorded, is NOT routed through the pre-profit branch, and is not capped.
    m = ScreenerMetrics(
        revenue_cagr_3y=12, eps_cagr_3y=None, op_margin=13.1, op_margin_trajectory=8.8,
        gross_margin=50.6, fcf_margin=1.07, roic_ttm=16.8, roic_5y_avg=11.2,
        roic_wacc_spread=9.6, rote=20.5, net_debt_ebitda=0.59, net_debt_fcf=12.0,
        ocf_capex=1.06, shares_cagr_3y=2.0, sbc_pct_rev=2.7, earnings_quality=1.8,
        insider_ownership=8.9, shareholder_yield=0.0,
        ebitda=155.9e9, fcf=7.7e9, net_income=77.7e9, sector="Consumer Cyclical",
    )
    q, _, profile, bd = score(m, "Consumer Cyclical")
    assert profile == "BALANCED"
    assert "capex_adjustment" in bd
    assert bd["pre_profit"] is None      # profitable -> not a pre-profit burn
    assert q > 7.0                       # lifted above the un-adjusted ~6.8


def test_earnings_distortion_detection():
    from screener.scoring import _earnings_distorted
    # ABBV-like: trailing P/E far above forward P/E AND a depressed (negative) EPS CAGR
    # (Allergan amortization + Humira patent-cliff trough).
    assert _earnings_distorted(ScreenerMetrics(trailing_pe=122.0, forward_pe=15.2, eps_cagr_3y=-29.1)) is True
    # NVDA-like: same P/E-ratio signal, but EPS is *growing* fast (forward > trailing
    # because it compounds, not a trough) -> must NOT rescue a legitimately strong signal.
    assert _earnings_distorted(ScreenerMetrics(trailing_pe=60.0, forward_pe=30.0, eps_cagr_3y=80.0)) is False
    # healthy steady name: trailing ~ forward -> not distorted
    assert _earnings_distorted(ScreenerMetrics(trailing_pe=25.0, forward_pe=22.0, eps_cagr_3y=-5.0)) is False
    # negative / absent trailing earnings -> no signal (trailing P/E None or <= 0)
    assert _earnings_distorted(ScreenerMetrics(trailing_pe=None, forward_pe=15.0, eps_cagr_3y=-5.0)) is False
    assert _earnings_distorted(ScreenerMetrics(trailing_pe=-10.0, forward_pe=15.0, eps_cagr_3y=-5.0)) is False
    # signal fires but EPS CAGR unavailable -> nothing to exclude
    assert _earnings_distorted(ScreenerMetrics(trailing_pe=122.0, forward_pe=15.2, eps_cagr_3y=None)) is False


def test_earnings_distortion_excludes_eps_growth_from_section_i():
    # The depressed -29% EPS CAGR must not drag Section I once the distortion fires.
    base = dict(revenue_cagr_3y=1.75, eps_cagr_3y=-29.1, fcf_cagr_3y=-9.8, fcf_margin=29.1,
                op_margin=32.2, op_margin_trajectory=0.44, gross_margin=72.0)
    distorted = ScreenerMetrics(**base, trailing_pe=122.0, forward_pe=15.2)
    normal = ScreenerMetrics(**base, trailing_pe=30.0, forward_pe=28.0)  # no P/E signal
    s_dist = section_scores(distorted, "BALANCED")
    s_norm = section_scores(normal, "BALANCED")
    assert s_dist["I"] > s_norm["I"]   # excluding the -29% EPS CAGR lifts Section I


def test_earnings_distortion_breakdown_and_lift():
    # End-to-end ABBV-like: the earnings adjustment is recorded, the name is NOT routed
    # through the pre-profit branch (it is profitable), and excluding the depressed EPS
    # CAGR lifts the score relative to the same metrics without the distortion signal.
    base = dict(
        revenue_cagr_3y=1.75, eps_cagr_3y=-29.1, fcf_cagr_3y=-9.8, fcf_margin=29.1,
        op_margin=32.2, op_margin_trajectory=0.44, gross_margin=72.0,
        roic_ttm=9.5, roic_5y_avg=8.9, roic_wacc_spread=4.0,
        net_debt_ebitda=2.08, net_debt_fcf=3.5, ocf_capex=15.7,
        shares_cagr_3y=-0.09, sbc_pct_rev=1.56, earnings_quality=4.5,
        insider_ownership=0.1, shareholder_yield=2.9,
        net_income=4.2e9, fcf=17.8e9, ebitda=29.9e9,
    )
    distorted = ScreenerMetrics(**base, trailing_pe=122.0, forward_pe=15.2, sector="Healthcare")
    normal = ScreenerMetrics(**base, trailing_pe=30.0, forward_pe=28.0, sector="Healthcare")
    q_d, _, profile, bd = score(distorted, "Healthcare")
    q_n, _, _, bd_n = score(normal, "Healthcare")
    assert profile == "BALANCED"
    assert "earnings_adjustment" in bd
    assert "earnings_adjustment" not in bd_n
    assert bd["pre_profit"] is None      # profitable -> not a pre-profit burn
    assert q_d > q_n                      # excluding the depressed EPS CAGR lifts the score


def test_acquisition_distortion_detection():
    from screener.scoring import _acquisition_distorted
    # AMD-like: goodwill dominates invested capital, tangible ROIC far above reported,
    # trailing P/E >> forward P/E (amortization-depressed, recovery priced in).
    amd = ScreenerMetrics(goodwill_intangible_share=0.63, roic_ttm=5.1,
                          roic_ex_goodwill=13.8, trailing_pe=185.0, forward_pe=42.0)
    assert _acquisition_distorted(amd) is True
    # Low goodwill share -> not acquisition-heavy -> no adjustment.
    assert _acquisition_distorted(ScreenerMetrics(
        goodwill_intangible_share=0.10, roic_ttm=5.1, roic_ex_goodwill=6.0,
        trailing_pe=185.0, forward_pe=42.0)) is False
    # Goodwill-heavy but no P/E recovery signal (trailing ~ forward): a genuine
    # over-payer must NOT be rescued.
    assert _acquisition_distorted(ScreenerMetrics(
        goodwill_intangible_share=0.63, roic_ttm=5.1, roic_ex_goodwill=13.8,
        trailing_pe=20.0, forward_pe=19.0)) is False
    # Fires even with a positive EPS CAGR (unlike _earnings_distorted): a fast-growing
    # acquirer still carries acquisition amortization. eps_cagr is irrelevant here.
    assert _acquisition_distorted(ScreenerMetrics(
        goodwill_intangible_share=0.63, roic_ttm=5.1, roic_ex_goodwill=13.8,
        trailing_pe=185.0, forward_pe=42.0, eps_cagr_3y=46.7)) is True
    # Missing tangible ROIC -> no adjustment.
    assert _acquisition_distorted(ScreenerMetrics(
        goodwill_intangible_share=0.63, roic_ttm=5.1, roic_ex_goodwill=None,
        trailing_pe=185.0, forward_pe=42.0)) is False


def test_wacc_crossover_detection():
    from screener.scoring import _wacc_crossover
    # VST-like: reported ROIC below WACC, ex-goodwill ROIC at/above WACC -> crossover.
    assert _wacc_crossover(ScreenerMetrics(
        roic_ttm=7.8, wacc=9.6, roic_ex_goodwill=10.1)) is True
    # Reported ROIC already clears WACC -> no rescue needed, not a crossover.
    assert _wacc_crossover(ScreenerMetrics(
        roic_ttm=11.0, wacc=9.6, roic_ex_goodwill=12.0)) is False
    # AMD-like: even the ex-goodwill ROIC is still below WACC -> not a crossover.
    assert _wacc_crossover(ScreenerMetrics(
        roic_ttm=5.1, wacc=14.5, roic_ex_goodwill=13.8)) is False
    # Missing data -> False.
    assert _wacc_crossover(ScreenerMetrics(roic_ttm=7.8, wacc=None,
                                           roic_ex_goodwill=10.1)) is False
    # Boundary: ex-goodwill ROIC exactly at WACC is inclusive (<=) -> crossover.
    assert _wacc_crossover(ScreenerMetrics(
        roic_ttm=7.8, wacc=10.1, roic_ex_goodwill=10.1)) is True
    # Boundary: reported ROIC exactly at WACC is exclusive (<) -> not a crossover.
    assert _wacc_crossover(ScreenerMetrics(
        roic_ttm=9.6, wacc=9.6, roic_ex_goodwill=10.1)) is False


def test_effective_goodwill_floor_is_dynamic():
    from screener.scoring import (_effective_goodwill_floor,
                                  GOODWILL_SHARE_FLOOR, GOODWILL_SHARE_FLOOR_XOVER)
    # Crossover present -> lowered floor.
    assert _effective_goodwill_floor(ScreenerMetrics(
        roic_ttm=7.8, wacc=9.6, roic_ex_goodwill=10.1)) == GOODWILL_SHARE_FLOOR_XOVER
    # No crossover -> strict floor.
    assert _effective_goodwill_floor(ScreenerMetrics(
        roic_ttm=5.1, wacc=14.5, roic_ex_goodwill=13.8)) == GOODWILL_SHARE_FLOOR


def test_dynamic_floor_catches_vst_without_regressing_amd():
    from screener.scoring import _acquisition_distorted
    # VST-like: goodwill 0.23 (below the 0.30 flat floor) BUT the WACC crossover holds
    # (7.8 < 9.6 <= 10.1) -> the floor drops to 0.15 -> fires.
    vst = ScreenerMetrics(goodwill_intangible_share=0.23, roic_ttm=7.8, wacc=9.6,
                          roic_ex_goodwill=10.1, trailing_pe=26.6, forward_pe=14.7)
    assert _acquisition_distorted(vst) is True
    # Same VST metrics but no crossover (WACC bumped above the ex-goodwill ROIC):
    # floor stays 0.30, 0.23 < 0.30 -> does NOT fire. Isolates the floor mechanism.
    vst_no_xover = ScreenerMetrics(goodwill_intangible_share=0.23, roic_ttm=7.8,
                                   wacc=10.5, roic_ex_goodwill=10.1,
                                   trailing_pe=26.6, forward_pe=14.7)
    assert _acquisition_distorted(vst_no_xover) is False
    # AMD-like no-regression: goodwill 0.63, ex-goodwill ROIC 13.8 still < WACC 14.5
    # (no crossover) -> qualifies via the unchanged 0.30 floor.
    amd = ScreenerMetrics(goodwill_intangible_share=0.63, roic_ttm=5.1, wacc=14.5,
                          roic_ex_goodwill=13.8, trailing_pe=185.0, forward_pe=42.0)
    assert _acquisition_distorted(amd) is True


def test_dynamic_floor_does_not_rescue_value_destroyer():
    from screener.scoring import _acquisition_distorted
    # INTC-like negative control: no crossover keeps the floor at 0.30, and its 0.17 goodwill
    # share is below that -> rejected at the floor check (the lowered 0.15 tier never applies).
    intc = ScreenerMetrics(goodwill_intangible_share=0.17, roic_ttm=1.3, wacc=13.6,
                           roic_ex_goodwill=1.6, trailing_pe=None, forward_pe=None)
    assert _acquisition_distorted(intc) is False


def test_low_floor_tier_still_requires_pe_trough():
    from screener.scoring import _acquisition_distorted
    # Crossover holds (floor drops to 0.15) and goodwill 0.23 clears it, but the P/E gate
    # fails (trailing ~ forward) -> still not rescued. Proves the P/E-trough gate applies
    # on the lowered tier too, not just the 0.30 tier.
    assert _acquisition_distorted(ScreenerMetrics(
        goodwill_intangible_share=0.23, roic_ttm=7.8, wacc=9.6, roic_ex_goodwill=10.1,
        trailing_pe=20.0, forward_pe=19.0)) is False


def test_acquisition_distortion_lifts_section_ii():
    # The goodwill-inflated ROIC drags Section II; scoring it on tangible invested
    # capital lifts the section. ROTE (already tangible) is unchanged either way.
    base = dict(roic_ttm=5.1, roic_5y_avg=2.6, roic_wacc_spread=-11.8, rote=20.5,
                wacc=14.5, roic_ex_goodwill=13.8, roic_5y_ex_goodwill=9.9)
    distorted = ScreenerMetrics(**base, goodwill_intangible_share=0.63,
                                trailing_pe=185.0, forward_pe=42.0)
    normal = ScreenerMetrics(**base, goodwill_intangible_share=0.63,
                             trailing_pe=20.0, forward_pe=19.0)  # no recovery signal
    s_dist = section_scores(distorted, "TECH_GROWTH")
    s_norm = section_scores(normal, "TECH_GROWTH")
    assert s_dist["II"] > s_norm["II"]


def test_acquisition_distortion_breakdown_and_lift():
    # End-to-end AMD-like: the roic adjustment is recorded, the tangible ROIC is scored
    # (lifting the score vs. the same metrics without the distortion signal), and the
    # name is NOT routed through the pre-profit branch (it is profitable).
    base = dict(
        revenue_cagr_3y=13.6, eps_cagr_3y=46.7, fcf_cagr_3y=29.3, fcf_margin=19.4,
        op_margin=14.4, op_margin_trajectory=5.3, gross_margin=53.1,
        roic_ttm=5.1, roic_5y_avg=2.6, roic_wacc_spread=-11.8, rote=20.5, wacc=14.5,
        roic_ex_goodwill=13.8, roic_5y_ex_goodwill=9.9, goodwill_intangible_share=0.63,
        net_debt_ebitda=-1.14, net_debt_fcf=-1.26, ocf_capex=7.9,
        shares_cagr_3y=1.4, sbc_pct_rev=4.7, earnings_quality=1.8,
        insider_ownership=0.4, shareholder_yield=0.2,
        net_income=4.3e9, fcf=6.7e9, ebitda=7.4e9,
    )
    distorted = ScreenerMetrics(**base, trailing_pe=185.0, forward_pe=42.0, sector="Technology")
    normal = ScreenerMetrics(**base, trailing_pe=25.0, forward_pe=22.0, sector="Technology")
    q_d, sec_d, profile, bd = score(distorted, "Technology")
    q_n, _, _, bd_n = score(normal, "Technology")
    assert profile == "TECH_GROWTH"
    assert "roic_adjustment" in bd
    assert "roic_adjustment" not in bd_n
    assert bd["roic_adjustment"]["tangible_roic"] == pytest.approx(13.8, abs=0.1)
    assert bd["pre_profit"] is None            # profitable -> not a pre-profit burn
    assert q_d > q_n                            # tangible ROIC lifts the score
    assert q_d == pytest.approx(7.2, abs=0.3)


def test_dynamic_floor_lifts_section_ii_for_vst_like():
    # VST-like DEFENSIVE_INCOME name: goodwill 0.23 with a WACC crossover. The dynamic
    # floor lets the ex-goodwill ROIC score Section II, lifting it (and the headline)
    # versus the same metrics with the crossover removed (WACC above ex-goodwill ROIC).
    base = dict(
        revenue_cagr_3y=8.9, fcf_margin=7.4, op_margin=26.6, op_margin_trajectory=20.1,
        gross_margin=38.6, roic_ttm=7.8, roic_5y_avg=8.3, roic_wacc_spread=-1.8,
        rote=None, roic_ex_goodwill=10.1, roic_5y_ex_goodwill=11.0,
        goodwill_intangible_share=0.23,
        net_debt_ebitda=2.84, net_debt_fcf=14.6, ocf_capex=1.48,
        shares_cagr_3y=-4.6, sbc_pct_rev=0.64, earnings_quality=4.3,
        insider_ownership=0.79, shareholder_yield=2.85,
        net_income=944e6, fcf=1318e6, ebitda=6790e6,
        trailing_pe=26.6, forward_pe=14.7,
    )
    distorted = ScreenerMetrics(**base, wacc=9.6, sector="Utilities")        # crossover
    normal = ScreenerMetrics(**{**base, "wacc": 10.5}, sector="Utilities")   # no crossover
    s_dist = section_scores(distorted, "DEFENSIVE_INCOME")
    s_norm = section_scores(normal, "DEFENSIVE_INCOME")
    assert s_dist["II"] > s_norm["II"]

    q_d, _, profile, bd = score(distorted, "Utilities")
    q_n, _, _, bd_n = score(normal, "Utilities")
    assert profile == "DEFENSIVE_INCOME"
    assert "roic_adjustment" in bd
    assert "roic_adjustment" not in bd_n
    assert bd["roic_adjustment"]["tangible_roic"] == pytest.approx(10.1, abs=0.1)
    assert bd["pre_profit"] is None            # profitable -> not a pre-profit burn
    assert q_d > q_n
    assert q_d == pytest.approx(5.7, abs=0.2)


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


def _iren_inputs():
    from screener.models import StatementSeries, ScreenerInputs
    # IREN-shaped: broken info operatingMargins (-64.5%) & revenueGrowth (0.0), but
    # healthy statements. FCF deeply negative from a data-centre capex build-out.
    inc = StatementSeries(years=[2025, 2024, 2023, 2022], rows={
        "EBIT": [22.1e6, -30e6, -40e6, -20e6], "Tax Rate For Calcs": [0.21] * 4,
        "Net Income": [87e6, -170e6, -50e6, -10e6],
        "Total Revenue": [501e6, 187e6, 75e6, 30e6],
        "Interest Expense": [5e6, 4e6, 3e6, 2e6],
        "Gross Profit": [340e6, 120e6, 45e6, 18e6],
        "Operating Income": [22.1e6, -30e6, -40e6, -20e6],
        "Diluted EPS": [0.77, -1.5, -0.6, -0.2],
        "Diluted Average Shares": [200e6, 150e6, 120e6, 100e6]})
    bal = StatementSeries(years=[2025, 2024, 2023, 2022], rows={
        "Invested Capital": [2000e6, 1200e6, 800e6, 500e6],
        "Tangible Book Value": [1500e6, 900e6, 600e6, 400e6],
        "Net Debt": [-200e6, -100e6, 50e6, 100e6],
        "Ordinary Shares Number": [200e6, 150e6, 120e6, 100e6]})
    cf = StatementSeries(years=[2025, 2024, 2023, 2022], rows={
        "Free Cash Flow": [-1.13e9, -800e6, -400e6, -200e6],
        "Operating Cash Flow": [246e6, 50e6, -20e6, -10e6],
        "Capital Expenditure": [-1.37e9, -850e6, -380e6, -190e6],
        "Stock Based Compensation": [30e6] * 4,
        "Repurchase Of Capital Stock": [0] * 4, "Cash Dividends Paid": [0] * 4})
    info = {"symbol": "IREN", "shortName": "IREN Limited", "sector": "Technology",
            "beta": 2.5, "marketCap": 8e9, "totalDebt": 300e6, "totalCash": 500e6,
            "ebitda": 147e6, "operatingMargins": -0.645, "grossMargins": 0.68,
            "heldPercentInsiders": 0.10, "trailingPE": 53.0, "forwardPE": 30.0,
            "trailingPegRatio": 1.0, "priceToSalesTrailing12Months": 16.0,
            "enterpriseValue": 7.8e9, "revenueGrowth": 0.0, "totalRevenue": 501e6,
            "freeCashflow": -1.13e9}
    return ScreenerInputs(ticker="IREN", info=info, income=inc, balance=bal,
                          cashflow=cf, price_monthly=tuple(), risk_free=0.045)


def test_iren_shaped_profitable_capex_investor_not_pre_profit():
    from screener.metrics import compute_metrics
    from screener.scoring import score
    inp = _iren_inputs()
    m = compute_metrics(inp)
    # Statement wins over both broken info fields.
    assert m.op_margin == pytest.approx(22.1e6 / 501e6 * 100, abs=0.5)   # not -64.5
    assert m.revenue_growth_yoy == pytest.approx((501.0 / 187.0 - 1) * 100, abs=1.0)
    q, _, profile, bd = score(m, inp.info["sector"])
    # Positive op margin -> NOT routed through the operating-loss / pre-profit branch.
    assert bd["pre_profit"] is None
    # Capex-eaten FCF metrics excluded as deliberate reinvestment (AMZN-style).
    assert "capex_adjustment" in bd
    # Clear of the reported 4.0 hole (exact value not asserted — see unit tests).
    assert q > 4.0
