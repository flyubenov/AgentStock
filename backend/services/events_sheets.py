from __future__ import annotations
import asyncio, json, os

from models import AnalyticsEvent
from services.sheets import _get_service, _sheet_id, _execute, _run_sheets

_EVENTS_TAB = "Events"
_EVENTS_HEADERS = ["Timestamp", "Event", "VisitorId", "Props"]

# Sheets rate-limits writes, so events are queued and appended in batches rather
# than one API call per click. The queue is flushed when it reaches the batch size
# or when flush_events() is called explicitly.
_BATCH_SIZE = int(os.getenv("EVENTS_BATCH_SIZE", "10"))
_queue: list[list[str]] = []
_lock = asyncio.Lock()


def _to_row(ev: AnalyticsEvent) -> list[str]:
    return [ev.ts or "", ev.event, ev.visitor_id, json.dumps(ev.props or {})]


def _ensure_events_sheet(svc, sheet_id: str) -> None:
    meta = _execute(svc.spreadsheets().get(spreadsheetId=sheet_id))
    titles = {s["properties"]["title"] for s in meta.get("sheets", [])}
    if _EVENTS_TAB in titles:
        return
    _execute(svc.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": _EVENTS_TAB}}}]},
    ))
    _execute(svc.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=f"{_EVENTS_TAB}!A1",
        valueInputOption="RAW", body={"values": [_EVENTS_HEADERS]},
    ))


def _append_sync(rows: list[list[str]]) -> None:
    svc = _get_service()
    sheet_id = _sheet_id()
    _ensure_events_sheet(svc, sheet_id)
    _execute(svc.spreadsheets().values().append(
        spreadsheetId=sheet_id, range=f"{_EVENTS_TAB}!A:D",
        valueInputOption="RAW", insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ))


async def record_event(ev: AnalyticsEvent) -> None:
    """Queue one event. Flushes automatically once a batch has accumulated."""
    async with _lock:
        _queue.append(_to_row(ev))
        ready = len(_queue) >= _BATCH_SIZE
    if ready:
        await flush_events()


async def flush_events() -> int:
    """Append everything queued. Returns the number of rows written."""
    async with _lock:
        rows, _queue[:] = list(_queue), []
    if not rows:
        return 0
    try:
        await _run_sheets(_append_sync, rows)
    except Exception:
        # Never lose the funnel to a Sheets outage — put them back for the next flush.
        async with _lock:
            _queue[:0] = rows
        raise
    return len(rows)
