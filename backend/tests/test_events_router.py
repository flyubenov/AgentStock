from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from main import app
import services.events_sheets as events_sheets

client = TestClient(app)


def test_event_is_recorded():
    with patch("routers.events.record_event", new=AsyncMock()) as rec:
        resp = client.post("/api/events", json={
            "event": "payment_button_clicked",
            "visitor_id": "v-123",
            "props": {"plan": "Pro", "billing": "annual"},
        })
    assert resp.status_code == 200
    assert resp.json() == {"recorded": True}
    assert rec.await_count == 1
    assert rec.await_args.args[0].event == "payment_button_clicked"


def test_event_gets_a_timestamp_when_the_client_omits_one():
    with patch("routers.events.record_event", new=AsyncMock()) as rec:
        client.post("/api/events", json={"event": "page_view", "visitor_id": "v-1"})
    assert rec.await_args.args[0].ts


def test_recorded_false_when_record_event_itself_raises():
    """Covers the router's own exception boundary: if record_event() raises
    directly (e.g. a json.dumps failure on bad props, not a Sheets outage —
    that path no longer raises, see below), the request still returns 200."""
    with patch("routers.events.record_event",
               new=AsyncMock(side_effect=RuntimeError("boom"))):
        resp = client.post("/api/events", json={"event": "page_view", "visitor_id": "v-1"})
    assert resp.status_code == 200
    assert resp.json() == {"recorded": False}


def test_an_unnamed_event_is_rejected():
    resp = client.post("/api/events", json={"event": "  ", "visitor_id": "v-1"})
    assert resp.json() == {"recorded": False, "error": "event name is required"}


def test_recorded_true_survives_a_real_sink_outage_during_auto_flush():
    """A genuine Sheets outage that fires during the request's own auto-flush
    (queue hits _BATCH_SIZE mid-request) does NOT surface as recorded=False:
    flush_events() swallows the failure and requeues, so record_event() returns
    normally and the router answers recorded=True. That True describes
    "accepted and queued", not "written to Sheets" — the assertion that
    actually matters is that the row is not lost, so the queue is checked
    directly rather than trusting the response body."""
    events_sheets._queue.clear()
    try:
        with patch.object(events_sheets, "_BATCH_SIZE", 1):
            svc = MagicMock()
            svc.spreadsheets.return_value.get.return_value.execute.return_value = {
                "sheets": [{"properties": {"title": events_sheets._EVENTS_TAB}}]
            }
            append = svc.spreadsheets.return_value.values.return_value.append
            append.return_value.execute.side_effect = RuntimeError("sheets down")

            with patch("services.events_sheets._get_service", return_value=svc), \
                 patch("services.events_sheets._sheet_id", return_value="sid"):
                resp = client.post("/api/events",
                                    json={"event": "page_view", "visitor_id": "v-1"})

        assert resp.status_code == 200
        assert resp.json() == {"recorded": True}
        append.assert_called_once()             # the write to Sheets was actually attempted
        assert len(events_sheets._queue) == 1    # ...and the row survives the outage
    finally:
        events_sheets._queue.clear()
