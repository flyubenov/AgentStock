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
