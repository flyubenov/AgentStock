from __future__ import annotations
import asyncio
import os
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.rate_limit import RateLimiter, client_key
from services.yahoo import validate_ticker
from landing.cache import get_analysis
from landing.contract import build_ticker_payload
from landing.tickers import normalize, lookup, list_available

router = APIRouter()

# The demo allowance (spec section 10). It is also the Free plan's per-run cap.
MAX_TICKERS = 3

# A per-IP brake on this public endpoint: an uncached ticker runs all four engines
# against Yahoo. A real visitor runs a handful per minute; this only bites a script.
RATE_LIMIT_MESSAGE = "Too many analyses from your network. Please wait a minute and try again."
_limiter = RateLimiter(int(os.getenv("LANDING_RATE_LIMIT", "20")),
                       float(os.getenv("LANDING_RATE_WINDOW_SECONDS", "60")))


class LandingAnalyzeRequest(BaseModel):
    tickers: list[str] = []


@router.post("/landing/analyze")
async def analyze(req: LandingAnalyzeRequest, request: Request):
    if _limiter.limited(client_key(request)):
        # Same three-key shape as every other return: the page renders `error` verbatim.
        return JSONResponse(status_code=429, content={
            "results": [], "invalid": [], "error": RATE_LIMIT_MESSAGE})

    seen: list[str] = []
    for raw in req.tickers:
        t = raw.strip().upper()
        if t and t not in seen:
            seen.append(t)

    if not seen:
        return {"results": [], "invalid": [], "error": "Enter at least one ticker."}
    if len(seen) > MAX_TICKERS:
        # Checked before validation and before any engine run.
        return {"results": [], "invalid": [],
                "error": f"Up to {MAX_TICKERS} tickers per analysis run."}

    checks = await asyncio.gather(*[validate_ticker(t) for t in seen])
    valid = [t for t, ok in zip(seen, checks) if ok]
    invalid = [t for t, ok in zip(seen, checks) if not ok]
    if not valid:
        return {"results": [], "invalid": invalid, "error": None}

    # get_analysis (backend/landing/cache.py) serves fundamentals from a multi-day cache (LANDING_SLOW_TTL; 7 days in production)
    # and price/Reward-Risk from a shorter one (LANDING_FAST_TTL). On this public,
    # unauthenticated endpoint a hung yfinance call must never hold a worker open
    # indefinitely, on either path: a cold/expired slow fill still goes through
    # _run_one_readonly's own asyncio.wait_for, and cache.py wraps its own fast-layer
    # quote refresh in a short asyncio.wait_for of its own. Either one timing out
    # raises, which the exception branch below degrades to a per-ticker error instead
    # of wedging the whole request.
    runs = await asyncio.gather(*[get_analysis(t) for t in valid], return_exceptions=True)

    results = []
    for ticker, run in zip(valid, runs):
        if isinstance(run, Exception):
            # One dead pipeline must not sink the whole grid. Tag with a prefix
            # build_ticker_payload's error mapping does not recognize so it falls
            # back to the generic label — the exception text (`run`) itself must
            # never reach the payload (contract.py's _public_error strips it).
            results.append(build_ticker_payload(
                {"ticker": ticker, "errors": [f"landing: {run}"], "status": "failed"}))
        else:
            results.append(build_ticker_payload(run))

    return {"results": results, "invalid": invalid, "error": None}


@router.get("/landing/ticker/{raw}")
async def ticker_check(raw: str, request: Request):
    """Is this /t/ link a real US ticker (spec 2026-10-03 §3)? While the SEC list is
    unavailable, any well-formed ticker reads as known: the page then tries the
    analysis and falls back only if that fails, so an SEC outage never breaks an
    ad landing. Only the card generator treats "list unavailable" as unknown."""
    if _limiter.limited(client_key(request)):
        return JSONResponse(status_code=429, content={"ticker": None, "known": False, "name": None})
    t = normalize(raw)
    if t is None:
        return {"ticker": None, "known": False, "name": None}
    if not await list_available():
        return {"ticker": t, "known": True, "name": None}
    known, name = await lookup(t)
    return {"ticker": t, "known": known, "name": name}
