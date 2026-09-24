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
    yield
    events_sheets._queue.clear()


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
