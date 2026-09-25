from __future__ import annotations
import json, os, re, time
from collections import OrderedDict, deque
from datetime import datetime, timezone
from fastapi import APIRouter, Request

from models import AnalyticsEvent
from services.events_sheets import record_event

router = APIRouter()

# The closed funnel list (spec section 9), mirrored from frontend/src/lib/analytics.ts
# EVENTS. test_events_router.py reads that file and fails if the two ever differ. This
# public, unauthenticated endpoint appends rows to a spreadsheet, so a name outside the
# list is refused rather than written: it can only be noise or abuse.
FUNNEL_EVENTS = frozenset({
    "page_view", "analysis_started", "analysis_completed", "breakdown_opened",
    "methodology_viewed", "pricing_viewed", "plan_selected", "checkout_started",
    "payment_button_clicked", "email_submitted", "free_plan_clicked",
})

# Size limits, each far above anything the page itself sends (the largest real payload
# is analysis_started's three tickers, or email_submitted's one address).
_VISITOR_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_MAX_TS_LEN = 40
_MAX_PROPS_KEYS = 20
_MAX_PROPS_BYTES = 2048

# A light per-client limit. One real visit posts about a dozen events over minutes;
# this allows several times that per minute, so it only ever bites a script.
_RATE_LIMIT = int(os.getenv("EVENTS_RATE_LIMIT", "60"))
_RATE_WINDOW_SECONDS = float(os.getenv("EVENTS_RATE_WINDOW_SECONDS", "60"))
# Bounds the limiter's own memory: past this many distinct clients the least recently
# seen is forgotten.
_MAX_CLIENTS = 10_000
_hits: "OrderedDict[str, deque[float]]" = OrderedDict()
_now = time.monotonic          # indirection so tests can move the clock


def _client_key(request: Request) -> str:
    """The caller's IP. Behind Cloud Run the Google front end APPENDS the address it
    saw to X-Forwarded-For, so the right-most entry is the one a client cannot forge;
    anything to its left came from the client itself."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd.strip():
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def _rate_limited(key: str) -> bool:
    now = _now()
    q = _hits.get(key)
    if q is None:
        q = deque()
        _hits[key] = q
        while len(_hits) > _MAX_CLIENTS:
            _hits.popitem(last=False)
    else:
        _hits.move_to_end(key)
    while q and now - q[0] >= _RATE_WINDOW_SECONDS:
        q.popleft()
    if len(q) >= _RATE_LIMIT:
        return True
    q.append(now)
    return False


def _rejection(ev: AnalyticsEvent) -> str | None:
    if ev.event not in FUNNEL_EVENTS:
        return "unknown event"
    if not _VISITOR_ID.match(ev.visitor_id or ""):
        return "invalid visitor_id"
    if ev.ts is not None and len(ev.ts) > _MAX_TS_LEN:
        return "invalid ts"
    props = ev.props or {}
    if len(props) > _MAX_PROPS_KEYS:
        return "too many props"
    try:
        size = len(json.dumps(props))
    except (TypeError, ValueError):
        return "invalid props"
    if size > _MAX_PROPS_BYTES:
        return "props too large"
    return None


@router.post("/events")
async def post_event(ev: AnalyticsEvent, request: Request):
    """Fire-and-forget funnel analytics. This endpoint must never make the funnel
    fail: a bad or refused payload returns 200 with recorded=False.

    recorded: True means the event was accepted and queued — not that it was
    confirmed written to Sheets. A queued row survives a Sheets outage and goes
    out on a later flush.
    """
    if not ev.event.strip():
        return {"recorded": False, "error": "event name is required"}
    reason = _rejection(ev)
    if reason:
        return {"recorded": False, "error": reason}
    if _rate_limited(_client_key(request)):
        return {"recorded": False, "error": "rate limited"}
    ev.ts = ev.ts or datetime.now(timezone.utc).isoformat()
    try:
        await record_event(ev)
    except Exception:
        # Don't leak sink internals (e.g. Sheets error text) to the client —
        # the funnel just needs to know the click wasn't recorded.
        return {"recorded": False}
    return {"recorded": True}
