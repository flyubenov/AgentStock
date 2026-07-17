from __future__ import annotations
from datetime import datetime, timezone
from valuation.classifier import classify
from valuation import models as m
from services.yahoo import (
    fetch_ticker_info, extract_financials, fetch_ticker_cashflow, real_fcf,
    fetch_ev_ebitda_history, fetch_quarterly_revenue,
)
from models import TickerResult

EBITDA_MARGIN_FLOOR = 0.08
SUSTAINABLE_CEIL = 0.039
# Below this FCF/EBITDA conversion, positive trailing FCF is treated as
# unrepresentative of earning power (capex is eating it — e.g. AMZN's AWS/AI
# build-out), so the DCF is rerouted onto EV/EBITDA + P/E rather than anchored to
# the residual. Distinct from the pre-profit guard, which handles negative FCF.
FCF_EBITDA_FLOOR = 0.15

# Revenue-coupled growth cap: growers earn a bounded increment of near-term growth credit
# above the flat base. The ramp credits SLOPE of each point of growth above the base, up to
# the CEIL backstop against a noisy-high reading. The near-term rate is held only `hold`
# years (3 for a $150B+ name) and then faded to TERMINAL_GROWTH by the horizon, so the fade
# — not this cap — bounds the long-run damage of a high rate; the cap need only avoid
# projecting a *spurious* rate. The original ramp (slope 0.125, ceil 0.25) was calibrated as
# a noise-suppressor for EARLY_GROWTH hyper-growers and was far too stingy for a corroborated
# operating compounder: ANET, growing a statement-corroborated ~28% (revenue) / 25%
# (earnings), was clamped to 21%. The steeper slope credits corroborated growth much more
# closely — but it can only ever pass through the demonstrated `raw` rate (earnings/revenue
# growth), never manufacture growth above it, so a single noisy-high feed reading is still
# bounded by `raw` and by the CEIL. EARLY_GROWTH keeps its own shallow slope (EG_CAP_SLOPE),
# so NBIS/TEM are unchanged.
#
# The CEILING is deliberately LEFT at 0.25: it is the backstop for a hyper-grower whose `raw`
# rate sits far above it (IREN's 167%, pinned at the ceiling whatever the slope). Only the
# SLOPE is steepened, so a mid-range corroborated grower REACHES the existing ceiling rather
# than a higher one — ANET's ~28.6% statement growth now lands at 0.25 (its 25% earnings-
# growth `raw`), while a 167% grower stays pinned at 0.25 exactly as before. At slope 0.60
# the 0.25 ceiling is reached at g≈0.283, so anything growing faster than ~28% saturates.
GROWTH_CAP_BASE = 0.20
GROWTH_CAP_CEIL = 0.25
GROWTH_CAP_SLOPE = 0.60
# The optimistic scenario runs this far above the realistic near-term cap. Without it, a
# grower whose demonstrated rate sits AT the cap had optimistic == realistic — the
# min(base+0.05, cap) clamp erased the entire bull case, so the 3-way scenario average was
# biased strictly BELOW realistic (only the pessimistic leg had room to move). The headroom
# restores a genuine, bounded upside leg (base is <= cap, so optimistic = base + 0.05).
GROWTH_OPT_HEADROOM = 0.05

# EARLY_GROWTH runs its own ceiling on the SAME shallow ramp. The tier is defined by
# unprofitability, so _cap_eligible ("names demonstrating economics": FCF > 0, or
# EBITDA > 0 and OCF > 0) can never fire for a cash burner and the tier fell through to
# the flat base — pinning a 684% grower (NBIS) and a 36% grower (TEM) at the identical
# 0.20 and making "massively overvalued" a foregone conclusion. For this tier revenue
# growth IS the demonstrated economics, so the ramp is what gates the credit: the slope
# is unchanged, so 36% growth still earns only 2pp (TEM -> 0.22) and only a >140% grower
# reaches the ceiling. Verified against statements, not just info: NBIS's 684% reconciles
# with its Q1 YoY (+683.9%) and annual (+479%), and is accelerating.
#
# 0.35 sits inside the STABLE zone. Swept against the (corrected) run-rate base, the whole
# 0.35-0.40 band leaves NBIS robustly overvalued (-46% to -23%) and moves it only ~$4 per
# 0.01 of ceiling — the verdict does not depend on the exact value. FV crosses price at
# 0.4361, so an earlier 0.45 sat just PAST the crossover, balanced on a knife edge where a
# 0.01 nudge flipped buy/sell, and above it the curve turns sharply convex. 0.45 was also
# calibrated against the stale TTM base, i.e. the cap was silently doing double duty
# compensating for a base that lagged 83%; once run_rate_revenue fixed the base that job
# disappeared and the ceiling came back down with it. Only names growing >140% ever reach
# this ceiling (TEM sits at 0.22 regardless), so it is set on a thin sample — prefer a
# round, defensible assumption over a value reverse-engineered from one company's output.
EG_CAP_CEIL = 0.35
# EARLY_GROWTH keeps the original shallow ramp (a noise-suppressor for hyper-growth rates
# printed off a small base); the GROWTH-tier slope steepening above must NOT leak into this
# tier, or NBIS/TEM re-calibrate. See EG_CAP_CEIL's note on why 0.125 was chosen here.
EG_CAP_SLOPE = 0.125
# ...but a hyper-growth *rate* off a tiny revenue base is arithmetic, not a business
# ($1M -> $5M = 400%). Demand demonstrated scale before granting the elevated ceiling,
# mirroring the screener's RULE_OF_40_GROWTH_CAP guard against a tiny-base rate
# dominating. Below the floor the tier keeps the flat GROWTH_CAP_BASE.
EG_REVENUE_FLOOR = 500_000_000

# Operating-compounder tiers: real earnings AND real EBITDA, so they take the
# "balance past and future" basis — historical-median EV/EBITDA + forward P/E.
FORWARD_TIERS = {"MEGA_CAP", "LARGE_CAP", "MID_CAP", "GROWTH"}

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


def _growth_cap(g: float, ceil: float = GROWTH_CAP_CEIL,
                slope: float = GROWTH_CAP_SLOPE) -> float:
    """Near-term growth cap coupled to revenue growth: flat GROWTH_CAP_BASE until growth
    passes GROWTH_CAP_BASE, then a linear ramp of `slope` per point of excess growth up to
    `ceil`. GROWTH tiers use the default (steep) slope; EARLY_GROWTH passes its own shallow
    EG_CAP_SLOPE. The ceiling bounds a noisy-high growth reading."""
    return min(ceil,
               GROWTH_CAP_BASE + slope * max(0.0, g - GROWTH_CAP_BASE))


def _eg_cap_eligible(fin: dict) -> bool:
    """EARLY_GROWTH earns the elevated ceiling on demonstrated SCALE — the cash-flow
    test in _cap_eligible is structurally unpassable for this tier, so revenue stands in
    as the evidence that the growth rate describes a business rather than a small
    denominator."""
    revenue = fin.get("revenue_ttm")
    return revenue is not None and revenue >= EG_REVENUE_FLOOR


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


def _earnings_non_operating(fin: dict) -> bool:
    """GAAP earnings grew while the OPERATING business did not — the increment came from
    below the operating line (JV equity income, other non-operating income), which cannot
    be extrapolated as operating cash-flow growth.

    The mirror image of _earnings_distorted: there earnings UNDERSTATE a healthy business
    (amortization / one-offs) and revenue stands in; here they OVERSTATE one whose
    operating line is flat or shrinking. BWXT: +20.7% earnings growth on operating income
    that FELL 1.4% (its JV equity income alone went 55.9M -> 74.9M while the operating
    margin compressed for a fourth year), which projected a decade of 20% growth for a
    business earning no more from operations than it did three years earlier.

    The trigger is the SIGN of operating growth, not a gap between the two rates: a
    declining operating line is a real cliff (any positive earnings growth is then
    non-operating by construction), whereas "earnings grew somewhat faster than
    operations" is an arbitrary threshold with nothing underneath it. A missing statement
    reading is unknown, not declining — keep the earnings source.

    BOTH readings are statement-ANNUAL and come from the same rows. This deliberately
    ignores info['earningsGrowth'], which is the latest-QUARTER YoY: testing it against
    an annual operating change compares a quarterly rate to an annual one. That mismatch
    misfired on CEG (a positive quarterly bounce against one soft annual operating year,
    while its annual net income had FALLEN 38% and its operating income had gone -408M ->
    4,198M over three years) and on DDOG (operating income oscillating around zero on a
    -1.3% margin, where the YoY is noise, not a trajectory). Comparing like with like
    excludes both: their annual earnings fell, so there was no growth to call
    non-operating."""
    ni_g = fin.get("net_income_growth_stmt")
    og = fin.get("op_income_growth_stmt")
    return ni_g is not None and ni_g > 0 and og is not None and og <= 0


def build_scenarios(fin: dict, distorted_cap: float = 0.20,
                    stock_type: str | None = None) -> dict:
    """Per-stock capped growth scenarios (spec decision #1).

    When GAAP earnings growth is negative while revenue is still growing, the
    earnings figure is treated as distorted (acquisition amortization / one-off
    charges, e.g. ABBV/ETN) rather than a real decline. Growth is then sourced
    from revenue growth. A genuine decline (revenue also falling) stays on the
    normal floored path.

    distorted_cap bounds the revenue-sourced rate. The default (0.20, the normal
    ceiling) is for the bounded-horizon legs (DCF/EV/EBITDA/PE), which can carry
    the real rate. The perpetuity-based DDM passes distorted_cap=SUSTAINABLE_CEIL
    so Gordon growth can't overshoot the discount rate.

    The near-term cap is revenue-coupled: an eligible (cash-generative) hyper-grower
    earns up to GROWTH_CAP_CEIL (0.25), sourced statement-YoY-first. The elevated cap
    rides only the normal bounded-horizon path (distorted_cap >= GROWTH_CAP_BASE);
    the DDM path keeps the flat base.

    stock_type == "EARLY_GROWTH" swaps in that tier's own ceiling (EG_CAP_CEIL) on the
    same ramp, gated on revenue scale rather than the cash generation the tier can never
    show — see EG_CAP_CEIL / _eg_cap_eligible."""
    cap = GROWTH_CAP_BASE
    if distorted_cap >= GROWTH_CAP_BASE:
        g = fin.get("revenue_growth_stmt")
        if g is None:
            g = fin.get("revenue_growth") or 0.0
        if stock_type == "EARLY_GROWTH":
            if _eg_cap_eligible(fin):
                cap = _growth_cap(g, EG_CAP_CEIL, EG_CAP_SLOPE)
        elif _cap_eligible(fin):
            cap = _growth_cap(g)
    if _earnings_distorted(fin):
        raw = min(fin.get("revenue_growth") or 0, distorted_cap)
    elif _earnings_non_operating(fin):
        # Source from the operating line itself — the clean signal here, unlike the
        # distorted case where amortization hits operating income too and revenue is the
        # fallback. Revenue growth would be wrong: BWXT's top line grew 18.3% precisely
        # WHILE margins compressed, so it overstates cash-flow growth for the same reason
        # the earnings figure does. The existing max(0.02, ...) floor keeps a declining
        # operating line from projecting negative growth.
        raw = fin["op_income_growth_stmt"]
    else:
        raw = (fin.get("earnings_growth") or fin.get("revenue_growth")
               or fin.get("revenue_growth_stmt") or 0.07)
    base = max(0.02, min(float(raw), cap))
    # Optimistic upside above the near-term cap is granted only when the demonstrated rate
    # isn't heavily suppressed by the ceiling backstop (raw within a headroom of the cap): a
    # corroborated grower like ANET (raw ≈ cap) gets a genuine bull case, while a hyper-grower
    # pinned far below its raw rate by the noise ceiling (IREN's 167%, NBIS's 684%) keeps
    # optimistic AT the cap — the backstop must hold in the bull case too, or the exact
    # noise the ceiling exists to suppress leaks back in through the optimistic leg.
    opt_ceiling = (cap + GROWTH_OPT_HEADROOM
                   if float(raw) <= cap + GROWTH_OPT_HEADROOM else cap)
    return {
        "optimistic": min(base + 0.05, opt_ceiling),
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
    # Banks / lenders / insurers are financed below the flat 10% default; discount
    # their book-value legs (P/B + RIM) at FINANCIAL_COE. Copy so the caller's dict is
    # never mutated. extract_financials hardcodes cost_of_equity = DISCOUNT_RATE (0.10)
    # as the flat default, so treat None *or* that default as "unset" and override; a
    # genuine per-name COE (anything other than the flat default) is respected.
    if stock_type == "FINANCIAL":
        coe = fin.get("cost_of_equity")
        if coe is None or coe == m.DISCOUNT_RATE:
            fin = {**fin, "cost_of_equity": m.FINANCIAL_COE}
    weights = {mid: classification["method_weights"][mid]["weight"] for mid in m.ALL_METHODS}
    weights = pick_ev_multiple(weights, fin)

    fcf_ttm = fin.get("fcf_ttm")
    ocf_ttm = fin.get("ocf_ttm")
    if ocf_ttm is None:
        ocf_ttm = fin.get("operating_cashflow")   # info fallback
    ebitda_ttm = fin.get("ebitda_ttm") or 0

    # EARLY_GROWTH is *defined* by unprofitability (classifier rule 4: revenue growth
    # > 20% AND eps/ebitda <= 0), so a trailing-FCF DCF is negative by construction for
    # exactly the names the tier exists to value — dragging the composite below zero and
    # declining a company its own EV/Sales leg prices fine (TEM: DCF -$47 vs EV/Sales
    # +$29). Zero the leg and let EV/Sales + SOTP carry the tier (weights renormalize
    # over the surviving legs below). This also makes the pre-profit guard skip the tier
    # for the same reason FINANCIAL skips it: a zero DCF weight, nothing left to protect.
    if stock_type == "EARLY_GROWTH" and fcf_ttm is not None and fcf_ttm <= 0:
        weights = {**weights, "dcf": 0.0}

    # Pre-profit guard: a DCF-anchored company burning cash on a trailing basis cannot be
    # valued reliably from trailing financials. The trigger is the SIGN of FCF, not the
    # depth of the burn: discounting negative cash flows yields a negative value however
    # shallow the burn, so a magnitude floor only let the near-breakeven names — the ones
    # closest to viable — through with a meaningless negative leg in the blend.
    if weights.get("dcf", 0) > 0 and fcf_ttm is not None and fcf_ttm < 0:
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

    growth = build_scenarios(fin, stock_type=stock_type)
    # The DDM perpetuity keeps distorted names on the sustainable ceiling.
    ddm_growth = build_scenarios(fin, distorted_cap=SUSTAINABLE_CEIL)

    # Forward-tier severe earnings trough (a just-closed transformative acquisition, e.g.
    # SNPS post-Ansys): the trailing-FCF DCF base carries the full deal cost but only a
    # stub of the acquired earnings, understating the combined company. Rebase the DCF
    # onto forward run-rate owner earnings, capped at the forward-P/E leg so the rebased
    # DCF can't run above that trustworthy forward anchor. Only forward tiers, which
    # already value the P/E leg off the forward multiple, qualify.
    dcf_base_override: float | None = None
    dcf_value_cap: float | None = None
    if is_forward_tier and weights.get("dcf", 0) > 0:
        rebased = m.rebased_dcf_base(fin)
        if rebased is not None:
            pe_cap = m.calc_pe(fin, forward=True).get("fair_value")
            if pe_cap is not None:
                dcf_base_override, dcf_value_cap = rebased, pe_cap

    results: dict[str, dict] = {}
    for mid in m.ALL_METHODS:
        weight = weights.get(mid, 0.0)
        if weight <= 0:
            continue
        if mid == "dcf":
            r = m.calc_dcf(fin, growth, base_override=dcf_base_override, value_cap=dcf_value_cap)
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

    # EV/Sales cannot be the SOLE anchor on a revenue base the model has already
    # declared uninformative. Below EG_REVENUE_FLOOR, _eg_cap_eligible refuses to read
    # the growth rate as evidence about the business (a tiny base prints hyper-growth on
    # arithmetic) — so the same base cannot then carry 100% of the value. That was
    # ASTS: $84.9M of lumpy contract revenue, one $54.3M milestone quarter, against a
    # $21.4B market cap, priced at $1.15 (-98%) — false precision about a pre-commercial
    # business the trailing statements cannot see. A sub-floor name with any independent
    # leg is corroborated and passes (AMBA keeps a DCF; IDR a P/E), as does a sole
    # EV/Sales leg once the base clears the floor (NBIS). Note this restores the outcome
    # the pre-profit guard used to produce for these names before the EARLY_GROWTH DCF
    # drop above made it skip the tier: the guard was also refusing to value cash-burning
    # pre-commercial companies, not just protecting against a negative DCF leg.
    if set(results) == {"ev_sales"} and not _eg_cap_eligible(fin):
        return {
            "ticker": ticker, "company_name": company_name, "current_price": current_price,
            "last_evaluated": None, "stock_type": stock_type,
            "fair_value": None, "price_vs_fair_value_pct": None,
            "fair_value_breakdown": {},
            "status": "failed",
            "errors": ["revenue base too small to anchor a sales-multiple valuation, and "
                       "no independent model survives — trailing financials don't support "
                       "a reliable valuation"],
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

    # A non-positive composite is not a valuation — a negative-FCF DCF leg (or similar)
    # dragged the blend at or below zero. Decline rather than surface a misleading
    # number (regression: INTC emitted a completed fair value of -$2.59).
    if fair_value is not None and fair_value <= 0:
        return {
            "ticker": ticker, "company_name": company_name, "current_price": current_price,
            "last_evaluated": None, "stock_type": stock_type,
            "fair_value": None, "price_vs_fair_value_pct": None,
            "fair_value_breakdown": {},
            "status": "failed",
            "errors": ["composite fair value non-positive — trailing financials "
                       "don't support a reliable valuation"],
        }

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

    # TTM revenue is centred ~6 months back, so it lags today's revenue on a fast grower;
    # derive the current run-rate for the EV/Sales base (gated + only-help inside
    # models.run_rate_revenue, so this is a no-op for everything but a hyper-grower).
    # Pre-gate on the growth we already hold from `info` so the extra quarterly fetch is
    # only paid by the few names that could clear the floor — a batch run over the whole
    # universe would otherwise add one yfinance round-trip per ticker for nothing, against
    # a feed that rate-limits (see services.yf_pool). run_rate_revenue re-checks the floor
    # and stays authoritative; this only avoids the IO.
    fin["revenue_run_rate"] = None
    if (fin.get("revenue_growth") or 0) > m.RUN_RATE_GROWTH_FLOOR:
        quarters = await fetch_quarterly_revenue(ticker)
        fin["revenue_run_rate"] = m.run_rate_revenue(
            quarters, fin.get("revenue_ttm"), fin.get("revenue_growth"))

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
        # Operating-line growth: lets build_scenarios tell earnings growth the operating
        # business produced from growth that arrived below it (see
        # _earnings_non_operating). Rides this fetch rather than paying its own yfinance
        # round-trip per ticker (rate limits — see services.yf_pool). Inherits this
        # dict's bail-to-None whenever the EV/EBITDA median is uncomputable, which the
        # guard reads as "unknown" and leaves the growth source alone.
        fin["op_income_growth_stmt"] = hist.get("op_income_growth")
        fin["net_income_growth_stmt"] = hist.get("net_income_growth")

    data = evaluate(fin)
    data["last_evaluated"] = datetime.now(timezone.utc).isoformat()
    return TickerResult(**data)
