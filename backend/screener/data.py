from __future__ import annotations
from services.yahoo import fetch_ticker_info
from services.statements import (
    fetch_income_stmt, fetch_balance_sheet, fetch_cashflow_annual,
    fetch_treasury_10y, fetch_price_monthly,
)
from services.yf_pool import run_yf
from screener.models import ScreenerInputs, StatementSeries


async def fetch_screener_inputs(ticker: str) -> ScreenerInputs | None:
    t = ticker.upper()
    try:
        info = await fetch_ticker_info(t)
    except Exception:
        return None

    def _blocking():
        return {
            "income": fetch_income_stmt(t),
            "balance": fetch_balance_sheet(t),
            "cashflow": fetch_cashflow_annual(t),
            "risk_free": fetch_treasury_10y(),
            "price": fetch_price_monthly(t),
        }

    d = await run_yf(_blocking)
    return ScreenerInputs(
        ticker=t,
        info=info,
        income=StatementSeries.from_dict(d["income"]),
        balance=StatementSeries.from_dict(d["balance"]),
        cashflow=StatementSeries.from_dict(d["cashflow"]),
        price_monthly=d["price"],
        risk_free=d["risk_free"],
    )
