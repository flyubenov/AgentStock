# Revenue-coupled Growth Cap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat `0.20` near-term growth cap in the valuation engine with a gentle, revenue-coupled, profitability-gated cap (0.20 → 0.25) so genuine hyper-growers earn a modest, bounded increment of growth credit.

**Architecture:** Two pure helpers (`_growth_cap`, `_cap_eligible`) added to `backend/valuation/engine.py`, wired into the existing `build_scenarios` in place of its two literal `0.20` constants. The elevated cap rides only the normal bounded-horizon path; the DDM/perpetuity path and distorted-earnings names keep the flat 0.20. No new cross-module data.

**Tech Stack:** Python 3.14, pytest. No new dependencies.

## Global Constraints

- Ceiling is `0.25`; base/floor is `0.20`; slope is `0.125` (cap reaches ceiling at revenue growth g = 0.60). Copy these exact values.
- Growth source: statement YoY (`fin["revenue_growth_stmt"]`) when not None, else info `fin["revenue_growth"]`, else `0.0`.
- Profitability gate: elevated cap applies only when `fcf_ttm > 0` OR (`ebitda_ttm > 0` AND OCF > 0), where OCF is `fin["ocf_ttm"]` falling back to `fin["operating_cashflow"]`.
- The elevated cap applies only when `distorted_cap >= 0.20` (the normal path). The DDM path passes `distorted_cap = SUSTAINABLE_CEIL (0.039)` and must keep the 0.20 clamp.
- Universal: no market-cap carve-out.
- Do not touch the size-coupled fade, the P/E leg, or any other model.
- Run all tests from the `backend/` directory with `python -m pytest`.

---

### Task 1: `_growth_cap` pure function

**Files:**
- Modify: `backend/valuation/engine.py` (add constants near the existing module constants at the top, ~line 18; add helper near the other `_`-helpers)
- Test: `backend/tests/test_engine.py`

**Interfaces:**
- Produces: `engine.GROWTH_CAP_BASE = 0.20`, `engine.GROWTH_CAP_CEIL = 0.25`, `engine.GROWTH_CAP_SLOPE = 0.125`, and `engine._growth_cap(g: float) -> float`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_engine.py`:

```python
def test_growth_cap_below_threshold_is_base():
    assert engine._growth_cap(0.10) == pytest.approx(0.20)
    assert engine._growth_cap(0.20) == pytest.approx(0.20)


def test_growth_cap_ramps_linearly():
    assert engine._growth_cap(0.30) == pytest.approx(0.2125)
    assert engine._growth_cap(0.40) == pytest.approx(0.225)
    assert engine._growth_cap(0.50) == pytest.approx(0.2375)


def test_growth_cap_saturates_at_ceiling():
    assert engine._growth_cap(0.60) == pytest.approx(0.25)
    assert engine._growth_cap(0.70) == pytest.approx(0.25)
    assert engine._growth_cap(1.68) == pytest.approx(0.25)   # IREN-shape backstop
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py -k growth_cap -v`
Expected: FAIL with `AttributeError: module 'valuation.engine' has no attribute '_growth_cap'`

- [ ] **Step 3: Add constants and the helper**

In `backend/valuation/engine.py`, add after the existing `FCF_EBITDA_FLOOR = 0.15` constant block (near line 18):

```python
# Revenue-coupled growth cap: hyper-growers earn a modest, bounded increment of
# near-term growth credit above the flat base. The ramp is deliberately shallow
# (+1pp of cap per 8pp of growth) and the 0.25 ceiling — reached at g=0.60 — is the
# ultimate backstop against a noisy-high growth reading.
GROWTH_CAP_BASE = 0.20
GROWTH_CAP_CEIL = 0.25
GROWTH_CAP_SLOPE = 0.125
```

Add the helper near the other module-level `_`-helpers (e.g. just above `_earnings_distorted`):

```python
def _growth_cap(g: float) -> float:
    """Near-term growth cap coupled to revenue growth: flat GROWTH_CAP_BASE until
    growth passes GROWTH_CAP_BASE, then a gentle linear ramp to GROWTH_CAP_CEIL
    (reached at g=0.60). The ceiling bounds a noisy-high growth reading."""
    return min(GROWTH_CAP_CEIL,
               GROWTH_CAP_BASE + GROWTH_CAP_SLOPE * max(0.0, g - GROWTH_CAP_BASE))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -k growth_cap -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/engine.py backend/tests/test_engine.py
git commit -m "feat(valuation): add revenue-coupled _growth_cap helper"
```

---

### Task 2: `_cap_eligible` profitability gate

**Files:**
- Modify: `backend/valuation/engine.py` (add helper near `_growth_cap`)
- Test: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: nothing from Task 1 (independent helper).
- Produces: `engine._cap_eligible(fin: dict) -> bool`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_engine.py`:

```python
def test_cap_eligible_fcf_positive():
    assert engine._cap_eligible({"fcf_ttm": 100.0}) is True


def test_cap_eligible_burner_excluded():
    # FCF < 0 and OCF < 0 -> genuine cash burn, not eligible
    assert engine._cap_eligible(
        {"fcf_ttm": -50.0, "ebitda_ttm": -10.0, "ocf_ttm": -20.0}) is False


def test_cap_eligible_capex_reroute_shape():
    # FCF < 0 but EBITDA > 0 and OCF > 0 (IREN-like) -> eligible via the OCF branch
    assert engine._cap_eligible(
        {"fcf_ttm": -50.0, "ebitda_ttm": 100.0, "ocf_ttm": 80.0}) is True


def test_cap_eligible_ocf_info_fallback():
    # ocf_ttm absent -> falls back to operating_cashflow (info)
    assert engine._cap_eligible(
        {"fcf_ttm": -50.0, "ebitda_ttm": 100.0, "operating_cashflow": 80.0}) is True


def test_cap_eligible_no_cashflow_data_not_eligible():
    assert engine._cap_eligible({"earnings_growth": 0.5}) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py -k cap_eligible -v`
Expected: FAIL with `AttributeError: module 'valuation.engine' has no attribute '_cap_eligible'`

- [ ] **Step 3: Add the helper**

In `backend/valuation/engine.py`, add directly below `_growth_cap`:

```python
def _cap_eligible(fin: dict) -> bool:
    """The elevated growth cap applies only to names demonstrating economics:
    FCF-positive, or operationally cash-generative (EBITDA > 0 and OCF > 0). This
    reuses the capex-reroute cash-generation signal, so capex-heavy reinvestors
    (negative FCF, positive EBITDA/OCF — e.g. IREN) still qualify. OCF falls back
    to the info figure when the statement value is absent."""
    fcf = fin.get("fcf_ttm")
    if fcf is not None and fcf > 0:
        return True
    ebitda = fin.get("ebitda_ttm") or 0
    ocf = fin.get("ocf_ttm")
    if ocf is None:
        ocf = fin.get("operating_cashflow")
    return ebitda > 0 and ocf is not None and ocf > 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -k cap_eligible -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/engine.py backend/tests/test_engine.py
git commit -m "feat(valuation): add _cap_eligible profitability gate"
```

---

### Task 3: Wire the cap into `build_scenarios`

**Files:**
- Modify: `backend/valuation/engine.py` — `build_scenarios` (currently ~lines 44-67)
- Test: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `engine._growth_cap` (Task 1), `engine._cap_eligible` (Task 2), `engine.GROWTH_CAP_BASE`, `engine._earnings_distorted` (existing), `engine.SUSTAINABLE_CEIL` (existing).
- Produces: unchanged public signature `build_scenarios(fin: dict, distorted_cap: float = 0.20) -> dict` with keys `optimistic` / `realistic` / `pessimistic`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_engine.py`:

```python
def _hypergrower_fin(**over):
    fin = {"fcf_ttm": 3.9e9, "ebitda_ttm": 4.8e9, "ocf_ttm": 4.0e9,
           "revenue_growth_stmt": 0.70, "revenue_growth": 0.59,
           "earnings_growth": 1.13}
    fin.update(over)
    return fin


def test_build_scenarios_elevated_cap_for_eligible_hypergrower():
    # statement growth 0.70 -> cap saturates at the 0.25 ceiling
    s = engine.build_scenarios(_hypergrower_fin())
    assert s["realistic"] == pytest.approx(0.25)
    assert s["optimistic"] == pytest.approx(0.25)     # capped at the elevated ceiling


def test_build_scenarios_statement_growth_preferred_over_info():
    # info 0.30 would give 0.2125; statement 0.70 wins -> 0.25
    s = engine.build_scenarios(_hypergrower_fin(revenue_growth_stmt=0.70, revenue_growth=0.30))
    assert s["realistic"] == pytest.approx(0.25)


def test_build_scenarios_info_growth_when_stmt_absent():
    # no statement growth -> info 0.40 -> _growth_cap(0.40) = 0.225
    s = engine.build_scenarios(
        _hypergrower_fin(revenue_growth_stmt=None, revenue_growth=0.40, earnings_growth=1.0))
    assert s["realistic"] == pytest.approx(0.225)


def test_build_scenarios_ceiling_backstop_on_absurd_growth():
    s = engine.build_scenarios(_hypergrower_fin(revenue_growth_stmt=3.0))
    assert s["realistic"] == pytest.approx(0.25)      # 300% growth still capped


def test_build_scenarios_ineligible_burner_stays_base():
    # FCF < 0 and OCF < 0 -> not eligible -> cap stays 0.20 despite 70% growth
    s = engine.build_scenarios(
        _hypergrower_fin(fcf_ttm=-1e8, ebitda_ttm=-1e7, ocf_ttm=-2e7, revenue_growth_stmt=0.70))
    assert s["realistic"] == pytest.approx(0.20)


def test_build_scenarios_ddm_path_not_elevated_for_hypergrower():
    # DDM copy (distorted_cap=SUSTAINABLE_CEIL) must NOT receive the elevated cap
    s = engine.build_scenarios(_hypergrower_fin(), distorted_cap=engine.SUSTAINABLE_CEIL)
    assert s["realistic"] <= 0.20


def test_build_scenarios_distorted_earnings_not_elevated():
    # eg < 0, rg > 0 -> distorted: raw pre-capped at distorted_cap (0.20), so even an
    # eligible hyper-grower does not get the elevated cap
    s = engine.build_scenarios(
        _hypergrower_fin(earnings_growth=-0.09, revenue_growth=0.70, revenue_growth_stmt=0.70))
    assert s["realistic"] == pytest.approx(0.20)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py -k build_scenarios -v`
Expected: the seven new tests FAIL (realistic == 0.20 where 0.25/0.225 expected); the existing `build_scenarios` tests still PASS.

- [ ] **Step 3: Rewrite `build_scenarios`**

Replace the body of `build_scenarios` in `backend/valuation/engine.py`. Keep the existing docstring; insert the cap computation before the `raw` block and swap both `0.20` literals for `cap`:

```python
def build_scenarios(fin: dict, distorted_cap: float = 0.20) -> dict:
    """Per-stock capped growth scenarios (spec decision #1).

    When GAAP earnings growth is negative while revenue is still growing, the
    earnings figure is treated as distorted (acquisition amortization / one-off
    charges, e.g. ABBV/ETN) rather than a real decline. Growth is then sourced
    from revenue growth. A genuine decline (revenue also falling) stays on the
    normal floored path.

    distorted_cap bounds the revenue-sourced rate. The default (0.20, the normal
    ceiling) is for the bounded-horizon legs (DCF/EV/EBITDA/PE), which can carry
    the real rate. The perpetuity-based DDM passes distorted_cap=SUSTAINABLE_CEIL
    so Gordon growth can't overshoot the discount rate.

    The near-term cap is revenue-coupled: an eligible (cash-generative) hyper-grower
    earns up to GROWTH_CAP_CEIL (0.25), sourced statement-YoY-first. The elevated cap
    rides only the normal bounded-horizon path (distorted_cap >= GROWTH_CAP_BASE);
    the DDM path keeps the flat base."""
    cap = GROWTH_CAP_BASE
    if distorted_cap >= GROWTH_CAP_BASE and _cap_eligible(fin):
        g = fin.get("revenue_growth_stmt")
        if g is None:
            g = fin.get("revenue_growth") or 0.0
        cap = _growth_cap(g)
    if _earnings_distorted(fin):
        raw = min(fin.get("revenue_growth") or 0, distorted_cap)
    else:
        raw = (fin.get("earnings_growth") or fin.get("revenue_growth")
               or fin.get("revenue_growth_stmt") or 0.07)
    base = max(0.02, min(float(raw), cap))
    return {
        "optimistic": min(base + 0.05, cap),
        "realistic": base,
        "pessimistic": max(base - 0.04, 0.02),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -k build_scenarios -v`
Expected: PASS (all new + all existing `build_scenarios` tests).

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/engine.py backend/tests/test_engine.py
git commit -m "feat(valuation): revenue-coupled growth cap in build_scenarios"
```

---

### Task 4: End-to-end guard + full-suite verification

**Files:**
- Test: `backend/tests/test_engine.py`

**Interfaces:**
- Consumes: `engine.evaluate(fin: dict) -> dict` (existing) — returns a dict with a `fair_value` float.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_engine.py`. This isolates the cap effect: two GROWTH names identical except for the growth figure that feeds the cap, both with the same capped `raw` (earnings_growth 1.0), so the only difference is 0.25 vs 0.20:

```python
def _growth_evalfin(**over):
    fin = {"ticker": "TST", "company_name": "Test", "current_price": 100.0,
           "market_cap": 150e9, "shares_outstanding": 3e8, "revenue_ttm": 6e9,
           "ebitda_ttm": 4.8e9, "ev_ebitda": 25.0, "ev_sales": 10.0,
           "fcf_ttm": 3.9e9, "ocf_ttm": 4.0e9, "net_debt": 1e9, "eps_ttm": 11.0,
           "trailing_pe": 39.0, "forward_pe": 20.0, "forward_eps": 21.0,
           "earnings_growth": 1.0, "dividend_yield": 0.0,
           "sector": "Communication Services", "industry": "Advertising Agencies",
           "return_on_equity": 0.3, "book_value_per_share": 10.0}
    fin.update(over)
    return fin


def test_evaluate_hypergrower_fv_exceeds_slow_growth_twin():
    fast = engine.evaluate(_growth_evalfin(revenue_growth=0.59, revenue_growth_stmt=0.70))
    slow = engine.evaluate(_growth_evalfin(revenue_growth=0.11, revenue_growth_stmt=0.11))
    assert fast["stock_type"] == "GROWTH"
    assert slow["stock_type"] == "GROWTH"
    # Same everything except the cap (0.25 vs 0.20) -> fast fair value is strictly higher
    assert fast["fair_value"] > slow["fair_value"]
```

- [ ] **Step 2: Run test to verify it fails (before Task 3 is applied) or passes (after)**

Run: `python -m pytest tests/test_engine.py::test_evaluate_hypergrower_fv_exceeds_slow_growth_twin -v`
Expected: PASS (Task 3 is already implemented). If it does not pass, the wiring in Task 3 is wrong — fix Task 3 before continuing.

- [ ] **Step 3: Run the full backend test suite**

Run: `python -m pytest -q`
Expected: all tests PASS (no regressions in `test_engine.py`, `test_models.py`, `test_engine_run.py`, `test_classifier.py`, or the screener suites). If any previously-green test now fails, stop and reconcile — the change must not move the untouched anchors.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_engine.py
git commit -m "test(valuation): e2e guard that eligible hyper-growers lift FV"
```

---

## Notes for the implementer

- **Why existing `build_scenarios` tests stay green:** their fins carry no cash-flow fields, so `_cap_eligible` returns `False` and the cap stays at `0.20` exactly as before. Do not add cash-flow fields to those fixtures.
- **Live-data expectations (context, not asserted):** with real yfinance data this change lifts APP ~+21% ($349→$423, −5.8% vs price), NVDA ~+25% (−14% vs price), IREN ~+32% (−47% vs price); sub-20%-growth names (MSFT/KLAC/NFLX/TSLA/ETN) are unchanged. No anchor flips to "undervalued." These come from the sweep in the spec; the unit/e2e tests above encode the mechanism deterministically without hitting the network.
- **Ordering safety:** Tasks 1 and 2 are independent; Task 3 depends on both; Task 4 depends on Task 3.
