from __future__ import annotations

import math
import re

from risk_reward.config import REWARD_SLOTS, RISK_SLOTS
from landing.labels import (
    CATEGORY_LABELS, ERROR_LABELS, EXCLUSION_LABELS, GENERIC_ERROR_LABEL,
    METHOD_LABELS, MOAT_FACTOR_LABELS, RR_FACTOR_LABELS, humanize,
)

# Fallback category weights when the engine did not report renormalized ones.
_DEFAULT_CATEGORY_WEIGHTS = {"I": 0.35, "II": 0.30, "III": 0.15, "IV": 0.20}


def _finite(v):
    """NaN/Inf never reach the boundary (fix round 1, item 5): these are
    pandas-derived ratios and raw yfinance values, and FastAPI would otherwise emit a
    bare `NaN`/`Infinity` literal that `JSON.parse` rejects outright — killing the
    whole page instead of blanking one cell."""
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def _round(v, n=2):
    v = _finite(v)
    return None if v is None else round(v, n)


def _exclusion_label(reason: str | None) -> str | None:
    """excluded_by is a key into the internal exclusion vocabulary, not display copy —
    map it through EXCLUSION_LABELS with a passthrough fallback so an unmapped reason
    degrades to its raw string rather than to None (controller addition 1)."""
    if not reason:
        return None
    return EXCLUSION_LABELS.get(reason, reason)


_ERROR_PREFIX_RE = re.compile(r"^([a-z_]+):\s")


def _public_error(raw: str) -> str:
    """orchestrator.batch._run_one tags a subsystem failure as "prefix: <exception
    text>" — the exception text must never reach a public page. A message with no
    such prefix (the engines' own plain-English decline reasons, e.g. "yfinance data
    unavailable") is already reader-safe and passes through unchanged; a prefixed one
    is replaced outright (never just have its prefix swapped, since the exception text
    after the colon is the leak)."""
    m = _ERROR_PREFIX_RE.match(raw)
    if not m:
        return raw
    return ERROR_LABELS.get(m.group(1), GENERIC_ERROR_LABEL)


def _public_errors(errors: list[str]) -> list[str]:
    out: list[str] = []
    for e in errors or []:
        label = _public_error(e)
        if label not in out:
            out.append(label)
    return out


def _quality(sc: dict | None) -> dict | None:
    if not sc or sc.get("quality_score") is None:
        return None
    bd = sc.get("score_breakdown") or {}
    weights = bd.get("section_weights") or _DEFAULT_CATEGORY_WEIGHTS
    details = sc.get("metric_details") or {}
    categories = []
    for key in ("I", "II", "III", "IV"):
        weight_pct = round(float(weights.get(key, 0.0)) * 100, 2)
        metrics = details.get(key) or []
        # Metrics are averaged inside a category (`_mean`), so each scored metric
        # carries an equal share of the category weight and an excluded one carries
        # none — which is what re-weights the survivors. A FINANCIALS Section III
        # (2 excluded leverage rows, 1 live OCF/CapEx row) falls out of this the same
        # way: the sole survivor picks up the whole category weight.
        active = [m for m in metrics if not m.get("excluded") and m.get("score") is not None]
        share = round(weight_pct / len(active), 2) if active else 0.0
        categories.append({
            "key": key,
            "name": CATEGORY_LABELS[key],
            "weight_pct": weight_pct,
            "score": _round((sc.get("section_scores") or {}).get(key)),
            "metrics": [{
                "label": m.get("label"),
                "raw": _finite(m.get("raw")),
                "score": _round(m.get("score")),
                "weight_pct": 0.0 if (m.get("excluded") or m.get("score") is None) else share,
                "excluded": bool(m.get("excluded")),
                "excluded_by": _exclusion_label(m.get("excluded_by")),
            } for m in metrics],
        })
    return {
        "score": _round(sc.get("quality_score"), 1),
        # The section-weighted composite before any pre-profit blend / unprofitable
        # cap (screener/scoring.py's `breakdown["fundamentals_composite"]`) — nullable,
        # since a name that never reaches `score()`'s composite step has none. This is
        # what `categories` actually rolls up to; `score` above is the published
        # headline (`final`), which can legitimately diverge from it for an
        # operationally-unprofitable name. Exposed so Task 10 can show that gap
        # instead of hiding it.
        "fundamentals_composite": _round(bd.get("fundamentals_composite"), 2),
        "profile_label": humanize(sc.get("sector_profile")),
        "categories": categories,
    }


def _humanize_excluded_pillar(entry: str) -> str:
    """moat/scoring.py's `excluded` list holds entries like "B3 margin durability" —
    the leading token is the same pillar code MOAT_FACTOR_LABELS maps in `factors`.
    Swap it for the label (dropping the redundant trailing description) so the code
    never survives; an entry that doesn't start with a known code passes through as
    already-human text rather than a classifier."""
    code = entry.split(" ", 1)[0] if entry else entry
    return MOAT_FACTOR_LABELS.get(code, entry)


def _moat(sc: dict | None) -> dict | None:
    if not sc or sc.get("moat_score") is None:
        return None
    bd = sc.get("moat_breakdown") or {}
    pillars, maxima = bd.get("pillars") or {}, bd.get("maxima") or {}
    available = sum(maxima.values()) or 100
    factors = []
    for code, points in pillars.items():
        # Controller addition 3: MoatBlock.factors[].max_points is a non-null number
        # on the frontend (Task 7). moat/scoring.py always gives a pillar that exists
        # a matching maximum, but if one is ever missing, omit the factor rather than
        # emit a null max_points.
        max_points = maxima.get(code)
        if max_points is None:
            continue
        factors.append({
            "label": MOAT_FACTOR_LABELS.get(code, humanize(code)),
            "points": _round(points),
            "max_points": max_points,
            "weight_pct": round(max_points / available * 100, 2),
        })
    return {
        "score": _round(sc.get("moat_score"), 1),
        "gated": bool(bd.get("gated")),
        # moat/scoring.py's `excluded` entries are raw pillar codes with a trailing
        # description ("B3 margin durability") — map the code through
        # MOAT_FACTOR_LABELS so the same pillar isn't shown humanized in `factors`
        # but raw here (fix round 1, item 3).
        "excluded": [_humanize_excluded_pillar(x) for x in (bd.get("excluded") or [])],
        "factors": factors,
    }


def _fair_value(res: dict) -> dict | None:
    if res.get("fair_value") is None:
        return None
    bd = res.get("fair_value_breakdown") or {}
    methods = [{
        "label": METHOD_LABELS.get(mid, humanize(mid)),
        "value": _round(leg.get("fair_value")),
        "weight_pct": round(float(leg.get("weight", 0.0)) * 100, 2),
        "contribution": _round(float(leg.get("weight", 0.0)) * float(leg.get("fair_value") or 0.0)),
    } for mid, leg in bd.items()]
    return {
        # One exact blended number — never a range (spec section 8 rule 7).
        "value": _round(res.get("fair_value")),
        "gap_pct": _round(res.get("price_vs_fair_value_pct")),
        "type_label": humanize(res.get("stock_type")),
        "methods": methods,
    }


def _reward_risk(rr: dict | None) -> dict | None:
    if not rr or rr.get("ratio") is None:
        return None
    scores = rr.get("metric_scores") or {}

    def factors(slots):
        # MetricScore.weight is the pre-renormalization slot weight: a dropped slot
        # still carries its full non-zero weight (risk_reward/scoring.py's
        # build_metric_scores), and renormalization happens only at aggregation
        # (_axis_average) — never written back onto the metric. Publishing that
        # nominal weight directly would render a dropped, zero-contribution factor
        # with a live-looking weight, and the axis wouldn't sum to 100 even with no
        # drops (analyst_upside's weight floats in [0.08, 0.18]). Mirror `_quality`
        # instead: total only the active (non-dropped, scored) slots' weights and
        # give each of THOSE its true share; every dropped/unscored slot gets 0.0.
        present = [(slot, scores[slot]) for slot in slots if scores.get(slot)]
        active_total = sum(
            float(ms.get("weight", 0.0)) for _, ms in present
            if not ms.get("dropped") and ms.get("score") is not None
        )
        out = []
        for slot, ms in present:
            is_active = not ms.get("dropped") and ms.get("score") is not None
            weight_pct = (round(float(ms.get("weight", 0.0)) / active_total * 100, 2)
                         if is_active and active_total > 0 else 0.0)
            out.append({
                "label": RR_FACTOR_LABELS.get(slot, humanize(slot)),
                "raw": _finite(ms.get("raw")),
                "score": _round(ms.get("score")),
                "weight_pct": weight_pct,
                "dropped": bool(ms.get("dropped")),
            })
        return out

    return {
        "ratio": _round(rr.get("ratio"), 2),
        "tier": rr.get("tier"),
        "reward_score": _round(rr.get("reward_score")),
        "risk_score": _round(rr.get("risk_score")),
        "reward": factors(REWARD_SLOTS),
        "risk": factors(RISK_SLOTS),
    }


def _calibrations(res: dict, sc: dict | None) -> list[str]:
    """Only the calibrations that actually fired, by name — reader-facing copy, never
    the raw internal reason string (controller addition 1)."""
    fired: list[str] = []

    def _add(reason: str) -> None:
        label = _exclusion_label(reason)
        if label and label not in fired:
            fired.append(label)

    bd = (sc or {}).get("score_breakdown") or {}
    if bd.get("sector_adjustment"):
        _add("Financials basis")
    if bd.get("capex_adjustment"):
        _add("Heavy-capex FCF exclusion")
    for cat in (sc or {}).get("metric_details", {}).values():
        for m in cat or []:
            name = m.get("excluded_by")
            if name:
                _add(name)
    # The two most consequential recalibrations otherwise fire invisibly: an
    # acquisition-distorted ROIC re-basing (no excluded_by anywhere — it substitutes
    # the metric rather than dropping it) and the pre-profit growth blend / cap that
    # can pull `quality.score` away from `quality.fundamentals_composite`.
    if bd.get("roic_adjustment"):
        _add("ROIC on tangible capital")
    pre_profit = bd.get("pre_profit") or {}
    if pre_profit.get("applied"):
        _add("Pre-profit growth blend")
    if pre_profit.get("capped"):
        _add("Unprofitable cap")
    if ((sc or {}).get("moat_breakdown") or {}).get("gated"):
        fired.append("Economic-profit gate")
    return fired


def build_ticker_payload(result: dict) -> dict:
    """Map one orchestrator result into the shape the landing page renders. Every
    headline the grid shows is present here alongside the factors it was derived
    from, so the grid and the breakdown cannot disagree.

    Must survive the synthetic failure dict orchestrator.batch produces for a ticker
    whose engine run raised (just {"ticker", "errors", "status": "failed"}) — every
    field below is read with .get(), so a missing screener/risk_reward/fair_value
    degrades to a blank assessment rather than a crash."""
    sc = result.get("screener")
    rr = result.get("risk_reward")
    return {
        "ticker": result.get("ticker"),
        "company_name": result.get("company_name"),
        "price": _round(result.get("current_price")),
        "quality": _quality(sc),
        "moat": _moat(sc),
        "fair_value": _fair_value(result),
        "reward_risk": _reward_risk(rr),
        "calibrations": _calibrations(result, sc),
        "errors": _public_errors(result.get("errors")),
    }
