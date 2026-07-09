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


ROIC_BANDS = [(20, 10), (15, 8.5), (10, 6.5), (5, 4), (0, 2)]
SPREAD_BANDS = [(10, 10), (5, 8), (0, 5.5), (-5, 2.5)]
ROTE_BANDS = [(25, 10), (20, 8.5), (15, 7), (10, 5), (5, 3)]
GROWTH_BANDS = [(20, 10), (15, 8.5), (10, 7), (5, 5), (2, 3), (0, 1.5)]
FCF_CAGR_BANDS = [(15, 10), (10, 8), (5, 6), (0, 4)]
FCF_MARGIN_BANDS = [(20, 10), (15, 8.5), (10, 7), (5, 5), (0, 3)]
MARGIN_LEVEL_BANDS = [(25, 10), (15, 8), (8, 6), (0, 3)]
TRAJECTORY_BANDS = [(2, 10), (0, 7), (-2, 4)]
GROSS_MARGIN_BANDS = [(60, 10), (40, 8), (25, 6), (10, 4)]
OCF_CAPEX_BANDS = [(5, 10), (3, 8), (2, 6), (1.5, 4), (1, 2)]
SHARES_BANDS = [(-3, 10), (-1, 8.5), (0, 7), (1, 5), (3, 3)]   # score_low
SBC_BANDS = [(2, 10), (5, 8), (10, 6), (15, 3.5), (20, 1.5)]   # score_low
EQ_BANDS = [(1.2, 10), (1.0, 8.5), (0.8, 6), (0.6, 4)]
INSIDER_BANDS = [(10, 10), (5, 8), (2, 6), (0.5, 4)]
YIELD_BANDS = [(6, 10), (4, 8.5), (2, 6.5), (0, 4)]


def _mean(vals: list[float | None]) -> float | None:
    present = [v for v in vals if v is not None]
    return sum(present) / len(present) if present else None


def _section_iii(m: ScreenerMetrics, profile: str) -> float | None:
    p = PROFILES[profile]
    nde = leverage_score(m.net_debt_ebitda, p["P"])
    ndf = leverage_score(m.net_debt_fcf, p["Q"])
    ocf = score_high(m.ocf_capex, OCF_CAPEX_BANDS, 0)
    # Balance-Sheet Dual-Check: FCF-based debt looks far worse than EBITDA-based
    # AND EBITDA leverage is healthy (<2.5) -> treat ND/FCF as capex-cycle noise.
    if (nde is not None and ndf is not None and m.net_debt_ebitda is not None
            and m.net_debt_ebitda < 2.5 and ndf < nde - 2):
        ndf = None  # drop the noisy metric
    return _mean([nde, ndf, ocf])


def section_scores(m: ScreenerMetrics, profile: str) -> dict[str, float | None]:
    section_i = _mean([
        score_high(m.revenue_cagr_3y, GROWTH_BANDS, 0),
        score_high(m.eps_cagr_3y, GROWTH_BANDS, 0),
        score_high(m.fcf_cagr_3y, FCF_CAGR_BANDS, 1),
        score_high(m.fcf_margin, FCF_MARGIN_BANDS, 0),
        score_high(m.op_margin, MARGIN_LEVEL_BANDS, 0),
        score_high(m.op_margin_trajectory, TRAJECTORY_BANDS, 1),
        score_high(m.gross_margin, GROSS_MARGIN_BANDS, 2),
    ])
    section_ii = _mean([
        score_high(m.roic_ttm, ROIC_BANDS, 0),
        score_high(m.roic_5y_avg, ROIC_BANDS, 0),
        score_high(m.roic_wacc_spread, SPREAD_BANDS, 0),
        score_high(m.rote, ROTE_BANDS, 1),
    ])
    section_iv = _mean([
        score_low(m.shares_cagr_3y, SHARES_BANDS, 1),
        score_low(m.sbc_pct_rev, SBC_BANDS, 0),
        score_high(m.earnings_quality, EQ_BANDS, 1.5),
        score_high(m.insider_ownership, INSIDER_BANDS, 2),
        score_high(m.shareholder_yield, YIELD_BANDS, 1.5),
    ])
    return {"I": section_i, "II": section_ii, "III": _section_iii(m, profile), "IV": section_iv}
