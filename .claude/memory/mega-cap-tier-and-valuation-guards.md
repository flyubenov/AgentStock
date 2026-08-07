---
name: mega-cap-tier-and-valuation-guards
description: "DONE + MERGED to master (no-ff 78d74c1): MEGA_CAP tier for >$1T names + two valuation guards (sotp non-positive EBITDA, negative-composite clamp); 241 tests pass"
metadata:
  node_type: memory
  type: project
  originSessionId: f864a523-1eae-4d6e-a999-72b060eec317
---

Three-part "Path 1" change, all TDD, MERGED to master @78d74c1 (no-ff), 241 tests pass.

**1. MEGA_CAP stock type (>$1T).** New tier splitting the old LARGE_CAP size default:
`_detect_type` rule 8 now returns MEGA_CAP for market_cap > $1T, LARGE_CAP for
$100B-$1T. Weights `dcf .55 / ev_ebitda .35 / pe .10` (vs LARGE `.50/.35/.15`) — leans
marginally more on DCF, trims P/E; **no standalone ev_sales** (see below why that was
the whole point). Added to `engine.FORWARD_TIERS` so mega-caps keep historical-median
EV/EBITDA + forward P/E. The >$1T line already existed in the math (`models.MEGA_CAP_FLOOR`,
FADE_HOLD_MEGA=0 fades from year 1 — see [[size-coupled-growth-fade]]); this just gives it
an honest label. Live sweep: only 7 >$1T names move (AVGO -4.5% — its forward-P/E leg
loses weight to DCF; AAPL -2.6%, MSFT -1.4%, NVDA -0.7%; AMZN unchanged, capex-rerouted);
**all 45 sub-$1T names exactly unchanged**.

**2. calc_sotp guard (models.py).** SOTP is EV/EBITDA-based (`ebitda * ev_ebitda`); only
null-guarded `is None`. Negative EBITDA either reconstructs ~0.85x current EV via a
double-negative (circular, defeats EV_EBITDA_CAP) or drags composite negative. Now nulls
on `ebitda <= 0 or multiple <= 0`.

**3. Negative-FV clamp (engine.py evaluate).** A moderate cash-burner (FCF/rev above the
-25% FCF_MARGIN_FLOOR, so pre-profit guard doesn't fire) could drive the weighted composite
<= 0 and surface it as `status: completed`. Now declines (failed, FV None) when composite
<= 0. **Verified live: INTC flipped from completed -$2.59 -> failed/no-FV.**

**KEY MECHANIC discovered (why the original ev_sales-ladder idea was abandoned):**
`engine.pick_ev_multiple` is a WINNER-TAKE-ALL selector, not an additive blend — when a
bucket weights BOTH ev_ebitda and ev_sales, it keeps ONE and folds the loser in:
ebitda<=0 or EBITDA-margin<8% -> use ev_sales; else -> use ev_ebitda. So for healthy-margin
names an ev_sales weight just folds back into ev_ebitda (a no-op), and for low-margin names
(WMT ~6%) it FLIPS the EV basis EBITDA->Sales (+52% FV in a sweep — bad). A blended
revenue+EBITDA leg for large/mega caps would require changing pick_ev_multiple (was called
"Path 2", NOT done). Also: V/MA/NVDA etc. are healthy-margin so they use EV/EBITDA regardless
of bucket — they never needed an ev_sales leg.

**Classification-rule discussion (context, no code):** user noted only >$1T reaches the
LARGE_CAP default. Data disproved the strong claim (12 sub-$1T names ARE LARGE_CAP). Real
edge: the GROWTH `dividend_yield < 0.01` gate dumps fast growers with a 1-2% yield (ORCL 21%,
TXN 19%, CRM, CSCO) into LARGE_CAP ("dividend dead zone" 1%-2.5%). A candidate fix (widen
GROWTH yield gate to <0.025) was discussed but NOT implemented — deferred.

Related: [[size-coupled-growth-fade]], [[payment-network-misclassification]],
[[revenue-coupled-growth-cap]], [[iren-opmargin-capex-reroute]] (capex reroute = why AMZN unmoved).
