from __future__ import annotations
import json
from datetime import datetime, timezone

from models import Watchlist
from services.sheets import (
    _get_service, _sheet_id, _execute, _run_sheets, _tab_gid,
)

_WATCHLIST_TAB = "Watchlists"
_WATCHLIST_HEADERS = ["Name", "Filter", "Created"]


def _watchlist_to_row(w: Watchlist) -> list:
    return [w.name, json.dumps(w.filter or {}), w.created or ""]


def _parse_filter(v) -> dict:
    if not v:
        return {}
    try:
        parsed = json.loads(v)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _row_to_watchlist(row: list) -> Watchlist:
    row = list(row) + [""] * (len(_WATCHLIST_HEADERS) - len(row))
    return Watchlist(name=row[0], filter=_parse_filter(row[1]), created=row[2] or "")


def _ensure_watchlist_sheet(svc, sheet_id: str) -> None:
    """Create the 'Watchlists' tab + header row if missing; repair a tab whose row 1
    is data rather than the header (mirrors _ensure_screener_sheet, minus the
    outdated-schema refresh — these three headers never change)."""
    meta = _execute(svc.spreadsheets().get(spreadsheetId=sheet_id))
    props = {s["properties"]["title"]: s["properties"] for s in meta.get("sheets", [])}
    if _WATCHLIST_TAB not in props:
        _execute(svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": _WATCHLIST_TAB}}}]},
        ))
        _execute(svc.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=f"{_WATCHLIST_TAB}!A1",
            valueInputOption="RAW", body={"values": [_WATCHLIST_HEADERS]},
        ))
        return
    first = _execute(svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{_WATCHLIST_TAB}!1:1")).get("values", [])
    row1 = first[0] if first else []
    if row1 and row1[0] == _WATCHLIST_HEADERS[0]:
        return
    if row1:
        _execute(svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"insertDimension": {
                "range": {"sheetId": props[_WATCHLIST_TAB]["sheetId"],
                          "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
                "inheritFromBefore": False}}]},
        ))
    _execute(svc.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=f"{_WATCHLIST_TAB}!A1",
        valueInputOption="RAW", body={"values": [_WATCHLIST_HEADERS]},
    ))
