from __future__ import annotations

from collections.abc import Callable

from risk_reward.config import CONFIG, REWARD_SLOTS, RISK_SLOTS, RiskRewardConfig
from risk_reward.models import RiskRewardInputs, MetricScore


def score_metric(raw, a5: float, a3: float, a1: float) -> float | None:
    """Map a raw metric value to a score in [1, 5] by piecewise-linear interpolation
    across the breakpoints [(a1, 1), (a3, 3), (a5, 5)]. Direction-agnostic: works
    whether higher raw is better (reward) or worse (danger). Values beyond the
    extreme anchors saturate. None/NaN/non-numeric -> None (metric is dropped)."""
    if raw is None:
        return None
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return None
    if x != x:  # NaN
        return None
    pts = sorted([(float(a1), 1.0), (float(a3), 3.0), (float(a5), 5.0)])
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (x0, s0), (x1, s1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return s1
            return s0 + (s1 - s0) * (x - x0) / (x1 - x0)
    return None  # unreachable given the bounds checks above


def _pos(v):
    """Return v as float if it is a positive finite number, else None."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f == f and f > 0 else None


def _ratio(num, den):
    d = _pos(den)
    return (num / d) if (d is not None and num is not None) else None


SOURCE_EXTRACTORS: dict[str, Callable[[RiskRewardInputs], float | None]] = {
    # reward
    "peg": lambda i: _pos(i.info.get("pegRatio")) or _pos(i.info.get("trailingPegRatio")),
    "earnings_yield": lambda i: _ratio(1.0, i.info.get("forwardPE")),
    "ps_yield": lambda i: _ratio(1.0, i.info.get("priceToSalesTrailing12Months")),
    "revenue_growth": lambda i: i.info.get("revenueGrowth"),
    "earnings_growth": lambda i: i.info.get("earningsGrowth"),
    "roe": lambda i: i.info.get("returnOnEquity"),
    "roa": lambda i: i.info.get("returnOnAssets"),
    "analyst_upside": lambda i: _ratio((i.info.get("targetMeanPrice") or 0) - (i.price or 0), i.price)
                                if i.info.get("targetMeanPrice") and i.price else None,
    "discount": lambda i: ((i.high_52w - i.price) / i.high_52w)
                          if (i.high_52w and i.price and i.high_52w > 0) else None,
    "rsi": lambda i: i.rsi,
    # risk
    "debt_to_equity": lambda i: i.info.get("debtToEquity"),
    "net_debt_ebitda": lambda i: _net_debt_ebitda(i),
    "operating_margin": lambda i: i.info.get("operatingMargins"),
    "profit_margin": lambda i: i.info.get("profitMargins"),
    "current_ratio": lambda i: i.info.get("currentRatio"),
    "quick_ratio": lambda i: i.info.get("quickRatio"),
    "volatility": lambda i: i.volatility,
    "trend": lambda i: ((i.price - i.ma_200) / i.ma_200)
                       if (i.price and i.ma_200 and i.ma_200 > 0) else None,
    "beta": lambda i: i.info.get("beta"),
    # statement-annual variants: gap-guard-only, never part of a normal fallback
    # chain (see [[iren-rr-stmt-gap-guard]] / _stmt_gap_override below).
    "revenue_growth_stmt": lambda i: i.revenue_growth_stmt,
    "operating_margin_stmt": lambda i: i.operating_margin_stmt,
}

# slot -> (statement source key, favor_high). growth: override only when the
# statement score is HIGHER than info's (info understates growth). burn: override
# only when the statement score is LOWER than info's (info overstates risk). Both
# directions are self-limiting -- see CONFIG.stmt_gap_min's docstring.
_STMT_GAP_GUARDS: dict[str, tuple[str, bool]] = {
    "growth": ("revenue_growth_stmt", True),
    "burn": ("operating_margin_stmt", False),
}


def _stmt_gap_override(inp: RiskRewardInputs, chosen: MetricScore, slot: str,
                       cfg: RiskRewardConfig) -> MetricScore:
    """Corroboration guard (see [[iren-rr-stmt-gap-guard]]): override `chosen`
    (the info-chain-resolved score) with the statement-sourced score only when the
    statement reads MATERIALLY more favorable, by >= cfg.stmt_gap_min points on the
    shared 1-5 scale. Directional per slot (growth: statement higher; burn: info
    higher) so a name where the statement reads WORSE than info (a real business
    divergence, not a feed artifact -- e.g. CORZ, APLD) is structurally excluded,
    with no per-name carve-out. No-op when the statement input is unavailable."""
    guard = _STMT_GAP_GUARDS.get(slot)
    if guard is None:
        return chosen
    stmt_source, favor_high = guard
    raw = SOURCE_EXTRACTORS[stmt_source](inp)
    stmt_score = score_metric(raw, *cfg.anchors[stmt_source])
    if stmt_score is None:
        return chosen
    gap = (stmt_score - chosen.score) if favor_high else (chosen.score - stmt_score)
    if gap >= cfg.stmt_gap_min:
        return MetricScore(raw=float(raw), source=stmt_source, score=stmt_score,
                           weight=chosen.weight, dropped=False)
    return chosen


def _net_debt_ebitda(i: RiskRewardInputs):
    ebitda = i.info.get("ebitda")
    if not ebitda or ebitda <= 0:
        return None
    total_debt = i.info.get("totalDebt") or 0
    total_cash = i.info.get("totalCash") or 0
    return (total_debt - total_cash) / ebitda


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _analyst_confidence(info: dict, cfg: RiskRewardConfig) -> float:
    """Trust in the analyst-upside signal, in [0, 1]: the weaker (min) of analyst
    COVERAGE and AGREEMENT. Magnitude of the upside is NOT an input (it already lives
    in the score). Any missing input collapses its factor to 0 -> the weight floor."""
    n = _pos(info.get("numberOfAnalystOpinions"))
    coverage = (_clamp01((n - cfg.analyst_coverage_lo)
                         / (cfg.analyst_coverage_hi - cfg.analyst_coverage_lo))
                if n is not None else 0.0)
    mean = _pos(info.get("targetMeanPrice"))
    hi = _pos(info.get("targetHighPrice"))
    lo = _pos(info.get("targetLowPrice"))
    if mean is not None and hi is not None and lo is not None and hi >= lo:
        spread = (hi - lo) / mean
        agreement = _clamp01((cfg.analyst_spread_hi - spread)
                             / (cfg.analyst_spread_hi - cfg.analyst_spread_lo))
    else:
        agreement = 0.0
    return min(coverage, agreement)


def _analyst_weight(info: dict, cfg: RiskRewardConfig) -> float:
    return cfg.analyst_weight_floor + cfg.analyst_weight_span * _analyst_confidence(info, cfg)


def build_metric_scores(inp: RiskRewardInputs,
                        cfg: RiskRewardConfig = CONFIG) -> dict[str, MetricScore]:
    out: dict[str, MetricScore] = {}
    for slot in REWARD_SLOTS + RISK_SLOTS:
        # Analyst upside carries a confidence-scaled weight (spec §4.1†); every other
        # slot uses its static config weight. The weight applies whether or not the
        # metric resolves — a dropped slot is excluded from Task 6's renormalization.
        weight = (_analyst_weight(inp.info, cfg) if slot == "analyst_upside"
                  else cfg.weights[slot])
        chosen = None
        for src in cfg.sources[slot]:
            raw = SOURCE_EXTRACTORS[src](inp)
            score = score_metric(raw, *cfg.anchors[src])
            if score is not None:
                chosen = MetricScore(raw=float(raw), source=src, score=score,
                                     weight=weight, dropped=False)
                break
        if chosen is not None:
            chosen = _stmt_gap_override(inp, chosen, slot, cfg)
        out[slot] = chosen or MetricScore(raw=None, source=None, score=None,
                                          weight=weight, dropped=True)
    return out


from dataclasses import dataclass


@dataclass
class Aggregation:
    reward: float | None
    risk: float | None
    ratio: float | None
    tier: str | None
    insight: str | None
    status: str


def _axis_average(scores, slots) -> tuple[float | None, int]:
    """Weighted average over the active (non-dropped) metrics in `slots`, with the
    active weights renormalized to sum to 1. Returns (average, active_count)."""
    active = [scores[s] for s in slots if not scores[s].dropped and scores[s].score is not None]
    total_w = sum(ms.weight for ms in active)
    if not active or total_w <= 0:
        return None, len(active)
    avg = sum(ms.score * ms.weight for ms in active) / total_w
    return avg, len(active)


def tier_for(ratio: float, cfg: RiskRewardConfig = CONFIG) -> str:
    for floor, label in cfg.tiers:
        if ratio >= floor:
            return label
    return cfg.tiers[-1][1]


def _insight(tier: str, reward: float, risk: float) -> str:
    lean = "reward outweighs risk" if reward >= risk else "risk outweighs reward"
    return f"{tier}: {lean} (reward {reward:.1f} vs risk {risk:.1f} on a 1-5 scale)."


def aggregate(scores: dict[str, MetricScore],
              cfg: RiskRewardConfig = CONFIG) -> Aggregation:
    reward, n_reward = _axis_average(scores, REWARD_SLOTS)
    risk, n_risk = _axis_average(scores, RISK_SLOTS)
    if n_reward < cfg.min_reward or n_risk < cfg.min_risk or reward is None or risk is None:
        return Aggregation(reward=reward, risk=risk, ratio=None, tier=None,
                           insight=None, status="insufficient_data")
    lo, hi = cfg.ratio_clamp
    ratio = max(lo, min(hi, reward / risk))
    tier = tier_for(ratio, cfg)
    return Aggregation(reward=reward, risk=risk, ratio=ratio, tier=tier,
                       insight=_insight(tier, reward, risk), status="completed")
