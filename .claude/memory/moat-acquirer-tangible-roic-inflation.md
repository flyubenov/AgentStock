---
name: moat-acquirer-tangible-roic-inflation
description: "Moat score can over-reward serial acquirers whose tangible ROIC >> full-capital ROIC — PANW 78 case; watch for recurrence, not yet fixed."
metadata:
  node_type: memory
  type: project
  originSessionId: cd567975-3d92-49b9-95bc-462fcb83e2cb
  modified: 2026-08-25T09:53:17.854Z
---

**Known Moat calibration edge (NOT yet fixed — revisit if it recurs).** For a serial
acquirer whose earnings are amortization-depressed, the Moat score can land in the
"wide moat" band (≥70) even though its economic profit on **full** invested capital is
~zero. Validated on **PANW = 77.8** (2026-08-25); by-design behavior, not a bug.

**Mechanism.** `moat.scoring._return_axis` reuses `screener.scoring._acquisition_distorted`
(spec §4.2). That guard fires when goodwill_share ≥ floor AND roic_ex_goodwill > roic_ttm
AND **trailing_pe/forward_pe > DEPRESSED_PE_RATIO (1.5)** — i.e. recently/thinly profitable
acquirers. When it fires, the return axis switches to **TANGIBLE (ex-goodwill) ROIC**,
which does TWO things at once in Moat:
  1. Maxes the 40-pt magnitude block (A1 level + A2 spread) on tangible ROIC.
  2. Makes the **economic-profit gate** compare *tangible* ROIC to WACC — so the gate that
     would otherwise cap the name at MOAT_GATE_CEIL (35) never fires.

**PANW evidence (live recompute):** goodwill 0.681; tpe/fpe = 313/85 = 3.68 (>>1.5) →
`_acquisition_distorted=True` → TANGIBLE_ROIC. Full-capital roic_5y = **8.44%** vs
WACC 9.13% → **−0.7pp (below cost of capital; plain-ROIC gate WOULD fire → cap 35)**.
Tangible roic_5y = 35.3% (+26pp) → A1 20/A2 20 maxed. B2=0 correctly flags volatility
(ex-gw ROIC series swings +84%→−18%) but not enough to leave the ≥70 band. Pillars:
A1 20 / A2 20 / B1 18.75 / B2 0 / B3 9 / C1 10 = 77.8. Verdict then: defensible-but-generous;
a fair range is ~55–70. NOT changed (user validation only).

**Contrast — MCO (same session) is fine:** 74.5% goodwill but tpe/fpe = 1.18 (<1.5) →
guard does NOT fire → plain ROIC (19.8% vs 10.7% WACC, +9pp) → 79.5 legitimately. So the
edge is specific to acquirers whose *earnings* (P/E) are depressed, not merely goodwill-heavy.

**Lever if it needs fixing (design fork — treat as a brainstorm, do NOT quick-edit).**
Make magnitude keep tangible ROIC but have the **gate test full-capital ROIC**
(`m.roic_5y_avg` vs `m.wacc`). Measured: PANW 77.8 → 35.0 — but a hard cap-to-35 is too
blunt (lumps PANW with value-destroyers); a graduated haircut when full-capital spread <0
would be fairer but is a new mechanism. **Broad blast radius:** the same TANGIBLE_ROIC
routing drives ADBE, CDNS, SNPS, AMD (all scored high via this axis in the calibration
sweep) — any gate change MUST be swept across them so a name with healthy full-capital
returns isn't slammed.

**Watchlist for recurrence:** any acquisition-heavy, recently-profitable name with a high
trailing/forward P/E ratio and a large gap between tangible and full-capital ROIC. If two
or three more surface, promote this from "watch" to a brainstormed fix.

Related: [[moat-score-design]] (the feature), [[snps-dominant-acquisition-normalization]] +
[[amd-acquisition-roic-distortion]] + [[vst-dynamic-goodwill-floor]] (the ex-goodwill /
tangible-capital lineage this reuses), [[app-serves-persisted-rows-not-live-compute]]
(why MCO showed blank — stale row, not a scoring failure).
