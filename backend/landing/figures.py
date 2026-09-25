"""Reader-facing figures for the breakdown's Data column.

The engines hand back bare floats in whatever unit their source uses — a Quality
margin arrives as 31.9 (already percent), a Reward/Risk growth rate as 0.164 (a
fraction), a debt-to-equity as 78.4 (yfinance's percent). Printed as-is, the Data
column reads "0.164" beside "31.9" and a visitor cannot tell a ratio from a
percentage. Every figure is therefore formatted here, next to the knowledge of what
it measures, and the frontend prints the string it is given.

Formatting only: nothing here maps a figure to a score (spec section 8 rule 3).
"""
from __future__ import annotations

import math

MINUS = "−"  # a typographic minus, as the mock renders it


def _ok(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _num(v: float) -> str:
    """One decimal under 10, whole numbers above — "0.4", "8.8", "55"."""
    text = f"{abs(v):.1f}" if abs(v) < 10 else f"{abs(v):.0f}"
    if float(text) == 0:
        return "0"
    return (MINUS if v < 0 else "") + text


def _signed(v: float) -> str:
    text = _num(v)
    return text if text.startswith(MINUS) or text == "0" else "+" + text


def pct(v) -> str | None:
    return f"{_num(v)}%" if _ok(v) else None


def signed_pct(v) -> str | None:
    return f"{_signed(v)}%" if _ok(v) else None


def pp(v) -> str | None:
    return f"{_signed(v)} pp" if _ok(v) else None


def times(v) -> str | None:
    return f"{_num(v)}×" if _ok(v) else None


def leverage(v) -> str | None:
    """Net debt over a flow: a non-positive ratio from a positive denominator means
    the company holds more cash than debt."""
    if not _ok(v):
        return None
    return "Net cash" if v <= 0 else times(v)


# Quality metric labels exactly as screener/scoring.py builds them.
_QUALITY = {
    "Revenue growth (3-yr)": lambda v: f"{_signed(v)}% / yr" if _ok(v) else None,
    "EPS growth (3-yr)": lambda v: f"{_signed(v)}% / yr" if _ok(v) else None,
    "FCF growth (3-yr)": lambda v: f"{_signed(v)}% / yr" if _ok(v) else None,
    "FCF margin": pct,
    "Operating margin": pct,
    "Operating-margin trajectory": pp,
    "Gross margin": pct,
    "ROIC (trailing)": pct,
    "ROIC (5-yr average)": pct,
    "Economic spread (ROIC - WACC)": pp,
    "Return on tangible equity": pct,
    "Net debt / EBITDA": leverage,
    "Net debt / FCF": leverage,
    "Operating cash flow / capex": times,
    "Share-count trend (3-yr)": lambda v: f"{_signed(v)}% / yr" if _ok(v) else None,
    "Stock comp % of revenue": pct,
    "Earnings quality (FCF / net income)": times,
    "Insider ownership": pct,
    "Shareholder yield": pct,
}


def quality_figure(label: str | None, raw) -> str | None:
    fmt = _QUALITY.get(label or "")
    if fmt is not None:
        return fmt(raw)
    return _num(raw) if _ok(raw) else None


def _frac(v) -> float | None:
    return v * 100 if _ok(v) else None


# Reward/Risk raw values keyed by the SOURCE that scored the slot, because a slot's
# fallback chain can land on a source with a different unit (valuation: PEG, or an
# earnings yield when there is no PEG).
_RR = {
    "peg": lambda v: f"PEG {_num(v)}" if _ok(v) else None,
    "earnings_yield": lambda v: f"Earnings yield {pct(_frac(v))}" if _ok(v) else None,
    "ps_yield": lambda v: f"Sales yield {pct(_frac(v))}" if _ok(v) else None,
    "revenue_growth": lambda v: f"Revenue {signed_pct(_frac(v))}" if _ok(v) else None,
    "earnings_growth": lambda v: f"Earnings {signed_pct(_frac(v))}" if _ok(v) else None,
    "revenue_growth_stmt": lambda v: f"Revenue {signed_pct(_frac(v))} (annual)" if _ok(v) else None,
    "roe": lambda v: f"ROE {pct(_frac(v))}" if _ok(v) else None,
    "roa": lambda v: f"ROA {pct(_frac(v))}" if _ok(v) else None,
    "analyst_upside": lambda v: f"{signed_pct(_frac(v))} to target" if _ok(v) else None,
    "discount": lambda v: f"{pct(_frac(v))} below high" if _ok(v) else None,
    "rsi": lambda v: f"{v:.0f}" if _ok(v) else None,
    "debt_to_equity": lambda v: f"D/E {_num(v / 100)}" if _ok(v) else None,
    "net_debt_ebitda": lambda v: (f"{leverage(v)} EBITDA" if _ok(v) and v > 0 else leverage(v)),
    "operating_margin": lambda v: f"{pct(_frac(v))} op margin" if _ok(v) else None,
    "operating_margin_stmt": lambda v: f"{pct(_frac(v))} op margin (annual)" if _ok(v) else None,
    "profit_margin": lambda v: f"{pct(_frac(v))} net margin" if _ok(v) else None,
    "current_ratio": lambda v: f"Current {_num(v)}" if _ok(v) else None,
    "quick_ratio": lambda v: f"Quick {_num(v)}" if _ok(v) else None,
    "volatility": lambda v: f"{pct(_frac(v))} ann." if _ok(v) else None,
    "trend": lambda v: f"{signed_pct(_frac(v))} vs 200-day" if _ok(v) else None,
    "beta": lambda v: f"β {v:.2f}" if _ok(v) else None,
}


def rr_figure(source: str | None, raw) -> str | None:
    fmt = _RR.get(source or "")
    if fmt is not None:
        return fmt(raw)
    return _num(raw) if _ok(raw) else None


def moat_figure(code: str, value) -> str | None:
    """The input behind one moat pillar, as moat/scoring.py records it in
    breakdown["inputs"]. Percent/pp units throughout, like the Quality metrics."""
    if code == "A1":
        return pct(value)
    if code == "A2":
        return pp(value)
    if code == "B1":
        if not isinstance(value, dict):
            return None
        frac, years = value.get("fraction"), value.get("years")
        if not _ok(frac) or not years:
            return None
        return f"{round(frac * years)} of {years} yrs"
    if code == "B2":
        return f"{_num(value * 100)}% variation" if _ok(value) else None
    if code == "B3":
        return f"{pp(value)} trend" if _ok(value) else None
    if code == "C1":
        return f"{pct(value * 100)} of EBITDA" if _ok(value) else None
    return None
