"""Moat Score — pure durability-of-economic-profit. A 40/50/10 model over the
series ScreenerMetrics already carries. Numeric only (0-100); no rating labels.
See docs/superpowers/specs/2026-08-24-moat-score-design.md."""
from __future__ import annotations
from screener.models import ScreenerMetrics
from screener.scoring import (
    score_high, score_low, _acquisition_distorted, _heavy_capex_distortion,
)
from moat.metrics import mean, pstdev, persistence_fraction, coef_of_variation

# --- tunables (swept in the calibration task) -------------------------------
FINANCIAL_COE_PCT = 8.5      # banks' hurdle: cost of equity, percent
MOAT_GATE_CEIL = 35.0        # no-durable-excess names capped here
MOAT_MIN_YEARS = 3           # min observations in the return series
MOAT_MIN_PILLARS = 3         # min scored pillar-metrics, else None

# --- bands ------------------------------------------------------------------
# A1 ROIC level, 5y avg (max 20) — score_high on percent
A1_ROIC_BANDS = [(25, 20), (20, 17), (15, 13), (12, 8), (8, 4)]
# A2 economic spread, ROIC-WACC blend (max 20) — score_high on pp
A2_SPREAD_BANDS = [(15, 20), (10, 16), (5, 11), (0, 5)]


def _return_axis(m: ScreenerMetrics, profile: str) -> dict:
    """Resolve the return axis: plain ROIC vs tangible (ex-goodwill) ROIC vs, for
    financials, ROTE vs cost of equity. Returns level / hurdle / series / spot &
    5y spreads, all percent/pp."""
    if profile == "FINANCIALS":
        level = m.rote_5y_avg
        hurdle = FINANCIAL_COE_PCT
        series = m.rote_series
        spot = (m.rote - FINANCIAL_COE_PCT) if m.rote is not None else None
        five = (m.rote_5y_avg - FINANCIAL_COE_PCT) if m.rote_5y_avg is not None else None
        return {"level": level, "hurdle": hurdle, "series": series,
                "spot": spot, "five": five, "variant": "FINANCIAL_ROTE"}
    if _acquisition_distorted(m):
        level = m.roic_5y_ex_goodwill if m.roic_5y_ex_goodwill is not None else m.roic_5y_avg
        series = m.roic_series_ex_goodwill or m.roic_series
        spot = ((m.roic_ex_goodwill - m.wacc) if (m.roic_ex_goodwill is not None
                and m.wacc is not None) else m.roic_wacc_spread)
        five = (level - m.wacc) if (level is not None and m.wacc is not None) else None
        return {"level": level, "hurdle": m.wacc, "series": series,
                "spot": spot, "five": five, "variant": "TANGIBLE_ROIC"}
    level = m.roic_5y_avg
    series = m.roic_series
    spot = m.roic_wacc_spread
    five = (m.roic_5y_avg - m.wacc) if (m.roic_5y_avg is not None
            and m.wacc is not None) else None
    return {"level": level, "hurdle": m.wacc, "series": series,
            "spot": spot, "five": five, "variant": "ROIC"}


def _spread_blend(spot: float | None, five: float | None) -> float | None:
    """0.5*spot + 0.5*5y; drops a missing leg and uses the other (spec: WACC-
    dependent legs dropped and renormalized)."""
    parts = [x for x in (spot, five) if x is not None]
    return sum(parts) / len(parts) if parts else None


def score(m: ScreenerMetrics, profile: str) -> tuple[float | None, dict]:
    axis = _return_axis(m, profile)
    pillars: dict[str, float] = {}   # name -> earned points
    maxima: dict[str, float] = {}    # name -> max points

    def add(name: str, earned: float | None, cap: float) -> None:
        if earned is not None:
            pillars[name] = earned
            maxima[name] = cap

    # A1 — ROIC/ROTE level
    add("A1", score_high(axis["level"], A1_ROIC_BANDS, 0.0), 20)
    # A2 — economic spread blend
    add("A2", score_high(_spread_blend(axis["spot"], axis["five"]), A2_SPREAD_BANDS, 0.0), 20)

    # (Durability B1/B2/B3 and cash-backing C1 are added in Tasks 4-6.)

    available = sum(maxima.values())
    breakdown: dict = {
        "variant": axis["variant"],
        "pillars": dict(pillars),
        "maxima": dict(maxima),
        "earned": round(sum(pillars.values()), 2),
        "available": available,
        "gated": False,
    }
    series_len = len(axis["series"] or [])
    if series_len < MOAT_MIN_YEARS or len(pillars) < MOAT_MIN_PILLARS or available <= 0:
        breakdown["moat_score"] = None
        return None, breakdown

    moat = 100.0 * sum(pillars.values()) / available
    breakdown["moat_score"] = round(moat, 1)
    return round(moat, 1), breakdown
