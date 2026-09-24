from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter

from models import AnalyticsEvent
from services.events_sheets import record_event

router = APIRouter()


@router.post("/events")
async def post_event(ev: AnalyticsEvent):
    """Fire-and-forget funnel analytics. This endpoint must never make the funnel
    fail: a bad payload or a dead sink returns 200 with recorded=False."""
    if not ev.event.strip():
        return {"recorded": False, "error": "event name is required"}
    ev.ts = ev.ts or datetime.now(timezone.utc).isoformat()
    try:
        await record_event(ev)
    except Exception:
        # Don't leak sink internals (e.g. Sheets error text) to the client —
        # the funnel just needs to know the click wasn't recorded.
        return {"recorded": False}
    return {"recorded": True}
