# Fade-band growth relief for the $150B–$1T tier

**Date:** 2026-07-19
**Status:** Approved design, ready for implementation plan
**Scope:** Fair Value pipeline only (`backend/valuation/models.py`). No Quality Score change.

## Problem

The FV engine fades near-term growth toward the 3% terminal rate over a 10-year
horizon. How long growth is *held* before it fades (the "hold") is set by
`_fade_hold_years(market_cap, revenue_growth)` and keyed to market-cap band:

| Band | Hold | Constant |
|---|---|---|
| `< $150B` | 5 yr | `FADE_HOLD_MID` |
| `$150B–$1T` | 3 yr | `FADE_HOLD_LARGE` |
| `>= $1T` | 0 yr (fade from yr 1) | `FADE_HOLD_MEGA` |
| `>= $1T` **and** `revenue_growth >= 0.40` | 5 yr (relief) | `FADE_HOLD_MID` via `MEGA_CAP_GROWTH_RELIEF` |

The design intent is **monotonic**: a larger company faces more base-rate drag on
sustained growth, so it gets a shorter hold and fades faster. The mega band carries
a *growth-relief valve* — "if the hyper-growth is demonstrably present, waive the
size penalty" — that reverts a fast-growing mega-cap back to the 5-year hold.

**The bug:** that relief valve was wired only to the mega band. The `$150B–$1T`
band has no equivalent, which makes the hold **non-monotonic** in size. Holding
growth fixed and varying only market cap:

- `< $150B` grower → hold **5**
- `$150B–$1T` grower → hold **3**  ← penalty trough
- `>= $1T` grower (>40%) → hold **5** (relief)

A company in the middle band is faded *harder* than both a smaller and a larger
company growing at the identical rate. There is no economic story in which a $317B
hyper-grower should be assumed to decelerate faster than a $120B or a $1.2T one at
the same growth. It is an artifact of the valve covering one of the two bands that
need it.

**Live example — PLTR (2026-07-19):** market cap $317B, revenue growth 84.7% →
lands in the `$150B–$1T` band → hold 3. Its DCF and EV/EBITDA legs fade two years
sooner than an otherwise-identical smaller or mega-cap peer.

## Goal

Restore monotonicity: at any fixed growth rate, a larger company never holds growth
*longer* than a smaller one. Apply the existing "demonstrably fast → waive the size
penalty" principle uniformly across bands.

Non-goals (explicitly out of scope):
- Reworking the fade into a shorter-horizon / constant-growth / scenario-banded-
  multiple model (considered and deferred — large rewrite, re-opens every
  fade-calibrated ticker).
- Adding scenario-banded exit multiples to restore scenario dispersion (a real,
  separate gap — the growth cap collapses optimistic==realistic for hyper-growers —
  but its own project).

## Design

A single, additive change to `_fade_hold_years` in `backend/valuation/models.py`:
the `$150B–$1T` branch gains the same growth check the mega branch already has.

```python
def _fade_hold_years(market_cap, revenue_growth=None):
    mc = market_cap or 0
    if mc >= MEGA_CAP_FLOOR:                              # >= $1T  (unchanged)
        if (revenue_growth or 0) >= MEGA_CAP_GROWTH_RELIEF:
            return FADE_HOLD_MID
        return FADE_HOLD_MEGA
    if mc >= LARGE_CAP_FADE_FLOOR:                        # $150B–$1T
        if (revenue_growth or 0) >= MEGA_CAP_GROWTH_RELIEF:  # NEW: mirror the mega valve
            return FADE_HOLD_MID
        return FADE_HOLD_LARGE
    return FADE_HOLD_MID                                  # < $150B (unchanged)
```

**Decisions (all "mirror the mega valve"):**
- **Shape:** step, not graduated. Matches the discontinuity the mega band already
  accepts; a graduated hold would be a new mechanism inconsistent with the mega band
  unless both were converted (larger blast radius). User chose step.
- **Threshold:** reuse `MEGA_CAP_GROWTH_RELIEF` (0.40). No new constant.
- **Relief hold:** `FADE_HOLD_MID` (5). Same target as the mega valve and the
  small-cap band → restores exact monotonicity.
- **Metric:** `revenue_growth` (`fin['revenue_growth']`), the same input the mega
  valve reads. Both `calc_dcf` and `calc_ev_ebitda` already pass it.

The inline comment at the mega-band relief should be extended (or a sibling comment
added) to record that the middle band mirrors it and why.

## Effect (measured, read-only)

Method: reconstruct each ticker's live `fin` (`extract_financials` + `real_fcf`),
run `valuation.engine.evaluate(fin)` with the current `_fade_hold_years` vs the
patched version, diff the composite `fair_value`.

- **PLTR:** hold 3 → 5. DCF leg $35.16 → $40.25, EV/EBITDA $26.31 → $31.22, P/E
  unchanged → composite **FV $48.42 → $52.42 (+8.3%)**, verdict −63.4% → −60.4%.
  Still overvalued: this is an internal-consistency correction, not a re-rating.
- **Quality Score:** unaffected. The fade lives only in the FV pipeline; the two
  pipelines share no fade code.

## Blast radius

The patched function returns a different value **only** when
`$150B <= market_cap < $1T` **and** `revenue_growth >= 0.40`. Every ticker outside
that box is byte-identical, so the blast radius is exactly the set of names in it.

Read-only sweep across the 27-ticker test universe (PLTR, NBIS, VRT, IREN, KLAC,
NVDA, AVGO, SNPS, CRWV, TEM, ANET, BWXT, META, MSFT, GOOGL, AAPL, V, MA, JPM, COST,
HOOD, AMD, VST, APP, CDNS, NFLX, KO):

- **PLTR is the only name that moves** (+8.3%).
- All 26 others unchanged, including the regression canaries **IREN, NBIS, KLAC**.

Nearest boundaries (unaffected, but document the edges):
- **AMD** — $808B, 38% growth: in-band but just under the 40% threshold. This is the
  residual step cliff, identical in kind to the one the mega band already has.
- **APP** — $143B, 59% growth: just *below* the $150B floor, so it already gets the
  5-year hold. The fix does not touch it, and makes the $150B boundary less jagged
  (>40% growers now get 5y on both sides of it).

## Accepted limitation

The step leaves a threshold discontinuity at 40% growth (an in-band name at 39% gets
3y, at 41% gets 5y). Deliberate: it mirrors the cliff the mega band already carries,
which is the "mirror the mega valve" decision. A graduated relief that removes the
cliff was considered and set aside as a larger, wider-blast-radius change.

## Testing (TDD, RED first)

1. **Unit test on the pure `_fade_hold_years`** pinning all four regimes:
   - `< $150B` → 5 (any growth)
   - `$150B–$1T`, growth `< 0.40` → 3
   - `$150B–$1T`, growth `>= 0.40` → 5  **(new behavior — the RED assertion)**
   - `>= $1T`, growth `< 0.40` → 0; `>= 0.40` → 5 (unchanged)
   Include a boundary case at exactly `0.40` and at the `$150B` / `$1T` edges.
2. **Regression assertion via `evaluate`:** a `$150B–$1T`, `>40%` fixture lifts the
   composite FV; an in-band `<40%` fixture (AMD-like) does not move.
3. **Full suite green:** `pytest` from `backend/` (`asyncio_mode=auto`) passes.
4. **Re-validate live** after the change: PLTR moves to ~$52.42; canaries IREN, NBIS,
   KLAC unchanged.

## Follow-up (record in memory when landed)

- Note the fix, that it reuses `MEGA_CAP_GROWTH_RELIEF` / `FADE_HOLD_MID`, and that
  the blast radius was verified to be PLTR-only across the test universe.
- Flag the deferred, separate gap: scenario dispersion is collapsed for capped
  hyper-growers (optimistic == realistic) and exit multiples are not scenario-banded.
  Link to this spec.
