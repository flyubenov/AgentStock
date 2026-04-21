"""
Calculator 2: DCF/WACC (30%), P/E (20%), EV/EBITDA (20%), EV/Sales (15%), PEG (0% default), RIM/EVA (15%).
MOS: 10%.
"""
from __future__ import annotations
import argparse, asyncio, json
from models import FairValueResult
from services.yahoo import fetch_ticker_info, extract_financials

MOS = 0.90
TERMINAL_GROWTH = 0.03
HORIZON = 10


def pv(cf: float, rate: float, year: int) -> float:
    return cf / (1 + rate) ** year


def _wacc(info: dict, fin: dict) -> float:
    beta = info.get("beta") or 1.0
    beta = max(0.5, min(beta, 2.5))
    cost_of_equity = 0.03 + beta * 0.06   # CAPM: rf=3%, ERP=6%
    market_cap = fin["market_cap"] or 1
    total_debt = info.get("totalDebt") or 0
    total_value = market_cap + total_debt
    equity_weight = market_cap / total_value
    debt_weight = total_debt / total_value
    tax_rate = info.get("effectiveTaxRate") or 0.21
    interest_expense = abs(info.get("interestExpense") or 0)
    cost_of_debt = (interest_expense / total_debt * (1 - tax_rate)) if total_debt > 0 else 0.04
    return equity_weight * cost_of_equity + debt_weight * cost_of_debt


def dcf_wacc(fcf: float, growth: float, wacc: float, net_debt: float, shares: float) -> float:
    total = 0.0
    cf = fcf
    for t in range(1, HORIZON + 1):
        cf *= (1 + growth)
        total += pv(cf, wacc, t)
    tv = cf * (1 + TERMINAL_GROWTH) / (wacc - TERMINAL_GROWTH)
    total += pv(tv, wacc, HORIZON)
    return (total - net_debt) / shares


def rim(bv: float, eps: float, cost_eq: float, growth: float) -> float:
    roe = eps / bv if bv > 0 else 0
    total_pv = 0.0
    bv_t = bv
    for t in range(1, HORIZON + 1):
        ri = bv_t * (roe - cost_eq)
        total_pv += pv(ri, cost_eq, t)
        bv_t *= (1 + growth)
    return bv + total_pv


def ev_multiple(base: float, growth: float, multiple: float, net_debt: float, shares: float) -> float:
    projected = base * (1 + growth) ** HORIZON
    return (projected * multiple - net_debt) / shares / (1 + 0.10) ** HORIZON


def pe_fv(eps: float, pe: float) -> float:
    return eps * min(pe, 40)


def peg_fv(eps: float, growth_pct: float) -> float | None:
    if growth_pct <= 0:
        return None
    return eps * growth_pct  # PEG=1 fair value: P/E = growth rate


async def run(ticker: str) -> FairValueResult:
    try:
        info = await fetch_ticker_info(ticker)
        fin = extract_financials(info)

        fcf = fin["fcf_ttm"]
        shares = fin["shares_outstanding"]
        net_debt = fin["net_debt"] or 0
        ebitda = fin["ebitda_ttm"]
        revenue = fin["revenue_ttm"]
        eps = fin["eps_ttm"]
        bv = fin["book_value_per_share"]
        raw_growth = fin["earnings_growth"] or fin["revenue_growth"] or 0.07
        # Cap to [2%, 20%] — yfinance quarterly YoY figures can be temporarily very high
        growth = max(0.02, min(float(raw_growth), 0.20))
        # Cap exit multiples to prevent compounded forward projections from inflating values
        ev_ebitda_m = min(info.get("enterpriseToEbitda") or 12.0, 20.0)
        ev_sales_m = min(info.get("enterpriseToRevenue") or 3.0, 8.0)
        trailing_pe = min(fin["trailing_pe"] or 15.0, 35.0)
        growth_pct = growth * 100

        wacc = _wacc(info, fin)
        cost_eq = 0.03 + (info.get("beta") or 1.0) * 0.06
        breakdown: dict = {}
        values: list[tuple[float, float]] = []

        def add(name: str, weight: float, raw: float | None):
            if raw and raw > 0:
                breakdown[name] = {"weight": weight, "pre_mos": round(raw, 2), "post_mos": round(raw * MOS, 2)}
                values.append((raw, weight))

        # DCF/WACC
        if fcf and shares and fcf > 0 and wacc > TERMINAL_GROWTH:
            add("dcf_wacc", 0.30, dcf_wacc(fcf, growth, wacc, net_debt, shares))

        # P/E
        if eps and eps > 0 and trailing_pe > 0:
            add("pe", 0.20, pe_fv(eps, trailing_pe))

        # EV/EBITDA
        if ebitda and shares and ebitda > 0:
            add("ev_ebitda", 0.20, ev_multiple(ebitda, growth, ev_ebitda_m, net_debt, shares))

        # EV/Sales
        if revenue and shares and revenue > 0:
            add("ev_sales", 0.15, ev_multiple(revenue, growth, ev_sales_m, net_debt, shares))

        # RIM/EVA
        if bv and eps and bv > 0:
            add("rim", 0.15, rim(bv, eps, cost_eq, growth))

        # PEG (bonus, 0% default weight but shown in breakdown)
        peg = peg_fv(eps, growth_pct) if eps and eps > 0 else None
        if peg and peg > 0:
            breakdown["peg"] = {"weight": 0, "pre_mos": round(peg, 2), "post_mos": round(peg * MOS, 2)}

        if not values:
            return FairValueResult(
                ticker=ticker, method_name="Calculator 2",
                status="failed", error="Insufficient data",
                methods_breakdown={}, data_sources=["yfinance"],
            )

        total_weight = sum(w for _, w in values)
        pre_mos = sum(v * w for v, w in values) / total_weight

        return FairValueResult(
            ticker=ticker,
            method_name="Calculator 2",
            pre_mos_value=round(pre_mos, 2),
            post_mos_value=round(pre_mos * MOS, 2),
            methods_breakdown=breakdown,
            data_sources=["yfinance"],
        )

    except Exception as e:
        return FairValueResult(
            ticker=ticker, method_name="Calculator 2",
            status="failed", error=str(e),
            methods_breakdown={}, data_sources=["yfinance"],
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    args = parser.parse_args()
    result = asyncio.run(run(args.ticker))
    print(json.dumps(result.model_dump(), indent=2))
