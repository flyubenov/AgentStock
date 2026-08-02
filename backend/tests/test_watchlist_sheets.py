from unittest.mock import MagicMock, patch

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


def _fake_service_with_rows(rows):
    """Fake Sheets service: metadata reports the Watchlists tab (gid 7); the A:C
    (and A:A) value reads return `rows` including the header row."""
    svc = MagicMock()
    svc.spreadsheets.return_value.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": _WATCHLIST_TAB, "sheetId": 7}}]
    }
    svc.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": rows
    }
    return svc


def test_read_sync_skips_header_and_parses_rows():
    from services.watchlist_sheets import _read_sync
    rows = [_WATCHLIST_HEADERS,
            ["Cheap quality", '{"quality":{"min":8,"max":null}}', "2026-08-01T00:00:00Z"]]
    svc = _fake_service_with_rows(rows)
    with patch("services.watchlist_sheets._get_service", return_value=svc), \
         patch("services.watchlist_sheets._sheet_id", return_value="sid"):
        out = _read_sync()
    assert len(out) == 1
    assert out[0].name == "Cheap quality"
    assert out[0].filter["quality"] == {"min": 8, "max": None}


def test_read_sync_swallows_missing_tab_only():
    from services.watchlist_sheets import _read_sync
    svc = MagicMock()
    svc.spreadsheets.return_value.get.return_value.execute.return_value = {"sheets": []}
    svc.spreadsheets.return_value.values.return_value.get.return_value.execute.side_effect = \
        Exception("Unable to parse range: Watchlists!A:C")
    with patch("services.watchlist_sheets._get_service", return_value=svc), \
         patch("services.watchlist_sheets._sheet_id", return_value="sid"):
        assert _read_sync() == []


def test_save_sync_appends_new_row():
    from services.watchlist_sheets import _save_sync
    svc = _fake_service_with_rows([_WATCHLIST_HEADERS])   # no data rows yet
    with patch("services.watchlist_sheets._get_service", return_value=svc), \
         patch("services.watchlist_sheets._sheet_id", return_value="sid"):
        w = _save_sync("New list", {"tickers": ["MSFT"]})
    assert w.name == "New list" and w.created  # created stamped
    svc.spreadsheets.return_value.values.return_value.append.assert_called_once()
    svc.spreadsheets.return_value.values.return_value.update.assert_not_called()


def test_save_sync_overwrites_and_preserves_created():
    from services.watchlist_sheets import _save_sync
    rows = [_WATCHLIST_HEADERS,
            ["Cheap quality", '{"quality":{"min":7}}', "2026-07-01T00:00:00Z"]]
    svc = _fake_service_with_rows(rows)
    with patch("services.watchlist_sheets._get_service", return_value=svc), \
         patch("services.watchlist_sheets._sheet_id", return_value="sid"):
        w = _save_sync("cheap QUALITY", {"quality": {"min": 9}})  # case-insensitive match
    assert w.created == "2026-07-01T00:00:00Z"                    # original created kept
    # updated in place at row 2 (A2), not appended
    upd = svc.spreadsheets.return_value.values.return_value.update
    assert upd.call_args.kwargs["range"] == "Watchlists!A2"
    svc.spreadsheets.return_value.values.return_value.append.assert_not_called()


def test_delete_sync_removes_matching_row():
    from services.watchlist_sheets import _delete_sync
    rows = [_WATCHLIST_HEADERS, ["Keep", "{}", ""], ["Drop", "{}", ""]]
    svc = _fake_service_with_rows(rows)
    with patch("services.watchlist_sheets._get_service", return_value=svc), \
         patch("services.watchlist_sheets._sheet_id", return_value="sid"):
        assert _delete_sync("drop") is True     # case-insensitive
    # deleted row index 2 (0-based) via deleteDimension on gid 7
    batch = svc.spreadsheets.return_value.batchUpdate.call_args
    rng = batch.kwargs["body"]["requests"][0]["deleteDimension"]["range"]
    assert rng == {"sheetId": 7, "dimension": "ROWS", "startIndex": 2, "endIndex": 3}


def test_delete_sync_returns_false_when_absent():
    from services.watchlist_sheets import _delete_sync
    svc = _fake_service_with_rows([_WATCHLIST_HEADERS, ["Keep", "{}", ""]])
    with patch("services.watchlist_sheets._get_service", return_value=svc), \
         patch("services.watchlist_sheets._sheet_id", return_value="sid"):
        assert _delete_sync("nope") is False
    svc.spreadsheets.return_value.batchUpdate.assert_not_called()
