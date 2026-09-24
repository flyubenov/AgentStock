from __future__ import annotations

# Spec section 8 rule 5: no internal identifier ever reaches the UI. Anything not
# mapped here still gets Title-Cased rather than leaking an ALL_CAPS code.
PROFILE_LABELS = {
    "TECH_GROWTH": "Tech / Growth",
    "BALANCED": "Balanced",
    "DEFENSIVE_INCOME": "Defensive / Income",
    "INDUSTRIAL_CYCLICAL": "Industrial / Cyclical",
    "FINANCIALS": "Financials",
    "REIT": "REIT",
}

STOCK_TYPE_LABELS = {
    "MEGA_CAP": "Mega Cap", "LARGE_CAP": "Large Cap", "MID_CAP": "Mid Cap",
    "GROWTH": "Growth", "EARLY_GROWTH": "Early Growth", "DIVIDEND": "Dividend Payer",
    "CYCLICAL": "Cyclical", "FINANCIAL": "Lender / Insurer",
    "ASSET_HEAVY": "Asset-Heavy",
}

METHOD_LABELS = {
    "dcf": "Discounted cash flow", "fcfe": "Free cash flow to equity",
    "ev_ebitda": "EV / EBITDA", "pe": "P / E", "ev_sales": "EV / Sales",
    "ddm": "Dividend discount", "pb": "Price / book", "rim": "Residual income",
    "nav": "Net asset value", "sotp": "Sum of the parts",
}

# Moat pillar codes. Concept only — the point bands stay internal (spec section 8 rule 3).
MOAT_FACTOR_LABELS = {
    "A1": "ROIC level", "A2": "Economic spread (ROIC - WACC)",
    "B1": "Persistence of economic profit", "B2": "Consistency of returns",
    "B3": "Margin durability", "C1": "Free-cash-flow conversion",
}

RR_FACTOR_LABELS = {
    "valuation": "Valuation", "growth": "Growth", "profitability": "Profitability",
    "analyst_upside": "Analyst upside", "discount": "Discount to 52-week high",
    "rsi": "RSI (14-day)",
    "leverage": "Leverage", "burn": "Burn / margin", "liquidity": "Liquidity",
    "volatility": "Volatility", "trend": "Trend vs 200-day", "beta": "Beta",
}

CATEGORY_LABELS = {
    "I": "Growth & Margins", "II": "Returns on Capital",
    "III": "Balance-Sheet Strength", "IV": "Shareholder Alignment",
}

# The stable internal exclusion vocabulary Task 4's screener.scoring emits on
# MetricDetail.excluded_by (read off backend/screener/scoring.py — do not rename any
# of these there; Tasks 9 and 10 key off this map, not the raw strings). Several read
# as engine jargon and must never reach the page raw. A reason not listed here still
# passes through unmapped (see EXCLUSION_LABELS.get(reason, reason) below) rather than
# degrading to None, so a new calibration added later degrades to readable-enough text
# instead of disappearing.
EXCLUSION_LABELS = {
    "Financials basis": "Not scored for banks & insurers",
    "Heavy-capex FCF exclusion": "Skipped during a heavy capex cycle",
    "Forward-EPS swap": "Skipped — one-off earnings distortion",
    "Dominant fresh-acquisition": "Skipped — recent acquisition distortion",
    "Recent acquisition": "Skipped — recent acquisition",
    "Heavy capex cycle": "Skipped during a heavy capex cycle",
    "Balance-sheet dual-check": "Skipped — balance-sheet cross-check",
    "Not meaningful at negative EBITDA": "Not meaningful (negative EBITDA)",
    "Not meaningful at negative FCF": "Not meaningful (negative FCF)",
}

# orchestrator.batch._run_one tags a subsystem failure with a bare prefix
# ("fair_value: ...", "sheets_write: ...", "screener: ...", "screener_write: ...",
# "risk_reward: ...", "risk_reward_write: ...") followed by the raw exception text.
# That exception text must never reach a public page (fix round 1, item 6) — only the
# prefix is meaningful to a reader, and even that gets rewritten to plain copy. A
# prefix not listed here (a future subsystem) falls back to GENERIC_ERROR_LABEL rather
# than leaking whatever followed its colon.
ERROR_LABELS = {
    "fair_value": "Fair value could not be calculated for this ticker.",
    "screener": "Quality Score could not be calculated for this ticker.",
    "risk_reward": "Reward/Risk could not be calculated for this ticker.",
    "sheets_write": "A result failed to save.",
    "screener_write": "A result failed to save.",
    "risk_reward_write": "A result failed to save.",
}
GENERIC_ERROR_LABEL = "Something went wrong calculating this ticker."

_ALL = {**PROFILE_LABELS, **STOCK_TYPE_LABELS}


def humanize(code: str | None) -> str | None:
    """Map an internal classifier code to its display label, Title-Casing anything
    unmapped so a new engine constant degrades into readable text rather than shouting
    TECH_GROWTH at a visitor."""
    if not code:
        return None
    if code in _ALL:
        return _ALL[code]
    return " ".join(w.capitalize() for w in str(code).replace("-", "_").split("_") if w)
