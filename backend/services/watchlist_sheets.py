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


def _read_sync() -> list[Watchlist]:
    svc = _get_service()
    sheet_id = _sheet_id()
    try:
        result = _execute(svc.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=f"{_WATCHLIST_TAB}!A:C"))
    except Exception as e:
        if "Unable to parse range" in str(e):
            _ensure_watchlist_sheet(svc, sheet_id)
            return []
        raise
    rows = result.get("values", [])
    return [_row_to_watchlist(r) for r in rows[1:]] if len(rows) >= 2 else []


async def read_watchlists() -> list[Watchlist]:
    return await _run_sheets(_read_sync)


def _save_sync(name: str, filter_obj: dict) -> Watchlist:
    svc = _get_service()
    sheet_id = _sheet_id()
    _ensure_watchlist_sheet(svc, sheet_id)
    rows = _execute(svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{_WATCHLIST_TAB}!A:C")).get("values", [])
    target = None                       # 1-based sheet row to overwrite
    created = datetime.now(timezone.utc).isoformat()
    for i, row in enumerate(rows[1:], start=2):     # row 1 is the header
        if row and row[0].strip().lower() == name.strip().lower():
            target = i
            if len(row) >= 3 and row[2]:
                created = row[2]                    # preserve original Created
            break
    w = Watchlist(name=name, filter=filter_obj, created=created)
    new_row = _watchlist_to_row(w)
    if target is None:
        _execute(svc.spreadsheets().values().append(
            spreadsheetId=sheet_id, range=f"{_WATCHLIST_TAB}!A:A",
            valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": [new_row]}))
    else:
        _execute(svc.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=f"{_WATCHLIST_TAB}!A{target}",
            valueInputOption="RAW", body={"values": [new_row]}))
    return w


async def save_watchlist(name: str, filter_obj: dict) -> Watchlist:
    return await _run_sheets(_save_sync, name, filter_obj)


def _delete_sync(name: str) -> bool:
    svc = _get_service()
    sheet_id = _sheet_id()
    gid = _tab_gid(svc, sheet_id, _WATCHLIST_TAB)
    if gid is None:
        return False
    rows = _execute(svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{_WATCHLIST_TAB}!A:A")).get("values", [])
    target = None                       # 0-based row index for deleteDimension
    for i, row in enumerate(rows):
        if row and row[0].strip().lower() == name.strip().lower():
            target = i
            break
    if target is None:
        return False
    _execute(svc.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": [{"deleteDimension": {"range": {
            "sheetId": gid, "dimension": "ROWS",
            "startIndex": target, "endIndex": target + 1}}}]}))
    return True


async def delete_watchlist(name: str) -> bool:
    return await _run_sheets(_delete_sync, name)
