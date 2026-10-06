from __future__ import annotations

from fastapi import FastAPI, Request

# Security review 2026-10-06. The public site loads everything from its own origin
# (fonts are self-hosted, the API is same-origin), so the policy can be strict.
# style-src needs 'unsafe-inline' for React's style attributes; scripts never do.
_CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Content-Security-Policy": _CSP,
}


def add_security_headers(app: FastAPI) -> None:
    """Add the standard browser security headers to every response. Production only:
    local dev serves the page from Vite, whose dev scripts this policy would block."""

    @app.middleware("http")
    async def _security_headers(request: Request, call_next):
        response = await call_next(request)
        for name, value in _HEADERS.items():
            response.headers.setdefault(name, value)
        return response
