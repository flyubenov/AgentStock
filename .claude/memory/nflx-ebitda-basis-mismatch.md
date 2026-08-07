---
name: nflx-ebitda-basis-mismatch
description: NFLX FV came out ~half (55.84) because the historical EV/EBITDA multiple and its projection base used two different EBITDA definitions
metadata: 
  node_type: memory
  type: project
  originSessionId: d082b724-6bcc-49a8-a23d-9d944039c12f
---

NFLX Fair Value computed to $55.84 (≈−24% vs price) because the forward-tier EV/EBITDA leg mixed two EBITDA definitions. The historical-median multiple (~10.2×) is reconstructed in `fetch_ev_ebitda_history` from the income-statement `EBITDA` row (~$30B, which adds back content amortization), but it was applied to a projection base of `ebitda_ttm` = yfinance `info['ebitda']` (~$14B, narrower). The two differ ~2×, so the narrow base × broad-basis multiple halved the leg ($43.66 vs the DCF's ~$62–69).

**Fix (branch screener-fixes):** `fetch_ev_ebitda_history` now returns `{"multiple", "ebitda"}` (both statement-basis); engine stores `ev_ebitda_hist_base`; `calc_ev_ebitda(..., hist_ebitda_base=)` projects that statement EBITDA whenever a `hist_multiple` is anchored. NFLX → $67.68 (−7.76%), EV/EBITDA leg $80.71, consistent with DCF.

**Why:** anchoring a normalized multiple only works if the multiple and the base it's applied to are the same EBITDA definition. Bites content/media names and any large-amortization business.

Not a split bug — NFLX's 10:1 (2025-11-17) is handled correctly; both prices and statement shares are consistently split-adjusted, so `statements_predate_split` correctly does not fire. Related: [[klac-growth-undervaluation]], [[size-coupled-growth-fade]].
