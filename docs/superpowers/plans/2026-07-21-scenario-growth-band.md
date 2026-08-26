# Growth-Coupled Scenario Band Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `build_scenarios`' constant ±0.05/−0.04 optimistic/pessimistic offsets with growth-coupled, asymmetric, ramp-and-saturate offsets bounded by a type/size/quality-coupled ceiling, so every stock gets three distinct scenarios and no bull leg can explode.

**Architecture:** Four new pure helpers in `engine.py` (`_ramp`, `_quality_frac`, `_opt_ceil`, `_band_growth_signal`) reuse the flat-floor→linear-ramp→saturating-ceiling shape the engine already uses in `_growth_cap`/`_ev_ebitda_ceiling`. `build_scenarios` keeps its realistic leg untouched and rebuilds the two outer legs from these helpers. The perpetuity DDM call (`distorted_cap < GROWTH_CAP_BASE`) keeps the flat floor offsets. The old corroboration-gated optimistic ceiling is removed; the saturating `_opt_ceil` is the new noise-suppressor.

**Tech Stack:** Python 3.14, pytest (`asyncio_mode=auto`), run from `backend/`.

## Global Constraints

- Design spec: `docs/superpowers/specs/2026-07-21-scenario-growth-band-design.md`. Every task's requirements implicitly include it.
- **Scope is `backend/valuation/engine.py` + `backend/tests/test_engine.py` only.** No change to any per-leg model in `models.py`, no Quality Score change.
- **The realistic leg of `build_scenarios` must not change** for any input (verified: realistic is byte-identical across all fixtures).
- **The DDM path** (`build_scenarios(fin, distorted_cap=SUSTAINABLE_CEIL)`) must stay byte-identical to today.
- Size/quality constants live in `models.py`, reachable as `m.*` (engine already does `from valuation import models as m`): `m.MEGA_CAP_FLOOR` (1e12), `m.LARGE_CAP_FADE_FLOOR` (150e9), `m.QUALITY_CONV_LO` (0.65), `m.QUALITY_CONV_HI` (0.90).
- Run tests from `backend/`: `python -m pytest`. Full suite must be green at every commit.
- New constant values (verbatim): `SCEN_BAND_G_LO=0.10`, `SCEN_BAND_G_HI=0.30`, `SCEN_UP_FLOOR=0.05`, `SCEN_UP_CEIL=0.10`, `SCEN_DOWN_FLOOR=0.04`, `SCEN_DOWN_CEIL=0.12`, `SCEN_OPT_CEIL_EARLY=0.50`, `SCEN_OPT_CEIL_MEGA=0.28`, `SCEN_OPT_CEIL_LARGE=0.32`, `SCEN_OPT_CEIL_DEFAULT=0.35`.

---

## File Structure

- **Modify `backend/valuation/engine.py`:**
  - Add the ten `SCEN_*` constants (after `EG_REVENUE_FLOOR`, line ~96).
  - Add four pure helpers (`_ramp`, `_quality_frac`, `_opt_ceil`, `_band_growth_signal`) after `_earnings_non_operating` (line ~186), before `build_scenarios`.
  - Rewrite the optimistic/pessimistic construction inside `build_scenarios` (lines ~236-252). Realistic and the whole cap-selection block above it are untouched.
  - Remove the now-dead constants `GROWTH_OPT_HEADROOM` and `CORROBORATED_GROWTH_CEIL` (and their comment blocks).
- **Modify `backend/tests/test_engine.py`:**
  - Add unit tests for the four helpers.
  - Update five existing `build_scenarios` tests to the new optimistic/pessimistic values.
  - Delete two obsolete corroboration-collapse tests.

---

## Task 1: Band primitive helpers + constants

Pure, deterministic functions with no dependency on `build_scenarios`. This task adds and tests them but does not wire them in, so it can be reviewed on its own.

**Files:**
- Modify: `backend/valuation/engine.py` (add constants ~line 96; add helpers ~line 187)
- Test: `backend/tests/test_engine.py` (append new tests)

**Interfaces:**
- Consumes: `m.MEGA_CAP_FLOOR`, `m.LARGE_CAP_FADE_FLOOR`, `m.QUALITY_CONV_LO`, `m.QUALITY_CONV_HI`; existing `_earnings_distorted(fin)`, `_earnings_non_operating(fin)`.
- Produces (relied on by Task 2):
  - `_ramp(g: float, lo: float, hi: float, at_lo: float, at_hi: float) -> float`
  - `_quality_frac(fin: dict) -> float`
  - `_opt_ceil(fin: dict, stock_type: str | None) -> float`
  - `_band_growth_signal(fin: dict) -> float`
  - constants `SCEN_BAND_G_LO`, `SCEN_BAND_G_HI`, `SCEN_UP_FLOOR`, `SCEN_UP_CEIL`, `SCEN_DOWN_FLOOR`, `SCEN_DOWN_CEIL`, `SCEN_OPT_CEIL_EARLY`, `SCEN_OPT_CEIL_MEGA`, `SCEN_OPT_CEIL_LARGE`, `SCEN_OPT_CEIL_DEFAULT`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_engine.py`:

```python
# --- scenario-band primitives (2026-07-21-scenario-growth-band) ----------------
def test_ramp_below_floor_returns_floor():
    assert engine._ramp(0.05, 0.10, 0.30, 0.05, 0.10) == pytest.approx(0.05)
    assert engine._ramp(0.10, 0.10, 0.30, 0.05, 0.10) == pytest.approx(0.05)


def test_ramp_linear_region():
    assert engine._ramp(0.20, 0.10, 0.30, 0.05, 0.10) == pytest.approx(0.075)
    assert engine._ramp(0.168, 0.10, 0.30, 0.05, 0.10) == pytest.approx(0.067)


def test_ramp_saturates_at_ceiling():
    assert engine._ramp(0.30, 0.10, 0.30, 0.05, 0.10) == pytest.approx(0.10)
    assert engine._ramp(6.84, 0.10, 0.30, 0.05, 0.10) == pytest.approx(0.10)


def test_quality_frac_conversion_ramp():
    # fcf/ebitda = 0.8125 -> (0.8125-0.65)/(0.90-0.65) = 0.65
    assert engine._quality_frac({"fcf_ttm": 3.9e9, "ebitda_ttm": 4.8e9}) == pytest.approx(0.65)
    # conversion >= HI -> clamps to 1.0
    assert engine._quality_frac({"fcf_ttm": 4.8e9, "ebitda_ttm": 4.8e9}) == pytest.approx(1.0)
    # conversion <= LO -> 0.0
    assert engine._quality_frac({"fcf_ttm": 3.0e9, "ebitda_ttm": 4.8e9}) == pytest.approx(0.0)


def test_quality_frac_missing_or_nonpositive_data():
    assert engine._quality_frac({"fcf_ttm": None, "ebitda_ttm": 4.8e9}) == 0.0
    assert engine._quality_frac({"fcf_ttm": 3.9e9, "ebitda_ttm": 0}) == 0.0
    assert engine._quality_frac({"fcf_ttm": 3.9e9, "ebitda_ttm": -1.0}) == 0.0


def test_opt_ceil_early_growth_is_highest():
    assert engine._opt_ceil({"market_cap": 5e9}, "EARLY_GROWTH") == pytest.approx(0.50)
    # EARLY wins even at mega size (checked before size bands)
    assert engine._opt_ceil({"market_cap": 2e12}, "EARLY_GROWTH") == pytest.approx(0.50)


def test_opt_ceil_mega_is_hard_cap():
    # mega, low quality -> 0.28
    assert engine._opt_ceil({"market_cap": 2e12, "fcf_ttm": 1.0, "ebitda_ttm": 10.0},
                            "MEGA_CAP") == pytest.approx(0.28)
    # mega, high quality -> STILL 0.28 (quality cannot lift the mega cap)
    assert engine._opt_ceil({"market_cap": 2e12, "fcf_ttm": 4.8e9, "ebitda_ttm": 4.8e9},
                            "MEGA_CAP") == pytest.approx(0.28)


def test_opt_ceil_large_quality_carveout():
    # large ($200B), q=1.0 (fcf==ebitda) -> 0.32 + 1.0*0.03 = 0.35
    assert engine._opt_ceil({"market_cap": 2e11, "fcf_ttm": 4.8e9, "ebitda_ttm": 4.8e9},
                            "GROWTH") == pytest.approx(0.35)
    # large, q=0.0 (low conversion) -> 0.32
    assert engine._opt_ceil({"market_cap": 2e11, "fcf_ttm": 3.0e9, "ebitda_ttm": 4.8e9},
                            "GROWTH") == pytest.approx(0.32)


def test_opt_ceil_default_below_large_floor():
    assert engine._opt_ceil({"market_cap": 1e11}, "GROWTH") == pytest.approx(0.35)
    assert engine._opt_ceil({}, None) == pytest.approx(0.35)


def test_band_growth_signal_respects_guards():
    # distorted (eg<0, rg>0) -> revenue_growth (matches realistic's distorted source)
    assert engine._band_growth_signal(
        {"earnings_growth": -0.1, "revenue_growth": 0.168}) == pytest.approx(0.168)
    # non-operating (ni_stmt>0, op_stmt<=0) -> op_income_growth_stmt
    assert engine._band_growth_signal(
        {"earnings_growth": 0.2, "revenue_growth": 0.18, "net_income_growth_stmt": 0.2,
         "op_income_growth_stmt": -0.014}) == pytest.approx(-0.014)
    # normal -> statement revenue growth preferred over info
    assert engine._band_growth_signal(
        {"earnings_growth": 0.3, "revenue_growth": 0.40,
         "revenue_growth_stmt": 0.29}) == pytest.approx(0.29)
    # normal, no statement -> info revenue growth
    assert engine._band_growth_signal(
        {"earnings_growth": 0.3, "revenue_growth": 0.40}) == pytest.approx(0.40)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine.py -k "ramp or quality_frac or opt_ceil or band_growth_signal" -v`
Expected: FAIL — `AttributeError: module 'valuation.engine' has no attribute '_ramp'`.

- [ ] **Step 3: Add the constants**

In `backend/valuation/engine.py`, immediately after the `EG_REVENUE_FLOOR = 500_000_000` line (~line 96), add:

```python
# Scenario-band offsets (2026-07-21-scenario-growth-band spec). The optimistic and
# pessimistic legs are asymmetric, growth-coupled offsets off the realistic base, ramped
# over [SCEN_BAND_G_LO, SCEN_BAND_G_HI] and saturating — the same flat-floor -> ramp ->
# ceiling shape as _growth_cap / _ev_ebitda_ceiling. Floors equal the prior flat offsets
# (+0.05 / -0.04) so low-growth names are inert and the band only widens as growth rises.
SCEN_BAND_G_LO = 0.10
SCEN_BAND_G_HI = 0.30
SCEN_UP_FLOOR = 0.05
SCEN_UP_CEIL = 0.10
SCEN_DOWN_FLOOR = 0.04
SCEN_DOWN_CEIL = 0.12
# Type/size-coupled saturating ceiling for the OPTIMISTIC growth leg — the noise-suppressor
# that replaces the old corroboration gate. EARLY_GROWTH's optimistic runs ABOVE its
# noise-suppressed realistic cap (the "what if the hyper-growth is real" leg). MEGA (>=$1T)
# is a HARD cap (mirrors _ev_ebitda_ceiling's mega top: quality decides whether a name
# reaches its size ceiling, never lifts it above). LARGE ($150B-$1T) earns back toward the
# default on FCF/EBITDA conversion quality.
SCEN_OPT_CEIL_EARLY = 0.50
SCEN_OPT_CEIL_MEGA = 0.28
SCEN_OPT_CEIL_LARGE = 0.32
SCEN_OPT_CEIL_DEFAULT = 0.35
```

- [ ] **Step 4: Add the helper functions**

In `backend/valuation/engine.py`, after `_earnings_non_operating` (ends ~line 186) and before `def build_scenarios`, add:

```python
def _ramp(g: float, lo: float, hi: float, at_lo: float, at_hi: float) -> float:
    """Flat floor -> linear ramp -> saturate, the shape _ev_ebitda_ceiling's g_frac uses.
    Returns at_lo for g <= lo, at_hi for g >= hi, linear in between."""
    if g <= lo:
        return at_lo
    return at_lo + min(1.0, (g - lo) / (hi - lo)) * (at_hi - at_lo)


def _quality_frac(fin: dict) -> float:
    """FCF/EBITDA conversion ramped QUALITY_CONV_LO->HI — the same quality signal
    _ev_ebitda_ceiling reads. 0.0 when the conversion is unavailable or non-positive."""
    fcf, ebitda = fin.get("fcf_ttm"), fin.get("ebitda_ttm")
    if fcf is None or not ebitda or ebitda <= 0:
        return 0.0
    conv = fcf / ebitda
    return max(0.0, min(1.0, (conv - m.QUALITY_CONV_LO) / (m.QUALITY_CONV_HI - m.QUALITY_CONV_LO)))


def _opt_ceil(fin: dict, stock_type: str | None) -> float:
    """Type/size-coupled saturating ceiling for the optimistic growth leg, with a quality
    carve-out for the large tier. EARLY_GROWTH is checked first (any size); mega (>=$1T) is a
    hard cap quality cannot lift; large ($150B-$1T) ramps from the large ceiling toward the
    default on _quality_frac; everything else takes the default."""
    if stock_type == "EARLY_GROWTH":
        return SCEN_OPT_CEIL_EARLY
    mc = fin.get("market_cap") or 0
    if mc >= m.MEGA_CAP_FLOOR:
        return SCEN_OPT_CEIL_MEGA
    if mc >= m.LARGE_CAP_FADE_FLOOR:
        return SCEN_OPT_CEIL_LARGE + _quality_frac(fin) * (SCEN_OPT_CEIL_DEFAULT - SCEN_OPT_CEIL_LARGE)
    return SCEN_OPT_CEIL_DEFAULT


def _band_growth_signal(fin: dict) -> float:
    """Growth rate the band offsets key off — the SAME rate the realistic leg is derived
    from, so the distorted / non-operating guards govern the bull leg too (BWXT's
    non-operating revenue growth must not sneak back through optimistic)."""
    if _earnings_distorted(fin):
        return float(fin.get("revenue_growth") or 0.0)
    if _earnings_non_operating(fin):
        return float(fin.get("op_income_growth_stmt") or 0.0)
    g = fin.get("revenue_growth_stmt")
    return float(g if g is not None else (fin.get("revenue_growth") or 0.0))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -k "ramp or quality_frac or opt_ceil or band_growth_signal" -v`
Expected: PASS (all helper tests green).

- [ ] **Step 6: Commit**

```bash
git add backend/valuation/engine.py backend/tests/test_engine.py
git commit -m "feat(valuation): scenario-band primitives (ramp/quality/opt-ceil/growth-signal)"
```

---

## Task 2: Wire the band into build_scenarios

Replace the optimistic/pessimistic construction, delete the obsolete corroboration constants and tests, update the five tests whose outer-leg values change, and confirm the full suite is green.

**Files:**
- Modify: `backend/valuation/engine.py` (`build_scenarios` body ~lines 236-252; remove `GROWTH_OPT_HEADROOM` ~lines 42-47 and `CORROBORATED_GROWTH_CEIL` ~lines 49-65 with their comment blocks)
- Modify: `backend/tests/test_engine.py` (update 5 tests, delete 2)

**Interfaces:**
- Consumes: all four helpers + constants from Task 1.
- Produces: `build_scenarios(fin, distorted_cap=0.20, stock_type=None) -> dict` with unchanged `realistic`, banded `optimistic`/`pessimistic`.

- [ ] **Step 1: Update the five affected tests and delete the two obsolete ones**

In `backend/tests/test_engine.py`:

**(a)** `test_build_scenarios_capped` — change the optimistic assertion (line ~26):

```python
def test_build_scenarios_capped():
    s = engine.build_scenarios({"earnings_growth": 0.56, "revenue_growth": 0.10})
    assert s["realistic"] == 0.20             # base capped at 0.20 (unchanged)
    # band: g = info revenue growth 0.10 (at the floor) -> up 0.05 -> opt 0.25, clipped by
    # the 0.35 default ceiling; the old corroboration gate no longer collapses it to the cap.
    assert s["optimistic"] == pytest.approx(0.25)
    assert s["pessimistic"] == pytest.approx(0.16)
```

**(b)** `test_build_scenarios_distorted_earnings_uses_full_revenue_growth` — change optimistic and pessimistic (lines ~44-45):

```python
    assert s["realistic"] == pytest.approx(0.168)
    # band: g = revenue_growth 0.168 (distorted source) -> up 0.067, dn 0.0672
    assert s["optimistic"] == pytest.approx(0.235)
    assert s["pessimistic"] == pytest.approx(0.1008)
```

**(c)** `test_build_scenarios_elevated_cap_for_eligible_hypergrower` — rewrite intent + optimistic (lines ~476-481):

```python
def test_build_scenarios_elevated_cap_for_eligible_hypergrower():
    # statement growth 0.70 -> realistic cap saturates at 0.25. The optimistic leg is no
    # longer collapsed onto the cap: it rides +0.10 (g saturates) up to the 0.35 default
    # ceiling, which is the new noise-suppressor (0.70 growth is NOT run at 0.70).
    s = engine.build_scenarios(_hypergrower_fin())
    assert s["realistic"] == pytest.approx(0.25)
    assert s["optimistic"] == pytest.approx(0.35)     # clipped at the default ceiling
    assert s["optimistic"] > s["realistic"]
```

**(d)** `test_build_scenarios_corroborated_grower_gets_optimistic_upside` — change optimistic (line ~492):

```python
    assert s["realistic"] == pytest.approx(0.25)
    # band: g = statement revenue growth 0.286 -> up 0.0965 -> opt 0.3465 (< 0.35 ceiling)
    assert s["optimistic"] == pytest.approx(0.3465)
    assert s["optimistic"] > s["realistic"]
```

**(e)** `test_build_scenarios_corroborated_compounder_above_magnitude_band` — change optimistic (line ~507):

```python
    assert s["realistic"] == pytest.approx(0.20)
    # band: g = statement revenue growth 0.1417 -> up 0.0604 -> opt 0.2604
    assert s["optimistic"] == pytest.approx(0.2604)
    assert s["optimistic"] > s["realistic"]
```

**(f)** DELETE these two tests entirely — they assert the `optimistic == realistic` collapse, which the band deliberately removes (the optimistic leg now always opens a bounded bull case):

- `test_build_scenarios_corroboration_requires_cash_generation` (lines ~511-519)
- `test_build_scenarios_corroboration_capped_at_regime_ceiling` (lines ~522-530)

- [ ] **Step 2: Run the updated tests to verify they now fail against the OLD engine**

Run: `python -m pytest tests/test_engine.py -k build_scenarios -v`
Expected: FAIL on `test_build_scenarios_capped`, `..._distorted_earnings_uses_full_revenue_growth`, `..._elevated_cap_for_eligible_hypergrower`, `..._corroborated_grower...`, `..._corroborated_compounder...` (old engine still returns the pre-band optimistic values). The two deleted tests no longer run. This confirms the assertions are RED before the implementation.

- [ ] **Step 3: Rewrite the optimistic/pessimistic construction in `build_scenarios`**

In `backend/valuation/engine.py`, replace everything from the `base = max(0.02, ...)` line's following comment through the `return {...}` (the block currently at lines ~236-252) — keep the `base = max(...)` line — with:

```python
    base = max(0.02, min(float(raw), cap))
    # Scenario dispersion (2026-07-21-scenario-growth-band spec): growth-coupled, asymmetric,
    # ramp-and-saturate offsets off the realistic base. The saturating _opt_ceil replaces the
    # old corroboration-gated ceiling as the noise-suppressor — a 684% grower's optimistic is
    # clipped to its tier ceiling, not run at 684% — so every name gets a genuine, bounded
    # bull leg instead of optimistic collapsing onto realistic.
    if distorted_cap < GROWTH_CAP_BASE:
        # DDM / perpetuity copy: keep the flat floor offsets so Gordon growth stays bounded.
        return {
            "optimistic": base + SCEN_UP_FLOOR,
            "realistic": base,
            "pessimistic": max(base - SCEN_DOWN_FLOOR, 0.02),
        }
    g = _band_growth_signal(fin)
    up = _ramp(g, SCEN_BAND_G_LO, SCEN_BAND_G_HI, SCEN_UP_FLOOR, SCEN_UP_CEIL)
    dn = _ramp(g, SCEN_BAND_G_LO, SCEN_BAND_G_HI, SCEN_DOWN_FLOOR, SCEN_DOWN_CEIL)
    return {
        "optimistic": max(base, min(base + up, _opt_ceil(fin, stock_type))),
        "realistic": base,
        "pessimistic": max(base - dn, 0.02),
    }
```

- [ ] **Step 4: Run the build_scenarios tests to verify they pass**

Run: `python -m pytest tests/test_engine.py -k build_scenarios -v`
Expected: PASS (all updated + retained tests green; realistic-only tests unaffected).

- [ ] **Step 5: Remove the now-dead constants**

Confirm they are unreferenced, then remove:

Run: `git grep -n "GROWTH_OPT_HEADROOM\|CORROBORATED_GROWTH_CEIL" backend/`
Expected: matches only remain at the definitions in `engine.py` (lines ~42-65). If any other reference exists (e.g. a missed test), stop and update it first.

Then delete from `backend/valuation/engine.py`:
- the `GROWTH_OPT_HEADROOM = 0.05` line and its comment block (lines ~42-47),
- the `CORROBORATED_GROWTH_CEIL = 0.35` line and its comment block (lines ~49-65).

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest`
Expected: PASS. If an `evaluate`-level test asserting a specific fair value for a growth/hyper-grower name fails, it is legitimately affected by the wider band — verify the new value is directionally correct (a grower's FV rises, a mega name does not rise, a low-growth name is unchanged) against the spec's effect table, then update the assertion. `test_evaluate_hypergrower_fv_exceeds_slow_growth_twin` must still pass unchanged (fast > slow still holds).

- [ ] **Step 7: Commit**

```bash
git add backend/valuation/engine.py backend/tests/test_engine.py
git commit -m "feat(valuation): growth-coupled ramp-and-saturate scenario bands"
```

---

## Task 3: Live validation

Confirm the change reproduces the spec's measured effect on real data and holds the regression canaries. This is the codebase's standard gate for a fair-value change (a code fix does not change what the app shows until verified live in a fresh process — see the `app-serves-persisted-rows-not-live-compute` memory).

**Files:** none (verification only).

- [ ] **Step 1: Invoke the validation skill**

Use the `validating-agent-stock` skill to run the 12-name basket (PLTR, NBIS, IREN, NVDA, ANET, KLAC, AAPL, MSFT, JPM, KO, BWXT, SNPS) through the live `evaluate` path and diff composite fair value against the pre-change baseline.

- [ ] **Step 2: Confirm the movers and canaries match the spec**

Expected (from the spec's effect table, tolerance a few %):
- Movers: PLTR ~+7%, NVDA ~−4%, NBIS ~+42% (bull leg lifts it), IREN ~+15%, ANET ~+1%, JPM ~+3%.
- Canaries **inert**: AAPL, KO, BWXT byte-identical; KLAC/MSFT/SNPS within ±1%.
- No name produces an absurd fair value (the saturating ceilings hold; IREN bounded, not exploding).

If any canary moves materially or any name explodes, stop and diagnose before proceeding — the band or a ceiling is mis-wired.

- [ ] **Step 3: Record the outcome**

Note the validated movers/canaries for the memory follow-up (below). No commit.

---

## Follow-up (record in memory when landed)

- The band shape, the four `SCEN_OPT_CEIL_*` tiers, the quality carve-out mirroring `_ev_ebitda_ceiling`, the guard-respecting offset signal, and that the corroboration mechanism (`GROWTH_OPT_HEADROOM` / `CORROBORATED_GROWTH_CEIL` / the opt-ceiling gate) was removed and replaced by the saturating `_opt_ceil`.
- Link to `docs/superpowers/specs/2026-07-21-scenario-growth-band-design.md`.
- Deferred, out-of-scope gaps to re-flag: NBIS's central EV/Sales estimate vs its ~$180 price, and the NBIS baseline data-shift ($48 here vs the ~$92 in `tem-sign-artifact-bugs`).

---

## Self-Review

- **Spec coverage:** realistic-leg-unchanged (Global Constraints + Task 2 Step 3 keeps `base`); ramp-and-saturate offsets (Task 1 `_ramp`, Task 2 wiring); type/size/quality ceiling (Task 1 `_opt_ceil` + `_quality_frac`); guard-respecting signal (Task 1 `_band_growth_signal`); DDM excluded (Task 2 Step 3 `distorted_cap < GROWTH_CAP_BASE` branch); inertness on mature names (floors = prior offsets, Task 3 canaries); dead-constant cleanup (Task 2 Step 5); measured effect (Task 3). All spec sections map to a task.
- **Placeholders:** none — every code and value is concrete (values computed against the proposed logic, not hand-derived).
- **Type consistency:** helper signatures in Task 1 Interfaces match their call sites in Task 2 Step 3 (`_band_growth_signal(fin)`, `_ramp(g, lo, hi, at_lo, at_hi)`, `_opt_ceil(fin, stock_type)`); constant names identical across Global Constraints, Task 1, and Task 2.
