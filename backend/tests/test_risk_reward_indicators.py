import math
from risk_reward.indicators import sma, rsi, realized_vol


def test_sma_last_n():
    assert sma([1, 2, 3, 4, 5], 3) == 4.0            # mean(3,4,5)
    assert sma([1, 2], 3) is None                     # not enough data


def test_rsi_all_gains_is_100():
    closes = list(range(1, 20))                        # strictly rising
    assert rsi(closes, 14) == 100.0


def test_rsi_needs_period_plus_one():
    assert rsi([1, 2, 3], 14) is None


def test_rsi_midrange_for_alternating():
    closes = [10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11, 10, 11]
    val = rsi(closes, 14)
    assert val is not None and 40 <= val <= 60


def test_realized_vol_zero_for_flat_series():
    assert realized_vol([5, 5, 5, 5]) == 0.0


def test_realized_vol_positive_and_annualized():
    closes = [100, 101, 99, 102, 98, 103]
    v = realized_vol(closes, 252)
    assert v is not None and v > 0
    assert realized_vol([100]) is None
