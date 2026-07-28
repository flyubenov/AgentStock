from unittest.mock import MagicMock, patch

from services.sheets import _delete_ticker_row_sync


def _svc(tab_gid, col_a_rows):
    """Fake Sheets service: metadata exposes a tab (unless tab_gid is None) and the
    A:A read returns `col_a_rows`."""
    svc = MagicMock()
    sheets = [] if tab_gid is None else [{"properties": {"title": "Database", "sheetId": tab_gid}}]
    svc.spreadsheets.return_value.get.return_value.execute.return_value = {"sheets": sheets}
    svc.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": col_a_rows
    }
    return svc


def _delete_requests(svc):
    return [
        req["deleteDimension"]
        for call in svc.spreadsheets.return_value.batchUpdate.call_args_list
        for req in call.kwargs.get("body", {}).get("requests", [])
        if "deleteDimension" in req
    ]


def _run(svc, ticker="MSFT", tab="Database"):
    with patch("services.sheets._get_service", return_value=svc), \
         patch("services.sheets._sheet_id", return_value="sid"):
        return _delete_ticker_row_sync(tab, ticker)


def test_deletes_the_row_dimension_at_the_matching_index():
    # header + 3 data rows; MSFT sits on sheet row 3 -> 0-based index 2
    svc = _svc(7, [["Ticker"], ["AAPL"], ["MSFT"], ["NVDA"]])
    assert _run(svc) is True
    reqs = _delete_requests(svc)
    assert len(reqs) == 1
    assert reqs[0]["range"] == {
        "sheetId": 7, "dimension": "ROWS", "startIndex": 2, "endIndex": 3,
    }


def test_match_is_case_and_whitespace_insensitive():
    svc = _svc(7, [["Ticker"], [" msft "]])
    assert _run(svc) is True
    assert _delete_requests(svc)[0]["range"]["startIndex"] == 1


def test_absent_ticker_deletes_nothing():
    svc = _svc(7, [["Ticker"], ["AAPL"]])
    assert _run(svc) is False
    svc.spreadsheets.return_value.batchUpdate.assert_not_called()


def test_missing_tab_deletes_nothing():
    """A tab that was never created (e.g. no Screener yet) is a no-op, not an error."""
    svc = _svc(None, [["Ticker"], ["MSFT"]])
    assert _run(svc) is False
    svc.spreadsheets.return_value.batchUpdate.assert_not_called()


def test_first_data_row_deletes_itself_not_the_header():
    svc = _svc(7, [["Ticker"], ["AAPL"]])
    assert _run(svc, ticker="AAPL") is True
    assert _delete_requests(svc)[0]["range"]["startIndex"] == 1
