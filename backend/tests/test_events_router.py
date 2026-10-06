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
    events_router._limiter.clear()
    yield
    events_router._limiter.clear()


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
    assert len(names) == 14  # 11 original + watchlist_clicked (2026-09-26) + ticker_link_opened, share_clicked (2026-10-03)
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
    monkeypatch.setattr(events_router._limiter, "limit", 3)
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


def test_a_forged_forwarded_for_prefix_does_not_dodge_the_limit(monkeypatch):
    # Cloud Run appends the real address; a client can only prepend. Keying on the
    # right-most entry means rotating the prefix changes nothing.
    monkeypatch.setattr(events_router._limiter, "limit", 2)
    with patch("routers.events.record_event", new=AsyncMock()):
        out = [client.post("/api/events", json={"event": "page_view", "visitor_id": "v-1"},
                           headers={"x-forwarded-for": f"10.0.0.{i}, 203.0.113.7"}).json()
               for i in range(3)]
    assert out[2] == {"recorded": False, "error": "rate limited"}


def test_attribution_rides_beside_the_props():
    att = {"channel": "x", "utm_source": "x", "utm_campaign": "oct-nvda",
           "landing": "/t/NVDA", "visit_channel": "direct"}
    resp, rec = _post(props={"plan": "Pro"}, attribution=att)
    assert resp.json() == {"recorded": True}
    ev = rec.await_args.args[0]
    assert ev.props == {"plan": "Pro"}
    assert ev.attribution == att


@pytest.mark.parametrize("att,reason", [
    ({f"k{i}": i for i in range(13)}, "too many attribution fields"),
    ({"utm_campaign": "x" * 3000}, "attribution too large"),
])
def test_oversized_attribution_is_refused(att, reason):
    resp, rec = _post(attribution=att)
    assert resp.json() == {"recorded": False, "error": reason}
    rec.assert_not_awaited()


def test_a_maximal_legitimate_attribution_is_recorded():
    # Eight Touch fields plus visit_channel, each at the 100-character cap: about
    # 1,040 bytes of JSON. First touch persists, so a refusal here would drop every
    # later event of that visitor.
    att = {f"field_{i}": "x" * 100 for i in range(9)}
    resp, rec = _post(attribution=att)
    assert resp.json() == {"recorded": True}


def test_accepts_the_owner_marker_visitor_id():
    # ?me=1 (frontend/src/lib/analytics.ts) sends "me-" + the browser's usual ID; a
    # refusal here would silently drop every event from a marked browser.
    from models import AnalyticsEvent
    ev = AnalyticsEvent(event="page_view", visitor_id="me-v-muu7m3cx-ezatcw8g")
    assert events_router._rejection(ev) is None


# --- Bot and junk filtering (security review 2026-10-06) ---------------------------
# Scanners that drive a real browser load /login, /admin and the like, get the page
# and fire its events. Those rows polluted the funnel, so they are refused here.

@pytest.mark.parametrize("landing", ["/", "/checkout", "/privacy", "/t/NVDA", "/t/brk-b",
                                     "/checkout/"])
def test_a_real_landing_page_is_recorded(landing):
    resp, rec = _post(attribution={"channel": "x", "landing": landing})
    assert resp.json() == {"recorded": True}


@pytest.mark.parametrize("landing", ["/login", "/wp-admin/install.php", "/.env", "//login",
                                     "/admin", "/app", "/database"])
def test_a_visitor_who_landed_on_a_page_that_does_not_exist_is_refused(landing):
    resp, rec = _post(attribution={"channel": "direct", "landing": landing})
    assert resp.json() == {"recorded": False, "error": "unknown landing page"}
    rec.assert_not_awaited()


def _post_as(headers, **body):
    base = {"event": "page_view", "visitor_id": "v-1"}
    base.update(body)
    with patch("routers.events.record_event", new=AsyncMock()) as rec:
        resp = client.post("/api/events", json=base, headers=headers)
    return resp, rec


@pytest.mark.parametrize("ua", [
    "",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/152.0.0.0 Safari/537.36",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; ChatGLM-Spider/1.0; +https://zhipuai.cn/)",
    "python-httpx/0.25.1",
    "curl/8.4.0",
    "Mozilla/5.0 (l9scan/2.0.1323e22333e2933323e2631323; +https://leakix.net)",
])
def test_automated_clients_are_refused(ua):
    resp, rec = _post_as({"user-agent": ua})
    assert resp.json() == {"recorded": False, "error": "automated client"}
    rec.assert_not_awaited()


@pytest.mark.parametrize("ua", [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 26_6_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/154.0.8037.55 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; CUBOT X30) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0 Mobile Safari/537.36",
])
def test_real_browsers_are_recorded_with_their_user_agent(ua):
    resp, rec = _post_as({"user-agent": ua})
    assert resp.json() == {"recorded": True}
    assert rec.await_args.kwargs["user_agent"] == ua


def test_an_event_posted_from_another_site_is_refused(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://intrinsica.io")
    resp, rec = _post_as({"origin": "https://evil.example"})
    assert resp.json() == {"recorded": False, "error": "foreign origin"}
    rec.assert_not_awaited()
    ok, _ = _post_as({"origin": "https://intrinsica.io"})
    assert ok.json() == {"recorded": True}
