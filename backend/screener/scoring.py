from __future__ import annotations
from screener.models import ScreenerMetrics


def score_high(value: float | None, bands: list[tuple[float, float]], below: float) -> float | None:
    if value is None:
        return None
    for thr, sc in bands:
        if value >= thr:
            return sc
    return below


def score_low(value: float | None, bands: list[tuple[float, float]], above: float) -> float | None:
    if value is None:
        return None
    for thr, sc in bands:
        if value <= thr:
            return sc
    return above


def leverage_score(r: float | None, pivot: float | None) -> float | None:
    if r is None or pivot is None:
        return None
    if r <= 0:
        return 10.0
    if r <= 0.5 * pivot:
        return 9.0
    if r <= pivot:
        return 7.0
    if r <= 1.4 * pivot:
        return 4.5
    if r <= 1.8 * pivot:
        return 2.0
    return 0.0
