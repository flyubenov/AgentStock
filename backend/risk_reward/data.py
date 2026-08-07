from __future__ import annotations
from services.yahoo import fetch_ticker_info
from services.statements import fetch_price_daily
from services.yf_pool import run_yf
from risk_reward.config import CONFIG
from risk_reward.indicators import sma, rsi, realized_vol
from risk_reward.models import RiskRewardInputs


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

    return RiskRewardInputs(
        ticker=t, info=info,
        company_name=info.get("shortName") or info.get("longName"),
        price=price, high_52w=high_52w,
        ma_200=sma(closes, 200), ma_50=sma(closes, 50),
        rsi=rsi(closes, CONFIG.rsi_period),
        volatility=realized_vol(closes, CONFIG.vol_annualization),
    )
