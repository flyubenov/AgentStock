from __future__ import annotations
from valuation.classifier import classify
from valuation import models as m

EBITDA_MARGIN_FLOOR = 0.08
CAPEX_CFO_GATE = 0.50

_SINGLE_VALUE_FN = {"pb": m.calc_pb, "sotp": m.calc_sotp, "nav": m.calc_nav}
_SCENARIO_FN = {
    "fcfe": m.calc_fcfe,
    "ev_ebitda": m.calc_ev_ebitda,
    "ev_sales": m.calc_ev_sales,
    "pe": m.calc_pe,
    "ddm": m.calc_ddm,
    "rim": m.calc_rim,
}


def build_scenarios(fin: dict) -> dict:
    """Per-stock capped growth scenarios (spec decision #1)."""
    raw = fin.get("earnings_growth") or fin.get("revenue_growth") or 0.07
    base = max(0.02, min(float(raw), 0.20))
    return {
        "optimistic": min(base + 0.05, 0.25),
        "realistic": base,
        "pessimistic": max(base - 0.04, 0.02),
    }


def pick_ev_multiple(weights: dict, fin: dict) -> dict:
    """Decision #4: when a type weights BOTH EV multiples, keep one and fold the
    loser's weight into the winner. Use EV/Sales when EBITDA is null/<=0 or the
    EBITDA margin is below the floor; otherwise EV/EBITDA."""
    w = dict(weights)
    if w.get("ev_ebitda", 0) > 0 and w.get("ev_sales", 0) > 0:
        ebitda = fin.get("ebitda_ttm")
        revenue = fin.get("revenue_ttm")
        margin = (ebitda / revenue) if (ebitda is not None and revenue) else None
        use_sales = (
            ebitda is None or ebitda <= 0
            or margin is None or margin < EBITDA_MARGIN_FLOOR
        )
        if use_sales:
            w["ev_sales"] = w["ev_sales"] + w["ev_ebitda"]
            w["ev_ebitda"] = 0.0
        else:
            w["ev_ebitda"] = w["ev_ebitda"] + w["ev_sales"]
            w["ev_sales"] = 0.0
    return w


def dcf_cashflow_base(fin: dict) -> float | None:
    """Decision #6: use CFO instead of FCF for the DCF base when capex is huge."""
    fcf = fin.get("fcf_ttm")
    cfo = fin.get("operating_cashflow")
    if cfo is not None and fcf is not None and cfo > 0:
        capex = cfo - fcf
        if capex / cfo > CAPEX_CFO_GATE:
            return cfo
    return fcf


def evaluate(fin: dict) -> dict:
    """Pure valuation pipeline. Returns a result dict (no IO, no timestamps)."""
    classification = classify(fin)
    stock_type = classification["stock_type"]
    weights = {mid: classification["method_weights"][mid]["weight"] for mid in m.ALL_METHODS}
    weights = pick_ev_multiple(weights, fin)
    growth = build_scenarios(fin)
    cf_base = dcf_cashflow_base(fin)

    results: dict[str, dict] = {}
    for mid in m.ALL_METHODS:
        weight = weights.get(mid, 0.0)
        if weight <= 0:
            continue
        if mid == "dcf":
            r = m.calc_dcf(fin, growth, cashflow_base=cf_base)
        elif mid in _SCENARIO_FN:
            r = _SCENARIO_FN[mid](fin, growth)
        else:
            r = _SINGLE_VALUE_FN[mid](fin)
        r["weight"] = weight
        if r["fair_value"] is not None:
            results[mid] = r

    company_name = fin.get("company_name")
    current_price = fin.get("current_price")
    ticker = fin.get("ticker") or ""

    if not results:
        return {
            "ticker": ticker, "company_name": company_name, "current_price": current_price,
            "last_evaluated": None, "stock_type": stock_type, "fair_value": None,
            "price_vs_fair_value_pct": None, "fair_value_breakdown": {},
            "status": "failed", "errors": ["insufficient data for any model"],
        }

    total_weight = sum(r["weight"] for r in results.values())
    breakdown = {
        mid: {
            "weight": round(r["weight"] / total_weight, 4),
            "fair_value": round(r["fair_value"], 2),
            "scenarios": {
                k: (round(v, 2) if v is not None else None)
                for k, v in r["scenarios"].items()
            },
            "is_approx": mid in m.APPROX_METHODS,
        }
        for mid, r in results.items()
    }

    # Derive fair_value from the breakdown so that consistency holds exactly:
    # result["fair_value"] == sum(b["weight"] * b["fair_value"]) (what the test checks).
    fair_value: float | None = None
    if breakdown:
        fair_value = sum(b["weight"] * b["fair_value"] for b in breakdown.values())

    pct = None
    if fair_value is not None and current_price and current_price > 0:
        pct = round((fair_value - current_price) / current_price * 100, 2)

    return {
        "ticker": ticker, "company_name": company_name, "current_price": current_price,
        "last_evaluated": None, "stock_type": stock_type,
        "fair_value": fair_value,
        "price_vs_fair_value_pct": pct, "fair_value_breakdown": breakdown,
        "status": "completed", "errors": [],
    }
