from __future__ import annotations
import asyncio, os
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
    ]


def _to_float(v):
    try:
        return float(v) if v not in ("", None) else None
    except (ValueError, TypeError):
        return None


def _row_to_result(row: list) -> ScreenerResult:
    row = list(row) + [""] * (len(_SCREENER_HEADERS) - len(row))
    sections = {s: _to_float(row[6 + i]) for i, s in enumerate(_SECTION_COLS)}
    metrics = {c: _to_float(row[10 + i]) for i, c in enumerate(_METRIC_COLS)}
    return ScreenerResult(
        ticker=row[0], company_name=row[1] or None, last_evaluated=row[2] or None,
        quality_score=_to_float(row[3]), sector=row[4] or None,
        sector_profile=row[5] or None, section_scores=sections, metrics=metrics,
    )
