"""
Calculator 1: DCF (40%), EV/EBITDA (25%), P/E (15%), P/FCF (15%), DDM (15% if yield>=1.5%).
Scenarios: Optimistic / Realistic / Pessimistic. MOS: 10%.
"""
from __future__ import annotations
import argparse, asyncio, json
from models import FairValueResult
from services.yahoo import fetch_ticker_info, extract_financials

MOS = 0.90
DISCOUNT_RATE = 0.10
TERMINAL_GROWTH = 0.03
HORIZON = 10


def pv(cf: float, rate: float, year: int) -> float:
    return cf / (1 + rate) ** year


def dcf_equity(fcf: float, growth: float, net_debt: float, shares: float) -> float:
    total = 0.0
    cf = fcf
    for t in range(1, HORIZON + 1):
        cf *= (1 + growth)
        total += pv(cf, DISCOUNT_RATE, t)
    tv = cf * (1 + TERMINAL_GROWTH) / (DISCOUNT_RATE - TERMINAL_GROWTH)
    total += pv(tv, DISCOUNT_RATE, HORIZON)
    return (total - net_debt) / shares


def ev_multiple(base: float, growth: float, multiple: float, net_debt: float, shares: float) -> float:
    projected = base * (1 + growth) ** HORIZON
    future_ev = projected * multiple
    return (future_ev - net_debt) / shares / (1 + DISCOUNT_RATE) ** HORIZON


def pe_justified(eps: float, growth: float, payout: float) -> float:
    capped = min(growth, DISCOUNT_RATE - 0.01)
    pe = payout / (DISCOUNT_RATE - capped) if capped > 0 else payout / DISCOUNT_RATE
    return eps * max(pe, 1)


def pfcf_value(fcf_per_share: float, growth: float, payout: float = 0.8) -> float:
    capped = min(growth, DISCOUNT_RATE - 0.01)
    multiple = payout / (DISCOUNT_RATE - capped) if capped > 0 else payout / DISCOUNT_RATE
    return fcf_per_share * max(multiple, 1)


def ddm(div: float, growth: float) -> float | None:
    capped = min(growth, DISCOUNT_RATE - 0.01)
    if DISCOUNT_RATE <= capped:
        return None
    return div * (1 + capped) / (DISCOUNT_RATE - capped)


def _scenarios(fin: dict) -> tuple[float, float, float]:
    base_growth = fin["earnings_growth"] or fin["revenue_growth"] or 0.07
    return (
        min(base_growth + 0.05, 0.30),   # optimistic
        base_growth,                       # realistic
        max(base_growth - 0.04, 0.01),    # pessimistic
    )


async def run(ticker: str) -> FairValueResult:
    try:
        info = await fetch_ticker_info(ticker)
        fin = extract_financials(info)

        fcf = fin["fcf_ttm"]
        shares = fin["shares_outstanding"]
        net_debt = fin["net_debt"] or 0
        ebitda = fin["ebitda_ttm"]
        eps = fin["eps_ttm"]
        payout = fin["payout_ratio"] or 0.40
        div_rate = fin["dividend_rate"]
        div_yield = fin["dividend_yield"] or 0
        ev_ebitda_m = info.get("enterpriseToEbitda") or 12.0
        trailing_pe = fin["trailing_pe"] or 15.0

        opt_g, real_g, pess_g = _scenarios(fin)
        breakdown: dict = {}
        scenario_values: dict[str, list[float]] = {"optimistic": [], "realistic": [], "pessimistic": []}
        weights_used: dict[str, float] = {}

        def add_method(name: str, weight: float, opt: float | None, real: float | None, pess: float | None):
            if any(v is not None and v > 0 for v in [opt, real, pess]):
                breakdown[name] = {
                    "weight": weight,
                    "optimistic": round(opt * MOS, 2) if opt else None,
                    "realistic": round(real * MOS, 2) if real else None,
                    "pessimistic": round(pess * MOS, 2) if pess else None,
                }
                weights_used[name] = weight
                for key, val in [("optimistic", opt), ("realistic", real), ("pessimistic", pess)]:
                    if val and val > 0:
                        scenario_values[key].append(val * weight)

        # DCF
        if fcf and shares and fcf > 0:
            add_method("dcf", 0.40,
                dcf_equity(fcf, opt_g, net_debt, shares),
                dcf_equity(fcf, real_g, net_debt, shares),
                dcf_equity(fcf, pess_g, net_debt, shares),
            )

        # EV/EBITDA
        if ebitda and shares and ebitda > 0:
            add_method("ev_ebitda", 0.25,
                ev_multiple(ebitda, opt_g, ev_ebitda_m, net_debt, shares),
                ev_multiple(ebitda, real_g, ev_ebitda_m, net_debt, shares),
                ev_multiple(ebitda, pess_g, ev_ebitda_m, net_debt, shares),
            )

        # P/E
        if eps and eps > 0:
            add_method("pe", 0.15,
                pe_justified(eps, opt_g, payout),
                pe_justified(eps, real_g, payout),
                pe_justified(eps, pess_g, payout),
            )

        # P/FCF
        if fcf and shares and fcf > 0:
            fcf_per_share = fcf / shares
            add_method("p_fcf", 0.15,
                pfcf_value(fcf_per_share, opt_g),
                pfcf_value(fcf_per_share, real_g),
                pfcf_value(fcf_per_share, pess_g),
            )

        # DDM (only if yield >= 1.5%)
        if div_rate and div_yield >= 0.015:
            add_method("ddm", 0.15,
                ddm(div_rate, opt_g),
                ddm(div_rate, real_g),
                ddm(div_rate, pess_g),
            )

        if not weights_used:
            return FairValueResult(
                ticker=ticker, method_name="Calculator 1",
                status="failed", error="Insufficient data",
                methods_breakdown={}, data_sources=["yfinance"],
            )

        total_weight = sum(weights_used.values())
        blended: dict[str, float | None] = {}
        for sc in ["optimistic", "realistic", "pessimistic"]:
            vals = scenario_values[sc]
            blended[sc] = sum(vals) / total_weight if vals else None

        valid = [v for v in blended.values() if v is not None]
        pre_mos = sum(valid) / len(valid) if valid else None

        return FairValueResult(
            ticker=ticker,
            method_name="Calculator 1",
            pre_mos_value=round(pre_mos, 2) if pre_mos else None,
            post_mos_value=round(pre_mos * MOS, 2) if pre_mos else None,
            methods_breakdown=breakdown,
            data_sources=["yfinance"],
        )

    except Exception as e:
        return FairValueResult(
            ticker=ticker, method_name="Calculator 1",
            status="failed", error=str(e),
            methods_breakdown={}, data_sources=["yfinance"],
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    args = parser.parse_args()
    result = asyncio.run(run(args.ticker))
    print(json.dumps(result.model_dump(), indent=2))
