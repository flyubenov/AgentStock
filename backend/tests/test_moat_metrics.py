import pytest
from moat.metrics import mean, pstdev, persistence_fraction, coef_of_variation


def test_mean_and_pstdev():
    assert mean([]) is None
    assert pstdev([]) is None
    assert mean([2.0, 4.0]) == pytest.approx(3.0)
    assert pstdev([2.0, 4.0]) == pytest.approx(1.0)  # population sd of {2,4}


def test_persistence_fraction():
    assert persistence_fraction([], 5.0) is None
    assert persistence_fraction([10.0, 12.0], None) is None
    # 3 of 4 years strictly above the 8% hurdle
    assert persistence_fraction([12.0, 9.0, 8.0, 20.0], 8.0) == pytest.approx(3 / 4)
    # exactly-equal does not count (strictly greater)
    assert persistence_fraction([8.0, 8.0], 8.0) == pytest.approx(0.0)


def test_coef_of_variation():
    assert coef_of_variation([]) is None
    assert coef_of_variation([-1.0, 1.0]) is None       # mean 0 -> None
    assert coef_of_variation([-5.0, -5.0]) is None       # negative mean -> None
    # stable series -> low CoV; volatile -> high CoV
    stable = coef_of_variation([20.0, 21.0, 19.0, 20.0])
    volatile = coef_of_variation([5.0, 35.0, 2.0, 38.0])
    assert stable is not None and volatile is not None
    assert stable < volatile
