from __future__ import annotations
import asyncio
from fastapi import APIRouter
from pydantic import BaseModel

from services.yahoo import validate_ticker
from orchestrator.batch import _run_one
from landing.contract import build_ticker_payload

router = APIRouter()

# The demo allowance (spec section 10). It is also the Free plan's per-run cap.
MAX_TICKERS = 3


class LandingAnalyzeRequest(BaseModel):
    tickers: list[str] = []


@router.post("/landing/analyze")
async def analyze(req: LandingAnalyzeRequest):
    seen: list[str] = []
    for raw in req.tickers:
        t = raw.strip().upper()
        if t and t not in seen:
            seen.append(t)

    if not seen:
        return {"results": [], "invalid": [], "error": "Enter at least one ticker."}
    if len(seen) > MAX_TICKERS:
        # Checked before validation so an oversized request never costs a Yahoo
        # round-trip or an engine run.
        return {"results": [], "invalid": [],
                "error": f"Up to {MAX_TICKERS} tickers per analysis run."}

    checks = await asyncio.gather(*[validate_ticker(t) for t in seen])
    valid = [t for t, ok in zip(seen, checks) if ok]
    invalid = [t for t, ok in zip(seen, checks) if not ok]
    if not valid:
        return {"results": [], "invalid": invalid, "error": None}

    runs = await asyncio.gather(*[_run_one(t) for t in valid], return_exceptions=True)

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
            results.append(build_ticker_payload(run["result"]))

    return {"results": results, "invalid": invalid, "error": None}
