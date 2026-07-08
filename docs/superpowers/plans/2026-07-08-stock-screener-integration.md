# Stock Screener Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fully deterministic, no-AI, yfinance-only Stock Screener that produces a 1–10 Business Quality Score per ticker, running alongside but architecturally isolated from the existing Fair Value pipeline.

**Architecture:** New `backend/screener/` package (models → data → metrics → scoring → engine), mirroring `backend/valuation/`. Shared cached low-level yfinance fetchers in `backend/services/statements.py` keep both pipelines from double-hitting the network. Screener results persist to a new "Screener" Google Sheet tab, with the headline Quality Score mirrored into a new column Q on the existing "Database" tab. Orchestrator runs both pipelines in parallel per ticker. Frontend gains a Screener results tab and grid column plus per-row and recalc-all buttons.

**Tech Stack:** Python 3.14, FastAPI, yfinance 1.3.0, pydantic, pytest; React + Vite + TypeScript + Tailwind (frontend).

## Global Constraints

- **No AI / no LLM calls anywhere** in the screener flow. Pure deterministic computation.
- **Data source: yfinance only** (plus `^TNX` for the 10-year Treasury). No other external data.
- **Isolation:** `screener/` must never import from `valuation/` and vice versa. Do not modify `valuation/`, `backend/services/sheets.py` `_result_to_row`/`_DB_HEADERS` (16 cols), or existing Fair Value tests. The screener owns Database column **Q** as a mirror.
- **Graceful degradation:** every metric is `Optional`; a missing field is excluded, never a crash.
- **Percent convention (screener):** growth rates, margins, yields, and pp-spreads are stored in `ScreenerMetrics` as **percent** (e.g. `15.0` = 15%). Pure ratios (Net Debt/EBITDA, OCF/CapEx, Earnings Quality, PEG, Price/FCF, Price/Sales) are stored as **raw ratios**.
- **Tests:** plain `pytest` functions, `pytest.approx` for floats, async tests marked `@pytest.mark.asyncio`, mock yfinance with `unittest.mock.patch`. Run from `backend/` with `python -m pytest`.
- **Score bounds:** final Quality Score is rounded to 1 decimal and clamped to `[1.0, 10.0]`; `None` when insufficient data (`< 6` available scored sub-scores or no income statement).

---

## File Structure

**New backend files**
- `backend/services/statements.py` — cached low-level yfinance fetchers: annual income/balance/cashflow as year-aligned primitive series, plus 10Y Treasury and monthly price history.
- `backend/screener/__init__.py` — package marker.
- `backend/screener/models.py` — `StatementSeries`, `ScreenerInputs`, `ScreenerMetrics`, `ScreenerResult`.
- `backend/screener/metrics.py` — pure functions: CAGR helpers, `compute_metrics(inputs) -> ScreenerMetrics`.
- `backend/screener/scoring.py` — band helpers, sector profiles + pivots, nudge, section rollup, cap rules, `score(metrics, sector) -> (quality_score, section_scores, applied_profile)`.
- `backend/screener/data.py` — `fetch_screener_inputs(ticker) -> ScreenerInputs`.
- `backend/screener/engine.py` — `run(ticker) -> ScreenerResult`.
- `backend/services/screener_sheets.py` — Screener tab I/O + Database-tab Quality Score mirror.

**New backend tests**
- `backend/tests/test_statements.py`, `test_screener_metrics.py`, `test_screener_scoring.py`, `test_screener_engine.py`, `test_screener_sheets.py`.

**Modified backend files**
- `backend/models.py` — add `DatabaseRow` (read DTO = FV fields + `quality_score`).
- `backend/services/sheets.py` — `_read_database_sync` reads `A:Q`, returns `DatabaseRow` with `quality_score`; `read_database()` return type widens.
- `backend/orchestrator/batch.py` — run both pipelines per ticker, upsert both, emit combined event.
- `backend/routers/analysis.py` — combined events; `POST /api/ticker/{ticker}/recalculate`; `POST /api/recalculate-all`.
- `backend/routers/database.py` — return `DatabaseRow[]`; add `GET /api/screener/{ticker}`.

**Frontend**
- `frontend/src/types.ts` — add `ScreenerMetrics`, `ScreenerResult`, `quality_score` on results, `qualityScoreColor`/`qualityScoreBadgeClass`.
- `frontend/src/components/ScreenerPanel.tsx` — new; renders score + section scores + metrics table.
- `frontend/src/pages/TickerDetail.tsx` — tabbed `Fair Value | Screener`.
- `frontend/src/pages/Database.tsx` — Quality Score column, per-row recalc button, recalc-all button.

---

## Phase 1 — Shared cached data layer

### Task 1: Cached statement/treasury/price fetchers

**Files:**
- Create: `backend/services/statements.py`
- Test: `backend/tests/test_statements.py`

**Interfaces:**
- Produces:
  - `fetch_income_stmt(ticker: str) -> dict | None` — `{"years": list[int desc], "rows": dict[str, list[float|None]]}` or `None`.
  - `fetch_balance_sheet(ticker: str) -> dict | None` — same shape.
  - `fetch_cashflow_annual(ticker: str) -> dict | None` — same shape.
  - `fetch_treasury_10y() -> float | None` — decimal yield (e.g. `0.045`).
  - `fetch_price_monthly(ticker: str) -> list[float]` — oldest→newest monthly closes (may be empty).
  - `_statement_to_dict(df) -> dict | None` — pure DataFrame→dict converter (unit-testable without network).

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_statements.py
import pandas as pd
from datetime import datetime
from services.statements import _statement_to_dict


def _df():
    cols = [datetime(2025, 9, 30), datetime(2024, 9, 30), datetime(2023, 9, 30)]
    return pd.DataFrame(
        {cols[0]: [100.0, 40.0], cols[1]: [90.0, float("nan")], cols[2]: [80.0, 30.0]},
        index=["Total Revenue", "EBITDA"],
    )


def test_statement_to_dict_orders_years_desc_and_maps_nan_to_none():
    out = _statement_to_dict(_df())
    assert out["years"] == [2025, 2024, 2023]
    assert out["rows"]["Total Revenue"] == [100.0, 90.0, 80.0]
    assert out["rows"]["EBITDA"] == [40.0, None, 30.0]  # NaN -> None


def test_statement_to_dict_empty_is_none():
    assert _statement_to_dict(None) is None
    assert _statement_to_dict(pd.DataFrame()) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_statements.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.statements'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/statements.py
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
```

Note: `fetch_price_monthly` returns a tuple so it is hashable/`lru_cache`-safe; callers treat it as a sequence.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_statements.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/services/statements.py backend/tests/test_statements.py
git commit -m "feat(screener): shared cached yfinance statement/treasury/price fetchers"
```

---

## Phase 2 — Screener domain types

### Task 2: Screener models

**Files:**
- Create: `backend/screener/__init__.py`, `backend/screener/models.py`
- Test: `backend/tests/test_screener_metrics.py` (bootstrap a models test here)

**Interfaces:**
- Produces:
  - `StatementSeries.from_dict(d: dict | None) -> StatementSeries | None`; methods `.latest(label) -> float|None`, `.series(label) -> list[float|None]`, `.value(label, idx) -> float|None`.
  - `ScreenerInputs` dataclass (fields: `ticker, info, income, balance, cashflow, price_monthly, risk_free`).
  - `ScreenerMetrics(BaseModel)` — all fields default `None` (see Global Constraints for percent vs ratio).
  - `ScreenerResult(BaseModel)` — `ticker, company_name, last_evaluated, quality_score, sector, sector_profile, section_scores, metrics, status, errors`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_screener_metrics.py
from screener.models import StatementSeries, ScreenerMetrics, ScreenerResult


def test_statement_series_lookups():
    s = StatementSeries.from_dict({"years": [2025, 2024, 2023],
                                   "rows": {"Total Revenue": [100.0, 90.0, None]}})
    assert s.latest("Total Revenue") == 100.0
    assert s.value("Total Revenue", 1) == 90.0
    assert s.value("Total Revenue", 2) is None
    assert s.value("Missing", 0) is None
    assert s.series("Total Revenue") == [100.0, 90.0, None]


def test_statement_series_from_none():
    assert StatementSeries.from_dict(None) is None


def test_models_default_to_none():
    m = ScreenerMetrics()
    assert m.roic_ttm is None and m.revenue_cagr_3y is None
    r = ScreenerResult(ticker="AAPL")
    assert r.quality_score is None and r.status == "completed" and r.errors == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_screener_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'screener'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/screener/__init__.py
```

```python
# backend/screener/models.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
from pydantic import BaseModel


@dataclass
class StatementSeries:
    years: list[int]
    rows: dict[str, list[float | None]]

    @classmethod
    def from_dict(cls, d: dict | None) -> "StatementSeries | None":
        if not d:
            return None
        return cls(years=list(d["years"]), rows=dict(d["rows"]))

    def series(self, label: str) -> list[float | None]:
        return self.rows.get(label, [])

    def value(self, label: str, idx: int) -> float | None:
        s = self.rows.get(label)
        if not s or idx >= len(s):
            return None
        return s[idx]

    def latest(self, label: str) -> float | None:
        return self.value(label, 0)


@dataclass
class ScreenerInputs:
    ticker: str
    info: dict
    income: StatementSeries | None
    balance: StatementSeries | None
    cashflow: StatementSeries | None
    price_monthly: tuple[float, ...]
    risk_free: float | None


class ScreenerMetrics(BaseModel):
    # Section I (percent)
    revenue_cagr_3y: float | None = None
    eps_cagr_3y: float | None = None
    fcf_cagr_3y: float | None = None
    fcf_margin: float | None = None
    op_margin: float | None = None
    op_margin_trajectory: float | None = None
    gross_margin: float | None = None
    # Section II (percent; spread in pp)
    roic_ttm: float | None = None
    roic_5y_avg: float | None = None
    wacc: float | None = None
    roic_wacc_spread: float | None = None
    rote: float | None = None
    # Section III (ratios; tangible_bv_per_share is currency)
    net_debt_ebitda: float | None = None
    net_debt_fcf: float | None = None
    ocf_capex: float | None = None
    tangible_bv_per_share: float | None = None
    # Section IV (percent, except earnings_quality ratio)
    shares_cagr_3y: float | None = None
    sbc_pct_rev: float | None = None
    earnings_quality: float | None = None
    insider_ownership: float | None = None
    shareholder_yield: float | None = None
    # Section V — reference only (not scored)
    trailing_pe: float | None = None
    forward_pe: float | None = None
    peg: float | None = None
    price_fcf: float | None = None
    price_sales: float | None = None
    fcf_yield: float | None = None
    owner_earnings_yield: float | None = None
    price_cagr_3y: float | None = None
    price_cagr_5y: float | None = None
    # raw inputs used by cap rules / dual-check
    net_income: float | None = None
    fcf: float | None = None
    revenue_growth: float | None = None
    total_cash: float | None = None
    net_debt: float | None = None
    ebitda: float | None = None
    sector: str | None = None


class ScreenerResult(BaseModel):
    ticker: str
    company_name: str | None = None
    last_evaluated: str | None = None
    quality_score: float | None = None
    sector: str | None = None
    sector_profile: str | None = None
    section_scores: dict[str, float | None] = {}
    metrics: dict = {}
    status: Literal["completed", "failed"] = "completed"
    errors: list[str] = []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_screener_metrics.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/screener/__init__.py backend/screener/models.py backend/tests/test_screener_metrics.py
git commit -m "feat(screener): domain models (StatementSeries, ScreenerMetrics, ScreenerResult)"
```

---

## Phase 3 — Metric computation (pure)

### Task 3: CAGR + series helpers

**Files:**
- Create: `backend/screener/metrics.py`
- Test: `backend/tests/test_screener_metrics.py` (append)

**Interfaces:**
- Produces:
  - `cagr(start: float|None, end: float|None, years: int) -> float|None` — decimal; `None` unless both endpoints > 0 and `years > 0`.
  - `series_cagr(series: list[float|None], span: int) -> float|None` — decimal, from index0 (latest) back to `min(span, len-1)`; needs both endpoints present & > 0.
  - `price_cagr(monthly: Sequence[float], years: int) -> float|None` — decimal from `years*12` months back.
  - `pct(x: float|None) -> float|None` — `x*100` or `None`.

- [ ] **Step 1: Write the failing test** (append to `test_screener_metrics.py`)

```python
from screener.metrics import cagr, series_cagr, price_cagr, pct


def test_cagr_basic_and_guards():
    assert cagr(100.0, 133.1, 3) == pytest.approx(0.10, abs=1e-4)
    assert cagr(0, 100.0, 3) is None       # non-positive start
    assert cagr(100.0, -5.0, 3) is None    # non-positive end
    assert cagr(100.0, 110.0, 0) is None   # zero years


def test_series_cagr_uses_available_span():
    # 5 points, span 3 -> compare index0 vs index3 over 3 years
    s = [161.05, 146.41, 133.1, 121.0, 110.0]
    assert series_cagr(s, 3) == pytest.approx(0.10, abs=1e-4)
    # only 3 points, span 5 -> falls back to 2-year span
    assert series_cagr([121.0, 110.0, 100.0], 5) == pytest.approx(0.10, abs=1e-4)
    assert series_cagr([100.0], 3) is None
    assert series_cagr([None, 100.0, 121.0], 2) is None  # latest missing


def test_price_cagr_and_pct():
    months = [float(100 * (1.10 ** (i / 12))) for i in range(37)]  # 36 mo -> +10%/yr
    assert price_cagr(months, 3) == pytest.approx(0.10, abs=1e-3)
    assert price_cagr([100.0], 3) is None
    assert pct(0.153) == pytest.approx(15.3)
    assert pct(None) is None
```

Add `import pytest` at the top of the test file if not already present.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_screener_metrics.py -k "cagr or pct" -v`
Expected: FAIL with `ImportError: cannot import name 'cagr'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/screener/metrics.py
from __future__ import annotations
from collections.abc import Sequence
from screener.models import ScreenerInputs, ScreenerMetrics, StatementSeries


def cagr(start: float | None, end: float | None, years: int) -> float | None:
    if start is None or end is None or years <= 0:
        return None
    if start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def series_cagr(series: list[float | None], span: int) -> float | None:
    if not series or len(series) < 2:
        return None
    end = series[0]
    idx = min(span, len(series) - 1)
    return cagr(series[idx], end, idx)


def price_cagr(monthly: Sequence[float], years: int) -> float | None:
    if not monthly or len(monthly) < 2:
        return None
    end = monthly[-1]
    months_back = years * 12
    idx = max(0, len(monthly) - 1 - months_back)
    span_years = (len(monthly) - 1 - idx) / 12
    if span_years <= 0:
        return None
    return _cagr_frac(monthly[idx], end, span_years)


def _cagr_frac(start: float | None, end: float | None, years: float) -> float | None:
    if start is None or end is None or years <= 0 or start <= 0 or end <= 0:
        return None
    return (end / start) ** (1 / years) - 1


def pct(x: float | None) -> float | None:
    return None if x is None else x * 100.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_screener_metrics.py -k "cagr or pct" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/screener/metrics.py backend/tests/test_screener_metrics.py
git commit -m "feat(screener): CAGR and percent helpers"
```

---

### Task 4: `compute_metrics` — Sections II & III (ROIC, WACC, leverage)

**Files:**
- Modify: `backend/screener/metrics.py`
- Test: `backend/tests/test_screener_metrics.py` (append)

**Interfaces:**
- Produces `compute_metrics(inp: ScreenerInputs) -> ScreenerMetrics`. This task fills the Section II/III fields; Task 5 fills I/IV/V in the same function. Implement incrementally but keep one function.
- Helpers (module-level, testable): `roic(ebit, tax_rate, invested_capital) -> float|None` (decimal), `wacc(inp, tax_rate) -> float|None` (decimal), `_tax_rate(income) -> float`.

- [ ] **Step 1: Write the failing test**

```python
from screener.metrics import compute_metrics, roic, wacc as wacc_fn
from screener.models import StatementSeries, ScreenerInputs


def _mk_inputs(**over):
    income = StatementSeries(
        years=[2025, 2024, 2023, 2022],
        rows={
            "EBIT": [200.0, 180.0, 150.0, 120.0],
            "Tax Rate For Calcs": [0.21, 0.21, 0.21, 0.21],
            "Net Income": [160.0, 150.0, 130.0, 100.0],
            "Total Revenue": [1000.0, 900.0, 800.0, 700.0],
            "Interest Expense": [10.0, 10.0, 10.0, 10.0],
            "Gross Profit": [500.0, 450.0, 400.0, 350.0],
            "Operating Income": [220.0, 190.0, 160.0, 130.0],
            "Diluted EPS": [3.2, 3.0, 2.6, 2.0],
            "Diluted Average Shares": [50.0, 51.0, 52.0, 53.0],
        },
    )
    balance = StatementSeries(
        years=[2025, 2024, 2023, 2022],
        rows={
            "Invested Capital": [1000.0, 950.0, 900.0, 850.0],
            "Tangible Book Value": [800.0, 750.0, 700.0, 650.0],
            "Net Debt": [-50.0, 0.0, 50.0, 100.0],
            "Ordinary Shares Number": [50.0, 51.0, 52.0, 53.0],
        },
    )
    cashflow = StatementSeries(
        years=[2025, 2024, 2023, 2022],
        rows={
            "Free Cash Flow": [150.0, 130.0, 110.0, 90.0],
            "Operating Cash Flow": [200.0, 180.0, 160.0, 140.0],
            "Capital Expenditure": [-50.0, -50.0, -50.0, -50.0],
            "Stock Based Compensation": [20.0, 20.0, 20.0, 20.0],
            "Repurchase Of Capital Stock": [-30.0, -30.0, -30.0, -30.0],
            "Cash Dividends Paid": [-10.0, -10.0, -10.0, -10.0],
        },
    )
    info = {"beta": 1.0, "totalDebt": 100.0, "totalCash": 150.0, "ebitda": 250.0,
            "marketCap": 5000.0, "operatingMargins": 0.22, "grossMargins": 0.50,
            "heldPercentInsiders": 0.03, "trailingPE": 25.0, "forwardPE": 20.0,
            "trailingPegRatio": 1.5, "priceToSalesTrailing12Months": 5.0,
            "enterpriseValue": 4950.0, "revenueGrowth": 0.11, "sector": "Technology"}
    info.update(over.pop("info", {}))
    return ScreenerInputs(ticker="T", info=info, income=income, balance=balance,
                          cashflow=cashflow, price_monthly=tuple(), risk_free=0.045, **over)


def test_roic_and_wacc():
    # NOPAT = 200*(1-0.21)=158; /1000 = 15.8%
    assert roic(200.0, 0.21, 1000.0) == pytest.approx(0.158, abs=1e-4)
    assert roic(200.0, 0.21, 0) is None
    inp = _mk_inputs()
    # WACC in (0, 1); equity-heavy so near cost of equity = 0.045 + 1.0*0.05 = 0.095
    w = wacc_fn(inp, 0.21)
    assert 0.05 < w < 0.12


def test_compute_section_ii_iii():
    m = compute_metrics(_mk_inputs())
    assert m.roic_ttm == pytest.approx(15.8, abs=0.1)         # percent
    assert m.roic_5y_avg is not None
    assert m.rote == pytest.approx(160.0 / 800.0 * 100, abs=0.1)
    assert m.net_debt_ebitda == pytest.approx(-50.0 / 250.0, abs=1e-4)  # net cash -> negative
    assert m.ocf_capex == pytest.approx(200.0 / 50.0, abs=1e-4)
    assert m.roic_wacc_spread is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_screener_metrics.py -k "roic or section_ii" -v`
Expected: FAIL (`cannot import name 'compute_metrics'`)

- [ ] **Step 3: Write minimal implementation** (append to `metrics.py`)

```python
ERP = 0.05  # equity risk premium (assumed constant)
DEFAULT_RISK_FREE = 0.043


def _tax_rate(income: StatementSeries | None) -> float:
    if income is None:
        return 0.21
    t = income.latest("Tax Rate For Calcs")
    if t is None or t < 0 or t > 0.6:
        return 0.21
    return t


def roic(ebit: float | None, tax_rate: float, invested_capital: float | None) -> float | None:
    if ebit is None or invested_capital is None or invested_capital <= 0:
        return None
    return ebit * (1 - tax_rate) / invested_capital


def wacc(inp: ScreenerInputs, tax_rate: float) -> float | None:
    info = inp.info
    beta = info.get("beta")
    if beta is None:
        return None
    rf = inp.risk_free if inp.risk_free is not None else DEFAULT_RISK_FREE
    cost_equity = rf + beta * ERP
    debt = info.get("totalDebt") or 0.0
    equity = info.get("marketCap") or 0.0
    total = debt + equity
    if total <= 0:
        return cost_equity
    interest = None
    if inp.income is not None:
        interest = inp.income.latest("Interest Expense")
    cost_debt = (abs(interest) / debt) * (1 - tax_rate) if (interest and debt > 0) else 0.0
    return (equity / total) * cost_equity + (debt / total) * cost_debt


def compute_metrics(inp: ScreenerInputs) -> ScreenerMetrics:
    m = ScreenerMetrics()
    info = inp.info
    inc, bal, cf = inp.income, inp.balance, inp.cashflow
    tax = _tax_rate(inc)

    # --- Section II ---
    if inc is not None and bal is not None:
        m.roic_ttm = pct(roic(inc.latest("EBIT"), tax, bal.latest("Invested Capital")))
        annual = []
        for i in range(len(inc.years)):
            r = roic(inc.value("EBIT", i), tax, bal.value("Invested Capital", i))
            if r is not None:
                annual.append(r)
        if annual:
            m.roic_5y_avg = pct(sum(annual) / len(annual))
        ni = inc.latest("Net Income")
        tbv = bal.latest("Tangible Book Value")
        if ni is not None and tbv and tbv > 0:
            m.rote = ni / tbv * 100.0
    w = wacc(inp, tax)
    m.wacc = pct(w)
    if m.roic_ttm is not None and w is not None:
        m.roic_wacc_spread = m.roic_ttm - w * 100.0

    # --- Section III ---
    net_debt = bal.latest("Net Debt") if bal is not None else None
    if net_debt is None and info.get("totalDebt") is not None:
        net_debt = (info.get("totalDebt") or 0.0) - (info.get("totalCash") or 0.0)
    m.net_debt = net_debt
    m.ebitda = info.get("ebitda")
    if net_debt is not None and m.ebitda:
        m.net_debt_ebitda = net_debt / m.ebitda
    fcf = cf.latest("Free Cash Flow") if cf is not None else info.get("freeCashflow")
    m.fcf = fcf
    if net_debt is not None and fcf:
        m.net_debt_fcf = net_debt / fcf
    if cf is not None:
        ocf = cf.latest("Operating Cash Flow")
        capex = cf.latest("Capital Expenditure")
        if ocf is not None and capex:
            m.ocf_capex = ocf / abs(capex)
    if bal is not None:
        tbv = bal.latest("Tangible Book Value")
        shares = bal.latest("Ordinary Shares Number") or info.get("sharesOutstanding")
        if tbv is not None and shares:
            m.tangible_bv_per_share = tbv / shares

    m.sector = info.get("sector")
    return m
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_screener_metrics.py -k "roic or section_ii" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/screener/metrics.py backend/tests/test_screener_metrics.py
git commit -m "feat(screener): compute Section II/III metrics (ROIC, WACC, leverage)"
```

---

### Task 5: `compute_metrics` — Sections I, IV, V

**Files:**
- Modify: `backend/screener/metrics.py`
- Test: `backend/tests/test_screener_metrics.py` (append)

**Interfaces:**
- Extends `compute_metrics` to fill Section I (growth/margins), IV (dilution/quality), V (valuation reference). No new public functions.

- [ ] **Step 1: Write the failing test**

```python
def test_compute_section_i_iv_v():
    m = compute_metrics(_mk_inputs())
    # Section I
    assert m.revenue_cagr_3y == pytest.approx(
        ((1000.0 / 700.0) ** (1 / 3) - 1) * 100, abs=0.1)
    assert m.eps_cagr_3y is not None
    assert m.fcf_cagr_3y is not None
    assert m.fcf_margin == pytest.approx(150.0 / 1000.0 * 100, abs=0.1)
    assert m.op_margin == pytest.approx(22.0, abs=0.1)
    assert m.gross_margin == pytest.approx(50.0, abs=0.1)
    # Section IV
    assert m.shares_cagr_3y is not None and m.shares_cagr_3y < 0  # buyback
    assert m.sbc_pct_rev == pytest.approx(20.0 / 1000.0 * 100, abs=0.1)
    assert m.earnings_quality == pytest.approx(200.0 / 160.0, abs=1e-3)
    assert m.insider_ownership == pytest.approx(3.0, abs=0.1)
    assert m.shareholder_yield == pytest.approx((30.0 + 10.0) / 5000.0 * 100, abs=0.1)
    # Section V reference
    assert m.trailing_pe == 25.0 and m.forward_pe == 20.0 and m.peg == 1.5
    assert m.fcf_yield == pytest.approx(150.0 / 4950.0 * 100, abs=0.1)
    # raw cap-rule inputs
    assert m.net_income == 160.0 and m.revenue_growth == pytest.approx(11.0, abs=0.1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_screener_metrics.py -k section_i_iv_v -v`
Expected: FAIL (assertions on `None`)

- [ ] **Step 3: Write minimal implementation** — insert before `m.sector = ...` (end of `compute_metrics`):

```python
    # --- Section I ---
    if inc is not None:
        m.revenue_cagr_3y = pct(series_cagr(inc.series("Total Revenue"), 3))
        m.eps_cagr_3y = pct(series_cagr(inc.series("Diluted EPS"), 3))
    if cf is not None:
        m.fcf_cagr_3y = pct(series_cagr(cf.series("Free Cash Flow"), 3))
    revenue = info.get("totalRevenue") or (inc.latest("Total Revenue") if inc else None)
    if fcf is not None and revenue:
        m.fcf_margin = fcf / revenue * 100.0
    m.op_margin = pct(info.get("operatingMargins"))
    m.gross_margin = pct(info.get("grossMargins"))
    if inc is not None and revenue:
        # operating-margin trajectory: latest OM minus OM at oldest available year (pp)
        oi_old = inc.value("Operating Income", min(3, len(inc.years) - 1))
        rev_old = inc.value("Total Revenue", min(3, len(inc.years) - 1))
        oi_new = inc.latest("Operating Income")
        if oi_old is not None and rev_old and oi_new is not None and revenue:
            m.op_margin_trajectory = (oi_new / revenue - oi_old / rev_old) * 100.0

    # --- Section IV ---
    if inc is not None:
        shares_series = inc.series("Diluted Average Shares")
        m.shares_cagr_3y = pct(series_cagr(shares_series, 3))
    if cf is not None and revenue:
        sbc = cf.latest("Stock Based Compensation")
        if sbc is not None:
            m.sbc_pct_rev = abs(sbc) / revenue * 100.0
    if cf is not None:
        ocf = cf.latest("Operating Cash Flow")
        ni = inc.latest("Net Income") if inc else None
        if ocf is not None and ni and abs(ni) > 1e-6:
            m.earnings_quality = ocf / ni
    m.insider_ownership = pct(info.get("heldPercentInsiders"))
    mktcap = info.get("marketCap")
    if cf is not None and mktcap:
        buyback = cf.latest("Repurchase Of Capital Stock") or 0.0
        divs = cf.latest("Cash Dividends Paid") or 0.0
        m.shareholder_yield = (abs(buyback) + abs(divs)) / mktcap * 100.0

    # --- Section V (reference, not scored) ---
    m.trailing_pe = info.get("trailingPE")
    m.forward_pe = info.get("forwardPE")
    m.peg = info.get("trailingPegRatio")
    m.price_sales = info.get("priceToSalesTrailing12Months")
    ev = info.get("enterpriseValue")
    if fcf and mktcap:
        m.price_fcf = mktcap / fcf if fcf > 0 else None
    if fcf is not None and ev:
        m.fcf_yield = fcf / ev * 100.0
    if m.fcf_yield is not None and inp.risk_free is not None:
        m.owner_earnings_yield = m.fcf_yield - inp.risk_free * 100.0
    m.price_cagr_3y = pct(price_cagr(inp.price_monthly, 3))
    m.price_cagr_5y = pct(price_cagr(inp.price_monthly, 5))

    # --- raw cap-rule inputs ---
    m.net_income = inc.latest("Net Income") if inc else None
    m.revenue_growth = pct(info.get("revenueGrowth"))
    m.total_cash = info.get("totalCash")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_screener_metrics.py -v`
Expected: PASS (all metric tests)

- [ ] **Step 5: Commit**

```bash
git add backend/screener/metrics.py backend/tests/test_screener_metrics.py
git commit -m "feat(screener): compute Section I/IV/V metrics"
```

---

## Phase 4 — Scoring (deterministic rubric)

### Task 6: Band helpers + sector-relative leverage score

**Files:**
- Create: `backend/screener/scoring.py`
- Test: `backend/tests/test_screener_scoring.py`

**Interfaces:**
- Produces:
  - `score_high(value, bands, below) -> float|None` — higher is better; `bands` = list of `(threshold, score)` DESC; `value >= threshold` → score, else `below`.
  - `score_low(value, bands, above) -> float|None` — lower is better; `bands` ASC; `value <= threshold` → score, else `above`.
  - `leverage_score(r, pivot) -> float|None` — sector-relative 6-band scale (§5.3.1); `pivot None` → `None`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_screener_scoring.py
import pytest
from screener.scoring import score_high, score_low, leverage_score


def test_score_high_bands():
    bands = [(20, 10), (15, 8.5), (10, 6.5), (5, 4), (0, 2)]
    assert score_high(25, bands, 0) == 10
    assert score_high(15, bands, 0) == 8.5
    assert score_high(3, bands, 0) == 2
    assert score_high(-1, bands, 0) == 0
    assert score_high(None, bands, 0) is None


def test_score_low_bands():
    bands = [(2, 10), (5, 8), (10, 6), (15, 3.5), (20, 1.5)]
    assert score_low(1, bands, 0) == 10
    assert score_low(5, bands, 0) == 8
    assert score_low(25, bands, 0) == 0
    assert score_low(None, bands, 0) is None


def test_leverage_score_is_sector_relative():
    # utility pivot 4.5: at 4.5 -> 7 (comfortable); at 7 -> 2
    assert leverage_score(-1, 4.5) == 10          # net cash
    assert leverage_score(4.5, 4.5) == 7
    assert leverage_score(7.0, 4.5) == 2
    # tech pivot 2.5: 4.5 is deep in penalty
    assert leverage_score(4.5, 2.5) == 2
    assert leverage_score(3.0, 2.5) == 4.5
    assert leverage_score(None, 2.5) is None
    assert leverage_score(3.0, None) is None      # financials skip
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_screener_scoring.py -v`
Expected: FAIL (`No module named 'screener.scoring'`)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/screener/scoring.py
from __future__ import annotations
from screener.models import ScreenerMetrics


def score_high(value: float | None, bands: list[tuple[float, float]], below: float) -> float | None:
    if value is None:
        return None
    for thr, sc in bands:
        if value >= thr:
            return sc
    return below


def score_low(value: float | None, bands: list[tuple[float, float]], above: float) -> float | None:
    if value is None:
        return None
    for thr, sc in bands:
        if value <= thr:
            return sc
    return above


def leverage_score(r: float | None, pivot: float | None) -> float | None:
    if r is None or pivot is None:
        return None
    if r <= 0:
        return 10.0
    if r <= 0.5 * pivot:
        return 9.0
    if r <= pivot:
        return 7.0
    if r <= 1.4 * pivot:
        return 4.5
    if r <= 1.8 * pivot:
        return 2.0
    return 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_screener_scoring.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/screener/scoring.py backend/tests/test_screener_scoring.py
git commit -m "feat(screener): scoring band helpers + sector-relative leverage score"
```

---

### Task 7: Sector profiles + base selection + metric nudge

**Files:**
- Modify: `backend/screener/scoring.py`
- Test: `backend/tests/test_screener_scoring.py` (append)

**Interfaces:**
- Produces:
  - `PROFILES: dict[str, dict]` — each `{"w": (i,ii,iii,iv), "P": float|None, "Q": float|None}`.
  - `SECTOR_TO_PROFILE: dict[str, str]` (lowercased sector → profile key).
  - `base_profile(sector: str|None) -> str`.
  - `apply_nudge(base: str, m: ScreenerMetrics) -> str`.

- [ ] **Step 1: Write the failing test**

```python
from screener.scoring import PROFILES, base_profile, apply_nudge
from screener.models import ScreenerMetrics


def test_profiles_weights_sum_to_one():
    for name, p in PROFILES.items():
        assert abs(sum(p["w"]) - 1.0) < 1e-9, name


def test_base_profile_mapping_and_default():
    assert base_profile("Technology") == "TECH_GROWTH"
    assert base_profile("communication services") == "BALANCED"
    assert base_profile("Utilities") == "DEFENSIVE_INCOME"
    assert base_profile("Financial Services") == "FINANCIALS"
    assert base_profile("Real Estate") == "REIT"
    assert base_profile(None) == "BALANCED"
    assert base_profile("Nonsense Sector") == "BALANCED"


def test_growth_override_nudge():
    # BALANCED + high revenue CAGR + net cash -> TECH_GROWTH
    m = ScreenerMetrics(revenue_cagr_3y=18.0, net_debt=-100.0)
    assert apply_nudge("BALANCED", m) == "TECH_GROWTH"
    # not enough growth -> stays BALANCED
    assert apply_nudge("BALANCED", ScreenerMetrics(revenue_cagr_3y=8.0, net_debt=-100.0)) == "BALANCED"


def test_special_profile_data_fit_fallback():
    # FINANCIALS/REIT label but operates like a normal company (material positive
    # EBITDA, normal leverage < 4, a real operating-margin signal) -> BALANCED.
    normal = ScreenerMetrics(ebitda=500.0, net_debt_ebitda=1.0, op_margin=20.0)
    assert apply_nudge("FINANCIALS", normal) == "BALANCED"
    assert apply_nudge("REIT", normal) == "BALANCED"
    # A real bank: no meaningful EBITDA signal -> stays FINANCIALS.
    assert apply_nudge("FINANCIALS", ScreenerMetrics(ebitda=None)) == "FINANCIALS"
    # High leverage (>= 4) does not trigger the fallback.
    assert apply_nudge("REIT", ScreenerMetrics(ebitda=500.0, net_debt_ebitda=6.0,
                                               op_margin=20.0)) == "REIT"
```

Note: the "EBITDA/Revenue ≥ 8%" test in §5.3.2 needs revenue. Since `ScreenerMetrics` does not store raw revenue, implement the data-fit check using `ebitda` present & positive **and** `net_debt_ebitda` present & `< 4` **and** an operating-margin signal present (`op_margin` not None) as the deterministic proxy for "operates like a normal company." Adjust the test above to match this rule (it does: `fin_revenue_ok` has `op_margin=20.0`).

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_screener_scoring.py -k "profile or nudge" -v`
Expected: FAIL (`cannot import name 'PROFILES'`)

- [ ] **Step 3: Write minimal implementation** (append to `scoring.py`)

```python
PROFILES: dict[str, dict] = {
    "TECH_GROWTH":         {"w": (0.35, 0.30, 0.15, 0.20), "P": 2.5, "Q": 3.0},
    "BALANCED":            {"w": (0.30, 0.30, 0.20, 0.20), "P": 2.5, "Q": 3.0},
    "DEFENSIVE_INCOME":    {"w": (0.15, 0.25, 0.35, 0.25), "P": 4.5, "Q": 6.0},
    "INDUSTRIAL_CYCLICAL": {"w": (0.25, 0.30, 0.30, 0.15), "P": 3.0, "Q": 4.0},
    "FINANCIALS":          {"w": (0.35, 0.40, 0.00, 0.25), "P": None, "Q": None},
    "REIT":                {"w": (0.30, 0.20, 0.25, 0.25), "P": 6.5, "Q": 8.0},
}

SECTOR_TO_PROFILE: dict[str, str] = {
    "technology": "TECH_GROWTH",
    "communication services": "BALANCED",
    "consumer cyclical": "BALANCED",
    "healthcare": "BALANCED",
    "utilities": "DEFENSIVE_INCOME",
    "consumer defensive": "DEFENSIVE_INCOME",
    "industrials": "INDUSTRIAL_CYCLICAL",
    "basic materials": "INDUSTRIAL_CYCLICAL",
    "energy": "INDUSTRIAL_CYCLICAL",
    "financial services": "FINANCIALS",
    "real estate": "REIT",
}


def base_profile(sector: str | None) -> str:
    return SECTOR_TO_PROFILE.get((sector or "").strip().lower(), "BALANCED")


def apply_nudge(base: str, m: ScreenerMetrics) -> str:
    # 1. Growth override: BALANCED + strong revenue growth + net cash -> TECH_GROWTH
    if base == "BALANCED" and (m.revenue_cagr_3y or 0) >= 15.0 and (m.net_debt is not None and m.net_debt < 0):
        return "TECH_GROWTH"
    # 2. Special-profile data-fit fallback: FINANCIALS/REIT that operate like a
    #    normal company (material positive EBITDA, normal leverage, real op margin).
    if base in ("FINANCIALS", "REIT"):
        if (m.ebitda is not None and m.ebitda > 0
                and m.net_debt_ebitda is not None and m.net_debt_ebitda < 4
                and m.op_margin is not None):
            return "BALANCED"
    return base
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_screener_scoring.py -k "profile or nudge" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/screener/scoring.py backend/tests/test_screener_scoring.py
git commit -m "feat(screener): sector profiles, base selection, deterministic nudge"
```

---

### Task 8: Section sub-scores + dual-check

**Files:**
- Modify: `backend/screener/scoring.py`
- Test: `backend/tests/test_screener_scoring.py` (append)

**Interfaces:**
- Produces:
  - Band constants: `ROIC_BANDS, SPREAD_BANDS, ROTE_BANDS, GROWTH_BANDS, FCF_CAGR_BANDS, MARGIN_LEVEL_BANDS, TRAJECTORY_BANDS, GROSS_MARGIN_BANDS, OCF_CAPEX_BANDS, SHARES_BANDS, SBC_BANDS, EQ_BANDS, INSIDER_BANDS, YIELD_BANDS` (module-level).
  - `section_scores(m: ScreenerMetrics, profile: str) -> dict[str, float|None]` — keys `"I","II","III","IV"`; each = mean of available sub-scores; `None` if none available. Section III applies the Balance-Sheet Dual-Check.

- [ ] **Step 1: Write the failing test**

```python
from screener.scoring import section_scores
from screener.models import ScreenerMetrics


def _strong():
    return ScreenerMetrics(
        revenue_cagr_3y=18, eps_cagr_3y=18, fcf_cagr_3y=16, fcf_margin=22,
        op_margin=28, op_margin_trajectory=3, gross_margin=65,
        roic_ttm=22, roic_5y_avg=20, roic_wacc_spread=12, rote=26,
        net_debt_ebitda=1.0, net_debt_fcf=2.0, ocf_capex=6,
        shares_cagr_3y=-2, sbc_pct_rev=1.5, earnings_quality=1.3,
        insider_ownership=12, shareholder_yield=7,
    )


def test_strong_company_high_sections():
    s = section_scores(_strong(), "BALANCED")
    assert s["I"] > 8 and s["II"] > 8 and s["III"] > 7 and s["IV"] > 7


def test_section_renormalizes_over_available():
    m = ScreenerMetrics(roic_ttm=22)  # only one Section II metric present
    s = section_scores(m, "BALANCED")
    assert s["II"] == 10.0            # mean over the single available sub-score
    assert s["I"] is None             # nothing in Section I


def test_dual_check_uses_ebitda_when_fcf_noise():
    # capex cycle: Net Debt/FCF terrible, Net Debt/EBITDA healthy (<2.5)
    m = ScreenerMetrics(net_debt_ebitda=1.2, net_debt_fcf=9.0, ocf_capex=2.0)
    s_dual = section_scores(m, "BALANCED")
    # without dual-check the awful ND/FCF would drag III far lower; assert it's protected
    assert s_dual["III"] >= 6.0


def test_financials_section_iii_ignores_leverage():
    # FINANCIALS pivots are None -> leverage sub-scores are None; only OCF/CapEx
    # remains. (Section III weight is 0.0 for FINANCIALS, so this never affects the
    # composite — but the sub-score should still reflect just the scorable metric.)
    m = ScreenerMetrics(net_debt_ebitda=1.0, net_debt_fcf=2.0, ocf_capex=5.0)
    s = section_scores(m, "FINANCIALS")
    assert s["III"] == 10.0  # OCF/CapEx 5.0 -> 10; leverage metrics excluded
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_screener_scoring.py -k section -v`
Expected: FAIL (`cannot import name 'section_scores'`)

- [ ] **Step 3: Write minimal implementation** (append to `scoring.py`)

```python
ROIC_BANDS = [(20, 10), (15, 8.5), (10, 6.5), (5, 4), (0, 2)]
SPREAD_BANDS = [(10, 10), (5, 8), (0, 5.5), (-5, 2.5)]
ROTE_BANDS = [(25, 10), (20, 8.5), (15, 7), (10, 5), (5, 3)]
GROWTH_BANDS = [(20, 10), (15, 8.5), (10, 7), (5, 5), (2, 3), (0, 1.5)]
FCF_CAGR_BANDS = [(15, 10), (10, 8), (5, 6), (0, 4)]
FCF_MARGIN_BANDS = [(20, 10), (15, 8.5), (10, 7), (5, 5), (0, 3)]
MARGIN_LEVEL_BANDS = [(25, 10), (15, 8), (8, 6), (0, 3)]
TRAJECTORY_BANDS = [(2, 10), (0, 7), (-2, 4)]
GROSS_MARGIN_BANDS = [(60, 10), (40, 8), (25, 6), (10, 4)]
OCF_CAPEX_BANDS = [(5, 10), (3, 8), (2, 6), (1.5, 4), (1, 2)]
SHARES_BANDS = [(-3, 10), (-1, 8.5), (0, 7), (1, 5), (3, 3)]   # score_low
SBC_BANDS = [(2, 10), (5, 8), (10, 6), (15, 3.5), (20, 1.5)]   # score_low
EQ_BANDS = [(1.2, 10), (1.0, 8.5), (0.8, 6), (0.6, 4)]
INSIDER_BANDS = [(10, 10), (5, 8), (2, 6), (0.5, 4)]
YIELD_BANDS = [(6, 10), (4, 8.5), (2, 6.5), (0, 4)]


def _mean(vals: list[float | None]) -> float | None:
    present = [v for v in vals if v is not None]
    return sum(present) / len(present) if present else None


def _section_iii(m: ScreenerMetrics, profile: str) -> float | None:
    p = PROFILES[profile]
    nde = leverage_score(m.net_debt_ebitda, p["P"])
    ndf = leverage_score(m.net_debt_fcf, p["Q"])
    ocf = score_high(m.ocf_capex, OCF_CAPEX_BANDS, 0)
    # Balance-Sheet Dual-Check: FCF-based debt looks far worse than EBITDA-based
    # AND EBITDA leverage is healthy (<2.5) -> treat ND/FCF as capex-cycle noise.
    if (nde is not None and ndf is not None and m.net_debt_ebitda is not None
            and m.net_debt_ebitda < 2.5 and ndf < nde - 2):
        ndf = None  # drop the noisy metric
    return _mean([nde, ndf, ocf])


def section_scores(m: ScreenerMetrics, profile: str) -> dict[str, float | None]:
    section_i = _mean([
        score_high(m.revenue_cagr_3y, GROWTH_BANDS, 0),
        score_high(m.eps_cagr_3y, GROWTH_BANDS, 0),
        score_high(m.fcf_cagr_3y, FCF_CAGR_BANDS, 1),
        score_high(m.fcf_margin, FCF_MARGIN_BANDS, 0),
        score_high(m.op_margin, MARGIN_LEVEL_BANDS, 0),
        score_high(m.op_margin_trajectory, TRAJECTORY_BANDS, 1),
        score_high(m.gross_margin, GROSS_MARGIN_BANDS, 2),
    ])
    section_ii = _mean([
        score_high(m.roic_ttm, ROIC_BANDS, 0),
        score_high(m.roic_5y_avg, ROIC_BANDS, 0),
        score_high(m.roic_wacc_spread, SPREAD_BANDS, 0),
        score_high(m.rote, ROTE_BANDS, 1),
    ])
    section_iv = _mean([
        score_low(m.shares_cagr_3y, SHARES_BANDS, 1),
        score_low(m.sbc_pct_rev, SBC_BANDS, 0),
        score_high(m.earnings_quality, EQ_BANDS, 1.5),
        score_high(m.insider_ownership, INSIDER_BANDS, 2),
        score_high(m.shareholder_yield, YIELD_BANDS, 1.5),
    ])
    return {"I": section_i, "II": section_ii, "III": _section_iii(m, profile), "IV": section_iv}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_screener_scoring.py -k section -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/screener/scoring.py backend/tests/test_screener_scoring.py
git commit -m "feat(screener): section sub-scores with balance-sheet dual-check"
```

---

### Task 9: Composite, cap rules, and top-level `score()`

**Files:**
- Modify: `backend/screener/scoring.py`
- Test: `backend/tests/test_screener_scoring.py` (append)

**Interfaces:**
- Produces:
  - `MIN_SCORED_SUBSCORES = 6`
  - `score(m: ScreenerMetrics, sector: str | None) -> tuple[float | None, dict[str, float | None], str]` — returns `(quality_score, section_scores, applied_profile)`. Applies profile selection + nudge, composite with section renormalization, Unprofitable Cap Rule, final clamp/round. `quality_score` is `None` when fewer than `MIN_SCORED_SUBSCORES` sub-scores are available.

- [ ] **Step 1: Write the failing test**

```python
from screener.scoring import score, MIN_SCORED_SUBSCORES
from screener.models import ScreenerMetrics


def test_score_strong_company_high():
    m = ScreenerMetrics(
        revenue_cagr_3y=18, eps_cagr_3y=18, fcf_cagr_3y=16, fcf_margin=22,
        op_margin=28, op_margin_trajectory=3, gross_margin=65,
        roic_ttm=22, roic_5y_avg=20, roic_wacc_spread=12, rote=26,
        net_debt_ebitda=1.0, net_debt_fcf=2.0, ocf_capex=6,
        shares_cagr_3y=-2, sbc_pct_rev=1.5, earnings_quality=1.3,
        insider_ownership=12, shareholder_yield=7,
        net_income=100, fcf=100, sector="Technology",
    )
    q, sections, profile = score(m, "Technology")
    assert profile == "TECH_GROWTH"
    assert 8.0 <= q <= 10.0
    assert set(sections) == {"I", "II", "III", "IV"}


def test_insufficient_data_returns_none():
    m = ScreenerMetrics(roic_ttm=20, rote=25)  # only 2 sub-scores
    q, _, _ = score(m, "Technology")
    assert q is None


def test_unprofitable_cap_rule():
    # negative net income caps at 8.0 even with otherwise strong metrics
    strong = dict(
        revenue_cagr_3y=25, eps_cagr_3y=25, fcf_cagr_3y=20, fcf_margin=30,
        op_margin=30, op_margin_trajectory=4, gross_margin=70,
        roic_ttm=30, roic_5y_avg=28, roic_wacc_spread=20, rote=30,
        net_debt_ebitda=0.5, net_debt_fcf=1.0, ocf_capex=8,
        shares_cagr_3y=-3, sbc_pct_rev=1, earnings_quality=1.5,
        insider_ownership=15, shareholder_yield=8,
    )
    # elite unprofitable (Rule of 40 pass, long runway) -> capped 7.0..8.0
    elite = ScreenerMetrics(**strong, net_income=-10, fcf=50,
                            revenue_growth=25, total_cash=100000)
    q_e, _, _ = score(elite, "Technology")
    assert 7.0 <= q_e <= 8.0
    # failing unprofitable (weak growth, no runway) -> forced <= 5.0
    fail = ScreenerMetrics(**strong, net_income=-100, fcf=-100,
                           revenue_growth=5, total_cash=100)
    q_f, _, _ = score(fail, "Technology")
    assert q_f <= 5.0


def test_score_clamped_and_rounded():
    m = ScreenerMetrics(roic_ttm=0, roic_5y_avg=0, roic_wacc_spread=-10, rote=0,
                        revenue_cagr_3y=-5, eps_cagr_3y=-5, fcf_cagr_3y=-5,
                        fcf_margin=-5, op_margin=-5, gross_margin=5,
                        net_debt_ebitda=10, net_debt_fcf=20, ocf_capex=0.2,
                        shares_cagr_3y=10, sbc_pct_rev=30, earnings_quality=0.2,
                        insider_ownership=0, shareholder_yield=-2,
                        net_income=1, fcf=1, sector="Technology")
    q, _, _ = score(m, "Technology")
    assert q >= 1.0 and round(q, 1) == q
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_screener_scoring.py -k "score or cap or clamp or insufficient" -v`
Expected: FAIL (`cannot import name 'score'`)

- [ ] **Step 3: Write minimal implementation** (append to `scoring.py`)

```python
MIN_SCORED_SUBSCORES = 6


def _count_subscores(m: ScreenerMetrics, profile: str) -> int:
    p = PROFILES[profile]
    candidates = [
        m.revenue_cagr_3y, m.eps_cagr_3y, m.fcf_cagr_3y, m.fcf_margin,
        m.op_margin, m.op_margin_trajectory, m.gross_margin,
        m.roic_ttm, m.roic_5y_avg, m.roic_wacc_spread, m.rote,
        m.ocf_capex,
        m.shares_cagr_3y, m.sbc_pct_rev, m.earnings_quality,
        m.insider_ownership, m.shareholder_yield,
    ]
    n = sum(1 for c in candidates if c is not None)
    if p["P"] is not None:
        n += sum(1 for c in (m.net_debt_ebitda, m.net_debt_fcf) if c is not None)
    return n


def _rule_of_40(m: ScreenerMetrics) -> float | None:
    g = m.revenue_growth if m.revenue_growth is not None else m.revenue_cagr_3y
    margin = m.fcf_margin if m.fcf_margin is not None else m.op_margin
    if g is None or margin is None:
        return None
    return g + margin


def _runway_months(m: ScreenerMetrics) -> float | None:
    if m.fcf is None or m.fcf >= 0:
        return float("inf")
    if m.total_cash is None:
        return None
    monthly_burn = abs(m.fcf) / 12.0
    return m.total_cash / monthly_burn if monthly_burn > 0 else float("inf")


def score(m: ScreenerMetrics, sector: str | None):
    profile = apply_nudge(base_profile(sector), m)
    if _count_subscores(m, profile) < MIN_SCORED_SUBSCORES:
        return None, {}, profile

    sections = section_scores(m, profile)
    weights = dict(zip(("I", "II", "III", "IV"), PROFILES[profile]["w"]))

    # renormalize weights over sections that produced a score
    active = {k: weights[k] for k in sections if sections[k] is not None and weights[k] > 0}
    total_w = sum(active.values())
    if total_w <= 0:
        return None, sections, profile
    composite = sum(sections[k] * (w / total_w) for k, w in active.items())

    # Unprofitable Cap Rule
    if (m.net_income is not None and m.net_income < 0) or (m.fcf is not None and m.fcf < 0):
        composite = min(composite, 8.0)
        r40 = _rule_of_40(m)
        runway = _runway_months(m)
        elite = r40 is not None and r40 >= 40 and runway is not None and runway >= 24
        fails = (r40 is not None and r40 < 40) or (runway is not None and runway < 12)
        if elite:
            composite = max(min(composite, 8.0), 7.0)
        elif fails:
            composite = min(composite, 5.0)

    composite = max(1.0, min(10.0, composite))
    return round(composite, 1), sections, profile
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_screener_scoring.py -v`
Expected: PASS (all scoring tests)

- [ ] **Step 5: Commit**

```bash
git add backend/screener/scoring.py backend/tests/test_screener_scoring.py
git commit -m "feat(screener): composite score, cap rules, top-level score()"
```

---

## Phase 5 — Data assembly + engine

### Task 10: `fetch_screener_inputs`

**Files:**
- Create: `backend/screener/data.py`
- Test: `backend/tests/test_screener_engine.py` (bootstrap here)

**Interfaces:**
- Consumes: `services.yahoo.fetch_ticker_info`; `services.statements.{fetch_income_stmt, fetch_balance_sheet, fetch_cashflow_annual, fetch_treasury_10y, fetch_price_monthly}`; `screener.models.{ScreenerInputs, StatementSeries}`.
- Produces: `async fetch_screener_inputs(ticker: str) -> ScreenerInputs | None` — `None` only when `.info` fetch fails.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_screener_engine.py
import pytest
from unittest.mock import patch
from screener import data
from screener.models import ScreenerInputs


_INFO = {"symbol": "AAPL", "shortName": "Apple Inc.", "sector": "Technology",
         "beta": 1.1, "marketCap": 3_000_000_000_000, "totalDebt": 100.0,
         "totalCash": 60.0, "ebitda": 130.0, "operatingMargins": 0.32}


@pytest.mark.asyncio
async def test_fetch_inputs_assembles_all_sources():
    stmt = {"years": [2025, 2024, 2023, 2022], "rows": {"Total Revenue": [4, 3, 2, 1]}}
    with patch("screener.data.fetch_ticker_info", return_value=_INFO), \
         patch("screener.data.fetch_income_stmt", return_value=stmt), \
         patch("screener.data.fetch_balance_sheet", return_value=stmt), \
         patch("screener.data.fetch_cashflow_annual", return_value=stmt), \
         patch("screener.data.fetch_treasury_10y", return_value=0.045), \
         patch("screener.data.fetch_price_monthly", return_value=(1.0, 2.0)):
        inp = await data.fetch_screener_inputs("AAPL")
    assert isinstance(inp, ScreenerInputs)
    assert inp.info["symbol"] == "AAPL"
    assert inp.income.latest("Total Revenue") == 4
    assert inp.risk_free == 0.045
    assert inp.price_monthly == (1.0, 2.0)


@pytest.mark.asyncio
async def test_fetch_inputs_none_when_info_fails():
    with patch("screener.data.fetch_ticker_info", side_effect=ValueError("boom")):
        assert await data.fetch_screener_inputs("BADX") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_screener_engine.py -k fetch_inputs -v`
Expected: FAIL (`No module named 'screener.data'`)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/screener/data.py
from __future__ import annotations
import asyncio
from services.yahoo import fetch_ticker_info
from services.statements import (
    fetch_income_stmt, fetch_balance_sheet, fetch_cashflow_annual,
    fetch_treasury_10y, fetch_price_monthly,
)
from screener.models import ScreenerInputs, StatementSeries


async def fetch_screener_inputs(ticker: str) -> ScreenerInputs | None:
    t = ticker.upper()
    try:
        info = await fetch_ticker_info(t)
    except Exception:
        return None

    loop = asyncio.get_event_loop()

    def _blocking():
        return {
            "income": fetch_income_stmt(t),
            "balance": fetch_balance_sheet(t),
            "cashflow": fetch_cashflow_annual(t),
            "risk_free": fetch_treasury_10y(),
            "price": fetch_price_monthly(t),
        }

    d = await loop.run_in_executor(None, _blocking)
    return ScreenerInputs(
        ticker=t,
        info=info,
        income=StatementSeries.from_dict(d["income"]),
        balance=StatementSeries.from_dict(d["balance"]),
        cashflow=StatementSeries.from_dict(d["cashflow"]),
        price_monthly=d["price"],
        risk_free=d["risk_free"],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_screener_engine.py -k fetch_inputs -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/screener/data.py backend/tests/test_screener_engine.py
git commit -m "feat(screener): assemble ScreenerInputs from cached fetchers"
```

---

### Task 11: `engine.run`

**Files:**
- Create: `backend/screener/engine.py`
- Test: `backend/tests/test_screener_engine.py` (append)

**Interfaces:**
- Consumes: `screener.data.fetch_screener_inputs`, `screener.metrics.compute_metrics`, `screener.scoring.score`, `screener.models.ScreenerResult`.
- Produces: `async run(ticker: str) -> ScreenerResult`. Sets `last_evaluated` (UTC iso), `metrics` = `ScreenerMetrics.model_dump()`, `status="failed"` with a reason when inputs are missing or the score is `None`.

- [ ] **Step 1: Write the failing test**

```python
from screener import engine
from screener.models import ScreenerResult, ScreenerInputs, StatementSeries


def _full_inputs():
    def series(rows):
        return StatementSeries(years=[2025, 2024, 2023, 2022], rows=rows)
    income = series({
        "EBIT": [200, 180, 150, 120], "Tax Rate For Calcs": [0.21]*4,
        "Net Income": [160, 150, 130, 100], "Total Revenue": [1000, 900, 800, 700],
        "Interest Expense": [10]*4, "Gross Profit": [500, 450, 400, 350],
        "Operating Income": [220, 190, 160, 130], "Diluted EPS": [3.2, 3.0, 2.6, 2.0],
        "Diluted Average Shares": [50, 51, 52, 53]})
    balance = series({"Invested Capital": [1000, 950, 900, 850],
                      "Tangible Book Value": [800, 750, 700, 650],
                      "Net Debt": [-50, 0, 50, 100], "Ordinary Shares Number": [50, 51, 52, 53]})
    cash = series({"Free Cash Flow": [150, 130, 110, 90], "Operating Cash Flow": [200, 180, 160, 140],
                   "Capital Expenditure": [-50]*4, "Stock Based Compensation": [20]*4,
                   "Repurchase Of Capital Stock": [-30]*4, "Cash Dividends Paid": [-10]*4})
    info = {"symbol": "AAPL", "shortName": "Apple Inc.", "sector": "Technology",
            "beta": 1.0, "marketCap": 5000, "totalDebt": 100, "totalCash": 150,
            "ebitda": 250, "operatingMargins": 0.22, "grossMargins": 0.50,
            "heldPercentInsiders": 0.03, "trailingPE": 25, "forwardPE": 20,
            "trailingPegRatio": 1.5, "priceToSalesTrailing12Months": 5.0,
            "enterpriseValue": 4950, "revenueGrowth": 0.11, "totalRevenue": 1000,
            "freeCashflow": 150}
    return ScreenerInputs(ticker="AAPL", info=info, income=income, balance=balance,
                          cashflow=cash, price_monthly=tuple(), risk_free=0.045)


@pytest.mark.asyncio
async def test_run_completed():
    with patch("screener.engine.fetch_screener_inputs", return_value=_full_inputs()):
        r = await engine.run("AAPL")
    assert isinstance(r, ScreenerResult)
    assert r.status == "completed"
    assert r.company_name == "Apple Inc."
    assert r.quality_score is not None
    assert r.sector_profile == "TECH_GROWTH"
    assert r.last_evaluated is not None
    assert "roic_ttm" in r.metrics


@pytest.mark.asyncio
async def test_run_failed_when_no_inputs():
    with patch("screener.engine.fetch_screener_inputs", return_value=None):
        r = await engine.run("BADX")
    assert r.status == "failed"
    assert r.quality_score is None and r.errors
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_screener_engine.py -k "run_completed or run_failed" -v`
Expected: FAIL (`No module named 'screener.engine'`)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/screener/engine.py
from __future__ import annotations
from datetime import datetime, timezone
from screener.data import fetch_screener_inputs
from screener.metrics import compute_metrics
from screener.scoring import score
from screener.models import ScreenerResult


async def run(ticker: str) -> ScreenerResult:
    t = ticker.upper()
    inp = await fetch_screener_inputs(t)
    if inp is None:
        return ScreenerResult(ticker=t, status="failed",
                              errors=["yfinance data unavailable"])
    metrics = compute_metrics(inp)
    quality, sections, profile = score(metrics, metrics.sector)
    now = datetime.now(timezone.utc).isoformat()
    if quality is None:
        return ScreenerResult(
            ticker=t, company_name=inp.info.get("shortName") or inp.info.get("longName"),
            last_evaluated=now, sector=metrics.sector, sector_profile=profile,
            section_scores=sections, metrics=metrics.model_dump(),
            status="failed", errors=["insufficient data for a quality score"],
        )
    return ScreenerResult(
        ticker=t, company_name=inp.info.get("shortName") or inp.info.get("longName"),
        last_evaluated=now, quality_score=quality, sector=metrics.sector,
        sector_profile=profile, section_scores=sections, metrics=metrics.model_dump(),
        status="completed", errors=[],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_screener_engine.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/screener/engine.py backend/tests/test_screener_engine.py
git commit -m "feat(screener): engine.run orchestrates fetch -> metrics -> score"
```

---

## Phase 6 — Persistence

### Task 12: Screener sheet row serialization

**Files:**
- Create: `backend/services/screener_sheets.py`
- Test: `backend/tests/test_screener_sheets.py`

**Interfaces:**
- Produces:
  - `_SCREENER_HEADERS: list[str]` and `_METRIC_COLS: list[str]` (metric field order).
  - `_result_to_row(r: ScreenerResult) -> list` — length equals `len(_SCREENER_HEADERS)`.
  - `_row_to_result(row: list) -> ScreenerResult` — inverse for reads.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_screener_sheets.py
from screener.models import ScreenerResult
from services.screener_sheets import (
    _result_to_row, _row_to_result, _SCREENER_HEADERS, _METRIC_COLS,
)


def _res():
    return ScreenerResult(
        ticker="AAPL", company_name="Apple", last_evaluated="2026-07-08T00:00:00",
        quality_score=8.4, sector="Technology", sector_profile="TECH_GROWTH",
        section_scores={"I": 8.1, "II": 9.0, "III": 7.5, "IV": 8.0},
        metrics={k: 1.23 for k in _METRIC_COLS}, status="completed",
    )


def test_row_length_matches_headers():
    row = _result_to_row(_res())
    assert len(row) == len(_SCREENER_HEADERS)
    assert row[0] == "AAPL"
    assert row[3] == 8.4                     # Quality Score
    assert row[4] == "Technology"
    assert row[5] == "TECH_GROWTH"


def test_round_trip_preserves_core_fields():
    r = _row_to_result(_result_to_row(_res()))
    assert r.ticker == "AAPL"
    assert r.quality_score == 8.4
    assert r.sector_profile == "TECH_GROWTH"
    assert r.section_scores["II"] == 9.0
    assert r.metrics[_METRIC_COLS[0]] == 1.23
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_screener_sheets.py -v`
Expected: FAIL (`No module named 'services.screener_sheets'`)

- [ ] **Step 3: Write minimal implementation**

```python
# backend/services/screener_sheets.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_screener_sheets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/screener_sheets.py backend/tests/test_screener_sheets.py
git commit -m "feat(screener): Screener sheet row serialization + round-trip"
```

---

### Task 13: Screener tab upsert + read + Database-Q mirror

**Files:**
- Modify: `backend/services/screener_sheets.py`
- Test: `backend/tests/test_screener_sheets.py` (append — a header-cell test; the Google API calls are integration-only and not unit-tested)

**Interfaces:**
- Produces:
  - `async upsert_screener_result(r: ScreenerResult) -> None` — upserts the Screener tab row (find-by-ticker → append/overwrite) AND mirrors `quality_score` into Database column Q for the same ticker (ensuring the `Quality Score` header at `Database!Q1`).
  - `async read_screener() -> list[ScreenerResult]`.
  - `async read_screener_one(ticker: str) -> ScreenerResult | None`.
  - `_ensure_screener_sheet(svc, sheet_id) -> None`; `DATABASE_QSCORE_COL = "Q"`.

- [ ] **Step 1: Write the failing test**

```python
def test_database_qscore_col_constant():
    from services.screener_sheets import DATABASE_QSCORE_COL
    assert DATABASE_QSCORE_COL == "Q"


def test_headers_have_quality_score_first_metric_block():
    from services.screener_sheets import _SCREENER_HEADERS
    assert _SCREENER_HEADERS[3] == "Quality Score"
    assert "Section I" in _SCREENER_HEADERS and "Section Iv".title() not in _SCREENER_HEADERS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_screener_sheets.py -k "qscore or headers" -v`
Expected: FAIL (`cannot import name 'DATABASE_QSCORE_COL'`)

- [ ] **Step 3: Write minimal implementation** (append to `screener_sheets.py`)

```python
_SCREENER_TAB = "Screener"
DATABASE_QSCORE_COL = "Q"
_LAST_COL = chr(ord("A") + len(_SCREENER_HEADERS) - 1) if len(_SCREENER_HEADERS) <= 26 else None


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
    titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
    if _SCREENER_TAB not in titles:
        svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": _SCREENER_TAB}}}]},
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
        if "Unable to parse range" in str(e) or "400" in str(e):
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_screener_sheets.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/screener_sheets.py backend/tests/test_screener_sheets.py
git commit -m "feat(screener): Screener tab upsert/read + Database column-Q mirror"
```

---

### Task 14: `DatabaseRow` + Database tab reads Quality Score (column Q)

**Files:**
- Modify: `backend/models.py`, `backend/services/sheets.py`
- Test: `backend/tests/test_sheets_row.py` (append)

**Interfaces:**
- Produces: `DatabaseRow(TickerResult)` with `quality_score: float | None = None`.
- Consumes/updates: `services.sheets._read_database_sync` reads `Database!A:Q`, parses `row[16]` → `quality_score`, returns `DatabaseRow`. `read_database()` return type becomes `list[DatabaseRow]`.
- **Do NOT change** `_result_to_row` or `_DB_HEADERS` (stay 16 cols — FV write path and its test are untouched).

- [ ] **Step 1: Write the failing test** (append to `test_sheets_row.py`)

```python
from models import DatabaseRow
from services.sheets import _row_to_database_row


def test_database_row_parses_quality_score_col_q():
    # 16 FV cols (A:P) + quality score in col Q (index 16)
    row = ["AAPL", "Apple", "2026-07-08", "LARGE_CAP", "180.5", "190.0", "-5.0",
           "175.0", "", "", "", "", "", "", "", "", "8.4"]
    dr = _row_to_database_row(row)
    assert isinstance(dr, DatabaseRow)
    assert dr.ticker == "AAPL"
    assert dr.fair_value == 180.5
    assert dr.quality_score == 8.4


def test_database_row_blank_quality_score_is_none():
    row = ["MSFT", "Microsoft", "2026-07-08", "LARGE_CAP", "400", "410", "-2.4",
           "395"]  # short row, no Q
    dr = _row_to_database_row(row)
    assert dr.quality_score is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_sheets_row.py -k database_row -v`
Expected: FAIL (`cannot import name 'DatabaseRow'`)

- [ ] **Step 3: Write minimal implementation**

In `backend/models.py`, append:

```python
class DatabaseRow(TickerResult):
    quality_score: float | None = None
```

In `backend/services/sheets.py`: add `from models import TickerResult, DatabaseRow` (extend existing import), then add a pure converter and switch the read path. Insert this helper near `_read_database_sync`:

```python
def _row_to_database_row(row: list) -> DatabaseRow:
    row = list(row) + [""] * (17 - len(row))  # pad to include col Q (index 16)

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
    )
```

Then change `_read_database_sync` to read the wider range and delegate:

```python
def _read_database_sync() -> list[DatabaseRow]:
    svc = _get_service()
    sheet_id = _sheet_id()
    try:
        result = svc.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range="Database!A:Q",      # was A:P — now includes the Quality Score mirror
        ).execute()
    except Exception as e:
        if "Unable to parse range" in str(e) or "400" in str(e):
            _ensure_database_sheet(svc, sheet_id)
            return []
        raise
    rows = result.get("values", [])
    if len(rows) < 2:
        return []
    return [_row_to_database_row(row) for row in rows[1:]]
```

Update the `read_database` annotation to `-> list[DatabaseRow]`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_sheets_row.py -v`
Expected: PASS (existing 16-col test + 2 new)

- [ ] **Step 5: Commit**

```bash
git add backend/models.py backend/services/sheets.py backend/tests/test_sheets_row.py
git commit -m "feat(screener): DatabaseRow with mirrored Quality Score (Database col Q)"
```

---

## Phase 7 — Orchestration + API

### Task 15: Run both pipelines in parallel per ticker

**Files:**
- Modify: `backend/orchestrator/batch.py`
- Test: `backend/tests/test_batch_screener.py` (new)

**Interfaces:**
- Consumes: `valuation.engine.run`, `screener.engine.run`, `services.sheets.upsert_result`, `services.screener_sheets.upsert_screener_result`.
- Produces: `run_batch` yields `ticker_done` events whose `result` is the FV `TickerResult.model_dump()` with an added `"screener"` key holding the `ScreenerResult.model_dump()`. FV is upserted before the screener (so the Database row exists for the Q mirror). A failure in one pipeline never aborts the other.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_batch_screener.py
import pytest
from unittest.mock import patch, AsyncMock
import asyncio
from orchestrator import batch
from models import TickerResult
from screener.models import ScreenerResult


@pytest.mark.asyncio
async def test_run_batch_emits_combined_result():
    fv = TickerResult(ticker="AAPL", status="completed", fair_value=180.0,
                      company_name="Apple", current_price=190.0)
    sc = ScreenerResult(ticker="AAPL", status="completed", quality_score=8.4)
    with patch("orchestrator.batch.engine_run", new=AsyncMock(return_value=fv)), \
         patch("orchestrator.batch.screener_run", new=AsyncMock(return_value=sc)), \
         patch("orchestrator.batch.upsert_result", new=AsyncMock()) as up_fv, \
         patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()) as up_sc:
        events = [e async for e in batch.run_batch(["AAPL"], "job1", asyncio.Event())]
    done = [e for e in events if e["type"] == "ticker_done"]
    assert len(done) == 1
    assert done[0]["result"]["fair_value"] == 180.0
    assert done[0]["result"]["screener"]["quality_score"] == 8.4
    up_fv.assert_awaited_once()
    up_sc.assert_awaited_once()


@pytest.mark.asyncio
async def test_screener_failure_does_not_block_fv():
    fv = TickerResult(ticker="AAPL", status="completed", fair_value=180.0)
    with patch("orchestrator.batch.engine_run", new=AsyncMock(return_value=fv)), \
         patch("orchestrator.batch.screener_run", new=AsyncMock(side_effect=ValueError("boom"))), \
         patch("orchestrator.batch.upsert_result", new=AsyncMock()), \
         patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()):
        events = [e async for e in batch.run_batch(["AAPL"], "job1", asyncio.Event())]
    done = [e for e in events if e["type"] == "ticker_done"]
    assert done[0]["result"]["fair_value"] == 180.0
    assert done[0]["result"]["screener"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_batch_screener.py -v`
Expected: FAIL (`AttributeError: module 'orchestrator.batch' has no attribute 'engine_run'`)

- [ ] **Step 3: Write minimal implementation** — rewrite `backend/orchestrator/batch.py`:

```python
from __future__ import annotations
import asyncio, os
from collections.abc import AsyncGenerator
from valuation.engine import run as engine_run
from screener.engine import run as screener_run
from services.sheets import upsert_result
from services.screener_sheets import upsert_screener_result

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))


async def _run_one(ticker: str) -> dict:
    """Run both pipelines for one ticker; upsert FV first (so the Database row
    exists for the Q mirror), then the screener. Neither failure aborts the other."""
    fv_task = asyncio.create_task(engine_run(ticker))
    sc_task = asyncio.create_task(screener_run(ticker))
    fv_res, sc_res = await asyncio.gather(fv_task, sc_task, return_exceptions=True)

    errors = []
    fv_dump = None
    if isinstance(fv_res, Exception):
        errors.append(f"fair_value: {fv_res}")
    else:
        fv_dump = fv_res.model_dump()
        if fv_res.status != "failed":
            try:
                await upsert_result(fv_res)
            except Exception as e:
                errors.append(f"sheets_write: {e}")

    sc_dump = None
    if isinstance(sc_res, Exception):
        errors.append(f"screener: {sc_res}")
    else:
        sc_dump = sc_res.model_dump()
        if sc_res.status != "failed":
            try:
                await upsert_screener_result(sc_res)
            except Exception as e:
                errors.append(f"screener_write: {e}")

    if fv_dump is None:
        fv_dump = {"ticker": ticker.upper(), "status": "failed", "errors": errors}
    else:
        fv_dump.setdefault("errors", []).extend(errors)
    fv_dump["screener"] = sc_dump
    fv_failed = fv_dump.get("status") == "failed"
    return {"result": fv_dump, "fv_failed": fv_failed}


async def run_batch(tickers: list[str], job_id: str,
                    cancel_event: asyncio.Event) -> AsyncGenerator[dict, None]:
    total = len(tickers)
    completed = 0
    failed = 0
    yield {"type": "job_start", "job_id": job_id, "total": total}

    groups = [tickers[i:i + BATCH_SIZE] for i in range(0, len(tickers), BATCH_SIZE)]
    for group in groups:
        if cancel_event.is_set():
            break
        tasks = {t: asyncio.create_task(_run_one(t)) for t in group}
        for ticker, task in tasks.items():
            yield {"type": "ticker_start", "ticker": ticker}
            try:
                out = await task
                if out["fv_failed"] and out["result"].get("screener") is None:
                    failed += 1
                else:
                    completed += 1
                yield {"type": "ticker_done", "ticker": ticker, "result": out["result"]}
            except Exception as e:
                failed += 1
                yield {"type": "ticker_error", "ticker": ticker, "error": str(e)}

    status = "cancelled" if cancel_event.is_set() else "completed"
    yield {"type": "job_done", "job_id": job_id, "completed": completed,
           "failed": failed, "status": status}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_batch_screener.py tests/test_batch_smoke.py -v`
Expected: PASS (new tests pass; verify the existing smoke test still passes — if it patched `engine.run`, update it to patch `orchestrator.batch.engine_run` as part of this task)

- [ ] **Step 5: Commit**

```bash
git add backend/orchestrator/batch.py backend/tests/test_batch_screener.py
git commit -m "feat(screener): run FV + screener in parallel per ticker, combined event"
```

---

### Task 16: Recalculate-one and recalculate-all endpoints

**Files:**
- Modify: `backend/routers/analysis.py`
- Test: `backend/tests/test_analysis_endpoints.py` (new)

**Interfaces:**
- Consumes: `orchestrator.batch._run_one`, `services.sheets.read_database`, existing `_jobs`/`_run_job` machinery.
- Produces:
  - `POST /api/ticker/{ticker}/recalculate` → runs both pipelines once for `ticker`, upserts, returns the combined result dict (FV fields + `screener`).
  - `POST /api/recalculate-all` → reads all tickers from the Database tab, starts a batch job (both pipelines), returns `{"job_id", "total"}`. Streams via the existing `/api/stream/{job_id}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_analysis_endpoints.py
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_recalculate_one_returns_combined():
    combined = {"result": {"ticker": "AAPL", "status": "completed", "fair_value": 180.0,
                           "screener": {"quality_score": 8.4}}, "fv_failed": False}
    with patch("routers.analysis._run_one", new=AsyncMock(return_value=combined)):
        resp = client.post("/api/ticker/AAPL/recalculate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["fair_value"] == 180.0
    assert body["screener"]["quality_score"] == 8.4


def test_recalculate_all_starts_job():
    from models import DatabaseRow
    rows = [DatabaseRow(ticker="AAPL"), DatabaseRow(ticker="MSFT")]
    with patch("routers.analysis.read_database", new=AsyncMock(return_value=rows)):
        resp = client.post("/api/recalculate-all")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2 and "job_id" in body


def test_recalculate_all_empty_database():
    with patch("routers.analysis.read_database", new=AsyncMock(return_value=[])):
        resp = client.post("/api/recalculate-all")
    assert resp.json().get("error")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_analysis_endpoints.py -v`
Expected: FAIL (404 — routes not defined)

- [ ] **Step 3: Write minimal implementation** — add to `backend/routers/analysis.py`:

At the top, extend imports:

```python
from orchestrator.batch import run_batch, _run_one
from services.sheets import read_tickers, read_database
```

Then add the endpoints (after `start_analysis`):

```python
@router.post("/ticker/{ticker}/recalculate")
async def recalculate_one(ticker: str):
    out = await _run_one(ticker.strip().upper())
    return out["result"]


@router.post("/recalculate-all")
async def recalculate_all():
    rows = await read_database()
    tickers = [r.ticker.strip().upper() for r in rows if r.ticker and r.ticker.strip()]
    if not tickers:
        return {"error": "No tickers in the database to recalculate"}
    job_id = str(uuid.uuid4())
    cancel_event = asyncio.Event()
    _cancel_events[job_id] = cancel_event
    _jobs[job_id] = {"status": "running", "total": len(tickers),
                     "completed": 0, "failed": 0, "results": [], "invalid": []}
    asyncio.create_task(_run_job(job_id, tickers, cancel_event))
    return {"job_id": job_id, "total": len(tickers)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_analysis_endpoints.py -v`
Expected: PASS

Note: if `fastapi.testclient` requires `httpx`, it is already a FastAPI test dependency; if missing, `pip install httpx` before running.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/analysis.py backend/tests/test_analysis_endpoints.py
git commit -m "feat(screener): recalculate-one and recalculate-all endpoints"
```

---

### Task 17: Database router returns rows + screener detail endpoint

**Files:**
- Modify: `backend/routers/database.py`
- Test: `backend/tests/test_database_router.py` (new)

**Interfaces:**
- Consumes: `services.sheets.read_database` (now `list[DatabaseRow]`), `services.screener_sheets.read_screener_one`.
- Produces:
  - `GET /api/database` → `{"results": [DatabaseRow.model_dump()...]}` (now includes `quality_score`).
  - `GET /api/screener/{ticker}` → full `ScreenerResult.model_dump()` or `{"error": ...}`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_database_router.py
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app
from models import DatabaseRow
from screener.models import ScreenerResult

client = TestClient(app)


def test_database_includes_quality_score():
    with patch("routers.database.read_database",
               new=AsyncMock(return_value=[DatabaseRow(ticker="AAPL", quality_score=8.4)])):
        resp = client.get("/api/database")
    assert resp.json()["results"][0]["quality_score"] == 8.4


def test_screener_detail_endpoint():
    r = ScreenerResult(ticker="AAPL", quality_score=8.4, sector_profile="TECH_GROWTH")
    with patch("routers.database.read_screener_one", new=AsyncMock(return_value=r)):
        resp = client.get("/api/screener/AAPL")
    assert resp.json()["sector_profile"] == "TECH_GROWTH"


def test_screener_detail_not_found():
    with patch("routers.database.read_screener_one", new=AsyncMock(return_value=None)):
        resp = client.get("/api/screener/ZZZZ")
    assert resp.json().get("error")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_database_router.py -v`
Expected: FAIL (404 for `/api/screener/...`)

- [ ] **Step 3: Write minimal implementation** — rewrite `backend/routers/database.py`:

```python
from fastapi import APIRouter
from services.sheets import read_database
from services.screener_sheets import read_screener_one

router = APIRouter()


@router.get("/database")
async def get_database():
    try:
        results = await read_database()
        return {"results": [r.model_dump() for r in results]}
    except Exception as e:
        return {"error": str(e), "results": []}


@router.get("/screener/{ticker}")
async def get_screener(ticker: str):
    try:
        r = await read_screener_one(ticker)
        if r is None:
            return {"error": f"No screener record for {ticker.upper()}"}
        return r.model_dump()
    except Exception as e:
        return {"error": str(e)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_database_router.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/routers/database.py backend/tests/test_database_router.py
git commit -m "feat(screener): database router returns quality score + screener detail endpoint"
```

---

### Task 18: Full backend regression

**Files:** none (verification task)

- [ ] **Step 1: Run the whole backend suite**

Run: `cd backend && python -m pytest -q`
Expected: PASS — all existing Fair Value tests plus every new screener test are green. If any existing test broke (e.g. `test_batch_smoke.py` patched `engine.run`), fix the patch target to the new `orchestrator.batch.engine_run`/`screener_run` names and re-run.

- [ ] **Step 2: Commit any test-target fixes**

```bash
git add backend/tests
git commit -m "test(screener): align existing tests with new orchestrator symbols"
```

---

## Phase 8 — Frontend

> No JS test harness exists. Each frontend task verifies with `cd frontend && npm run build` (runs `tsc -b` typecheck + `vite build`) and a described manual check. Backend must be running (`./start.sh`) for manual checks.

### Task 19: Screener types + color helpers

**Files:**
- Modify: `frontend/src/types.ts`

**Interfaces:**
- Produces: `ScreenerMetrics`, `ScreenerResult` interfaces; `screener?: ScreenerResult | null` and `quality_score?: number | null` on `TickerResult`; `qualityScoreColor(score)`, `qualityScoreBadgeClass(score)`.

- [ ] **Step 1: Add the types + helpers** — append to `frontend/src/types.ts`:

```typescript
export interface ScreenerMetrics {
  revenue_cagr_3y: number | null
  eps_cagr_3y: number | null
  fcf_cagr_3y: number | null
  fcf_margin: number | null
  op_margin: number | null
  op_margin_trajectory: number | null
  gross_margin: number | null
  roic_ttm: number | null
  roic_5y_avg: number | null
  wacc: number | null
  roic_wacc_spread: number | null
  rote: number | null
  net_debt_ebitda: number | null
  net_debt_fcf: number | null
  ocf_capex: number | null
  tangible_bv_per_share: number | null
  shares_cagr_3y: number | null
  sbc_pct_rev: number | null
  earnings_quality: number | null
  insider_ownership: number | null
  shareholder_yield: number | null
  trailing_pe: number | null
  forward_pe: number | null
  peg: number | null
  price_fcf: number | null
  price_sales: number | null
  fcf_yield: number | null
  owner_earnings_yield: number | null
  price_cagr_3y: number | null
  price_cagr_5y: number | null
  [key: string]: number | null | string | undefined
}

export interface ScreenerResult {
  ticker: string
  company_name: string | null
  last_evaluated: string | null
  quality_score: number | null
  sector: string | null
  sector_profile: string | null
  section_scores: Record<string, number | null>
  metrics: Partial<ScreenerMetrics>
  status: 'completed' | 'failed'
  errors: string[]
}

/** 1-10 quality score -> text color band. */
export function qualityScoreColor(score: number | null | undefined): string {
  if (score == null) return 'text-slate-400'
  if (score >= 8) return 'text-green-400'
  if (score >= 6.5) return 'text-blue-400'
  if (score >= 5) return 'text-yellow-400'
  return 'text-red-400'
}

export function qualityScoreBadgeClass(score: number | null | undefined): string {
  if (score == null) return 'bg-slate-800 text-slate-300'
  if (score >= 8) return 'bg-green-900/40 text-green-400 border border-green-700'
  if (score >= 6.5) return 'bg-blue-900/40 text-blue-400 border border-blue-700'
  if (score >= 5) return 'bg-yellow-900/40 text-yellow-400 border border-yellow-700'
  return 'bg-red-900/40 text-red-400 border border-red-700'
}
```

Then extend the existing `TickerResult` interface with two optional fields (add inside the interface body):

```typescript
  quality_score?: number | null
  screener?: ScreenerResult | null
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npm run build`
Expected: build succeeds, no TS errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types.ts
git commit -m "feat(screener): frontend screener types + quality-score color helpers"
```

---

### Task 20: ScreenerPanel component

**Files:**
- Create: `frontend/src/components/ScreenerPanel.tsx`

**Interfaces:**
- Consumes: `ScreenerResult`, `qualityScoreColor`, `qualityScoreBadgeClass` from `../types`.
- Produces: `default export function ScreenerPanel({ result }: { result: ScreenerResult })`.

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/ScreenerPanel.tsx
import type { ScreenerResult } from '../types'
import { qualityScoreColor, qualityScoreBadgeClass } from '../types'

const SECTIONS: [string, string][] = [
  ['I', 'Growth & Trajectory'],
  ['II', 'Capital Efficiency'],
  ['III', 'Balance Sheet'],
  ['IV', 'Dilution & Quality'],
]

// [field, label, format] — grouped by section for display
const METRIC_GROUPS: { title: string; rows: [string, string, 'pct' | 'ratio' | 'money'][] }[] = [
  { title: 'I · Growth & Trajectory', rows: [
    ['revenue_cagr_3y', 'Revenue CAGR 3Y', 'pct'],
    ['eps_cagr_3y', 'EPS CAGR 3Y', 'pct'],
    ['fcf_cagr_3y', 'FCF CAGR 3Y', 'pct'],
    ['fcf_margin', 'FCF Margin', 'pct'],
    ['op_margin', 'Operating Margin', 'pct'],
    ['op_margin_trajectory', 'Op Margin Δ (pp)', 'pct'],
    ['gross_margin', 'Gross Margin', 'pct'],
  ]},
  { title: 'II · Capital Efficiency', rows: [
    ['roic_ttm', 'ROIC (TTM)', 'pct'],
    ['roic_5y_avg', 'ROIC 5Y avg', 'pct'],
    ['wacc', 'WACC', 'pct'],
    ['roic_wacc_spread', 'ROIC − WACC (pp)', 'pct'],
    ['rote', 'ROTE', 'pct'],
  ]},
  { title: 'III · Balance Sheet', rows: [
    ['net_debt_ebitda', 'Net Debt / EBITDA', 'ratio'],
    ['net_debt_fcf', 'Net Debt / FCF', 'ratio'],
    ['ocf_capex', 'OCF / CapEx', 'ratio'],
    ['tangible_bv_per_share', 'Tangible BV / Share', 'money'],
  ]},
  { title: 'IV · Dilution & Quality', rows: [
    ['shares_cagr_3y', 'Shares CAGR 3Y', 'pct'],
    ['sbc_pct_rev', 'SBC % of Revenue', 'pct'],
    ['earnings_quality', 'Earnings Quality (OCF/NI)', 'ratio'],
    ['insider_ownership', 'Insider Ownership', 'pct'],
    ['shareholder_yield', 'Shareholder Yield', 'pct'],
  ]},
  { title: 'V · Valuation (reference — not scored)', rows: [
    ['trailing_pe', 'Trailing P/E', 'ratio'],
    ['forward_pe', 'Forward P/E', 'ratio'],
    ['peg', 'PEG', 'ratio'],
    ['price_fcf', 'Price / FCF', 'ratio'],
    ['price_sales', 'Price / Sales', 'ratio'],
    ['fcf_yield', 'FCF Yield (FCF/EV)', 'pct'],
    ['owner_earnings_yield', 'Owner Earnings Yield vs 10Y', 'pct'],
    ['price_cagr_3y', 'Price CAGR 3Y', 'pct'],
    ['price_cagr_5y', 'Price CAGR 5Y', 'pct'],
  ]},
]

function fmt(v: number | null | undefined, kind: 'pct' | 'ratio' | 'money'): string {
  if (v == null) return '—'
  if (kind === 'pct') return `${v.toFixed(1)}%`
  if (kind === 'money') return `$${v.toFixed(2)}`
  return v.toFixed(2)
}

export default function ScreenerPanel({ result }: { result: ScreenerResult }) {
  const m = result.metrics || {}
  const sections = result.section_scores || {}

  return (
    <div className="space-y-6">
      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-6 flex items-center justify-between">
        <div>
          <div className="text-xs text-slate-500 uppercase tracking-wide">Business Quality Score</div>
          <div className={`text-4xl font-mono font-bold mt-1 ${qualityScoreColor(result.quality_score)}`}>
            {result.quality_score != null ? result.quality_score.toFixed(1) : '—'}
            <span className="text-lg text-slate-600">/10</span>
          </div>
          <div className="text-xs text-slate-600 mt-2">
            {result.sector || '—'}{result.sector_profile ? ` · ${result.sector_profile}` : ''}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {SECTIONS.map(([key, label]) => (
            <div key={key} className="text-right">
              <span className="text-[11px] text-slate-500">{label}</span>
              <span className={`ml-2 font-mono text-sm px-2 py-0.5 rounded ${qualityScoreBadgeClass(sections[key])}`}>
                {sections[key] != null ? sections[key]!.toFixed(1) : '—'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {METRIC_GROUPS.map(group => (
        <div key={group.title} className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-4">
          <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">{group.title}</div>
          <table className="w-full text-sm">
            <tbody>
              {group.rows.map(([field, label, kind]) => (
                <tr key={field} className="border-b border-[#1e1e2a] last:border-0">
                  <td className="py-1.5 text-slate-400">{label}</td>
                  <td className="py-1.5 text-right font-mono text-slate-300">
                    {fmt(m[field] as number | null | undefined, kind)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      {result.errors && result.errors.length > 0 && (
        <div className="bg-amber-900/10 border border-amber-900/50 rounded-lg p-4">
          <p className="text-xs text-amber-400 font-semibold mb-2">Screener notes</p>
          <ul className="text-xs text-amber-300 space-y-1">
            {result.errors.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ScreenerPanel.tsx
git commit -m "feat(screener): ScreenerPanel — score, section scores, metric tables"
```

---

### Task 21: Tabbed Fair Value | Screener detail view

**Files:**
- Modify: `frontend/src/pages/TickerDetail.tsx`

**Interfaces:**
- Consumes: `ScreenerPanel`; `result.screener` (from a live job) or a fetched `ScreenerResult` (from the Database, via `GET /api/screener/{ticker}`).

- [ ] **Step 1: Add a tab switcher and lazy screener fetch** — replace the `FairValuePanel` render block and imports in `TickerDetail.tsx`:

Add imports at top:

```tsx
import { useEffect, useState } from 'react'
import type { TickerResult, ScreenerResult } from '../types'
import ScreenerPanel from '../components/ScreenerPanel'

const API = 'http://localhost:8000'
```

Inside the component, after `const result` is resolved (and before the early return is fine — hooks must be unconditional, so place these hooks at the top of the component body):

```tsx
  const [tab, setTab] = useState<'fv' | 'screener'>('fv')
  const [screener, setScreener] = useState<ScreenerResult | null>(result?.screener ?? null)

  useEffect(() => {
    if (tab === 'screener' && !screener && result?.ticker) {
      fetch(`${API}/api/screener/${result.ticker}`)
        .then(r => r.json())
        .then(d => { if (!d.error) setScreener(d as ScreenerResult) })
        .catch(() => {})
    }
  }, [tab, screener, result])
```

Replace `<FairValuePanel result={result} />` with:

```tsx
      <div className="flex gap-4 border-b border-[#1e1e2a] mb-4">
        {(['fv', 'screener'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`pb-2 text-sm ${tab === t ? 'text-blue-400 border-b-2 border-blue-400' : 'text-slate-500 hover:text-slate-300'}`}
          >
            {t === 'fv' ? 'Fair Value' : 'Screener'}
          </button>
        ))}
      </div>

      {tab === 'fv' ? (
        <FairValuePanel result={result} />
      ) : screener ? (
        <ScreenerPanel result={screener} />
      ) : (
        <div className="text-slate-500 text-sm py-8 text-center">
          No screener data for this ticker yet.
        </div>
      )}
```

Keep the existing `import FairValuePanel from '../components/FairValuePanel'`. Ensure the `const result` line uses the type already imported. Move the two hooks above the `if (!result)` early return so hooks always run.

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Manual check**

With backend running and at least one screened ticker in the DB: open a ticker detail, click **Screener** — the score, four section badges, and metric tables render; **Fair Value** tab still shows the FV breakdown.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/TickerDetail.tsx
git commit -m "feat(screener): tabbed Fair Value | Screener detail view"
```

---

### Task 22: Database grid — Quality Score column + recalc buttons

**Files:**
- Modify: `frontend/src/pages/Database.tsx`

**Interfaces:**
- Consumes: `qualityScoreColor`; `POST /api/ticker/{ticker}/recalculate`; `POST /api/recalculate-all`.

- [ ] **Step 1: Add column + buttons** — update `Database.tsx`:

Add to imports:

```tsx
import { fvGapColor, qualityScoreColor } from '../types'
```

Add recalc state + handlers inside the component (after `load`):

```tsx
  const [busy, setBusy] = useState<string | null>(null)
  const [recalcAll, setRecalcAll] = useState(false)

  const recalcOne = async (ticker: string) => {
    setBusy(ticker)
    try {
      await fetch(`${API}/api/ticker/${ticker}/recalculate`, { method: 'POST' })
      await load()
    } finally {
      setBusy(null)
    }
  }

  const recalcEverything = async () => {
    setRecalcAll(true)
    try {
      const res = await fetch(`${API}/api/recalculate-all`, { method: 'POST' })
      const data = await res.json()
      if (data.job_id) window.location.href = `/progress/${data.job_id}`
    } finally {
      setRecalcAll(false)
    }
  }
```

Add the top button next to Refresh:

```tsx
        <button
          onClick={recalcEverything}
          disabled={recalcAll}
          className="text-sm text-slate-300 hover:text-white border border-[#1e1e2a] px-3 py-1.5 rounded disabled:opacity-50"
        >
          {recalcAll ? 'Starting…' : 'Recalculate All'}
        </button>
```

Add a header cell for Quality Score (after the Stock Type `<th>`):

```tsx
                <th className="text-right py-2 px-2">Quality</th>
```

Add a `<td>` in each row (after the Stock Type cell) and an actions cell at the row end:

```tsx
                  <td className={`py-2 px-2 text-right font-mono text-xs ${qualityScoreColor(r.quality_score)}`}>
                    {r.quality_score != null ? r.quality_score.toFixed(1) : '—'}
                  </td>
```

At the end of each `<tr>`, add a recalc button cell:

```tsx
                  <td className="py-2 px-2 text-right">
                    <button
                      onClick={() => recalcOne(r.ticker)}
                      disabled={busy === r.ticker}
                      title="Recalculate Fair Value + Screener"
                      className="text-xs text-slate-500 hover:text-blue-400 disabled:opacity-50"
                    >
                      {busy === r.ticker ? '…' : '↻'}
                    </button>
                  </td>
```

Also add an empty `<th></th>` at the end of the header row to align the actions column. Ensure `TickerResult` used by this page includes `quality_score` (added in Task 19).

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 3: Manual check**

With backend running: the Database grid shows a **Quality** column; clicking a row's **↻** re-runs both pipelines and refreshes that data; **Recalculate All** starts a job and navigates to the progress page.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Database.tsx
git commit -m "feat(screener): Database grid quality column + per-row and recalc-all buttons"
```

---

## Phase 9 — End-to-end verification

### Task 23: Live smoke test of both pipelines

**Files:** none (verification)

- [ ] **Step 1: Backend suite green**

Run: `cd backend && python -m pytest -q`
Expected: all pass.

- [ ] **Step 2: Frontend builds**

Run: `cd frontend && npm run build`
Expected: succeeds.

- [ ] **Step 3: Live run** (requires Google Sheets creds + network)

Start the app (`./start.sh`), analyse a small basket (e.g. `AAPL, MSFT, KO, NEE, JPM, O`) covering Technology, Consumer Defensive, Utilities, Financials, and a REIT. Verify:
- Each ticker gets both a Fair Value and a Quality Score.
- The "Screener" tab is created in the Sheet with full metrics; Database column Q shows the score.
- JPM (Financials) shows `sector_profile = FINANCIALS` (Section III blank/None); O (Real Estate) shows `REIT`.
- The Database grid shows the Quality column; per-row ↻ and Recalculate All work.

- [ ] **Step 4: Commit any fixes**, then the plan is complete.

```bash
git add -A && git commit -m "chore(screener): end-to-end verification fixes"
```

---

## Self-Review

Coverage vs spec:
- §2 caveats → 5Y-as-available (`series_cagr`, Task 3), assumed ERP (Task 4), None-degradation (throughout), financials profile (Task 7/8).
- §4 metrics → Tasks 4–5. §5 rubric → Tasks 6–9 (bands, sector-relative leverage, nudge, dual-check, cap rules, clamp, insufficient-data).
- §6 persistence → Tasks 12–14 (Screener tab, Q mirror, DatabaseRow). §7 API → Tasks 15–17. §8 frontend → Tasks 19–22.
- Isolation constraint honored: `screener/` never imports `valuation/`; FV `_result_to_row`/`_DB_HEADERS` untouched; screener owns column Q.

Type consistency: `score()` returns `(quality_score, section_scores, applied_profile)` consumed by `engine.run` (Task 9 ↔ 11). `_run_one` combined dict shape (`{...fv, "screener": {...}}`) consumed by analysis endpoints (Task 15 ↔ 16) and frontend `result.screener` (Task 21). `DatabaseRow.quality_score` produced in Task 14, consumed in Tasks 17/19/22.
