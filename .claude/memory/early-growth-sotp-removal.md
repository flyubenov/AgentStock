---
name: early-growth-sotp-removal
description: SOTP removed from EARLY_GROWTH tier — it was an EV/EBITDA leg the tier already bans; degenerate below-book value for CRWD
metadata: 
  node_type: memory
  type: project
  originSessionId: aaed5efa-0ffb-43c8-a1a6-751cfac3da1d
  modified: 2026-07-22T10:41:43.242Z
---

DONE (not yet committed as of 2026-07-22; on master — branch before committing). CRWD's FV was dragged by a degenerate SOTP leg ($3.69, *below* its own $4.55 book value, at 0.25 weight → composite $34.22 pulled down to $26.59).

**Root cause:** `calc_sotp` (`models.py:562`) is a misnomer — it is NOT a real sum-of-the-parts. It computes whole-company `EBITDA × min(ev_ebitda, EV_EBITDA_CAP=20) − net_debt, /shares × 0.85 × MOS` — i.e. EV/EBITDA-with-a-15%-discount, on ONE blended multiple, no segments, using the STALE flat 20× cap (not the dynamic `_ev_ebitda_ceiling` the real EV/EBITDA leg got in the ANET work). EARLY_GROWTH deliberately zeroes `ev_ebitda` (near-zero/SBC-depressed EBITDA) yet re-admitted the same basis via `sotp` 0.25. The old guard only dropped SOTP on `ebitda <= 0`; a barely-positive SBC-crushed EBITDA (CRWD $59M, 1.2% margin) slipped through.

**Fix:** `classifier.py` EARLY_GROWTH `sotp 0.25 → 0.00`, redistributed to `dcf 0.4667 / ev_sales 0.5333` (preserving the original 0.35:0.40 ratio; engine renormalizes anyway). Chose tier-removal over a margin-floor guard (the other option — reuse `EBITDA_MARGIN_FLOOR=0.08`, would have kept CRWV byte-identical) because SOTP conceptually doesn't belong in a tier that bans EV/EBITDA.

**Blast radius = exactly 2 names** (swept NET/CRWD/TEM/NBIS/ASTS/CRWV/IREN live):
- **CRWD** $26.59 → **$34.22** (fixed; still +459% overvalued — CrowdStrike is genuinely stratospheric, unchanged verdict).
- **CRWV** (canary, [[crwv-funding-gap-bridge]] / [[scenario-growth-band]]) $62.07 → **$71.38**. dcf is zeroed for the burner, so CRWV now values on **ev_sales ALONE**. Verdict **stays SELL** (+11% live vs price $79.58) but on a thinner margin — the funding-gap cushion shrank (at the test's synthetic $73.21 it's only +2.6%). Watch CRWV on any future EARLY_GROWTH/bull-path change.
- Pre-profit names (NET/TEM/NBIS/ASTS) unaffected — negative EBITDA → SOTP already dropped by the non-positive guard. IREN reclassified to MID_CAP (no SOTP in that tier).

340 tests pass. New test `test_early_growth_weights_no_sotp`; CRWV canary test updated (fv 62.07→71.38, `sotp not in breakdown`). SOTP still weights CONGLOMERATE 0.40 — untouched here, see [[conglomerate-valuation-gaps]].
