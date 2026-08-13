from risk_reward.models import RiskRewardInputs
from risk_reward.scoring import build_metric_scores


def _inputs(info=None, **kw):
    base = dict(ticker="X", info=info or {}, company_name=None, price=100.0,
                high_52w=130.0, ma_200=110.0, ma_50=105.0, rsi=35.0, volatility=0.30)
    base.update(kw)
    return RiskRewardInputs(**base)


def test_valuation_uses_peg_when_present():
    ms = build_metric_scores(_inputs(info={"pegRatio": 1.0}))
    assert ms["valuation"].source == "peg"
    assert ms["valuation"].score == 5.0
    assert ms["valuation"].dropped is False


def test_valuation_falls_back_to_earnings_yield():
    # no PEG, forwardPE 12.5 -> earnings yield 0.08 -> score 5
    ms = build_metric_scores(_inputs(info={"forwardPE": 12.5}))
    assert ms["valuation"].source == "earnings_yield"
    assert ms["valuation"].score == 5.0


def test_slot_dropped_when_no_source_resolves():
    ms = build_metric_scores(_inputs(info={}))
    assert ms["valuation"].dropped is True
    assert ms["valuation"].score is None
    assert ms["valuation"].weight > 0  # weight retained for reference


def test_discount_and_trend_from_price_and_ma():
    ms = build_metric_scores(_inputs(info={}))
    # discount = (130-100)/130 = 0.2308 -> between a3=0.12 and a5=0.25 -> ~4.6
    assert ms["discount"].source == "discount"
    assert 4.0 <= ms["discount"].score <= 5.0
    # trend = (100-110)/110 = -0.0909 -> between a3=0 and a5=-0.15 (danger) -> ~4.2
    assert ms["trend"].source == "trend"
    assert ms["trend"].score is not None


def test_leverage_percent_debt_to_equity():
    ms = build_metric_scores(_inputs(info={"debtToEquity": 150.0}))
    assert ms["leverage"].source == "debt_to_equity"
    assert ms["leverage"].score == 5.0


def test_analyst_weight_at_cap_when_well_covered_and_tight():
    # 25 analysts (>= hi=20) + spread (140-120)/130 = 15% (<= 20%) -> c=1 -> weight 0.18
    info = {"targetMeanPrice": 130.0, "targetHighPrice": 140.0,
            "targetLowPrice": 120.0, "numberOfAnalystOpinions": 25}
    ms = build_metric_scores(_inputs(info=info))
    assert ms["analyst_upside"].source == "analyst_upside"
    assert round(ms["analyst_upside"].weight, 4) == 0.18


def test_analyst_weight_at_floor_when_thin_and_dispersed():
    # 1 analyst (< lo=3) + huge spread -> c=0 -> weight 0.08 (metric still scores)
    info = {"targetMeanPrice": 130.0, "targetHighPrice": 260.0,
            "targetLowPrice": 30.0, "numberOfAnalystOpinions": 1}
    ms = build_metric_scores(_inputs(info=info))
    assert ms["analyst_upside"].score is not None
    assert round(ms["analyst_upside"].weight, 4) == 0.08


def test_analyst_weight_floors_when_confidence_data_missing():
    # only targetMeanPrice present: metric scores, but no coverage/dispersion -> floor
    ms = build_metric_scores(_inputs(info={"targetMeanPrice": 130.0}))
    assert ms["analyst_upside"].score is not None
    assert round(ms["analyst_upside"].weight, 4) == 0.08


def test_negative_peg_falls_back_to_earnings_yield():
    # pre-profit name: yfinance reports a NEGATIVE pegRatio. Must NOT be used
    # (and must NOT score 5.0 via peg) -> falls through to earnings_yield.
    ms = build_metric_scores(_inputs(info={"pegRatio": -2.0, "forwardPE": 12.5}))
    assert ms["valuation"].source == "earnings_yield"
    assert ms["valuation"].score == 5.0


def test_negative_peg_alone_drops_valuation_slot():
    # negative PEG with no fallback source available must drop the slot,
    # never fabricate a 5.0 "best" reward score.
    ms = build_metric_scores(_inputs(info={"pegRatio": -2.0}))
    assert ms["valuation"].dropped is True
    assert ms["valuation"].score is None


def test_growth_stmt_override_fires_on_iren_shaped_gap():
    # IREN-shaped: info.revenueGrowth reads a flat/negative artifact (-0.0) while the
    # statement shows real, strong annual growth (+167.7%) -> gap (5.0-1.0=4.0) >= 1.0.
    ms = build_metric_scores(_inputs(info={"revenueGrowth": -0.0},
                                     revenue_growth_stmt=1.677))
    assert ms["growth"].source == "revenue_growth_stmt"
    assert ms["growth"].score == 5.0


def test_growth_stmt_override_fires_on_riot_shaped_gap():
    # RIOT-shaped: info reads a modest positive (+13.9%, score 3.52) while the
    # statement reads much stronger (+71.9%, score 5.0) -> gap 1.48 >= 1.0 (the
    # smallest live true-positive in the swept basket).
    ms = build_metric_scores(_inputs(info={"revenueGrowth": 0.139},
                                     revenue_growth_stmt=0.719))
    assert ms["growth"].source == "revenue_growth_stmt"
    assert ms["growth"].score == 5.0


def test_growth_stmt_no_override_when_gap_below_threshold():
    # info already reads decently (score ~4.33); statement only slightly better
    # (score 5.0) -> gap 0.67 < 1.0 -> stays on info (not every small divergence
    # should flip the source).
    ms = build_metric_scores(_inputs(info={"revenueGrowth": 0.20},
                                     revenue_growth_stmt=0.25))
    assert ms["growth"].source == "revenue_growth"


def test_growth_stmt_no_override_when_info_reads_better_corz_shaped():
    # CORZ-shaped: info reads a large positive (+108.8%, saturates at 5.0) while the
    # statement reads NEGATIVE (-37.5%, score 1.0) -- a real business-transition
    # divergence, not a feed artifact. The guard is directional (only fires when
    # statement is BETTER than info) so this must stay on info, unmoved.
    ms = build_metric_scores(_inputs(info={"revenueGrowth": 1.088},
                                     revenue_growth_stmt=-0.375))
    assert ms["growth"].source == "revenue_growth"
    assert ms["growth"].score == 5.0


def test_growth_stmt_ignored_when_missing():
    # No statement data available (None) -> falls through untouched, same as before
    # this guard existed.
    ms = build_metric_scores(_inputs(info={"revenueGrowth": 0.05}))
    assert ms["growth"].source == "revenue_growth"


def test_burn_stmt_override_fires_on_iren_shaped_gap():
    # IREN-shaped: info.operatingMargins reads a deep artifact (-64.5%, saturates
    # danger score at 5.0) while the statement shows real mild profitability (+4.4%,
    # score ~2.41) -> gap 2.59 >= 1.0, info OVERSTATES risk.
    ms = build_metric_scores(_inputs(info={"operatingMargins": -0.645},
                                     operating_margin_stmt=0.044))
    assert ms["burn"].source == "operating_margin_stmt"
    assert round(ms["burn"].score, 2) == 2.41


def test_burn_stmt_no_override_when_gap_below_threshold():
    # Both already read as the safest score (1.0) -- no meaningful gap to correct.
    ms = build_metric_scores(_inputs(info={"operatingMargins": 0.20},
                                     operating_margin_stmt=0.18))
    assert ms["burn"].source == "operating_margin"


def test_burn_stmt_no_override_when_info_reads_better_corz_shaped():
    # CORZ-shaped: info reads mildly positive (+6.9%, score ~2.08) while the
    # statement shows a real, deep operating LOSS (-70.4%, score 5.0, likely an
    # impairment/restructuring charge). The guard must not fire here -- correcting
    # in this direction would mask real risk, not artifacts, and this failure mode
    # is unproven (unlike IREN's). Stays on info.
    ms = build_metric_scores(_inputs(info={"operatingMargins": 0.069},
                                     operating_margin_stmt=-0.704))
    assert ms["burn"].source == "operating_margin"


def test_burn_stmt_ignored_when_missing():
    ms = build_metric_scores(_inputs(info={"operatingMargins": -0.10}))
    assert ms["burn"].source == "operating_margin"
