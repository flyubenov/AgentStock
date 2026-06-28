import pytest
from services.yahoo import (
    quarterly_eps_sum, eps_unreliable, ev_ebitda_history_median, shares_corrupted,
)


# -- shares_corrupted ----------------------------------------------------------
def test_shares_corrupted_flags_tenfold_inflation():
    # KLAC: info sharesOutstanding 1.306e9 vs statement diluted 1.362e8 -> ~9.6x
    assert shares_corrupted(1.306e9, 1.362e8) is True


def test_shares_corrupted_passes_when_consistent():
    # AMAT: 7.94e8 vs 8.08e8 -> 0.98x; and a buyback-driven small gap stays OK
    assert shares_corrupted(7.94e8, 8.08e8) is False


def test_shares_corrupted_allows_dual_class_gap():
    # dual-class (sharesOutstanding = one class) can be ~2x off -> must NOT trigger
    assert shares_corrupted(6.0e9, 3.0e9) is False


def test_shares_corrupted_false_when_missing():
    assert shares_corrupted(None, 1.0e8) is False
    assert shares_corrupted(1.0e9, None) is False
    assert shares_corrupted(0, 1.0e8) is False


# -- quarterly_eps_sum ---------------------------------------------------------
def test_quarterly_eps_sum_sums_last_four():
    # newest-first list of quarterly diluted EPS
    assert quarterly_eps_sum([9.12, 8.68, 8.47, 9.06, 8.16]) == pytest.approx(35.33)


def test_quarterly_eps_sum_skips_none_leading():
    # a NaN-derived None at the head is skipped; next four valid quarters sum
    assert quarterly_eps_sum([None, 9.12, 8.68, 8.47, 9.06]) == pytest.approx(35.33)


def test_quarterly_eps_sum_none_when_under_four_valid():
    assert quarterly_eps_sum([9.12, 8.68, None]) is None
    assert quarterly_eps_sum([]) is None


# -- eps_unreliable ------------------------------------------------------------
def test_eps_unreliable_flags_tenfold_gap():
    # KLAC: trailing 3.53 vs quarterly sum 35.33 -> ~90% divergence
    assert eps_unreliable(3.53, 35.33) is True


def test_eps_unreliable_passes_when_consistent():
    # AMAT: trailing 10.66 vs quarterly sum 10.65 -> consistent
    assert eps_unreliable(10.66, 10.65) is False


def test_eps_unreliable_false_when_unjudgeable():
    assert eps_unreliable(None, 35.0) is False
    assert eps_unreliable(10.0, None) is False
    assert eps_unreliable(10.0, 0) is False


# -- ev_ebitda_history_median --------------------------------------------------
def _row(px, sh, ebitda, nd):
    return {"avg_price": px, "shares": sh, "ebitda": ebitda, "net_debt": nd}


def test_ev_ebitda_history_median_computes_median():
    # AMAT-like: 11.0, 12.9, 17.7, 14.7 -> median 13.8 (approx)
    rows = [
        _row(104.60, 0.84e9, 8.27e9, 3.25e9),
        _row(132.37, 0.83e9, 8.47e9, -0.87e9),
        _row(192.72, 0.82e9, 8.79e9, -2.86e9),
        _row(187.14, 0.79e9, 9.97e9, -1.52e9),
    ]
    assert ev_ebitda_history_median(rows) == pytest.approx(13.8, abs=0.3)


def test_ev_ebitda_history_median_skips_nonpositive_ebitda():
    rows = [
        _row(100.0, 1e9, 0, 0),       # zero EBITDA -> skipped
        _row(100.0, 1e9, -5e9, 0),    # negative EBITDA -> skipped
        _row(100.0, 1e9, 10e9, 0),    # valid: 10x
    ]
    # only one valid year < min_years -> None
    assert ev_ebitda_history_median(rows) is None


def test_ev_ebitda_history_median_none_when_too_few_years():
    rows = [_row(100.0, 1e9, 10e9, 0), _row(120.0, 1e9, 10e9, 0)]
    assert ev_ebitda_history_median(rows, min_years=3) is None
