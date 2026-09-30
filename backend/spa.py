from __future__ import annotations
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

# Vite fingerprints everything under assets/, so a changed file gets a new name and
# can be cached for good. index.html must always be revalidated, or a deploy would not
# reach returning visitors. Other root files (og-image.png, favicon) get an hour.
_IMMUTABLE = "public, max-age=31536000, immutable"
_SHORT = "public, max-age=3600"
_NO_CACHE = "no-cache"


def mount_spa(app: FastAPI, static_dir: str) -> bool:
    """Serve the built frontend from static_dir: real files as-is, every other non-/api
    path as index.html (React Router takes it from there -- including future /t/AMZN
    share links). /api/* never falls back to the page: an unknown API path is a JSON
    404, so the frontend never parses HTML as JSON. Register this LAST: its catch-all
    would otherwise shadow later routes. Returns False, registering nothing, when
    static_dir is unset or has no index.html (local dev, where Vite serves the page)."""
    if not static_dir:
        return False
    root = Path(static_dir).resolve()
    index = root / "index.html"
    if not index.is_file():
        return False
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
        return FileResponse(index, headers={"Cache-Control": _NO_CACHE})

    return True
