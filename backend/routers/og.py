from __future__ import annotations
import asyncio
from fastapi import APIRouter
from fastapi.responses import RedirectResponse, Response

from landing import og_card
from landing.tickers import normalize, lookup

router = APIRouter()
_GENERIC = "/og-image.png"


@router.api_route("/og/{name}", methods=["GET", "HEAD"], include_in_schema=False)
async def og_image(name: str):
    """Per-ticker share card. Only tickers on the SEC list are ever drawn: anything
    else, including the list being unavailable, redirects to the generic card, so
    nobody can mint a branded image carrying their own text (spec §5)."""
    if not name.endswith(".png"):
        return RedirectResponse(_GENERIC, status_code=302)
    t = normalize(name[:-4])
    if t is None or not (await lookup(t))[0]:
        return RedirectResponse(_GENERIC, status_code=302)
    png = await asyncio.to_thread(og_card.render_card, t)
    return Response(png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})
