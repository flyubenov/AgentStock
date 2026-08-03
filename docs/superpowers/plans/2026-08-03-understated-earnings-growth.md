# Understated-Earnings-Growth Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 5th `build_scenarios` growth guard, `_earnings_understated`, that re-sources the realistic growth from the statement earnings lines when the quarterly `earnings_growth` is an understated outlier below the company's own annual trajectory (fixes NFLX −30% and NXT −45%, both too bearish).

**Architecture:** Mirror of the existing `_earnings_non_operating` guard. A pure predicate `_earnings_understated(fin)` detects the pattern (quarterly `earnings_growth` below both annual statement earnings lines, with forward EPS rising); a new `elif` branch in `build_scenarios`, placed last before the final `else`, re-sources `raw = min(net_income_growth_stmt, op_income_growth_stmt)`. The existing `base = max(0.02, min(raw, cap))` clamp and the scenario band are untouched.

**Tech Stack:** Python 3.14, pytest (`asyncio_mode=auto`). Run tests from `backend/`.

## Global Constraints

- No new module-level constant. The detector is gateless (no numeric gap threshold).
- No new network fetch. `net_income_growth_stmt` and `op_income_growth_stmt` are already populated by the EV/EBITDA-history fetch (`engine.py` ~725–726); the predicate only reads existing `fin` keys.
- The predicate must read only statement-annual + forward-EPS fields — never mix a quarterly rate against an annual one (the [[bwxt-non-operating-growth-source]] like-with-like discipline).
- Guard order is fixed: `_earnings_distorted` → `_earnings_non_operating` → `_earnings_inflated` → `_earnings_outpaces_revenue` → **`_earnings_understated`** → `else`. The new guard is last so every existing guard keeps priority.
- Baseline is green: 421 tests pass before any change.
- All work happens in worktree `understated-earnings-growth-guard`, branch `worktree-understated-earnings-growth-guard`. Tests live in `backend/tests/test_engine.py`; the engine is `backend/valuation/engine.py`.

---

### Task 1: `_earnings_understated` predicate

**Files:**
- Modify: `backend/valuation/engine.py` (add function directly after `_earnings_outpaces_revenue`, ~line 260)
- Test: `backend/tests/test_engine.py` (add helper + tests near the `_non_operating_growth_fin` block, ~line 907)

**Interfaces:**
- Consumes: a `fin` dict with keys `earnings_growth`, `net_income_growth_stmt`, `op_income_growth_stmt`, `forward_eps`, `eps_ttm`.
- Produces: `engine._earnings_understated(fin: dict) -> bool`. Used by Task 2's `build_scenarios` branch.

- [ ] **Step 1: Write the failing tests + fixture**

Add to `backend/tests/test_engine.py` (after the `_non_operating_growth_fin` tests):

```python
def _understated_growth_fin(**over):
    """NXT-shaped: quarterly earnings_growth (2.9%) sits below BOTH annual statement
    earnings lines (net income +15.1%, operating income +9.1%) while forward EPS rises
    (5.80 > 3.87). The quarterly print is an understated single-quarter outlier, not a
    real slowdown. Mirror of _non_operating_growth_fin but earnings understated LOW."""
    fin = _large_cap_fin(market_cap=13_800_000_000, shares_outstanding=151_653_265,
                         current_price=89.87, revenue_ttm=3_630_307_072,
                         fcf_ttm=513_634_000, operating_cashflow=562_911_000,
                         ebitda_ttm=745_852_032, eps_ttm=3.87, forward_eps=5.79648,
                         net_debt=-1_213_897_984, trailing_pe=23.22, forward_pe=15.50,
                         dividend_rate=0, dividend_yield=0, payout_ratio=0,
                         revenue_growth=0.082, earnings_growth=0.029,
                         revenue_growth_stmt=0.203, net_income_growth_stmt=0.151,
                         op_income_growth_stmt=0.091)
    fin.update(over)
    return fin


def test_earnings_understated_fires_on_low_quarterly_vs_annual():
    # Quarterly eg below BOTH annual lines, forward EPS rising -> understated.
    assert engine._earnings_understated(_understated_growth_fin()) is True


def test_earnings_understated_requires_both_annual_lines_above_eg():
    # If either annual line is at/below the quarterly eg, the quarterly print is NOT a
    # low outlier — the annual trajectory does not corroborate it. Must not fire.
    assert engine._earnings_understated(
        _understated_growth_fin(op_income_growth_stmt=0.029)) is False   # op == eg
    assert engine._earnings_understated(
        _understated_growth_fin(net_income_growth_stmt=0.020)) is False   # ni < eg


def test_earnings_understated_requires_positive_annual_lines():
    # A negative annual line is a decline signal, not an understated grower. Must not fire.
    assert engine._earnings_understated(
        _understated_growth_fin(op_income_growth_stmt=-0.05)) is False


def test_earnings_understated_requires_positive_quarterly_eg():
    # eg <= 0 is handled by the distorted/decline paths, not this guard.
    assert engine._earnings_understated(
        _understated_growth_fin(earnings_growth=0.0)) is False
    assert engine._earnings_understated(
        _understated_growth_fin(earnings_growth=-0.1)) is False


def test_earnings_understated_requires_forward_eps_above_trailing():
    # Forward EPS must corroborate the upward re-source. feps <= teps -> do not fire.
    assert engine._earnings_understated(
        _understated_growth_fin(forward_eps=3.80)) is False   # < eps_ttm 3.87


def test_earnings_understated_false_when_statement_lines_missing():
    # No statement reading (fetch bailed to None) is "unknown", leave the source alone.
    assert engine._earnings_understated(
        _understated_growth_fin(net_income_growth_stmt=None)) is False
    assert engine._earnings_understated(
        _understated_growth_fin(op_income_growth_stmt=None)) is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_engine.py -k earnings_understated -v`
Expected: FAIL — `AttributeError: module 'valuation.engine' has no attribute '_earnings_understated'`.

- [ ] **Step 3: Write the minimal implementation**

In `backend/valuation/engine.py`, immediately after the `_earnings_outpaces_revenue` function (~line 260), add:

```python
def _earnings_understated(fin: dict) -> bool:
    """Quarterly info `earnings_growth` is an understated outlier below the company's
    OWN annual statement trajectory — the mirror of _earnings_non_operating (which fires
    when earnings OVERSTATE the operating business). Fires when a low single-quarter YoY
    print would drag the multi-year projection below both annual earnings lines while
    forward EPS is rising. Growth is then re-sourced from min(ni, op) in build_scenarios.

    Gateless statement-corroboration (no numeric gap threshold): the "both annual lines
    exceed the quarterly eg" test is the sole discriminator — a live 20-name sweep isolates
    exactly {NFLX, NXT}. Like-with-like ANNUAL + both-lines-agree discipline from
    _earnings_non_operating: THERE ni>0 & op<=0 (overstated); HERE eg < both ni,op (>0)
    (understated). feps>teps validates the upward re-source (analyst corroboration)."""
    eg = fin.get("earnings_growth")
    if eg is None or eg <= 0:
        return False
    ni = fin.get("net_income_growth_stmt")
    op = fin.get("op_income_growth_stmt")
    if ni is None or op is None or ni <= 0 or op <= 0:
        return False
    feps, teps = fin.get("forward_eps"), fin.get("eps_ttm")
    if feps is None or teps is None or feps <= teps:
        return False
    return ni > eg and op > eg
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_engine.py -k earnings_understated -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/engine.py backend/tests/test_engine.py
git commit -m "feat(engine): _earnings_understated predicate (NFLX/NXT low-quarterly guard)"
```

---

### Task 2: Wire the re-source branch into `build_scenarios`

**Files:**
- Modify: `backend/valuation/engine.py` — `build_scenarios`, the guard chain (the `elif _earnings_outpaces_revenue(fin):` block, ~line 395–401; add a new `elif` after it, before the `else` at ~line 402)
- Test: `backend/tests/test_engine.py` (add tests after Task 1's tests)

**Interfaces:**
- Consumes: `engine._earnings_understated` (Task 1); the existing `build_scenarios(fin, distorted_cap=0.20, stock_type=None)` signature and its `base = max(0.02, min(float(raw), cap))` clamp.
- Produces: no new public symbol — `build_scenarios` now re-sources `raw = min(ni, op)` when `_earnings_understated` fires.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_engine.py` (after Task 1's tests):

```python
def test_build_scenarios_understated_resources_from_min_annual_line():
    # eg 0.029 is understated; re-source realistic base to min(ni 0.151, op 0.091) = 0.091,
    # which is below the cap so it passes through the max(0.02, min(raw, cap)) clamp intact.
    s = engine.build_scenarios(_understated_growth_fin(), stock_type="MID_CAP")
    assert s["realistic"] == pytest.approx(0.091)


def test_build_scenarios_understated_takes_lower_of_the_two_lines():
    # min(ni, op): when op is the higher line, ni (the lower) is chosen.
    s = engine.build_scenarios(
        _understated_growth_fin(net_income_growth_stmt=0.07, op_income_growth_stmt=0.12),
        stock_type="MID_CAP")
    assert s["realistic"] == pytest.approx(0.07)


def test_build_scenarios_understated_clamped_by_cap():
    # A high min(ni,op) is still bounded by the normal growth cap (NFLX: min 0.261 -> 0.20).
    # revenue_growth_stmt is set low so the cash-generative elevated cap (_growth_cap ramps
    # 0.20->0.25 on revenue growth) stays at the 0.20 base and the clamp is a clean literal.
    s = engine.build_scenarios(
        _understated_growth_fin(net_income_growth_stmt=0.261, op_income_growth_stmt=0.279,
                                revenue_growth_stmt=0.05),
        stock_type="MID_CAP")
    assert s["realistic"] == pytest.approx(0.20)


def test_build_scenarios_understated_does_not_fire_keeps_earnings_source():
    # When the guard does not fire (op == eg), the old else-branch behaviour holds:
    # realistic sources from earnings_growth 0.029 (not the annual lines).
    s = engine.build_scenarios(
        _understated_growth_fin(op_income_growth_stmt=0.029), stock_type="MID_CAP")
    assert s["realistic"] == pytest.approx(0.029)


def test_build_scenarios_outpaces_revenue_still_wins_over_understated():
    # Precedence: _earnings_outpaces_revenue is checked first. A fin that trips it must be
    # handled there (re-source from revenue), never reaching the understated branch. Build a
    # fin where eg outpaces revenue 3x AND both annual lines exceed eg: outpaces must win.
    fin = _understated_growth_fin(earnings_growth=0.40, revenue_growth=0.10,
                                  net_income_growth_stmt=0.50, op_income_growth_stmt=0.50)
    # sanity: both guards' predicates are individually satisfiable here
    assert engine._earnings_outpaces_revenue(fin) is True
    s = engine.build_scenarios(fin, stock_type="MID_CAP")
    # outpaces re-sources from revenue 0.10, NOT min(ni,op) 0.50
    assert s["realistic"] == pytest.approx(0.10)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_engine.py -k "build_scenarios_understated or outpaces_revenue_still_wins" -v`
Expected: FAIL — the understated cases return `0.029` (current `else` behaviour) instead of the re-sourced `min(ni,op)`.

- [ ] **Step 3: Write the minimal implementation**

In `backend/valuation/engine.py`, in `build_scenarios`, add a new `elif` immediately after the `_earnings_outpaces_revenue` block and before the final `else`:

```python
    elif _earnings_understated(fin):
        # Quarterly earnings_growth is an understated outlier below both annual statement
        # earnings lines (NFLX, NXT). Re-source from min(ni, op) — the lower annual line,
        # the SAME quantity the detector fires on, so the correction is self-limiting (its
        # size equals the gap). The lower line is conservative and immune to a depressed
        # trailing EPS inflating a forward-implied rate (the AVGO risk of an earlier design).
        raw = min(fin["net_income_growth_stmt"], fin["op_income_growth_stmt"])
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_engine.py -k "build_scenarios_understated or outpaces_revenue_still_wins" -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the full suite (regression + canaries)**

Run: `cd backend && python -m pytest -q`
Expected: PASS — all prior tests plus the 11 new ones green (was 421; now 432). No canary (IREN/NBIS/KLAC) test regresses.

- [ ] **Step 6: Commit**

```bash
git add backend/valuation/engine.py backend/tests/test_engine.py
git commit -m "feat(engine): re-source growth from min(ni,op) when earnings understated (NFLX/NXT)"
```

---

## Post-implementation (out of band, not a code task)

Re-run the live harnesses in `_scratch/understated-earnings-growth/` to reconfirm against fresh data before merge:
- `PYTHONIOENCODING=utf-8 python sweep_corroboration.py` — detector still fires on exactly {NFLX, NXT}.
- `PYTHONIOENCODING=utf-8 python blast_nflx.py` — NFLX ~$74 / NXT ~$63, 9 canaries byte-identical.

Then follow `superpowers:finishing-a-development-branch` and record the result in the [[understated-earnings-growth-guard]] memory.
