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
# Below this FCF/EBITDA conversion, positive trailing FCF is treated as
# unrepresentative of earning power (capex is eating it — e.g. AMZN's AWS/AI
# build-out), so the DCF is rerouted onto EV/EBITDA + P/E rather than anchored to
# the residual. Distinct from FCF_MARGIN_FLOOR, which declines deeply-negative FCF.
FCF_EBITDA_FLOOR = 0.15

# Revenue-coupled growth cap: hyper-growers earn a modest, bounded increment of
# near-term growth credit above the flat base. The ramp is deliberately shallow
# (+1pp of cap per 8pp of growth) and the 0.25 ceiling — reached at g=0.60 — is the
# ultimate backstop against a noisy-high growth reading.
GROWTH_CAP_BASE = 0.20
GROWTH_CAP_CEIL = 0.25
GROWTH_CAP_SLOPE = 0.125

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


def _growth_cap(g: float) -> float:
    """Near-term growth cap coupled to revenue growth: flat GROWTH_CAP_BASE until
    growth passes GROWTH_CAP_BASE, then a gentle linear ramp to GROWTH_CAP_CEIL
    (reached at g=0.60). The ceiling bounds a noisy-high growth reading."""
    return min(GROWTH_CAP_CEIL,
               GROWTH_CAP_BASE + GROWTH_CAP_SLOPE * max(0.0, g - GROWTH_CAP_BASE))


def _cap_eligible(fin: dict) -> bool:
    """The elevated growth cap applies only to names demonstrating economics:
    FCF-positive, or operationally cash-generative (EBITDA > 0 and OCF > 0). This
    reuses the capex-reroute cash-generation signal, so capex-heavy reinvestors
    (negative FCF, positive EBITDA/OCF — e.g. IREN) still qualify. OCF falls back
    to the info figure when the statement value is absent."""
    fcf = fin.get("fcf_ttm")
    if fcf is not None and fcf > 0:
        return True
    ebitda = fin.get("ebitda_ttm") or 0
    ocf = fin.get("ocf_ttm")
    if ocf is None:
        ocf = fin.get("operating_cashflow")
    return ebitda > 0 and ocf is not None and ocf > 0


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
        raw = (fin.get("earnings_growth") or fin.get("revenue_growth")
               or fin.get("revenue_growth_stmt") or 0.07)
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
    ocf_ttm = fin.get("ocf_ttm")
    if ocf_ttm is None:
        ocf_ttm = fin.get("operating_cashflow")   # info fallback
    ebitda_ttm = fin.get("ebitda_ttm") or 0
    if (weights.get("dcf", 0) > 0 and fcf_ttm is not None and revenue_ttm
            and fcf_ttm / revenue_ttm < FCF_MARGIN_FLOOR):
        if ebitda_ttm > 0 and ocf_ttm is not None and ocf_ttm > 0:
            # Capex-distorted, negative-FCF variant: operations generate cash (OCF > 0)
            # and EBITDA is valuable, so deeply negative FCF is a capex/investment
            # choice, not a burn. Value on EV/EBITDA + P/E, leaning harder on the
            # multiple than the positive-FCF case (0.85/0.15) because these names carry
            # accrual-distorted earnings (e.g. IREN's net income is inflated by non-cash
            # bitcoin fair-value gains) — so EPS is excluded from the gate and trusted
            # for only 15% of the value.
            weights = {mid: 0.0 for mid in m.ALL_METHODS}
            weights["ev_ebitda"], weights["pe"] = 0.85, 0.15
        else:
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

    # Capex-distorted FCF: a DCF-anchored company whose trailing FCF is POSITIVE but
    # a negligible fraction of EBITDA (capex is eating it — e.g. AMZN's AWS/AI
    # build-out) cannot be valued off that residual. Reroute the DCF onto EV/EBITDA +
    # P/E. The P/E leg self-drops when trailing EPS <= 0, renormalising onto EV/EBITDA
    # alone. Only positive FCF is handled here; deeply-negative FCF is already declined
    # above by the pre-profit guard.
    ebitda_ttm = fin.get("ebitda_ttm") or 0
    if (weights.get("dcf", 0) > 0 and fcf_ttm is not None and fcf_ttm >= 0
            and ebitda_ttm > 0 and fcf_ttm < FCF_EBITDA_FLOOR * ebitda_ttm):
        weights = {mid: 0.0 for mid in m.ALL_METHODS}
        weights["ev_ebitda"], weights["pe"] = 0.70, 0.30

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
            hist_base = fin.get("ev_ebitda_hist_base") if is_forward_tier else None
            r = m.calc_ev_ebitda(fin, growth, hist_multiple=hist, hist_ebitda_base=hist_base,
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
    if cashflow:
        ocf = cashflow.get("operating_cash_flow")
        if ocf is not None:
            fin["ocf_ttm"] = ocf   # statement-primary; gate falls back to info operating_cashflow

    # Forward tiers anchor EV/EBITDA to its historical median when reconstructable
    # (the reconstruction skips itself across a recent split — see services.yahoo).
    hist = await fetch_ev_ebitda_history(ticker)
    if hist is not None:
        fin["ev_ebitda_hist"] = hist["multiple"]
        # Project the statement EBITDA the median was built from, not info['ebitda']
        # (they can differ ~2x — content amortization at NFLX).
        fin["ev_ebitda_hist_base"] = hist["ebitda"]
        if hist.get("revenue_growth") is not None:
            fin["revenue_growth_stmt"] = hist["revenue_growth"]

    data = evaluate(fin)
    data["last_evaluated"] = datetime.now(timezone.utc).isoformat()
    return TickerResult(**data)
