from __future__ import annotations

from risk_reward.config import CONFIG, REWARD_SLOTS, RISK_SLOTS
from landing.labels import (
    CATEGORY_LABELS, EXCLUSION_LABELS, METHOD_LABELS, MOAT_FACTOR_LABELS,
    RR_FACTOR_LABELS, humanize,
)

# Fallback category weights when the engine did not report renormalized ones.
_DEFAULT_CATEGORY_WEIGHTS = {"I": 0.35, "II": 0.30, "III": 0.15, "IV": 0.20}


def _round(v, n=2):
    return None if v is None else round(v, n)


def _exclusion_label(reason: str | None) -> str | None:
    """excluded_by is a key into the internal exclusion vocabulary, not display copy —
    map it through EXCLUSION_LABELS with a passthrough fallback so an unmapped reason
    degrades to its raw string rather than to None (controller addition 1)."""
    if not reason:
        return None
    return EXCLUSION_LABELS.get(reason, reason)


def _quality(sc: dict | None) -> dict | None:
    if not sc or sc.get("quality_score") is None:
        return None
    weights = (sc.get("score_breakdown") or {}).get("section_weights") \
        or _DEFAULT_CATEGORY_WEIGHTS
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
                "raw": m.get("raw"),
                "score": _round(m.get("score")),
                "weight_pct": 0.0 if (m.get("excluded") or m.get("score") is None) else share,
                "excluded": bool(m.get("excluded")),
                "excluded_by": _exclusion_label(m.get("excluded_by")),
            } for m in metrics],
        })
    return {
        "score": _round(sc.get("quality_score"), 1),
        "profile_label": humanize(sc.get("sector_profile")),
        "categories": categories,
    }


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
            # Left unrounded: a factor's weight is its exact share of the available
            # points (e.g. 20/65), and rounding to 2dp here would drift the sum of a
            # moat's factor weights away from 100%.
            "weight_pct": max_points / available * 100,
        })
    return {
        "score": _round(sc.get("moat_score"), 1),
        "gated": bool(bd.get("gated")),
        "excluded": bd.get("excluded") or [],
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
        out = []
        for slot in slots:
            ms = scores.get(slot)
            if not ms:
                continue
            out.append({
                "label": RR_FACTOR_LABELS.get(slot, humanize(slot)),
                "raw": ms.get("raw"),
                "score": _round(ms.get("score")),
                "weight_pct": round(float(ms.get("weight", CONFIG.weights.get(slot, 0.0))) * 100, 2),
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
        "errors": result.get("errors") or [],
    }
