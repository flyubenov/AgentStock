from __future__ import annotations
from datetime import datetime, timezone
from valuation.classifier import classify
from valuation import models as m
from services.yahoo import (
    fetch_ticker_info, extract_financials, fetch_ticker_cashflow, real_fcf,
    fetch_ev_ebitda_history,
)
from models import TickerResult

EBITDA_MARGIN_FLOOR = 0.08
SUSTAINABLE_CEIL = 0.039
FCF_MARGIN_FLOOR = -0.25

# Operating-compounder tiers: real earnings AND real EBITDA, so they take the
# "balance past and future" basis — historical-median EV/EBITDA + forward P/E.
FORWARD_TIERS = {"LARGE_CAP", "MID_CAP", "GROWTH"}

# pe and ev_ebitda are dispatched explicitly (they take method-basis flags); the
# maps cover the remaining methods with uniform signatures.
_SINGLE_VALUE_FN = {"pb": m.calc_pb, "sotp": m.calc_sotp, "nav": m.calc_nav}
# ddm is dispatched explicitly: its perpetuity is fed the SUSTAINABLE_CEIL-capped
# growth (see evaluate), so it can't overshoot Gordon growth on a distorted name.
_SCENARIO_FN = {
    "fcfe": m.calc_fcfe,
    "ev_sales": m.calc_ev_sales,
    "rim": m.calc_rim,
}


def _earnings_distorted(fin: dict) -> bool:
    """GAAP earnings treated as distorted: negative earnings growth while
    revenue is still growing (acquisition amortization / one-offs, e.g. ABBV)."""
    eg = fin.get("earnings_growth")
    rg = fin.get("revenue_growth") or 0
    return eg is not None and eg < 0 and rg > 0


def build_scenarios(fin: dict, distorted_cap: float = 0.20) -> dict:
    """Per-stock capped growth scenarios (spec decision #1).

    When GAAP earnings growth is negative while revenue is still growing, the
    earnings figure is treated as distorted (acquisition amortization / one-off
    charges, e.g. ABBV/ETN) rather than a real decline. Growth is then sourced
    from revenue growth. A genuine decline (revenue also falling) stays on the
    normal floored path.

    distorted_cap bounds the revenue-sourced rate. The default (0.20, the normal
    ceiling) is for the bounded-horizon legs (DCF/EV/EBITDA/PE), which can carry
    the real rate. The perpetuity-based DDM passes distorted_cap=SUSTAINABLE_CEIL
    so Gordon growth can't overshoot the discount rate."""
    if _earnings_distorted(fin):
        raw = min(fin.get("revenue_growth") or 0, distorted_cap)
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

    is_growth = stock_type == "GROWTH"
    is_forward_tier = stock_type in FORWARD_TIERS

    # Distorted GAAP earnings make a *trailing* P/E unreliable; drop the P/E leg
    # and let the remaining models renormalize (e.g. ABBV). Forward tiers value
    # P/E off the *forward* multiple, which is robust to a one-off trailing
    # charge, so they keep the leg (regression: ETN's recovery leg was discarded).
    if _earnings_distorted(fin) and not is_forward_tier and weights.get("pe", 0) > 0:
        weights = dict(weights)
        weights["pe"] = 0.0

    growth = build_scenarios(fin)
    # The DDM perpetuity keeps distorted names on the sustainable ceiling.
    ddm_growth = build_scenarios(fin, distorted_cap=SUSTAINABLE_CEIL)

    results: dict[str, dict] = {}
    for mid in m.ALL_METHODS:
        weight = weights.get(mid, 0.0)
        if weight <= 0:
            continue
        if mid == "dcf":
            r = m.calc_dcf(fin, growth)
        elif mid == "ev_ebitda":
            # Forward tiers anchor to the historical-median multiple when available
            # (no compression). Without it, GROWTH keeps its full multiple
            # uncompressed; other tiers compress the current trailing multiple.
            hist = fin.get("ev_ebitda_hist") if is_forward_tier else None
            r = m.calc_ev_ebitda(fin, growth, hist_multiple=hist,
                                 compress=(hist is None and not is_growth))
        elif mid == "pe":
            r = m.calc_pe(fin, forward=is_forward_tier)
        elif mid == "ddm":
            r = m.calc_ddm(fin, ddm_growth)
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

    # Forward tiers anchor EV/EBITDA to its historical median when reconstructable
    # (the reconstruction skips itself across a recent split — see services.yahoo).
    hist = await fetch_ev_ebitda_history(ticker)
    if hist is not None:
        fin["ev_ebitda_hist"] = hist

    data = evaluate(fin)
    data["last_evaluated"] = datetime.now(timezone.utc).isoformat()
    return TickerResult(**data)
