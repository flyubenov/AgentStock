from __future__ import annotations
import json, os, re
from datetime import datetime, timezone
from fastapi import APIRouter, Request

from models import AnalyticsEvent
from services.events_sheets import record_event
from services.rate_limit import RateLimiter, client_key

router = APIRouter()

# The closed funnel list (spec section 9), mirrored from frontend/src/lib/analytics.ts
# EVENTS. test_events_router.py reads that file and fails if the two ever differ. This
# public, unauthenticated endpoint appends rows to a spreadsheet, so a name outside the
# list is refused rather than written: it can only be noise or abuse.
FUNNEL_EVENTS = frozenset({
    "page_view", "analysis_started", "analysis_completed", "breakdown_opened",
    "methodology_viewed", "pricing_viewed", "plan_selected", "checkout_started",
    "payment_button_clicked", "email_submitted", "free_plan_clicked",
    "watchlist_clicked", "ticker_link_opened", "share_clicked",
})

# Size limits, each far above anything the page itself sends (the largest real payload
# is analysis_started's three tickers, or email_submitted's one address).
_VISITOR_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_MAX_TS_LEN = 40
_MAX_PROPS_KEYS = 20
_MAX_PROPS_BYTES = 2048
# The page sends at most nine attribution fields (eight Touch fields plus
# visit_channel) of at most 100 characters each: about 1,040 bytes of JSON. The limit
# must clear that with room to spare, because first touch persists and a refusal would
# drop every later event of that visitor.
_MAX_ATTRIBUTION_KEYS = 12
_MAX_ATTRIBUTION_BYTES = 2048

# A light per-client limit. One real visit posts about a dozen events over minutes;
# this allows several times that per minute, so it only ever bites a script.
_limiter = RateLimiter(int(os.getenv("EVENTS_RATE_LIMIT", "60")),
                       float(os.getenv("EVENTS_RATE_WINDOW_SECONDS", "60")))


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
    attribution = ev.attribution or {}
    if len(attribution) > _MAX_ATTRIBUTION_KEYS:
        return "too many attribution fields"
    try:
        size = len(json.dumps(attribution))
    except (TypeError, ValueError):
        return "invalid attribution"
    if size > _MAX_ATTRIBUTION_BYTES:
        return "attribution too large"
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
    if _limiter.limited(client_key(request)):
        return {"recorded": False, "error": "rate limited"}
    ev.ts = ev.ts or datetime.now(timezone.utc).isoformat()
    try:
        await record_event(ev)
    except Exception:
        # Don't leak sink internals (e.g. Sheets error text) to the client —
        # the funnel just needs to know the click wasn't recorded.
        return {"recorded": False}
    return {"recorded": True}
