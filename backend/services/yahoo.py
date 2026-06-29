import asyncio
import statistics
import time
import yfinance as yf
from functools import lru_cache
from datetime import date as _date

EV_EBITDA_HISTORY_MIN_YEARS = 3

try:
    from yfinance.exceptions import YFRateLimitError as _YFRateLimitError
except ImportError:
    _YFRateLimitError = None  # older yfinance versions

_RATE_LIMIT_RETRIES = 3
_RATE_LIMIT_BACKOFF = 8.0  # seconds; multiplied by attempt number (8, 16, 24 = 48s max)


async def fetch_ticker_info(ticker: str) -> dict:
    """Async wrapper around yfinance Ticker.info."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_sync, ticker.upper())


@lru_cache(maxsize=256)
def _fetch_sync(ticker: str) -> dict:
    """Fetch yfinance info with retry on rate-limit. Cached per ticker per process."""
    for attempt in range(_RATE_LIMIT_RETRIES):
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}
            if not info.get("symbol") and not info.get("shortName"):
                raise ValueError(f"Ticker '{ticker}' not found or returned no data")
            return info
        except Exception as e:
            is_rate_limit = (
                (_YFRateLimitError and isinstance(e, _YFRateLimitError))
                or "rate" in str(e).lower()
                or "too many" in str(e).lower()
            )
            if is_rate_limit and attempt < _RATE_LIMIT_RETRIES - 1:
                time.sleep(_RATE_LIMIT_BACKOFF * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"Failed to fetch {ticker} after {_RATE_LIMIT_RETRIES} attempts")


@lru_cache(maxsize=256)
def _fetch_cashflow_sync(ticker: str) -> dict | None:
    """Fetch the cashflow statement and extract the rows we need. Cached per ticker.
    Returns None (never raises) when the statement is unavailable."""
    for attempt in range(_RATE_LIMIT_RETRIES):
        try:
            cf = yf.Ticker(ticker).cashflow
            if cf is None or cf.empty:
                return None

            def _row(label: str) -> float | None:
                try:
                    val = cf.loc[label].iloc[0]
                except (KeyError, IndexError):
                    return None
                return float(val) if val == val else None  # NaN -> None

            return {
                "free_cash_flow": _row("Free Cash Flow"),
                "operating_cash_flow": _row("Operating Cash Flow"),
                "capital_expenditure": _row("Capital Expenditure"),
            }
        except Exception as e:
            is_rate_limit = (
                (_YFRateLimitError and isinstance(e, _YFRateLimitError))
                or "rate" in str(e).lower()
                or "too many" in str(e).lower()
            )
            if is_rate_limit and attempt < _RATE_LIMIT_RETRIES - 1:
                time.sleep(_RATE_LIMIT_BACKOFF * (attempt + 1))
                continue
            return None
    return None


async def fetch_ticker_cashflow(ticker: str) -> dict | None:
    """Async wrapper around _fetch_cashflow_sync."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_cashflow_sync, ticker.upper())


def real_fcf(cashflow: dict | None, info_fcf: float | None) -> float | None:
    """Real FCF priority: statement 'Free Cash Flow', else OCF + (negative) capex,
    else the info-dict free cash flow fallback."""
    if cashflow:
        fcf = cashflow.get("free_cash_flow")
        if fcf is not None:
            return fcf
        ocf = cashflow.get("operating_cash_flow")
        capex = cashflow.get("capital_expenditure")
        if ocf is not None and capex is not None:
            return ocf + capex  # capex is negative in the statement
    return info_fcf


# -- historical EV/EBITDA ------------------------------------------------------
def statements_predate_split(latest_statement_date, split_dates) -> bool:
    """True when a stock split occurred AFTER the latest financial-statement date.
    yfinance split-adjusts prices immediately but lags the per-share statement
    figures (shares, EPS), so across a recent split the two are on different bases
    and any reconstruction mixing them (price x statement-shares) is garbage."""
    if latest_statement_date is None or not split_dates:
        return False
    return any(d > latest_statement_date for d in split_dates)


def ev_ebitda_history_median(rows: list[dict],
                             min_years: int = EV_EBITDA_HISTORY_MIN_YEARS) -> float | None:
    """Median historical EV/EBITDA from per-year rows of
    {avg_price, shares, ebitda, net_debt}. Years with non-positive EBITDA or
    missing price/shares are skipped; None if fewer than min_years remain."""
    mults = []
    for r in rows:
        ebitda = r.get("ebitda")
        shares = r.get("shares")
        px = r.get("avg_price")
        if not ebitda or ebitda <= 0 or not shares or not px:
            continue
        ev = px * shares + (r.get("net_debt") or 0)
        mults.append(ev / ebitda)
    if len(mults) < min_years:
        return None
    return statistics.median(mults)


@lru_cache(maxsize=256)
def _fetch_ev_ebitda_history_sync(ticker: str) -> float | None:
    """Reconstruct annual EV/EBITDA = (avg price * shares + net debt) / EBITDA from
    income statement + balance sheet + monthly price history, and return the median.
    Returns None (never raises) when the statements are unavailable/insufficient, or
    when a stock split postdates the statements (price/share bases would mismatch)."""
    try:
        tk = yf.Ticker(ticker)
        ist, bs = tk.income_stmt, tk.balance_sheet
        if ist is None or ist.empty or bs is None or bs.empty:
            return None
        # Skip across a recent split: prices are split-adjusted but statement
        # shares are not, so the reconstruction would mix incompatible bases.
        latest_stmt = max((c.date() for c in ist.columns), default=None)
        split_dates = [d.date() for d in tk.splits.index] if tk.splits is not None else []
        if statements_predate_split(latest_stmt, split_dates):
            return None
        hist = tk.history(period="6y", interval="1mo")
        if hist is None or hist.empty:
            return None
        avg_close = hist["Close"].groupby(hist.index.year).mean()

        def _cell(df, label, col):
            try:
                v = df.loc[label, col]
            except (KeyError, IndexError):
                return None
            return float(v) if v == v else None

        rows = []
        for col in ist.columns:
            year = col.year
            if year not in avg_close.index:
                continue
            ebitda = _cell(ist, "EBITDA", col)
            shares = _cell(ist, "Diluted Average Shares", col)
            debt = _cell(bs, "Total Debt", col) if col in bs.columns else None
            cash = _cell(bs, "Cash Cash Equivalents And Short Term Investments", col) if col in bs.columns else None
            net_debt = (debt or 0) - (cash or 0) if (debt is not None or cash is not None) else 0
            rows.append({"avg_price": float(avg_close[year]), "shares": shares,
                         "ebitda": ebitda, "net_debt": net_debt})
        return ev_ebitda_history_median(rows)
    except Exception:
        return None


async def fetch_ev_ebitda_history(ticker: str) -> float | None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_ev_ebitda_history_sync, ticker.upper())


def extract_financials(info: dict) -> dict:
    """Normalise yfinance info dict to the fields our valuation scripts need."""
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    div_rate = info.get("dividendRate")
    # yfinance 1.3.0 changed dividendYield to percentage form (0.86 = 0.86%);
    # compute from dividendRate/price so callers always receive a ratio.
    div_yield = (div_rate / price) if (div_rate and price) else 0
    return {
        "ticker": info.get("symbol", ""),
        "company_name": info.get("shortName") or info.get("longName"),
        "current_price": price,
        "market_cap": info.get("marketCap"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "fcf_ttm": info.get("freeCashflow"),
        "net_debt": _net_debt(info),
        "ebitda_ttm": info.get("ebitda"),
        "eps_ttm": info.get("trailingEps"),
        "forward_eps": info.get("forwardEps"),
        "revenue_ttm": info.get("totalRevenue"),
        "book_value_per_share": info.get("bookValue"),
        "dividend_rate": div_rate,
        "dividend_yield": div_yield,
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
        "operating_cashflow": info.get("operatingCashflow"),
        "ev_ebitda": info.get("enterpriseToEbitda"),
        "ev_sales": info.get("enterpriseToRevenue"),
        "cost_of_equity": 0.10,
    }


def _net_debt(info: dict) -> float:
    total_debt = info.get("totalDebt") or 0
    cash = info.get("totalCash") or 0
    return total_debt - cash


_TICKER_RE = __import__('re').compile(r'^[A-Z]{1,5}(\.[A-Z]{1,2})?$')

async def validate_ticker(ticker: str) -> bool:
    """Validate ticker by format only — yfinance is too slow/rate-limited to use here.
    Analysis will fail gracefully if the ticker doesn't exist."""
    return bool(_TICKER_RE.match(ticker.upper()))


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
        abs_val = abs(val)
        sign = "-" if val < 0 else ""
        if abs_val >= 1e12:
            return f"{sign}${abs_val / 1e12:.2f}T"
        if abs_val >= 1e9:
            return f"{sign}${abs_val / 1e9:.2f}B"
        return f"{sign}${abs_val / 1e6:.2f}M"

    def _n(val: float | None, d: int = 2) -> str:
        return "N/A" if val is None else f"{val:.{d}f}"

    price = info.get("currentPrice")
    if price is None:
        price = info.get("regularMarketPrice")
    mkt_cap = info.get("marketCap")
    ma200 = info.get("twoHundredDayAverage")
    fcf = info.get("freeCashflow")
    div_rate = info.get("dividendRate")

    price_vs_ma = None
    if price and ma200 and ma200 > 0:
        price_vs_ma = (price - ma200) / ma200 * 100

    fcf_yield = None
    if fcf is not None and mkt_cap and mkt_cap > 0:
        fcf_yield = fcf / mkt_cap * 100

    # Compute yield from dividendRate/price — yfinance 1.x changed dividendYield scale
    div_yield_ratio = (div_rate / price) if (div_rate and price) else None

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
        f"- Dividend Yield: {_pct(div_yield_ratio)} | Institutional Ownership: {_pct(info.get('heldPercentInstitutions'))}\n"
        f"- Analyst Consensus: {rec} | Avg Target: {_p(info.get('targetMeanPrice'))}"
    )
