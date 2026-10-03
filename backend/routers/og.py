from __future__ import annotations
import asyncio
import os
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from landing import og_card
from landing.tickers import normalize, lookup
from services.rate_limit import RateLimiter, client_key

router = APIRouter()
_GENERIC = "/og-image.png"
_LOOKUP_TIMEOUT = 2.0  # a crawler will not wait for a cold SEC list download (spec §9)
# Drawing is the costly part, so it is limited per client. Over the limit is a redirect
# to the generic card, never a 429 body: a crawler would cache the error as the preview.
_limiter = RateLimiter(int(os.getenv("OG_RATE_LIMIT", "30")),
                       float(os.getenv("OG_RATE_WINDOW_SECONDS", "60")))


@router.api_route("/og/{name}", methods=["GET", "HEAD"], include_in_schema=False)
async def og_image(name: str, request: Request):
    """Per-ticker share card. Only tickers on the SEC list are ever drawn: anything
    else, including the list being unavailable, redirects to the generic card, so
    nobody can mint a branded image carrying their own text (spec §5)."""
    if not name.endswith(".png"):
        return RedirectResponse(_GENERIC, status_code=302)
    t = normalize(name[:-4])
    if t is None:
        return RedirectResponse(_GENERIC, status_code=302)
    try:
        known = (await asyncio.wait_for(asyncio.shield(lookup(t)), _LOOKUP_TIMEOUT))[0]
    except asyncio.TimeoutError:
        known = False  # shield(): the download carries on for the next request
    if not known or _limiter.limited(client_key(request)):
        return RedirectResponse(_GENERIC, status_code=302)
    png = await asyncio.to_thread(og_card.render_card, t)
    return Response(png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})
