# Fade-Band Growth Relief ($150B–$1T tier) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the mega-band growth-relief valve to the `$150B–$1T` fade band in `_fade_hold_years`, restoring monotonicity so a fast grower there (e.g. PLTR) is no longer faded harder than both smaller and larger peers at the same growth rate.

**Architecture:** One additive branch in `backend/valuation/models.py::_fade_hold_years`. The `$150B–$1T` band gains the identical `revenue_growth >= MEGA_CAP_GROWTH_RELIEF` check the `>= $1T` band already carries, returning `FADE_HOLD_MID` (5) instead of `FADE_HOLD_LARGE` (3) when the growth is demonstrably present. No new constants; no change to any other leg, tier, cap, or the Quality pipeline.

**Tech Stack:** Python 3.14, pytest (`asyncio_mode=auto`), run from `backend/`. Python interpreter: `C:/Users/f_lub/AppData/Local/Python/bin/python3.exe`.

## Global Constraints

- Reuse existing constants only — `MEGA_CAP_GROWTH_RELIEF` (0.40), `FADE_HOLD_MID` (5), `FADE_HOLD_LARGE` (3), `LARGE_CAP_FADE_FLOOR` ($150B), `MEGA_CAP_FLOOR` ($1T). Do NOT introduce a new constant.
- Change is scoped to `_fade_hold_years` only. Do not touch `calc_dcf`, `calc_ev_ebitda`, the classifier, or any scoring code.
- FV pipeline only. The Quality Score must be provably unaffected (no shared code path).
- Blast radius is PLTR-only across the test universe; the regression canaries **IREN, NBIS, KLAC** must not move.
- Tests run from the `backend/` directory. Spec: `docs/superpowers/specs/2026-07-19-fade-band-relief-design.md`.

---

### Task 1: Extend the growth-relief valve to the $150B–$1T fade band

**Files:**
- Modify: `backend/valuation/models.py` (`_fade_hold_years`, ~lines 186–198)
- Test: `backend/tests/test_models.py` (add beside the existing fade tests, ~line 224)

**Interfaces:**
- Consumes: `m._fade_hold_years(market_cap, revenue_growth=None) -> int`; constants `m.MEGA_CAP_GROWTH_RELIEF`, `m.FADE_HOLD_MID`, `m.FADE_HOLD_LARGE`, `m.FADE_HOLD_MEGA`; the module-level `GROWTH` scenario fixture already defined in `test_models.py`; `m.calc_dcf(fin: dict, growth: dict) -> dict` returning `{"fair_value": float, ...}`.
- Produces: no new public symbol — the behavior of `_fade_hold_years` changes for the `$150B–$1T` / `>=0.40` case only. Later tasks: none.

- [ ] **Step 1: Write the failing tests**

Add these three tests to `backend/tests/test_models.py` immediately after `test_dcf_fade_relieved_for_high_growth_mega_cap` (after line 232). They mirror the existing mega-band relief tests, applied to the `$150B–$1T` band, plus an explicit monotonicity check.

```python
def test_fade_relief_for_high_growth_large_cap():
    # The $150B-$1T band mirrors the mega valve: a fast grower there keeps the
    # small-cap hold (FADE_HOLD_MID) instead of the faster mid-band fade. Restores
    # monotonicity -- a mid-band grower must not fade harder than smaller AND larger
    # peers at the same rate (e.g. PLTR at ~$317B / ~85% growth).
    mc = 300_000_000_000
    assert m._fade_hold_years(mc, m.MEGA_CAP_GROWTH_RELIEF) == m.FADE_HOLD_MID
    assert m._fade_hold_years(mc, m.MEGA_CAP_GROWTH_RELIEF - 0.01) == m.FADE_HOLD_LARGE
    assert m._fade_hold_years(mc, None) == m.FADE_HOLD_LARGE   # no growth signal -> mid-band fade


def test_fade_hold_years_monotonic_at_high_growth():
    # At a fixed high growth rate, a larger company never holds LONGER than a smaller
    # one: small (<$150B) == large ($150B-$1T) == mega (>=$1T) all == FADE_HOLD_MID.
    g = 0.50
    small = m._fade_hold_years(40_000_000_000, g)
    large = m._fade_hold_years(300_000_000_000, g)
    mega = m._fade_hold_years(2_000_000_000_000, g)
    assert small == large == mega == m.FADE_HOLD_MID


def test_dcf_fade_relieved_for_high_growth_large_cap():
    # Same $300B company: a 45% grower fades gentler (higher FV) than a flat one.
    base = {"fcf_ttm": 1_000_000, "net_debt": 0, "shares_outstanding": 100_000,
            "market_cap": 300_000_000_000}
    fast = m.calc_dcf({**base, "revenue_growth": 0.45}, GROWTH)["fair_value"]
    flat = m.calc_dcf({**base, "revenue_growth": 0.05}, GROWTH)["fair_value"]
    assert fast > flat
```

- [ ] **Step 2: Run the new tests to verify they FAIL (RED)**

Run (from `backend/`):
```
"C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" -m pytest tests/test_models.py::test_fade_relief_for_high_growth_large_cap tests/test_models.py::test_fade_hold_years_monotonic_at_high_growth tests/test_models.py::test_dcf_fade_relieved_for_high_growth_large_cap -v
```
Expected: all three FAIL. `_fade_hold_years(300B, 0.40)` currently returns `FADE_HOLD_LARGE` (3), so the first assertion fails with `3 == 5`; the monotonic test fails because `large` (3) != `FADE_HOLD_MID` (5); the DCF test fails because `fast` and `flat` are equal (both held 3 years).

- [ ] **Step 3: Write the minimal implementation**

In `backend/valuation/models.py`, add the growth check to the `$150B–$1T` branch of `_fade_hold_years`, and update the docstring. Replace the current function body:

```python
def _fade_hold_years(market_cap: float | None, revenue_growth: float | None = None) -> int:
    """Years near-term growth is held before fading to TERMINAL_GROWTH, keyed to
    size: mega-caps (>= $1T) fade immediately, mid/small names hold growth longer.
    A company still growing above MEGA_CAP_GROWTH_RELIEF keeps the small-cap hold
    (its size penalty is waived while the hyper-growth is demonstrably present) --
    applied to BOTH the mega (>= $1T) and the $150B-$1T bands so the hold is
    monotonic in size: a larger company never holds longer than a smaller one at
    the same growth rate (e.g. PLTR at ~$317B / ~85% is no longer faded harder than
    a <$150B or a >$1T peer growing as fast)."""
    mc = market_cap or 0
    if mc >= MEGA_CAP_FLOOR:
        if (revenue_growth or 0) >= MEGA_CAP_GROWTH_RELIEF:
            return FADE_HOLD_MID
        return FADE_HOLD_MEGA
    if mc >= LARGE_CAP_FADE_FLOOR:
        if (revenue_growth or 0) >= MEGA_CAP_GROWTH_RELIEF:
            return FADE_HOLD_MID
        return FADE_HOLD_LARGE
    return FADE_HOLD_MID
```

- [ ] **Step 4: Run the new tests to verify they PASS (GREEN)**

Run (from `backend/`):
```
"C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" -m pytest tests/test_models.py::test_fade_relief_for_high_growth_large_cap tests/test_models.py::test_fade_hold_years_monotonic_at_high_growth tests/test_models.py::test_dcf_fade_relieved_for_high_growth_large_cap -v
```
Expected: all three PASS.

- [ ] **Step 5: Run the full fade-band group to confirm no existing test regressed**

The pre-existing `test_fade_hold_years_bands` calls `_fade_hold_years(300B)` with no growth arg, which still returns `FADE_HOLD_LARGE` — it must stay green.

Run (from `backend/`):
```
"C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" -m pytest tests/test_models.py -k fade -v
```
Expected: every `fade` test PASSES, including `test_fade_hold_years_bands`, `test_dcf_fade_is_more_aggressive_for_mega_caps`, `test_fade_relief_for_high_growth_mega_cap`.

- [ ] **Step 6: Run the full suite green**

Run (from `backend/`):
```
"C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" -m pytest
```
Expected: all tests PASS (no failures, no errors). This is the whole-pipeline regression gate.

- [ ] **Step 7: Live re-validation of the ticker and canaries**

Confirm the live effect and that the canaries do not move, using the read-only skill harness (from the repo root `C:/Users/f_lub/proj/Agent Stock`):
```
"C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" ".claude/skills/validating-agent-stock/validate_ticker.py" PLTR
"C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" ".claude/skills/validating-agent-stock/validate_ticker.py" NBIS
"C:/Users/f_lub/AppData/Local/Python/bin/python3.exe" ".claude/skills/validating-agent-stock/validate_ticker.py" VRT
```
Expected: **PLTR** FV rises ~8% (to roughly $52; exact cents drift with live data) and stays deeply overvalued. **NBIS** ($45B, <$150B) and **VRT** ($111B, <$150B) are unchanged from their pre-change values — both sit below `LARGE_CAP_FADE_FLOOR`, so `_fade_hold_years` returns byte-identical results for them. (KLAC at $278B / 12% growth is in-band but <40%, so also unaffected; NBIS/VRT are the project's convention test tickers and the cheapest live confirmation.)

- [ ] **Step 8: Commit**

Run (from repo root):
```bash
git add backend/valuation/models.py backend/tests/test_models.py
git commit -m "fix(valuation): growth relief for the \$150B-\$1T fade band

Extend the mega-band growth-relief valve to the \$150B-\$1T band in
_fade_hold_years so the hold is monotonic in size: a mid-band hyper-grower
(PLTR, ~\$317B/~85%) no longer fades harder than both smaller and larger peers
at the same rate. Step shape mirroring the mega valve; reuses
MEGA_CAP_GROWTH_RELIEF/FADE_HOLD_MID. PLTR FV +8% (still overvalued), Quality
unaffected, blast radius PLTR-only across the test universe (IREN/NBIS/KLAC
unmoved). Spec: docs/superpowers/specs/2026-07-19-fade-band-relief-design.md

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0151XW1XyrVFMLfsGXG7r17Q"
```

- [ ] **Step 9: Record the fix in memory**

Create `C:\Users\f_lub\.claude\projects\C--Users-f-lub-proj-Agent-Stock\memory\pltr-fade-band-relief.md`:

```markdown
---
name: pltr-fade-band-relief
description: "$150B-$1T fade band had no growth-relief valve; PLTR faded harder than smaller AND larger peers at the same growth rate"
metadata:
  type: project
---

`_fade_hold_years` was non-monotonic: the mega (>= $1T) band had a growth-relief
valve (`MEGA_CAP_GROWTH_RELIEF` 0.40 -> `FADE_HOLD_MID` 5) but the $150B-$1T band
did not, so a fast grower there got only a 3y hold (`FADE_HOLD_LARGE`) while both a
<$150B and a >$1T peer growing at the same rate got 5y. PLTR ($317B, ~85% growth)
sat in the trough. Fixed by mirroring the mega valve into the $150B-$1T branch
(step shape, reuses the same constants -- no new knob). PLTR FV +8.3%
($48.42 -> $52.42, still ~-60% overvalued -- an internal-consistency fix, not a
re-rating). Quality Score unaffected (fade is FV-only). Blast radius verified
PLTR-only across the 27-ticker test universe; canaries IREN/NBIS/KLAC unmoved.
Nearest near-miss: AMD ($808B, 38%) -- in-band but just below the 0.40 cliff (the
residual step discontinuity, identical in kind to the mega band's). See
[[size-coupled-growth-fade]]. DEFERRED separate gap: scenario dispersion collapses
for capped hyper-growers (optimistic == realistic) and exit multiples are not
scenario-banded -- its own future project.
Spec: docs/superpowers/specs/2026-07-19-fade-band-relief-design.md
```

Then add one line to `C:\Users\f_lub\.claude\projects\C--Users-f-lub-proj-Agent-Stock\memory\MEMORY.md`:

```markdown
- [PLTR fade-band relief](pltr-fade-band-relief.md) — $150B-$1T band had no growth-relief valve so PLTR faded harder than smaller & larger peers; mirrored the mega valve, PLTR FV +8%, blast radius PLTR-only, canaries unmoved
```

Commit (from repo root):
```bash
git add "C:/Users/f_lub/.claude/projects/C--Users-f-lub-proj-Agent-Stock/memory/pltr-fade-band-relief.md" "C:/Users/f_lub/.claude/projects/C--Users-f-lub-proj-Agent-Stock/memory/MEMORY.md"
git commit -m "docs(memory): record PLTR fade-band relief fix"
```
Note: the memory dir is outside the repo working tree — if `git add` reports it is not tracked / outside the repository, skip the commit; writing the files is sufficient (they are the persistent memory store, not repo content).

---

## Self-Review

**1. Spec coverage:**
- Problem (non-monotonic middle band) → Task 1 Step 3. ✓
- Design (step, reuse `MEGA_CAP_GROWTH_RELIEF`/`FADE_HOLD_MID`, `revenue_growth`) → Step 3. ✓
- Effect (PLTR +8%, Quality unaffected) → Step 7 live check. ✓
- Blast radius PLTR-only, canaries unmoved → Steps 6–7. ✓
- Testing (unit pins all bands incl. new relief + `<40%` no-relief; full suite green) → Steps 1–6. The spec suggested an `evaluate`-based "in-band <40% does not move" guard; this plan uses the exact unit assertion `_fade_hold_years(300B, 0.39) == FADE_HOLD_LARGE` (Step 1) plus the DCF `flat` case, which is a more precise and cheaper regression guard than an `evaluate` diff. ✓
- Follow-up memory + deferred scenario-dispersion note → Step 9. ✓

**2. Placeholder scan:** No TBD/TODO/"handle edge cases"/"write tests for the above". All test and implementation code is complete and inline. ✓

**3. Type consistency:** `_fade_hold_years(market_cap, revenue_growth=None) -> int`, `calc_dcf(fin, growth) -> {"fair_value": ...}`, constant names, and the `GROWTH` fixture all match `backend/valuation/models.py` and the existing `backend/tests/test_models.py`. ✓
