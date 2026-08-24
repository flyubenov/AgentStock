from __future__ import annotations
import asyncio, json, os
import time as _time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from models import TickerResult, DatabaseRow

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_service = None

# All Google Sheets I/O runs on THIS single-thread executor — never the default
# multi-thread executor. googleapiclient is built on httplib2, which is NOT
# thread-safe: the batch runs many _run_one tasks concurrently, and routing their
# Sheets calls (2 upserts/ticker, ~10 API calls each) through the shared service on
# the default pool let multiple threads hit the one httplib2 connection at once —
# it corrupted the connection and froze the whole recalc after ~6 tickers. One
# dedicated thread serializes every call so the shared client is only ever touched
# by a single thread. It also smooths the request burst against the Sheets quota.
_SHEETS_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sheets")
_SHEETS_MAX_RETRIES = int(os.getenv("SHEETS_MAX_RETRIES", "6"))


async def _run_sheets(fn, *args):
    """Run a blocking Sheets call on the dedicated single-thread executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_SHEETS_EXECUTOR, fn, *args)


def _execute(request):
    """Execute a Sheets API request, backing off on quota (429) / transient (500,
    503) errors so a full recalc self-throttles under the ~60-req/min per-user
    limit instead of erroring out or hanging. Non-quota errors (403, 404, parse
    errors) are raised immediately — retrying them is pointless."""
    for attempt in range(_SHEETS_MAX_RETRIES):
        try:
            return request.execute()
        except HttpError as e:
            status = getattr(getattr(e, "resp", None), "status", None)
            if status in (429, 500, 503) and attempt < _SHEETS_MAX_RETRIES - 1:
                _time.sleep(min(2 ** attempt, 20))
                continue
            raise


def _get_service():
    global _service
    if _service is None:
        # Cloud hosts (Cloud Run / Railway / Render) can't ship the gitignored key
        # file, so accept the raw service-account JSON via env var; fall back to the
        # on-disk file for local dev (GOOGLE_SHEETS_CREDS_PATH, default ./credentials/).
        creds_json = os.environ.get("GOOGLE_SHEETS_CREDS_JSON")
        if creds_json:
            creds = service_account.Credentials.from_service_account_info(
                json.loads(creds_json), scopes=SCOPES)
        else:
            creds_path = os.environ.get("GOOGLE_SHEETS_CREDS_PATH", "./credentials/service_account.json")
            creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        _service = build("sheets", "v4", credentials=creds)
    return _service


def _sheet_id() -> str:
    return os.environ["GOOGLE_SHEETS_ID"]


async def read_tickers() -> list[str]:
    """Read ticker symbols from the 'Tickers' sheet, column A."""
    return await _run_sheets(_read_tickers_sync)


def _read_tickers_sync() -> list[str]:
    svc = _get_service()
    result = _execute(svc.spreadsheets().values().get(
        spreadsheetId=_sheet_id(),
        range="Tickers!A:A",
    ))
    rows = result.get("values", [])
    return [row[0].strip() for row in rows if row and row[0].strip() and row[0].strip().upper() != "TICKER"]


async def upsert_result(result: TickerResult) -> None:
    """Upsert a TickerResult row into the 'Database' sheet."""
    await _run_sheets(_upsert_sync, result)


_MODEL_COLS = ["dcf", "ev_ebitda", "ev_sales", "pe", "ddm", "rim", "pb", "sotp", "nav"]

_DB_HEADERS = [
    "Ticker", "Company Name", "Last Evaluated", "Stock Type", "Fair Value",
    "Current Price", "Price vs Fair Value %",
    "DCF", "EV/EBITDA", "EV/Sales", "P/E", "DDM", "RIM", "P/B", "SOTP", "NAV",
]


def _result_to_row(r: TickerResult) -> list:
    bd = r.fair_value_breakdown or {}

    def model_value(mid: str):
        cell = bd.get(mid)
        if cell and cell.get("fair_value") is not None:
            return cell["fair_value"]
        return ""

    return [
        r.ticker,
        r.company_name or "",
        r.last_evaluated or datetime.now(timezone.utc).isoformat(),
        r.stock_type or "",
        r.fair_value if r.fair_value is not None else "",
        r.current_price if r.current_price is not None else "",
        r.price_vs_fair_value_pct if r.price_vs_fair_value_pct is not None else "",
        *[model_value(mid) for mid in _MODEL_COLS],
    ]


def _upsert_sync(result: TickerResult) -> None:
    svc = _get_service()
    sheet_id = _sheet_id()

    _ensure_database_sheet(svc, sheet_id)

    # Read existing data
    existing = _execute(svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range="Database!A:A"
    ))
    rows = existing.get("values", [])

    # Find row index (1-based, +1 for header)
    target_row = None
    for i, row in enumerate(rows):
        if row and row[0].strip().upper() == result.ticker.upper():
            target_row = i + 1  # 1-based
            break

    new_row = _result_to_row(result)

    if target_row is None:
        # Append new row
        _execute(svc.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Database!A:A",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [new_row]},
        ))
    else:
        # Overwrite existing row
        _execute(svc.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"Database!A{target_row}",
            valueInputOption="RAW",
            body={"values": [new_row]},
        ))


async def read_database() -> list[DatabaseRow]:
    """Read all rows from the 'Database' sheet and return as DatabaseRow list."""
    return await _run_sheets(_read_database_sync)


def _tab_gid(svc, sheet_id: str, tab: str) -> int | None:
    """Numeric sheetId of a tab by title, or None when the tab doesn't exist."""
    meta = _execute(svc.spreadsheets().get(spreadsheetId=sheet_id))
    for s in meta.get("sheets", []):
        props = s.get("properties", {})
        if props.get("title") == tab:
            return props.get("sheetId")
    return None


def _delete_ticker_row_sync(tab: str, ticker: str) -> bool:
    """Remove the row whose column A holds `ticker` from `tab`.

    Deletes the row DIMENSION rather than clearing its values: the readers walk
    rows positionally (`rows[1:]`, index-into-columns), so a cleared-but-present
    row would come back as a blank record instead of disappearing."""
    svc = _get_service()
    sheet_id = _sheet_id()
    gid = _tab_gid(svc, sheet_id, tab)
    if gid is None:
        return False

    rows = _execute(svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{tab}!A:A",
    )).get("values", [])

    target = None
    for i, row in enumerate(rows):
        if row and row[0].strip().upper() == ticker.upper():
            target = i          # 0-based — deleteDimension indexes from 0
            break
    if target is None:
        return False

    _execute(svc.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": [{"deleteDimension": {"range": {
            "sheetId": gid, "dimension": "ROWS",
            "startIndex": target, "endIndex": target + 1,
        }}}]},
    ))
    return True


async def delete_ticker_row(tab: str, ticker: str) -> bool:
    """Delete a ticker's row from `tab`. True when a row was actually removed."""
    return await _run_sheets(_delete_ticker_row_sync, tab, ticker)


async def delete_database_row(ticker: str) -> bool:
    return await delete_ticker_row("Database", ticker)


async def delete_watchlist_row(ticker: str) -> bool:
    """Drop the ticker from the 'Tickers' input list too — otherwise the next
    Sheets-driven run re-adds the row the user just deleted."""
    return await delete_ticker_row("Tickers", ticker)


def _ensure_database_sheet(svc, sheet_id: str) -> None:
    """Create the 'Database' sheet tab if it doesn't exist."""
    meta = _execute(svc.spreadsheets().get(spreadsheetId=sheet_id))
    existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if "Database" not in existing:
        _execute(svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": "Database"}}}]},
        ))
        # Write headers on the new sheet
        _execute(svc.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="Database!A1",
            valueInputOption="RAW",
            body={"values": [_DB_HEADERS]},
        ))


def _row_to_database_row(row: list) -> DatabaseRow:
    row = list(row) + [""] * (19 - len(row))  # pad to include col S (index 18)

    def safe_float(val):
        try:
            return float(val) if val else None
        except (ValueError, TypeError):
            return None

    breakdown = {}
    for i, mid in enumerate(_MODEL_COLS):
        fv = safe_float(row[7 + i])
        if fv is not None:
            breakdown[mid] = {"fair_value": fv}
    return DatabaseRow(
        ticker=row[0], company_name=row[1] or None, last_evaluated=row[2] or None,
        stock_type=row[3] or None, fair_value=safe_float(row[4]),
        current_price=safe_float(row[5]), price_vs_fair_value_pct=safe_float(row[6]),
        fair_value_breakdown=breakdown, quality_score=safe_float(row[16]),
        risk_reward_ratio=safe_float(row[17]),
        moat_score=safe_float(row[18]),
    )


def _read_database_sync() -> list[DatabaseRow]:
    svc = _get_service()
    sheet_id = _sheet_id()
    try:
        result = _execute(svc.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Database!A:S",      # A:R + the Moat Score mirror (S)
        ))
    except Exception as e:
        if "Unable to parse range" in str(e) or "400" in str(e):
            _ensure_database_sheet(svc, sheet_id)
            return []
        raise
    rows = result.get("values", [])
    if len(rows) < 2:
        return []
    return [_row_to_database_row(row) for row in rows[1:]]
