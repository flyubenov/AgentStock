from __future__ import annotations
from collections.abc import Sequence
from screener.models import ScreenerInputs, ScreenerMetrics, StatementSeries


def cagr(start: float | None, end: float | None, years: int) -> float | None:
    if start is None or end is None or years <= 0:
        return None
    if start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def series_cagr(series: list[float | None], span: int) -> float | None:
    if not series or len(series) < 2:
        return None
    end = series[0]
    idx = min(span, len(series) - 1)
    return cagr(series[idx], end, idx)


def price_cagr(monthly: Sequence[float], years: int) -> float | None:
    if not monthly or len(monthly) < 2:
        return None
    end = monthly[-1]
    months_back = years * 12
    idx = max(0, len(monthly) - 1 - months_back)
    span_years = (len(monthly) - 1 - idx) / 12
    if span_years <= 0:
        return None
    return _cagr_frac(monthly[idx], end, span_years)


def _cagr_frac(start: float | None, end: float | None, years: float) -> float | None:
    if start is None or end is None or years <= 0 or start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def pct(x: float | None) -> float | None:
    return None if x is None else x * 100.0
