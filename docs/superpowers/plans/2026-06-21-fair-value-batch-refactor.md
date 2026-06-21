# Fair Value Batch Calculator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert Agent Stock from an AI-agent stock-scoring app into a free, unattended, parallel fair-value batch calculator that takes a ticker list and outputs a composite fair value per ticker.

**Architecture:** Port `fairvalue3`'s 8-type classifier + 10 valuation models into Agent Stock's backend as a pure `valuation/` package; drive it from the existing batch + Google Sheets + SSE-progress pipeline. Remove all Anthropic/AI agents and the Anthropic Batch API path. Keep Agent Stock's per-stock capped growth scenarios and multiple-capping.

**Tech Stack:** Python 3 / FastAPI / pytest (backend), yfinance (free data), Google Sheets API (free I/O), React 19 / TypeScript / Vite / Tailwind (frontend).

## Global Constraints

These apply to every task. Values are copied verbatim from the spec.

- **No paid/AI dependencies.** `anthropic` is removed from `requirements.txt`. The only external calls are yfinance (free) and Google Sheets (free within quota). No `ANTHROPIC_API_KEY` is read anywhere.
- **Valuation constants:** discount rate `0.10`, terminal growth `0.03`, horizon `10` years, margin of safety `0.90` (applied **once** per model, internally), cost of equity `0.10`.
- **Growth scenarios (per stock, capped):** `base = clamp(earnings_growth or revenue_growth or 0.07, 0.02, 0.20)`; `optimistic = min(base + 0.05, 0.25)`; `realistic = base`; `pessimistic = max(base - 0.04, 0.02)`.
- **EV multiple caps:** EV/EBITDA multiple ≤ `20.0`, EV/Sales multiple ≤ `8.0` (spot multiples).
- **EV pick rule (tunable):** EBITDA margin floor = `0.08`. Arbitrates **only** when the stock type weights both `ev_ebitda` and `ev_sales` (LARGE_CAP, GROWTH).
- **Capex→CFO rule (tunable):** capex/CFO gate = `0.50`. `capex = operating_cashflow − fcf`. Applies only when `operating_cashflow > 0` and both CFO and FCF present.
- **Stock types & weights:** 8 types, per-type model weights copied verbatim from `fairvalue3/backend/services/classifier.py`.
- **FCFE model:** ported for completeness but **dormant** — no stock type weights it, and it is omitted from the Sheets schema.
- **Test data:** backend valuation/classifier/engine tests use static Python fixtures — no live yfinance calls.
- **Frontend verification:** `cd frontend && npm run build` (runs `tsc -b` + `vite build`). Vitest is not configured in this repo; type-check + build is the frontend gate (see Task 8 note).

## File Structure

**Backend — new `valuation/` package (pure, no IO except `engine.run`):**
- `backend/valuation/classifier.py` — `classify(fin)` → stock type + per-model weights (ported from fairvalue3).
- `backend/valuation/models.py` — the 10 model functions + `composite()` + constants. Pure functions over a `fin` dict.
- `backend/valuation/engine.py` — `evaluate(fin)` (pure orchestration → result dict) + `run(ticker)` (async IO wrapper → `TickerResult`).

**Backend — modified:**
- `backend/services/yahoo.py` — extend `extract_financials` with `operating_cashflow`, `ev_ebitda`, `ev_sales`, and `cost_of_equity=0.10`.
- `backend/models.py` — reshape `TickerResult`; delete `AgentResult`, `FairValueResult`, `BatchJobFile`; drop `mode` from `AnalyseRequest`.
- `backend/services/sheets.py` — new 16-column Database schema.
- `backend/orchestrator/batch.py` — call `engine.run(ticker)`; drop agent/calculator fan-out.
- `backend/routers/analysis.py` — drop Batch API branch; always stream.
- `backend/main.py` — drop `jobs_router`.

**Backend — deleted:**
- `backend/agents/` (8 files), `backend/prompts/` (6 files)
- `backend/services/batch_service.py`, `backend/routers/jobs.py`, `backend/services/normalizer.py`
- `backend/orchestrator/aggregator.py`
- `backend/valuation/calculator_1.py`, `calculator_2.py`, `gemini_fv.py`
- `backend/tests/test_base_agent_parse.py`, `test_batch_service.py`, `test_normalizer_prescreener.py`

**Frontend — modified:** `types.ts`, `App.tsx`, `pages/Home.tsx`, `pages/Progress.tsx`, `pages/Results.tsx`, `pages/Database.tsx`, `pages/TickerDetail.tsx`, `components/FairValuePanel.tsx`.

**Frontend — deleted:** `components/ScoreBadge.tsx`, `components/AgentCard.tsx`, `pages/JobStatus.tsx`.

---

## Task 1: Extend `extract_financials` with the new fields

**Files:**
- Modify: `backend/services/yahoo.py:45-78` (`extract_financials`)
- Test: `backend/tests/test_yahoo_block.py`

**Interfaces:**
- Produces: `extract_financials(info: dict) -> dict` now additionally returns keys `operating_cashflow` (from `operatingCashflow`), `ev_ebitda` (spot `enterpriseToEbitda`), `ev_sales` (spot `enterpriseToRevenue`), and `cost_of_equity = 0.10`. All other existing keys are unchanged. These keys are consumed by `valuation/models.py` and `valuation/engine.py` (Tasks 3–4).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_yahoo_block.py`:

```python
from services.yahoo import extract_financials


def test_extract_financials_adds_valuation_fields():
    info = {
        "symbol": "AAPL",
        "shortName": "Apple Inc.",
        "currentPrice": 189.45,
        "operatingCashflow": 120_000_000_000,
        "freeCashflow": 99_000_000_000,
        "enterpriseToEbitda": 24.3,
        "enterpriseToRevenue": 8.1,
        "ebitda": 130_000_000_000,
        "totalRevenue": 391_000_000_000,
    }
    fin = extract_financials(info)
    assert fin["operating_cashflow"] == 120_000_000_000
    assert fin["ev_ebitda"] == 24.3
    assert fin["ev_sales"] == 8.1
    assert fin["cost_of_equity"] == 0.10
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_yahoo_block.py::test_extract_financials_adds_valuation_fields -v`
Expected: FAIL with `KeyError: 'operating_cashflow'`.

- [ ] **Step 3: Add the fields to `extract_financials`**

In `backend/services/yahoo.py`, inside the `return {...}` of `extract_financials`, replace the final two lines:

```python
        "interest_expense": info.get("interestExpense"),
        "effective_tax_rate": info.get("effectiveTaxRate"),
        "cost_of_equity": None,
    }
```

with:

```python
        "interest_expense": info.get("interestExpense"),
        "effective_tax_rate": info.get("effectiveTaxRate"),
        "operating_cashflow": info.get("operatingCashflow"),
        "ev_ebitda": info.get("enterpriseToEbitda"),
        "ev_sales": info.get("enterpriseToRevenue"),
        "cost_of_equity": 0.10,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_yahoo_block.py -v`
Expected: PASS (all tests, including the existing three).

- [ ] **Step 5: Commit**

```bash
git add backend/services/yahoo.py backend/tests/test_yahoo_block.py
git commit -m "feat: add operating_cashflow + spot EV multiples to extract_financials"
```

---

## Task 2: Port the stock-type classifier

**Files:**
- Create: `backend/valuation/classifier.py`
- Test: `backend/tests/test_classifier.py`

**Interfaces:**
- Consumes: a `fin` dict (from `extract_financials`, Task 1) — reads `sector`, `industry`, `long_business_summary`, `market_cap`, `ebitda_ttm`, `eps_ttm`, `revenue_growth`, `dividend_yield`, `payout_ratio`, `trailing_pe`.
- Produces: `classify(fin: dict) -> {"stock_type": str, "method_weights": dict[str, {"enabled": bool, "weight": float}]}` and module constant `_TYPE_WEIGHTS`. Consumed by `valuation/engine.py` (Task 4).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_classifier.py`:

```python
from valuation.classifier import classify


def test_financial_sector_is_financial():
    fin = {"sector": "Financial Services"}
    assert classify(fin)["stock_type"] == "FINANCIAL"


def test_real_estate_is_asset_heavy():
    fin = {"sector": "Real Estate"}
    assert classify(fin)["stock_type"] == "ASSET_HEAVY"


def test_small_negative_ebitda_is_asset_heavy():
    fin = {"sector": "Technology", "ebitda_ttm": -5_000_000, "market_cap": 1_000_000_000}
    assert classify(fin)["stock_type"] == "ASSET_HEAVY"


def test_conglomerate_industry():
    fin = {"sector": "Industrials", "industry": "Conglomerates"}
    assert classify(fin)["stock_type"] == "CONGLOMERATE"


def test_conglomerate_keyword_in_summary():
    fin = {"sector": "Industrials", "long_business_summary": "A diversified holding company."}
    assert classify(fin)["stock_type"] == "CONGLOMERATE"


def test_early_growth():
    fin = {"sector": "Technology", "revenue_growth": 0.35, "eps_ttm": -1.2, "ebitda_ttm": 10}
    assert classify(fin)["stock_type"] == "EARLY_GROWTH"


def test_growth():
    fin = {"sector": "Technology", "revenue_growth": 0.18, "eps_ttm": 3.0, "dividend_yield": 0.0}
    assert classify(fin)["stock_type"] == "GROWTH"


def test_dividend():
    fin = {"sector": "Consumer Defensive", "dividend_yield": 0.04, "payout_ratio": 0.6}
    assert classify(fin)["stock_type"] == "DIVIDEND"


def test_cyclical_sector():
    fin = {"sector": "Energy"}
    assert classify(fin)["stock_type"] == "CYCLICAL"


def test_large_cap_default():
    fin = {"sector": "Technology", "revenue_growth": 0.05, "eps_ttm": 5.0, "dividend_yield": 0.005}
    assert classify(fin)["stock_type"] == "LARGE_CAP"


def test_method_weights_shape():
    res = classify({"sector": "Financial Services"})
    assert res["method_weights"]["rim"] == {"enabled": True, "weight": 0.45}
    assert res["method_weights"]["dcf"] == {"enabled": False, "weight": 0.0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_classifier.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'valuation.classifier'`.

- [ ] **Step 3: Create the classifier (ported verbatim from fairvalue3)**

Create `backend/valuation/classifier.py`:

```python
from __future__ import annotations

CONGLOMERATE_KEYWORDS = [
    "portfolio", "capital allocation", "subsidiaries", "spin-off", "spinoff",
    "breakup", "divestiture", "holding company", "conglomerate",
]

CYCLICAL_SECTORS = {"Energy", "Basic Materials"}

# Default method weights per stock type. Keys match the MethodId set:
# dcf, fcfe, ev_ebitda, pe, ev_sales, ddm, pb, rim, sotp, nav.
_TYPE_WEIGHTS: dict[str, dict[str, float]] = {
    "LARGE_CAP":    {"dcf": 0.45, "fcfe": 0.00, "ev_ebitda": 0.25, "pe": 0.15, "ev_sales": 0.10, "ddm": 0.00, "pb": 0.00, "rim": 0.00, "sotp": 0.05, "nav": 0.00},
    "DIVIDEND":     {"dcf": 0.25, "fcfe": 0.00, "ev_ebitda": 0.00, "pe": 0.25, "ev_sales": 0.00, "ddm": 0.40, "pb": 0.10, "rim": 0.00, "sotp": 0.00, "nav": 0.00},
    "GROWTH":       {"dcf": 0.40, "fcfe": 0.00, "ev_ebitda": 0.20, "pe": 0.20, "ev_sales": 0.20, "ddm": 0.00, "pb": 0.00, "rim": 0.00, "sotp": 0.00, "nav": 0.00},
    "EARLY_GROWTH": {"dcf": 0.35, "fcfe": 0.00, "ev_ebitda": 0.00, "pe": 0.00, "ev_sales": 0.40, "ddm": 0.00, "pb": 0.00, "rim": 0.00, "sotp": 0.25, "nav": 0.00},
    "CYCLICAL":     {"dcf": 0.40, "fcfe": 0.00, "ev_ebitda": 0.20, "pe": 0.25, "ev_sales": 0.00, "ddm": 0.00, "pb": 0.00, "rim": 0.00, "sotp": 0.00, "nav": 0.15},
    "FINANCIAL":    {"dcf": 0.00, "fcfe": 0.00, "ev_ebitda": 0.00, "pe": 0.20, "ev_sales": 0.00, "ddm": 0.00, "pb": 0.35, "rim": 0.45, "sotp": 0.00, "nav": 0.00},
    "CONGLOMERATE": {"dcf": 0.00, "fcfe": 0.00, "ev_ebitda": 0.30, "pe": 0.00, "ev_sales": 0.00, "ddm": 0.00, "pb": 0.00, "rim": 0.00, "sotp": 0.40, "nav": 0.30},
    "ASSET_HEAVY":  {"dcf": 0.30, "fcfe": 0.00, "ev_ebitda": 0.00, "pe": 0.25, "ev_sales": 0.00, "ddm": 0.00, "pb": 0.00, "rim": 0.00, "sotp": 0.00, "nav": 0.45},
}


def classify(fin: dict) -> dict:
    """Return stock_type and method_weights derived from an extract_financials dict."""
    stock_type = _detect_type(fin)
    weights = _TYPE_WEIGHTS[stock_type]
    method_weights = {
        method_id: {"enabled": weight > 0, "weight": weight}
        for method_id, weight in weights.items()
    }
    return {"stock_type": stock_type, "method_weights": method_weights}


def _detect_type(fin: dict) -> str:
    sector = fin.get("sector") or ""
    industry = (fin.get("industry") or "").lower()
    summary = (fin.get("long_business_summary") or "").lower()
    market_cap = fin.get("market_cap") or 0
    ebitda = fin.get("ebitda_ttm") or 0
    eps = fin.get("eps_ttm") or 0
    revenue_growth = fin.get("revenue_growth") or 0
    dividend_yield = fin.get("dividend_yield") or 0
    payout_ratio = fin.get("payout_ratio") or 0
    trailing_pe = fin.get("trailing_pe") or 0

    # 1. Financial
    if sector == "Financial Services":
        return "FINANCIAL"

    # 2. Asset-heavy / Real Estate
    if sector == "Real Estate" or (ebitda <= 0 and 0 < market_cap < 2_000_000_000):
        return "ASSET_HEAVY"

    # 3. Conglomerate
    is_conglomerate_industry = "conglomerate" in industry or "diversified" in industry
    has_conglomerate_keywords = any(kw in summary for kw in CONGLOMERATE_KEYWORDS)
    if is_conglomerate_industry or has_conglomerate_keywords:
        return "CONGLOMERATE"

    # 4. Early growth
    if revenue_growth > 0.20 and (eps <= 0 or ebitda <= 0):
        return "EARLY_GROWTH"

    # 5. Growth
    if revenue_growth > 0.10 and eps > 0 and dividend_yield < 0.01:
        return "GROWTH"

    # 6. Dividend
    if dividend_yield > 0.025 and payout_ratio > 0.40:
        return "DIVIDEND"

    # 7. Cyclical
    if sector in CYCLICAL_SECTORS or (0 < trailing_pe < 12 and revenue_growth < 0.05):
        return "CYCLICAL"

    # 8. Large cap (default)
    return "LARGE_CAP"
```

Also create an empty `backend/valuation/__init__.py` if one does not already exist (the directory currently holds calculators, so it likely exists — skip if present).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_classifier.py -v`
Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/classifier.py backend/tests/test_classifier.py
git commit -m "feat: port fairvalue3 stock-type classifier"
```

---

## Task 3: Port the 10 valuation models

**Files:**
- Create: `backend/valuation/models.py`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: a `fin` dict (Task 1) and a `growth` dict `{"optimistic": float, "realistic": float, "pessimistic": float}` (built in Task 4).
- Produces (all consumed by `valuation/engine.py`, Task 4):
  - Constants: `DISCOUNT_RATE=0.10`, `TERMINAL_GROWTH=0.03`, `HORIZON=10`, `MOS=0.90`, `EV_EBITDA_CAP=20.0`, `EV_SALES_CAP=8.0`, `ALL_METHODS` (list of 10 ids), `SCENARIO_MODELS` (set), `APPROX_METHODS={"sotp","nav"}`, `SCENARIO_KEYS=("optimistic","realistic","pessimistic")`.
  - Model functions each returning a `ModelResult` dict `{"scenarios": {opt,real,pess}, "fair_value": float|None, "weight": float, "has_scenarios": bool}`:
    `calc_dcf(fin, growth, cashflow_base=None)`, `calc_fcfe(fin, growth)`, `calc_ev_ebitda(fin, growth)`, `calc_ev_sales(fin, growth)`, `calc_pe(fin, growth)`, `calc_ddm(fin, growth)`, `calc_rim(fin, growth)`, `calc_pb(fin)`, `calc_sotp(fin)`, `calc_nav(fin)`.
  - `composite(results: dict[str, dict]) -> float | None` — weighted average over results whose `fair_value` is not None and `weight > 0`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_models.py`:

```python
import pytest
from valuation import models as m

GROWTH = {"optimistic": 0.12, "realistic": 0.07, "pessimistic": 0.03}


def test_nav_is_exact():
    # bvps=10, net_debt=0 -> fv = 10 * 0.90
    fin = {"book_value_per_share": 10.0, "net_debt": 0, "shares_outstanding": 1_000}
    r = m.calc_nav(fin)
    assert r["fair_value"] == pytest.approx(9.0)
    assert r["has_scenarios"] is False


def test_pb_justified_is_exact():
    # roe=0.10, discount=0.10 -> justifiedPB=1.0 -> fv = 10 * 1.0 * 0.90
    fin = {"book_value_per_share": 10.0, "return_on_equity": 0.10}
    r = m.calc_pb(fin)
    assert r["fair_value"] == pytest.approx(9.0)


def test_pb_floor_justified_pb_at_0_1():
    fin = {"book_value_per_share": 10.0, "return_on_equity": 0.0}
    r = m.calc_pb(fin)
    assert r["fair_value"] == pytest.approx(10.0 * 0.1 * 0.90)


def test_missing_inputs_return_null():
    assert m.calc_dcf({"fcf_ttm": None, "shares_outstanding": 1000}, GROWTH)["fair_value"] is None
    assert m.calc_ev_ebitda({"ebitda_ttm": None, "ev_ebitda": 10, "shares_outstanding": 1}, GROWTH)["fair_value"] is None
    assert m.calc_pe({"eps_ttm": 0, "payout_ratio": 0.5}, GROWTH)["fair_value"] is None
    assert m.calc_ddm({"dividend_rate": 0}, GROWTH)["fair_value"] is None


def test_ev_ebitda_multiple_is_capped():
    base = {"ebitda_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000}
    capped = m.calc_ev_ebitda({**base, "ev_ebitda": 50.0}, GROWTH)["fair_value"]
    at_cap = m.calc_ev_ebitda({**base, "ev_ebitda": 20.0}, GROWTH)["fair_value"]
    assert capped == pytest.approx(at_cap)


def test_ev_sales_multiple_is_capped():
    base = {"revenue_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000}
    capped = m.calc_ev_sales({**base, "ev_sales": 20.0}, GROWTH)["fair_value"]
    at_cap = m.calc_ev_sales({**base, "ev_sales": 8.0}, GROWTH)["fair_value"]
    assert capped == pytest.approx(at_cap)


def test_dcf_scenarios_ordered_for_positive_inputs():
    fin = {"fcf_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000}
    s = m.calc_dcf(fin, GROWTH)["scenarios"]
    assert s["optimistic"] > s["realistic"] > s["pessimistic"] > 0


def test_dcf_uses_cashflow_base_override():
    fin = {"fcf_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000}
    fcf_val = m.calc_dcf(fin, GROWTH)["fair_value"]
    cfo_val = m.calc_dcf(fin, GROWTH, cashflow_base=2_000_000)["fair_value"]
    assert cfo_val == pytest.approx(fcf_val * 2)


def test_composite_weighted_average():
    results = {
        "a": {"fair_value": 100.0, "weight": 0.75},
        "b": {"fair_value": 50.0, "weight": 0.25},
        "c": {"fair_value": None, "weight": 0.5},  # dropped
    }
    assert m.composite(results) == pytest.approx((100 * 0.75 + 50 * 0.25) / 1.0)


def test_composite_empty_is_none():
    assert m.composite({"a": {"fair_value": None, "weight": 0.5}}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'valuation.models'`.

- [ ] **Step 3: Create the models module**

Create `backend/valuation/models.py`:

```python
from __future__ import annotations

DISCOUNT_RATE = 0.10
TERMINAL_GROWTH = 0.03
HORIZON = 10
MOS = 0.90
EV_EBITDA_CAP = 20.0
EV_SALES_CAP = 8.0

ALL_METHODS = ["dcf", "fcfe", "ev_ebitda", "pe", "ev_sales", "ddm", "pb", "rim", "sotp", "nav"]
SCENARIO_MODELS = {"dcf", "fcfe", "ev_ebitda", "ev_sales", "pe", "ddm", "rim"}
APPROX_METHODS = {"sotp", "nav"}
SCENARIO_KEYS = ("optimistic", "realistic", "pessimistic")


# -- helpers -------------------------------------------------------------------
def _pv(cf: float, rate: float, year: int) -> float:
    return cf / (1 + rate) ** year


def _apply_mos(value: float) -> float:
    return value * MOS


def _avg(scenarios: dict) -> float | None:
    vals = [v for v in scenarios.values() if v is not None]
    return sum(vals) / len(vals) if vals else None


def _null_result(has_scenarios: bool) -> dict:
    return {
        "scenarios": {"optimistic": None, "realistic": None, "pessimistic": None},
        "fair_value": None,
        "weight": 0.0,
        "has_scenarios": has_scenarios,
    }


def _scenario_dcf_equity(cf: float, growth: float, net_debt: float, shares: float) -> float:
    total = 0.0
    cf_t = cf
    for t in range(1, HORIZON + 1):
        cf_t *= (1 + growth)
        total += _pv(cf_t, DISCOUNT_RATE, t)
    tv = cf_t * (1 + TERMINAL_GROWTH) / (DISCOUNT_RATE - TERMINAL_GROWTH)
    total += _pv(tv, DISCOUNT_RATE, HORIZON)
    return _apply_mos((total - net_debt) / shares)


def _scenario_ev_multiple(base: float, growth: float, multiple: float, net_debt: float, shares: float) -> float:
    projected = base * (1 + growth) ** HORIZON
    future_ev = projected * multiple
    return _apply_mos((future_ev - net_debt) / shares / (1 + DISCOUNT_RATE) ** HORIZON)


# -- DCF (FCFF) ----------------------------------------------------------------
def calc_dcf(fin: dict, growth: dict, cashflow_base: float | None = None) -> dict:
    base = cashflow_base if cashflow_base is not None else fin.get("fcf_ttm")
    shares = fin.get("shares_outstanding")
    if base is None or not shares:
        return _null_result(True)
    net_debt = fin.get("net_debt") or 0
    scenarios = {k: _scenario_dcf_equity(base, growth[k], net_debt, shares) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- FCFE DCF (dormant) --------------------------------------------------------
def calc_fcfe(fin: dict, growth: dict) -> dict:
    fcf = fin.get("fcf_ttm")
    shares = fin.get("shares_outstanding")
    if fcf is None or not shares:
        return _null_result(True)
    tax_rate = fin.get("effective_tax_rate")
    tax_rate = 0.21 if tax_rate is None else tax_rate
    interest_adj = (fin.get("interest_expense") or 0) * (1 - tax_rate)
    fcfe = fcf - interest_adj
    scenarios = {k: _scenario_dcf_equity(fcfe, growth[k], 0, shares) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- EV/EBITDA -----------------------------------------------------------------
def calc_ev_ebitda(fin: dict, growth: dict) -> dict:
    ebitda = fin.get("ebitda_ttm")
    multiple = fin.get("ev_ebitda")
    shares = fin.get("shares_outstanding")
    if ebitda is None or multiple is None or not shares:
        return _null_result(True)
    multiple = min(multiple, EV_EBITDA_CAP)
    net_debt = fin.get("net_debt") or 0
    scenarios = {k: _scenario_ev_multiple(ebitda, growth[k], multiple, net_debt, shares) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- EV/Sales ------------------------------------------------------------------
def calc_ev_sales(fin: dict, growth: dict) -> dict:
    revenue = fin.get("revenue_ttm")
    multiple = fin.get("ev_sales")
    shares = fin.get("shares_outstanding")
    if revenue is None or multiple is None or not shares:
        return _null_result(True)
    multiple = min(multiple, EV_SALES_CAP)
    net_debt = fin.get("net_debt") or 0
    scenarios = {k: _scenario_ev_multiple(revenue, growth[k], multiple, net_debt, shares) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- P/E (justified) -----------------------------------------------------------
def calc_pe(fin: dict, growth: dict) -> dict:
    eps = fin.get("eps_ttm")
    payout = fin.get("payout_ratio")
    if eps is None or eps <= 0 or payout is None:
        return _null_result(True)

    def scenario_pe(g: float) -> float:
        capped_g = min(g, DISCOUNT_RATE - 0.01)
        pe = payout / (DISCOUNT_RATE - capped_g) if capped_g > 0 else payout / DISCOUNT_RATE
        return _apply_mos(eps * max(pe, 1))

    scenarios = {k: scenario_pe(growth[k]) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- DDM (Gordon growth) -------------------------------------------------------
def calc_ddm(fin: dict, growth: dict) -> dict:
    div = fin.get("dividend_rate")
    if div is None or div <= 0:
        return _null_result(True)

    def scenario_ddm(g: float) -> float | None:
        capped_g = min(g, DISCOUNT_RATE - 0.01)
        if DISCOUNT_RATE <= capped_g:
            return None
        return _apply_mos(div * (1 + capped_g) / (DISCOUNT_RATE - capped_g))

    scenarios = {k: scenario_ddm(growth[k]) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- P/B (justified) -----------------------------------------------------------
def calc_pb(fin: dict) -> dict:
    bvps = fin.get("book_value_per_share")
    roe = fin.get("return_on_equity")
    if bvps is None or roe is None:
        return _null_result(False)
    justified_pb = roe / DISCOUNT_RATE
    fv = _apply_mos(bvps * max(justified_pb, 0.1))
    return {"scenarios": {k: fv for k in SCENARIO_KEYS}, "fair_value": fv, "weight": 0.0, "has_scenarios": False}


# -- RIM (residual income) -----------------------------------------------------
def calc_rim(fin: dict, growth: dict) -> dict:
    bvps = fin.get("book_value_per_share")
    eps = fin.get("eps_ttm")
    if bvps is None or eps is None:
        return _null_result(True)
    coe = fin.get("cost_of_equity") or 0.10
    roe = eps / bvps if bvps > 0 else 0

    def scenario_rim(g: float) -> float:
        total = 0.0
        bv = bvps
        for t in range(1, HORIZON + 1):
            bv_prev = bv
            bv = bv * (1 + g)
            total += _pv(bv_prev * (roe - coe), coe, t)
        return _apply_mos(bvps + total)

    scenarios = {k: scenario_rim(growth[k]) for k in SCENARIO_KEYS}
    return {"scenarios": scenarios, "fair_value": _avg(scenarios), "weight": 0.0, "has_scenarios": True}


# -- SOTP (EV/EBITDA with 15% conglomerate discount) ---------------------------
def calc_sotp(fin: dict) -> dict:
    ebitda = fin.get("ebitda_ttm")
    multiple = fin.get("ev_ebitda")
    shares = fin.get("shares_outstanding")
    if ebitda is None or multiple is None or not shares:
        return _null_result(False)
    multiple = min(multiple, EV_EBITDA_CAP)
    net_debt = fin.get("net_debt") or 0
    ev = ebitda * multiple
    fv = _apply_mos((ev - net_debt) / shares * 0.85)
    return {"scenarios": {k: fv for k in SCENARIO_KEYS}, "fair_value": fv, "weight": 0.0, "has_scenarios": False}


# -- NAV (book value adjusted for net debt per share) --------------------------
def calc_nav(fin: dict) -> dict:
    bvps = fin.get("book_value_per_share")
    shares = fin.get("shares_outstanding")
    if bvps is None or not shares:
        return _null_result(False)
    net_debt = fin.get("net_debt") or 0
    fv = _apply_mos(bvps - net_debt / shares)
    return {"scenarios": {k: fv for k in SCENARIO_KEYS}, "fair_value": fv, "weight": 0.0, "has_scenarios": False}


# -- composite -----------------------------------------------------------------
def composite(results: dict) -> float | None:
    """Weighted average over results whose fair_value is not None and weight > 0."""
    total = 0.0
    total_weight = 0.0
    for r in results.values():
        if r.get("fair_value") is not None and r.get("weight", 0) > 0:
            total += r["fair_value"] * r["weight"]
            total_weight += r["weight"]
    return total / total_weight if total_weight > 0 else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_models.py -v`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/models.py backend/tests/test_models.py
git commit -m "feat: port fairvalue3 10-model valuation engine to Python"
```

---

## Task 4: Build the engine — `evaluate(fin)` pipeline

This task builds the pure orchestration: scenarios, EV-pick + weight folding, capex→CFO selection, model computation, null-drop, renormalization, composite. The async `run(ticker)` wrapper and `TickerResult` construction are added later in Task 6 (after the pydantic model is reshaped).

**Files:**
- Create: `backend/valuation/engine.py`
- Test: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `classify` (Task 2); the model functions + `composite` + constants (Task 3); a `fin` dict (Task 1).
- Produces (consumed by Task 6):
  - `build_scenarios(fin: dict) -> dict` — per-stock capped `{optimistic, realistic, pessimistic}`.
  - `pick_ev_multiple(weights: dict[str, float], fin: dict) -> dict[str, float]` — folds the losing EV weight into the winner when both are weighted.
  - `dcf_cashflow_base(fin: dict) -> float | None` — returns CFO above the capex gate, else FCF.
  - `evaluate(fin: dict) -> dict` — result dict with keys: `ticker, company_name, current_price, last_evaluated (None), stock_type, fair_value, price_vs_fair_value_pct, fair_value_breakdown, status, errors`. `fair_value_breakdown` maps each contributing model id → `{weight (normalized), fair_value, scenarios{opt,real,pess}, is_approx}`.
  - Constants `EBITDA_MARGIN_FLOOR=0.08`, `CAPEX_CFO_GATE=0.50`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_engine.py`:

```python
import pytest
from valuation import engine


def _large_cap_fin(**over):
    fin = {
        "ticker": "AAPL", "company_name": "Apple Inc.", "current_price": 190.0,
        "sector": "Technology", "industry": "Consumer Electronics", "long_business_summary": "",
        "market_cap": 3_000_000_000_000, "shares_outstanding": 15_000_000_000,
        "fcf_ttm": 99_000_000_000, "operating_cashflow": 120_000_000_000,
        "net_debt": 0, "ebitda_ttm": 130_000_000_000, "revenue_ttm": 391_000_000_000,
        "eps_ttm": 6.6, "book_value_per_share": 4.0,
        "dividend_rate": 1.0, "dividend_yield": 0.005, "payout_ratio": 0.15,
        "return_on_equity": 1.4, "trailing_pe": 28.0, "revenue_growth": 0.05,
        "earnings_growth": 0.08, "ev_ebitda": 24.0, "ev_sales": 8.0,
        "interest_expense": 0, "effective_tax_rate": 0.15, "cost_of_equity": 0.10,
    }
    fin.update(over)
    return fin


def test_build_scenarios_capped():
    s = engine.build_scenarios({"earnings_growth": 0.56, "revenue_growth": 0.10})
    assert s["realistic"] == 0.20            # capped at 0.20
    assert s["optimistic"] == pytest.approx(0.25)
    assert s["pessimistic"] == pytest.approx(0.16)


def test_build_scenarios_floor():
    s = engine.build_scenarios({"earnings_growth": -0.5, "revenue_growth": None})
    assert s["realistic"] == 0.02
    assert s["pessimistic"] == 0.02


def test_pick_ev_uses_ebitda_when_margin_healthy():
    weights = {"ev_ebitda": 0.20, "ev_sales": 0.20}
    fin = {"ebitda_ttm": 100, "revenue_ttm": 1000}  # 10% margin > 8%
    out = engine.pick_ev_multiple(weights, fin)
    assert out["ev_ebitda"] == pytest.approx(0.40)
    assert out["ev_sales"] == 0.0


def test_pick_ev_uses_sales_when_margin_thin():
    weights = {"ev_ebitda": 0.20, "ev_sales": 0.20}
    fin = {"ebitda_ttm": 50, "revenue_ttm": 1000}  # 5% margin < 8%
    out = engine.pick_ev_multiple(weights, fin)
    assert out["ev_sales"] == pytest.approx(0.40)
    assert out["ev_ebitda"] == 0.0


def test_pick_ev_no_fold_when_only_one_weighted():
    weights = {"ev_ebitda": 0.30, "ev_sales": 0.0}
    fin = {"ebitda_ttm": 10, "revenue_ttm": 1000}  # thin margin, but ev_sales not weighted
    out = engine.pick_ev_multiple(weights, fin)
    assert out["ev_ebitda"] == 0.30
    assert out["ev_sales"] == 0.0


def test_dcf_cashflow_base_swaps_to_cfo_above_gate():
    # capex = 120 - 50 = 70; 70/120 = 0.58 > 0.50 -> use CFO (120)
    fin = {"operating_cashflow": 120, "fcf_ttm": 50}
    assert engine.dcf_cashflow_base(fin) == 120


def test_dcf_cashflow_base_keeps_fcf_below_gate():
    # capex = 120 - 90 = 30; 30/120 = 0.25 < 0.50 -> use FCF (90)
    fin = {"operating_cashflow": 120, "fcf_ttm": 90}
    assert engine.dcf_cashflow_base(fin) == 90


def test_dcf_cashflow_base_defaults_to_fcf_when_cfo_missing():
    assert engine.dcf_cashflow_base({"operating_cashflow": None, "fcf_ttm": 90}) == 90


def test_evaluate_large_cap_blend():
    fin = _large_cap_fin()
    result = engine.evaluate(fin)
    assert result["status"] == "completed"
    assert result["stock_type"] == "LARGE_CAP"
    assert result["fair_value"] is not None and result["fair_value"] > 0
    # breakdown weights renormalize to ~1.0
    total_w = sum(b["weight"] for b in result["fair_value_breakdown"].values())
    assert total_w == pytest.approx(1.0)
    # composite is the weight-internal blend of the breakdown values (consistency guard)
    blend = sum(b["weight"] * b["fair_value"] for b in result["fair_value_breakdown"].values())
    assert result["fair_value"] == pytest.approx(blend, rel=1e-6)
    # LARGE_CAP weights both EV multiples; only one should survive the fold
    bd = result["fair_value_breakdown"]
    assert not ("ev_ebitda" in bd and "ev_sales" in bd)


def test_evaluate_price_vs_fair_value_pct():
    fin = _large_cap_fin(current_price=100.0)
    result = engine.evaluate(fin)
    expected = round((result["fair_value"] - 100.0) / 100.0 * 100, 2)
    assert result["price_vs_fair_value_pct"] == expected


def test_evaluate_insufficient_data_is_failed():
    fin = {"ticker": "ZZZ", "sector": "Technology", "shares_outstanding": None,
           "current_price": 10.0, "company_name": "Zilch"}
    result = engine.evaluate(fin)
    assert result["status"] == "failed"
    assert "insufficient data for any model" in result["errors"]


def test_evaluate_sotp_flagged_approx():
    # Conglomerate weights sotp + nav + ev_ebitda
    fin = _large_cap_fin(industry="Conglomerates", book_value_per_share=20.0)
    result = engine.evaluate(fin)
    assert result["stock_type"] == "CONGLOMERATE"
    assert result["fair_value_breakdown"]["sotp"]["is_approx"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'valuation.engine'`.

- [ ] **Step 3: Create the engine module (`evaluate` + helpers only)**

Create `backend/valuation/engine.py`:

```python
from __future__ import annotations
from valuation.classifier import classify
from valuation import models as m

EBITDA_MARGIN_FLOOR = 0.08
CAPEX_CFO_GATE = 0.50

_SINGLE_VALUE_FN = {"pb": m.calc_pb, "sotp": m.calc_sotp, "nav": m.calc_nav}
_SCENARIO_FN = {
    "fcfe": m.calc_fcfe,
    "ev_ebitda": m.calc_ev_ebitda,
    "ev_sales": m.calc_ev_sales,
    "pe": m.calc_pe,
    "ddm": m.calc_ddm,
    "rim": m.calc_rim,
}


def build_scenarios(fin: dict) -> dict:
    """Per-stock capped growth scenarios (spec decision #1)."""
    raw = fin.get("earnings_growth") or fin.get("revenue_growth") or 0.07
    base = max(0.02, min(float(raw), 0.20))
    return {
        "optimistic": min(base + 0.05, 0.25),
        "realistic": base,
        "pessimistic": max(base - 0.04, 0.02),
    }


def pick_ev_multiple(weights: dict, fin: dict) -> dict:
    """Decision #4: when a type weights BOTH EV multiples, keep one and fold the
    loser's weight into the winner. Use EV/Sales when EBITDA is null/<=0 or the
    EBITDA margin is below the floor; otherwise EV/EBITDA."""
    w = dict(weights)
    if w.get("ev_ebitda", 0) > 0 and w.get("ev_sales", 0) > 0:
        ebitda = fin.get("ebitda_ttm")
        revenue = fin.get("revenue_ttm")
        margin = (ebitda / revenue) if (ebitda is not None and revenue) else None
        use_sales = (
            ebitda is None or ebitda <= 0
            or margin is None or margin < EBITDA_MARGIN_FLOOR
        )
        if use_sales:
            w["ev_sales"] = w["ev_sales"] + w["ev_ebitda"]
            w["ev_ebitda"] = 0.0
        else:
            w["ev_ebitda"] = w["ev_ebitda"] + w["ev_sales"]
            w["ev_sales"] = 0.0
    return w


def dcf_cashflow_base(fin: dict) -> float | None:
    """Decision #6: use CFO instead of FCF for the DCF base when capex is huge."""
    fcf = fin.get("fcf_ttm")
    cfo = fin.get("operating_cashflow")
    if cfo is not None and fcf is not None and cfo > 0:
        capex = cfo - fcf
        if capex / cfo > CAPEX_CFO_GATE:
            return cfo
    return fcf


def evaluate(fin: dict) -> dict:
    """Pure valuation pipeline. Returns a result dict (no IO, no timestamps)."""
    classification = classify(fin)
    stock_type = classification["stock_type"]
    weights = {mid: classification["method_weights"][mid]["weight"] for mid in m.ALL_METHODS}
    weights = pick_ev_multiple(weights, fin)
    growth = build_scenarios(fin)
    cf_base = dcf_cashflow_base(fin)

    results: dict[str, dict] = {}
    for mid in m.ALL_METHODS:
        weight = weights.get(mid, 0.0)
        if weight <= 0:
            continue
        if mid == "dcf":
            r = m.calc_dcf(fin, growth, cashflow_base=cf_base)
        elif mid in _SCENARIO_FN:
            r = _SCENARIO_FN[mid](fin, growth)
        else:
            r = _SINGLE_VALUE_FN[mid](fin)
        r["weight"] = weight
        if r["fair_value"] is not None:
            results[mid] = r

    company_name = fin.get("company_name")
    current_price = fin.get("current_price")
    ticker = fin.get("ticker") or ""

    if not results:
        return {
            "ticker": ticker, "company_name": company_name, "current_price": current_price,
            "last_evaluated": None, "stock_type": stock_type, "fair_value": None,
            "price_vs_fair_value_pct": None, "fair_value_breakdown": {},
            "status": "failed", "errors": ["insufficient data for any model"],
        }

    fair_value = m.composite(results)
    total_weight = sum(r["weight"] for r in results.values())
    breakdown = {
        mid: {
            "weight": round(r["weight"] / total_weight, 4),
            "fair_value": round(r["fair_value"], 2),
            "scenarios": {
                k: (round(v, 2) if v is not None else None)
                for k, v in r["scenarios"].items()
            },
            "is_approx": mid in m.APPROX_METHODS,
        }
        for mid, r in results.items()
    }

    pct = None
    if fair_value is not None and current_price and current_price > 0:
        pct = round((fair_value - current_price) / current_price * 100, 2)

    return {
        "ticker": ticker, "company_name": company_name, "current_price": current_price,
        "last_evaluated": None, "stock_type": stock_type,
        "fair_value": round(fair_value, 2) if fair_value is not None else None,
        "price_vs_fair_value_pct": pct, "fair_value_breakdown": breakdown,
        "status": "completed", "errors": [],
    }
```

> **Note on the consistency guard:** `evaluate` rounds each model's `fair_value` to 2 dp in the breakdown but composites from the unrounded values, so `test_evaluate_large_cap_blend` uses `rel=1e-6` rather than exact equality. If the implementer prefers exact equality, composite from the rounded breakdown values instead — either is acceptable; keep the test and code consistent.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_engine.py -v`
Expected: PASS (12 tests). If the blend consistency assertion fails on rounding, see the note above.

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/engine.py backend/tests/test_engine.py
git commit -m "feat: add fair-value engine pipeline (evaluate)"
```

---

## Task 5: Cutover part 1 — reshape `models.py`, add `engine.run`, new Sheets schema

This task reshapes the data model, adds the async `run` wrapper, rewrites the Sheets I/O to the new 16-column schema, deletes the now-redundant aggregator, and removes the three obsolete test files. After this task the **backend test suite is green**, but `uvicorn main:app` will not import yet (batch.py/analysis.py still reference deleted symbols) — Task 6 completes the wiring. Do not start the server between Task 5 and Task 6.

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/valuation/engine.py` (add `run`)
- Modify: `backend/services/sheets.py`
- Delete: `backend/orchestrator/aggregator.py`
- Delete: `backend/tests/test_base_agent_parse.py`, `backend/tests/test_batch_service.py`, `backend/tests/test_normalizer_prescreener.py`
- Test: `backend/tests/test_engine_run.py` (new), `backend/tests/test_sheets_row.py` (new)

**Interfaces:**
- Produces: reshaped `TickerResult` (fields: `ticker, company_name, current_price, last_evaluated, stock_type, fair_value, price_vs_fair_value_pct, fair_value_breakdown, status, errors`); `AnalyseRequest` without `mode`; `engine.run(ticker: str) -> TickerResult` (async). Consumed by `batch.py`, `analysis.py`, `sheets.py` (Task 6).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_engine_run.py`:

```python
import pytest
from unittest.mock import patch
from valuation import engine
from models import TickerResult

_INFO = {
    "symbol": "AAPL", "shortName": "Apple Inc.", "currentPrice": 190.0,
    "marketCap": 3_000_000_000_000, "sharesOutstanding": 15_000_000_000,
    "freeCashflow": 99_000_000_000, "operatingCashflow": 120_000_000_000,
    "ebitda": 130_000_000_000, "totalRevenue": 391_000_000_000,
    "trailingEps": 6.6, "bookValue": 4.0, "dividendRate": 1.0,
    "payoutRatio": 0.15, "returnOnEquity": 1.4, "trailingPE": 28.0,
    "revenueGrowth": 0.05, "earningsGrowth": 0.08,
    "enterpriseToEbitda": 24.0, "enterpriseToRevenue": 8.0,
    "sector": "Technology", "industry": "Consumer Electronics",
}


@pytest.mark.asyncio
async def test_run_returns_completed_ticker_result():
    with patch("valuation.engine.fetch_ticker_info", return_value=_INFO):
        result = await engine.run("AAPL")
    assert isinstance(result, TickerResult)
    assert result.status == "completed"
    assert result.stock_type == "LARGE_CAP"
    assert result.fair_value is not None
    assert result.last_evaluated is not None


@pytest.mark.asyncio
async def test_run_yfinance_failure_is_failed():
    with patch("valuation.engine.fetch_ticker_info", side_effect=ValueError("boom")):
        result = await engine.run("BADX")
    assert result.status == "failed"
    assert result.errors == ["yfinance data unavailable"]
```

Create `backend/tests/test_sheets_row.py`:

```python
from models import TickerResult
from services.sheets import _result_to_row, _DB_HEADERS, _MODEL_COLS


def test_db_headers_length_matches_row():
    r = TickerResult(
        ticker="AAPL", company_name="Apple", last_evaluated="2026-06-21T00:00:00",
        stock_type="LARGE_CAP", fair_value=180.5, current_price=190.0,
        price_vs_fair_value_pct=-5.0,
        fair_value_breakdown={
            "dcf": {"weight": 0.5, "fair_value": 175.0, "scenarios": {}, "is_approx": False},
            "ev_ebitda": {"weight": 0.5, "fair_value": 186.0, "scenarios": {}, "is_approx": False},
        },
    )
    row = _result_to_row(r)
    assert len(row) == len(_DB_HEADERS) == 16
    assert row[0] == "AAPL"
    assert row[3] == "LARGE_CAP"
    # dcf is the first model column (index 7); ev_ebitda the second (index 8)
    assert row[7 + _MODEL_COLS.index("dcf")] == 175.0
    assert row[7 + _MODEL_COLS.index("ev_ebitda")] == 186.0
    # a model not in the breakdown is blank
    assert row[7 + _MODEL_COLS.index("nav")] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_engine_run.py tests/test_sheets_row.py -v`
Expected: FAIL (`AttributeError`/`ImportError`: `engine.run` and `_MODEL_COLS` / new `TickerResult` fields do not exist yet).

- [ ] **Step 3: Reshape `backend/models.py`**

Replace the entire contents of `backend/models.py` with:

```python
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel


class TickerResult(BaseModel):
    ticker: str
    company_name: str | None = None
    current_price: float | None = None
    last_evaluated: str | None = None
    stock_type: str | None = None
    fair_value: float | None = None
    price_vs_fair_value_pct: float | None = None
    fair_value_breakdown: dict = {}
    status: Literal["completed", "failed"] = "completed"
    errors: list[str] = []


class AnalyseRequest(BaseModel):
    tickers: list[str] = []
    sheets_url: str | None = None


class JobStatus(BaseModel):
    job_id: str
    total: int
    completed: int
    failed: int
    status: Literal["running", "completed", "failed", "cancelled"]
    results: list[TickerResult] = []
```

- [ ] **Step 4: Add `run` to `backend/valuation/engine.py`**

At the top of `backend/valuation/engine.py`, change the import block to add the IO + model imports:

```python
from __future__ import annotations
from datetime import datetime, timezone
from valuation.classifier import classify
from valuation import models as m
from services.yahoo import fetch_ticker_info, extract_financials
from models import TickerResult
```

Then append at the end of the file:

```python
async def run(ticker: str) -> TickerResult:
    """Async IO wrapper: fetch + extract + evaluate -> TickerResult."""
    try:
        info = await fetch_ticker_info(ticker)
    except Exception:
        return TickerResult(ticker=ticker.upper(), status="failed",
                            errors=["yfinance data unavailable"])
    fin = extract_financials(info)
    fin["ticker"] = fin.get("ticker") or ticker.upper()
    data = evaluate(fin)
    data["last_evaluated"] = datetime.now(timezone.utc).isoformat()
    return TickerResult(**data)
```

- [ ] **Step 5: Rewrite `backend/services/sheets.py` schema**

In `backend/services/sheets.py`, replace `_result_to_row`, `_DB_HEADERS`, and `_read_database_sync` (lines 47-75 and 142-188), and the range strings, as follows.

Replace the `_result_to_row` + `_DB_HEADERS` block (currently lines 47-75) with:

```python
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
```

Replace `_read_database_sync` (currently lines 142-188) with:

```python
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
```

(The `_upsert_sync` read range `Database!A:A` and append/update logic are unchanged — they key off column A only.)

- [ ] **Step 6: Delete the redundant aggregator and obsolete tests**

```bash
git rm backend/orchestrator/aggregator.py \
       backend/tests/test_base_agent_parse.py \
       backend/tests/test_batch_service.py \
       backend/tests/test_normalizer_prescreener.py
```

- [ ] **Step 7: Run the backend suite to verify green**

Run: `cd backend && python -m pytest -v`
Expected: PASS for `test_yahoo_block`, `test_classifier`, `test_models`, `test_engine`, `test_engine_run`, `test_sheets_row`. No collection errors (the obsolete tests are gone). `batch.py`/`analysis.py` are not imported by any test, so the suite is green even though the app is mid-cutover.

- [ ] **Step 8: Commit**

```bash
git add backend/models.py backend/valuation/engine.py backend/services/sheets.py \
        backend/tests/test_engine_run.py backend/tests/test_sheets_row.py
git commit -m "feat: reshape TickerResult, add engine.run, new Database schema"
```

---

## Task 6: Cutover part 2 — wire engine into the pipeline, delete dead code

After this task the backend imports and runs FV-only: `uvicorn main:app` starts, `/api/analyse` streams `engine.run` results to Sheets and SSE, and there is zero Anthropic surface.

**Files:**
- Modify: `backend/orchestrator/batch.py`
- Modify: `backend/routers/analysis.py`
- Modify: `backend/main.py`
- Modify: `backend/requirements.txt`
- Delete: `backend/agents/` (all 8 files), `backend/prompts/` (all 6 files), `backend/services/batch_service.py`, `backend/services/normalizer.py`, `backend/routers/jobs.py`, `backend/valuation/calculator_1.py`, `backend/valuation/calculator_2.py`, `backend/valuation/gemini_fv.py`
- Test: `backend/tests/test_batch_smoke.py` (new)

**Interfaces:**
- Consumes: `engine.run` (Task 5), `read_tickers`/`upsert_result` (existing sheets), `validate_ticker` (existing yahoo).
- Produces: `run_batch(tickers, job_id, cancel_event)` unchanged in signature/events; `analysis.py` `/analyse` always uses the streaming path.

- [ ] **Step 1: Write the failing smoke test**

Create `backend/tests/test_batch_smoke.py`:

```python
import asyncio
import pytest
from unittest.mock import patch, AsyncMock
from models import TickerResult
from orchestrator import batch


@pytest.mark.asyncio
async def test_run_batch_emits_lifecycle_events():
    fake = TickerResult(ticker="AAPL", status="completed", fair_value=100.0)
    with patch.object(batch, "engine") as eng, \
         patch.object(batch, "upsert_result", new=AsyncMock()):
        eng.run = AsyncMock(return_value=fake)
        events = []
        async for ev in batch.run_batch(["AAPL"], "job-1", asyncio.Event()):
            events.append(ev["type"])
    assert events[0] == "job_start"
    assert "ticker_done" in events
    assert events[-1] == "job_done"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_batch_smoke.py -v`
Expected: FAIL (`AttributeError`: `batch` has no attribute `engine`; current `batch.py` imports deleted agent modules and will raise an ImportError on collection).

- [ ] **Step 3: Rewrite `backend/orchestrator/batch.py`**

Replace the entire contents of `backend/orchestrator/batch.py` with:

```python
from __future__ import annotations
import asyncio, os
from collections.abc import AsyncGenerator
from valuation import engine
from services.sheets import upsert_result

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))


async def run_batch(
    tickers: list[str],
    job_id: str,
    cancel_event: asyncio.Event,
) -> AsyncGenerator[dict, None]:
    """Process tickers in groups of BATCH_SIZE, yield SSE events."""
    total = len(tickers)
    completed = 0
    failed = 0

    yield {"type": "job_start", "job_id": job_id, "total": total}

    groups = [tickers[i : i + BATCH_SIZE] for i in range(0, len(tickers), BATCH_SIZE)]

    for group in groups:
        if cancel_event.is_set():
            break

        group_tasks = {t: asyncio.create_task(engine.run(t)) for t in group}

        for ticker, task in group_tasks.items():
            yield {"type": "ticker_start", "ticker": ticker}
            try:
                result = await task
                if result.status == "failed":
                    failed += 1
                else:
                    completed += 1
                    try:
                        await upsert_result(result)
                    except Exception as e:
                        result.errors.append(f"sheets_write: {e}")
                yield {"type": "ticker_done", "ticker": ticker, "result": result.model_dump()}
            except Exception as e:
                failed += 1
                yield {"type": "ticker_error", "ticker": ticker, "error": str(e)}

    status = "cancelled" if cancel_event.is_set() else "completed"
    yield {"type": "job_done", "job_id": job_id, "completed": completed, "failed": failed, "status": status}
```

- [ ] **Step 4: Rewrite `backend/routers/analysis.py`**

Replace the entire contents of `backend/routers/analysis.py` with:

```python
from __future__ import annotations
import asyncio, json, uuid
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from models import AnalyseRequest
from services.yahoo import validate_ticker
from services.sheets import read_tickers
from orchestrator.batch import run_batch

router = APIRouter()

_jobs: dict[str, dict] = {}
_cancel_events: dict[str, asyncio.Event] = {}


@router.post("/analyse")
async def start_analysis(request: AnalyseRequest):
    tickers: list[str] = []

    if request.tickers:
        tickers.extend([t.strip().upper() for t in request.tickers if t.strip()])

    if request.sheets_url and not request.tickers:
        try:
            sheet_tickers = await read_tickers()
            tickers.extend([t.upper() for t in sheet_tickers if t not in tickers])
        except Exception as e:
            if not tickers:
                return {"error": f"No tickers provided and Sheets read failed: {e}"}

    if not tickers:
        return {"error": "No tickers provided"}

    valid_results = await asyncio.gather(*[validate_ticker(t) for t in tickers])
    valid_tickers = [t for t, ok in zip(tickers, valid_results) if ok]
    invalid_tickers = [t for t, ok in zip(tickers, valid_results) if not ok]

    if not valid_tickers:
        return {"error": "No valid tickers found", "invalid": invalid_tickers}

    job_id = str(uuid.uuid4())
    cancel_event = asyncio.Event()
    _cancel_events[job_id] = cancel_event
    _jobs[job_id] = {
        "status": "running",
        "total": len(valid_tickers),
        "completed": 0,
        "failed": 0,
        "results": [],
        "invalid": invalid_tickers,
    }
    asyncio.create_task(_run_job(job_id, valid_tickers, cancel_event))
    return {"job_id": job_id, "total": len(valid_tickers), "invalid": invalid_tickers}


async def _run_job(job_id: str, tickers: list[str], cancel_event: asyncio.Event):
    job = _jobs[job_id]
    async for event in run_batch(tickers, job_id, cancel_event):
        if event["type"] == "ticker_done":
            job["completed"] += 1
            job["results"].append(event["result"])
        elif event["type"] == "ticker_error":
            job["failed"] += 1
        elif event["type"] == "job_done":
            job["status"] = event["status"]


@router.get("/stream/{job_id}")
async def stream_job(job_id: str):
    if job_id not in _jobs:
        return {"error": "Job not found"}

    async def event_generator():
        last_sent = 0
        while True:
            job = _jobs.get(job_id)
            if not job:
                break
            results = job["results"]
            for result in results[last_sent:]:
                yield {"event": "ticker_done", "data": json.dumps(result)}
                last_sent += 1
            yield {
                "event": "status",
                "data": json.dumps({
                    "job_id": job_id,
                    "status": job["status"],
                    "total": job["total"],
                    "completed": job["completed"],
                    "failed": job["failed"],
                }),
            }
            if job["status"] in ("completed", "failed", "cancelled"):
                break
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


@router.post("/cancel/{job_id}")
async def cancel_job(job_id: str):
    if job_id in _cancel_events:
        _cancel_events[job_id].set()
        if job_id in _jobs:
            _jobs[job_id]["status"] = "cancelled"
        return {"cancelled": True}
    return {"error": "Job not found"}
```

- [ ] **Step 5: Update `backend/main.py`**

Replace the entire contents of `backend/main.py` with:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers.analysis import router as analysis_router
from routers.database import router as database_router

load_dotenv()

app = FastAPI(title="Fair Value Batch Calculator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router, prefix="/api")
app.include_router(database_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Remove `anthropic` from `backend/requirements.txt`**

Delete the line `anthropic==0.40.0` (line 4) from `backend/requirements.txt`.

- [ ] **Step 7: Delete the dead AI/Batch-API modules**

```bash
git rm -r backend/agents backend/prompts \
       backend/services/batch_service.py \
       backend/services/normalizer.py \
       backend/routers/jobs.py \
       backend/valuation/calculator_1.py \
       backend/valuation/calculator_2.py \
       backend/valuation/gemini_fv.py
```

- [ ] **Step 8: Verify the app imports and the full suite is green**

Run: `cd backend && python -c "import main; print('import OK')"`
Expected: prints `import OK` with no ImportError.

Run: `cd backend && python -m pytest -v`
Expected: PASS for all backend tests, including the new `test_batch_smoke`.

- [ ] **Step 9: Commit**

```bash
git add -A backend
git commit -m "feat: wire FV engine into batch pipeline; remove AI agents + Batch API"
```

---

## Task 7: Frontend cutover — fair-value UI

This is an atomic UI cutover: the `TickerResult` type changes shape, so every consumer changes together. The gate is a single clean `npm run build` (type-check + bundle) at the end. Commit once.

**Files:**
- Modify: `frontend/src/types.ts`, `frontend/src/App.tsx`, `frontend/src/pages/Home.tsx`, `frontend/src/pages/Progress.tsx`, `frontend/src/pages/Results.tsx`, `frontend/src/pages/Database.tsx`, `frontend/src/pages/TickerDetail.tsx`, `frontend/src/components/FairValuePanel.tsx`
- Delete: `frontend/src/components/ScoreBadge.tsx`, `frontend/src/components/AgentCard.tsx`, `frontend/src/pages/JobStatus.tsx`

**Interfaces:**
- Produces (used across the frontend): `TickerResult` (new shape mirroring backend), `ModelBreakdown`, `METHOD_LABELS`, `fvGapLabel(pct)`, `fvGapColor(pct)`, `fvBadgeClass(pct)`. `JobStatus` is retained (used by `useAnalysisStream`).

- [ ] **Step 1: Replace `frontend/src/types.ts`**

Replace the entire contents of `frontend/src/types.ts` with:

```ts
export interface ModelBreakdown {
  weight: number
  fair_value: number
  scenarios: {
    optimistic: number | null
    realistic: number | null
    pessimistic: number | null
  }
  is_approx: boolean
}

export interface TickerResult {
  ticker: string
  company_name: string | null
  current_price: number | null
  last_evaluated: string | null
  stock_type: string | null
  fair_value: number | null
  price_vs_fair_value_pct: number | null
  fair_value_breakdown: Record<string, ModelBreakdown>
  status: 'completed' | 'failed'
  errors: string[]
}

export interface JobStatus {
  job_id: string
  total: number
  completed: number
  failed: number
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  results: TickerResult[]
}

/** Display labels for model ids, matching backend valuation/models.ALL_METHODS. */
export const METHOD_LABELS: Record<string, string> = {
  dcf: 'DCF (FCFF)',
  fcfe: 'FCFE DCF',
  ev_ebitda: 'EV/EBITDA',
  ev_sales: 'EV/Sales',
  pe: 'P/E',
  ddm: 'DDM',
  rim: 'RIM',
  pb: 'P/B',
  sotp: 'SOTP',
  nav: 'NAV',
}

export type ValuationLabel = 'Undervalued' | 'Fairly valued' | 'Overvalued'

/** price_vs_fair_value_pct > 0 means fair value exceeds price (undervalued). */
export function fvGapLabel(pct: number | null): ValuationLabel | null {
  if (pct == null) return null
  if (pct > 10) return 'Undervalued'
  if (pct < -10) return 'Overvalued'
  return 'Fairly valued'
}

export function fvGapColor(pct: number | null): string {
  if (pct == null) return 'text-slate-400'
  if (pct > 10) return 'text-green-400'
  if (pct > 0) return 'text-blue-400'
  if (pct > -10) return 'text-yellow-400'
  return 'text-red-400'
}

export function fvBadgeClass(pct: number | null): string {
  if (pct == null) return 'bg-slate-800 text-slate-300'
  if (pct > 10) return 'bg-green-900/40 text-green-400 border border-green-700'
  if (pct > 0) return 'bg-blue-900/40 text-blue-400 border border-blue-700'
  if (pct > -10) return 'bg-yellow-900/40 text-yellow-400 border border-yellow-700'
  return 'bg-red-900/40 text-red-400 border border-red-700'
}
```

- [ ] **Step 2: Delete the dead components**

```bash
git rm frontend/src/components/ScoreBadge.tsx \
       frontend/src/components/AgentCard.tsx \
       frontend/src/pages/JobStatus.tsx
```

- [ ] **Step 3: Replace `frontend/src/App.tsx`** (remove the JobStatus route)

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Progress from './pages/Progress'
import Results from './pages/Results'
import TickerDetail from './pages/TickerDetail'
import Database from './pages/Database'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/progress/:jobId" element={<Progress />} />
          <Route path="/results/:jobId" element={<Results />} />
          <Route path="/ticker/:jobId/:ticker" element={<TickerDetail />} />
          <Route path="/database" element={<Database />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
```

- [ ] **Step 4: Replace `frontend/src/pages/Home.tsx`** (drop the mode toggle; always stream)

```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const API = 'http://localhost:8000'

export default function Home() {
  const [tickers, setTickers] = useState('')
  const [useSheets, setUseSheets] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const handleAnalyse = async () => {
    setLoading(true)
    setError(null)
    try {
      const tickerList = tickers
        .split(/[\s,]+/)
        .map(t => t.trim().toUpperCase())
        .filter(Boolean)

      const body: Record<string, unknown> = {}
      if (tickerList.length > 0) body.tickers = tickerList
      if (useSheets) body.sheets_url = 'from_sheets'

      const res = await fetch(`${API}/api/analyse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()

      if (data.error) {
        setError(data.error)
      } else {
        navigate(`/progress/${data.job_id}`, { state: { total: data.total, invalid: data.invalid } })
      }
    } catch {
      setError('Failed to connect to backend. Is uvicorn running on port 8000?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-slate-100 mb-2">Fair Value Calculator</h1>
      <p className="text-slate-500 text-sm mb-8">
        Enter tickers (or load from Google Sheets) to compute an adaptive, sector-aware fair value for each. Free — no API costs.
      </p>

      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-6 space-y-4">
        <div>
          <label className="block text-xs text-slate-500 uppercase tracking-wide mb-2">
            Ticker Symbols (comma or space separated)
          </label>
          <textarea
            value={tickers}
            onChange={e => setTickers(e.target.value)}
            placeholder="AAPL, MSFT, GOOGL, NVDA..."
            className="w-full bg-[#0a0a0f] border border-[#1e1e2a] rounded px-3 py-2 text-slate-200 font-mono text-sm resize-none focus:outline-none focus:border-blue-700 h-24"
          />
        </div>

        <div className="flex items-center gap-3">
          <div className="flex-1 border-t border-[#1e1e2a]" />
          <span className="text-xs text-slate-600">OR</span>
          <div className="flex-1 border-t border-[#1e1e2a]" />
        </div>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={useSheets}
            onChange={e => setUseSheets(e.target.checked)}
            className="w-4 h-4 rounded border-slate-600 bg-[#0a0a0f]"
          />
          <span className="text-sm text-slate-300">Load tickers from Google Sheets</span>
        </label>

        {error && (
          <div className="text-red-400 text-sm bg-red-900/20 border border-red-900 rounded px-3 py-2">
            {error}
          </div>
        )}

        <button
          onClick={handleAnalyse}
          disabled={loading || (!tickers.trim() && !useSheets)}
          className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 text-white font-semibold py-3 rounded transition-colors text-sm uppercase tracking-wide"
        >
          {loading ? 'Submitting...' : 'Calculate Fair Values'}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Replace `frontend/src/pages/Progress.tsx`** (swap score column for fair value)

```tsx
import { useEffect } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useAnalysisStream } from '../hooks/useAnalysisStream'
import ProgressBar from '../components/ProgressBar'
import { fvGapColor } from '../types'
import { cn } from '../lib/utils'

export default function Progress() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { status, total, completed, failed, results, tickerStatuses, cancel } = useAnalysisStream(jobId ?? null)

  useEffect(() => {
    if (status === 'completed') {
      navigate(`/results/${jobId}`, { state: { results } })
    }
  }, [status])

  const allTickers = Object.keys(tickerStatuses)
  const displayTotal = total || (location.state?.total ?? 0)

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-slate-100">Calculating Fair Values</h1>
        <button
          onClick={cancel}
          className="text-sm text-red-400 hover:text-red-300 border border-red-900 px-3 py-1.5 rounded"
        >
          Cancel
        </button>
      </div>

      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-4 mb-6">
        <ProgressBar
          current={completed + failed}
          total={displayTotal}
          label={`Evaluated ${completed + failed} / ${displayTotal} tickers`}
        />
        <div className="flex gap-4 mt-2 text-xs text-slate-500">
          <span className="text-green-400">{completed} completed</span>
          {failed > 0 && <span className="text-red-400">{failed} failed</span>}
          {status === 'running' && <span className="text-blue-400 animate-pulse">Running...</span>}
        </div>
      </div>

      {allTickers.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-6">
          {allTickers.map(ticker => {
            const s = tickerStatuses[ticker]
            return (
              <span key={ticker} className={cn(
                'px-2 py-1 rounded text-xs font-mono border',
                s === 'done' ? 'border-green-800 text-green-400 bg-green-900/20' :
                s === 'failed' ? 'border-red-800 text-red-400 bg-red-900/20' :
                s === 'running' ? 'border-blue-800 text-blue-400 bg-blue-900/20 animate-pulse' :
                'border-slate-800 text-slate-500'
              )}>
                {ticker}
              </span>
            )
          })}
        </div>
      )}

      {results.length > 0 && (
        <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg overflow-hidden">
          <div className="text-xs text-slate-500 uppercase tracking-wide px-4 py-2 border-b border-[#1e1e2a]">
            Live Results
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e1e2a] text-xs text-slate-600">
                <th className="text-left py-2 px-4">Ticker</th>
                <th className="text-left py-2">Company</th>
                <th className="text-right py-2 px-2">Fair Value</th>
                <th className="text-right py-2 pr-4">vs Price</th>
              </tr>
            </thead>
            <tbody>
              {results.map(r => (
                <tr key={r.ticker} className="border-b border-[#1e1e2a] hover:bg-[#1a1a24]">
                  <td className="py-2 px-4 font-mono font-semibold text-blue-400">{r.ticker}</td>
                  <td className="py-2 text-slate-400 text-xs">{r.company_name || '—'}</td>
                  <td className="py-2 px-2 text-right font-mono text-slate-300">
                    {r.fair_value != null ? `$${r.fair_value.toFixed(2)}` : '—'}
                  </td>
                  <td className={`py-2 pr-4 text-right font-mono text-xs ${fvGapColor(r.price_vs_fair_value_pct)}`}>
                    {r.price_vs_fair_value_pct != null
                      ? `${r.price_vs_fair_value_pct > 0 ? '+' : ''}${r.price_vs_fair_value_pct.toFixed(1)}%`
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 6: Replace `frontend/src/pages/Results.tsx`**

```tsx
import { useState } from 'react'
import { useParams, useLocation, Link } from 'react-router-dom'
import type { TickerResult } from '../types'
import { fvGapColor, fvGapLabel } from '../types'

type SortKey = 'fair_value' | 'price_vs_fair_value_pct' | 'ticker'

export default function Results() {
  const { jobId } = useParams()
  const location = useLocation()
  const results: TickerResult[] = location.state?.results || []
  const [sortKey, setSortKey] = useState<SortKey>('price_vs_fair_value_pct')
  const [sortAsc, setSortAsc] = useState(false)

  const sorted = [...results].sort((a, b) => {
    const av = a[sortKey] ?? (sortAsc ? Infinity : -Infinity)
    const bv = b[sortKey] ?? (sortAsc ? Infinity : -Infinity)
    return sortAsc ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1)
  })

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(p => !p)
    else { setSortKey(key); setSortAsc(false) }
  }

  const exportCSV = () => {
    const headers = ['Ticker', 'Company', 'Stock Type', 'Fair Value', 'Price', 'FV Gap%', 'Verdict']
    const rows = sorted.map(r => [
      r.ticker, r.company_name, r.stock_type,
      r.fair_value, r.current_price, r.price_vs_fair_value_pct,
      fvGapLabel(r.price_vs_fair_value_pct),
    ])
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'fair_values.csv'; a.click()
  }

  if (!results.length) return (
    <div className="text-slate-500 text-center py-20">
      No results. <Link to="/" className="text-blue-400">Run a new calculation</Link>.
    </div>
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-slate-100">Fair Values — {results.length} tickers</h1>
        <button onClick={exportCSV} className="text-sm text-slate-400 hover:text-slate-200 border border-[#1e1e2a] px-3 py-1.5 rounded">
          Export CSV
        </button>
      </div>
      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1e1e2a] text-xs text-slate-500">
              <th className="text-left py-2 px-4 cursor-pointer hover:text-slate-300" onClick={() => toggleSort('ticker')}>Ticker</th>
              <th className="text-left py-2">Company</th>
              <th className="text-left py-2 px-2">Stock Type</th>
              <th className="text-right py-2 px-2 cursor-pointer hover:text-slate-300" onClick={() => toggleSort('fair_value')}>Fair Value</th>
              <th className="text-right py-2 px-2">Price</th>
              <th className="text-right py-2 px-4 cursor-pointer hover:text-slate-300" onClick={() => toggleSort('price_vs_fair_value_pct')}>FV Gap%</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(r => (
              <tr key={r.ticker} className="border-b border-[#1e1e2a] hover:bg-[#1a1a24]">
                <td className="py-2 px-4">
                  <Link to={`/ticker/${jobId}/${r.ticker}`} state={{ result: r }} className="font-mono font-semibold text-blue-400 hover:text-blue-300">
                    {r.ticker}
                  </Link>
                </td>
                <td className="py-2 text-slate-400 text-xs max-w-xs truncate">{r.company_name || '—'}</td>
                <td className="py-2 px-2 text-xs text-slate-500 font-mono">{r.stock_type || '—'}</td>
                <td className="py-2 px-2 text-right font-mono text-xs text-slate-300">
                  {r.fair_value != null ? `$${r.fair_value.toFixed(2)}` : '—'}
                </td>
                <td className="py-2 px-2 text-right font-mono text-xs text-slate-400">
                  {r.current_price != null ? `$${r.current_price.toFixed(2)}` : '—'}
                </td>
                <td className={`py-2 px-4 text-right font-mono text-xs ${fvGapColor(r.price_vs_fair_value_pct)}`}>
                  {r.price_vs_fair_value_pct != null ? `${r.price_vs_fair_value_pct > 0 ? '+' : ''}${r.price_vs_fair_value_pct.toFixed(1)}%` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

- [ ] **Step 7: Replace `frontend/src/pages/Database.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { TickerResult } from '../types'
import { fvGapColor } from '../types'

const API = 'http://localhost:8000'

export default function Database() {
  const [results, setResults] = useState<TickerResult[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API}/api/database`)
      const data = await res.json()
      if (data.error) setError(data.error)
      else setResults(data.results)
    } catch {
      setError('Failed to load database. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return (
    <div className="text-slate-500 text-center py-20 animate-pulse">Loading database...</div>
  )

  if (error) return (
    <div className="text-red-400 text-center py-20">{error}</div>
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-slate-100">Database — {results.length} records</h1>
        <button
          onClick={load}
          className="text-sm text-slate-400 hover:text-slate-200 border border-[#1e1e2a] px-3 py-1.5 rounded"
        >
          Refresh
        </button>
      </div>

      {results.length === 0 ? (
        <div className="text-slate-500 text-center py-20">
          No records yet. <Link to="/" className="text-blue-400">Run a calculation</Link>.
        </div>
      ) : (
        <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e1e2a] text-xs text-slate-500">
                <th className="text-left py-2 px-4">Ticker</th>
                <th className="text-left py-2">Company</th>
                <th className="text-left py-2 px-2">Stock Type</th>
                <th className="text-right py-2 px-2">Fair Value</th>
                <th className="text-right py-2 px-2">Price</th>
                <th className="text-right py-2 px-4">Gap%</th>
                <th className="text-right py-2 px-4">Evaluated</th>
              </tr>
            </thead>
            <tbody>
              {results.map(r => (
                <tr key={r.ticker} className="border-b border-[#1e1e2a] hover:bg-[#1a1a24]">
                  <td className="py-2 px-4">
                    <Link
                      to={`/ticker/db/${r.ticker}`}
                      state={{ result: r }}
                      className="font-mono font-semibold text-blue-400 hover:text-blue-300"
                    >
                      {r.ticker}
                    </Link>
                  </td>
                  <td className="py-2 text-slate-400 text-xs max-w-xs truncate">{r.company_name || '—'}</td>
                  <td className="py-2 px-2 text-xs text-slate-500 font-mono">{r.stock_type || '—'}</td>
                  <td className="py-2 px-2 text-right font-mono text-xs text-slate-300">
                    {r.fair_value != null ? `$${r.fair_value.toFixed(2)}` : '—'}
                  </td>
                  <td className="py-2 px-2 text-right font-mono text-xs text-slate-400">
                    {r.current_price != null ? `$${r.current_price.toFixed(2)}` : '—'}
                  </td>
                  <td className={`py-2 px-4 text-right font-mono text-xs ${fvGapColor(r.price_vs_fair_value_pct)}`}>
                    {r.price_vs_fair_value_pct != null
                      ? `${r.price_vs_fair_value_pct > 0 ? '+' : ''}${r.price_vs_fair_value_pct.toFixed(1)}%`
                      : '—'}
                  </td>
                  <td className="py-2 px-4 text-right text-xs text-slate-600">
                    {r.last_evaluated ? new Date(r.last_evaluated).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 8: Replace `frontend/src/components/FairValuePanel.tsx`** (render the new breakdown)

```tsx
import type { TickerResult, ModelBreakdown } from '../types'
import { METHOD_LABELS, fvGapColor } from '../types'

interface FairValuePanelProps {
  result: TickerResult
}

function money(v: number | null | undefined): string {
  return v != null ? `$${v.toFixed(2)}` : '—'
}

function ModelRow({ id, model }: { id: string; model: ModelBreakdown }) {
  const s = model.scenarios || { optimistic: null, realistic: null, pessimistic: null }
  return (
    <tr className="border-b border-[#1e1e2a]">
      <td className="py-2 pr-4 text-slate-400 text-sm">
        {METHOD_LABELS[id] ?? id}
        {model.is_approx && <span className="ml-1 text-[10px] text-amber-500 uppercase">approx</span>}
      </td>
      <td className="py-2 pr-4 text-right font-mono text-xs text-slate-500">{(model.weight * 100).toFixed(0)}%</td>
      <td className="py-2 pr-4 text-right font-mono text-blue-400">{money(model.fair_value)}</td>
      <td className="py-2 text-right font-mono text-xs text-slate-500">
        {money(s.pessimistic)} / {money(s.realistic)} / {money(s.optimistic)}
      </td>
    </tr>
  )
}

export default function FairValuePanel({ result }: FairValuePanelProps) {
  const entries = Object.entries(result.fair_value_breakdown || {})
  const gapPct = result.price_vs_fair_value_pct

  return (
    <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-4">
      <div className="text-xs text-slate-500 uppercase tracking-wide mb-3">
        Fair Value Breakdown{result.stock_type ? ` — ${result.stock_type}` : ''}
      </div>
      {entries.length === 0 ? (
        <div className="text-sm text-slate-500">No models resolved for this ticker.</div>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1e1e2a]">
              <th className="text-left py-1 text-xs text-slate-600 font-normal">Model</th>
              <th className="text-right py-1 text-xs text-slate-600 font-normal">Weight</th>
              <th className="text-right py-1 text-xs text-slate-600 font-normal">Fair Value</th>
              <th className="text-right py-1 text-xs text-slate-600 font-normal">Pess / Real / Opt</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([id, model]) => <ModelRow key={id} id={id} model={model} />)}
          </tbody>
        </table>
      )}
      <div className="mt-3 pt-3 border-t border-[#1e1e2a] flex justify-between items-center">
        <div>
          <div className="text-xs text-slate-500">Composite Fair Value</div>
          <div className="text-lg font-mono text-slate-200">{money(result.fair_value)}</div>
        </div>
        {gapPct != null && (
          <div className="text-right">
            <div className="text-xs text-slate-500">vs Current Price</div>
            <div className={`text-lg font-mono ${fvGapColor(gapPct)}`}>
              {gapPct > 0 ? '+' : ''}{gapPct.toFixed(1)}%
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 9: Replace `frontend/src/pages/TickerDetail.tsx`** (remove agent cards + score badge)

```tsx
import { useLocation, Link } from 'react-router-dom'
import type { TickerResult } from '../types'
import { fvBadgeClass, fvGapLabel } from '../types'
import FairValuePanel from '../components/FairValuePanel'

export default function TickerDetail() {
  const location = useLocation()
  const result: TickerResult | undefined = location.state?.result

  if (!result) {
    return (
      <div className="text-slate-500 text-center py-20">
        Result not found. <Link to="/" className="text-blue-400">Go home</Link>.
      </div>
    )
  }

  const verdict = fvGapLabel(result.price_vs_fair_value_pct)

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-4">
        <button
          onClick={() => window.history.back()}
          className="text-xs text-slate-500 hover:text-slate-300"
        >
          ← Back
        </button>
      </div>

      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold font-mono text-slate-100">{result.ticker}</h1>
            <p className="text-slate-400 mt-0.5">{result.company_name || '—'}</p>
            <p className="text-xs text-slate-600 mt-1">
              {result.stock_type || '—'}{result.last_evaluated ? ` · ${result.last_evaluated}` : ''}
            </p>
          </div>
          <div className="text-right">
            {verdict && (
              <span className={`rounded font-mono font-semibold inline-flex items-center px-3 py-1.5 text-sm ${fvBadgeClass(result.price_vs_fair_value_pct)}`}>
                {verdict}
              </span>
            )}
            <div className="text-slate-300 font-mono mt-2">
              FV {result.fair_value != null ? `$${result.fair_value.toFixed(2)}` : '—'}
            </div>
            {result.current_price != null && (
              <div className="text-slate-500 font-mono text-sm">Price ${result.current_price.toFixed(2)}</div>
            )}
          </div>
        </div>
      </div>

      <FairValuePanel result={result} />

      {result.errors.length > 0 && (
        <div className="mt-6 bg-red-900/10 border border-red-900/50 rounded-lg p-4">
          <p className="text-xs text-red-400 font-semibold mb-2">Errors</p>
          <ul className="text-xs text-red-300 space-y-1">
            {result.errors.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 10: Type-check and build**

Run: `cd frontend && npm run build`
Expected: `tsc -b` reports no errors and `vite build` completes. If `tsc` flags an unused import or a stale reference to `ScoreBadge`/`AgentCard`/`JobStatus`/`scoreTo*`, fix the offending file (those symbols no longer exist).

- [ ] **Step 11: Commit**

```bash
git add -A frontend
git commit -m "feat: convert frontend to fair-value UI; remove agent score components"
```

---

## Task 8: Integration verification, docs, and secret hygiene

Final pass: confirm the whole app runs FV-only, remove stale user-facing copy and any `ANTHROPIC_API_KEY` references, and flag the tracked `.env` secret for rotation.

**Files:**
- Modify (if they reference agents/AI/Anthropic or the removed Batch mode): `start.sh`, `frontend/README.md`, root `README.md` / `CLAUDE.md` if present.
- Inspect: `backend/.env` (tracked secret).

- [ ] **Step 1: Full backend suite**

Run: `cd backend && python -m pytest -v`
Expected: PASS, no collection errors. Confirm there is no remaining import of `anthropic`, `agents`, `batch_service`, `normalizer`, `aggregator`, `calculator_1/2`, or `gemini_fv`:

Run: `cd backend && python -c "import main; print('import OK')"`
Expected: `import OK`.

- [ ] **Step 2: Grep for dead references**

Use the editor/Grep to search the repo (excluding `node_modules`, `docs/`, and `.git`) for: `ANTHROPIC_API_KEY`, `anthropic`, `submit_batch_job`, `jobs_router`, `ScoreBadge`, `AgentCard`, `overall_final_score`, `blended_fair_value`.
Expected: no hits in `backend/*.py` (except the deleted-file history) or `frontend/src`. Fix any stragglers (e.g. an import that `tsc`/`pytest` didn't reach). The only acceptable hits are inside `docs/`.

- [ ] **Step 3: Update `start.sh` banner copy**

In `start.sh`, line 2, change:

```bash
echo "Starting Stock Evaluator..."
```

to:

```bash
echo "Starting Fair Value Calculator..."
```

(The launch commands themselves are unchanged — uvicorn + vite.)

- [ ] **Step 4: Update user-facing docs**

If `frontend/README.md` or a root `README.md`/`CLAUDE.md` describes the app as an "AI-powered" / "9 evaluation models" / "batch vs live cost" tool, replace that description with: "Free, unattended fair-value batch calculator — adaptive sector-aware valuation (8 stock types, up to 9 active models) over yfinance data, no API costs." Only edit files that exist; do not create new docs.

- [ ] **Step 5: Frontend build (final confirmation)**

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 6: Flag the tracked `.env` secret (manual, user action)**

`backend/.env` is tracked in git and historically held `ANTHROPIC_API_KEY`. The key is no longer read by any code, but it remains in git history. Surface this to the user in the task summary (do **not** auto-rotate or force-push): recommend they (a) remove `ANTHROPIC_API_KEY` from `backend/.env`, and (b) rotate that key in the Anthropic console since it was committed. This is a notification step, not a code change — leave the actual rotation to the user.

- [ ] **Step 7: Commit**

```bash
git add start.sh frontend/README.md README.md CLAUDE.md 2>/dev/null; git commit -m "docs: rebrand to fair-value calculator; drop AI/cost copy"
```

(Adjust the `git add` list to whichever of those files actually exist and changed.)

---

## Self-Review

**Spec coverage** (each spec section → task):
- Goal / free, no-cost → Tasks 1–6 (anthropic removed in Task 6).
- Decision #1 capped per-stock scenarios → Task 4 `build_scenarios` + tests.
- Decision #2 keep Sheets + SSE, drop Batch API → Task 6 (analysis.py streaming-only; jobs.py/batch_service deleted).
- Decision #3 spot multiples + caps → Task 3 `EV_EBITDA_CAP`/`EV_SALES_CAP` + cap tests.
- Decision #4 EV pick + weight fold → Task 4 `pick_ev_multiple` + 3 tests.
- Decision #5 fairvalue3 weights verbatim → Task 2 `_TYPE_WEIGHTS`.
- Decision #6 capex→CFO → Task 4 `dcf_cashflow_base` + 3 tests + `calc_dcf` cashflow override (Task 3).
- 10 models → Task 3 (all ten, incl. dormant FCFE).
- Data model reshape → Task 5 `models.py`.
- Sheets schema (16 cols, FCFE omitted) → Task 5 `sheets.py` + `test_sheets_row`.
- Backend delete list → Tasks 5–6.
- yahoo.py new fields → Task 1.
- Frontend delete/adjust list → Task 7.
- Error handling (yfinance fail, insufficient-data, per-ticker isolation, non-fatal sheets write) → Task 4 (`evaluate` failed path), Task 5 (`run` yfinance path), Task 6 (`run_batch` try/except + sheets append-to-errors).
- Testing plan (classifier, models, engine, golden/consistency, yahoo extend) → Tasks 1–5.
- Open item "confirm jobs.py serves only Batch API" → confirmed during planning (jobs.py imports only `batch_service`; deleted in Task 6).

**Placeholder scan:** No TBD/TODO/"handle edge cases"/"similar to" — every code step contains full code; every test step contains real assertions.

**Type consistency:** Result dict keys from `evaluate` (Task 4) exactly match reshaped `TickerResult` fields (Task 5) so `TickerResult(**data)` in `engine.run` is valid. Model-result dict shape (`scenarios`/`fair_value`/`weight`/`has_scenarios`) is consistent across Tasks 3–4. `_MODEL_COLS` (Task 5) and `METHOD_LABELS` (Task 7) use the same 9 visible model ids (FCFE omitted from both). Frontend `ModelBreakdown` matches the backend breakdown cell (`weight`, `fair_value`, `scenarios`, `is_approx`).

**Deviations from spec (intentional, noted):**
- `orchestrator/aggregator.py` is **deleted**, not edited — `engine.evaluate`/`run` construct `TickerResult` directly, making the aggregator redundant.
- `models.FairValueResult` is **deleted** (only ever consumed by removed code); spec named only `AgentResult`/`BatchJobFile`.
- Frontend uses `npm run build` (tsc + vite) as its test gate rather than vitest — vitest is not configured in this repo. Adding a vitest harness is out of scope; the type-checker covers the shape regressions the spec's "light smoke" tests targeted.
