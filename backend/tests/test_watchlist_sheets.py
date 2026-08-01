from unittest.mock import MagicMock

from models import Watchlist
from services.watchlist_sheets import (
    _watchlist_to_row, _row_to_watchlist, _ensure_watchlist_sheet,
    _WATCHLIST_HEADERS, _WATCHLIST_TAB,
)


def _wl():
    return Watchlist(
        name="Cheap quality",
        filter={"tickers": ["NVDA", "AMD"], "stockTypes": [],
                "quality": {"min": 8, "max": None},
                "gap": {"min": None, "max": -20}},
        created="2026-08-01T12:00:00Z",
    )


def test_row_length_and_json_column():
    row = _watchlist_to_row(_wl())
    assert len(row) == len(_WATCHLIST_HEADERS)
    assert row[0] == "Cheap quality"
    assert row[2] == "2026-08-01T12:00:00Z"
    # column B is JSON text, not a dict
    assert isinstance(row[1], str) and '"tickers"' in row[1]


def test_round_trip_preserves_filter():
    r = _row_to_watchlist(_watchlist_to_row(_wl()))
    assert r.name == "Cheap quality"
    assert r.filter["quality"] == {"min": 8, "max": None}
    assert r.filter["tickers"] == ["NVDA", "AMD"]
    assert r.created == "2026-08-01T12:00:00Z"


def test_row_to_watchlist_tolerates_short_and_garbage_rows():
    # a row missing the Created column
    r = _row_to_watchlist(["Momentum", '{"tickers":["MSFT"]}'])
    assert r.name == "Momentum" and r.created == ""
    assert r.filter["tickers"] == ["MSFT"]
    # a row whose JSON is malformed -> empty filter, still loads
    r2 = _row_to_watchlist(["Broken", "{not json", ""])
    assert r2.name == "Broken" and r2.filter == {}


def test_ensure_watchlist_sheet_creates_tab_and_header():
    svc = MagicMock()
    svc.spreadsheets.return_value.get.return_value.execute.return_value = {"sheets": []}
    _ensure_watchlist_sheet(svc, "sid")
    # tab added
    batch_calls = svc.spreadsheets.return_value.batchUpdate.call_args_list
    assert any(
        req.get("addSheet", {}).get("properties", {}).get("title") == _WATCHLIST_TAB
        for call in batch_calls
        for req in call.kwargs.get("body", {}).get("requests", [])
    )
    # header row written to A1
    update_calls = svc.spreadsheets.return_value.values.return_value.update.call_args_list
    assert any(
        call.kwargs.get("body", {}).get("values") == [_WATCHLIST_HEADERS]
        for call in update_calls
    )


def test_ensure_watchlist_sheet_noop_when_header_present():
    svc = MagicMock()
    svc.spreadsheets.return_value.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": _WATCHLIST_TAB, "sheetId": 7}}]
    }
    svc.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": [_WATCHLIST_HEADERS]
    }
    _ensure_watchlist_sheet(svc, "sid")
    svc.spreadsheets.return_value.batchUpdate.assert_not_called()
    svc.spreadsheets.return_value.values.return_value.update.assert_not_called()
