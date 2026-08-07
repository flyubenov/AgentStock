from __future__ import annotations
import json
from datetime import datetime, timezone
from risk_reward.models import RiskRewardResult, MetricScore
from services.sheets import (
    _get_service, _sheet_id, _execute, _run_sheets, delete_ticker_row,
)

_RR_TAB = "Risk-Reward"
DATABASE_RR_COL = "R"

_HEADERS = [
    "Ticker", "Company", "Last Evaluated", "Ratio", "Tier",
    "Reward Score", "Risk Score", "Actionable Insight",
    "Metric Scores", "Raw Snapshot", "Status",
]


def _num(v):
    return v if isinstance(v, (int, float)) else ""


def _result_to_row(r: RiskRewardResult) -> list:
    ms = {k: v.model_dump() for k, v in (r.metric_scores or {}).items()}
    return [
        r.ticker, r.company_name or "",
        r.last_evaluated or datetime.now(timezone.utc).isoformat(),
        _num(r.ratio), r.tier or "", _num(r.reward_score), _num(r.risk_score),
        r.actionable_insight or "", json.dumps(ms), json.dumps(r.raw_snapshot or {}),
        r.status,
    ]


def _to_float(v):
    try:
        return float(v) if v not in ("", None) else None
    except (ValueError, TypeError):
        return None


def _parse_json(v) -> dict:
    if not v:
        return {}
    try:
        p = json.loads(v)
        return p if isinstance(p, dict) else {}
    except (ValueError, TypeError):
        return {}


def _row_to_result(row: list) -> RiskRewardResult:
    row = list(row) + [""] * (len(_HEADERS) - len(row))
    ms = {k: MetricScore(**v) for k, v in _parse_json(row[8]).items()}
    return RiskRewardResult(
        ticker=row[0], company_name=row[1] or None, last_evaluated=row[2] or None,
        ratio=_to_float(row[3]), tier=row[4] or None,
        reward_score=_to_float(row[5]), risk_score=_to_float(row[6]),
        actionable_insight=row[7] or None, metric_scores=ms,
        raw_snapshot=_parse_json(row[9]), status=row[10] or "completed",
    )


def _col_range() -> str:
    end = chr(ord("A") + len(_HEADERS) - 1)  # 11 cols -> "K"
    return f"{_RR_TAB}!A:{end}"


def _ensure_rr_sheet(svc, sheet_id: str) -> None:
    meta = _execute(svc.spreadsheets().get(spreadsheetId=sheet_id))
    props = {s["properties"]["title"]: s["properties"] for s in meta.get("sheets", [])}
    if _RR_TAB not in props:
        _execute(svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": _RR_TAB}}}]}))
        _execute(svc.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=f"{_RR_TAB}!A1",
            valueInputOption="RAW", body={"values": [_HEADERS]}))
        return
    first = _execute(svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{_RR_TAB}!1:1")).get("values", [])
    row1 = first[0] if first else []
    if row1 and row1[0] == _HEADERS[0]:
        if row1 != _HEADERS:
            _execute(svc.spreadsheets().values().update(
                spreadsheetId=sheet_id, range=f"{_RR_TAB}!A1",
                valueInputOption="RAW", body={"values": [_HEADERS]}))
        return
    if row1:
        _execute(svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"insertDimension": {"range": {
                "sheetId": props[_RR_TAB]["sheetId"], "dimension": "ROWS",
                "startIndex": 0, "endIndex": 1}, "inheritFromBefore": False}}]}))
    _execute(svc.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=f"{_RR_TAB}!A1",
        valueInputOption="RAW", body={"values": [_HEADERS]}))


def _mirror_ratio(svc, sheet_id: str, ticker: str, ratio) -> None:
    _execute(svc.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=f"Database!{DATABASE_RR_COL}1",
        valueInputOption="RAW", body={"values": [["Risk-Reward"]]}))
    rows = _execute(svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range="Database!A:A")).get("values", [])
    for i, row in enumerate(rows):
        if row and row[0].strip().upper() == ticker.upper():
            _execute(svc.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"Database!{DATABASE_RR_COL}{i + 1}",
                valueInputOption="RAW", body={"values": [[_num(ratio)]]}))
            return


def _upsert_sync(r: RiskRewardResult) -> None:
    svc = _get_service()
    sheet_id = _sheet_id()
    _ensure_rr_sheet(svc, sheet_id)
    rows = _execute(svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{_RR_TAB}!A:A")).get("values", [])
    target = None
    for i, row in enumerate(rows):
        if row and row[0].strip().upper() == r.ticker.upper():
            target = i + 1
            break
    new_row = _result_to_row(r)
    if target is None:
        _execute(svc.spreadsheets().values().append(
            spreadsheetId=sheet_id, range=f"{_RR_TAB}!A:A",
            valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": [new_row]}))
    else:
        _execute(svc.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=f"{_RR_TAB}!A{target}",
            valueInputOption="RAW", body={"values": [new_row]}))
    _mirror_ratio(svc, sheet_id, r.ticker, r.ratio)


async def upsert_risk_reward_result(r: RiskRewardResult) -> None:
    await _run_sheets(_upsert_sync, r)


def _read_sync() -> list[RiskRewardResult]:
    svc = _get_service()
    sheet_id = _sheet_id()
    try:
        result = _execute(svc.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=_col_range()))
    except Exception as e:
        if "Unable to parse range" in str(e):
            _ensure_rr_sheet(svc, sheet_id)
            return []
        raise
    rows = result.get("values", [])
    return [_row_to_result(r) for r in rows[1:]] if len(rows) >= 2 else []


async def read_risk_reward() -> list[RiskRewardResult]:
    return await _run_sheets(_read_sync)


async def read_risk_reward_one(ticker: str) -> RiskRewardResult | None:
    for r in await read_risk_reward():
        if r.ticker.upper() == ticker.upper():
            return r
    return None


async def delete_risk_reward_row(ticker: str) -> bool:
    return await delete_ticker_row(_RR_TAB, ticker)
