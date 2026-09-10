# EV/EBITDA Terminal-Multiple Temper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Temper the terminal EV/EBITDA exit multiple toward a mature anchor for thin-gross-margin forward-tier names, so a commodity manufacturer (FN) isn't handed a franchise multiple, while high-gross-margin franchises are left byte-unchanged.

**Architecture:** A gross-margin quality fraction blends the existing growth-coupled ceiling in `_ev_ebitda_ceiling` toward a derived mature anchor. Gross margin is sourced into the `fin` dict in `engine.run()` beside the existing WACC/ROIC signals and threaded through `calc_ev_ebitda`. When gross margin is absent the temper is a no-op (identity), so all existing behavior and tests are preserved.

**Tech Stack:** Python, pytest (`asyncio_mode=auto`), run from `backend/`.

**Spec:** `docs/superpowers/specs/2026-09-10-ev-ebitda-terminal-multiple-temper-design.md`

## Global Constraints

- Fair Value pipeline only — do NOT touch Quality, Moat, or R-R code paths.
- The temper applies ONLY to the `durable=True` branch of `_ev_ebitda_ceiling` (forward tiers with a historical multiple). The spot / non-durable path must return `EV_EBITDA_CAP` unchanged.
- Neutral fallback is mandatory: `gross_margin is None` → temper is identity (ceiling == today's growth ceiling). This preserves backward-compat and pipeline independence.
- `MATURE_EBITDA_MULT` is DERIVED, never hardcoded: `MATURE_EBITDA_MULT = QUALITY_CONV_HI * MATURE_MULTIPLE_FACTOR`.
- Gross margin is carried in `fin` as a PERCENT (e.g. `12.0`); `_ev_ebitda_ceiling` receives it as a FRACTION (e.g. `0.12`). The `/100` conversion happens in `calc_ev_ebitda` at the call site (matching `conversion`, which is already a fraction).
- Ramp band: `GM_TEMPER_LO = 0.25`, `GM_TEMPER_HI = 0.50` (fractions).
- Run tests from `backend/`: `python3 -m pytest`.

---

### Task 1: Gross-margin temper in `_ev_ebitda_ceiling`

**Files:**
- Modify: `backend/valuation/models.py` (constants near lines 57-69; function `_ev_ebitda_ceiling` at 206-224)
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: existing `EV_EBITDA_CAP`, `EV_EBITDA_CAP_CEIL`, `EV_EBITDA_CAP_CEIL_MEGA`, `QUALITY_CONV_HI`, `MATURE_MULTIPLE_FACTOR` (all in `models.py`).
- Produces: `MATURE_EBITDA_MULT`, `GM_TEMPER_LO`, `GM_TEMPER_HI` module constants; new signature
  `_ev_ebitda_ceiling(growth, durable, mega=False, conversion=None, gross_margin=None) -> float` where `gross_margin` is a fraction or None.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_models.py`:

```python
def test_ev_ebitda_ceiling_tempered_by_thin_gross_margin():
    # A thin-gross-margin commodity name (12%) growing fast still gets a 30x
    # growth ceiling today; the temper floors it to the mature anchor instead.
    mature = m.QUALITY_CONV_HI * m.MATURE_MULTIPLE_FACTOR
    assert m._ev_ebitda_ceiling(0.30, durable=True, gross_margin=0.12) == pytest.approx(mature)
    assert m.MATURE_EBITDA_MULT == pytest.approx(mature)


def test_ev_ebitda_ceiling_gross_margin_franchise_unchanged():
    # High gross margin (>= GM_TEMPER_HI) -> no temper -> today's growth ceiling.
    assert m._ev_ebitda_ceiling(0.30, durable=True, gross_margin=0.80) == pytest.approx(30.0)


def test_ev_ebitda_ceiling_gross_margin_none_is_identity():
    # Missing gross margin -> identity fallback (byte-identical to pre-temper).
    assert m._ev_ebitda_ceiling(0.30, durable=True, gross_margin=None) == pytest.approx(30.0)
    assert m._ev_ebitda_ceiling(0.20, durable=True, gross_margin=None) == pytest.approx(25.0)


def test_ev_ebitda_ceiling_gross_margin_ramps_between_anchors():
    # Midpoint gross (0.375) -> half-way between MATURE and the growth ceiling.
    mature = m.QUALITY_CONV_HI * m.MATURE_MULTIPLE_FACTOR
    expected = mature + 0.5 * (30.0 - mature)
    assert m._ev_ebitda_ceiling(0.30, durable=True, gross_margin=0.375) == pytest.approx(expected)
    # Band edges.
    assert m._ev_ebitda_ceiling(0.30, durable=True, gross_margin=0.25) == pytest.approx(mature)
    assert m._ev_ebitda_ceiling(0.30, durable=True, gross_margin=0.50) == pytest.approx(30.0)


def test_ev_ebitda_ceiling_spot_path_ignores_gross_margin():
    # Non-durable (spot) multiple path is untouched: always EV_EBITDA_CAP.
    assert m._ev_ebitda_ceiling(0.30, durable=False, gross_margin=0.12) == pytest.approx(20.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_models.py -k "gross_margin or tempered" -v`
Expected: FAIL — `_ev_ebitda_ceiling() got an unexpected keyword argument 'gross_margin'` and `AttributeError: MATURE_EBITDA_MULT`.

- [ ] **Step 3: Add the constants**

In `backend/valuation/models.py`, immediately after the `MATURE_MULTIPLE_FACTOR` definition (line 67), add:

```python
# Thin-gross-margin terminal-multiple temper (see 2026-09-10 spec). A durable
# forward-tier multiple is blended toward MATURE_EBITDA_MULT as gross margin
# falls from GM_TEMPER_HI (franchise, no temper) to GM_TEMPER_LO (commodity,
# full temper). The anchor is DERIVED, not tuned to any ticker: a matured
# business whose growth-capex has ended converts ~QUALITY_CONV_HI of EBITDA to
# cash, capitalized at the model's own Gordon factor. Gross margin (immune to
# SBC/amortization, unlike op margin, and to capital structure, unlike ROIC) is
# the franchise-vs-commodity discriminator; a full-universe sweep confirmed it
# spares every high-gross franchise and moves only FN's verdict. FN 26x->~13x.
MATURE_EBITDA_MULT = QUALITY_CONV_HI * MATURE_MULTIPLE_FACTOR  # 0.90 * 14.714 = 13.24x
GM_TEMPER_LO = 0.25
GM_TEMPER_HI = 0.50
```

- [ ] **Step 4: Add the gross_margin parameter and temper blend**

In `backend/valuation/models.py`, change the `_ev_ebitda_ceiling` signature (line 206-207) from:

```python
def _ev_ebitda_ceiling(growth: float | None, durable: bool, mega: bool = False,
                       conversion: float | None = None) -> float:
```

to:

```python
def _ev_ebitda_ceiling(growth: float | None, durable: bool, mega: bool = False,
                       conversion: float | None = None,
                       gross_margin: float | None = None) -> float:
```

Then replace the final return line (currently line 224):

```python
    return EV_EBITDA_CAP + max(g_frac, q_frac) * (top - EV_EBITDA_CAP)
```

with:

```python
    growth_ceiling = EV_EBITDA_CAP + max(g_frac, q_frac) * (top - EV_EBITDA_CAP)
    # Thin-gross-margin temper: blend the growth ceiling toward the mature anchor
    # by a gross-margin quality fraction (identity when gross margin is unknown).
    if gross_margin is None:
        return growth_ceiling
    gm_frac = (0.0 if gross_margin <= GM_TEMPER_LO
               else min(1.0, (gross_margin - GM_TEMPER_LO) / (GM_TEMPER_HI - GM_TEMPER_LO)))
    return MATURE_EBITDA_MULT + gm_frac * (growth_ceiling - MATURE_EBITDA_MULT)
```

Also extend the docstring's summary line to mention the gross-margin temper (one sentence) so the design intent stays with the code.

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `python3 -m pytest tests/test_models.py -k "gross_margin or tempered" -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Run the full existing ceiling suite to confirm no regression**

Run: `python3 -m pytest tests/test_models.py -k "ev_ebitda" -v`
Expected: PASS — the pre-existing ceiling tests (`test_ev_ebitda_ceiling_ramps_with_growth`, `..._lifted_by_quality...`, `..._quality_takes_the_greater_fraction`, `..._mega...`, and all `calc_ev_ebitda` tests) are unchanged because they pass no `gross_margin` → identity fallback.

- [ ] **Step 7: Commit**

```bash
git add backend/valuation/models.py backend/tests/test_models.py
git commit -m "feat(valuation): gross-margin temper for _ev_ebitda_ceiling

Blend the durable growth ceiling toward MATURE_EBITDA_MULT
(= QUALITY_CONV_HI * MATURE_MULTIPLE_FACTOR) as gross margin falls
0.50->0.25. Identity when gross margin is None (backward-compat).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01G4hXRNJQbuMgZRUHEiZk7J"
```

---

### Task 2: Thread gross margin through `calc_ev_ebitda`

**Files:**
- Modify: `backend/valuation/models.py` (`calc_ev_ebitda`, the `_ev_ebitda_ceiling` call at 424-425)
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `_ev_ebitda_ceiling(..., gross_margin=<fraction or None>)` from Task 1; `fin["gross_margin"]` (percent) when present.
- Produces: `calc_ev_ebitda` reads `fin.get("gross_margin")` (percent), converts to a fraction, and passes it to `_ev_ebitda_ceiling`. No signature change to `calc_ev_ebitda`.

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_models.py`:

```python
def test_calc_ev_ebitda_thin_gross_margin_tempers_leg():
    # Forward-tier durable leg: a thin-gross-margin name's exit multiple is
    # floored to the mature anchor, lowering the leg vs an untempered run.
    base = {"ebitda_ttm": 1_000_000, "shares_outstanding": 1_000, "net_debt": 0,
            "revenue_growth": 0.44, "market_cap": 15_000_000_000}
    scen = {"optimistic": 0.35, "realistic": 0.25, "pessimistic": 0.13}
    none_gm = m.calc_ev_ebitda(base, scen, hist_multiple=26.0, compress=False)["fair_value"]
    franchise = m.calc_ev_ebitda({**base, "gross_margin": 80.0}, scen,
                                 hist_multiple=26.0, compress=False)["fair_value"]
    commodity = m.calc_ev_ebitda({**base, "gross_margin": 12.0}, scen,
                                 hist_multiple=26.0, compress=False)["fair_value"]
    # High gross margin -> identical to the no-gross-margin run.
    assert franchise == pytest.approx(none_gm)
    # Thin gross margin -> tempered lower.
    assert commodity < none_gm


def test_calc_ev_ebitda_gross_margin_only_affects_durable_leg():
    # Spot (non-durable, no hist_multiple) multiple path is untouched by gross margin.
    base = {"ebitda_ttm": 1_000_000, "shares_outstanding": 1_000, "net_debt": 0,
            "revenue_growth": 0.44, "market_cap": 15_000_000_000, "ev_ebitda": 26.0}
    scen = {"optimistic": 0.35, "realistic": 0.25, "pessimistic": 0.13}
    no_gm = m.calc_ev_ebitda(base, scen, compress=False)["fair_value"]
    thin = m.calc_ev_ebitda({**base, "gross_margin": 12.0}, scen, compress=False)["fair_value"]
    assert thin == pytest.approx(no_gm)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_models.py -k "calc_ev_ebitda_thin or only_affects_durable" -v`
Expected: FAIL — `commodity` equals `none_gm` (temper not wired), so `commodity < none_gm` fails.

- [ ] **Step 3: Wire gross margin into the ceiling call**

In `backend/valuation/models.py`, replace the `_ev_ebitda_ceiling` call in `calc_ev_ebitda` (currently lines 424-425):

```python
    multiple = min(multiple, _ev_ebitda_ceiling(
        g_demo, durable=hist_multiple is not None, mega=mega, conversion=conversion))
```

with:

```python
    # Gross margin (percent in fin) -> fraction for the thin-gross-margin temper.
    gm = fin.get("gross_margin")
    gm_frac = gm / 100.0 if gm is not None else None
    multiple = min(multiple, _ev_ebitda_ceiling(
        g_demo, durable=hist_multiple is not None, mega=mega, conversion=conversion,
        gross_margin=gm_frac))
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `python3 -m pytest tests/test_models.py -k "calc_ev_ebitda_thin or only_affects_durable" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full models suite**

Run: `python3 -m pytest tests/test_models.py -v`
Expected: PASS — no regression (all pre-existing `calc_ev_ebitda` tests pass no `gross_margin` in `fin` → identity).

- [ ] **Step 6: Commit**

```bash
git add backend/valuation/models.py backend/tests/test_models.py
git commit -m "feat(valuation): thread gross margin into calc_ev_ebitda ceiling

Reads fin['gross_margin'] (percent), converts to fraction, passes to
_ev_ebitda_ceiling. No-op when absent.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01G4hXRNJQbuMgZRUHEiZk7J"
```

---

### Task 3: Source gross margin in `engine.run()` + full regression / live re-validation

**Files:**
- Modify: `backend/valuation/engine.py` (WACC/ROIC sourcing block, lines 798-801)
- Modify: `.claude/memory/fn-ev-ebitda-terminal-multiple-temper.md` (status → DONE)

**Interfaces:**
- Consumes: `met = compute_metrics(sinp)` already computed in `run()`; `met.gross_margin` (percent scalar).
- Produces: `fin["gross_margin"]` populated live, consumed by `calc_ev_ebitda` (Task 2).

- [ ] **Step 1: Add the sourcing line**

In `backend/valuation/engine.py`, in the `try:` block that sources screener signals (after line 801, `fin["roic_5y_avg"] = met.roic_5y_avg`), add:

```python
            fin["gross_margin"] = met.gross_margin
```

This mirrors the adjacent WACC/spread/ROIC sourcing and is failure-isolated by the surrounding `except Exception: pass` — if the screener fetch fails, `gross_margin` stays absent and the temper is a no-op (neutral fallback), exactly like the WACC signals.

- [ ] **Step 2: Run the full backend test suite (regression gate)**

Run: `python3 -m pytest`
Expected: PASS — full suite green. No test supplies `fin["gross_margin"]` via synthetic input, so evaluate/engine tests are unchanged; the new Task 1/2 tests pass.

- [ ] **Step 3: Live re-validate FN (the target)**

Run: `python3 ".claude/skills/validating-agent-stock/validate_ticker.py" FN` from the repo root.
Expected: FN `fair_value` drops from ~$769 to roughly **$440–460** (EV/EBITDA leg multiple floored from ~26x to ~13.2x); `price_vs_fair_value_pct` moves from ~+83% to roughly **+5% to +10%**. Exact number moves with live data; the direction and rough magnitude are the check.

- [ ] **Step 4: Live-confirm canaries are unmoved / verdict-neutral**

Run the harness for the canaries: `python3 ".claude/skills/validating-agent-stock/validate_ticker.py" <T>` for `CDNS`, `NOW`, `KLAC`, `ANET`, `NBIS`, `IREN`.
Expected: `CDNS`, `NOW`, `KLAC`, `ANET` fair values **unchanged** (high gross margin or no durable temper); `NBIS`, `IREN` **unchanged** (non-durable path). If any franchise moves materially, STOP — the band or sourcing is wrong.

- [ ] **Step 5: Update the memory note**

Edit `.claude/memory/fn-ev-ebitda-terminal-multiple-temper.md`: change the status from "brainstorm PAUSED" to "DONE on branch `ev-ebitda-terminal-multiple-temper`", record the final FN number from Step 3, the constants shipped (`MATURE_EBITDA_MULT = QUALITY_CONV_HI * MATURE_MULTIPLE_FACTOR`, `GM_TEMPER_LO/HI = 0.25/0.50`), and the canaries verified unmoved. Update the matching `MEMORY.md` index line.

- [ ] **Step 6: Commit**

```bash
git add backend/valuation/engine.py .claude/memory/fn-ev-ebitda-terminal-multiple-temper.md .claude/memory/MEMORY.md
git commit -m "feat(valuation): source gross margin into fin for the EV/EBITDA temper

engine.run() populates fin['gross_margin'] from screener metrics
(failure-isolated). FN FV ~\$769 -> ~\$450; franchises + non-durable
names unchanged. Memory note updated.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01G4hXRNJQbuMgZRUHEiZk7J"
```

---

## Self-Review

**1. Spec coverage:**
- Signal = gross margin sourced into `fin` → Task 3 Step 1. ✓
- Action = temper durable branch of `_ev_ebitda_ceiling` → Task 1. ✓
- Mature anchor derived `QUALITY_CONV_HI * MATURE_MULTIPLE_FACTOR` → Task 1 Step 3 + test Step 1. ✓
- Ramp band 0.25→0.50 → Task 1 constants + edge tests. ✓
- Percent→fraction conversion at call site → Task 2 Step 3. ✓
- Neutral fallback (None → identity) → Task 1 test `..._none_is_identity`, Task 2 `franchise == none_gm`. ✓
- Spot path untouched → Task 1 `..._spot_path_ignores...`, Task 2 `..._only_affects_durable_leg`. ✓
- Blast radius / canaries → Task 3 Steps 3-4. ✓
- Files touched (models.py, engine.py, tests) → all covered. ✓

**2. Placeholder scan:** No TBD/TODO; every code + test step has concrete content and exact run/expected lines. ✓

**3. Type consistency:** `_ev_ebitda_ceiling(..., gross_margin: float | None = None)` (fraction) defined in Task 1, called with `gross_margin=gm_frac` in Task 2, fed from `fin["gross_margin"]` (percent, ÷100) sourced in Task 3. `MATURE_EBITDA_MULT`/`GM_TEMPER_LO`/`GM_TEMPER_HI` defined in Task 1, used only there. Consistent. ✓
