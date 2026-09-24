from screener.models import ScreenerMetrics
from screener.scoring import section_metric_details, section_scores, _mean


def _tech_metrics() -> ScreenerMetrics:
    return ScreenerMetrics(
        revenue_cagr_3y=0.25, eps_cagr_3y=0.30, fcf_cagr_3y=0.22, fcf_margin=0.28,
        op_margin=0.31, op_margin_trajectory=0.02, gross_margin=0.46,
        roic_ttm=0.55, roic_5y_avg=0.48, wacc=0.09, roic_wacc_spread=0.46, rote=0.60,
        net_debt_ebitda=0.4, net_debt_fcf=0.5, ocf_capex=6.0,
        shares_cagr_3y=-0.03, sbc_pct_rev=0.04, earnings_quality=1.05,
        insider_ownership=0.01, shareholder_yield=0.04,
    )


def test_every_section_reports_its_metrics():
    details = section_metric_details(_tech_metrics(), "TECH_GROWTH")
    assert [len(details[k]) for k in ("I", "II", "III", "IV")] == [7, 4, 3, 5]
    assert all(d.label for d in details["I"])


def test_the_section_score_is_the_mean_of_its_metric_scores():
    m, profile = _tech_metrics(), "TECH_GROWTH"
    details = section_metric_details(m, profile)
    sections = section_scores(m, profile)
    for key in ("I", "II", "III", "IV"):
        assert sections[key] == _mean([d.score for d in details[key]])


def test_an_excluded_metric_is_flagged_and_scoreless():
    details = section_metric_details(_tech_metrics(), "FINANCIALS")
    fcf_metrics = [d for d in details["I"] if "FCF" in d.label]
    assert fcf_metrics, "expected FCF metrics in section I"
    assert all(d.excluded and d.score is None for d in fcf_metrics)
    assert all(d.excluded_by for d in fcf_metrics)


def test_an_excluded_metric_does_not_drag_the_section_score_down():
    m, profile = _tech_metrics(), "FINANCIALS"
    details = section_metric_details(m, profile)
    scored = [d.score for d in details["I"] if not d.excluded]
    assert section_scores(m, profile)["I"] == _mean(scored)


def test_the_raw_figure_travels_with_the_score():
    details = section_metric_details(_tech_metrics(), "TECH_GROWTH")
    roic = next(d for d in details["II"] if d.label.startswith("ROIC (trailing)"))
    assert roic.raw == 0.55


# --- Section III exclusion reasons -------------------------------------------------
# Section III is the only place this task introduces genuinely new behaviour: the
# reasons are not in the pre-refactor code, which simply nulled the scores. Tasks 5, 9
# and 10 render these, so each policy drop is pinned to its exact reason string here.


def _leverage(**over) -> ScreenerMetrics:
    """A plain, undistorted balance sheet: both leverage ratios score, OCF/CapEx scores,
    and no drop fires. Each test below perturbs only what its branch needs."""
    base = dict(net_debt_ebitda=1.0, net_debt_fcf=1.5, ocf_capex=4.0,
                ebitda=1_000_000_000.0, fcf=400_000_000.0, op_margin=20.0)
    base.update(over)
    return ScreenerMetrics(**base)


def _iii(m: ScreenerMetrics, profile: str = "BALANCED") -> dict[str, "object"]:
    return {d.label: d for d in section_metric_details(m, profile)["III"]}


def test_nothing_is_excluded_on_an_undistorted_balance_sheet():
    # Guards the tests below: each reason must be caused by the perturbation, not by
    # the shared fixture already tripping a branch.
    for d in _iii(_leverage()).values():
        assert not d.excluded and d.excluded_by is None and d.score is not None


def test_a_recent_acquisition_drops_both_leverage_metrics():
    # Fresh, balance-sheet-dominating deal (goodwill dominates invested capital, ROIC
    # is goodwill-depressed, trailing P/E >> forward) and the acquirer levered up.
    m = _leverage(net_debt_ebitda=3.5, net_debt_fcf=6.0,
                  goodwill_intangible_share=0.95, roic_ttm=6.0, roic_ex_goodwill=14.0,
                  trailing_pe=60.0, forward_pe=20.0)
    iii = _iii(m)
    for label in ("Net debt / EBITDA", "Net debt / FCF"):
        assert iii[label].excluded
        assert iii[label].excluded_by == "Recent acquisition"
        assert iii[label].score is None
    # the undistorted coverage metric is what the balance sheet is judged on instead
    assert not iii["Operating cash flow / capex"].excluded


def test_a_heavy_capex_cycle_drops_the_fcf_derived_metrics():
    # Healthy EBITDA and a real operating margin, but capex has eaten FCF down to a
    # negligible fraction of EBITDA -> the FCF-derived metrics are unrepresentative.
    m = _leverage(ebitda=1_000_000_000.0, fcf=50_000_000.0, op_margin=20.0)
    iii = _iii(m)
    for label in ("Net debt / FCF", "Operating cash flow / capex"):
        assert iii[label].excluded
        assert iii[label].excluded_by == "Heavy capex cycle"
        assert iii[label].score is None
    # EBITDA leverage is undistorted, so the balance sheet is judged on it
    assert not iii["Net debt / EBITDA"].excluded


def test_the_balance_sheet_dual_check_drops_the_noisy_fcf_ratio():
    # ND/FCF looks far worse than ND/EBITDA while EBITDA leverage is healthy -> the
    # FCF ratio is capex-cycle noise, not leverage.
    m = _leverage(net_debt_ebitda=1.2, net_debt_fcf=9.0, ocf_capex=2.0)
    ndf = _iii(m)["Net debt / FCF"]
    assert ndf.excluded and ndf.score is None
    assert ndf.excluded_by == "Balance-sheet dual-check"


def test_a_negative_ebitda_leaves_its_leverage_ratio_unscored():
    # Positive net debt over negative EBITDA gives a negative ratio, which
    # leverage_score would otherwise read as pristine net cash.
    nde = _iii(_leverage(net_debt_ebitda=-3.43, ebitda=-185_000_000.0,
                         op_margin=-30.0))["Net debt / EBITDA"]
    assert nde.excluded and nde.score is None
    assert nde.excluded_by == "Not meaningful at negative EBITDA"


def test_a_negative_fcf_leaves_its_leverage_ratio_unscored():
    ndf = _iii(_leverage(net_debt_fcf=-2.1, fcf=-300_000_000.0,
                         op_margin=-30.0))["Net debt / FCF"]
    assert ndf.excluded and ndf.score is None
    assert ndf.excluded_by == "Not meaningful at negative FCF"


def test_a_missing_input_is_scoreless_but_not_excluded():
    # The distinction the breakdown table renders: "we did not apply this metric"
    # (a policy drop, struck through with a reason) vs "we had no data" (simply blank).
    m = _leverage(net_debt_ebitda=None, net_debt_fcf=9.0, ocf_capex=2.0)
    iii = _iii(m)
    missing = iii["Net debt / EBITDA"]
    assert missing.score is None
    assert missing.excluded is False and missing.excluded_by is None
    # ...while a metric dropped by a calibration in the same section says why
    dropped = _iii(_leverage(net_debt_ebitda=1.2, net_debt_fcf=9.0,
                             ocf_capex=2.0))["Net debt / FCF"]
    assert dropped.score is None
    assert dropped.excluded is True and dropped.excluded_by
