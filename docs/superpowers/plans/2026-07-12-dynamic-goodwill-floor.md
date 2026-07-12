# Dynamic Goodwill Floor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lower the Section II acquisition-ROIC goodwill-share floor from a flat 0.30 to 0.15 when the ex-goodwill ROIC clears WACC while reported ROIC sits below it (the "WACC crossover"), so VST is corrected without regressing AMD or firing on genuine value-destroyers.

**Architecture:** A single-file change in `backend/screener/scoring.py`. Add a `_wacc_crossover(m)` helper and an `_effective_goodwill_floor(m)` helper; change the one goodwill-share comparison inside the existing `_acquisition_distorted(m)` to use the dynamic floor. All downstream behavior (the ex-goodwill Section II substitution and the `roic_adjustment` breakdown) is unchanged. Quality-Score-only — no Fair-Value, no frontend changes.

**Tech Stack:** Python 3.14, pytest. Pure functions over the `ScreenerMetrics` pydantic model.

## Global Constraints

- Change is confined to `backend/screener/scoring.py` and `backend/tests/test_screener_scoring.py`. No other files.
- `GOODWILL_SHARE_FLOOR = 0.30` stays; add `GOODWILL_SHARE_FLOOR_XOVER = 0.15`.
- Crossover definition (verbatim): `roic_ttm < wacc <= roic_ex_goodwill`.
- The `roic_ex_goodwill > roic_ttm` lift check and the P/E-trough gate (`trailing_pe / forward_pe > DEPRESSED_PE_RATIO`, 1.5) are retained and apply to **both** floor tiers.
- No change to `GOODWILL_SHARE_FLOOR`, the beta cap, ROTE, Section III, the FV engine, or the frontend.
- Run backend commands from `backend/` (that is the import root: `from screener.scoring import ...`).

---

### Task 1: Dynamic goodwill floor logic + unit tests

**Files:**
- Modify: `backend/screener/scoring.py` (around the `GOODWILL_SHARE_FLOOR` block, ~line 154, and `_acquisition_distorted`, ~line 157)
- Test: `backend/tests/test_screener_scoring.py`

**Interfaces:**
- Consumes: `ScreenerMetrics` fields `roic_ttm`, `roic_ex_goodwill`, `wacc`, `goodwill_intangible_share`, `trailing_pe`, `forward_pe`; existing constant `DEPRESSED_PE_RATIO` (1.5).
- Produces:
  - `GOODWILL_SHARE_FLOOR_XOVER: float = 0.15`
  - `_wacc_crossover(m: ScreenerMetrics) -> bool`
  - `_effective_goodwill_floor(m: ScreenerMetrics) -> float`
  - `_acquisition_distorted(m: ScreenerMetrics) -> bool` (signature unchanged; now uses the dynamic floor)

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_screener_scoring.py` (after `test_acquisition_distortion_detection`, near line 347):

```python
def test_wacc_crossover_detection():
    from screener.scoring import _wacc_crossover
    # VST-like: reported ROIC below WACC, ex-goodwill ROIC at/above WACC -> crossover.
    assert _wacc_crossover(ScreenerMetrics(
        roic_ttm=7.8, wacc=9.6, roic_ex_goodwill=10.1)) is True
    # Reported ROIC already clears WACC -> no rescue needed, not a crossover.
    assert _wacc_crossover(ScreenerMetrics(
        roic_ttm=11.0, wacc=9.6, roic_ex_goodwill=12.0)) is False
    # AMD-like: even the ex-goodwill ROIC is still below WACC -> not a crossover.
    assert _wacc_crossover(ScreenerMetrics(
        roic_ttm=5.1, wacc=14.5, roic_ex_goodwill=13.8)) is False
    # Missing data -> False.
    assert _wacc_crossover(ScreenerMetrics(roic_ttm=7.8, wacc=None,
                                           roic_ex_goodwill=10.1)) is False


def test_effective_goodwill_floor_is_dynamic():
    from screener.scoring import (_effective_goodwill_floor,
                                  GOODWILL_SHARE_FLOOR, GOODWILL_SHARE_FLOOR_XOVER)
    # Crossover present -> lowered floor.
    assert _effective_goodwill_floor(ScreenerMetrics(
        roic_ttm=7.8, wacc=9.6, roic_ex_goodwill=10.1)) == GOODWILL_SHARE_FLOOR_XOVER
    # No crossover -> strict floor.
    assert _effective_goodwill_floor(ScreenerMetrics(
        roic_ttm=5.1, wacc=14.5, roic_ex_goodwill=13.8)) == GOODWILL_SHARE_FLOOR


def test_dynamic_floor_catches_vst_without_regressing_amd():
    from screener.scoring import _acquisition_distorted
    # VST-like: goodwill 0.23 (below the 0.30 flat floor) BUT the WACC crossover holds
    # (7.8 < 9.6 <= 10.1) -> the floor drops to 0.15 -> fires.
    vst = ScreenerMetrics(goodwill_intangible_share=0.23, roic_ttm=7.8, wacc=9.6,
                          roic_ex_goodwill=10.1, trailing_pe=26.6, forward_pe=14.7)
    assert _acquisition_distorted(vst) is True
    # Same VST metrics but no crossover (WACC bumped above the ex-goodwill ROIC):
    # floor stays 0.30, 0.23 < 0.30 -> does NOT fire. Isolates the floor mechanism.
    vst_no_xover = ScreenerMetrics(goodwill_intangible_share=0.23, roic_ttm=7.8,
                                   wacc=10.5, roic_ex_goodwill=10.1,
                                   trailing_pe=26.6, forward_pe=14.7)
    assert _acquisition_distorted(vst_no_xover) is False
    # AMD-like no-regression: goodwill 0.63, ex-goodwill ROIC 13.8 still < WACC 14.5
    # (no crossover) -> qualifies via the unchanged 0.30 floor.
    amd = ScreenerMetrics(goodwill_intangible_share=0.63, roic_ttm=5.1, wacc=14.5,
                          roic_ex_goodwill=13.8, trailing_pe=185.0, forward_pe=42.0)
    assert _acquisition_distorted(amd) is True


def test_dynamic_floor_does_not_rescue_value_destroyer():
    from screener.scoring import _acquisition_distorted
    # INTC-like negative control: goodwill 0.17 would clear the lowered 0.15 floor, but
    # the tangible business earns far below its cost of capital (1.6 < 13.6 -> no
    # crossover) and there is no P/E-trough -> correctly NOT rescued.
    intc = ScreenerMetrics(goodwill_intangible_share=0.17, roic_ttm=1.3, wacc=13.6,
                           roic_ex_goodwill=1.6, trailing_pe=None, forward_pe=None)
    assert _acquisition_distorted(intc) is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_screener_scoring.py::test_wacc_crossover_detection tests/test_screener_scoring.py::test_effective_goodwill_floor_is_dynamic tests/test_screener_scoring.py::test_dynamic_floor_catches_vst_without_regressing_amd tests/test_screener_scoring.py::test_dynamic_floor_does_not_rescue_value_destroyer -v`

Expected: FAIL — `ImportError: cannot import name '_wacc_crossover'` (and `_effective_goodwill_floor`, `GOODWILL_SHARE_FLOOR_XOVER`).

- [ ] **Step 3: Add the constant and helpers**

In `backend/screener/scoring.py`, locate the `GOODWILL_SHARE_FLOOR = 0.30` line (~154) and the block comment above `_acquisition_distorted`. Add the new constant and two helpers immediately **before** `def _acquisition_distorted(m: ScreenerMetrics) -> bool:`:

```python
GOODWILL_SHARE_FLOOR = 0.30

# When a company's tangible (ex-goodwill) ROIC already clears its cost of capital while
# its reported ROIC sits below it, that crossover is itself direct evidence the reported
# weakness is an acquisition artifact — so a smaller goodwill share is sufficient proof
# and the floor drops from 0.30 to 0.15. AMD keeps qualifying via the 0.30 floor: its
# ex-goodwill ROIC (13.8) is still below its beta-capped WACC (14.5), so it has no
# crossover. VST does (reported 7.8 < WACC 9.6 <= ex-goodwill 10.1) at 0.23 goodwill share.
GOODWILL_SHARE_FLOOR_XOVER = 0.15


def _wacc_crossover(m: ScreenerMetrics) -> bool:
    if m.roic_ttm is None or m.roic_ex_goodwill is None or m.wacc is None:
        return False
    return m.roic_ttm < m.wacc <= m.roic_ex_goodwill


def _effective_goodwill_floor(m: ScreenerMetrics) -> float:
    return GOODWILL_SHARE_FLOOR_XOVER if _wacc_crossover(m) else GOODWILL_SHARE_FLOOR
```

Keep the existing explanatory comment block that documents `GOODWILL_SHARE_FLOOR`; place the new constant/helpers after it (right before the function).

- [ ] **Step 4: Wire the dynamic floor into `_acquisition_distorted`**

In `_acquisition_distorted`, replace the fixed floor comparison. Change:

```python
    if (m.goodwill_intangible_share is None
            or m.goodwill_intangible_share < GOODWILL_SHARE_FLOOR):
        return False
```

to:

```python
    if (m.goodwill_intangible_share is None
            or m.goodwill_intangible_share < _effective_goodwill_floor(m)):
        return False
```

Leave the rest of the function (the `roic_ex_goodwill <= roic_ttm` lift check and the P/E-trough gate) exactly as-is.

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_screener_scoring.py::test_wacc_crossover_detection tests/test_screener_scoring.py::test_effective_goodwill_floor_is_dynamic tests/test_screener_scoring.py::test_dynamic_floor_catches_vst_without_regressing_amd tests/test_screener_scoring.py::test_dynamic_floor_does_not_rescue_value_destroyer -v`

Expected: 4 passed.

- [ ] **Step 6: Run the full scoring test file to confirm no regression**

Run: `cd backend && python -m pytest tests/test_screener_scoring.py -v`

Expected: all pass, including the pre-existing `test_acquisition_distortion_detection`, `test_acquisition_distortion_lifts_section_ii`, and `test_acquisition_distortion_breakdown_and_lift` (AMD path unchanged).

- [ ] **Step 7: Commit**

```bash
git add backend/screener/scoring.py backend/tests/test_screener_scoring.py
git commit -m "fix(screener): dynamic goodwill floor keyed to WACC crossover

Lower the acquisition-ROIC goodwill-share floor from a flat 0.30 to 0.15
when the ex-goodwill ROIC clears WACC while reported ROIC is below it,
catching VST (23% goodwill) without regressing AMD or rescuing value
destroyers (INTC). Quality-Score-only.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: End-to-end Section II lift + live VST verification

**Files:**
- Test: `backend/tests/test_screener_scoring.py`

**Interfaces:**
- Consumes: `section_scores(m, profile)` and `score(m, sector)` from `screener.scoring`; the dynamic floor from Task 1.
- Produces: no new symbols — validation only.

- [ ] **Step 1: Write the failing end-to-end test**

Add to `backend/tests/test_screener_scoring.py` (after the tests from Task 1):

```python
def test_dynamic_floor_lifts_section_ii_for_vst_like():
    # VST-like DEFENSIVE_INCOME name: goodwill 0.23 with a WACC crossover. The dynamic
    # floor lets the ex-goodwill ROIC score Section II, lifting it (and the headline)
    # versus the same metrics with the crossover removed (WACC above ex-goodwill ROIC).
    base = dict(
        revenue_cagr_3y=8.9, fcf_margin=7.4, op_margin=26.6, op_margin_trajectory=20.1,
        gross_margin=38.6, roic_ttm=7.8, roic_5y_avg=8.3, roic_wacc_spread=-1.8,
        rote=None, roic_ex_goodwill=10.1, roic_5y_ex_goodwill=11.0,
        goodwill_intangible_share=0.23,
        net_debt_ebitda=2.84, net_debt_fcf=14.6, ocf_capex=1.48,
        shares_cagr_3y=-4.6, sbc_pct_rev=0.64, earnings_quality=4.3,
        insider_ownership=0.79, shareholder_yield=2.85,
        net_income=944e6, fcf=1318e6, ebitda=6790e6,
        trailing_pe=26.6, forward_pe=14.7,
    )
    distorted = ScreenerMetrics(**base, wacc=9.6, sector="Utilities")        # crossover
    normal = ScreenerMetrics(**{**base, "wacc": 10.5}, sector="Utilities")   # no crossover
    s_dist = section_scores(distorted, "DEFENSIVE_INCOME")
    s_norm = section_scores(normal, "DEFENSIVE_INCOME")
    assert s_dist["II"] > s_norm["II"]

    q_d, _, profile, bd = score(distorted, "Utilities")
    q_n, _, _, bd_n = score(normal, "Utilities")
    assert profile == "DEFENSIVE_INCOME"
    assert "roic_adjustment" in bd
    assert "roic_adjustment" not in bd_n
    assert bd["roic_adjustment"]["tangible_roic"] == pytest.approx(10.1, abs=0.1)
    assert bd["pre_profit"] is None            # profitable -> not a pre-profit burn
    assert q_d > q_n
    assert q_d == pytest.approx(5.7, abs=0.2)
```

- [ ] **Step 2: Run it to verify it passes**

Run: `cd backend && python -m pytest tests/test_screener_scoring.py::test_dynamic_floor_lifts_section_ii_for_vst_like -v`

Expected: PASS (the Task 1 code already makes this green; if it fails on the `5.7` assertion, do NOT change the code — re-verify the expected value against the live run in Step 4 and adjust only the test's expected number to the live headline).

- [ ] **Step 3: Run the entire backend test suite**

Run: `cd backend && python -m pytest -q`

Expected: all pass (prior baseline was 184 passing + the new tests).

- [ ] **Step 4: Live end-to-end verification against real VST data**

Run:

```bash
cd backend && python -c "
import asyncio, time
from screener.engine import run as srun
for i in range(4):
    r = asyncio.run(srun('VST'))
    if r.status=='completed' and r.metrics.get('roic_ex_goodwill') is not None: break
    time.sleep(4)
print('score', r.quality_score, 'secII', r.section_scores.get('II'))
print('roic_adjustment', r.score_breakdown.get('roic_adjustment'))
"
```

Expected: `score 5.7`, `secII ~6.17`, and a populated `roic_adjustment` block (reported_roic ~7.8, tangible_roic ~10.1, goodwill_intangible_share 0.23). Confirm AMD is unchanged:

```bash
cd backend && python -c "
import asyncio
from screener.engine import run as srun
r = asyncio.run(srun('AMD'))
print('AMD score', r.quality_score, 'secII', r.section_scores.get('II'))
"
```

Expected: `AMD score 7.2` (unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_screener_scoring.py
git commit -m "test(screener): end-to-end VST dynamic-goodwill-floor lift (5.0 -> 5.7)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Dynamic floor keyed to crossover → Task 1 (`_wacc_crossover`, `_effective_goodwill_floor`, wired into `_acquisition_distorted`).
- Crossover defined as `roic_ttm < wacc <= roic_ex_goodwill` → Task 1 Step 3, matches spec verbatim.
- No AMD regression (no crossover, 0.30 path) → Task 1 test `test_dynamic_floor_catches_vst_without_regressing_amd` + Task 2 Step 4 live check.
- INTC negative control → Task 1 test `test_dynamic_floor_does_not_rescue_value_destroyer`.
- VST 5.0 → 5.7, `roic_adjustment` recorded, FV/frontend untouched → Task 2.
- P/E-trough + lift gates retained on both tiers → Task 1 Step 4 leaves them intact; covered by the no-P/E INTC control and the crossover VST case.

**Placeholder scan:** none — all steps have concrete code and commands.

**Type consistency:** `_wacc_crossover`/`_effective_goodwill_floor` take `ScreenerMetrics`, return `bool`/`float`; used consistently in `_acquisition_distorted`. Constant names `GOODWILL_SHARE_FLOOR_XOVER` consistent across Task 1 code and tests. Breakdown key `roic_adjustment` and field `tangible_roic` match the existing `score()` breakdown shape.
