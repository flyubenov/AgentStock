"""
Fair value via: Revised Graham Formula, P/E Multiples, EV/EBITDA.
Weights: Graham 40%, P/E 30%, EV/EBITDA 30%. MOS: 10%.
"""
from __future__ import annotations
import argparse, asyncio, json
from models import FairValueResult
from services.yahoo import fetch_ticker_info, extract_financials

MOS = 0.90
DISCOUNT_RATE = 0.10


def _graham(eps: float, growth_pct: float, aaa_yield: float = 4.4) -> float | None:
    """Revised Graham Formula: V = EPS × (8.5 + 2g) × (4.4 / Y)"""
    if eps <= 0:
        return None
    current_aaa = aaa_yield  # caller should pass current yield; default 4.4 as per original
    return eps * (8.5 + 2 * growth_pct) * (4.4 / current_aaa)


def _pe_fair_value(eps: float, sector_pe: float) -> float:
    return eps * sector_pe


def _ev_ebitda_fv(ebitda: float, multiple: float, net_debt: float, shares: float) -> float:
    return (ebitda * multiple - net_debt) / shares


async def run(ticker: str) -> FairValueResult:
    try:
        info = await fetch_ticker_info(ticker)
        fin = extract_financials(info)

        eps = fin["eps_ttm"]
        ebitda = fin["ebitda_ttm"]
        shares = fin["shares_outstanding"]
        net_debt = fin["net_debt"] or 0
        growth_rate = (fin["earnings_growth"] or fin["revenue_growth"] or 0.05) * 100
        trailing_pe = fin["trailing_pe"]
        forward_pe = fin["forward_pe"]

        breakdown: dict = {}
        values: list[float] = []

        # Graham
        if eps and eps > 0:
            g = min(max(growth_rate, 0), 20)
            graham_raw = _graham(eps, g)
            if graham_raw and graham_raw > 0:
                breakdown["graham"] = {"pre_mos": round(graham_raw, 2), "post_mos": round(graham_raw * MOS, 2)}
                values.append(graham_raw)

        # P/E multiples
        sector_pe = trailing_pe or forward_pe or 15.0
        if eps and eps > 0 and sector_pe and sector_pe > 0:
            pe_raw = _pe_fair_value(eps, min(sector_pe, 40))
            breakdown["pe_multiples"] = {"pre_mos": round(pe_raw, 2), "post_mos": round(pe_raw * MOS, 2)}
            values.append(pe_raw)

        # EV/EBITDA
        ev_ebitda_multiple = info.get("enterpriseToEbitda") or 12.0
        if ebitda and ebitda > 0 and shares and shares > 0 and ev_ebitda_multiple > 0:
            ev_raw = _ev_ebitda_fv(ebitda, ev_ebitda_multiple, net_debt, shares)
            if ev_raw > 0:
                breakdown["ev_ebitda"] = {"pre_mos": round(ev_raw, 2), "post_mos": round(ev_raw * MOS, 2)}
                values.append(ev_raw)

        if not values:
            return FairValueResult(
                ticker=ticker, method_name="Gemini FV",
                status="failed", error="Insufficient data for any sub-method",
                methods_breakdown={}, data_sources=["yfinance"],
            )

        pre_mos = sum(values) / len(values)
        post_mos = pre_mos * MOS

        return FairValueResult(
            ticker=ticker,
            method_name="Gemini FV",
            pre_mos_value=round(pre_mos, 2),
            post_mos_value=round(post_mos, 2),
            methods_breakdown=breakdown,
            data_sources=["yfinance"],
        )

    except Exception as e:
        return FairValueResult(
            ticker=ticker, method_name="Gemini FV",
            status="failed", error=str(e),
            methods_breakdown={}, data_sources=["yfinance"],
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    args = parser.parse_args()
    result = asyncio.run(run(args.ticker))
    print(json.dumps(result.model_dump(), indent=2))
