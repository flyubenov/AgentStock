from __future__ import annotations
import asyncio, json, os
from datetime import datetime, timezone
from screener.models import ScreenerResult
from services.sheets import _get_service, _sheet_id

# metric fields persisted, in column order (matches ScreenerMetrics scored + reference set)
_METRIC_COLS = [
    "revenue_cagr_3y", "eps_cagr_3y", "fcf_cagr_3y", "fcf_margin", "op_margin",
    "op_margin_trajectory", "gross_margin",
    "roic_ttm", "roic_5y_avg", "wacc", "roic_wacc_spread", "rote",
    "net_debt_ebitda", "net_debt_fcf", "ocf_capex", "tangible_bv_per_share",
    "shares_cagr_3y", "sbc_pct_rev", "earnings_quality", "insider_ownership",
    "shareholder_yield",
    "trailing_pe", "forward_pe", "peg", "price_fcf", "price_sales",
    "fcf_yield", "owner_earnings_yield", "price_cagr_3y", "price_cagr_5y",
]

_SECTION_COLS = ["I", "II", "III", "IV"]

_SCREENER_HEADERS = [
    "Ticker", "Company", "Last Evaluated", "Quality Score", "Sector", "Sector Profile",
    "Section I", "Section II", "Section III", "Section IV",
    *[c.replace("_", " ").title() for c in _METRIC_COLS],
    "Score Breakdown",
]


def _num(v):
    return v if isinstance(v, (int, float)) else ""


def _result_to_row(r: ScreenerResult) -> list:
    sec = r.section_scores or {}
    metrics = r.metrics or {}
    return [
        r.ticker,
        r.company_name or "",
        r.last_evaluated or datetime.now(timezone.utc).isoformat(),
        _num(r.quality_score),
        r.sector or "",
        r.sector_profile or "",
        *[_num(sec.get(s)) for s in _SECTION_COLS],
        *[_num(metrics.get(c)) for c in _METRIC_COLS],
        json.dumps(r.score_breakdown or {}),
    ]


def _to_float(v):
    try:
        return float(v) if v not in ("", None) else None
    except (ValueError, TypeError):
        return None


def _parse_breakdown(v) -> dict:
    if not v:
        return {}
    try:
        parsed = json.loads(v)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _row_to_result(row: list) -> ScreenerResult:
    row = list(row) + [""] * (len(_SCREENER_HEADERS) - len(row))
    sections = {s: _to_float(row[6 + i]) for i, s in enumerate(_SECTION_COLS)}
    metrics = {c: _to_float(row[10 + i]) for i, c in enumerate(_METRIC_COLS)}
    breakdown = _parse_breakdown(row[10 + len(_METRIC_COLS)])
    return ScreenerResult(
        ticker=row[0], company_name=row[1] or None, last_evaluated=row[2] or None,
        quality_score=_to_float(row[3]), sector=row[4] or None,
        sector_profile=row[5] or None, section_scores=sections, metrics=metrics,
        score_breakdown=breakdown,
    )


_SCREENER_TAB = "Screener"
DATABASE_QSCORE_COL = "Q"


def _col_range() -> str:
    # supports > 26 columns (AA..) — compute the end column label
    n = len(_SCREENER_HEADERS)
    label = ""
    x = n
    while x > 0:
        x, rem = divmod(x - 1, 26)
        label = chr(ord("A") + rem) + label
    return f"{_SCREENER_TAB}!A:{label}"


def _ensure_screener_sheet(svc, sheet_id: str) -> None:
    meta = svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
    props = {s["properties"]["title"]: s["properties"] for s in meta.get("sheets", [])}
    if _SCREENER_TAB not in props:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": _SCREENER_TAB}}}]},
        ).execute()
        svc.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=f"{_SCREENER_TAB}!A1",
            valueInputOption="RAW", body={"values": [_SCREENER_HEADERS]},
        ).execute()
        return
    # Tab exists — ensure row 1 is the header row. Repairs a tab created empty (or
    # populated before headers were ever written): without a header row the reader
    # skips the first data row via rows[1:] and the columns stay unlabelled.
    first = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{_SCREENER_TAB}!1:1").execute().get("values", [])
    row1 = first[0] if first else []
    if row1 and row1[0] == _SCREENER_HEADERS[0]:
        if row1 != _SCREENER_HEADERS:
            # header row exists but is outdated (schema grew) — refresh it in place
            svc.spreadsheets().values().update(
                spreadsheetId=sheet_id, range=f"{_SCREENER_TAB}!A1",
                valueInputOption="RAW", body={"values": [_SCREENER_HEADERS]},
            ).execute()
        return
    if row1:
        # real data already sits in row 1 — insert a blank row above it so the
        # header write below doesn't overwrite that record
        svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"insertDimension": {
                "range": {"sheetId": props[_SCREENER_TAB]["sheetId"],
                          "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
                "inheritFromBefore": False}}]},
        ).execute()
    svc.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=f"{_SCREENER_TAB}!A1",
        valueInputOption="RAW", body={"values": [_SCREENER_HEADERS]},
    ).execute()


def _mirror_quality_score(svc, sheet_id: str, ticker: str, score) -> None:
    # ensure the Database Q1 header, then update Q{row} for this ticker if present
    svc.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=f"Database!{DATABASE_QSCORE_COL}1",
        valueInputOption="RAW", body={"values": [["Quality Score"]]},
    ).execute()
    existing = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range="Database!A:A").execute()
    rows = existing.get("values", [])
    for i, row in enumerate(rows):
        if row and row[0].strip().upper() == ticker.upper():
            svc.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"Database!{DATABASE_QSCORE_COL}{i + 1}",
                valueInputOption="RAW",
                body={"values": [[_num(score)]]},
            ).execute()
            return


def _upsert_sync(r: ScreenerResult) -> None:
    svc = _get_service()
    sheet_id = _sheet_id()
    _ensure_screener_sheet(svc, sheet_id)
    existing = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{_SCREENER_TAB}!A:A").execute()
    rows = existing.get("values", [])
    target = None
    for i, row in enumerate(rows):
        if row and row[0].strip().upper() == r.ticker.upper():
            target = i + 1
            break
    new_row = _result_to_row(r)
    if target is None:
        svc.spreadsheets().values().append(
            spreadsheetId=sheet_id, range=f"{_SCREENER_TAB}!A:A",
            valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": [new_row]}).execute()
    else:
        svc.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=f"{_SCREENER_TAB}!A{target}",
            valueInputOption="RAW", body={"values": [new_row]}).execute()
    _mirror_quality_score(svc, sheet_id, r.ticker, r.quality_score)


async def upsert_screener_result(r: ScreenerResult) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _upsert_sync, r)


def _read_sync() -> list[ScreenerResult]:
    svc = _get_service()
    sheet_id = _sheet_id()
    try:
        result = svc.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=_col_range()).execute()
    except Exception as e:
        if "Unable to parse range" in str(e):
            _ensure_screener_sheet(svc, sheet_id)
            return []
        raise
    rows = result.get("values", [])
    return [_row_to_result(r) for r in rows[1:]] if len(rows) >= 2 else []


async def read_screener() -> list[ScreenerResult]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _read_sync)


async def read_screener_one(ticker: str) -> ScreenerResult | None:
    for r in await read_screener():
        if r.ticker.upper() == ticker.upper():
            return r
    return None
