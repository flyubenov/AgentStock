import asyncio
import yfinance as yf
from functools import lru_cache


async def fetch_ticker_info(ticker: str) -> dict:
    """Async wrapper around yfinance Ticker.info."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_sync, ticker)


def _fetch_sync(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    info = t.info or {}
    if not info.get("symbol") and not info.get("shortName"):
        raise ValueError(f"Ticker '{ticker}' not found or returned no data")
    return info


def extract_financials(info: dict) -> dict:
    """Normalise yfinance info dict to the fields our valuation scripts need."""
    return {
        "ticker": info.get("symbol", ""),
        "company_name": info.get("shortName") or info.get("longName"),
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap": info.get("marketCap"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "fcf_ttm": info.get("freeCashflow"),
        "net_debt": _net_debt(info),
        "ebitda_ttm": info.get("ebitda"),
        "eps_ttm": info.get("trailingEps"),
        "revenue_ttm": info.get("totalRevenue"),
        "book_value_per_share": info.get("bookValue"),
        "dividend_rate": info.get("dividendRate"),
        "dividend_yield": info.get("dividendYield") or 0,
        "payout_ratio": info.get("payoutRatio") or 0,
        "return_on_equity": info.get("returnOnEquity"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "revenue_growth": info.get("revenueGrowth") or 0,
        "earnings_growth": info.get("earningsGrowth"),
        "sector": info.get("sector", ""),
        "industry": info.get("industry", ""),
        "long_business_summary": info.get("longBusinessSummary", ""),
        "interest_expense": info.get("interestExpense"),
        "effective_tax_rate": info.get("effectiveTaxRate"),
        "cost_of_equity": None,
    }


def _net_debt(info: dict) -> float:
    total_debt = info.get("totalDebt") or 0
    cash = info.get("totalCash") or 0
    return total_debt - cash


_TICKER_RE = __import__('re').compile(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$')

async def validate_ticker(ticker: str) -> bool:
    """Validate ticker format first; fall back to yfinance only if format looks odd.
    On any network/rate-limit error, assume valid to avoid blocking the user."""
    if not _TICKER_RE.match(ticker.upper()):
        return False
    try:
        info = await fetch_ticker_info(ticker)
        return bool(info.get("symbol") or info.get("shortName"))
    except Exception:
        # Rate limit or network error — assume valid, let analysis fail gracefully
        return True
