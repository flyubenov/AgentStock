# backend/tests/test_risk_reward_aggregation.py
from risk_reward.models import MetricScore
from risk_reward.config import REWARD_SLOTS, RISK_SLOTS, CONFIG
from risk_reward.scoring import aggregate, tier_for


def _scores(reward_val, risk_val, n_reward=6, n_risk=6):
    out = {}
    for idx, slot in enumerate(REWARD_SLOTS):
        dropped = idx >= n_reward
        out[slot] = MetricScore(raw=1.0, source="x", score=None if dropped else reward_val,
                                weight=CONFIG.weights[slot], dropped=dropped)
    for idx, slot in enumerate(RISK_SLOTS):
        dropped = idx >= n_risk
        out[slot] = MetricScore(raw=1.0, source="x", score=None if dropped else risk_val,
                                weight=CONFIG.weights[slot], dropped=dropped)
    return out


def test_ratio_reward_over_risk():
    agg = aggregate(_scores(4.0, 2.0))
    assert agg.status == "completed"
    assert round(agg.reward, 3) == 4.0 and round(agg.risk, 3) == 2.0
    assert round(agg.ratio, 3) == 2.0
    assert agg.tier == "Asymmetric Upside"


def test_clamp_upper_and_lower():
    assert aggregate(_scores(5.0, 1.0)).ratio == 5.0    # 5.0 exactly at clamp
    assert aggregate(_scores(1.0, 5.0)).ratio == 0.2    # 0.2 at clamp


def test_renormalizes_when_metrics_dropped():
    # only 3 reward + 3 risk active, all equal -> averages unaffected, still scored
    agg = aggregate(_scores(3.0, 3.0, n_reward=3, n_risk=3))
    assert agg.status == "completed"
    assert round(agg.ratio, 3) == 1.0
    assert agg.tier == "Balanced"


def test_coverage_floor_reward():
    agg = aggregate(_scores(4.0, 2.0, n_reward=1, n_risk=6))
    assert agg.status == "insufficient_data"
    assert agg.ratio is None and agg.tier is None


def test_coverage_floor_risk():
    agg = aggregate(_scores(4.0, 2.0, n_reward=6, n_risk=1))
    assert agg.status == "insufficient_data"


def test_tier_boundaries():
    assert tier_for(2.0) == "Asymmetric Upside"
    assert tier_for(1.3) == "Reward-Favored"
    assert tier_for(0.8) == "Balanced"
    assert tier_for(0.5) == "Risk-Favored"
    assert tier_for(0.3) == "Value Trap"
