import asyncio
import yfinance as yf
from functools import lru_cache
from datetime import date as _date


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


async def format_financial_block(ticker: str) -> str | None:
    """Fetch ~20 financial metrics and format as a structured markdown block.
    Returns None if the fetch fails — callers must abort the ticker in that case."""
    try:
        info = await fetch_ticker_info(ticker)
    except Exception:
        return None

    def _p(val: float | None, prefix: str = "$") -> str:
        if val is None:
            return "N/A"
        return f"{prefix}{val:,.2f}"

    def _pct(val: float | None) -> str:
        if val is None:
            return "N/A"
        return f"{val * 100:.1f}%"

    def _large(val: float | None) -> str:
        if val is None:
            return "N/A"
        if val >= 1e12:
            return f"${val / 1e12:.2f}T"
        if val >= 1e9:
            return f"${val / 1e9:.2f}B"
        return f"${val / 1e6:.2f}M"

    def _n(val: float | None, d: int = 2) -> str:
        return "N/A" if val is None else f"{val:.{d}f}"

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    mkt_cap = info.get("marketCap")
    ma200 = info.get("twoHundredDayAverage")
    fcf = info.get("freeCashflow")

    price_vs_ma = None
    if price and ma200 and ma200 > 0:
        price_vs_ma = (price - ma200) / ma200 * 100

    fcf_yield = None
    if fcf and mkt_cap and mkt_cap > 0:
        fcf_yield = fcf / mkt_cap * 100

    rec = (info.get("recommendationKey") or "N/A").upper()

    return (
        f"## Pre-fetched Financial Data for {ticker} (via yfinance, {_date.today()})\n"
        f"- Current Price: {_p(price)} | Market Cap: {_large(mkt_cap)}\n"
        f"- P/E (TTM): {_n(info.get('trailingPE'))} | Forward P/E: {_n(info.get('forwardPE'))} | PEG: {_n(info.get('pegRatio'))}\n"
        f"- EPS (TTM): {_p(info.get('trailingEps'))} | EPS Growth YoY: {_pct(info.get('earningsGrowth'))}\n"
        f"- Revenue (TTM): {_large(info.get('totalRevenue'))} | Revenue Growth YoY: {_pct(info.get('revenueGrowth'))}\n"
        f"- Gross Margin: {_pct(info.get('grossMargins'))} | Operating Margin: {_pct(info.get('operatingMargins'))}\n"
        f"- FCF (TTM): {_large(fcf)} | FCF Yield: {'N/A' if fcf_yield is None else f'{fcf_yield:.1f}%'}\n"
        f"- ROE: {_pct(info.get('returnOnEquity'))} | Debt/Equity: {_n(info.get('debtToEquity'))}\n"
        f"- 52w High: {_p(info.get('fiftyTwoWeekHigh'))} | 52w Low: {_p(info.get('fiftyTwoWeekLow'))} | Beta: {_n(info.get('beta'))}\n"
        f"- Price vs 200-day MA: {'N/A' if price_vs_ma is None else f'{price_vs_ma:+.1f}%'}\n"
        f"- Dividend Yield: {_pct(info.get('dividendYield'))} | Institutional Ownership: {_pct(info.get('heldPercentInstitutions'))}\n"
        f"- Analyst Consensus: {rec} | Avg Target: {_p(info.get('targetMeanPrice'))}"
    )
