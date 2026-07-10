from __future__ import annotations
from datetime import datetime, timezone
from screener.data import fetch_screener_inputs
from screener.metrics import compute_metrics
from screener.scoring import score
from screener.models import ScreenerResult


async def run(ticker: str) -> ScreenerResult:
    t = ticker.upper()
    inp = await fetch_screener_inputs(t)
    if inp is None:
        return ScreenerResult(ticker=t, status="failed",
                              errors=["yfinance data unavailable"])
    metrics = compute_metrics(inp)
    quality, sections, profile = score(metrics, metrics.sector)
    now = datetime.now(timezone.utc).isoformat()
    if quality is None:
        return ScreenerResult(
            ticker=t, company_name=inp.info.get("shortName") or inp.info.get("longName"),
            last_evaluated=now, sector=metrics.sector, sector_profile=profile,
            section_scores=sections, metrics=metrics.model_dump(),
            status="failed", errors=["insufficient data for a quality score"],
        )
    return ScreenerResult(
        ticker=t, company_name=inp.info.get("shortName") or inp.info.get("longName"),
        last_evaluated=now, quality_score=quality, sector=metrics.sector,
        sector_profile=profile, section_scores=sections, metrics=metrics.model_dump(),
        status="completed", errors=[],
    )
