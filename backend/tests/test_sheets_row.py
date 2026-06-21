from models import TickerResult
from services.sheets import _result_to_row, _DB_HEADERS, _MODEL_COLS


def test_db_headers_length_matches_row():
    r = TickerResult(
        ticker="AAPL", company_name="Apple", last_evaluated="2026-06-21T00:00:00",
        stock_type="LARGE_CAP", fair_value=180.5, current_price=190.0,
        price_vs_fair_value_pct=-5.0,
        fair_value_breakdown={
            "dcf": {"weight": 0.5, "fair_value": 175.0, "scenarios": {}, "is_approx": False},
            "ev_ebitda": {"weight": 0.5, "fair_value": 186.0, "scenarios": {}, "is_approx": False},
        },
    )
    row = _result_to_row(r)
    assert len(row) == len(_DB_HEADERS) == 16
    assert row[0] == "AAPL"
    assert row[3] == "LARGE_CAP"
    # dcf is the first model column (index 7); ev_ebitda the second (index 8)
    assert row[7 + _MODEL_COLS.index("dcf")] == 175.0
    assert row[7 + _MODEL_COLS.index("ev_ebitda")] == 186.0
    # a model not in the breakdown is blank
    assert row[7 + _MODEL_COLS.index("nav")] == ""
