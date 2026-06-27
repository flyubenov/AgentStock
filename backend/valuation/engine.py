from __future__ import annotations
from datetime import datetime, timezone
from valuation.classifier import classify
from valuation import models as m
from services.yahoo import fetch_ticker_info, extract_financials, fetch_ticker_cashflow, real_fcf
from models import TickerResult

EBITDA_MARGIN_FLOOR = 0.08
SUSTAINABLE_CEIL = 0.039
FCF_MARGIN_FLOOR = -0.25

_SINGLE_VALUE_FN = {"pe": m.calc_pe, "pb": m.calc_pb, "sotp": m.calc_sotp, "nav": m.calc_nav}
_SCENARIO_FN = {
    "fcfe": m.calc_fcfe,
    "ev_ebitda": m.calc_ev_ebitda,
    "ev_sales": m.calc_ev_sales,
    "ddm": m.calc_ddm,
    "rim": m.calc_rim,
}


def _earnings_distorted(fin: dict) -> bool:
    """GAAP earnings treated as distorted: negative earnings growth while
    revenue is still growing (acquisition amortization / one-offs, e.g. ABBV)."""
    eg = fin.get("earnings_growth")
    rg = fin.get("revenue_growth") or 0
    return eg is not None and eg < 0 and rg > 0


def build_scenarios(fin: dict) -> dict:
    """Per-stock capped growth scenarios (spec decision #1).

    When GAAP earnings growth is negative while revenue is still growing, the
    earnings figure is treated as distorted (acquisition amortization / one-off
    charges, e.g. ABBV) rather than a real decline. Growth is then sourced from
    revenue growth, capped at SUSTAINABLE_CEIL to avoid the r-g overshoot in the
    perpetuity-based models (DDM, P/E). A genuine decline (revenue also falling)
    stays on the normal floored path."""
    if _earnings_distorted(fin):
        raw = min(fin.get("revenue_growth") or 0, SUSTAINABLE_CEIL)
    else:
        raw = fin.get("earnings_growth") or fin.get("revenue_growth") or 0.07
    base = max(0.02, min(float(raw), 0.20))
    return {
        "optimistic": min(base + 0.05, 0.20),
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


def evaluate(fin: dict) -> dict:
    """Pure valuation pipeline. Returns a result dict (no IO, no timestamps)."""
    classification = classify(fin)
    stock_type = classification["stock_type"]
    weights = {mid: classification["method_weights"][mid]["weight"] for mid in m.ALL_METHODS}
    weights = pick_ev_multiple(weights, fin)

    # Pre-profit guard: a DCF-anchored company burning cash on a trailing basis
    # cannot be valued reliably from trailing financials. Decline rather than
    # emit a misleading number.
    fcf_ttm = fin.get("fcf_ttm")
    revenue_ttm = fin.get("revenue_ttm")
    if (weights.get("dcf", 0) > 0 and fcf_ttm is not None and revenue_ttm
            and fcf_ttm / revenue_ttm < FCF_MARGIN_FLOOR):
        return {
            "ticker": fin.get("ticker") or "",
            "company_name": fin.get("company_name"),
            "current_price": fin.get("current_price"),
            "last_evaluated": None, "stock_type": "PRE_PROFIT",
            "fair_value": None, "price_vs_fair_value_pct": None,
            "fair_value_breakdown": {},
            "status": "failed",
            "errors": ["Negative free cash flow (pre-profit / heavy investment "
                       "phase) — trailing financials don't support a reliable valuation"],
        }

    # Distorted GAAP earnings make any trailing-earnings multiple unreliable;
    # drop the P/E leg and let the remaining models renormalize (e.g. ABBV).
    if _earnings_distorted(fin) and weights.get("pe", 0) > 0:
        weights = dict(weights)
        weights["pe"] = 0.0

    growth = build_scenarios(fin)

    results: dict[str, dict] = {}
    for mid in m.ALL_METHODS:
        weight = weights.get(mid, 0.0)
        if weight <= 0:
            continue
        if mid == "dcf":
            r = m.calc_dcf(fin, growth)
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
    breakdown = {}
    methods_list = list(results.items())
    for idx, (mid, r) in enumerate(methods_list):
        rounded_weight = round(r["weight"] / total_weight, 4)
        # For the last method, adjust weight to ensure sum == 1.0
        if idx == len(methods_list) - 1:
            rounded_weight = round(1.0 - sum(
                breakdown[m]["weight"] for m in breakdown.keys()
            ), 4)
        breakdown[mid] = {
            "weight": rounded_weight,
            "fair_value": round(r["fair_value"], 2),
            "scenarios": {
                k: (round(v, 2) if v is not None else None)
                for k, v in r["scenarios"].items()
            },
            "is_approx": mid in m.APPROX_METHODS,
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


async def run(ticker: str) -> TickerResult:
    """Async IO wrapper: fetch info + cashflow, source real FCF, evaluate -> TickerResult."""
    try:
        info = await fetch_ticker_info(ticker)
    except Exception:
        return TickerResult(ticker=ticker.upper(), status="failed",
                            errors=["yfinance data unavailable"])
    fin = extract_financials(info)
    fin["ticker"] = fin.get("ticker") or ticker.upper()
    cashflow = await fetch_ticker_cashflow(ticker)
    rf = real_fcf(cashflow, fin.get("fcf_ttm"))
    if rf is not None:
        fin["fcf_ttm"] = rf
    data = evaluate(fin)
    data["last_evaluated"] = datetime.now(timezone.utc).isoformat()
    return TickerResult(**data)
