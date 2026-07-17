import pytest
from datetime import date
from services.yahoo import (
    ev_ebitda_history_median, latest_statement_ebitda, statements_predate_split,
    _statement_revenue_yoy, _statement_op_income_yoy, _statement_net_income_yoy,
)


# -- statements_predate_split (split-aware skip) -------------------------------
def test_statements_predate_split_true_when_split_is_newer():
    # KLAC: latest statement ~2025-06-30, 10:1 split on 2026-06-12 -> stale per-share
    assert statements_predate_split(date(2025, 6, 30), [date(2026, 6, 12)]) is True


def test_statements_predate_split_false_for_old_splits():
    # AMAT: last split 2002 is far before the latest statement -> reconstruction ok
    assert statements_predate_split(date(2025, 10, 31), [date(2000, 1, 19), date(2002, 4, 17)]) is False


def test_statements_predate_split_false_when_unjudgeable():
    assert statements_predate_split(date(2025, 6, 30), []) is False
    assert statements_predate_split(None, [date(2026, 1, 1)]) is False


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


# -- latest_statement_ebitda (consistent projection base) ----------------------
def test_latest_statement_ebitda_takes_first_positive_row():
    # Rows are most-recent-first; the base must be the latest statement EBITDA so
    # it matches the definition the median multiple was built from.
    rows = [_row(110.0, 1e9, 30e9, 0), _row(68.0, 1e9, 26e9, 0), _row(40.0, 1e9, 21e9, 0)]
    assert latest_statement_ebitda(rows) == pytest.approx(30e9)


def test_latest_statement_ebitda_skips_leading_nonpositive():
    rows = [_row(110.0, 1e9, 0, 0), _row(68.0, 1e9, -5e9, 0), _row(40.0, 1e9, 21e9, 0)]
    assert latest_statement_ebitda(rows) == pytest.approx(21e9)


def test_latest_statement_ebitda_none_when_no_positive():
    rows = [_row(110.0, 1e9, 0, 0), _row(68.0, 1e9, -5e9, 0)]
    assert latest_statement_ebitda(rows) is None


# -- _statement_revenue_yoy (YoY growth from reconstruction rows) ---------------
def test_statement_revenue_yoy_latest_over_prior():
    # Rows most-recent-first: 501 vs 187 -> +167.9% (fraction 1.679).
    rows = [{"revenue": 501e6}, {"revenue": 187e6}, {"revenue": 75e6}]
    assert _statement_revenue_yoy(rows) == pytest.approx(501e6 / 187e6 - 1)


def test_statement_revenue_yoy_none_when_insufficient():
    assert _statement_revenue_yoy([{"revenue": 100.0}]) is None
    assert _statement_revenue_yoy([{"revenue": 100.0}, {"revenue": None}]) is None
    assert _statement_revenue_yoy([{"revenue": 100.0}, {"revenue": 0.0}]) is None


# -- _statement_op_income_yoy (operating-line growth from reconstruction rows) --
def test_statement_op_income_yoy_latest_over_prior():
    # BWXT FY25 vs FY24: operating income FELL 329.066M -> 324.576M (-1.4%) while
    # revenue grew +18.3% — the signal that its +20.7% earnings growth is non-operating.
    rows = [{"operating_income": 324.576e6}, {"operating_income": 329.066e6},
            {"operating_income": 333.286e6}]
    assert _statement_op_income_yoy(rows) == pytest.approx(324.576 / 329.066 - 1)


def test_statement_op_income_yoy_none_when_insufficient():
    assert _statement_op_income_yoy([{"operating_income": 100.0}]) is None
    assert _statement_op_income_yoy([{"operating_income": 100.0},
                                     {"operating_income": None}]) is None
    # A non-positive prior year makes the ratio meaningless (sign flip), not "growth".
    assert _statement_op_income_yoy([{"operating_income": 100.0},
                                     {"operating_income": 0.0}]) is None
    assert _statement_op_income_yoy([{"operating_income": 100.0},
                                     {"operating_income": -50.0}]) is None


# -- _statement_net_income_yoy (annual earnings reading, comparable to the op line) ----
def test_statement_net_income_yoy_latest_over_prior():
    # BWXT FY25 vs FY24: net income +16.7% (281.941M -> 328.945M) while operating income
    # fell — the pair the non-operating guard tests against each other.
    rows = [{"net_income": 328.945e6}, {"net_income": 281.941e6}]
    assert _statement_net_income_yoy(rows) == pytest.approx(328.945 / 281.941 - 1)


def test_statement_net_income_yoy_none_when_insufficient():
    assert _statement_net_income_yoy([{"net_income": 100.0}]) is None
    assert _statement_net_income_yoy([{"net_income": 100.0}, {"net_income": None}]) is None
    assert _statement_net_income_yoy([{"net_income": 100.0}, {"net_income": -50.0}]) is None
