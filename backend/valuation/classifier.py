from __future__ import annotations

# Keep only phrases that are specifically indicative of a multi-business
# conglomerate or breakup thesis. Generic SEC boilerplate ("together with its
# subsidiaries", "product portfolio", "capital allocation") was pruned because
# it false-positived single-business companies (e.g. KLAC) into CONGLOMERATE.
CONGLOMERATE_KEYWORDS = [
    "spin-off", "spinoff", "breakup", "divestiture",
    "holding company", "conglomerate",
]

CYCLICAL_SECTORS = {"Energy", "Basic Materials"}

# Phrases that mark a yfinance "Financial Services" tag as a mis-classification:
# crypto miners and data-center operators are tagged Financial Services but are
# not balance-sheet / book-value businesses.
NON_FINANCIAL_KEYWORDS = [
    "bitcoin", "cryptocurrency", "crypto", "digital asset",
    "data center", "data centre", "mining", "miner",
]

# Industries where the FINANCIAL valuation methods (P/B + RIM + P/E) genuinely fit —
# balance-sheet lenders / banks / insurers. A name in one of these stays FINANCIAL even
# when it also offers a crypto product (e.g. SoFi's "digital asset trading platform"),
# overriding NON_FINANCIAL_KEYWORDS — which targets crypto miners / data-center operators
# mis-tagged as Financial Services, not real lenders that merely offer crypto.
CORE_FINANCIAL_INDUSTRIES = ("bank", "credit services", "mortgage", "insurance")

# Default method weights per stock type. Keys match the MethodId set:
# dcf, fcfe, ev_ebitda, pe, ev_sales, ddm, pb, rim, sotp, nav.
_TYPE_WEIGHTS: dict[str, dict[str, float]] = {
    "LARGE_CAP":    {"dcf": 0.50, "fcfe": 0.00, "ev_ebitda": 0.35, "pe": 0.15, "ev_sales": 0.00, "ddm": 0.00, "pb": 0.00, "rim": 0.00, "sotp": 0.00, "nav": 0.00},
    "MID_CAP":      {"dcf": 0.45, "fcfe": 0.00, "ev_ebitda": 0.25, "pe": 0.15, "ev_sales": 0.15, "ddm": 0.00, "pb": 0.00, "rim": 0.00, "sotp": 0.00, "nav": 0.00},
    "DIVIDEND":     {"dcf": 0.25, "fcfe": 0.00, "ev_ebitda": 0.00, "pe": 0.25, "ev_sales": 0.00, "ddm": 0.40, "pb": 0.10, "rim": 0.00, "sotp": 0.00, "nav": 0.00},
    "GROWTH":       {"dcf": 0.40, "fcfe": 0.00, "ev_ebitda": 0.20, "pe": 0.20, "ev_sales": 0.20, "ddm": 0.00, "pb": 0.00, "rim": 0.00, "sotp": 0.00, "nav": 0.00},
    "EARLY_GROWTH": {"dcf": 0.35, "fcfe": 0.00, "ev_ebitda": 0.00, "pe": 0.00, "ev_sales": 0.40, "ddm": 0.00, "pb": 0.00, "rim": 0.00, "sotp": 0.25, "nav": 0.00},
    "CYCLICAL":     {"dcf": 0.40, "fcfe": 0.00, "ev_ebitda": 0.20, "pe": 0.25, "ev_sales": 0.00, "ddm": 0.00, "pb": 0.00, "rim": 0.00, "sotp": 0.00, "nav": 0.15},
    "FINANCIAL":    {"dcf": 0.00, "fcfe": 0.00, "ev_ebitda": 0.00, "pe": 0.20, "ev_sales": 0.00, "ddm": 0.00, "pb": 0.35, "rim": 0.45, "sotp": 0.00, "nav": 0.00},
    "CONGLOMERATE": {"dcf": 0.00, "fcfe": 0.00, "ev_ebitda": 0.30, "pe": 0.00, "ev_sales": 0.00, "ddm": 0.00, "pb": 0.00, "rim": 0.00, "sotp": 0.40, "nav": 0.30},
    "ASSET_HEAVY":  {"dcf": 0.30, "fcfe": 0.00, "ev_ebitda": 0.00, "pe": 0.25, "ev_sales": 0.00, "ddm": 0.00, "pb": 0.00, "rim": 0.00, "sotp": 0.00, "nav": 0.45},
}


def classify(fin: dict) -> dict:
    """Return stock_type and method_weights derived from an extract_financials dict."""
    stock_type = _detect_type(fin)
    weights = _TYPE_WEIGHTS[stock_type]
    method_weights = {
        method_id: {"enabled": weight > 0, "weight": weight}
        for method_id, weight in weights.items()
    }
    return {"stock_type": stock_type, "method_weights": method_weights}


def _detect_type(fin: dict) -> str:
    sector = fin.get("sector") or ""
    industry = (fin.get("industry") or "").lower()
    summary = (fin.get("long_business_summary") or "").lower()
    market_cap = fin.get("market_cap") or 0
    ebitda = fin.get("ebitda_ttm") or 0
    eps = fin.get("eps_ttm") or 0
    revenue_growth = fin.get("revenue_growth") or 0
    dividend_yield = fin.get("dividend_yield") or 0
    payout_ratio = fin.get("payout_ratio") or 0
    trailing_pe = fin.get("trailing_pe") or 0

    # 1. Financial. A core-financial industry (bank / lender / insurer) stays FINANCIAL
    # even if the summary mentions crypto — the de-financialize keyword override only
    # applies to Financial-Services names that are NOT a balance-sheet lender (crypto
    # miners / data-center operators mis-tagged as Financial Services).
    if sector == "Financial Services":
        is_core_financial = any(kw in industry for kw in CORE_FINANCIAL_INDUSTRIES)
        if is_core_financial or not any(kw in summary for kw in NON_FINANCIAL_KEYWORDS):
            return "FINANCIAL"

    # 2. Asset-heavy / Real Estate
    if sector == "Real Estate" or (ebitda <= 0 and 0 < market_cap < 2_000_000_000):
        return "ASSET_HEAVY"

    # 3. Conglomerate
    is_conglomerate_industry = "conglomerate" in industry or "diversified" in industry
    has_conglomerate_keywords = any(kw in summary for kw in CONGLOMERATE_KEYWORDS)
    if is_conglomerate_industry or has_conglomerate_keywords:
        return "CONGLOMERATE"

    # 4. Early growth
    if revenue_growth > 0.20 and (eps <= 0 or ebitda <= 0):
        return "EARLY_GROWTH"

    # 5. Growth — fast-growing, but only below the mega-cap line. A $1T+ company
    # is a LARGE_CAP regardless of growth (no size ceiling here would mislabel
    # META/MSFT/GOOGL as GROWTH); base-rate drag is handled by the size-coupled fade.
    if revenue_growth > 0.10 and eps > 0 and dividend_yield < 0.01 and market_cap < 1_000_000_000_000:
        return "GROWTH"

    # 6. Dividend
    if dividend_yield > 0.025 and payout_ratio > 0.40:
        return "DIVIDEND"

    # 7. Cyclical
    if sector in CYCLICAL_SECTORS or (0 < trailing_pe < 12 and revenue_growth < 0.05):
        return "CYCLICAL"

    # 8. Size-based default
    if market_cap > 100_000_000_000:
        return "LARGE_CAP"
    return "MID_CAP"
