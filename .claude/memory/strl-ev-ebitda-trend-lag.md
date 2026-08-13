---
name: strl-ev-ebitda-trend-lag
description: Forward-tier EV/EBITDA anchor used a flat historical median, which lags a persistent multi-year re-rating (STRL) or de-rating (CRM, NVDA) trend; replaced with a recency-weighted (EWMA) representative multiple
metadata:
  node_type: memory
  type: project
---

Validating STRL (Sterling Infrastructure, data-center/E-Infrastructure construction,
`GROWTH` tier) against the user's "isn't its FV too low?" question found FV $333.80/−39.19%
was pulled almost entirely by one outlier leg: DCF $415.39 and P/E $494.05 both read STRL
as only modestly rich, but **EV/EBITDA read $172.08** — a huge outlier.

**Root cause: `FORWARD_TIERS` (MEGA_CAP/LARGE_CAP/MID_CAP/GROWTH) anchor the EV/EBITDA leg
to a historical-median multiple (`services.yahoo.ev_ebitda_history_median`, now
`_ewma`) reconstructed from ~4-6 statement years.** STRL's own year-by-year multiple:
2022 5.24x -> 2023 6.23x -> 2024 8.15x -> 2025 14.54x (spot: 23.4x) — a **strict, 4-year
monotonic re-rating**, not a noisy/mean-reverting range. `statistics.median()` of that
series is `(6.23+8.15)/2 = 7.19x`, which sits near the OLDEST two years and understates
what STRL's *current* growth regime (revenue +90% YoY, quarterly revenue $614M->$1,168M)
commands. A flat median is the wrong central-tendency statistic for a trending series.

**Live-measured, not estimated:** disabling the hist anchor entirely (forcing the leg onto
the current 23.4x spot multiple) flipped composite STRL from -39.19% to **+25.31%** —
confirming the anchor mechanism was the whole swing between "deeply overvalued" and
"roughly fair" (this crude probe conflated the multiple-choice with a separate
growth-rate-sourcing gate, so the swing shape isn't a candidate design's actual effect
-- see the clean sweep below for the isolated numbers).

**This is a symmetric, two-sided problem, not an STRL-only quirk.** The same reconstruction
for **CRM**: 36.9x -> 27.4x -> 23.0x -> 14.8x (monotonically DECREASING) — median 25.2x
OVERSTATES the current level, the mirror image of STRL's understatement. **NVDA**: 158x ->
76x -> 44x -> 33x, same shape. Confirms the mechanism is a genuine statistical gap, not
deliberate calibration (no ticker-tagged comment defends this failure mode).

**Design brainstorm (run directly against live data instead of `superpowers:brainstorming`,
which isn't mounted in this checkout) swept 4 candidate replacements for the flat median
across 49 live `FORWARD_TIERS` names** (built `fin` exactly as `engine.run` does, called
the pure `evaluate()` with only `ev_ebitda_hist` swapped per variant — no engine changes,
no mocking, isolates exactly the multiple-selection question):

| Design | STRL swing | Other-48 mean\|swing\| | Other-48 median\|swing\| | Names >15pp elsewhere |
|---|---|---|---|---|
| skip (monotonic -> fall back to spot) | +36.4pp | 3.4pp | 0.0pp | WMT -27.1, CRM -26.3, NVDA -23.1 |
| recent_avg (avg of last 1-2 yrs) | +7.2pp | 3.6pp | 0.9pp | IREN +19.6, CRM -16.7, ORCL +16.1 |
| blend (50/50 median+latest) | +6.3pp | 2.8pp | 0.9pp | ADBE -17.5 (only one) |
| **ewma (exponential recency-weight, decay=0.5)** | +6.8pp | **2.7pp** | 1.0pp | ADBE -16.6 (only one) |

`skip` gives STRL the biggest correction but is a blunt binary: falling back to the spot
multiple re-engages FCF-conversion **compression** for non-GROWTH tiers (a separate
mechanism), producing unpredictable-direction swings on unrelated monotonic names (WMT is
ALSO a genuine multi-year re-rater, non-AI-related, yet `skip` swings it -27.1pp).
`recent_avg`'s hard 2-year window is noisier (window-edge-sensitive: ORCL's swing is an
artifact of which 2 years land in the cutoff). `blend`/`ewma` are smooth, continuous, and
nearly tied; `ewma` edges out `blend` on principle (a natural decay generalizes to however
many years exist — 3 for IREN, 4 for STRL/CRM/NVDA — without an arbitrary "last 2 years" or
"50/50" split) and had the lowest mean blast radius. ADBE (both designs' only >15pp name)
is itself a directionally-correct move: its own multiple climbed 26.2x->29.1x then FELL to
16.4x in the latest year (real AI-disruption de-rating), so pulling its FV down too is the
mechanism working, not a regression.

**Shipped: `ev_ebitda_history_ewma`** (`services/yahoo.py`, replaces
`ev_ebitda_history_median`) — exponentially recency-weighted average, `decay=0.5`
(half-life 1 year: rows are most-recent-first, weight `decay**i` for i=0..n-1). A flat
(non-trending) series still resolves to that same constant (invariant, tested). New
constant `EV_EBITDA_HISTORY_DECAY = 0.5`; `EV_EBITDA_HISTORY_MIN_YEARS` unchanged. Sole
call site (`_fetch_ev_ebitda_history_sync`) updated; no other caller existed.

**Live result:** STRL EV/EBITDA leg $172.08 -> $265.09, composite **$333.80/-39.19% ->
$371.00/-32.42%**. Quality 9.1 untouched (FV-only, no shared code). Live-verified via
`valuation.engine.run` (not the sweep probe) matches the sweep's ewma prediction exactly:
STRL -32.42, PWR -31.04, CRM +40.81 (corrected DOWN from a +54.26 baseline -- the
stale-high-median overstatement, same mechanism as STRL's understatement but mirrored),
ADBE +75.59 (down from +92.16), WMT -26.37, NVDA -14.26 (unchanged, ewma barely differs
from median for NVDA), KLAC/PLTR/NBIS/IREN/AAPL/KO/MU/ANET all consistent with the sweep.

**Tests:** `test_data_guards.py` — replaced the 3 old median-specific tests with 5 new
ones (STRL-shaped re-rating pulls above median; CRM-shaped de-rating pulls below median,
proving the two-sided correction; a flat/non-trending series is invariant under EWMA;
skip-nonpositive-EBITDA and too-few-years preserved). 483 backend tests pass (was 481).

Related: this closes the specific gap surfaced while validating STRL; no prior memory
entry existed for STRL. See the ANET fix (`anet-ev-ebitda-cap-growth.md`) for a
structurally different but adjacent gap in the same leg (a flat CEILING clipping a valid
high historical median — already fixed; this entry is about the MEDIAN STATISTIC ITSELF
lagging a trend, not the ceiling that caps it afterward).
