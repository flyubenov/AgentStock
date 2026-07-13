# IREN-class Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop a single broken yfinance `info` field from tanking IREN's screener score (4.0 → 4.7) and denying it a fair value (none → ~$15), by preferring the financial statement over `info` for operating margin and revenue growth, and rerouting GAAP-profitable, cash-generative, capex-driven-negative-FCF names onto EV/EBITDA + P/E.

**Architecture:** Two independent fixes sharing one principle — *prefer the statement, fall back to `info`*. Fix #1 touches the screener (`metrics.py`, `models.py`, `scoring.py`); Fix #2 touches the valuation engine (`engine.py`) and its data service (`services/yahoo.py`). All changes are additive; existing logic (dynamic goodwill floor, positive-FCF reroute, statement-consistent EBITDA base) is untouched.

**Tech Stack:** Python 3.14, pydantic v2, pytest 9.x (with `pytest.approx`), `unittest.mock.patch`, yfinance (mocked in tests).

## Global Constraints

- Run all tests from the `backend/` directory — imports are top-level (`from screener...`, `from valuation...`, `from services...`, `from models import ...`).
- **Guiding principle:** statement-primary, `info` fallback. Never let a single `info` field override a healthy statement.
- **Reroute weights are `ev_ebitda 0.85 / pe 0.15`** for the *negative-FCF* branch added here. The pre-existing *positive-FCF* reroute stays `0.70 / 0.30` and MUST NOT be modified.
- **Units differ by pipeline and must not be mixed:** screener `ScreenerMetrics` fields are **percent** (`× 100`); valuation `build_scenarios` growth is a **fraction** (`0.20` = 20%). `revenue_growth_yoy` (screener) is percent; `revenue_growth_stmt`/`revenue_growth` (valuation) are fractions.
- `ScreenerMetrics` is a pydantic `BaseModel` that **rejects assignment to undeclared fields** — a new metric must be declared in `models.py` before `metrics.py` can set it.
- Commit after every task. Test files live in `backend/tests/`.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `backend/screener/metrics.py` | Compute `ScreenerMetrics` from statements + info | op_margin statement-primary; add `revenue_growth_yoy` |
| `backend/screener/models.py` | `ScreenerMetrics` schema | declare `revenue_growth_yoy` |
| `backend/screener/scoring.py` | Quality score, Rule of 40, branches | `_rule_of_40` statement-first growth chain |
| `backend/services/yahoo.py` | yfinance fetch + statement reconstruction | `_statement_revenue_yoy` helper; add `revenue` to rows; return `revenue_growth` |
| `backend/valuation/engine.py` | Valuation pipeline (`evaluate`, `build_scenarios`, `run`) | reroute gate; growth fallback; plumb `ocf_ttm` + `revenue_growth_stmt` |

Test files touched: `test_screener_metrics.py`, `test_screener_scoring.py`, `test_data_guards.py`, `test_engine.py`, `test_engine_run.py`.

**Task order (dependency-aware):** Fix #1 first (Tasks 1–4, self-contained screener change), then Fix #2 (Tasks 5–8). Within Fix #2, the pure helpers (5, 6) precede the `evaluate` gate (7), which precedes the `run` wiring + end-to-end (8).

---

### Task 1: Screener op-margin — statement-primary, info fallback (Fix #1a)

**Files:**
- Modify: `backend/screener/metrics.py` (the `m.op_margin = pct(info.get("operatingMargins"))` line, ~line 177, in the Section I block)
- Test: `backend/tests/test_screener_metrics.py`

**Interfaces:**
- Consumes: existing `_mk_inputs(**over)` test helper (builds `ScreenerInputs` with income Operating Income `[220,190,160,130]`, Total Revenue `[1000,900,800,700]`, and `info["operatingMargins"]`).
- Produces: `compute_metrics(inp).op_margin` now equals `Operating Income / Total Revenue × 100` from the statement when present; else `pct(info["operatingMargins"])`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_screener_metrics.py`:

```python
def test_op_margin_prefers_statement_over_broken_info():
    from screener.metrics import compute_metrics
    # IREN-shaped: info operatingMargins is broken (-64.5%) but the statement is
    # healthy (Operating Income 220 / Total Revenue 1000 = +22%). Trust the statement.
    m = compute_metrics(_mk_inputs(info={"operatingMargins": -0.645}))
    assert m.op_margin == pytest.approx(22.0, abs=0.1)


def test_op_margin_falls_back_to_info_without_statement():
    from screener.metrics import compute_metrics
    from screener.models import ScreenerInputs
    inp = ScreenerInputs(ticker="X",
                         info={"operatingMargins": 0.15, "totalRevenue": 1000.0},
                         income=None, balance=None, cashflow=None,
                         price_monthly=tuple(), risk_free=0.045)
    m = compute_metrics(inp)
    assert m.op_margin == pytest.approx(15.0, abs=0.1)
```

- [ ] **Step 2: Run the tests to verify the first one fails**

Run: `python -m pytest tests/test_screener_metrics.py::test_op_margin_prefers_statement_over_broken_info -v`
Expected: FAIL — current code returns `pct(-0.645)` = `-64.5`, not `22.0`.

- [ ] **Step 3: Write the implementation**

In `backend/screener/metrics.py`, replace this single line (in the Section I block):

```python
    m.op_margin = pct(info.get("operatingMargins"))
```

with:

```python
    oi = inc.latest("Operating Income") if inc is not None else None
    stmt_rev = inc.latest("Total Revenue") if inc is not None else None
    if oi is not None and stmt_rev:
        # Statement-primary: a single broken info['operatingMargins'] (e.g. IREN's
        # -64.5% vs a real +4.4%) must not override a healthy statement. Use the
        # statement's own revenue as the denominator for a consistent basis.
        m.op_margin = oi / stmt_rev * 100.0
    else:
        m.op_margin = pct(info.get("operatingMargins"))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_screener_metrics.py -v -k "op_margin"`
Expected: PASS (both new tests). Also confirm the existing `test_compute_section_i_iv_v` still passes (statement 220/1000 = 22.0 matches its `pytest.approx(22.0)`).

- [ ] **Step 5: Commit**

```bash
git add backend/screener/metrics.py backend/tests/test_screener_metrics.py
git commit -m "fix(screener): op_margin statement-primary, info fallback"
```

---

### Task 2: Screener `revenue_growth_yoy` metric (Fix #1b, part 1)

**Files:**
- Modify: `backend/screener/models.py` (`ScreenerMetrics`, in the "raw inputs used by cap rules / dual-check" block, next to `revenue_growth`)
- Modify: `backend/screener/metrics.py` (Section I `if inc is not None:` block, ~lines 169–171)
- Test: `backend/tests/test_screener_metrics.py`

**Interfaces:**
- Produces: `ScreenerMetrics.revenue_growth_yoy: float | None` — statement latest-FY vs prior-FY, in **percent**. `None` when fewer than two revenue points or the prior year is missing/zero. Consumed by Task 3 (`_rule_of_40`).

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_screener_metrics.py`:

```python
def test_revenue_growth_yoy_from_statement():
    from screener.metrics import compute_metrics
    # Two most-recent statement revenues: 1000 vs 900 -> +11.1% YoY (percent).
    m = compute_metrics(_mk_inputs())
    assert m.revenue_growth_yoy == pytest.approx((1000.0 / 900.0 - 1) * 100, abs=0.1)


def test_revenue_growth_yoy_none_with_one_point():
    from screener.metrics import compute_metrics
    inp = _mk_inputs()
    inp.income.rows["Total Revenue"] = [1000.0]  # only one year available
    m = compute_metrics(inp)
    assert m.revenue_growth_yoy is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_screener_metrics.py::test_revenue_growth_yoy_from_statement -v`
Expected: FAIL — `AttributeError`/validation: `ScreenerMetrics` has no `revenue_growth_yoy` field yet.

- [ ] **Step 3a: Declare the field in `models.py`**

In `backend/screener/models.py`, in the `# raw inputs used by cap rules / dual-check` block, add the field directly after `revenue_growth: float | None = None`:

```python
    revenue_growth: float | None = None
    revenue_growth_yoy: float | None = None   # statement latest-FY vs prior-FY (percent)
```

- [ ] **Step 3b: Compute it in `metrics.py`**

In `backend/screener/metrics.py`, extend the Section I `if inc is not None:` block that currently reads:

```python
    if inc is not None:
        m.revenue_cagr_3y = pct(series_cagr(inc.series("Total Revenue"), 3))
        m.eps_cagr_3y = pct(series_cagr(inc.series("Diluted EPS"), 3))
```

to:

```python
    if inc is not None:
        m.revenue_cagr_3y = pct(series_cagr(inc.series("Total Revenue"), 3))
        m.eps_cagr_3y = pct(series_cagr(inc.series("Diluted EPS"), 3))
        rev_series = inc.series("Total Revenue")
        if len(rev_series) >= 2 and rev_series[0] is not None and rev_series[1]:
            m.revenue_growth_yoy = (rev_series[0] / rev_series[1] - 1) * 100.0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_screener_metrics.py -v -k "revenue_growth_yoy or models_default"`
Expected: PASS. `test_models_default_to_none` still passes (new field defaults to `None`).

- [ ] **Step 5: Commit**

```bash
git add backend/screener/models.py backend/screener/metrics.py backend/tests/test_screener_metrics.py
git commit -m "feat(screener): add statement revenue_growth_yoy metric"
```

---

### Task 3: Rule-of-40 statement-first growth chain (Fix #1b, part 2)

**Files:**
- Modify: `backend/screener/scoring.py` (`_rule_of_40`, the `g = ...` growth-source line, ~line 282)
- Test: `backend/tests/test_screener_scoring.py`

**Interfaces:**
- Consumes: `ScreenerMetrics.revenue_growth_yoy` (Task 2), plus existing `revenue_growth`, `revenue_cagr_3y`, `op_margin`.
- Produces: `_rule_of_40(m)` growth term sourced as `revenue_growth_yoy` → `revenue_growth` → `revenue_cagr_3y` (first non-`None`), still capped by `RULE_OF_40_GROWTH_CAP = 100.0`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_screener_scoring.py`:

```python
def test_rule_of_40_prefers_statement_yoy_growth():
    from screener.scoring import _rule_of_40
    # Statement YoY wins over the broken info revenue_growth (IREN: 0.0 broken).
    m = ScreenerMetrics(revenue_growth_yoy=167.7, revenue_growth=0.0,
                        revenue_cagr_3y=50.0, op_margin=4.4)
    assert _rule_of_40(m) == pytest.approx(100.0 + 4.4)   # 167.7 capped at 100 + margin
    # Falls back to info revenue_growth when yoy is missing.
    m2 = ScreenerMetrics(revenue_growth=30.0, revenue_cagr_3y=50.0, op_margin=10.0)
    assert _rule_of_40(m2) == pytest.approx(40.0)
    # Falls back to 3y CAGR when both are missing.
    m3 = ScreenerMetrics(revenue_cagr_3y=25.0, op_margin=10.0)
    assert _rule_of_40(m3) == pytest.approx(35.0)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_screener_scoring.py::test_rule_of_40_prefers_statement_yoy_growth -v`
Expected: FAIL — current code uses `revenue_growth` (0.0) → `min(0,100) + 4.4 = 4.4`, not `104.4`.

- [ ] **Step 3: Write the implementation**

In `backend/screener/scoring.py`, in `_rule_of_40`, replace:

```python
    g = m.revenue_growth if m.revenue_growth is not None else m.revenue_cagr_3y
```

with (explicit `is not None` so a legitimate 0% is respected, not skipped as falsy):

```python
    # Statement YoY first (info revenue_growth can be broken, e.g. IREN's 0.0);
    # then info growth; then the 3y CAGR. Explicit None checks so a real 0% holds.
    if m.revenue_growth_yoy is not None:
        g = m.revenue_growth_yoy
    elif m.revenue_growth is not None:
        g = m.revenue_growth
    else:
        g = m.revenue_cagr_3y
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_screener_scoring.py -v -k "rule_of_40"`
Expected: PASS. The existing `test_rule_of_40_uses_operating_margin_and_caps_growth` still passes (it sets no `revenue_growth_yoy`, so the chain falls to `revenue_growth`).

- [ ] **Step 5: Commit**

```bash
git add backend/screener/scoring.py backend/tests/test_screener_scoring.py
git commit -m "fix(screener): Rule-of-40 prefers statement YoY growth"
```

---

### Task 4: Fix #1 end-to-end — IREN-shaped screener behavior

**Files:**
- Test: `backend/tests/test_screener_scoring.py`

**Interfaces:**
- Consumes: `compute_metrics` (Tasks 1–2) and `score` (Task 3). No production change — this task locks in the combined behavior.

- [ ] **Step 1: Write the end-to-end test**

Add to `backend/tests/test_screener_scoring.py`. Note the extra imports at the top of the file: it already imports `from screener.models import ScreenerMetrics`; add `StatementSeries, ScreenerInputs` and `compute_metrics`, `score` as needed inside the test.

```python
def _iren_inputs():
    from screener.models import StatementSeries, ScreenerInputs
    # IREN-shaped: broken info operatingMargins (-64.5%) & revenueGrowth (0.0), but
    # healthy statements. FCF deeply negative from a data-centre capex build-out.
    inc = StatementSeries(years=[2025, 2024, 2023, 2022], rows={
        "EBIT": [22.1e6, -30e6, -40e6, -20e6], "Tax Rate For Calcs": [0.21] * 4,
        "Net Income": [87e6, -170e6, -50e6, -10e6],
        "Total Revenue": [501e6, 187e6, 75e6, 30e6],
        "Interest Expense": [5e6, 4e6, 3e6, 2e6],
        "Gross Profit": [340e6, 120e6, 45e6, 18e6],
        "Operating Income": [22.1e6, -30e6, -40e6, -20e6],
        "Diluted EPS": [0.77, -1.5, -0.6, -0.2],
        "Diluted Average Shares": [200e6, 150e6, 120e6, 100e6]})
    bal = StatementSeries(years=[2025, 2024, 2023, 2022], rows={
        "Invested Capital": [2000e6, 1200e6, 800e6, 500e6],
        "Tangible Book Value": [1500e6, 900e6, 600e6, 400e6],
        "Net Debt": [-200e6, -100e6, 50e6, 100e6],
        "Ordinary Shares Number": [200e6, 150e6, 120e6, 100e6]})
    cf = StatementSeries(years=[2025, 2024, 2023, 2022], rows={
        "Free Cash Flow": [-1.13e9, -800e6, -400e6, -200e6],
        "Operating Cash Flow": [246e6, 50e6, -20e6, -10e6],
        "Capital Expenditure": [-1.37e9, -850e6, -380e6, -190e6],
        "Stock Based Compensation": [30e6] * 4,
        "Repurchase Of Capital Stock": [0] * 4, "Cash Dividends Paid": [0] * 4})
    info = {"symbol": "IREN", "shortName": "IREN Limited", "sector": "Technology",
            "beta": 2.5, "marketCap": 8e9, "totalDebt": 300e6, "totalCash": 500e6,
            "ebitda": 147e6, "operatingMargins": -0.645, "grossMargins": 0.68,
            "heldPercentInsiders": 0.10, "trailingPE": 53.0, "forwardPE": 30.0,
            "trailingPegRatio": 1.0, "priceToSalesTrailing12Months": 16.0,
            "enterpriseValue": 7.8e9, "revenueGrowth": 0.0, "totalRevenue": 501e6,
            "freeCashflow": -1.13e9}
    return ScreenerInputs(ticker="IREN", info=info, income=inc, balance=bal,
                          cashflow=cf, price_monthly=tuple(), risk_free=0.045)


def test_iren_shaped_profitable_capex_investor_not_pre_profit():
    from screener.metrics import compute_metrics
    from screener.scoring import score
    inp = _iren_inputs()
    m = compute_metrics(inp)
    # Statement wins over both broken info fields.
    assert m.op_margin == pytest.approx(22.1e6 / 501e6 * 100, abs=0.5)   # not -64.5
    assert m.revenue_growth_yoy == pytest.approx((501.0 / 187.0 - 1) * 100, abs=1.0)
    q, _, profile, bd = score(m, inp.info["sector"])
    # Positive op margin -> NOT routed through the operating-loss / pre-profit branch.
    assert bd["pre_profit"] is None
    # Capex-eaten FCF metrics excluded as deliberate reinvestment (AMZN-style).
    assert "capex_adjustment" in bd
    # Clear of the reported 4.0 hole (exact value not asserted — see unit tests).
    assert q > 4.0
```

- [ ] **Step 2: Run the test**

Run: `python -m pytest tests/test_screener_scoring.py::test_iren_shaped_profitable_capex_investor_not_pre_profit -v`
Expected: PASS (Tasks 1–3 already implemented). If it fails, the failure pinpoints which fix regressed.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_screener_scoring.py
git commit -m "test(screener): IREN-shaped capex investor lifts out of pre-profit branch"
```

---

### Task 5: `_statement_revenue_yoy` helper + revenue in reconstruction rows (Fix #2, part 1)

**Files:**
- Modify: `backend/services/yahoo.py` (add `_statement_revenue_yoy` after `latest_statement_ebitda`; add `"revenue"` to each row in `_fetch_ev_ebitda_history_sync`; add `"revenue_growth"` to its return dict)
- Test: `backend/tests/test_data_guards.py`

**Interfaces:**
- Produces: `_statement_revenue_yoy(rows: list[dict]) -> float | None` — YoY revenue growth as a **fraction** from `rows[0]["revenue"] / rows[1]["revenue"] - 1` (rows are most-recent-first). `None` when `< 2` rows or prior revenue missing/`<= 0`.
- Produces: `_fetch_ev_ebitda_history_sync` / `fetch_ev_ebitda_history` return dict gains key `"revenue_growth"` (fraction or `None`). Consumed by Task 8 (`run` plumbing).

Design note: the helper takes `rows` (not the raw yfinance DataFrame) to match `latest_statement_ebitda(rows)` and to be unit-testable without pandas. Each row already carries the reconstruction fields; we add `revenue` alongside them.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_data_guards.py`, extend the import and add tests:

```python
from services.yahoo import (
    ev_ebitda_history_median, latest_statement_ebitda, statements_predate_split,
    _statement_revenue_yoy,
)


def test_statement_revenue_yoy_latest_over_prior():
    # Rows most-recent-first: 501 vs 187 -> +167.9% (fraction 1.679).
    rows = [{"revenue": 501e6}, {"revenue": 187e6}, {"revenue": 75e6}]
    assert _statement_revenue_yoy(rows) == pytest.approx(501e6 / 187e6 - 1)


def test_statement_revenue_yoy_none_when_insufficient():
    assert _statement_revenue_yoy([{"revenue": 100.0}]) is None
    assert _statement_revenue_yoy([{"revenue": 100.0}, {"revenue": None}]) is None
    assert _statement_revenue_yoy([{"revenue": 100.0}, {"revenue": 0.0}]) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_data_guards.py -v -k "statement_revenue_yoy"`
Expected: FAIL at import — `ImportError: cannot import name '_statement_revenue_yoy'`.

- [ ] **Step 3a: Add the helper in `yahoo.py`**

In `backend/services/yahoo.py`, immediately after the `latest_statement_ebitda` function, add:

```python
def _statement_revenue_yoy(rows: list[dict]) -> float | None:
    """Year-over-year revenue growth (as a fraction) from the two most-recent
    reconstruction rows (most-recent-first). None when fewer than two rows or the
    prior-year revenue is missing/non-positive. Feeds build_scenarios as a growth
    fallback when yfinance info['revenueGrowth'] is broken (statement-primary)."""
    if len(rows) < 2:
        return None
    latest = rows[0].get("revenue")
    prior = rows[1].get("revenue")
    if latest is None or not prior or prior <= 0:
        return None
    return latest / prior - 1.0
```

- [ ] **Step 3b: Carry revenue into each row and return the growth**

In `_fetch_ev_ebitda_history_sync`, in the `for col in ist.columns:` loop, add a `revenue` read next to the existing `_cell` reads and include it in the appended row:

```python
            ebitda = _cell(ist, "EBITDA", col)
            shares = _cell(ist, "Diluted Average Shares", col)
            revenue = _cell(ist, "Total Revenue", col)
            debt = _cell(bs, "Total Debt", col) if col in bs.columns else None
            cash = _cell(bs, "Cash Cash Equivalents And Short Term Investments", col) if col in bs.columns else None
            net_debt = (debt or 0) - (cash or 0) if (debt is not None or cash is not None) else 0
            rows.append({"avg_price": float(avg_close[year]), "shares": shares,
                         "ebitda": ebitda, "net_debt": net_debt, "revenue": revenue})
```

Then change the success return from:

```python
        return {"multiple": median, "ebitda": latest_statement_ebitda(rows)}
```

to:

```python
        return {"multiple": median, "ebitda": latest_statement_ebitda(rows),
                "revenue_growth": _statement_revenue_yoy(rows)}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_data_guards.py -v`
Expected: PASS (new `_statement_revenue_yoy` tests plus all existing guards). Existing median/ebitda tests are unaffected — they build rows without `revenue`, and the helper only reads `revenue` when called.

- [ ] **Step 5: Commit**

```bash
git add backend/services/yahoo.py backend/tests/test_data_guards.py
git commit -m "feat(valuation): statement revenue-growth from EV/EBITDA reconstruction"
```

---

### Task 6: `build_scenarios` statement-growth fallback (Fix #2, part 2)

**Files:**
- Modify: `backend/valuation/engine.py` (`build_scenarios`, the `raw = ...` fallback line, ~line 60)
- Test: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `fin["revenue_growth_stmt"]` (a fraction; plumbed in Task 8).
- Produces: `build_scenarios` growth source becomes `earnings_growth` → `revenue_growth` → `revenue_growth_stmt` → `0.07`, still bounded by the existing `min(..., 0.20)` cap.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_engine.py`:

```python
def test_build_scenarios_statement_growth_fallback_when_info_broken():
    # info revenueGrowth is the broken 0 and earnings_growth is None, so the
    # statement fallback supplies growth. IREN: +167.7% -> capped at 20%.
    s = engine.build_scenarios({"revenue_growth": 0, "earnings_growth": None,
                                "revenue_growth_stmt": 1.677})
    assert s["realistic"] == 0.20


def test_build_scenarios_statement_growth_ignored_when_info_valid():
    # A valid nonzero info growth must win; the statement fallback never fires.
    s = engine.build_scenarios({"revenue_growth": 0.05, "earnings_growth": None,
                                "revenue_growth_stmt": 1.677})
    assert s["realistic"] == pytest.approx(0.05)
```

- [ ] **Step 2: Run the tests to verify the first fails**

Run: `python -m pytest tests/test_engine.py::test_build_scenarios_statement_growth_fallback_when_info_broken -v`
Expected: FAIL — current fallback yields `0.07` (base `0.07`), not `0.20`.

- [ ] **Step 3: Write the implementation**

In `backend/valuation/engine.py`, in `build_scenarios`, replace:

```python
        raw = fin.get("earnings_growth") or fin.get("revenue_growth") or 0.07
```

with:

```python
        raw = (fin.get("earnings_growth") or fin.get("revenue_growth")
               or fin.get("revenue_growth_stmt") or 0.07)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -v -k "build_scenarios"`
Expected: PASS (both new tests plus all existing `build_scenarios` tests — none set `revenue_growth_stmt`, so their behavior is unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/engine.py backend/tests/test_engine.py
git commit -m "fix(valuation): statement revenue-growth fallback in build_scenarios"
```

---

### Task 7: Reroute gate for profitable negative-FCF names (Fix #2, part 3)

**Files:**
- Modify: `backend/valuation/engine.py` (`evaluate`, the pre-profit guard block, ~lines 98–115)
- Test: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `fin["fcf_ttm"]`, `fin["revenue_ttm"]`, `fin["ebitda_ttm"]`, `fin["ocf_ttm"]` (Task 8) or `fin["operating_cashflow"]` (info fallback).
- Produces: when a DCF-anchored name has `fcf_ttm/revenue_ttm < FCF_MARGIN_FLOOR` **and** `ebitda_ttm > 0` **and** `ocf_ttm > 0`, `evaluate` reroutes to `ev_ebitda 0.85 / pe 0.15` instead of declining as `PRE_PROFIT`. Otherwise the existing decline stands.

- [ ] **Step 1: Write the tests (one new driver, two guards, one modified existing)**

In `backend/tests/test_engine.py`, first **modify** the existing `test_evaluate_pre_profit_guard_fires` so its declined case is a genuine burn (OCF < 0). Replace the whole function with:

```python
def test_evaluate_pre_profit_guard_fires():
    # Deeply FCF-negative AND operations consume cash (OCF < 0) -> genuine burn,
    # declined as PRE_PROFIT (not a capex investor).
    fin = _large_cap_fin(market_cap=16_000_000_000, fcf_ttm=-1_130_000_000,
                         revenue_ttm=757_000_000, operating_cashflow=-200_000_000)
    result = engine.evaluate(fin)
    assert result["status"] == "failed"
    assert result["stock_type"] == "PRE_PROFIT"
    assert result["fair_value"] is None
    assert result["price_vs_fair_value_pct"] is None
    assert "Negative free cash flow" in result["errors"][0]
```

Then **add** the reroute driver and the EBITDA-guard:

```python
def test_evaluate_negative_fcf_reroutes_when_cash_generative():
    # IREN pattern: FCF deeply negative from a capex build, but EBITDA > 0 and OCF > 0
    # (operations self-fund) -> reroute onto EV/EBITDA (0.85) + P/E (0.15), not decline.
    fin = _large_cap_fin(market_cap=16_000_000_000, fcf_ttm=-1_130_000_000,
                         revenue_ttm=757_000_000, operating_cashflow=246_000_000,
                         ebitda_ttm=286_000_000, eps_ttm=0.77, forward_eps=0.90)
    result = engine.evaluate(fin)
    assert result["status"] == "completed"
    assert result["stock_type"] == "MID_CAP"
    assert "dcf" not in result["fair_value_breakdown"]
    assert "ev_ebitda" in result["fair_value_breakdown"]
    assert result["fair_value_breakdown"]["ev_ebitda"]["weight"] == pytest.approx(0.85)
    if "pe" in result["fair_value_breakdown"]:
        assert result["fair_value_breakdown"]["pe"]["weight"] == pytest.approx(0.15)


def test_evaluate_negative_fcf_declines_when_ebitda_nonpositive():
    # OCF > 0 but EBITDA <= 0 -> no operating-profit anchor for a multiple -> decline.
    fin = _large_cap_fin(market_cap=16_000_000_000, fcf_ttm=-1_130_000_000,
                         revenue_ttm=757_000_000, operating_cashflow=246_000_000,
                         ebitda_ttm=-50_000_000)
    result = engine.evaluate(fin)
    assert result["status"] == "failed"
    assert result["stock_type"] == "PRE_PROFIT"
```

- [ ] **Step 2: Run the tests to verify the reroute driver fails**

Run: `python -m pytest tests/test_engine.py::test_evaluate_negative_fcf_reroutes_when_cash_generative -v`
Expected: FAIL — current code declines (status `failed`, stock_type `PRE_PROFIT`), so `status == "completed"` fails.

- [ ] **Step 3: Write the implementation**

In `backend/valuation/engine.py`, replace the current pre-profit guard block:

```python
    fcf_ttm = fin.get("fcf_ttm")
    revenue_ttm = fin.get("revenue_ttm")
    if (weights.get("dcf", 0) > 0 and fcf_ttm is not None and revenue_ttm
            and fcf_ttm / revenue_ttm < FCF_MARGIN_FLOOR):
        return {
            "ticker": fin.get("ticker") or "",
            "company_name": fin.get("company_name"),
            "current_price": fin.get("current_price"),
            "last_evaluated": None, "stock_type": "PRE_PROFIT",
            "fair_value": None, "price_vs_fair_value_pct": None,
            "fair_value_breakdown": {},
            "status": "failed",
            "errors": ["Negative free cash flow (pre-profit / heavy investment "
                       "phase) — trailing financials don't support a reliable valuation"],
        }
```

with:

```python
    fcf_ttm = fin.get("fcf_ttm")
    revenue_ttm = fin.get("revenue_ttm")
    ocf_ttm = fin.get("ocf_ttm")
    if ocf_ttm is None:
        ocf_ttm = fin.get("operating_cashflow")   # info fallback
    ebitda_ttm = fin.get("ebitda_ttm") or 0
    if (weights.get("dcf", 0) > 0 and fcf_ttm is not None and revenue_ttm
            and fcf_ttm / revenue_ttm < FCF_MARGIN_FLOOR):
        if ebitda_ttm > 0 and ocf_ttm is not None and ocf_ttm > 0:
            # Capex-distorted, negative-FCF variant: operations generate cash (OCF > 0)
            # and EBITDA is valuable, so deeply negative FCF is a capex/investment
            # choice, not a burn. Value on EV/EBITDA + P/E, leaning harder on the
            # multiple than the positive-FCF case (0.85/0.15) because these names carry
            # accrual-distorted earnings (e.g. IREN's net income is inflated by non-cash
            # bitcoin fair-value gains) — so EPS is excluded from the gate and trusted
            # for only 15% of the value.
            weights = {mid: 0.0 for mid in m.ALL_METHODS}
            weights["ev_ebitda"], weights["pe"] = 0.85, 0.15
        else:
            return {
                "ticker": fin.get("ticker") or "",
                "company_name": fin.get("company_name"),
                "current_price": fin.get("current_price"),
                "last_evaluated": None, "stock_type": "PRE_PROFIT",
                "fair_value": None, "price_vs_fair_value_pct": None,
                "fair_value_breakdown": {},
                "status": "failed",
                "errors": ["Negative free cash flow (pre-profit / heavy investment "
                           "phase) — trailing financials don't support a reliable valuation"],
            }
```

Leave the existing positive-FCF reroute block that follows (its own `ebitda_ttm = fin.get("ebitda_ttm") or 0` and the `fcf_ttm >= 0` guard) unchanged — a rerouted negative-FCF name has `weights["dcf"] == 0` and `fcf_ttm < 0`, so that block cannot re-fire.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -v`
Expected: PASS — all four target tests plus every existing `evaluate`/reroute test (`test_evaluate_pre_profit_guard_not_fired_when_fcf_positive`, `test_evaluate_pre_profit_guard_skips_financial`, `test_evaluate_capex_distorted_positive_fcf_reroutes_off_dcf`, `test_evaluate_capex_reroute_not_fired_for_healthy_conversion`).

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/engine.py backend/tests/test_engine.py
git commit -m "feat(valuation): reroute profitable negative-FCF capex investors to EV/EBITDA+PE"
```

---

### Task 8: `run` plumbing + IREN end-to-end (Fix #2, part 4)

**Files:**
- Modify: `backend/valuation/engine.py` (`run`, after the cashflow fetch and in the `hist` block, ~lines 225–237)
- Test: `backend/tests/test_engine_run.py`

**Interfaces:**
- Consumes: `fetch_ticker_cashflow` (returns dict with `operating_cash_flow`) and `fetch_ev_ebitda_history` (returns dict with `revenue_growth` from Task 5).
- Produces: `fin["ocf_ttm"]` (statement OCF) and `fin["revenue_growth_stmt"]` (statement growth fraction) available to `evaluate` (Task 7) and `build_scenarios` (Task 6).

- [ ] **Step 1: Write the failing end-to-end test**

Add to `backend/tests/test_engine_run.py`:

```python
_IREN_INFO = {
    "symbol": "IREN", "shortName": "IREN Limited", "currentPrice": 41.14,
    "marketCap": 8_000_000_000, "sharesOutstanding": 200_000_000,
    "freeCashflow": -1_130_000_000, "operatingCashflow": 246_000_000,
    "ebitda": 147_000_000, "totalRevenue": 501_000_000,
    "trailingEps": 0.77, "forwardEps": 0.90, "bookValue": 7.5,
    "trailingPE": 53.0, "forwardPE": 30.0, "revenueGrowth": 0.0,
    "enterpriseToEbitda": 20.0, "enterpriseToRevenue": 16.0,
    "sector": "Technology", "industry": "Software",
    "totalDebt": 300_000_000, "totalCash": 500_000_000,
}
_IREN_CF = {"free_cash_flow": -1_130_000_000, "operating_cash_flow": 246_000_000,
            "capital_expenditure": -1_370_000_000}
_IREN_HIST = {"multiple": 16.8, "ebitda": 286_000_000, "revenue_growth": 1.677}


@pytest.mark.asyncio
async def test_run_iren_reroutes_to_completed_fair_value():
    with patch("valuation.engine.fetch_ticker_info", return_value=_IREN_INFO), \
         patch("valuation.engine.fetch_ticker_cashflow", return_value=_IREN_CF), \
         patch("valuation.engine.fetch_ev_ebitda_history", return_value=_IREN_HIST):
        result = await engine.run("IREN")
    assert result.status == "completed"
    assert result.stock_type == "MID_CAP"
    assert result.fair_value is not None
    assert 0 < result.fair_value < _IREN_INFO["currentPrice"]   # valued & expensive (~-63%)
    assert "ev_ebitda" in result.fair_value_breakdown
    assert "dcf" not in result.fair_value_breakdown
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/test_engine_run.py::test_run_iren_reroutes_to_completed_fair_value -v`
Expected: FAIL — without the `run` plumbing, `fin["ocf_ttm"]` is absent and `fin.get("operating_cashflow")` (from `extract_financials`) is `+246M`, so the reroute would actually fire off the info fallback; but `revenue_growth_stmt` is absent, so growth defaults to `0.07` and the FV is understated (~$9). The assertion most likely to fail first is the plumbing wiring; if the reroute happens to fire, the test still guards the growth path. (Either way it must go green only after Step 3.)

- [ ] **Step 3: Write the implementation**

In `backend/valuation/engine.py`, in `run`, after the existing `real_fcf` block:

```python
    cashflow = await fetch_ticker_cashflow(ticker)
    rf = real_fcf(cashflow, fin.get("fcf_ttm"))
    if rf is not None:
        fin["fcf_ttm"] = rf
```

add statement-OCF plumbing:

```python
    if cashflow:
        ocf = cashflow.get("operating_cash_flow")
        if ocf is not None:
            fin["ocf_ttm"] = ocf   # statement-primary; gate falls back to info operating_cashflow
```

Then extend the `hist` block from:

```python
    hist = await fetch_ev_ebitda_history(ticker)
    if hist is not None:
        fin["ev_ebitda_hist"] = hist["multiple"]
        # Project the statement EBITDA the median was built from, not info['ebitda']
        # (they can differ ~2x — content amortization at NFLX).
        fin["ev_ebitda_hist_base"] = hist["ebitda"]
```

to also plumb the statement growth:

```python
    hist = await fetch_ev_ebitda_history(ticker)
    if hist is not None:
        fin["ev_ebitda_hist"] = hist["multiple"]
        # Project the statement EBITDA the median was built from, not info['ebitda']
        # (they can differ ~2x — content amortization at NFLX).
        fin["ev_ebitda_hist_base"] = hist["ebitda"]
        if hist.get("revenue_growth") is not None:
            fin["revenue_growth_stmt"] = hist["revenue_growth"]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_engine_run.py -v`
Expected: PASS — the IREN reroute test plus the existing `test_run_returns_completed_ticker_result`, `test_run_yfinance_failure_is_failed`, `test_run_uses_real_fcf_from_cashflow` (the new `hist.get("revenue_growth")` guard is `None`-safe when a mock omits the key, and `cashflow.get("operating_cash_flow")` is `None`-safe when the mock passes `None` or `cashflow` is `None`).

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/engine.py backend/tests/test_engine_run.py
git commit -m "feat(valuation): plumb statement OCF + revenue-growth into run(); IREN end-to-end"
```

---

### Task 9: Full suite green

**Files:** none (verification only).

- [ ] **Step 1: Run the entire backend suite**

Run: `python -m pytest -q`  (from `backend/`)
Expected: all tests pass, no errors. Investigate and fix any regression before considering the plan complete.

- [ ] **Step 2: Final commit if any fixups were needed**

```bash
git add -A
git commit -m "test: green suite for IREN op-margin + capex reroute"
```

---

## Self-Review

**1. Spec coverage:**
- Fix #1a (op_margin statement-primary) → Task 1. ✓
- Fix #1b field `revenue_growth_yoy` (models + metrics) → Task 2. ✓
- Fix #1b `_rule_of_40` chain → Task 3. ✓
- Fix #1 end-to-end (score lifts, no pre-profit, capex_adjustment fires) → Task 4. ✓
- Fix #2a reroute gate (EBITDA>0 & OCF>0, 0.85/0.15) → Task 7. ✓
- Fix #2b `_statement_revenue_yoy` + return key → Task 5; `build_scenarios` fallback → Task 6; `run` plumbing → Task 8. ✓
- Spec "Testing" bullets: op_margin source ✓ (T1); revenue_growth_yoy ✓ (T2); `_rule_of_40` preference ✓ (T3); screener end-to-end ✓ (T4); `_statement_revenue_yoy` ✓ (T5); reroute fires/weights ✓ (T7); still declines OCF≤0 / EBITDA≤0 ✓ (T7); build_scenarios statement-only-when-info-falsy ✓ (T6); engine end-to-end ✓ (T8); full pytest green ✓ (T9).

**2. Placeholder scan:** No "TBD"/"handle edge cases"/"similar to"/"write tests for the above" — every code and test step contains complete code. ✓

**3. Type/name consistency:**
- `revenue_growth_yoy` (percent) declared in `models.py` (T2), set in `metrics.py` (T2), read in `scoring.py` (T3) — same name throughout. ✓
- `revenue_growth_stmt` (fraction) returned as `revenue_growth` by the service (T5), renamed to `fin["revenue_growth_stmt"]` in `run` (T8), read in `build_scenarios` (T6) — chain consistent. ✓
- `ocf_ttm` set in `run` (T8), read in `evaluate` with `operating_cashflow` fallback (T7) — consistent. ✓
- Reroute weights `0.85 / 0.15` identical in the implementation (T7) and the asserting test (T7). ✓
- Units kept distinct: screener percent vs valuation fraction, called out in Global Constraints and each task. ✓

**Deviation from spec (noted):** `_statement_revenue_yoy` takes `rows: list[dict]` rather than the raw income-statement DataFrame shown in the spec snippet — same data, but consistent with `latest_statement_ebitda(rows)` and unit-testable without pandas. Behavior (two most-recent statement revenues → YoY fraction) is identical.
