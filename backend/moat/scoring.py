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
# B2 consistency (max 10) — score_low on coefficient of variation
B2_COV_BANDS = [(0.10, 10), (0.20, 8), (0.35, 5), (0.50, 3)]
# B3 margin durability (max 15) — three 0-10 components, mean scaled to 15
GROSS_STDEV_BANDS = [(1.0, 10), (2.0, 8), (4.0, 5), (7.0, 3)]   # score_low, pp
OP_STDEV_BANDS = [(1.0, 10), (2.0, 8), (4.0, 5), (7.0, 3)]      # score_low, pp
MARGIN_TRAJ_BANDS = [(2, 10), (0, 7), (-2, 4)]                  # score_high, pp


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


def _margin_durability(m: ScreenerMetrics) -> float | None:
    """Mean of up to three 0-10 components (gross stability, op stability,
    non-erosion), scaled to 15. Emphasis on stability + non-erosion, not level."""
    comps: list[float] = []
    if len(m.gross_margin_series) >= 2:
        comps.append(score_low(pstdev(m.gross_margin_series), GROSS_STDEV_BANDS, 0.0))
    if len(m.op_margin_series) >= 2:
        comps.append(score_low(pstdev(m.op_margin_series), OP_STDEV_BANDS, 0.0))
    traj = m.gross_margin_trajectory if m.gross_margin_trajectory is not None \
        else m.op_margin_trajectory
    if traj is not None:
        comps.append(score_high(traj, MARGIN_TRAJ_BANDS, 0.0))
    avg = mean(comps)
    return None if avg is None else 15.0 * avg / 10.0


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

    # B1 — persistence: fraction of years the business out-earned its hurdle
    frac = persistence_fraction(axis["series"], axis["hurdle"])
    add("B1", (25.0 * frac) if frac is not None else None, 25)
    # B2 — consistency: low variability of the return series
    add("B2", score_low(coef_of_variation(axis["series"]), B2_COV_BANDS, 0.0), 10)
    # B3 — margin durability
    add("B3", _margin_durability(m), 15)

    # (Cash-backing C1 is added in Task 6.)

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
    level, hurdle = axis["level"], axis["hurdle"]
    if level is not None and hurdle is not None and level <= hurdle:
        moat = min(moat, MOAT_GATE_CEIL)
        breakdown["gated"] = True
    breakdown["moat_score"] = round(moat, 1)
    return round(moat, 1), breakdown
