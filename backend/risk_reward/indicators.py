from __future__ import annotations
import math
import statistics


def sma(closes, period: int) -> float | None:
    if not closes or len(closes) < period or period <= 0:
        return None
    window = closes[-period:]
    return float(statistics.fmean(window))


def rsi(closes, period: int = 14) -> float | None:
    """Wilder's RSI. Needs at least period+1 closes. Returns 100 when there are no
    losses over the smoothed window, else 100 - 100/(1+RS)."""
    if not closes or len(closes) < period + 1:
        return None
    gains, losses = [], []
    for prev, cur in zip(closes, closes[1:]):
        change = cur - prev
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = statistics.fmean(gains[:period])
    avg_loss = statistics.fmean(losses[:period])
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def realized_vol(closes, annualization: float = 252.0) -> float | None:
    """Annualized standard deviation of daily log returns. Needs >= 2 closes."""
    if not closes or len(closes) < 2:
        return None
    returns = []
    for prev, cur in zip(closes, closes[1:]):
        if prev and prev > 0 and cur and cur > 0:
            returns.append(math.log(cur / prev))
    if len(returns) < 2:
        return None
    if len(set(returns)) == 1:
        sd = 0.0
    else:
        sd = statistics.stdev(returns)
    return float(sd * math.sqrt(annualization))
