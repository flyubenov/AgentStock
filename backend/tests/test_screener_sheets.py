from unittest.mock import MagicMock, patch

import pytest

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


def test_database_qscore_col_constant():
    from services.screener_sheets import DATABASE_QSCORE_COL
    assert DATABASE_QSCORE_COL == "Q"


def test_headers_have_quality_score_first_metric_block():
    from services.screener_sheets import _SCREENER_HEADERS
    assert _SCREENER_HEADERS[3] == "Quality Score"
    assert "Section I" in _SCREENER_HEADERS and "Section Iv".title() not in _SCREENER_HEADERS


def _fake_service(get_error):
    """Fake Sheets service: the Screener tab exists (so _ensure no-ops) but
    values().get(...).execute() raises `get_error`."""
    svc = MagicMock()
    # spreadsheets().get(...).execute() -> metadata with Screener tab present
    svc.spreadsheets.return_value.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Screener"}}]
    }
    # spreadsheets().values().get(...).execute() -> raises
    svc.spreadsheets.return_value.values.return_value.get.return_value.execute.side_effect = get_error
    return svc


def test_read_sync_only_swallows_missing_tab():
    from services.screener_sheets import _read_sync

    # Case 1: genuine missing-tab error -> swallowed, returns []
    missing = _fake_service(Exception("Unable to parse range: Screener!A:AN"))
    with patch("services.screener_sheets._get_service", return_value=missing), \
         patch("services.screener_sheets._sheet_id", return_value="sid"):
        assert _read_sync() == []

    # Case 2: generic error (no "Unable to parse range") -> re-raised
    denied = _fake_service(Exception("HttpError 403 permission denied"))
    with patch("services.screener_sheets._get_service", return_value=denied), \
         patch("services.screener_sheets._sheet_id", return_value="sid"):
        with pytest.raises(Exception, match="permission denied"):
            _read_sync()
