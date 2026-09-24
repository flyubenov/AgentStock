from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app

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


def test_a_sink_failure_never_fails_the_request():
    with patch("routers.events.record_event",
               new=AsyncMock(side_effect=RuntimeError("sheets down"))):
        resp = client.post("/api/events", json={"event": "page_view", "visitor_id": "v-1"})
    assert resp.status_code == 200
    assert resp.json() == {"recorded": False}


def test_an_unnamed_event_is_rejected():
    resp = client.post("/api/events", json={"event": "  ", "visitor_id": "v-1"})
    assert resp.json() == {"recorded": False, "error": "event name is required"}
