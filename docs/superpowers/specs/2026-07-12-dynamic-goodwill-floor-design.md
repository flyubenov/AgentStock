# Dynamic Goodwill Floor for the Section II Acquisition-ROIC Adjustment

**Date:** 2026-07-12
**Status:** Approved
**Area:** `backend/screener` (scoring)

## Problem

The Screener rated **VST (Vistra Corp.) 5.0**, understating a merchant power producer
whose weakness is concentrated in **Section II (Returns on Capital) = 3.5** at 0.25
weight. Its ROIC sub-scores:

| Sub-score | Reported | Ex-goodwill | Band score (reported) |
|---|---|---|---|
| ROIC (TTM) | 7.8% | 10.1% | 4.0 |
| ROIC (5y avg) | 8.3% | 11.0% | 4.0 |
| ROIC − WACC spread | −1.8% | **+0.5%** | 2.5 |

VST carries goodwill/intangibles from the Energy Harbor / Dynegy / Ambit acquisitions —
**23% of invested capital**. This is the *same distortion* the existing
`_acquisition_distorted` adjustment (built for AMD) corrects: goodwill inflates invested
capital and its amortization depresses EBIT, so reported ROIC (7.8%, **below** the 9.6%
WACC → looks value-destroying) understates the real operating business (10.1%, **above**
WACC → value-creating).

But the adjustment never fires for VST. Its gate requires
`goodwill_intangible_share >= GOODWILL_SHARE_FLOOR (0.30)`; VST is at **0.23**, just under.
The 0.30 floor was a deliberately conservative, hand-picked cutoff set when the adjustment
was built for AMD (whose goodwill share is 0.63) — chosen to be safe, not derived. It is
too blunt for a genuine but more moderate acquirer like VST.

### Why the floor can't simply be lowered to a flat 0.15

A lower flat floor would start rescuing names on goodwill share alone, weakening the
guard against genuine value-destroyers. What actually separates VST from a value-destroyer
is not its goodwill *size* but a stronger economic signal: on a **tangible-capital basis
its ROIC clears its cost of capital** (the "WACC crossover"), even though reported ROIC
does not. That crossover is direct evidence the reported weakness is an accounting
artifact — so where it is present, a smaller goodwill share is sufficient proof.

### Why keying purely on the crossover would regress AMD

The obvious idea — "fire whenever ex-goodwill ROIC clears WACC" — cannot be the *sole*
gate. **AMD's ex-goodwill ROIC (13.8%) is still below its beta-capped WACC (14.5%)**, so
AMD has no crossover. AMD must keep qualifying via the existing high-goodwill path. The
crossover is therefore used to *lower* the floor, layered on the existing gate — never to
replace it.

## Approach (chosen)

**Option A — Two-tier dynamic floor keyed to the WACC crossover.** The goodwill-share
floor becomes a function of one related metric: whether the ex-goodwill ROIC clears WACC.

```python
GOODWILL_SHARE_FLOOR = 0.30       # existing, unchanged (AMD path)
GOODWILL_SHARE_FLOOR_XOVER = 0.15 # new: applies when the WACC crossover holds

def _wacc_crossover(m) -> bool:
    """Tangible (ex-goodwill) ROIC clears the cost of capital while reported ROIC
    sits below it — direct evidence the reported ROIC weakness is an acquisition
    artifact, not a weak business."""
    if m.roic_ttm is None or m.roic_ex_goodwill is None or m.wacc is None:
        return False
    return m.roic_ttm < m.wacc <= m.roic_ex_goodwill

def _effective_goodwill_floor(m) -> float:
    return GOODWILL_SHARE_FLOOR_XOVER if _wacc_crossover(m) else GOODWILL_SHARE_FLOOR
```

The only change to `_acquisition_distorted` is that the fixed `GOODWILL_SHARE_FLOOR`
comparison becomes the dynamic floor:

```python
def _acquisition_distorted(m) -> bool:
    if m.goodwill_intangible_share is None:
        return False
    if m.goodwill_intangible_share < _effective_goodwill_floor(m):   # was: < GOODWILL_SHARE_FLOOR
        return False
    if m.roic_ex_goodwill is None or m.roic_ttm is None:
        return False
    if m.roic_ex_goodwill <= m.roic_ttm:            # can only ever help, never hurt
        return False
    tpe, fpe = m.trailing_pe, m.forward_pe          # P/E-trough gate — unchanged
    if tpe is None or fpe is None or tpe <= 0 or fpe <= 0:
        return False
    return tpe / fpe > DEPRESSED_PE_RATIO
```

Every other gate condition (the `roic_ex_goodwill > roic_ttm` lift and the P/E-trough
`trailing/forward > 1.5`) is **retained and applies to both floor tiers** — the crossover
lowers the materiality bar, it does not remove the other evidence requirements. The
downstream substitution (Section II scoring ROIC / 5y-ROIC / spread on the ex-goodwill
basis) and the `roic_adjustment` breakdown are unchanged.

Note the crossover (`roic_ttm < wacc <= roic_ex_goodwill`) already implies the lift
condition (`roic_ex_goodwill > roic_ttm`), so on the low-floor path the lift check is
redundant but harmless.

### Rejected alternatives

- **Continuous sliding floor** (`floor = clamp(0.30 − k·max(0, exgw_spread), 0.15, 0.30)`).
  More literally "dynamic" but needs an arbitrary slope constant `k`, and VST's spread
  clears WACC by only +0.5pp — a sensible `k` leaves the floor at ~0.285, *above* VST's
  0.23, so VST is not fixed unless `k` is cranked arbitrarily high. More complex and fails
  the goal.
- **Two-tier with a 0.20 low floor** instead of 0.15. Behaves identically to 0.15 on every
  name examined (VST is 0.23). Marginally more conservative for hypothetical future names
  in the 0.15–0.20 band; the crossover is the real gate, so the extra caution buys little.

## Behavior preserved (verified against a 12-name basket)

Only **VST newly fires**. All others are unchanged:

| Company | goodwill share | ex-gw clears WACC? | Fires (before → after) |
|---|---|---|---|
| **VST** | 0.23 | yes (10.1 ≥ 9.6, rep 7.8) | **no → yes** (the fix) |
| AMD | 0.63 | no (13.8 < 14.5) | yes → yes (high-floor path, unchanged) |
| AVGO, CRM, ETN, ORCL, CSCO | ≥ 0.30 | no | yes → yes (unchanged) |
| MSFT, GOOGL, META | < 0.30 | no | no → no |
| NVDA | 0.15 | no (rep ROIC already ≫ WACC) | no → no |
| **INTC** | 0.17 | no (ex-gw ROIC 1.6 ≪ WACC 13.6) | **no → no** — genuine value-destroyer, correctly left unrescued |

INTC is the key negative control: goodwill share (0.17) would clear the lowered 0.15
floor, but no crossover (its tangible business earns far below its cost of capital) and no
P/E-trough, so it is correctly *not* rescued.

## Expected outcome for VST

Section II: 3.5 → **6.17** (ROIC 6.5, ROIC-5y 6.5, spread 5.5, ROTE null/excluded).
Quality Score: **5.0 → 5.7** — honest, not inflated. VST's tangible ROIC (~10%) only
modestly clears its cost of capital, and Section III (balance sheet, 3.0) correctly still
reflects genuine merchant-IPP leverage. The fix removes the acquisition-accounting drag on
returns without pretending the balance sheet is stronger than it is.

No other discussed name moves (AMD 7.2, MNDY 6.1, FIG 5.3, SOFI 5.4, NBIS 6.2 all
unchanged). The Fair-Value engine is untouched — this is a Quality-Score-only change.

## Testing

- `_wacc_crossover`: true for a VST-like name (reported ROIC below WACC, ex-goodwill ROIC
  at/above WACC); false when reported ROIC already clears WACC, and false when ex-goodwill
  ROIC is still below WACC (AMD-like).
- Dynamic floor: a name with goodwill share in [0.15, 0.30) **with** a crossover fires;
  the **same** name without a crossover does **not** (regression guard for the 0.30 bar).
- No AMD regression: an AMD-like name (goodwill 0.63, no crossover) still fires via the
  high floor.
- INTC-like negative control: goodwill share in [0.15, 0.30), ex-goodwill ROIC below WACC,
  no P/E-trough → does not fire.
- End-to-end VST: Quality ≈ 5.7, `roic_adjustment` recorded, Section II scored on the
  ex-goodwill basis.

## Non-goals

- No change to the Fair-Value engine.
- No change to the `GOODWILL_SHARE_FLOOR` (0.30) high-tier constant, the beta cap, the P/E
  gate, ROTE, the balance-sheet (Section III) handling, or any other section/adjustment.
- No change to the frontend — the existing `roic_adjustment` breakdown and
  `AdjustmentCard` already render this case; VST simply now populates it.
- The floors (0.30 / 0.15) remain fixed constants, not configurable.
