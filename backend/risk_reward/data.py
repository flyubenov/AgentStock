from __future__ import annotations
from services.yahoo import fetch_ticker_info
from services.statements import fetch_price_daily, fetch_income_stmt
from services.yf_pool import run_yf
from screener.models import StatementSeries
from risk_reward.config import CONFIG
from risk_reward.indicators import sma, rsi, realized_vol
from risk_reward.models import RiskRewardInputs


def _statement_growth_and_margin(income: dict | None) -> tuple[float | None, float | None]:
    """Statement-annual revenue YoY (fraction) and operating margin (Operating
    Income / Total Revenue, fraction) — same basis and math as
    screener/metrics.py's revenue_growth_yoy / op_margin (there in percent; here
    as a fraction to match R-R's anchor units). Feeds the gap guard in
    scoring.py, not a primary source — see [[iren-rr-stmt-gap-guard]]."""
    inc = StatementSeries.from_dict(income)
    if inc is None:
        return None, None
    growth = None
    rev_series = inc.series("Total Revenue")
    if len(rev_series) >= 2 and rev_series[0] is not None and rev_series[1]:
        growth = rev_series[0] / rev_series[1] - 1.0
    margin = None
    oi = inc.latest("Operating Income")
    revenue = inc.latest("Total Revenue")
    if oi is not None and revenue:
        margin = oi / revenue
    return growth, margin


async def fetch_risk_reward_inputs(ticker: str) -> RiskRewardInputs | None:
    t = ticker.upper()
    try:
        info = await fetch_ticker_info(t)
    except Exception:
        return None

    closes = await run_yf(fetch_price_daily, t, CONFIG.history_period)
    last_close = closes[-1] if closes else None
    price = info.get("currentPrice") or info.get("regularMarketPrice") or last_close
    high_52w = info.get("fiftyTwoWeekHigh") or (max(closes) if closes else None)
    income = await run_yf(fetch_income_stmt, t)
    revenue_growth_stmt, operating_margin_stmt = _statement_growth_and_margin(income)

    return RiskRewardInputs(
        ticker=t, info=info,
        company_name=info.get("shortName") or info.get("longName"),
        price=price, high_52w=high_52w,
        ma_200=sma(closes, 200), ma_50=sma(closes, 50),
        rsi=rsi(closes, CONFIG.rsi_period),
        volatility=realized_vol(closes, CONFIG.vol_annualization),
        revenue_growth_stmt=revenue_growth_stmt,
        operating_margin_stmt=operating_margin_stmt,
    )
