import asyncio
import time
import yfinance as yf
from functools import lru_cache

try:
    from yfinance.exceptions import YFRateLimitError as _YFRateLimitError
except ImportError:
    _YFRateLimitError = None

_RETRIES = 3
_BACKOFF = 8.0


def _is_rate_limit(e: Exception) -> bool:
    return (
        (_YFRateLimitError and isinstance(e, _YFRateLimitError))
        or "rate" in str(e).lower()
        or "too many" in str(e).lower()
    )


def _statement_to_dict(df) -> dict | None:
    if df is None or getattr(df, "empty", True):
        return None
    years = [c.year for c in df.columns]
    rows: dict[str, list[float | None]] = {}
    for label in df.index:
        vals = []
        for col in df.columns:
            v = df.loc[label, col]
            vals.append(float(v) if v == v else None)  # NaN -> None
        rows[str(label)] = vals
    return {"years": years, "rows": rows}


def _fetch_statement(ticker: str, attr: str) -> dict | None:
    for attempt in range(_RETRIES):
        try:
            df = getattr(yf.Ticker(ticker), attr)
            return _statement_to_dict(df)
        except Exception as e:
            if _is_rate_limit(e) and attempt < _RETRIES - 1:
                time.sleep(_BACKOFF * (attempt + 1))
                continue
            return None
    return None


@lru_cache(maxsize=256)
def fetch_income_stmt(ticker: str) -> dict | None:
    return _fetch_statement(ticker, "income_stmt")


@lru_cache(maxsize=256)
def fetch_balance_sheet(ticker: str) -> dict | None:
    return _fetch_statement(ticker, "balance_sheet")


@lru_cache(maxsize=256)
def fetch_cashflow_annual(ticker: str) -> dict | None:
    return _fetch_statement(ticker, "cashflow")


@lru_cache(maxsize=8)
def fetch_treasury_10y() -> float | None:
    try:
        hist = yf.Ticker("^TNX").history(period="5d")
        if hist is None or hist.empty:
            return None
        return float(hist["Close"].iloc[-1]) / 1000.0  # ^TNX is yield*10 in percent
    except Exception:
        return None


@lru_cache(maxsize=256)
def fetch_price_monthly(ticker: str) -> tuple[float, ...]:
    try:
        hist = yf.Ticker(ticker).history(period="6y", interval="1mo")
        if hist is None or hist.empty:
            return tuple()
        return tuple(float(x) for x in hist["Close"].tolist() if x == x)
    except Exception:
        return tuple()
