"""Single-ticker validation harness for Agent Stock.

Runs BOTH pipelines live (yfinance) for one ticker and dumps everything an
analyst needs to cross-check the result against the pipeline logic:
the extracted `fin` inputs, the raw statement fetches, the classifier verdict,
the full FV breakdown (per-leg weight + scenarios), and the Quality sections.

Usage (from anywhere; it locates backend/ itself):
    python validate_ticker.py PLTR
    python validate_ticker.py NBIS --inputs      # also dump raw fin inputs

This is a READ-ONLY probe: it only calls existing engine functions on live
data. It changes nothing and does not touch Sheets.
"""
from __future__ import annotations
import asyncio, json, sys
from pathlib import Path


def _add_backend_to_path() -> Path:
    """Walk up from this file looking for a dir containing backend/valuation/engine.py."""
    here = Path(__file__).resolve()
    for base in [here.parent, *here.parents]:
        cand = base / "backend"
        if (cand / "valuation" / "engine.py").exists():
            sys.path.insert(0, str(cand))
            return cand
    raise SystemExit("Could not locate the Agent Stock backend/ dir from " + str(here))


_add_backend_to_path()

from valuation.engine import run as fv_run              # noqa: E402
from screener.engine import run as sc_run               # noqa: E402
from services.yahoo import (                            # noqa: E402
    fetch_ticker_info, extract_financials, fetch_ticker_cashflow,
    fetch_ev_ebitda_history, fetch_quarterly_revenue,
)


async def dump_inputs(ticker: str) -> dict:
    """Reproduce the raw inputs engine.run() feeds the pipeline, for cross-checking."""
    info = await fetch_ticker_info(ticker)
    fin = extract_financials(info)
    cashflow = await fetch_ticker_cashflow(ticker)
    hist = await fetch_ev_ebitda_history(ticker)
    quarters = await fetch_quarterly_revenue(ticker)
    return {
        "extract_financials": fin,
        "cashflow_statement": cashflow,
        "ev_ebitda_history": hist,
        "quarterly_revenue": quarters,
    }


async def main(ticker: str, with_inputs: bool):
    fv, sc = await asyncio.gather(fv_run(ticker), sc_run(ticker))
    out = {
        "FV": fv.model_dump(),
        "QUALITY": {
            "quality_score": sc.quality_score,
            "sector": sc.sector,
            "sector_profile": sc.sector_profile,
            "section_scores": sc.section_scores,
            "score_breakdown": sc.score_breakdown,
            "status": sc.status,
            "errors": sc.errors,
        },
    }
    if with_inputs:
        out["INPUTS"] = await dump_inputs(ticker)
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = {a for a in sys.argv[1:] if a.startswith("-")}
    ticker = (args[0] if args else "PLTR").upper()
    asyncio.run(main(ticker, with_inputs="--inputs" in flags))
