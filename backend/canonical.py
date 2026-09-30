from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse


def add_canonical_host_redirect(app: FastAPI, canonical_host: str) -> None:
    """301 www.<canonical_host> to https://<canonical_host>, keeping path and query, so
    every shared link and og:url has one address. Both hosts are mapped to the same
    Cloud Run service; only www is redirected (never the apex, so no loop). A no-op
    when canonical_host is empty (local dev)."""
    if not canonical_host:
        return
    www = f"www.{canonical_host}".lower()

    @app.middleware("http")
    async def _to_canonical(request: Request, call_next):
        host = request.headers.get("host", "").split(":")[0].lower()
        if host == www:
            target = f"https://{canonical_host}{request.url.path}"
            if request.url.query:
                target += f"?{request.url.query}"
            return RedirectResponse(target, status_code=301)
        return await call_next(request)
