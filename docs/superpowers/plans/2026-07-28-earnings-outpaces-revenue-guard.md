# Earnings-Outpaces-Revenue Growth Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop `build_scenarios` from projecting an acquisition-consolidation-inflated quarterly earnings-growth figure as a decade-long organic rate, by re-sourcing growth from revenue when quarterly earnings outpace revenue 3×+ (CRM/Informatica: +204% → +109%).

**Architecture:** Add a fourth growth-source guard, `_earnings_outpaces_revenue`, to the existing `if/elif` chain in `backend/valuation/engine.py::build_scenarios`. It mirrors `models._forward_target_pe`'s divergence re-sourcing (opposite direction) and reuses that pattern's two constants; when it fires, growth is sourced from `revenue_growth` exactly as `_earnings_distorted`/`_earnings_inflated` already do. It sits last in the chain so existing precedence (LYFT stays on `_earnings_inflated`) is preserved.

**Tech Stack:** Python 3.14, pytest. `cd backend` and run `python -m pytest` (or the project's configured runner). Live re-validation uses the `validate_ticker.py` harness in `.claude/skills/validating-agent-stock/` run with `C:/Users/f_lub/AppData/Local/Python/bin/python3.exe`.

## Global Constraints

- **No new tunable constant.** Reuse `GROWTH_TRUST_FLOOR = 0.10` and `GROWTH_REVENUE_RATIO = 3.0` (both already in `backend/valuation/models.py:72-73`).
- **No new fetch / no new field.** Use only `earnings_growth` and `revenue_growth`, already present in `fin`.
- **Reference the reused constants `m.`-prefixed** (`m.GROWTH_TRUST_FLOOR`, `m.GROWTH_REVENUE_RATIO`), matching how `_earnings_inflated` references `m.DEPRESSED_PE_RATIO` (`engine.py:224`). `models` is imported as `m` in `engine.py`.
- **Scope: Fair Value pipeline only.** No Quality Score change; no per-leg valuation-model change; the guard lives entirely inside `build_scenarios`.
- **Design spec of record:** `docs/superpowers/specs/2026-07-28-earnings-outpaces-revenue-guard-design.md`.

---

### Task 1: Add the `_earnings_outpaces_revenue` predicate

**Files:**
- Modify: `backend/valuation/engine.py` (add the function after `_earnings_inflated`, which currently ends at line 227)
- Test: `backend/tests/test_engine.py` (add near the existing `_earnings_inflated` tests, ~line 948)

**Interfaces:**
- Consumes: nothing from other tasks. Reads `fin["earnings_growth"]`, `fin["revenue_growth"]` (both `float | None`), and module constants `m.GROWTH_TRUST_FLOOR`, `m.GROWTH_REVENUE_RATIO`.
- Produces: `engine._earnings_outpaces_revenue(fin: dict) -> bool` — consumed by Task 2's `build_scenarios` wiring.

- [ ] **Step 1: Write the failing tests for the pure predicate**

Add to `backend/tests/test_engine.py`:

```python
def _outpaces_fin(**over):
    """CRM-shaped: quarterly-YoY earnings growth (0.522, inflated by just-consolidated
    Informatica revenue) runs ~4x the ~13% revenue growth. A step change in the size of
    the business from the acquired quarter, not a rate the business compounds."""
    fin = _growth_fin(earnings_growth=0.522, revenue_growth=0.133)
    fin.update(over)
    return fin


def test_earnings_outpaces_revenue_fires_on_acquisition_consolidation_shape():
    # eg>0, rev>=floor 0.10, eg > rev*3.0 (0.522 > 0.133*3 = 0.399) -> the CRM fingerprint.
    assert engine._earnings_outpaces_revenue(_outpaces_fin()) is True


def test_earnings_outpaces_revenue_excluded_below_revenue_floor():
    # HON/MMM/UNH-shape: a big earnings jump on flat revenue is a depressed-base recovery,
    # NOT consolidation on a growing top line. rev < GROWTH_TRUST_FLOOR must not fire, or the
    # re-source would crush a recovering name to the 0.02 floor off its ~0% revenue.
    assert engine._earnings_outpaces_revenue(_outpaces_fin(revenue_growth=0.043)) is False


def test_earnings_outpaces_revenue_excluded_when_ratio_not_met():
    # A normal fast grower whose earnings lead revenue by less than 3x (eg 0.30 vs rev 0.13,
    # ratio 2.26) is real operating growth -> keep the earnings source.
    assert engine._earnings_outpaces_revenue(_outpaces_fin(earnings_growth=0.30)) is False


def test_earnings_outpaces_revenue_excluded_at_exact_ratio_boundary():
    # Strict '>' : eg exactly == rev*3.0 does NOT fire (0.399 == 0.133*3).
    assert engine._earnings_outpaces_revenue(_outpaces_fin(earnings_growth=0.399)) is False


def test_earnings_outpaces_revenue_requires_both_readings_and_positive_earnings():
    assert engine._earnings_outpaces_revenue(_outpaces_fin(earnings_growth=None)) is False
    assert engine._earnings_outpaces_revenue(_outpaces_fin(revenue_growth=None)) is False
    # eg <= 0 is _earnings_distorted's domain, never this guard.
    assert engine._earnings_outpaces_revenue(_outpaces_fin(earnings_growth=-0.30)) is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_engine.py -k earnings_outpaces_revenue -v`
Expected: FAIL — `AttributeError: module 'valuation.engine' has no attribute '_earnings_outpaces_revenue'`.

- [ ] **Step 3: Implement the predicate**

In `backend/valuation/engine.py`, add immediately after `_earnings_inflated` (after line 227, before `_ramp`):

```python
def _earnings_outpaces_revenue(fin: dict) -> bool:
    """GAAP earnings growth runs far ahead of revenue growth — the signature of a
    just-consolidated acquisition, where acquired revenue/earnings land in the trailing
    quarter and inflate the quarterly-YoY earnings figure into a one-time step change,
    not a rate the business compounds. Growth is re-sourced from revenue, like
    _earnings_distorted / _earnings_inflated.

    The exact mirror of models._forward_target_pe's divergence re-sourcing: THERE revenue
    outpaces earnings 3x (a tiny noisy quarterly earnings print on a fast grower, HOOD) and
    the PEG target sources growth from revenue; HERE earnings outpace revenue 3x and the
    realistic leg sources growth from revenue. Both operands are the quarterly-YoY info
    figures, so the comparison is like-with-like, and both reused thresholds
    (GROWTH_TRUST_FLOOR, GROWTH_REVENUE_RATIO) carry over unchanged — no second knob.

    The revenue floor (>= GROWTH_TRUST_FLOOR) keeps this off flat-revenue recovery names,
    whose earnings spike is a depressed-base effect, not consolidation on a growing business
    (HON/MMM/UNH). It also self-limits above the cap: once revenue growth exceeds the ~0.20
    growth cap (DDOG/PLTR/GOOGL/MU), revenue-sourced == earnings-sourced == cap, so firing
    changes nothing. It bites only in the 0.10 <= rev < ~0.20 band — a healthy double-digit
    grower whose quarterly earnings run 3x+ its revenue (CRM post-Informatica, CSCO post-Splunk)."""
    eg = fin.get("earnings_growth")
    rg = fin.get("revenue_growth")
    return (eg is not None and eg > 0
            and rg is not None and rg >= m.GROWTH_TRUST_FLOOR
            and eg > rg * m.GROWTH_REVENUE_RATIO)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_engine.py -k earnings_outpaces_revenue -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/valuation/engine.py backend/tests/test_engine.py
git commit -m "feat(valuation): add _earnings_outpaces_revenue growth-source predicate"
```

---

### Task 2: Wire the guard into `build_scenarios` and fix the one incidentally-tripping fixture

**Files:**
- Modify: `backend/valuation/engine.py` — `build_scenarios` guard chain (the `if/elif` at lines 337-355)
- Modify: `backend/tests/test_engine.py` — `test_build_scenarios_capped` fixture (line 24)
- Test: `backend/tests/test_engine.py` — new behavior tests

**Interfaces:**
- Consumes: `engine._earnings_outpaces_revenue(fin)` from Task 1.
- Produces: no new symbol. Changes `build_scenarios`' behavior so a fired name's `realistic` becomes `max(0.02, min(revenue_growth, distorted_cap))`.

- [ ] **Step 1: Write the failing behavior tests**

Add to `backend/tests/test_engine.py` (the `_outpaces_fin` helper from Task 1 is in scope):

```python
def test_build_scenarios_sources_revenue_when_earnings_outpace_revenue():
    # CRM: +52.2% quarterly earnings growth is Informatica consolidation, not a rate. Capping
    # it to 0.20 projects a decade of 20% growth off a 13% top line; the guard re-sources the
    # realistic leg from revenue growth (0.133) instead.
    s = engine.build_scenarios(_outpaces_fin(), stock_type="GROWTH")
    assert s["realistic"] == pytest.approx(0.133)   # min(revenue_growth 0.133, cap 0.20)


def test_build_scenarios_outpaces_ddm_path_respects_sustainable_ceiling():
    # The DDM/perpetuity copy passes distorted_cap=SUSTAINABLE_CEIL; the re-source
    # min(revenue_growth, SUSTAINABLE_CEIL) must bound Gordon growth like the sibling guards.
    s = engine.build_scenarios(_outpaces_fin(revenue_growth=0.40),
                               distorted_cap=engine.SUSTAINABLE_CEIL)
    assert s["realistic"] == pytest.approx(engine.SUSTAINABLE_CEIL)


def test_build_scenarios_outpaces_does_not_fire_without_revenue_reading():
    # Unlike _earnings_inflated (which fires on P/E conditions alone and then re-sources
    # min(revenue or 0, cap) -> 0.02 when revenue is missing), THIS guard REQUIRES a revenue
    # reading to fire (rg is not None). With revenue None it cannot fire, so the else-branch
    # caps the 0.52 earnings figure to 0.20 -> realistic 0.20. This pins that the guard needs
    # revenue present and does not misfire on a missing reading.
    s = engine.build_scenarios(_outpaces_fin(revenue_growth=None), stock_type="GROWTH")
    assert s["realistic"] == pytest.approx(0.20)   # rev None -> guard False -> else caps 0.52 to 0.20


def test_build_scenarios_inflated_precedence_beats_outpaces():
    # LYFT is BOTH inflated (fpe/tpe>1.5, feps<teps) AND outpaces (eg 4.89 >> rev 0.14). The
    # inflated guard is earlier in the chain and wins; both re-source from revenue here, so the
    # value is identical, but this pins the precedence order so a future reorder can't regress it.
    s = engine.build_scenarios(_inflated_earnings_fin(), stock_type="GROWTH")
    assert s["realistic"] == pytest.approx(0.14)   # revenue growth via _earnings_inflated


def test_build_scenarios_outpaces_inert_for_self_limiting_hypergrower():
    # DDOG-shape: eg 1.04, rev 0.32 (above the cap). Whether or not the guard fires, revenue-
    # sourced and earnings-sourced both cap to 0.20 -> realistic unchanged. Self-limiting.
    fired = engine.build_scenarios(_outpaces_fin(earnings_growth=1.04, revenue_growth=0.32))
    assert fired["realistic"] == pytest.approx(0.20)
```

- [ ] **Step 2: Run the new behavior tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_engine.py -k "outpaces or inflated_precedence" -v`
Expected: `test_build_scenarios_sources_revenue_when_earnings_outpace_revenue` FAILS (realistic is 0.20, not 0.133 — guard not wired yet). The DDM/floor/precedence/inert tests may already pass by coincidence; the sources-revenue test is the red one that drives the change.

- [ ] **Step 3: Add the fourth `elif` to `build_scenarios`**

In `backend/valuation/engine.py`, in `build_scenarios`, add the new branch after the `_earnings_inflated` branch (after line 352, before the `else:` at line 353):

```python
    elif _earnings_outpaces_revenue(fin):
        # Quarterly earnings growth runs 3x+ ahead of revenue (CRM post-Informatica, CSCO
        # post-Splunk): a just-consolidated acquisition inflates the trailing-quarter YoY
        # earnings into a one-time step change, not a compounding rate. Re-source from revenue
        # like the distorted / inflated paths. Placed LAST so _earnings_inflated still wins for
        # a one-time trailing gain (LYFT) and _earnings_non_operating for a flat operating line.
        raw = min(fin.get("revenue_growth") or 0, distorted_cap)
```

- [ ] **Step 4: Run the new behavior tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_engine.py -k "outpaces or inflated_precedence" -v`
Expected: PASS.

- [ ] **Step 5: Run the full engine suite to catch the incidentally-tripping fixture**

Run: `cd backend && python -m pytest tests/test_engine.py -v`
Expected: exactly ONE pre-existing failure — `test_build_scenarios_capped`. Its fixture `{"earnings_growth": 0.56, "revenue_growth": 0.10}` is the guard's target shape (0.56 > 0.10×3 = 0.30, rev at the 0.10 floor), so `realistic` is now re-sourced to 0.10 instead of the asserted 0.20.

- [ ] **Step 6: Fix the `test_build_scenarios_capped` fixture**

The test's purpose is "positive earnings above the cap → capped to 0.20", NOT the outpaces path. Lower `earnings_growth` so it still exceeds the cap but stays below the 3× revenue ratio (0.28 < 0.10×3 = 0.30). Band assertions are unchanged because the band keys off `revenue_growth` (0.10), which is untouched.

In `backend/tests/test_engine.py`, change line 24:

```python
def test_build_scenarios_capped():
    # eg 0.28 exceeds the 0.20 cap but stays below rev*3 (0.30), so this exercises capping,
    # NOT the _earnings_outpaces_revenue guard (which would re-source to revenue 0.10).
    s = engine.build_scenarios({"earnings_growth": 0.28, "revenue_growth": 0.10})
    assert s["realistic"] == 0.20             # base capped at 0.20 (unchanged)
    # band: g = info revenue growth 0.10 (at the floor) -> up 0.05 -> opt 0.25, clipped by
    # the 0.35 default ceiling; the old corroboration gate no longer collapses it to the cap.
    assert s["optimistic"] == pytest.approx(0.25)
    assert s["pessimistic"] == pytest.approx(0.16)
```

- [ ] **Step 7: Run the full engine suite green**

Run: `cd backend && python -m pytest tests/test_engine.py -v`
Expected: PASS (all engine tests, including the amended `test_build_scenarios_capped`).

- [ ] **Step 8: Commit**

```bash
git add backend/valuation/engine.py backend/tests/test_engine.py
git commit -m "feat(valuation): re-source growth from revenue when earnings outpace revenue 3x

Wire _earnings_outpaces_revenue into build_scenarios as the 4th (last) growth-source
guard, so CRM/Informatica and CSCO/Splunk consolidation no longer projects an inflated
quarterly earnings-growth as a decade-long organic rate. Adjust test_build_scenarios_capped
fixture (eg 0.56->0.28) so it still exercises capping without tripping the new guard."
```

---

### Task 3: Full-suite verification and live re-validation

**Files:** none modified — verification only.

**Interfaces:** none.

- [ ] **Step 1: Run the entire backend test suite**

Run: `cd backend && python -m pytest`
Expected: PASS — the previous count plus the new tests (5 predicate + 5 behavior), and no unrelated regression.

- [ ] **Step 2: Live re-validate the two names the guard moves**

Run the validation harness for CRM and CSCO:

```bash
C:/Users/f_lub/AppData/Local/Python/bin/python3.exe .claude/skills/validating-agent-stock/validate_ticker.py CRM
C:/Users/f_lub/AppData/Local/Python/bin/python3.exe .claude/skills/validating-agent-stock/validate_ticker.py CSCO
```

Expected (matches the measured blast radius in the design spec):
- CRM fair value ≈ **$342** (down from $497.78, from +204% to ~+109%).
- CSCO fair value ≈ **$61** (down from $84.12, ≈ −27%).

If either differs materially from the spec's measured figures, STOP and reconcile against the design spec before proceeding — a divergence means the wired guard is not behaving as the monkey-patched measurement did.

- [ ] **Step 3: Live-confirm the canaries are byte-identical**

```bash
C:/Users/f_lub/AppData/Local/Python/bin/python3.exe .claude/skills/validating-agent-stock/validate_ticker.py IREN
C:/Users/f_lub/AppData/Local/Python/bin/python3.exe .claude/skills/validating-agent-stock/validate_ticker.py NBIS
C:/Users/f_lub/AppData/Local/Python/bin/python3.exe .claude/skills/validating-agent-stock/validate_ticker.py KLAC
```

Expected: fair values unchanged from their pre-change baselines (these do not meet the fingerprint — IREN/NBIS are EARLY_GROWTH loss-makers with `earnings_growth None`; KLAC's earnings and revenue growth are close, ratio < 3×).

- [ ] **Step 4: No commit**

Verification only — nothing to commit. If any expectation failed, treat it as a bug (use `superpowers:systematic-debugging`), fix, and re-run from Step 1.

---

## Self-Review

**1. Spec coverage.** Every section of `2026-07-28-earnings-outpaces-revenue-guard-design.md` maps to a task:
- New guard `_earnings_outpaces_revenue` + fingerprint → Task 1.
- Placement as 4th `elif`, revenue sourcing, DDM bound, precedence → Task 2.
- Reused constants / no new knob / no new fetch → enforced in both the predicate (Task 1 Step 3) and Global Constraints.
- Measured blast radius (CRM/CSCO move; canaries inert) → Task 3 live re-validation.
- Test list (fires / floor-excludes / ratio-excludes / precedence / self-limiting inert) → Tasks 1–2 test steps.
- The known fixture collision (`test_build_scenarios_capped`) is handled explicitly in Task 2 Steps 5–6 (this is an implementation detail the spec's blast-radius section did not surface, caught during the fixture audit).

**2. Placeholder scan.** No TBD/TODO/"handle edge cases"/"similar to". Every code step has literal code; every run step has an exact command and expected result.

**3. Type consistency.** `_earnings_outpaces_revenue(fin: dict) -> bool` is defined in Task 1 and called with that exact name in Task 2's `elif` and its tests. `_outpaces_fin` helper defined in Task 1, reused in Task 2. Constants referenced as `m.GROWTH_TRUST_FLOOR` / `m.GROWTH_REVENUE_RATIO` consistently. `distorted_cap` and `SUSTAINABLE_CEIL` names match `engine.build_scenarios`' existing signature and the sibling tests.

One asymmetry the implementer must not "fix": `test_build_scenarios_outpaces_does_not_fire_without_revenue_reading` asserts 0.20, whereas the `_earnings_inflated` sibling's missing-revenue test asserts 0.02. This is correct and intended — `_earnings_inflated` fires on P/E conditions alone (so with revenue `None` it fires and re-sources to 0.02), while `_earnings_outpaces_revenue` requires `rg is not None` to fire (so with revenue `None` it cannot fire and the `else`-branch caps earnings to 0.20). The differing assertions reflect a genuine behavioral difference, not a bug.
