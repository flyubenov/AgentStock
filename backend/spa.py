from __future__ import annotations
import asyncio
import html
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from landing.tickers import normalize, lookup

# Vite fingerprints everything under assets/, so a changed file gets a new name and
# can be cached for good. index.html must always be revalidated, or a deploy would not
# reach returning visitors. Other root files (og-image.png, favicon) get an hour.
_IMMUTABLE = "public, max-age=31536000, immutable"
_SHORT = "public, max-age=3600"
_NO_CACHE = "no-cache"
_SITE = "https://intrinsica.io"
# X's crawler gives up after a few seconds; a cold instance may still be downloading
# the SEC list, so the page is served generic rather than late (spec §9).
_LOOKUP_TIMEOUT = 2.0


def _ticker_page(index_html: str, t: str) -> str:
    """index.html with the preview tags swapped for ticker t (spec 2026-10-03 §5).
    t is a canonical ticker already confirmed on the SEC list; escaped regardless."""
    title = html.escape(f"{t}: quality business? Durable moat? Fair price? · Intrinsica", quote=True)
    image = html.escape(f"{_SITE}/og/{t}.png", quote=True)
    url = html.escape(f"{_SITE}/t/{t}", quote=True)
    out = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", index_html, count=1, flags=re.S)
    out = re.sub(r'(<meta property="og:title" content=")[^"]*(")', rf"\g<1>{title}\g<2>", out, count=1)
    out = re.sub(r'(<meta property="og:url" content=")[^"]*(")', rf"\g<1>{url}\g<2>", out, count=1)
    out = re.sub(r'(<meta property="og:image" content=")[^"]*(")', rf"\g<1>{image}\g<2>", out, count=1)
    out = re.sub(r'(<meta name="twitter:image" content=")[^"]*(")', rf"\g<1>{image}\g<2>", out, count=1)
    return out


def mount_spa(app: FastAPI, static_dir: str) -> bool:
    """Serve the built frontend from static_dir: real files as-is, every other non-/api
    path as index.html (React Router takes it from there -- /t/{TICKER}
    share links, which get per-ticker preview tags). /api/* never falls back to the page: an unknown API path is a JSON
    404, so the frontend never parses HTML as JSON. Register this LAST: its catch-all
    would otherwise shadow later routes. Returns False, registering nothing, when
    static_dir is unset or has no index.html (local dev, where Vite serves the page)."""
    if not static_dir:
        return False
    root = Path(static_dir).resolve()
    index = root / "index.html"
    if not index.is_file():
        return False
    index_html = index.read_text(encoding="utf-8")
    assets = root / "assets"

    # HEAD too: uptime monitors and link-preview crawlers probe with it, and FastAPI's
    # @app.get does not add it (a 405 there reads as "site down").
    @app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def spa(path: str):
        if path == "api" or path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        if path:
            candidate = (root / path).resolve()
            # resolve() collapses ../ and follows links; is_relative_to then refuses
            # anything that ended up outside the static dir (path traversal).
            if candidate.is_relative_to(root) and candidate.is_file() and candidate != index:
                cache = _IMMUTABLE if candidate.is_relative_to(assets) else _SHORT
                return FileResponse(candidate, headers={"Cache-Control": cache})
        m = re.fullmatch(r"t/([^/]+)", path)
        if m:
            t = normalize(m.group(1))
            known = False
            if t is not None:
                try:
                    known = (await asyncio.wait_for(asyncio.shield(lookup(t)), _LOOKUP_TIMEOUT))[0]
                except asyncio.TimeoutError:
                    pass  # shield(): the download carries on for the next request
            if known:
                return HTMLResponse(_ticker_page(index_html, t), headers={"Cache-Control": _NO_CACHE})
        return FileResponse(index, headers={"Cache-Control": _NO_CACHE})

    return True
