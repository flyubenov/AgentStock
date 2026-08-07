from __future__ import annotations


def score_metric(raw, a5: float, a3: float, a1: float) -> float | None:
    """Map a raw metric value to a score in [1, 5] by piecewise-linear interpolation
    across the breakpoints [(a1, 1), (a3, 3), (a5, 5)]. Direction-agnostic: works
    whether higher raw is better (reward) or worse (danger). Values beyond the
    extreme anchors saturate. None/NaN/non-numeric -> None (metric is dropped)."""
    if raw is None:
        return None
    try:
        x = float(raw)
    except (TypeError, ValueError):
        return None
    if x != x:  # NaN
        return None
    pts = sorted([(float(a1), 1.0), (float(a3), 3.0), (float(a5), 5.0)])
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (x0, s0), (x1, s1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return s1
            return s0 + (s1 - s0) * (x - x0) / (x1 - x0)
    return None  # unreachable given the bounds checks above
