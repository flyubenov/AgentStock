import os
import time
import yfinance as yf
from functools import lru_cache
from datetime import date as _date
from services.yf_pool import run_yf, note_rate_limit

EV_EBITDA_HISTORY_MIN_YEARS = 3
# Recency-weight decay for ev_ebitda_history_ewma: each year further into the past
# counts for half as much as the year after it (half-life = 1 year). See that
# function's docstring / [[strl-ev-ebitda-trend-lag]] for why a flat median was
# replaced.
EV_EBITDA_HISTORY_DECAY = 0.5

try:
    from yfinance.exceptions import YFRateLimitError as _YFRateLimitError
except ImportError:
    _YFRateLimitError = None  # older yfinance versions

_RATE_LIMIT_RETRIES = 3
# seconds, multiplied by attempt number (3, 6 = 9s worst case). Kept short so a
# rate-limited fetch releases its pool worker quickly; the dedicated yf_pool already
# contains the blast radius, this bounds how long a single fetch can hold a thread.
_RATE_LIMIT_BACKOFF = 3.0
# Hard network timeout on the price-history pull (the one yfinance call here that
# accepts one). Without it a stuck socket holds a yf_pool worker indefinitely —
# enough of those starve the pool and the whole batch freezes with no error.
_HISTORY_TIMEOUT = float(os.getenv("YF_HISTORY_TIMEOUT", "30"))


async def fetch_ticker_info(ticker: str) -> dict:
    """Async wrapper around yfinance Ticker.info (dedicated yfinance pool)."""
    return await run_yf(_fetch_sync, ticker.upper())


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
            if is_rate_limit:
                note_rate_limit()  # let the batch orchestrator slow its pacing
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
            if is_rate_limit:
                note_rate_limit()  # let the batch orchestrator slow its pacing
            if is_rate_limit and attempt < _RATE_LIMIT_RETRIES - 1:
                time.sleep(_RATE_LIMIT_BACKOFF * (attempt + 1))
                continue
            return None
    return None


async def fetch_ticker_cashflow(ticker: str) -> dict | None:
    """Async wrapper around _fetch_cashflow_sync (dedicated yfinance pool)."""
    return await run_yf(_fetch_cashflow_sync, ticker.upper())


@lru_cache(maxsize=256)
def _fetch_quarterly_revenue_sync(ticker: str) -> tuple | None:
    """Latest-first quarterly Total Revenue, for the EV/Sales run-rate base (see
    models.run_rate_revenue). Returns None (never raises) when unavailable."""
    for attempt in range(_RATE_LIMIT_RETRIES):
        try:
            q = yf.Ticker(ticker).quarterly_income_stmt
            if q is None or q.empty or "Total Revenue" not in q.index:
                return None
            vals = []
            for col in sorted(q.columns, reverse=True):   # newest quarter first
                v = q.loc["Total Revenue", col]
                vals.append(float(v) if v == v else None)  # NaN -> None
            return tuple(vals) or None
        except Exception as e:
            is_rate_limit = (
                (_YFRateLimitError and isinstance(e, _YFRateLimitError))
                or "rate" in str(e).lower()
                or "too many" in str(e).lower()
            )
            if is_rate_limit:
                note_rate_limit()  # let the batch orchestrator slow its pacing
            if is_rate_limit and attempt < _RATE_LIMIT_RETRIES - 1:
                time.sleep(_RATE_LIMIT_BACKOFF * (attempt + 1))
                continue
            return None
    return None


async def fetch_quarterly_revenue(ticker: str) -> tuple | None:
    """Async wrapper around _fetch_quarterly_revenue_sync (dedicated yfinance pool)."""
    return await run_yf(_fetch_quarterly_revenue_sync, ticker.upper())


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


def ev_ebitda_history_ewma(rows: list[dict], min_years: int = EV_EBITDA_HISTORY_MIN_YEARS,
                          decay: float = EV_EBITDA_HISTORY_DECAY) -> float | None:
    """Exponentially recency-weighted historical EV/EBITDA from per-year rows of
    {avg_price, shares, ebitda, net_debt} (most-recent-first, matching
    latest_statement_ebitda's convention). Years with non-positive EBITDA or
    missing price/shares are skipped; None if fewer than min_years remain.

    Replaces a flat median (see [[strl-ev-ebitda-trend-lag]]): a median lags a
    persistent multi-year re-rating trend, in EITHER direction. STRL's multiple
    climbed 5.24x->6.23x->8.15x->14.54x over 4 years (a genuine, sustained
    business-mix shift, not noise) but the median (7.19x) sat near the OLDEST
    two years, understating the fair value by anchoring to a growth regime STRL
    has since grown past. The mirror-image also happens: CRM's multiple fell
    36.9x->27.4x->23.0x->14.8x, and its median (25.2x) OVERSTATES the current
    level. A flat median is simply the wrong central-tendency statistic for a
    trending (not mean-reverting) series.

    decay=0.5 (weight halves each year further into the past, i.e. the latest
    year counts 2x the year before it) smoothly favors the recent trading level
    without a hard year-cutoff (noisier, window-edge-sensitive) or a
    monotonicity on/off switch (blunter -- live-swept to move unrelated names
    -27pp to +20pp, unpredictable in direction once it falls back to the spot
    multiple's separate compression path). A flat (non-trending) series still
    resolves to that same constant, so a stable/cyclical name is unaffected."""
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
    weights = [decay ** i for i in range(len(mults))]   # mults[0] (most recent) -> weight 1.0
    return sum(w * mlt for w, mlt in zip(weights, mults)) / sum(weights)


def latest_statement_ebitda(rows: list[dict]) -> float | None:
    """The most recent positive statement EBITDA from the reconstruction rows
    (most-recent-first). This is the projection base that stays consistent with
    the statement-derived representative multiple — using yfinance info['ebitda']
    instead mixes two EBITDA definitions (they differ ~2x for content names like NFLX)."""
    for r in rows:
        ebitda = r.get("ebitda")
        if ebitda and ebitda > 0:
            return ebitda
    return None


def _statement_yoy(rows: list[dict], field: str) -> float | None:
    """Year-over-year growth (as a fraction) of `field` from the two most-recent
    reconstruction rows (most-recent-first). None when fewer than two rows or the
    prior-year figure is missing/non-positive — a sign flip out of a loss is not a
    growth rate. All callers share one timeframe (statement-annual), which is what makes
    the readings comparable to each other (see engine._earnings_non_operating)."""
    if len(rows) < 2:
        return None
    latest = rows[0].get(field)
    prior = rows[1].get(field)
    if latest is None or not prior or prior <= 0:
        return None
    return latest / prior - 1.0


def _statement_revenue_yoy(rows: list[dict]) -> float | None:
    """Feeds build_scenarios as a growth fallback when yfinance info['revenueGrowth']
    is broken (statement-primary)."""
    return _statement_yoy(rows, "revenue")


def _statement_op_income_yoy(rows: list[dict]) -> float | None:
    """The clean operating-line signal: lets build_scenarios tell earnings growth the
    operating business produced from growth that arrived below it."""
    return _statement_yoy(rows, "operating_income")


def _statement_net_income_yoy(rows: list[dict]) -> float | None:
    """The earnings reading _earnings_non_operating tests against the operating line.
    Statement-annual on purpose: info['earningsGrowth'] is a QUARTERLY YoY and is not
    comparable to an annual operating change."""
    return _statement_yoy(rows, "net_income")


def _latest_ordinary_shares(bs) -> float | None:
    """Newest non-null total share count from the balance sheet (all classes).

    'Ordinary Shares Number' / 'Share Issued' carry every class, unlike info's
    single-class sharesOutstanding. Returns the most recent positive value, or None."""
    for label in ("Ordinary Shares Number", "Share Issued"):
        if label not in bs.index:
            continue
        row = bs.loc[label]
        for col in sorted(bs.columns, reverse=True):
            v = row.get(col)
            if v is not None and v == v and v > 0:  # not None, not NaN, positive
                return float(v)
    return None


@lru_cache(maxsize=256)
def _fetch_ev_ebitda_history_sync(ticker: str) -> dict | None:
    """Reconstruct annual EV/EBITDA = (avg price * shares + net debt) / EBITDA from
    income statement + balance sheet + monthly price history.

    Returns {"multiple": recency-weighted representative EV/EBITDA (see
    ev_ebitda_history_ewma), "ebitda": latest statement EBITDA} — both
    on the same statement-EBITDA definition so the caller can project a consistent
    base against the multiple. Returns None (never raises) when the statements are
    unavailable/insufficient, or when a stock split postdates the statements
    (price/share bases would mismatch)."""
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
        hist = tk.history(period="6y", interval="1mo", timeout=_HISTORY_TIMEOUT)
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
            revenue = _cell(ist, "Total Revenue", col)
            op_income = _cell(ist, "Operating Income", col)
            net_income = _cell(ist, "Net Income", col)
            debt = _cell(bs, "Total Debt", col) if col in bs.columns else None
            cash = _cell(bs, "Cash Cash Equivalents And Short Term Investments", col) if col in bs.columns else None
            net_debt = (debt or 0) - (cash or 0) if (debt is not None or cash is not None) else 0
            rows.append({"avg_price": float(avg_close[year]), "shares": shares,
                         "ebitda": ebitda, "net_debt": net_debt, "revenue": revenue,
                         "operating_income": op_income, "net_income": net_income})
        representative = ev_ebitda_history_ewma(rows)
        if representative is None:
            return None
        return {"multiple": representative, "ebitda": latest_statement_ebitda(rows),
                "revenue_growth": _statement_revenue_yoy(rows),
                "op_income_growth": _statement_op_income_yoy(rows),
                "net_income_growth": _statement_net_income_yoy(rows),
                # Full multi-class share total (all classes) — lets engine.run correct a
                # dual-class subsidiary whose info marketCap AND sharesOutstanding both
                # undercount (MBLY). Rides this fetch's balance sheet; no extra round-trip.
                "ordinary_shares": _latest_ordinary_shares(bs)}
    except Exception as e:
        msg = str(e).lower()
        if "rate" in msg or "too many" in msg:
            note_rate_limit()
        return None


async def fetch_ev_ebitda_history(ticker: str) -> dict | None:
    return await run_yf(_fetch_ev_ebitda_history_sync, ticker.upper())


# Below this divergence, market_cap/price and sharesOutstanding agree to rounding
# (single-class names <=0.1%); above it a hidden share class is present (PLTR ~4.2%;
# KVYO/GOOGL ~2.1x, where sharesOutstanding is the Class A float only). 3% clears
# intraday market_cap/price staleness and sits below the smallest real multi-class gap.
_SHARE_GATE_RATIO = 1.03


def _effective_shares(info: dict, price: float | None,
                      balance_sheet_shares: float | None = None) -> float | None:
    """Fully-diluted share count for the per-share fair-value divide.

    yfinance's sharesOutstanding returns only one class for multi-class companies
    (typically the Class A float), while marketCap capitalizes every class. Dividing
    an absolute equity value by the single-class count inflates per-share FV by
    true_shares / reported_shares. Correct UPWARD ONLY and gated at _SHARE_GATE_RATIO
    against two independent full-class estimates, keeping the largest:

      * market_cap / price — catches the case where marketCap capitalizes every class
        (KVYO/GOOGL: sharesOutstanding is the Class A float only);
      * balance_sheet_shares — the statement Ordinary Shares / Share Issued total,
        which catches the case where marketCap ALSO undercounts. MBLY (Mobileye, an
        Intel dual-class subsidiary) reports both marketCap and sharesOutstanding on
        the ~252M Class A count, so market_cap/price == reported and the first path
        is blind; only the 814.7M balance-sheet total exposes Intel's Class B, and
        without it every per-share leg divided whole-company value by ~31% of the
        shares (FV +193%). Rides the existing EV/EBITDA-history balance-sheet fetch
        (see engine.run) rather than paying its own yfinance round-trip.

    Single-class names stay byte-identical (both estimates sit inside the gate).
    Falls back to the reported count whenever an estimate is unavailable.
    """
    reported = info.get("sharesOutstanding")
    best = reported if (reported and reported > 0) else None
    market_cap = info.get("marketCap")
    if market_cap and price:
        implied = market_cap / price
        if best is None or implied > best * _SHARE_GATE_RATIO:
            best = implied
    if balance_sheet_shares:
        if best is None or balance_sheet_shares > best * _SHARE_GATE_RATIO:
            best = balance_sheet_shares
    return best if best is not None else reported


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
        "shares_outstanding": _effective_shares(info, price),
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
