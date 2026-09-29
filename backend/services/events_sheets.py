from __future__ import annotations
import asyncio, json, logging, os, time

from models import AnalyticsEvent
from services.sheets import _get_service, _execute, _run_sheets

log = logging.getLogger(__name__)

_EVENTS_TAB = "Events"
_EVENTS_HEADERS = ["Timestamp", "Event", "VisitorId", "Props"]
_EVENTS_SHEET_ENV = "INTRINSICA_EVENTS_SHEET_ID"


def _sheet_id() -> str:
    """The dedicated Intrinsica events spreadsheet (spec §9, 2026-09-29). Never the
    Agent Stock spreadsheet (GOOGLE_SHEETS_ID): that is the analyst tool's own, and
    visitors' tickers and emails do not belong in it. Unset means no sink: the flush
    fails and flush_events keeps the rows queued (bounded by _MAX_QUEUE)."""
    sid = os.environ.get(_EVENTS_SHEET_ENV, "").strip()
    if not sid:
        raise RuntimeError(f"{_EVENTS_SHEET_ENV} is not set; funnel events are not being stored")
    return sid

# Sheets rate-limits writes, so events are queued and appended in batches rather
# than one API call per click. The queue is flushed when ANY of these happens:
#   - it reaches the batch size (record_event);
#   - the oldest queued row has waited longer than _MAX_AGE_SECONDS — checked on every
#     record_event, because on Cloud Run's request-based CPU a background timer may not
#     run between requests, but a request always has CPU;
#   - the periodic flush_loop ticks (started by main.py's lifespan);
#   - the app shuts down (main.py's lifespan awaits a final flush_events()).
# Before this, only the batch size triggered a write: at smoke-test traffic up to nine
# events — payment clicks among them — could sit in memory indefinitely and were lost
# whenever an idle instance was scaled to zero.
_BATCH_SIZE = int(os.getenv("EVENTS_BATCH_SIZE", "10"))
_MAX_AGE_SECONDS = float(os.getenv("EVENTS_MAX_AGE_SECONDS", "30"))
_FLUSH_INTERVAL_SECONDS = float(os.getenv("EVENTS_FLUSH_INTERVAL_SECONDS", "15"))
# A hard ceiling on memory: during a long Sheets outage the queue keeps every row for a
# later flush, but never more than this many. Beyond it the OLDEST rows are dropped —
# a bounded loss is better than an instance that runs out of memory and loses all of
# them — and the drop is counted in _dropped.
_MAX_QUEUE = int(os.getenv("EVENTS_MAX_QUEUE", "5000"))
_queue: list[list[str]] = []
_oldest: float | None = None       # time.monotonic() of the oldest queued row
_dropped = 0
_lock = asyncio.Lock()
_now = time.monotonic              # indirection so tests can move the clock
_warned = False                    # a failing sink is logged once per process, not per flush


def _trim_locked() -> None:
    """Drop the oldest rows beyond _MAX_QUEUE. Caller holds _lock."""
    global _dropped
    excess = len(_queue) - _MAX_QUEUE
    if excess > 0:
        del _queue[:excess]
        _dropped += excess


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
    """Queue one event. Flushes automatically once a batch has accumulated.

    Returning normally means the event was accepted and queued — not that it
    was confirmed written to Sheets. flush_events() swallows sink failures and
    requeues, so a queued row survives an outage and goes out on a later flush.
    """
    global _oldest
    async with _lock:
        _queue.append(_to_row(ev))
        _trim_locked()
        now = _now()
        if _oldest is None:
            _oldest = now
        ready = len(_queue) >= _BATCH_SIZE or (now - _oldest) >= _MAX_AGE_SECONDS
    if ready:
        await flush_events()


async def flush_events() -> int:
    """Append everything queued. Returns the number of rows written, or 0 if the
    sink is unavailable — the failure is swallowed, never propagated, so a dead
    Sheets backend can't turn into a broken request for whoever triggered the
    flush (e.g. record_event's own auto-flush)."""
    global _oldest, _warned
    async with _lock:
        rows, _queue[:] = list(_queue), []
        taken_oldest, _oldest = _oldest, None
    if not rows:
        return 0
    try:
        await _run_sheets(_append_sync, rows)
    except asyncio.CancelledError:
        # Shutdown cancels flush_loop, possibly mid-write. CancelledError is not an
        # Exception, so without this the rows already taken off the queue would be
        # lost with the task. Put them back synchronously (no await, so nothing can
        # interleave on the event loop), and let the cancellation proceed; the
        # lifespan's final flush_events() then writes them.
        _queue[:0] = rows
        _trim_locked()
        _oldest = _now() if _queue else None
        raise
    except Exception as exc:
        # Logged once per process: an unset INTRINSICA_EVENTS_SHEET_ID or an unshared
        # sheet must be visible in the logs, but not repeated on every retry.
        if not _warned:
            _warned = True
            log.warning("funnel events not written, kept queued for a later flush: %s", exc)
        # Never lose the funnel to a Sheets outage — put them back for the next flush,
        # still bounded by _MAX_QUEUE. The age clock restarts rather than resuming:
        # keeping the original age would make every following request retry a Sheets
        # outage immediately; the periodic loop still retries on its own interval.
        async with _lock:
            _queue[:0] = rows
            _trim_locked()
            _oldest = _now() if _queue else None
        return 0
    return len(rows)


async def flush_loop(interval: float | None = None) -> None:
    """Flush on a fixed interval until cancelled. Started from main.py's lifespan.
    flush_events() never raises, so one bad flush cannot end the loop."""
    period = _FLUSH_INTERVAL_SECONDS if interval is None else interval
    while True:
        await asyncio.sleep(period)
        await flush_events()


def queue_stats() -> dict:
    return {"queued": len(_queue), "dropped": _dropped}
