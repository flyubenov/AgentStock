import asyncio
import contextlib
from unittest.mock import MagicMock, patch

import pytest

from models import AnalyticsEvent
import services.events_sheets as events_sheets
from services.events_sheets import record_event, flush_events, _EVENTS_TAB


@pytest.fixture(autouse=True)
def _reset_queue():
    """The queue is module-level state shared across every test in the process —
    clear it before and after so tests can't leak events into each other."""
    events_sheets._queue.clear()
    events_sheets._oldest = None
    events_sheets._dropped = 0
    yield
    events_sheets._queue.clear()
    events_sheets._oldest = None
    events_sheets._dropped = 0


def _fake_service():
    """Fake Sheets service whose metadata already reports the Events tab, so
    _ensure_events_sheet is a no-op and only the append call is exercised."""
    svc = MagicMock()
    svc.spreadsheets.return_value.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": _EVENTS_TAB}}]
    }
    return svc


def _ev(n: int) -> AnalyticsEvent:
    return AnalyticsEvent(event=f"event-{n}", visitor_id=f"v-{n}")


@pytest.mark.asyncio
async def test_record_event_flushes_only_once_the_batch_threshold_is_reached(monkeypatch):
    monkeypatch.setattr(events_sheets, "_BATCH_SIZE", 3)
    svc = _fake_service()
    append = svc.spreadsheets.return_value.values.return_value.append

    with patch("services.events_sheets._get_service", return_value=svc), \
         patch("services.events_sheets._sheet_id", return_value="sid"):
        await record_event(_ev(1))
        await record_event(_ev(2))

        # Below the threshold: nothing appended yet, rows stay queued.
        append.assert_not_called()
        assert len(events_sheets._queue) == 2

        await record_event(_ev(3))  # hits the threshold -> auto-flush

    # At the threshold: exactly one append call with all 3 rows, queue drained.
    append.assert_called_once()
    written_rows = append.call_args.kwargs["body"]["values"]
    assert len(written_rows) == 3
    assert [row[1] for row in written_rows] == ["event-1", "event-2", "event-3"]
    assert events_sheets._queue == []


@pytest.mark.asyncio
async def test_flush_events_requeues_and_swallows_a_sink_failure(monkeypatch):
    # Large enough that record_event's own auto-flush never fires here — this
    # test drives flush_events() directly.
    monkeypatch.setattr(events_sheets, "_BATCH_SIZE", 100)
    svc = _fake_service()
    svc.spreadsheets.return_value.values.return_value.append.return_value.execute.side_effect = \
        RuntimeError("sheets down")

    with patch("services.events_sheets._get_service", return_value=svc), \
         patch("services.events_sheets._sheet_id", return_value="sid"):
        await record_event(_ev(1))
        await record_event(_ev(2))
        assert len(events_sheets._queue) == 2

        written = await flush_events()  # the append raises inside _run_sheets

    assert written == 0                        # failure is swallowed, not raised
    assert len(events_sheets._queue) == 2       # rows are back in the queue

    # The next successful flush writes the rows that were put back.
    svc.spreadsheets.return_value.values.return_value.append.return_value.execute.side_effect = None
    svc.spreadsheets.return_value.values.return_value.append.return_value.execute.return_value = {}
    with patch("services.events_sheets._get_service", return_value=svc), \
         patch("services.events_sheets._sheet_id", return_value="sid"):
        written_after_recovery = await flush_events()

    assert written_after_recovery == 2
    assert events_sheets._queue == []


class _Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.mark.asyncio
async def test_a_small_batch_is_written_once_its_oldest_row_is_old_enough(monkeypatch):
    # The smoke test's real traffic: a handful of events, never a full batch. Before,
    # they waited in memory for a tenth event that might never come.
    clock = _Clock()
    monkeypatch.setattr(events_sheets, "_now", clock)
    monkeypatch.setattr(events_sheets, "_BATCH_SIZE", 10)
    monkeypatch.setattr(events_sheets, "_MAX_AGE_SECONDS", 30)
    svc = _fake_service()
    with patch.object(events_sheets, "_get_service", return_value=svc),          patch.object(events_sheets, "_sheet_id", return_value="sid"):
        await record_event(_ev(1))
        clock.t += 29
        await record_event(_ev(2))
        assert len(events_sheets._queue) == 2          # not yet old enough
        clock.t += 1
        await record_event(_ev(3))                     # the oldest is now 30s old
    assert events_sheets._queue == []
    rows = svc.spreadsheets.return_value.values.return_value.append.call_args.kwargs["body"]["values"]
    assert [r[1] for r in rows] == ["event-1", "event-2", "event-3"]


@pytest.mark.asyncio
async def test_the_age_clock_starts_at_the_first_row_after_a_flush(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(events_sheets, "_now", clock)
    monkeypatch.setattr(events_sheets, "_BATCH_SIZE", 2)
    monkeypatch.setattr(events_sheets, "_MAX_AGE_SECONDS", 30)
    with patch.object(events_sheets, "_get_service", return_value=_fake_service()),          patch.object(events_sheets, "_sheet_id", return_value="sid"):
        await record_event(_ev(1))
        await record_event(_ev(2))                     # batch-size flush
        assert events_sheets._queue == []
        clock.t += 100                                 # long idle gap
        await record_event(_ev(3))                     # a fresh row, not an old one
    assert len(events_sheets._queue) == 1


@pytest.mark.asyncio
async def test_the_periodic_loop_writes_what_is_queued(monkeypatch):
    monkeypatch.setattr(events_sheets, "_BATCH_SIZE", 100)
    svc = _fake_service()
    with patch.object(events_sheets, "_get_service", return_value=svc),          patch.object(events_sheets, "_sheet_id", return_value="sid"):
        await record_event(_ev(1))
        task = asyncio.create_task(events_sheets.flush_loop(0.01))
        for _ in range(100):
            if not events_sheets._queue:
                break
            await asyncio.sleep(0.01)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    assert events_sheets._queue == []


@pytest.mark.asyncio
async def test_the_periodic_loop_survives_a_failing_sink(monkeypatch):
    monkeypatch.setattr(events_sheets, "_BATCH_SIZE", 100)
    await record_event(_ev(1))
    with patch.object(events_sheets, "_get_service", side_effect=RuntimeError("down")):
        task = asyncio.create_task(events_sheets.flush_loop(0.01))
        await asyncio.sleep(0.08)                      # several failing ticks
        assert not task.done()                         # still running
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    assert len(events_sheets._queue) == 1              # kept for a later flush


@pytest.mark.asyncio
async def test_the_queue_is_bounded_and_drops_the_oldest_first(monkeypatch):
    monkeypatch.setattr(events_sheets, "_BATCH_SIZE", 1000)
    monkeypatch.setattr(events_sheets, "_MAX_QUEUE", 3)
    for n in range(5):
        await record_event(_ev(n))
    assert [r[1] for r in events_sheets._queue] == ["event-2", "event-3", "event-4"]
    assert events_sheets.queue_stats() == {"queued": 3, "dropped": 2}


@pytest.mark.asyncio
async def test_a_failed_flush_requeues_within_the_bound(monkeypatch):
    monkeypatch.setattr(events_sheets, "_BATCH_SIZE", 1000)
    monkeypatch.setattr(events_sheets, "_MAX_QUEUE", 2)
    for n in range(2):
        await record_event(_ev(n))
    with patch.object(events_sheets, "_get_service", side_effect=RuntimeError("down")):
        assert await flush_events() == 0
    assert len(events_sheets._queue) == 2
    await record_event(_ev(9))
    assert [r[1] for r in events_sheets._queue] == ["event-1", "event-9"]


def test_shutdown_writes_whatever_is_still_queued(monkeypatch):
    # main.py's lifespan: the last flush runs as the app stops.
    from fastapi.testclient import TestClient
    import main
    monkeypatch.setattr(main, "seed", lambda tickers: asyncio.sleep(0))
    monkeypatch.setattr(events_sheets, "_BATCH_SIZE", 100)
    svc = _fake_service()
    with patch.object(events_sheets, "_get_service", return_value=svc),          patch.object(events_sheets, "_sheet_id", return_value="sid"):
        with TestClient(main.app) as client:
            client.post("/api/events", json={"event": "payment_button_clicked",
                                             "visitor_id": "v-1", "props": {"plan": "Pro"}})
            assert len(events_sheets._queue) == 1
        # leaving the block runs the lifespan shutdown
    assert events_sheets._queue == []
    rows = svc.spreadsheets.return_value.values.return_value.append.call_args.kwargs["body"]["values"]
    assert rows[0][1] == "payment_button_clicked"


# --- Spec §9 (2026-09-29): a dedicated Intrinsica events spreadsheet ---
def test_events_go_to_the_intrinsica_sheet_never_the_agent_stock_one(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_ID", "agent-stock")
    monkeypatch.setenv("INTRINSICA_EVENTS_SHEET_ID", "intrinsica-events")
    assert events_sheets._sheet_id() == "intrinsica-events"


def test_an_unset_events_sheet_never_falls_back_to_agent_stock(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_ID", "agent-stock")
    monkeypatch.delenv("INTRINSICA_EVENTS_SHEET_ID", raising=False)
    with pytest.raises(RuntimeError, match="INTRINSICA_EVENTS_SHEET_ID"):
        events_sheets._sheet_id()


@pytest.mark.asyncio
async def test_with_no_events_sheet_events_stay_queued_and_nothing_is_written(monkeypatch):
    monkeypatch.setenv("GOOGLE_SHEETS_ID", "agent-stock")
    monkeypatch.delenv("INTRINSICA_EVENTS_SHEET_ID", raising=False)
    svc = _fake_service()
    append = svc.spreadsheets.return_value.values.return_value.append
    with patch.object(events_sheets, "_get_service", return_value=svc):
        events_sheets._queue.append(["2026-09-29T00:00:00Z", "page_view", "v1", "{}"])
        written = await flush_events()
    assert written == 0
    assert len(events_sheets._queue) == 1          # kept for a later flush, bounded by _MAX_QUEUE
    append.assert_not_called()


@pytest.mark.asyncio
async def test_a_write_that_completes_after_cancellation_is_not_written_twice(monkeypatch):
    """Cancelling the flush does not stop the Sheets write already running in its
    executor thread. If that write succeeds, the shutdown flush must not send the
    same rows again: a duplicated payment click inflates the metric the page is for."""
    import threading
    monkeypatch.setattr(events_sheets, "_BATCH_SIZE", 100)
    await record_event(_ev(1))
    writes: list[list[list[str]]] = []
    started, release = threading.Event(), threading.Event()

    def slow_append(rows):                             # runs in the real executor thread
        started.set()
        release.wait(5)
        writes.append(rows)

    monkeypatch.setattr(events_sheets, "_append_sync", slow_append)
    task = asyncio.create_task(flush_events())
    await asyncio.to_thread(started.wait, 5)
    task.cancel()
    release.set()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    await flush_events()                               # the lifespan's final flush
    assert [[r[1] for r in rows] for rows in writes] == [["event-1"]]
    assert events_sheets._queue == []


@pytest.mark.asyncio
async def test_a_write_that_fails_after_cancellation_is_requeued(monkeypatch):
    import threading
    monkeypatch.setattr(events_sheets, "_BATCH_SIZE", 100)
    await record_event(_ev(1))
    started, release = threading.Event(), threading.Event()

    def failing_append(rows):
        started.set()
        release.wait(5)
        raise RuntimeError("down")

    monkeypatch.setattr(events_sheets, "_append_sync", failing_append)
    task = asyncio.create_task(flush_events())
    await asyncio.to_thread(started.wait, 5)
    task.cancel()
    release.set()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    assert [r[1] for r in events_sheets._queue] == ["event-1"]
