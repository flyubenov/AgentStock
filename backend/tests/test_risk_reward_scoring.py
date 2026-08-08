import math
from risk_reward.scoring import score_metric


def test_exact_anchors_reward_direction():
    # PEG: lower is better -> a5=1.0, a3=1.5, a1=3.0
    assert score_metric(1.0, 1.0, 1.5, 3.0) == 5.0
    assert score_metric(1.5, 1.0, 1.5, 3.0) == 3.0
    assert score_metric(3.0, 1.0, 1.5, 3.0) == 1.0


def test_linear_between_anchors():
    # PRD example: PEG 1.25 -> 4.0
    assert score_metric(1.25, 1.0, 1.5, 3.0) == 4.0


def test_saturates_beyond_extremes():
    assert score_metric(0.2, 1.0, 1.5, 3.0) == 5.0   # cheaper than a5
    assert score_metric(9.0, 1.0, 1.5, 3.0) == 1.0   # pricier than a1


def test_danger_direction_increasing_anchors():
    # D/E: higher is worse -> a5=150, a3=90, a1=40
    assert score_metric(150.0, 150.0, 90.0, 40.0) == 5.0
    assert score_metric(40.0, 150.0, 90.0, 40.0) == 1.0
    assert score_metric(200.0, 150.0, 90.0, 40.0) == 5.0


def test_none_and_nan_return_none():
    assert score_metric(None, 1.0, 1.5, 3.0) is None
    assert score_metric(math.nan, 1.0, 1.5, 3.0) is None
    assert score_metric("x", 1.0, 1.5, 3.0) is None
