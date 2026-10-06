"""Shared-secret API token guard.

Every /api route except /api/health requires the token, sent as the X-Api-Key
header or, for EventSource (which cannot set headers), a ?token= query param.
The token comes from the API_TOKEN env var (a Secret Manager secret on Cloud Run).

Env is read per request so tests can monkeypatch it. With no API_TOKEN set the
API stays open for local dev, but on Cloud Run (K_SERVICE is set) it fails
closed so a missing secret binding never re-exposes the service.
"""
import hmac
import os

from fastapi import Request
from fastapi.responses import JSONResponse

API_KEY_HEADER = "X-Api-Key"
OPEN_PATHS = {"/api/health"}


def _on_cloud_run() -> bool:
    return bool(os.getenv("K_SERVICE"))


def docs_kwargs() -> dict:
    """FastAPI kwargs that hide /docs, /redoc and /openapi.json on Cloud Run."""
    if _on_cloud_run():
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}


async def require_api_token(request: Request, call_next):
    path = request.url.path
    if request.method == "OPTIONS" or not path.startswith("/api") or path in OPEN_PATHS:
        return await call_next(request)

    expected = os.getenv("API_TOKEN") or None
    if expected is None:
        if _on_cloud_run():
            return JSONResponse({"error": "Server auth not configured"}, status_code=503)
        return await call_next(request)

    supplied = request.headers.get(API_KEY_HEADER) or request.query_params.get("token") or ""
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await call_next(request)
