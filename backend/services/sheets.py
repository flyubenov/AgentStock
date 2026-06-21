from __future__ import annotations
import asyncio, json, os
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from models import TickerResult

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_service = None


def _get_service():
    global _service
    if _service is None:
        creds_path = os.environ.get("GOOGLE_SHEETS_CREDS_PATH", "./credentials/service_account.json")
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        _service = build("sheets", "v4", credentials=creds)
    return _service


def _sheet_id() -> str:
    return os.environ["GOOGLE_SHEETS_ID"]


async def read_tickers() -> list[str]:
    """Read ticker symbols from the 'Tickers' sheet, column A."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _read_tickers_sync)


def _read_tickers_sync() -> list[str]:
    svc = _get_service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=_sheet_id(),
        range="Tickers!A:A",
    ).execute()
    rows = result.get("values", [])
    return [row[0].strip() for row in rows if row and row[0].strip() and row[0].strip().upper() != "TICKER"]


async def upsert_result(result: TickerResult) -> None:
    """Upsert a TickerResult row into the 'Database' sheet."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _upsert_sync, result)


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
        r.last_evaluated or datetime.utcnow().isoformat(),
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
    existing = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range="Database!A:A"
    ).execute()
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
        svc.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Database!A:A",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [new_row]},
        ).execute()
    else:
        # Overwrite existing row
        svc.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"Database!A{target_row}",
            valueInputOption="RAW",
            body={"values": [new_row]},
        ).execute()


async def read_database() -> list[TickerResult]:
    """Read all rows from the 'Database' sheet and return as TickerResult list."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _read_database_sync)


def _ensure_database_sheet(svc, sheet_id: str) -> None:
    """Create the 'Database' sheet tab if it doesn't exist."""
    meta = svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if "Database" not in existing:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": "Database"}}}]},
        ).execute()
        # Write headers on the new sheet
        svc.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range="Database!A1",
            valueInputOption="RAW",
            body={"values": [_DB_HEADERS]},
        ).execute()


def _read_database_sync() -> list[TickerResult]:
    svc = _get_service()
    sheet_id = _sheet_id()
    try:
        result = svc.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Database!A:P",
        ).execute()
    except Exception as e:
        if "Unable to parse range" in str(e) or "400" in str(e):
            _ensure_database_sheet(svc, sheet_id)
            return []
        raise
    rows = result.get("values", [])
    if len(rows) < 2:
        return []

    def safe_float(val: str) -> float | None:
        try:
            return float(val) if val else None
        except (ValueError, TypeError):
            return None

    results = []
    for row in rows[1:]:  # skip header
        while len(row) < 16:
            row.append("")
        breakdown = {}
        for i, mid in enumerate(_MODEL_COLS):
            fv = safe_float(row[7 + i])
            if fv is not None:
                breakdown[mid] = {"fair_value": fv}
        results.append(TickerResult(
            ticker=row[0],
            company_name=row[1] or None,
            last_evaluated=row[2] or None,
            stock_type=row[3] or None,
            fair_value=safe_float(row[4]),
            current_price=safe_float(row[5]),
            price_vs_fair_value_pct=safe_float(row[6]),
            fair_value_breakdown=breakdown,
        ))
    return results
