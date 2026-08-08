# backend/tests/test_risk_reward_config.py
from risk_reward.config import CONFIG, REWARD_SLOTS, RISK_SLOTS


def test_axis_weights_each_sum_to_one():
    rw = sum(CONFIG.weights[s] for s in REWARD_SLOTS)
    kw = sum(CONFIG.weights[s] for s in RISK_SLOTS)
    assert round(rw, 6) == 1.0
    assert round(kw, 6) == 1.0


def test_every_source_has_anchors_and_every_slot_has_sources():
    for slot in REWARD_SLOTS + RISK_SLOTS:
        assert CONFIG.axis[slot] in ("reward", "risk")
        assert CONFIG.sources[slot], f"{slot} has no source chain"
        for src in CONFIG.sources[slot]:
            assert src in CONFIG.anchors, f"missing anchors for {src}"


def test_clamp_and_floor_defaults():
    assert CONFIG.ratio_clamp == (0.2, 5.0)
    assert CONFIG.min_reward == 2 and CONFIG.min_risk == 2


def test_analyst_weight_knobs_bracket_base():
    # floor 8% <= nominal base 12% <= cap (floor+span) 18%
    cap = CONFIG.analyst_weight_floor + CONFIG.analyst_weight_span
    assert CONFIG.analyst_weight_floor == 0.08
    assert cap == 0.18
    assert CONFIG.analyst_weight_floor <= CONFIG.weights["analyst_upside"] <= cap
    assert CONFIG.analyst_coverage_lo < CONFIG.analyst_coverage_hi
    assert CONFIG.analyst_spread_lo < CONFIG.analyst_spread_hi
