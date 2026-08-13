import pytest
from datetime import date
from services.yahoo import (
    ev_ebitda_history_ewma, latest_statement_ebitda, statements_predate_split,
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


# -- ev_ebitda_history_ewma -----------------------------------------------------
# Rows are most-recent-first (rows[0] = latest year), matching the real
# _fetch_ev_ebitda_history_sync convention (yfinance's income_stmt columns are
# newest-first) and latest_statement_ebitda's own docstring.
def _row(px, sh, ebitda, nd):
    return {"avg_price": px, "shares": sh, "ebitda": ebitda, "net_debt": nd}


def test_ev_ebitda_history_ewma_favors_recent_years_over_a_flat_median():
    # STRL-shaped: a persistent multi-year RE-RATING (5.24x -> 6.23x -> 8.15x -> 14.54x,
    # oldest to newest). A flat median (7.19x) lags this trend badly -- see
    # [[strl-ev-ebitda-trend-lag]]. EWMA (decay=0.5, most-recent-first weighting)
    # should land well above the median, closer to the recent level, without fully
    # chasing the current spot multiple (23.4x).
    rows = [
        _row(238.77, 30.7e6, 505.377e6, -127.6e6),   # 2025 (latest) -> ~14.54x
        _row(127.76, 30.6e6, 451.943e6, -80e6),       # 2024          -> ~8.15x
        _row(57.67, 30.5e6, 277.338e6, -50e6),        # 2023          -> ~6.23x
        _row(26.35, 30.4e6, 212.821e6, -30e6),        # 2022          -> ~5.24x
    ]
    ewma = ev_ebitda_history_ewma(rows)
    import statistics
    mults = [(r["avg_price"] * r["shares"] + r["net_debt"]) / r["ebitda"] for r in rows]
    median = statistics.median(mults)
    assert ewma > median                     # corrects the understatement
    assert ewma == pytest.approx(11.1, abs=0.3)
    assert ewma < mults[0]                    # still doesn't fully chase the latest year


def test_ev_ebitda_history_ewma_corrects_a_stale_high_median_too():
    # CRM-shaped: a persistent multi-year DE-RATING (36.9x -> 27.4x -> 23.0x -> 14.8x,
    # oldest to newest) -- the mirror-image problem: a flat median (25.2x) OVERSTATES
    # the current level. EWMA must pull the representative multiple DOWN, not just up
    # -- proving the fix is a genuine two-sided statistical correction, not an
    # STRL-only patch.
    rows = [
        _row(14.8, 1, 1, 0),
        _row(23.0, 1, 1, 0),
        _row(27.4, 1, 1, 0),
        _row(36.9, 1, 1, 0),
    ]
    ewma = ev_ebitda_history_ewma(rows)
    import statistics
    median = statistics.median([14.8, 23.0, 27.4, 36.9])
    assert ewma < median
    assert ewma == pytest.approx(20.14, abs=0.05)


def test_ev_ebitda_history_ewma_equals_the_constant_for_a_flat_series():
    # Sanity/invariant: a non-trending (flat) series -> EWMA must equal that same
    # constant, same as a median would (no artificial bias introduced by weighting).
    rows = [_row(10.0, 1, 1, 0), _row(10.0, 1, 1, 0), _row(10.0, 1, 1, 0)]
    assert ev_ebitda_history_ewma(rows) == pytest.approx(10.0)


def test_ev_ebitda_history_ewma_skips_nonpositive_ebitda():
    rows = [
        _row(100.0, 1e9, 0, 0),       # zero EBITDA -> skipped
        _row(100.0, 1e9, -5e9, 0),    # negative EBITDA -> skipped
        _row(100.0, 1e9, 10e9, 0),    # valid: 10x
    ]
    # only one valid year < min_years -> None
    assert ev_ebitda_history_ewma(rows) is None


def test_ev_ebitda_history_ewma_none_when_too_few_years():
    rows = [_row(100.0, 1e9, 10e9, 0), _row(120.0, 1e9, 10e9, 0)]
    assert ev_ebitda_history_ewma(rows, min_years=3) is None


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
