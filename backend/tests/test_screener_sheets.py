from screener.models import ScreenerResult
from services.screener_sheets import (
    _result_to_row, _row_to_result, _SCREENER_HEADERS, _METRIC_COLS,
)


def _res():
    return ScreenerResult(
        ticker="AAPL", company_name="Apple", last_evaluated="2026-07-08T00:00:00",
        quality_score=8.4, sector="Technology", sector_profile="TECH_GROWTH",
        section_scores={"I": 8.1, "II": 9.0, "III": 7.5, "IV": 8.0},
        metrics={k: 1.23 for k in _METRIC_COLS}, status="completed",
    )


def test_row_length_matches_headers():
    row = _result_to_row(_res())
    assert len(row) == len(_SCREENER_HEADERS)
    assert row[0] == "AAPL"
    assert row[3] == 8.4                     # Quality Score
    assert row[4] == "Technology"
    assert row[5] == "TECH_GROWTH"


def test_round_trip_preserves_core_fields():
    r = _row_to_result(_result_to_row(_res()))
    assert r.ticker == "AAPL"
    assert r.quality_score == 8.4
    assert r.sector_profile == "TECH_GROWTH"
    assert r.section_scores["II"] == 9.0
    assert r.metrics[_METRIC_COLS[0]] == 1.23
