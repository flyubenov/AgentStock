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
        metrics={k: 1.23 for k in _METRIC_COLS},
        score_breakdown={"fundamentals_composite": 4.3, "final": 6.2,
                         "pre_profit": {"applied": True, "rule_of_40": 67.9,
                                        "runway_months": 30.6, "growth_score": 9.0,
                                        "blend_weight": 0.4, "capped": False}},
        status="completed",
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
    # the score breakdown (JSON column) survives the round trip
    assert r.score_breakdown["final"] == 6.2
    assert r.score_breakdown["pre_profit"]["rule_of_40"] == 67.9


def test_row_to_result_tolerates_missing_breakdown_column():
    # a legacy row written before the Score Breakdown column existed
    legacy = _result_to_row(_res())[:-1]   # drop the JSON column
    r = _row_to_result(legacy)
    assert r.ticker == "AAPL"
    assert r.score_breakdown == {}


def test_database_qscore_col_constant():
    from services.screener_sheets import DATABASE_QSCORE_COL
    assert DATABASE_QSCORE_COL == "Q"


def test_headers_have_quality_score_first_metric_block():
    from services.screener_sheets import _SCREENER_HEADERS
    assert _SCREENER_HEADERS[3] == "Quality Score"
    assert "Section I" in _SCREENER_HEADERS and "Section Iv".title() not in _SCREENER_HEADERS


def _fake_service(get_error):
    """Fake Sheets service where the data-range read raises `get_error`. Metadata
    reports NO Screener tab, so the missing-tab (parse-error) branch takes the
    create path rather than a second failing read."""
    svc = MagicMock()
    # spreadsheets().get(...).execute() -> metadata with no Screener tab yet
    svc.spreadsheets.return_value.get.return_value.execute.return_value = {"sheets": []}
    # spreadsheets().values().get(...).execute() -> raises
    svc.spreadsheets.return_value.values.return_value.get.return_value.execute.side_effect = get_error
    return svc


def test_ensure_screener_sheet_repairs_missing_header_row():
    """A pre-existing Screener tab with data in row 1 but no header row gets a
    header row inserted above the data (not overwriting it)."""
    from services.screener_sheets import _ensure_screener_sheet, _SCREENER_HEADERS

    svc = MagicMock()
    svc.spreadsheets.return_value.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Screener", "sheetId": 42}}]
    }
    # row 1 currently holds a data row (ticker in A1), not the header
    svc.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": [["NBIS", "Nebius", "..."]]
    }
    _ensure_screener_sheet(svc, "sid")

    # a blank row was inserted at the top of the Screener tab (sheetId 42, rows 0..1)
    batch_calls = svc.spreadsheets.return_value.batchUpdate.call_args_list
    assert any(
        req.get("insertDimension", {}).get("range", {}).get("sheetId") == 42
        for call in batch_calls
        for req in call.kwargs.get("body", {}).get("requests", [])
    ), "expected an insertDimension inserting a header row"
    # the header row was written to A1
    update_calls = svc.spreadsheets.return_value.values.return_value.update.call_args_list
    assert any(
        call.kwargs.get("body", {}).get("values") == [_SCREENER_HEADERS]
        for call in update_calls
    ), "expected the header row to be written to A1"


def test_ensure_screener_sheet_refreshes_outdated_headers():
    """A header row from an older, shorter schema is refreshed in place (no insert)."""
    from services.screener_sheets import _ensure_screener_sheet, _SCREENER_HEADERS

    svc = MagicMock()
    svc.spreadsheets.return_value.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Screener", "sheetId": 42}}]
    }
    svc.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": [_SCREENER_HEADERS[:-1]]   # missing the newest "Score Breakdown" column
    }
    _ensure_screener_sheet(svc, "sid")
    svc.spreadsheets.return_value.batchUpdate.assert_not_called()   # no row inserted
    update_calls = svc.spreadsheets.return_value.values.return_value.update.call_args_list
    assert any(
        call.kwargs.get("body", {}).get("values") == [_SCREENER_HEADERS]
        for call in update_calls
    ), "expected the outdated header row to be refreshed in place"


def test_ensure_screener_sheet_noop_when_headers_present():
    """When row 1 already is the header row, no insert and no header rewrite."""
    from services.screener_sheets import _ensure_screener_sheet, _SCREENER_HEADERS

    svc = MagicMock()
    svc.spreadsheets.return_value.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": "Screener", "sheetId": 42}}]
    }
    svc.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": [_SCREENER_HEADERS]
    }
    _ensure_screener_sheet(svc, "sid")
    svc.spreadsheets.return_value.batchUpdate.assert_not_called()
    svc.spreadsheets.return_value.values.return_value.update.assert_not_called()


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
