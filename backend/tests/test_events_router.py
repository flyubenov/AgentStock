import re
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from main import app
import routers.events as events_router
import services.events_sheets as events_sheets

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_limiter():
    """The per-client rate limiter is module state; every test starts clean."""
    events_router._hits.clear()
    yield
    events_router._hits.clear()


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


# --- Problem 6: the endpoint accepts only what the page sends ---------------------

def test_the_backend_allowlist_is_exactly_the_frontend_event_list():
    # Two hand-kept copies of one list drift; read the frontend's and compare.
    src = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib"
           / "analytics.ts").read_text(encoding="utf-8")
    block = src[src.index("export const EVENTS"):]
    block = block[:block.index("})")]
    names = set(re.findall(r"^\s*\w+:\s*'([a-z_]+)'", block, re.M))
    assert len(names) == 12  # 11 original + watchlist_clicked (user decision 2026-09-26)
    assert names == events_router.FUNNEL_EVENTS


def _post(**body):
    base = {"event": "page_view", "visitor_id": "v-1"}
    base.update(body)
    with patch("routers.events.record_event", new=AsyncMock()) as rec:
        resp = client.post("/api/events", json=base)
    return resp, rec


@pytest.mark.parametrize("body,reason", [
    ({"event": "rage_click_v2"}, "unknown event"),
    ({"visitor_id": "x" * 65}, "invalid visitor_id"),
    ({"visitor_id": "<script>"}, "invalid visitor_id"),
    ({"ts": "9" * 41}, "invalid ts"),
    ({"props": {f"k{i}": i for i in range(21)}}, "too many props"),
    ({"props": {"blob": "x" * 3000}}, "props too large"),
])
def test_a_refused_event_is_not_queued_and_still_answers_200(body, reason):
    resp, rec = _post(**body)
    assert resp.status_code == 200
    assert resp.json() == {"recorded": False, "error": reason}
    rec.assert_not_awaited()


def test_the_real_payloads_all_fit():
    # The largest things the page actually sends must never be refused.
    real = [
        {"event": "analysis_started",
         "props": {"tickers": ["AAPL", "MSFT", "NVDA"], "count": 3, "source": "sample"}},
        {"event": "email_submitted",
         "props": {"plan": "Unlimited", "billing": "monthly",
                   "email": "someone.with.a.long.name@example-company.co.uk"}},
        {"event": "free_plan_clicked",
         "props": {"plan": "Free", "billing": "annual", "source": "checkout"}},
    ]
    for body in real:
        resp, rec = _post(visitor_id="v-mf2k9x1a-3kd9s0qp", **body)
        assert resp.json() == {"recorded": True}, body
        rec.assert_awaited_once()


def test_one_client_is_rate_limited_and_another_is_not(monkeypatch):
    monkeypatch.setattr(events_router, "_RATE_LIMIT", 3)
    with patch("routers.events.record_event", new=AsyncMock()) as rec:
        a = [client.post("/api/events", json={"event": "page_view", "visitor_id": "v-1"},
                         headers={"x-forwarded-for": "203.0.113.7"}).json()
             for _ in range(4)]
        b = client.post("/api/events", json={"event": "page_view", "visitor_id": "v-2"},
                        headers={"x-forwarded-for": "198.51.100.9"}).json()
    assert a[:3] == [{"recorded": True}] * 3
    assert a[3] == {"recorded": False, "error": "rate limited"}
    assert b == {"recorded": True}
    assert rec.await_count == 4


def test_the_limit_frees_up_once_the_window_passes(monkeypatch):
    t = [100.0]
    monkeypatch.setattr(events_router, "_now", lambda: t[0])
    monkeypatch.setattr(events_router, "_RATE_LIMIT", 2)
    monkeypatch.setattr(events_router, "_RATE_WINDOW_SECONDS", 60)
    assert not events_router._rate_limited("ip")
    assert not events_router._rate_limited("ip")
    assert events_router._rate_limited("ip")
    t[0] += 60
    assert not events_router._rate_limited("ip")


def test_a_forged_forwarded_for_prefix_does_not_dodge_the_limit(monkeypatch):
    # Cloud Run appends the real address; a client can only prepend. Keying on the
    # right-most entry means rotating the prefix changes nothing.
    monkeypatch.setattr(events_router, "_RATE_LIMIT", 2)
    with patch("routers.events.record_event", new=AsyncMock()):
        out = [client.post("/api/events", json={"event": "page_view", "visitor_id": "v-1"},
                           headers={"x-forwarded-for": f"10.0.0.{i}, 203.0.113.7"}).json()
               for i in range(3)]
    assert out[2] == {"recorded": False, "error": "rate limited"}


def test_the_limiter_forgets_the_least_recent_client_past_its_bound(monkeypatch):
    monkeypatch.setattr(events_router, "_MAX_CLIENTS", 3)
    for ip in ["a", "b", "c", "d"]:
        events_router._rate_limited(ip)
    assert list(events_router._hits) == ["b", "c", "d"]
