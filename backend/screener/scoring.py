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


FCF_EBITDA_FLOOR = 0.15


def _heavy_capex_distortion(m: ScreenerMetrics) -> bool:
    """Operationally profitable, healthy EBITDA, but trailing FCF is a negligible
    (or negative) fraction of EBITDA because capex is eating it (e.g. AMZN's AWS/AI
    data-centre build-out). The FCF-derived metrics are then unrepresentative and
    excluded from scoring — the same principle as the FINANCIALS FCF/OCF exclusion,
    and mirroring the Fair-Value pipeline's capex-distorted DCF reroute.

    An operating loss is NOT treated here: that is a genuine pre-profit burn, which
    the pre-profit growth/runway branch handles separately."""
    if m.ebitda is None or m.ebitda <= 0 or m.fcf is None:
        return False
    if m.op_margin is not None and m.op_margin < 0:
        return False
    return m.fcf < FCF_EBITDA_FLOOR * m.ebitda


def _section_iii(m: ScreenerMetrics, profile: str, heavy_capex: bool = False) -> float | None:
    p = PROFILES[profile]
    nde = leverage_score(m.net_debt_ebitda, p["P"])
    ndf = leverage_score(m.net_debt_fcf, p["Q"])
    ocf = score_high(m.ocf_capex, OCF_CAPEX_BANDS, 0)
    if heavy_capex:
        # Capex is deliberately consuming FCF, so the FCF-derived coverage/leverage
        # metrics are unrepresentative -> judge the balance sheet on EBITDA leverage.
        ndf = None
        ocf = None
    # Balance-Sheet Dual-Check: FCF-based debt looks far worse than EBITDA-based
    # AND EBITDA leverage is healthy (<2.5) -> treat ND/FCF as capex-cycle noise.
    elif (nde is not None and ndf is not None and m.net_debt_ebitda is not None
            and m.net_debt_ebitda < 2.5 and ndf < nde - 2):
        ndf = None  # drop the noisy metric
    return _mean([nde, ndf, ocf])


def section_scores(m: ScreenerMetrics, profile: str) -> dict[str, float | None]:
    # For a lender/insurer, free-cash-flow and operating-cash-flow derived metrics are
    # structurally distorted (loan originations dominate cash flows), so they are
    # excluded from scoring — the same principle already applied to the Section III
    # leverage metrics (zero weight for FINANCIALS). A heavy-capex reinvestor whose
    # capex eats its FCF gets the same treatment for the FCF-derived metrics.
    is_fin = profile == "FINANCIALS"
    heavy_capex = _heavy_capex_distortion(m)
    exclude_fcf = is_fin or heavy_capex
    section_i = _mean([
        score_high(m.revenue_cagr_3y, GROWTH_BANDS, 0),
        score_high(m.eps_cagr_3y, GROWTH_BANDS, 0),
        None if exclude_fcf else score_high(m.fcf_cagr_3y, FCF_CAGR_BANDS, 1),
        None if exclude_fcf else score_high(m.fcf_margin, FCF_MARGIN_BANDS, 0),
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
        None if is_fin else score_high(m.earnings_quality, EQ_BANDS, 1.5),
        score_high(m.insider_ownership, INSIDER_BANDS, 2),
        score_high(m.shareholder_yield, YIELD_BANDS, 1.5),
    ])
    return {"I": section_i, "II": section_ii,
            "III": _section_iii(m, profile, heavy_capex), "IV": section_iv}


MIN_SCORED_SUBSCORES = 6


def _count_subscores(m: ScreenerMetrics, profile: str) -> int:
    p = PROFILES[profile]
    candidates = [
        m.revenue_cagr_3y, m.eps_cagr_3y, m.fcf_cagr_3y, m.fcf_margin,
        m.op_margin, m.op_margin_trajectory, m.gross_margin,
        m.roic_ttm, m.roic_5y_avg, m.roic_wacc_spread, m.rote,
        m.ocf_capex,
        m.shares_cagr_3y, m.sbc_pct_rev, m.earnings_quality,
        m.insider_ownership, m.shareholder_yield,
    ]
    n = sum(1 for c in candidates if c is not None)
    if p["P"] is not None:
        n += sum(1 for c in (m.net_debt_ebitda, m.net_debt_fcf) if c is not None)
    return n


RULE_OF_40_GROWTH_CAP = 100.0


def _rule_of_40(m: ScreenerMetrics) -> float | None:
    g = m.revenue_growth if m.revenue_growth is not None else m.revenue_cagr_3y
    # Use an operating (profitability) margin, not FCF margin: a company in a heavy
    # investment phase drives FCF margin far below -100% (capex >> nascent revenue),
    # which would collapse the Rule of 40 and mislabel an elite growth story as a
    # failure. Fall back to FCF margin only when operating margin is unavailable.
    margin = m.op_margin if m.op_margin is not None else m.fcf_margin
    if g is None or margin is None:
        return None
    # Cap the growth contribution so a tiny-revenue-base hyper-growth rate can't
    # dominate the metric either.
    return min(g, RULE_OF_40_GROWTH_CAP) + margin


def _runway_months(m: ScreenerMetrics) -> float | None:
    if m.fcf is None or m.fcf >= 0:
        return float("inf")
    if m.total_cash is None:
        return None
    monthly_burn = abs(m.fcf) / 12.0
    return m.total_cash / monthly_burn if monthly_burn > 0 else float("inf")


# Unprofitable Cap Rule tunables
UNPROFITABLE_CEIL = 8.0          # any negative NI/FCF name is capped here
PP_BLEND_WEIGHT = 0.4            # weight of the pre-profit growth score vs sections
IMMINENT_RUNWAY_MONTHS = 12.0    # below this, liquidity risk hard-caps the score
IMMINENT_CEIL = 5.0
R40_BANDS = [(60, 10), (40, 8.5), (20, 6), (0, 4)]         # score_high, below -> 2
RUNWAY_BANDS = [(36, 10), (24, 8), (18, 6), (12, 4)]       # months, below -> 2


def _pre_profit_growth_score(r40: float | None, runway: float | None) -> float | None:
    """Score a pre-profit company on Rule of 40 + Cash Runway (1..10), the mean of
    whichever sub-scores are available."""
    parts: list[float | None] = []
    if r40 is not None:
        parts.append(score_high(r40, R40_BANDS, 2))
    if runway is not None:
        parts.append(10.0 if runway == float("inf") else score_high(runway, RUNWAY_BANDS, 2))
    return _mean(parts)


def score(m: ScreenerMetrics, sector: str | None):
    """Return (quality_score, section_scores, profile, breakdown). `breakdown`
    explains how the headline was derived — the section composite and, for
    unprofitable names, the pre-profit growth blend that adjusts it."""
    profile = apply_nudge(base_profile(sector), m)
    if _count_subscores(m, profile) < MIN_SCORED_SUBSCORES:
        return None, {}, profile, {}

    sections = section_scores(m, profile)
    weights = dict(zip(("I", "II", "III", "IV"), PROFILES[profile]["w"]))

    # renormalize weights over sections that produced a score
    active = {k: weights[k] for k in sections if sections[k] is not None and weights[k] > 0}
    total_w = sum(active.values())
    if total_w <= 0:
        return None, sections, profile, {}
    composite = sum(sections[k] * (w / total_w) for k, w in active.items())

    breakdown: dict = {
        "fundamentals_composite": round(composite, 2),
        "section_weights": {k: round(w / total_w, 3) for k, w in active.items()},
        "pre_profit": None,
        "final": None,
    }
    if profile == "FINANCIALS":
        breakdown["sector_adjustment"] = {
            "profile": "FINANCIALS",
            "excluded": ["FCF Margin", "FCF CAGR", "Earnings Quality (OCF/NI)",
                         "Leverage (Net Debt / EBITDA & FCF)"],
            "note": ("Free-cash-flow, operating-cash-flow and leverage metrics are "
                     "excluded — structurally distorted for lenders."),
        }
    elif _heavy_capex_distortion(m):
        breakdown["capex_adjustment"] = {
            "profile": profile,
            "excluded": ["FCF Margin", "FCF CAGR", "OCF / CapEx", "Net Debt / FCF"],
            "note": ("Trailing free cash flow is a negligible share of EBITDA because "
                     "capex is heavily reinvested (e.g. data-centre build-out), so the "
                     "FCF-derived metrics are excluded — deliberate reinvestment isn't "
                     "scored as balance-sheet weakness."),
        }

    final = composite
    # Unprofitable Cap Rule (Gem): a company with negative net income OR negative FCF
    # is capped at 8.0.
    unprofitable = ((m.net_income is not None and m.net_income < 0)
                    or (m.fcf is not None and m.fcf < 0))
    # Pre-profit growth branch: only when the company is *operationally* unprofitable
    # (operating loss). A profitable company with negative FCF — a lender's loan-book
    # growth, or a heavy capex build — is investing, not burning toward insolvency, so
    # it is NOT routed through the runway/blend logic (which would misread the loan
    # outflows as an imminent cash-out).
    operating_loss = ((m.op_margin is not None and m.op_margin < 0)
                      or (m.op_margin is None and m.net_income is not None and m.net_income < 0))
    if operating_loss:
        r40 = _rule_of_40(m)
        runway = _runway_months(m)
        growth = _pre_profit_growth_score(r40, runway)
        capped = False
        if growth is not None:
            final = PP_BLEND_WEIGHT * growth + (1 - PP_BLEND_WEIGHT) * composite
        if runway is not None and runway < IMMINENT_RUNWAY_MONTHS:
            final, capped = min(final, IMMINENT_CEIL), True
        breakdown["pre_profit"] = {
            "applied": growth is not None,
            "rule_of_40": round(r40, 1) if r40 is not None else None,
            "runway_months": (None if runway is None else
                              ("inf" if runway == float("inf") else round(runway, 1))),
            "growth_score": round(growth, 2) if growth is not None else None,
            "blend_weight": PP_BLEND_WEIGHT,
            "capped": capped,
        }
    if unprofitable and final > UNPROFITABLE_CEIL:
        final = UNPROFITABLE_CEIL
        if breakdown["pre_profit"]:
            breakdown["pre_profit"]["capped"] = True

    final = max(1.0, min(10.0, final))
    breakdown["final"] = round(final, 1)
    return round(final, 1), sections, profile, breakdown
