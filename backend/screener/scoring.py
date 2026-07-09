from __future__ import annotations
from screener.models import ScreenerMetrics


def score_high(value: float | None, bands: list[tuple[float, float]], below: float) -> float | None:
    if value is None:
        return None
    for thr, sc in bands:
        if value >= thr:
            return sc
    return below


def score_low(value: float | None, bands: list[tuple[float, float]], above: float) -> float | None:
    if value is None:
        return None
    for thr, sc in bands:
        if value <= thr:
            return sc
    return above


def leverage_score(r: float | None, pivot: float | None) -> float | None:
    if r is None or pivot is None:
        return None
    if r <= 0:
        return 10.0
    if r <= 0.5 * pivot:
        return 9.0
    if r <= pivot:
        return 7.0
    if r <= 1.4 * pivot:
        return 4.5
    if r <= 1.8 * pivot:
        return 2.0
    return 0.0


PROFILES: dict[str, dict] = {
    "TECH_GROWTH":         {"w": (0.35, 0.30, 0.15, 0.20), "P": 2.5, "Q": 3.0},
    "BALANCED":            {"w": (0.30, 0.30, 0.20, 0.20), "P": 2.5, "Q": 3.0},
    "DEFENSIVE_INCOME":    {"w": (0.15, 0.25, 0.35, 0.25), "P": 4.5, "Q": 6.0},
    "INDUSTRIAL_CYCLICAL": {"w": (0.25, 0.30, 0.30, 0.15), "P": 3.0, "Q": 4.0},
    "FINANCIALS":          {"w": (0.35, 0.40, 0.00, 0.25), "P": None, "Q": None},
    "REIT":                {"w": (0.30, 0.20, 0.25, 0.25), "P": 6.5, "Q": 8.0},
}

SECTOR_TO_PROFILE: dict[str, str] = {
    "technology": "TECH_GROWTH",
    "communication services": "BALANCED",
    "consumer cyclical": "BALANCED",
    "healthcare": "BALANCED",
    "utilities": "DEFENSIVE_INCOME",
    "consumer defensive": "DEFENSIVE_INCOME",
    "industrials": "INDUSTRIAL_CYCLICAL",
    "basic materials": "INDUSTRIAL_CYCLICAL",
    "energy": "INDUSTRIAL_CYCLICAL",
    "financial services": "FINANCIALS",
    "real estate": "REIT",
}


def base_profile(sector: str | None) -> str:
    return SECTOR_TO_PROFILE.get((sector or "").strip().lower(), "BALANCED")


def apply_nudge(base: str, m: ScreenerMetrics) -> str:
    # 1. Growth override: BALANCED + strong revenue growth + net cash -> TECH_GROWTH
    if base == "BALANCED" and (m.revenue_cagr_3y or 0) >= 15.0 and (m.net_debt is not None and m.net_debt < 0):
        return "TECH_GROWTH"
    # 2. Special-profile data-fit fallback: FINANCIALS/REIT that operate like a
    #    normal company (material positive EBITDA, normal leverage, real op margin).
    if base in ("FINANCIALS", "REIT"):
        if (m.ebitda is not None and m.ebitda > 0
                and m.net_debt_ebitda is not None and m.net_debt_ebitda < 4
                and m.op_margin is not None):
            return "BALANCED"
    return base
