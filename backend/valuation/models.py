from __future__ import annotations

DISCOUNT_RATE = 0.10
TERMINAL_GROWTH = 0.03
HORIZON = 10
MOS = 0.90
EV_EBITDA_CAP = 20.0
EV_SALES_CAP = 8.0

ALL_METHODS = ["dcf", "fcfe", "ev_ebitda", "pe", "ev_sales", "ddm", "pb", "rim", "sotp", "nav"]
SCENARIO_MODELS = {"dcf", "fcfe", "ev_ebitda", "ev_sales", "pe", "ddm", "rim"}
APPROX_METHODS = {"sotp", "nav"}
SCENARIO_KEYS = ("optimistic", "realistic", "pessimistic")


# -- helpers -------------------------------------------------------------------
def _pv(cf: float, rate: float, year: int) -> float:
    return cf / (1 + rate) ** year


def _apply_mos(value: float) -> float:
    return value * MOS


def _avg(scenarios: dict) -> float | None:
    vals = [v for v in scenarios.values() if v is not None]
    return sum(vals) / len(vals) if vals else None


def _null_result(has_scenarios: bool) -> dict:
    return {
        "scenarios": {"optimistic": None, "realistic": None, "pessimistic": None},
        "fair_value": None,
        "weight": 0.0,
        "has_scenarios": has_scenarios,
    }


def _scenario_dcf_equity(cf: float, growth: float, net_debt: float, shares: float) -> float:
    total = 0.0
    cf_t = cf
    for t in range(1, HORIZON + 1):
        cf_t *= (1 + growth)
        total += _pv(cf_t, DISCOUNT_RATE, t)
    tv = cf_t * (1 + TERMINAL_GROWTH) / (DISCOUNT_RATE - TERMINAL_GROWTH)
    total += _pv(tv, DISCOUNT_RATE, HORIZON)
    return _apply_mos((total - net_debt) / shares)


def _scenario_ev_multiple(base: float, growth: float, multiple: float, net_debt: float, shares: float) -> float:
    projected = base * (1 + growth) ** HORIZON
    future_ev = projected * multiple
    return _apply_mos((future_ev - net_debt) / shares / (1 + DISCOUNT_RATE) ** HORIZON)


# -- DCF (FCFF) ----------------------------------------------------------------
def calc_dcf(fin: dict, growth: dict, cashflow_base: float | None = None) -> dict:
    base = cashflow_base if cashflow_base is not None else fin.get("fcf_ttm")
    shares = fin.get("shares_outstanding")
    if base is None or not shares:
        return _null_result(True)
    net_debt = fin.get("net_debt") or 0
    scenarios = {k: _scenario_dcf_equity(base, growth[k], net_debt, shares) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- FCFE DCF (dormant) --------------------------------------------------------
def calc_fcfe(fin: dict, growth: dict) -> dict:
    fcf = fin.get("fcf_ttm")
    shares = fin.get("shares_outstanding")
    if fcf is None or not shares:
        return _null_result(True)
    tax_rate = fin.get("effective_tax_rate")
    tax_rate = 0.21 if tax_rate is None else tax_rate
    interest_adj = (fin.get("interest_expense") or 0) * (1 - tax_rate)
    fcfe = fcf - interest_adj
    scenarios = {k: _scenario_dcf_equity(fcfe, growth[k], 0, shares) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- EV/EBITDA -----------------------------------------------------------------
def calc_ev_ebitda(fin: dict, growth: dict) -> dict:
    ebitda = fin.get("ebitda_ttm")
    multiple = fin.get("ev_ebitda")
    shares = fin.get("shares_outstanding")
    if ebitda is None or multiple is None or not shares:
        return _null_result(True)
    multiple = min(multiple, EV_EBITDA_CAP)
    net_debt = fin.get("net_debt") or 0
    scenarios = {k: _scenario_ev_multiple(ebitda, growth[k], multiple, net_debt, shares) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- EV/Sales ------------------------------------------------------------------
def calc_ev_sales(fin: dict, growth: dict) -> dict:
    revenue = fin.get("revenue_ttm")
    multiple = fin.get("ev_sales")
    shares = fin.get("shares_outstanding")
    if revenue is None or multiple is None or not shares:
        return _null_result(True)
    multiple = min(multiple, EV_SALES_CAP)
    net_debt = fin.get("net_debt") or 0
    scenarios = {k: _scenario_ev_multiple(revenue, growth[k], multiple, net_debt, shares) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- P/E (justified) -----------------------------------------------------------
def calc_pe(fin: dict, growth: dict) -> dict:
    eps = fin.get("eps_ttm")
    payout = fin.get("payout_ratio")
    if eps is None or eps <= 0 or payout is None:
        return _null_result(True)

    def scenario_pe(g: float) -> float:
        capped_g = min(g, DISCOUNT_RATE - 0.01)
        pe = payout / (DISCOUNT_RATE - capped_g) if capped_g > 0 else payout / DISCOUNT_RATE
        return _apply_mos(eps * max(pe, 1))

    scenarios = {k: scenario_pe(growth[k]) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- DDM (Gordon growth) -------------------------------------------------------
def calc_ddm(fin: dict, growth: dict) -> dict:
    div = fin.get("dividend_rate")
    if div is None or div <= 0:
        return _null_result(True)

    def scenario_ddm(g: float) -> float | None:
        capped_g = min(g, DISCOUNT_RATE - 0.01)
        if DISCOUNT_RATE <= capped_g:
            return None
        return _apply_mos(div * (1 + capped_g) / (DISCOUNT_RATE - capped_g))

    scenarios = {k: scenario_ddm(growth[k]) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- P/B (justified) -----------------------------------------------------------
def calc_pb(fin: dict) -> dict:
    bvps = fin.get("book_value_per_share")
    roe = fin.get("return_on_equity")
    if bvps is None or roe is None:
        return _null_result(False)
    justified_pb = roe / DISCOUNT_RATE
    fv = _apply_mos(bvps * max(justified_pb, 0.1))
    return {"scenarios": {k: fv for k in SCENARIO_KEYS}, "fair_value": fv, "weight": 0.0, "has_scenarios": False}


# -- RIM (residual income) -----------------------------------------------------
def calc_rim(fin: dict, growth: dict) -> dict:
    bvps = fin.get("book_value_per_share")
    eps = fin.get("eps_ttm")
    if bvps is None or eps is None:
        return _null_result(True)
    coe = fin.get("cost_of_equity") or 0.10
    roe = eps / bvps if bvps > 0 else 0

    def scenario_rim(g: float) -> float:
        total = 0.0
        bv = bvps
        for t in range(1, HORIZON + 1):
            bv_prev = bv
            bv = bv * (1 + g)
            total += _pv(bv_prev * (roe - coe), coe, t)
        return _apply_mos(bvps + total)

    scenarios = {k: scenario_rim(growth[k]) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- SOTP (EV/EBITDA with 15% conglomerate discount) ---------------------------
def calc_sotp(fin: dict) -> dict:
    ebitda = fin.get("ebitda_ttm")
    multiple = fin.get("ev_ebitda")
    shares = fin.get("shares_outstanding")
    if ebitda is None or multiple is None or not shares:
        return _null_result(False)
    multiple = min(multiple, EV_EBITDA_CAP)
    net_debt = fin.get("net_debt") or 0
    ev = ebitda * multiple
    fv = _apply_mos((ev - net_debt) / shares * 0.85)
    return {"scenarios": {k: fv for k in SCENARIO_KEYS}, "fair_value": fv, "weight": 0.0, "has_scenarios": False}


# -- NAV (book value adjusted for net debt per share) --------------------------
def calc_nav(fin: dict) -> dict:
    bvps = fin.get("book_value_per_share")
    shares = fin.get("shares_outstanding")
    if bvps is None or not shares:
        return _null_result(False)
    net_debt = fin.get("net_debt") or 0
    fv = _apply_mos(bvps - net_debt / shares)
    return {"scenarios": {k: fv for k in SCENARIO_KEYS}, "fair_value": fv, "weight": 0.0, "has_scenarios": False}


# -- composite -----------------------------------------------------------------
def composite(results: dict) -> float | None:
    """Weighted average over results whose fair_value is not None and weight > 0."""
    total = 0.0
    total_weight = 0.0
    for r in results.values():
        if r.get("fair_value") is not None and r.get("weight", 0) > 0:
            total += r["fair_value"] * r["weight"]
            total_weight += r["weight"]
    return total / total_weight if total_weight > 0 else None
