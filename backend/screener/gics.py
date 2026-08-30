"""Map yfinance's sector taxonomy onto the 11 GICS sectors.

Yahoo's `info["sector"]` is GICS-11 with five relabelled buckets; the rest are
already GICS names. So GICS compliance for the *sector* line is a small,
deterministic rename — we do NOT touch `industry` (Yahoo's ~140 industries do
not map 1:1 to GICS sub-industries, so it is shown verbatim). Unknown values
pass through unchanged rather than blanking out."""
from __future__ import annotations

# Yahoo label -> GICS sector, only for the five that differ. Anything not here
# (Industrials, Energy, Utilities, Real Estate, Communication Services) already
# matches GICS and passes through.
YAHOO_TO_GICS_SECTOR: dict[str, str] = {
    "Technology": "Information Technology",
    "Financial Services": "Financials",
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Healthcare": "Health Care",
    "Basic Materials": "Materials",
}


def to_gics_sector(sector: str | None) -> str | None:
    """Yahoo sector -> GICS sector. None/blank -> None; unknown -> verbatim."""
    if not sector:
        return None
    return YAHOO_TO_GICS_SECTOR.get(sector, sector)
