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
