"""Pure statistics over the per-year series ScreenerMetrics stores. No fetching,
no ScreenerMetrics dependency — just lists of floats — so the durability math
is trivially testable and reusable."""
from __future__ import annotations
import statistics


def mean(vals: list[float]) -> float | None:
    return sum(vals) / len(vals) if vals else None


def pstdev(vals: list[float]) -> float | None:
    return statistics.pstdev(vals) if vals else None


def persistence_fraction(series: list[float], hurdle: float | None) -> float | None:
    """Fraction of observations strictly above `hurdle`. This is the durability
    core: how often the business actually out-earned its cost of capital."""
    if not series or hurdle is None:
        return None
    return sum(1 for v in series if v > hurdle) / len(series)


def coef_of_variation(series: list[float]) -> float | None:
    """Population CoV = stdev / mean. Undefined for a non-positive mean (the
    economic-profit gate covers those names), so returns None there."""
    if not series:
        return None
    mu = mean(series)
    if mu is None or mu <= 0:
        return None
    return pstdev(series) / mu
