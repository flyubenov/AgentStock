# Moat Score Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pure durability-of-economic-profit **Moat Score** (0–100) as a fourth rating, computed as a pure scoring function over the metrics the Screener already builds (zero extra yfinance I/O), and shown as a sortable/filterable column next to Quality in the Database grid.

**Architecture:** A new `backend/moat/` package holds the durability math (`metrics.py`) and the 40/50/10 scoring model (`scoring.py`). `screener/metrics.py` is extended to *store* per-year series it already computes (ROIC, ex-goodwill ROIC, ROTE, gross/op margins). `screener/engine.py` calls `moat.scoring.score(metrics, profile)` right after the quality score, attaching `moat_score` + `moat_breakdown` to `ScreenerResult`. Persistence mirrors the existing quality-score pattern exactly: written to the Screener tab and mirrored into a new Database column (S). The React Database grid gains a Moat column following the existing Quality/R-R column pattern.

**Tech Stack:** Python 3.14, Pydantic v2, pytest (backend); React + TypeScript + Vite + Tailwind (frontend); Google Sheets as the persistence store.

**Spec:** `docs/superpowers/specs/2026-08-24-moat-score-design.md` (read it alongside this plan — the plan argues from it).

## Global Constraints

- **Zero additional yfinance round-trips.** Moat consumes the in-memory `ScreenerMetrics` the Screener pipeline already builds. No new fetch helpers, no new network calls.
- **Existing scores must stay byte-identical.** Quality, Fair-Value, and Risk-Reward outputs must not change. New fields default to `None`/`[]` and are read by nothing in the existing pipelines; the persisted metric-column allowlist (`_METRIC_COLS`) is not touched, so no schema drift there.
- **Moat rides the Screener pipeline** — it is a pure function, never its own fetch pipeline.
- **All bands / thresholds are module-level constants** in `moat/scoring.py`, so the calibration task (Task 10) can sweep them without touching logic.
- **User decisions locked in:** (1a) financials use the **ROTE − FINANCIAL_COE** return axis (deliberate, not inherited from Quality); (2a) the §3.1 bands ship as defaults and are tuned via the sweep in Task 10 — do **not** invent different band values in earlier tasks.
- **Score scale is 0–100** (stored and displayed). Numeric only — no Wide/Narrow/Strong rating labels anywhere.
- **Coverage floor:** `MOAT_MIN_YEARS = 3` observations in the return series AND at least `MOAT_MIN_PILLARS = 3` scored pillar-metrics, else `moat_score = None` (blank column).
- Run backend tests from `backend/` with `python -m pytest`. The full suite is **520 tests** today and must stay green.

---

## File Structure

**Backend — new:**
- `backend/moat/__init__.py` — package marker.
- `backend/moat/metrics.py` — pure statistics helpers over series (persistence fraction, coefficient of variation, population stdev, mean).
- `backend/moat/scoring.py` — the 40/50/10 model: bands, the economic-profit gate, distortion/exclusion routing, renormalization, coverage floor. Public `score(m, profile) -> (float | None, dict)`.

**Backend — modified:**
- `backend/screener/models.py` — add the stored series + `rote_5y_avg` + `gross_margin_trajectory` to `ScreenerMetrics`; add `moat_score` + `moat_breakdown` to `ScreenerResult`.
- `backend/screener/metrics.py` — populate the new series (most are one line from data already looped over).
- `backend/screener/engine.py` — call `moat.scoring.score(...)` after `score(...)`, attach results to both `ScreenerResult` return paths.
- `backend/services/screener_sheets.py` — persist `Moat Score` + `Moat Breakdown` as two trailing columns on the Screener tab; mirror `moat_score` into Database column S.
- `backend/services/sheets.py` — extend the Database read range `A:R` → `A:S` and read `moat_score` from column S (index 18).
- `backend/models.py` — add `moat_score` to `DatabaseRow`.

**Frontend — modified:**
- `frontend/src/types.ts` — add `moat_score?` to `TickerResult`; add a `moatScoreColor(...)` helper.
- `frontend/src/pages/Database.tsx` — add a **Moat** column immediately after Quality: sortable + range-filterable, following the existing Quality column exactly.

**Tests — new:**
- `backend/tests/test_moat_metrics.py`
- `backend/tests/test_moat_scoring.py`

**Tests — extended:**
- `backend/tests/test_screener_metrics.py` (new series stored)
- `backend/tests/test_screener_engine.py` (engine attaches moat)
- `backend/tests/test_screener_sheets.py` (persistence roundtrip + mirror)

---

## Task 1: Store per-year series on `ScreenerMetrics`

Add the fields the Moat module needs, and populate them in `compute_metrics`. All are derived from statement rows the function already reads, so this adds no fetches.

**Files:**
- Modify: `backend/screener/models.py:42-93` (the `ScreenerMetrics` class)
- Modify: `backend/screener/metrics.py:123-262` (`compute_metrics`)
- Test: `backend/tests/test_screener_metrics.py`

**Interfaces:**
- Produces (new `ScreenerMetrics` fields, all percent-scaled to match `roic_5y_avg`):
  - `roic_series: list[float]` — per-year ROIC (%).
  - `roic_series_ex_goodwill: list[float]` — per-year ROIC on tangible invested capital (%).
  - `rote_series: list[float]` — per-year Net Income ÷ Tangible Book Value (%).
  - `rote_5y_avg: float | None` — mean of `rote_series` (%).
  - `gross_margin_series: list[float]` — per-year Gross Profit ÷ Total Revenue (%).
  - `op_margin_series: list[float]` — per-year Operating Income ÷ Total Revenue (%).
  - `gross_margin_trajectory: float | None` — latest − oldest gross margin (pp).

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_screener_metrics.py`. This reuses the module's existing `_full_inputs()` helper if present; if the test file has no such helper, build inputs inline the same way `test_screener_engine.py::_full_inputs` does. Assert the series are stored, percent-scaled, and ordered latest-first (matching `roic_5y_avg`'s basis).

```python
from screener.metrics import compute_metrics
from screener.models import ScreenerInputs, StatementSeries


def _series(rows):
    return StatementSeries(years=[2025, 2024, 2023, 2022], rows=rows)


def _inputs_for_series():
    income = _series({
        "EBIT": [200, 180, 150, 120], "Tax Rate For Calcs": [0.21] * 4,
        "Net Income": [160, 150, 130, 100], "Total Revenue": [1000, 900, 800, 700],
        "Gross Profit": [500, 450, 400, 350],
        "Operating Income": [220, 190, 160, 130]})
    balance = _series({"Invested Capital": [1000, 950, 900, 850],
                       "Tangible Book Value": [800, 750, 700, 650]})
    info = {"symbol": "T", "sector": "Technology", "beta": 1.1,
            "marketCap": 1_000_000, "totalDebt": 0.0}
    return ScreenerInputs(ticker="T", info=info, income=income, balance=balance,
                          cashflow=None, price_monthly=(), risk_free=0.043)


def test_stores_roic_and_rote_series_percent_scaled_latest_first():
    m = compute_metrics(_inputs_for_series())
    # 4 years present -> 4 observations; latest first
    assert len(m.roic_series) == 4
    # ROIC yr0 = 200*(1-0.21)/1000 = 0.158 -> 15.8%
    assert m.roic_series[0] == pytest.approx(15.8, abs=0.05)
    assert m.roic_series[0] > m.roic_series[-1]  # improving, latest first
    # ROTE yr0 = 160/800 = 20%
    assert len(m.rote_series) == 4
    assert m.rote_series[0] == pytest.approx(20.0, abs=0.05)
    assert m.rote_5y_avg == pytest.approx(sum(m.rote_series) / len(m.rote_series), abs=1e-6)


def test_stores_margin_series_and_gross_trajectory():
    m = compute_metrics(_inputs_for_series())
    # gross margin yr0 = 500/1000 = 50%
    assert m.gross_margin_series[0] == pytest.approx(50.0, abs=0.05)
    # op margin yr0 = 220/1000 = 22%
    assert m.op_margin_series[0] == pytest.approx(22.0, abs=0.05)
    # trajectory = latest(50) - oldest(350/700=50) = 0pp here
    assert m.gross_margin_trajectory == pytest.approx(0.0, abs=0.05)
```

Add `import pytest` at the top of the test file if it isn't already imported.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_screener_metrics.py::test_stores_roic_and_rote_series_percent_scaled_latest_first tests/test_screener_metrics.py::test_stores_margin_series_and_gross_trajectory -v`
Expected: FAIL — `AttributeError`/validation error, `roic_series` (etc.) not defined on `ScreenerMetrics`.

- [ ] **Step 3: Add the fields to `ScreenerMetrics`**

In `backend/screener/models.py`, inside `class ScreenerMetrics`, add after the existing Section II block (after `roic_5y_ex_goodwill` / `goodwill_intangible_share`, around line 63):

```python
    # Moat inputs — per-year series (percent), latest-first, matching roic_5y_avg's basis.
    # Stored here so the Moat module can measure durability without any extra fetch.
    roic_series: list[float] = []
    roic_series_ex_goodwill: list[float] = []
    rote_series: list[float] = []
    rote_5y_avg: float | None = None
    gross_margin_series: list[float] = []
    op_margin_series: list[float] = []
    gross_margin_trajectory: float | None = None
```

(Pydantic v2 gives each instance its own copy of a list default, so `= []` is safe here.)

- [ ] **Step 4: Populate the series in `compute_metrics`**

In `backend/screener/metrics.py`, in the `--- Section II ---` block, replace **only lines 132–147** — the per-year `annual`/`annual_ex` loop and the two `if annual:` / `if annual_ex:` averaging blocks — with the version below, which also stores the per-year series and computes ROTE per-year. **Leave lines 148–157 exactly as they are** (`ic0`/`gwi0` → `roic_ex_goodwill` + `goodwill_intangible_share`, and the spot `m.rote`). The `annual` / `annual_ex` lists are fractions; store them as percents. The new block ends with the ROTE loop, which sits immediately above the untouched line 148:

```python
        annual = []
        annual_ex = []  # ROIC on tangible invested capital (ex goodwill & intangibles)
        for i in range(len(inc.years)):
            ic = bal.value("Invested Capital", i)
            r = roic(inc.value("EBIT", i), tax, ic)
            if r is not None:
                annual.append(r)
            gwi = goodwill_intangibles(bal, i)
            if ic is not None and gwi is not None:
                r_ex = roic(inc.value("EBIT", i), tax, ic - gwi)
                if r_ex is not None:
                    annual_ex.append(r_ex)
        m.roic_series = [x * 100.0 for x in annual]
        m.roic_series_ex_goodwill = [x * 100.0 for x in annual_ex]
        if annual:
            m.roic_5y_avg = pct(sum(annual) / len(annual))
        if annual_ex:
            m.roic_5y_ex_goodwill = pct(sum(annual_ex) / len(annual_ex))
        # per-year ROTE (Net Income / Tangible Book Value), percent
        rote_series = []
        for i in range(len(inc.years)):
            ni_i = inc.value("Net Income", i)
            tbv_i = bal.value("Tangible Book Value", i)
            if ni_i is not None and tbv_i and tbv_i > 0:
                rote_series.append(ni_i / tbv_i * 100.0)
        m.rote_series = rote_series
        if rote_series:
            m.rote_5y_avg = sum(rote_series) / len(rote_series)
```

(The lines that follow — `ic0`/`gwi0` → `roic_ex_goodwill`, `goodwill_intangible_share`, and the spot `m.rote` — stay exactly as they are; the block above is inserted immediately before them.)

Then, in the `--- Section I ---` block, alongside `op_margin_trajectory` (after line 214), add the per-year margin series and the gross trajectory. Insert:

```python
    # per-year margin series (percent), for Moat margin-durability
    if inc is not None:
        gm_series, om_series = [], []
        for i in range(len(inc.years)):
            rev_i = inc.value("Total Revenue", i)
            gp_i = inc.value("Gross Profit", i)
            oi_i = inc.value("Operating Income", i)
            if gp_i is not None and rev_i:
                gm_series.append(gp_i / rev_i * 100.0)
            if oi_i is not None and rev_i:
                om_series.append(oi_i / rev_i * 100.0)
        m.gross_margin_series = gm_series
        m.op_margin_series = om_series
        # gross-margin trajectory: latest minus oldest available (pp), twin of op_margin_trajectory
        gp_old = inc.value("Gross Profit", min(3, len(inc.years) - 1))
        rev_old = inc.value("Total Revenue", min(3, len(inc.years) - 1))
        gp_new = inc.latest("Gross Profit")
        rev_new = inc.latest("Total Revenue")
        if gp_old is not None and rev_old and gp_new is not None and rev_new:
            m.gross_margin_trajectory = (gp_new / rev_new - gp_old / rev_old) * 100.0
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_screener_metrics.py -v`
Expected: PASS (new tests + all existing metric tests).

- [ ] **Step 6: Run the full suite to confirm no regression**

Run: `python -m pytest -q`
Expected: 522 passed (520 existing + 2 new).

- [ ] **Step 7: Commit**

```bash
git add backend/screener/models.py backend/screener/metrics.py backend/tests/test_screener_metrics.py
git commit -m "feat(moat): store per-year ROIC/ROTE/margin series on ScreenerMetrics"
```

---

## Task 2: Moat statistics helpers (`moat/metrics.py`)

Pure functions over the stored series. No dependence on `ScreenerMetrics` — just lists — so they are trivially unit-testable.

**Files:**
- Create: `backend/moat/__init__.py`
- Create: `backend/moat/metrics.py`
- Test: `backend/tests/test_moat_metrics.py`

**Interfaces:**
- Produces:
  - `mean(vals: list[float]) -> float | None` — arithmetic mean, `None` if empty.
  - `pstdev(vals: list[float]) -> float | None` — population standard deviation, `None` if empty.
  - `persistence_fraction(series: list[float], hurdle: float | None) -> float | None` — fraction of observations strictly greater than `hurdle`; `None` if the series is empty or `hurdle is None`.
  - `coef_of_variation(series: list[float]) -> float | None` — `pstdev / mean`; `None` if the series is empty or `mean <= 0` (a non-positive mean makes CoV meaningless — the economic-profit gate handles those names anyway).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_moat_metrics.py`:

```python
import pytest
from moat.metrics import mean, pstdev, persistence_fraction, coef_of_variation


def test_mean_and_pstdev():
    assert mean([]) is None
    assert pstdev([]) is None
    assert mean([2.0, 4.0]) == pytest.approx(3.0)
    assert pstdev([2.0, 4.0]) == pytest.approx(1.0)  # population sd of {2,4}


def test_persistence_fraction():
    assert persistence_fraction([], 5.0) is None
    assert persistence_fraction([10.0, 12.0], None) is None
    # 3 of 4 years strictly above the 8% hurdle
    assert persistence_fraction([12.0, 9.0, 8.0, 20.0], 8.0) == pytest.approx(3 / 4)
    # exactly-equal does not count (strictly greater)
    assert persistence_fraction([8.0, 8.0], 8.0) == pytest.approx(0.0)


def test_coef_of_variation():
    assert coef_of_variation([]) is None
    assert coef_of_variation([-1.0, 1.0]) is None       # mean 0 -> None
    assert coef_of_variation([-5.0, -5.0]) is None       # negative mean -> None
    # stable series -> low CoV; volatile -> high CoV
    stable = coef_of_variation([20.0, 21.0, 19.0, 20.0])
    volatile = coef_of_variation([5.0, 35.0, 2.0, 38.0])
    assert stable is not None and volatile is not None
    assert stable < volatile
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_moat_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moat'`.

- [ ] **Step 3: Create the package and helpers**

Create `backend/moat/__init__.py` (empty).

Create `backend/moat/metrics.py`:

```python
"""Pure statistics over the per-year series ScreenerMetrics stores. No fetching,
no ScreenerMetrics dependency — just lists of floats — so the durability math
is trivially testable and reusable."""
from __future__ import annotations
import statistics


def mean(vals: list[float]) -> float | None:
    return sum(vals) / len(vals) if vals else None


def pstdev(vals: list[float]) -> float | None:
    return statistics.pstdev(vals) if vals else None


def persistence_fraction(series: list[float], hurdle: float | None) -> float | None:
    """Fraction of observations strictly above `hurdle`. This is the durability
    core: how often the business actually out-earned its cost of capital."""
    if not series or hurdle is None:
        return None
    return sum(1 for v in series if v > hurdle) / len(series)


def coef_of_variation(series: list[float]) -> float | None:
    """Population CoV = stdev / mean. Undefined for a non-positive mean (the
    economic-profit gate covers those names), so returns None there."""
    if not series:
        return None
    mu = mean(series)
    if mu is None or mu <= 0:
        return None
    return pstdev(series) / mu
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_moat_metrics.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/moat/__init__.py backend/moat/metrics.py backend/tests/test_moat_metrics.py
git commit -m "feat(moat): statistics helpers (persistence, CoV, stdev, mean)"
```

---

## Task 3: Moat scoring bands + the two magnitude pillars (A1, A2)

Start `moat/scoring.py` with the constants and the magnitude pillars. The gate, durability, cash-backing, and renormalization arrive in Tasks 4–6, so this task's `score()` is intentionally partial but already produces a real (renormalized) number over whatever it can compute — the accumulator design makes the later pillars purely additive.

**Files:**
- Create: `backend/moat/scoring.py`
- Test: `backend/tests/test_moat_scoring.py`

**Interfaces:**
- Consumes: `ScreenerMetrics` (Task 1 fields), and `screener.scoring.score_high`, `screener.scoring.score_low`, `screener.scoring._acquisition_distorted`, `screener.scoring._heavy_capex_distortion`.
- Produces:
  - Band constants: `A1_ROIC_BANDS`, `A2_SPREAD_BANDS` (and, added in later tasks, `B2_COV_BANDS`, `GROSS_STDEV_BANDS`, `OP_STDEV_BANDS`, `MARGIN_TRAJ_BANDS`, `C1_FCF_BANDS`).
  - Tunables: `FINANCIAL_COE_PCT = 8.5`, `MOAT_GATE_CEIL = 35.0`, `MOAT_MIN_YEARS = 3`, `MOAT_MIN_PILLARS = 3`.
  - `_return_axis(m, profile) -> dict` — resolves which series/level/hurdle/spot-spread/5y-spread to use (plain ROIC vs ex-goodwill vs financial ROTE).
  - `score(m: ScreenerMetrics, profile: str) -> tuple[float | None, dict]` — `(moat_score_0_100_or_None, breakdown)`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_moat_scoring.py`:

```python
import pytest
from screener.models import ScreenerMetrics
from moat import scoring
from moat.scoring import score, A1_ROIC_BANDS, A2_SPREAD_BANDS


def test_band_tables_are_descending_and_cover_expected_points():
    # A1 top band awards 20; A2 top band awards 20
    assert A1_ROIC_BANDS[0] == (25, 20)
    assert A2_SPREAD_BANDS[0] == (15, 20)
    # thresholds strictly descending (score_high scans top-down)
    for bands in (A1_ROIC_BANDS, A2_SPREAD_BANDS):
        thr = [t for t, _ in bands]
        assert thr == sorted(thr, reverse=True)


def _wide_moat_metrics():
    # high, stable ROIC well above WACC
    m = ScreenerMetrics()
    m.roic_5y_avg = 30.0
    m.roic_ttm = 31.0
    m.wacc = 9.0
    m.roic_wacc_spread = 22.0
    m.roic_series = [31.0, 30.0, 29.0, 30.0, 30.0]
    return m


def test_magnitude_only_score_is_renormalized_to_100():
    # With only A1+A2 computable, a top-band name earns 40/40 -> 100 before other pillars.
    m = _wide_moat_metrics()
    # blank out everything the later pillars would read so only A1/A2 score
    m.gross_margin_series = []
    m.op_margin_series = []
    m.fcf = None
    m.ebitda = None
    val, bd = score(m, "TECH_GROWTH")
    assert bd["pillars"]["A1"] == 20
    assert bd["pillars"]["A2"] == 20
    # magnitude alone renormalizes to 100 (durability/cash unavailable here);
    # coverage floor is satisfied (5 years, >=3 pillars once Tasks 4-5 land).
    assert val is not None
```

Note: the second assertion on `val is not None` depends on the coverage floor (Task 4/5). If this task is executed strictly in isolation, expect `val` to be gated by `MOAT_MIN_PILLARS` once implemented; keep the assertion — it will pass after Task 5 adds durability pillars. For this task's own green bar, rely on the `bd["pillars"]` assertions.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_moat_scoring.py::test_band_tables_are_descending_and_cover_expected_points -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'moat.scoring'`.

- [ ] **Step 3: Create `moat/scoring.py` with constants, axis resolver, and A1/A2**

```python
"""Moat Score — pure durability-of-economic-profit. A 40/50/10 model over the
series ScreenerMetrics already carries. Numeric only (0-100); no rating labels.
See docs/superpowers/specs/2026-08-24-moat-score-design.md."""
from __future__ import annotations
from screener.models import ScreenerMetrics
from screener.scoring import (
    score_high, score_low, _acquisition_distorted, _heavy_capex_distortion,
)
from moat.metrics import mean, pstdev, persistence_fraction, coef_of_variation

# --- tunables (swept in the calibration task) -------------------------------
FINANCIAL_COE_PCT = 8.5      # banks' hurdle: cost of equity, percent
MOAT_GATE_CEIL = 35.0        # no-durable-excess names capped here
MOAT_MIN_YEARS = 3           # min observations in the return series
MOAT_MIN_PILLARS = 3         # min scored pillar-metrics, else None

# --- bands ------------------------------------------------------------------
# A1 ROIC level, 5y avg (max 20) — score_high on percent
A1_ROIC_BANDS = [(25, 20), (20, 17), (15, 13), (12, 8), (8, 4)]
# A2 economic spread, ROIC-WACC blend (max 20) — score_high on pp
A2_SPREAD_BANDS = [(15, 20), (10, 16), (5, 11), (0, 5)]


def _return_axis(m: ScreenerMetrics, profile: str) -> dict:
    """Resolve the return axis: plain ROIC vs tangible (ex-goodwill) ROIC vs, for
    financials, ROTE vs cost of equity. Returns level / hurdle / series / spot &
    5y spreads, all percent/pp."""
    if profile == "FINANCIALS":
        level = m.rote_5y_avg
        hurdle = FINANCIAL_COE_PCT
        series = m.rote_series
        spot = (m.rote - FINANCIAL_COE_PCT) if m.rote is not None else None
        five = (m.rote_5y_avg - FINANCIAL_COE_PCT) if m.rote_5y_avg is not None else None
        return {"level": level, "hurdle": hurdle, "series": series,
                "spot": spot, "five": five, "variant": "FINANCIAL_ROTE"}
    if _acquisition_distorted(m):
        level = m.roic_5y_ex_goodwill if m.roic_5y_ex_goodwill is not None else m.roic_5y_avg
        series = m.roic_series_ex_goodwill or m.roic_series
        spot = ((m.roic_ex_goodwill - m.wacc) if (m.roic_ex_goodwill is not None
                and m.wacc is not None) else m.roic_wacc_spread)
        five = (level - m.wacc) if (level is not None and m.wacc is not None) else None
        return {"level": level, "hurdle": m.wacc, "series": series,
                "spot": spot, "five": five, "variant": "TANGIBLE_ROIC"}
    level = m.roic_5y_avg
    series = m.roic_series
    spot = m.roic_wacc_spread
    five = (m.roic_5y_avg - m.wacc) if (m.roic_5y_avg is not None
            and m.wacc is not None) else None
    return {"level": level, "hurdle": m.wacc, "series": series,
            "spot": spot, "five": five, "variant": "ROIC"}


def _spread_blend(spot: float | None, five: float | None) -> float | None:
    """0.5*spot + 0.5*5y; drops a missing leg and uses the other (spec: WACC-
    dependent legs dropped and renormalized)."""
    parts = [x for x in (spot, five) if x is not None]
    return sum(parts) / len(parts) if parts else None


def score(m: ScreenerMetrics, profile: str) -> tuple[float | None, dict]:
    axis = _return_axis(m, profile)
    pillars: dict[str, float] = {}   # name -> earned points
    maxima: dict[str, float] = {}    # name -> max points

    def add(name: str, earned: float | None, cap: float) -> None:
        if earned is not None:
            pillars[name] = earned
            maxima[name] = cap

    # A1 — ROIC/ROTE level
    add("A1", score_high(axis["level"], A1_ROIC_BANDS, 0.0), 20)
    # A2 — economic spread blend
    add("A2", score_high(_spread_blend(axis["spot"], axis["five"]), A2_SPREAD_BANDS, 0.0), 20)

    # (Durability B1/B2/B3 and cash-backing C1 are added in Tasks 4-6.)

    available = sum(maxima.values())
    breakdown: dict = {
        "variant": axis["variant"],
        "pillars": dict(pillars),
        "maxima": dict(maxima),
        "earned": round(sum(pillars.values()), 2),
        "available": available,
        "gated": False,
    }
    series_len = len(axis["series"] or [])
    if series_len < MOAT_MIN_YEARS or len(pillars) < MOAT_MIN_PILLARS or available <= 0:
        breakdown["moat_score"] = None
        return None, breakdown

    moat = 100.0 * sum(pillars.values()) / available
    breakdown["moat_score"] = round(moat, 1)
    return round(moat, 1), breakdown
```

- [ ] **Step 4: Run tests to verify the band test passes**

Run: `python -m pytest tests/test_moat_scoring.py::test_band_tables_are_descending_and_cover_expected_points tests/test_moat_scoring.py::test_magnitude_only_score_is_renormalized_to_100 -v`
Expected: the band test PASSES; the `pillars` assertions in the magnitude test PASS. `val is not None` may be `None` here because only 2 pillars exist (< `MOAT_MIN_PILLARS`) — that is expected and resolves after Task 5. If executing strictly task-by-task, temporarily assert `val is None and bd["pillars"]["A1"] == 20` and restore the `is not None` assertion after Task 5. (If executing the whole plan before running, leave as written.)

- [ ] **Step 5: Commit**

```bash
git add backend/moat/scoring.py backend/tests/test_moat_scoring.py
git commit -m "feat(moat): scoring scaffold + magnitude pillars (A1 ROIC level, A2 spread)"
```

---

## Task 4: Economic-profit gate + coverage floor

Add the gate that caps names with no durable excess return, and confirm the coverage-floor behaviour. The gate uses the resolved axis `level` vs `hurdle`.

**Files:**
- Modify: `backend/moat/scoring.py` (the `score` function)
- Test: `backend/tests/test_moat_scoring.py`

**Interfaces:**
- Consumes: `_return_axis` output (`level`, `hurdle`).
- Produces: `score()` now caps at `MOAT_GATE_CEIL` when `level <= hurdle` (both non-None); `breakdown["gated"]` reflects it. Coverage floor returns `None` below `MOAT_MIN_YEARS` / `MOAT_MIN_PILLARS`.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_moat_scoring.py`:

```python
def _no_moat_metrics():
    # ROIC below WACC every year: no durable excess return
    m = ScreenerMetrics()
    m.roic_5y_avg = 6.0
    m.roic_ttm = 6.0
    m.wacc = 9.0
    m.roic_wacc_spread = -3.0
    m.roic_series = [6.0, 5.0, 7.0, 6.0, 6.0]
    m.gross_margin_series = [40.0, 40.0, 40.0, 40.0, 40.0]
    m.op_margin_series = [10.0, 10.0, 10.0, 10.0, 10.0]
    m.gross_margin_trajectory = 0.0
    m.op_margin_trajectory = 0.0
    m.fcf = 50.0
    m.ebitda = 100.0
    return m


def test_gate_caps_no_durable_excess_names():
    m = _no_moat_metrics()
    val, bd = score(m, "INDUSTRIAL_CYCLICAL")
    assert bd["gated"] is True
    assert val is not None and val <= scoring.MOAT_GATE_CEIL


def test_coverage_floor_returns_none_for_short_history():
    m = _wide_moat_metrics()
    m.roic_series = [30.0, 31.0]           # only 2 years < MOAT_MIN_YEARS
    val, bd = score(m, "TECH_GROWTH")
    assert val is None
    assert bd["moat_score"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_moat_scoring.py::test_gate_caps_no_durable_excess_names -v`
Expected: FAIL — `bd["gated"]` is `False` (gate not implemented yet).

- [ ] **Step 3: Add the gate to `score`**

In `backend/moat/scoring.py`, replace the final scoring block (from `moat = 100.0 * ...` onward) with:

```python
    moat = 100.0 * sum(pillars.values()) / available
    level, hurdle = axis["level"], axis["hurdle"]
    if level is not None and hurdle is not None and level <= hurdle:
        moat = min(moat, MOAT_GATE_CEIL)
        breakdown["gated"] = True
    breakdown["moat_score"] = round(moat, 1)
    return round(moat, 1), breakdown
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_moat_scoring.py -v`
Expected: PASS (gate + coverage-floor tests; earlier tests still green).

- [ ] **Step 5: Commit**

```bash
git add backend/moat/scoring.py backend/tests/test_moat_scoring.py
git commit -m "feat(moat): economic-profit gate + coverage floor"
```

---

## Task 5: Durability pillars (B1 persistence, B2 consistency, B3 margin durability)

The largest pillar (50 points). B1/B2 run over the resolved return series; B3 over the margin series.

**Files:**
- Modify: `backend/moat/scoring.py`
- Test: `backend/tests/test_moat_scoring.py`

**Interfaces:**
- Consumes: `persistence_fraction`, `coef_of_variation`, `pstdev`, `mean` from `moat.metrics`; axis `series`/`hurdle`; `m.gross_margin_series`, `m.op_margin_series`, `m.gross_margin_trajectory`, `m.op_margin_trajectory`.
- Produces: new bands `B2_COV_BANDS`, `GROSS_STDEV_BANDS`, `OP_STDEV_BANDS`, `MARGIN_TRAJ_BANDS`; `score()` now adds `B1` (max 25), `B2` (max 10), `B3` (max 15) to the accumulator; `breakdown["pillars"]` includes them.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_moat_scoring.py`:

```python
def test_persistence_pillar_scales_with_years_above_hurdle():
    m = _wide_moat_metrics()          # 5 years all ~30% vs wacc 9% -> 5/5 above
    _, bd = score(m, "TECH_GROWTH")
    assert bd["pillars"]["B1"] == pytest.approx(25.0)     # 25 * 5/5


def test_eroding_margins_score_below_stable_peer_at_equal_level():
    stable = _wide_moat_metrics()
    stable.gross_margin_series = [70.0, 71.0, 69.0, 72.0, 70.0]
    stable.op_margin_series = [30.0, 31.0, 29.0, 30.0, 30.0]
    stable.gross_margin_trajectory = 0.0
    stable.op_margin_trajectory = 0.0

    eroding = _wide_moat_metrics()
    eroding.gross_margin_series = [70.0, 64.0, 57.0, 51.0, 45.0]
    eroding.op_margin_series = [30.0, 24.0, 18.0, 12.0, 8.0]
    eroding.gross_margin_trajectory = -25.0
    eroding.op_margin_trajectory = -22.0

    _, sbd = score(stable, "TECH_GROWTH")
    _, ebd = score(eroding, "TECH_GROWTH")
    assert sbd["pillars"]["B3"] > ebd["pillars"]["B3"]


def test_b3_drops_gross_component_when_gross_series_missing():
    m = _wide_moat_metrics()
    m.gross_margin_series = []          # no Gross Profit row
    m.gross_margin_trajectory = None
    m.op_margin_series = [30.0, 31.0, 29.0, 30.0, 30.0]
    m.op_margin_trajectory = 0.0
    _, bd = score(m, "TECH_GROWTH")
    assert "B3" in bd["pillars"]        # still scored on op-margin components only
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_moat_scoring.py::test_persistence_pillar_scales_with_years_above_hurdle -v`
Expected: FAIL — `KeyError: 'B1'`.

- [ ] **Step 3: Add durability bands + pillars**

In `backend/moat/scoring.py`, add the bands after `A2_SPREAD_BANDS`:

```python
# B2 consistency (max 10) — score_low on coefficient of variation
B2_COV_BANDS = [(0.10, 10), (0.20, 8), (0.35, 5), (0.50, 3)]
# B3 margin durability (max 15) — three 0-10 components, mean scaled to 15
GROSS_STDEV_BANDS = [(1.0, 10), (2.0, 8), (4.0, 5), (7.0, 3)]   # score_low, pp
OP_STDEV_BANDS = [(1.0, 10), (2.0, 8), (4.0, 5), (7.0, 3)]      # score_low, pp
MARGIN_TRAJ_BANDS = [(2, 10), (0, 7), (-2, 4)]                  # score_high, pp
```

Add a B3 helper above `score`:

```python
def _margin_durability(m: ScreenerMetrics) -> float | None:
    """Mean of up to three 0-10 components (gross stability, op stability,
    non-erosion), scaled to 15. Emphasis on stability + non-erosion, not level."""
    comps: list[float] = []
    if len(m.gross_margin_series) >= 2:
        comps.append(score_low(pstdev(m.gross_margin_series), GROSS_STDEV_BANDS, 0.0))
    if len(m.op_margin_series) >= 2:
        comps.append(score_low(pstdev(m.op_margin_series), OP_STDEV_BANDS, 0.0))
    traj = m.gross_margin_trajectory if m.gross_margin_trajectory is not None \
        else m.op_margin_trajectory
    if traj is not None:
        comps.append(score_high(traj, MARGIN_TRAJ_BANDS, 0.0))
    avg = mean(comps)
    return None if avg is None else 15.0 * avg / 10.0
```

Then, in `score`, insert the durability pillars after the A2 `add(...)` line and before the `available = ...` line:

```python
    # B1 — persistence: fraction of years the business out-earned its hurdle
    frac = persistence_fraction(axis["series"], axis["hurdle"])
    add("B1", (25.0 * frac) if frac is not None else None, 25)
    # B2 — consistency: low variability of the return series
    add("B2", score_low(coef_of_variation(axis["series"]), B2_COV_BANDS, 0.0), 10)
    # B3 — margin durability
    add("B3", _margin_durability(m), 15)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_moat_scoring.py -v`
Expected: PASS. The Task-3 `test_magnitude_only_score_is_renormalized_to_100` now yields `val is not None` (B1/B2/B3 present → ≥3 pillars); if you temporarily weakened that assertion in Task 3, restore it to `assert val is not None` now.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add backend/moat/scoring.py backend/tests/test_moat_scoring.py
git commit -m "feat(moat): durability pillars (persistence, consistency, margin durability)"
```

---

## Task 6: Cash-backing pillar (C1) + financials/heavy-capex exclusion

Add FCF conversion, excluded for financials and heavy-capex reinvestors (renormalized out of the denominator), plus the financials ROTE-variant golden check.

**Files:**
- Modify: `backend/moat/scoring.py`
- Test: `backend/tests/test_moat_scoring.py`

**Interfaces:**
- Consumes: `_heavy_capex_distortion(m)`; `m.fcf`, `m.ebitda`.
- Produces: band `C1_FCF_BANDS`; `score()` adds `C1` (max 10) except for `FINANCIALS`/heavy-capex; `breakdown["excluded"]` lists what was dropped.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_moat_scoring.py`:

```python
def test_fcf_conversion_excluded_for_financials():
    m = _wide_moat_metrics()
    m.rote = 22.0
    m.rote_5y_avg = 21.0
    m.rote_series = [22.0, 21.0, 20.0, 21.0, 21.0]
    m.fcf = 50.0
    m.ebitda = 100.0
    _, bd = score(m, "FINANCIALS")
    assert "C1" not in bd["pillars"]
    assert "C1 FCF conversion" in bd["excluded"]
    assert bd["variant"] == "FINANCIAL_ROTE"


def test_fcf_conversion_scored_for_normal_company():
    m = _wide_moat_metrics()
    m.gross_margin_series = [70.0, 70.0, 70.0, 70.0, 70.0]
    m.op_margin_series = [30.0, 30.0, 30.0, 30.0, 30.0]
    m.gross_margin_trajectory = 0.0
    m.op_margin_trajectory = 0.0
    m.fcf = 95.0
    m.ebitda = 100.0                    # 0.95 conversion -> top band
    _, bd = score(m, "TECH_GROWTH")
    assert bd["pillars"]["C1"] == 10


def test_bank_produces_sane_score_on_rote_axis():
    m = ScreenerMetrics()
    m.rote = 16.0
    m.rote_5y_avg = 15.0
    m.rote_series = [16.0, 15.0, 14.0, 15.0, 15.0]
    m.roic_5y_avg = None               # ROIC frame irrelevant for a bank
    m.wacc = None
    val, bd = score(m, "FINANCIALS")
    assert val is not None
    assert bd["gated"] is False        # ROTE 15% > COE 8.5%
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_moat_scoring.py::test_fcf_conversion_excluded_for_financials -v`
Expected: FAIL — `bd["excluded"]` missing / `KeyError`.

- [ ] **Step 3: Add C1 + exclusions**

In `backend/moat/scoring.py`, add the band:

```python
# C1 FCF conversion (max 10) — score_high on fcf/ebitda
C1_FCF_BANDS = [(0.90, 10), (0.70, 8), (0.50, 6), (0.30, 3)]
```

In `score`, initialise an `excluded` list where `pillars`/`maxima` are set up:

```python
    excluded: list[str] = []
```

After the B3 `add(...)` line, add the cash-backing pillar:

```python
    # C1 — cash-backing: FCF conversion. Structurally distorted for lenders and
    # heavy-capex reinvestors -> excluded and renormalized out (mirrors Quality).
    is_fin = profile == "FINANCIALS"
    heavy_capex = _heavy_capex_distortion(m)
    if is_fin or heavy_capex:
        excluded.append("C1 FCF conversion")
    elif m.fcf is not None and m.ebitda is not None and m.ebitda > 0:
        add("C1", score_high(m.fcf / m.ebitda, C1_FCF_BANDS, 0.0), 10)
```

Add `"excluded": excluded,` to the `breakdown` dict literal.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_moat_scoring.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/moat/scoring.py backend/tests/test_moat_scoring.py
git commit -m "feat(moat): FCF-conversion pillar + financials/heavy-capex exclusion"
```

---

## Task 7: Wire Moat into the Screener engine

Compute the Moat Score in the Screener pipeline and attach it to `ScreenerResult`.

**Files:**
- Modify: `backend/screener/models.py` (`ScreenerResult`, lines 96-107)
- Modify: `backend/screener/engine.py`
- Test: `backend/tests/test_screener_engine.py`

**Interfaces:**
- Consumes: `moat.scoring.score`.
- Produces: `ScreenerResult.moat_score: float | None`, `ScreenerResult.moat_breakdown: dict`; `engine.run()` sets both on every result path.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_screener_engine.py` (it already has a `_full_inputs()` helper and patches `fetch_screener_inputs`):

```python
@pytest.mark.asyncio
async def test_engine_attaches_moat_score():
    inp = _full_inputs()
    with patch("screener.engine.fetch_screener_inputs", return_value=inp):
        result = await engine.run("AAPL")
    assert result.status == "completed"
    assert result.moat_score is not None
    assert 0.0 <= result.moat_score <= 100.0
    assert result.moat_breakdown.get("variant") in {"ROIC", "TANGIBLE_ROIC", "FINANCIAL_ROTE"}
```

Confirm the patch target matches how `engine.run` imports `fetch_screener_inputs` (the module imports it by name at `screener/engine.py:3`, so `screener.engine.fetch_screener_inputs` is correct — mirror the existing engine tests' patch target).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_screener_engine.py::test_engine_attaches_moat_score -v`
Expected: FAIL — `AttributeError: 'ScreenerResult' object has no attribute 'moat_score'`.

- [ ] **Step 3: Add fields to `ScreenerResult`**

In `backend/screener/models.py`, in `class ScreenerResult`, add after `quality_score` (line 100):

```python
    moat_score: float | None = None
    moat_breakdown: dict = {}
```

- [ ] **Step 4: Compute and attach in the engine**

In `backend/screener/engine.py`, add the import and compute the moat after the quality score. Replace the body from `metrics = compute_metrics(inp)` onward:

```python
    metrics = compute_metrics(inp)
    quality, sections, profile, breakdown = score(metrics, metrics.sector)
    moat, moat_breakdown = moat_score(metrics, profile)
    now = datetime.now(timezone.utc).isoformat()
    if quality is None:
        return ScreenerResult(
            ticker=t, company_name=inp.info.get("shortName") or inp.info.get("longName"),
            last_evaluated=now, sector=metrics.sector, sector_profile=profile,
            section_scores=sections, metrics=metrics.model_dump(),
            score_breakdown=breakdown, moat_score=moat, moat_breakdown=moat_breakdown,
            status="failed", errors=["insufficient data for a quality score"],
        )
    return ScreenerResult(
        ticker=t, company_name=inp.info.get("shortName") or inp.info.get("longName"),
        last_evaluated=now, quality_score=quality, sector=metrics.sector,
        sector_profile=profile, section_scores=sections, metrics=metrics.model_dump(),
        score_breakdown=breakdown, moat_score=moat, moat_breakdown=moat_breakdown,
        status="completed", errors=[],
    )
```

And add the import near the top (after `from screener.scoring import score`):

```python
from moat.scoring import score as moat_score
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_screener_engine.py -v`
Expected: PASS (new test + all existing engine tests unchanged).

- [ ] **Step 6: Commit**

```bash
git add backend/screener/models.py backend/screener/engine.py backend/tests/test_screener_engine.py
git commit -m "feat(moat): wire moat score into the screener engine"
```

---

## Task 8: Persist Moat to the Screener tab + mirror to Database column S

Persist `moat_score` (and `moat_breakdown` JSON) as two trailing columns on the Screener tab, and mirror `moat_score` into Database column S — copying the existing quality-score mirror pattern exactly. Then teach the Database reader to load column S.

**Files:**
- Modify: `backend/services/screener_sheets.py`
- Modify: `backend/services/sheets.py` (`_row_to_database_row` line 242 & 259; `_read_database_sync` range line 270)
- Modify: `backend/models.py` (`DatabaseRow`, line 24-26)
- Test: `backend/tests/test_screener_sheets.py`

**Interfaces:**
- Consumes: `ScreenerResult.moat_score`, `ScreenerResult.moat_breakdown`.
- Produces: `DatabaseRow.moat_score: float | None`; Screener tab gains trailing `Moat Score` + `Moat Breakdown` columns; `DATABASE_MOAT_COL = "S"` mirror.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_screener_sheets.py` (uses the module's existing `_result_to_row`/`_row_to_result` roundtrip helpers):

```python
from screener.models import ScreenerResult
from services import screener_sheets as ss


def test_moat_score_survives_row_roundtrip():
    r = ScreenerResult(
        ticker="AAPL", company_name="Apple", quality_score=8.1,
        sector="Technology", sector_profile="TECH_GROWTH",
        section_scores={"I": 8, "II": 9, "III": 7, "IV": 8},
        metrics={}, score_breakdown={"final": 8.1},
        moat_score=82.4, moat_breakdown={"variant": "ROIC"},
    )
    row = ss._result_to_row(r)
    back = ss._row_to_result(row)
    assert back.moat_score == 82.4
    assert back.moat_breakdown.get("variant") == "ROIC"


def test_moat_header_appended_after_score_breakdown():
    assert ss._SCREENER_HEADERS[-2] == "Moat Score"
    assert ss._SCREENER_HEADERS[-1] == "Moat Breakdown"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_screener_sheets.py::test_moat_score_survives_row_roundtrip tests/test_screener_sheets.py::test_moat_header_appended_after_score_breakdown -v`
Expected: FAIL — headers/roundtrip don't carry moat yet.

- [ ] **Step 3: Extend the Screener-tab schema + roundtrip**

In `backend/services/screener_sheets.py`:

Append to `_SCREENER_HEADERS` (after `"Score Breakdown"`, line 27):

```python
_SCREENER_HEADERS = [
    "Ticker", "Company", "Last Evaluated", "Quality Score", "Sector", "Sector Profile",
    "Section I", "Section II", "Section III", "Section IV",
    *[c.replace("_", " ").title() for c in _METRIC_COLS],
    "Score Breakdown", "Moat Score", "Moat Breakdown",
]
```

In `_result_to_row`, append the two trailing values after the breakdown JSON (line 47):

```python
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
        _num(r.moat_score),
        json.dumps(r.moat_breakdown or {}),
    ]
```

In `_row_to_result`, read the two trailing columns (after line 72). The breakdown index is `10 + len(_METRIC_COLS)`; moat follows it:

```python
    bd_idx = 10 + len(_METRIC_COLS)
    breakdown = _parse_breakdown(row[bd_idx])
    moat_score = _to_float(row[bd_idx + 1])
    moat_breakdown = _parse_breakdown(row[bd_idx + 2])
    return ScreenerResult(
        ticker=row[0], company_name=row[1] or None, last_evaluated=row[2] or None,
        quality_score=_to_float(row[3]), sector=row[4] or None,
        sector_profile=row[5] or None, section_scores=sections, metrics=metrics,
        score_breakdown=breakdown, moat_score=moat_score, moat_breakdown=moat_breakdown,
    )
```

(`_row_to_result` already pads the row to `len(_SCREENER_HEADERS)` at line 69, so old rows lacking the new columns read back as `None`/`{}`.)

- [ ] **Step 4: Add the Database mirror for Moat**

In `backend/services/screener_sheets.py`, add the column constant next to `DATABASE_QSCORE_COL` (line 82):

```python
DATABASE_MOAT_COL = "S"
```

Add a mirror twin after `_mirror_quality_score` (after line 156), copying its structure:

```python
def _mirror_moat_score(svc, sheet_id: str, ticker: str, score) -> None:
    # ensure the Database S1 header, then update S{row} for this ticker if present
    _execute(svc.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=f"Database!{DATABASE_MOAT_COL}1",
        valueInputOption="RAW", body={"values": [["Moat Score"]]},
    ))
    existing = _execute(svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range="Database!A:A"))
    rows = existing.get("values", [])
    for i, row in enumerate(rows):
        if row and row[0].strip().upper() == ticker.upper():
            _execute(svc.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range=f"Database!{DATABASE_MOAT_COL}{i + 1}",
                valueInputOption="RAW",
                body={"values": [[_num(score)]]},
            ))
            return
```

Call it in `_upsert_sync`, right after the quality mirror (line 181):

```python
    _mirror_quality_score(svc, sheet_id, r.ticker, r.quality_score)
    _mirror_moat_score(svc, sheet_id, r.ticker, r.moat_score)
```

- [ ] **Step 5: Teach the Database reader to load column S**

In `backend/services/sheets.py`:

Change the read range (line 270) from `A:R` to `A:S`:

```python
            range="Database!A:S",      # A:R + the Moat Score mirror (S)
```

In `_row_to_database_row` (line 242), pad to 19 columns and read moat:

```python
    row = list(row) + [""] * (19 - len(row))  # pad to include col S (index 18)
```

and add `moat_score` to the `DatabaseRow(...)` return (after `risk_reward_ratio`, line 260):

```python
        risk_reward_ratio=safe_float(row[17]),
        moat_score=safe_float(row[18]),
```

In `backend/models.py`, add to `DatabaseRow` (line 24-26):

```python
class DatabaseRow(TickerResult):
    quality_score: float | None = None
    risk_reward_ratio: float | None = None
    moat_score: float | None = None
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_screener_sheets.py -v`
Expected: PASS (new tests + existing roundtrip/sheet tests).

- [ ] **Step 7: Run the full backend suite**

Run: `python -m pytest -q`
Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add backend/services/screener_sheets.py backend/services/sheets.py backend/models.py backend/tests/test_screener_sheets.py
git commit -m "feat(moat): persist moat score to Screener tab + mirror to Database col S"
```

---

## Task 9: Frontend Moat column (types + Database grid)

Add the `moat_score` type, a color ramp, and a sortable + range-filterable Moat column immediately after Quality, mirroring the existing Quality column exactly.

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/pages/Database.tsx`

**Interfaces:**
- Consumes: `TickerResult.moat_score` (from `/api/database`).
- Produces: `moatScoreColor(score)` helper; a Moat header + cell; `SortKey` gains `'moat'`; `Filters`/`EMPTY_FILTERS`/serialize/deserialize/`rowMatches` gain `moat`.

- [ ] **Step 1: Add the type + color helper**

In `frontend/src/types.ts`, add to `TickerResult` (after line 23, `quality_score`):

```typescript
  moat_score?: number | null
```

Add a color ramp helper after `qualityScoreBadgeClass` (after line 166). Moat is 0–100, so the thresholds differ from Quality's 0–10:

```typescript
/** 0-100 moat score -> text color band (gate ceiling is 35). */
export function moatScoreColor(score: number | null | undefined): string {
  if (score == null) return 'text-slate-400'
  if (score >= 70) return 'text-green-400'
  if (score >= 50) return 'text-blue-400'
  if (score >= 35) return 'text-yellow-400'
  return 'text-red-400'
}
```

- [ ] **Step 2: Extend the Database grid types**

In `frontend/src/pages/Database.tsx`:

Import the helper (line 6):

```typescript
import { fvGapColor, qualityScoreColor, moatScoreColor, riskRewardColor, riskRewardRatio } from '../types'
```

Extend `SortKey` (line 12):

```typescript
type SortKey = 'quality' | 'moat' | 'fair_value' | 'price_vs_fair_value_pct' | 'risk_reward'
```

Extend `ColKey`, `Filters`, `EMPTY_FILTERS`, serialize/deserialize (lines 19-51). Add `moat` alongside `quality`:

```typescript
type ColKey = 'ticker' | 'stockType' | 'quality' | 'moat' | 'gap' | 'riskReward'
```
```typescript
type Filters = {
  tickers: Set<string>
  stockTypes: Set<string>
  quality: NumRange
  moat: NumRange
  gap: NumRange
  riskReward: NumRange
}
```
```typescript
const EMPTY_FILTERS: Filters = {
  tickers: new Set(),
  stockTypes: new Set(),
  quality: { min: null, max: null },
  moat: { min: null, max: null },
  gap: { min: null, max: null },
  riskReward: { min: null, max: null },
}
```
```typescript
const serializeFilters = (f: Filters): SerializedFilters => ({
  tickers: [...f.tickers].sort(),
  stockTypes: [...f.stockTypes].sort(),
  quality: f.quality,
  moat: f.moat,
  gap: f.gap,
  riskReward: f.riskReward,
})
```
```typescript
const deserializeFilters = (s: Partial<SerializedFilters> | undefined): Filters => ({
  tickers: new Set(s?.tickers ?? []),
  stockTypes: new Set(s?.stockTypes ?? []),
  quality: s?.quality ?? { min: null, max: null },
  moat: s?.moat ?? { min: null, max: null },
  gap: s?.gap ?? { min: null, max: null },
  riskReward: s?.riskReward ?? { min: null, max: null },
})
```

Then check `frontend/src/lib/watchlists.ts` — the `SerializedFilters` interface there (fields `quality: NumRange`, `gap: NumRange`, `riskReward: NumRange`) must gain a `moat: NumRange` field so save/load compiles. Declare it exactly like its `quality` sibling (required, not optional). Saved watchlists from before this change simply lack the key; `deserializeFilters` already tolerates that via `s?.moat ?? { min: null, max: null }`.

- [ ] **Step 3: Wire filter-active, rowMatches, and sortVal**

In `colActive` (line 255) add:

```typescript
    moat: rangeActive(filters.moat),
```

In `rowMatches` (after the quality line, ~line 310) add:

```typescript
    if (!inRange(r.moat_score, filters.moat)) return false
```

In `sortVal` (line 316) add:

```typescript
    if (key === 'moat') return r.moat_score ?? null
```

- [ ] **Step 4: Add the header + cell**

In the header row, add a Moat `<th>` immediately after the Quality `<th>` (after line 518, before the R/R header). Copy the Quality header, swapping label/keys:

```tsx
                <th className="text-right py-2 px-2">
                  <FilterHeader
                    label={<span className="cursor-pointer hover:text-slate-300 select-none" onClick={() => toggleSort('moat')}>Moat</span>}
                    active={colActive.moat}
                    open={openFilter === 'moat'}
                    align="right"
                    onToggle={() => toggleFilter('moat')}
                  >
                    <RangeFilter value={filters.moat} step="1" onChange={v => setFilters(f => ({ ...f, moat: v }))} />
                  </FilterHeader>
                </th>
```

In the body, add a Moat `<td>` immediately after the Quality cell (after line 563). Moat is 0–100, shown as an integer:

```tsx
                  <td className={`py-2 px-2 text-right font-mono text-xs ${moatScoreColor(r.moat_score)}`}>
                    {r.moat_score != null ? r.moat_score.toFixed(0) : '—'}
                  </td>
```

- [ ] **Step 5: Build to verify it compiles**

Run: `cd frontend && npm run build`
Expected: build succeeds, no TypeScript errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types.ts frontend/src/pages/Database.tsx frontend/src/lib/watchlists.ts
git commit -m "feat(moat): Database grid Moat column (sortable + range filter)"
```

---

## Task 10: Calibration sweep against real tickers (exploratory — network, no red/green cycle)

**This task does not follow TDD** — it is an empirical calibration pass over the ~136 DB tickers, producing a distribution report so the user can confirm or adjust the §3.1 band defaults. It must not auto-tune: it surfaces the distribution and the golden-name landings, then **STOPS for user review** before any constant is changed.

**Files:**
- Create: `<scratchpad>/moat_sweep.py` (scratchpad, not committed)
- Create: `docs/analysis/2026-08-24-moat-calibration/README.md` (the report — committed)

**Constraints:**
- Read-only against yfinance; **run `CONCURRENCY=1`** — the screener fetch layer relies on process-global `lru_cache` and a shared monkeypatch pattern that races under concurrency (see the FV-rerating memory note).
- Reuse the live pipeline: for each ticker, `await fetch_screener_inputs(t)` → `compute_metrics(inp)` → `moat.scoring.score(metrics, profile)` where `profile = apply_nudge(base_profile(m.sector), m)`.

- [ ] **Step 1: Get the DB ticker universe**

Read the ticker list the same way the app does — `services.sheets.read_database()` returns rows with `.ticker`. In the sweep script, collect `tickers = [r.ticker for r in await read_database()]`.

- [ ] **Step 2: Write the sweep script**

Create `<scratchpad>/moat_sweep.py`:

```python
import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
# adjust the path above to point at the repo's backend/ dir

from services.sheets import read_database
from screener.data import fetch_screener_inputs
from screener.metrics import compute_metrics
from screener.scoring import apply_nudge, base_profile
from moat.scoring import score as moat_score


async def one(ticker: str):
    try:
        inp = await fetch_screener_inputs(ticker)
        if inp is None:
            return ticker, None, None, "no-inputs"
        m = compute_metrics(inp)
        profile = apply_nudge(base_profile(m.sector), m)
        val, bd = moat_score(m, profile)
        return ticker, val, bd.get("variant"), "gated" if bd.get("gated") else ""
    except Exception as e:
        return ticker, None, None, f"err:{e}"


async def main():
    tickers = [r.ticker for r in await read_database()]
    rows = []
    for t in tickers:                       # CONCURRENCY=1: strictly sequential
        rows.append(await one(t))
    rows.sort(key=lambda r: (r[1] is None, -(r[1] or 0)))
    for t, val, variant, note in rows:
        print(f"{t:8} {('%.1f' % val) if val is not None else '  -  ':>6}  {variant or '':16} {note}")


asyncio.run(main())
```

- [ ] **Step 3: Run the sweep**

Run: `python "<scratchpad>/moat_sweep.py"` (from `backend/`, or with the path adjusted). Expected: a ranked table of ticker → moat score → variant → gated flag for the DB universe.

- [ ] **Step 4: Sanity-check the distribution against expectations**

Confirm the shape matches the design intent (record findings in the report):
- Wide-moat compounders (e.g. V, MA, MSFT, MCO if present) land high (≈ 70+).
- Commodity/cyclical or no-excess names land gated (≤ 35).
- Pre-profit burners land low or blank (coverage floor).
- At least one bank (e.g. JPM) produces a sane non-blank score on the ROTE variant.
- No unexpected `err:` rows (a crash in the scoring path is a real bug — fix it and re-run, adding a unit test to `test_moat_scoring.py` for the case).

- [ ] **Step 5: Write the calibration report**

Create `docs/analysis/2026-08-24-moat-calibration/README.md` with: the ranked table (or a representative excerpt), the four golden-name landings above, the count gated / blank / scored, the variant split (ROIC / TANGIBLE_ROIC / FINANCIAL_ROTE), and any bands that look mis-calibrated with a proposed adjustment. **Do not change any constant yet.**

- [ ] **Step 6: STOP and present to the user**

Summarise the distribution and any proposed band changes, and ask the user to approve tuning before editing constants in `moat/scoring.py`. Any approved change is a follow-up TDD edit: adjust the constant, update/add the affected boundary test in `test_moat_scoring.py`, re-run the sweep, and commit.

- [ ] **Step 7: Commit the report**

```bash
git add docs/analysis/2026-08-24-moat-calibration/README.md
git commit -m "docs(moat): calibration sweep report across DB tickers"
```

---

## Self-Review

**1. Spec coverage** — every spec section maps to a task:
- §3 model (A/B/C pillars, 40/50/10) → Tasks 3, 5, 6. §3.1 bands → Tasks 3/5/6 defaults, calibrated in Task 10.
- §4.1 gate → Task 4. §4.2 acquisition ex-goodwill reuse + financials ROTE variant → Task 3 (`_return_axis`), verified in Task 6. §4.3 exclusions + renormalization → Task 6 (C1 exclusion) and the accumulator in Task 3. §4.4 coverage floor → Task 4.
- §5 new stored metrics → Task 1. §6 architecture (`backend/moat/`, wiring, persistence, frontend) → Tasks 2/3, 7, 8, 9. §6.1 folds `moat_score` into `ScreenerResult` (no separate `moat/models.py` — YAGNI; noted below). §6.2 frontend → Task 9.
- §7 performance (zero fetches) → guaranteed by construction (Tasks 1-3 read in-memory metrics). §8 edge cases → covered by tests in Tasks 4/5/6. §10 testing → Tasks 1-9 unit tests + Task 10 golden/sweep. §11 tunables → all are constants in `moat/scoring.py`, swept in Task 10.

**Deliberate deviation from the spec:** §6/§6.1 mention an optional `backend/moat/models.py` (`MoatResult`) *or* folding `moat_score` into `ScreenerResult`. This plan folds into `ScreenerResult` (mirrors how `quality_score` travels) and does **not** create `moat/models.py` — it would be an unused type. If a future ticker-detail panel needs a richer object, add it then.

**2. Placeholder scan** — no TBD/TODO/"add error handling"/"similar to Task N" left; every code step shows the actual code; every test step shows the actual assertions.

**3. Type consistency** — `score(m, profile) -> (float | None, dict)` is used identically in Tasks 3-7 (engine imports it as `moat_score`). `_return_axis` keys (`level`/`hurdle`/`series`/`spot`/`five`/`variant`) are set in Task 3 and read in Tasks 4-6. Band names (`A1_ROIC_BANDS`, `A2_SPREAD_BANDS`, `B2_COV_BANDS`, `GROSS_STDEV_BANDS`, `OP_STDEV_BANDS`, `MARGIN_TRAJ_BANDS`, `C1_FCF_BANDS`) are defined once and referenced consistently. `ScreenerMetrics` field names in Task 1 match their reads in Tasks 3/5/6. Database column S / index 18 is consistent across `screener_sheets._mirror_moat_score`, `sheets._row_to_database_row`, and the `A:S` range. `moatScoreColor` and the `moat` filter/sort keys are consistent across `types.ts`, `Database.tsx`, and `watchlists.ts`.

One cross-task note surfaced by review and handled inline: Task 3's `test_magnitude_only_score_is_renormalized_to_100` asserts `val is not None`, which only holds once Task 5 supplies ≥ `MOAT_MIN_PILLARS` pillars. Step 4 of both Task 3 and Task 5 calls this out explicitly so an executor running strictly task-by-task isn't surprised.
