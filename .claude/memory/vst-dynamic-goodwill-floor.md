---
name: vst-dynamic-goodwill-floor
description: VST scored 5.0 — the acquisition-ROIC adjustment missed it at 23% goodwill (flat 0.30 floor); fixed with a dynamic floor keyed to the WACC crossover
metadata: 
  node_type: memory
  type: project
  originSessionId: ea25e0a9-65a1-45de-bc36-6155c47ebbed
---

VST (Vistra) screener Quality Score was **5.0**, dragged by Section II (Returns on Capital
3.5): reported ROIC 7.8% sits **below** its 9.6% WACC (looks value-destroying), but its
Energy Harbor/Dynegy acquisition goodwill inflates invested capital — strip it and the
tangible ROIC is 10.1%, **above** WACC. Same distortion as [[amd-acquisition-roic-distortion]],
but the `_acquisition_distorted` gate never fired: goodwill was **23% of invested capital**,
just under the flat `GOODWILL_SHARE_FLOOR = 0.30` (a hand-picked conservative cutoff from
the AMD fix, where goodwill was 63%).

Fix (2026-07-12, merged to master, FF `ed3360a..c6d120c`): the goodwill floor is now
**dynamic** in `screener/scoring.py`. Added `GOODWILL_SHARE_FLOOR_XOVER = 0.15`, applied
when the **WACC crossover** holds — `_wacc_crossover(m)`: `roic_ttm < wacc <= roic_ex_goodwill`
(reported ROIC below cost of capital, tangible ROIC at/above it). That crossover is itself
direct evidence the reported weakness is an acquisition artifact, so a smaller goodwill
share suffices. `_effective_goodwill_floor(m)` returns 0.15 on crossover else 0.30; it's the
only change inside `_acquisition_distorted` (lift check + P/E-trough gate retained on both
tiers). VST Section II 3.5→6.17, **score 5.0→5.7**.

**Key subtlety — why the crossover can't be the sole gate:** AMD's ex-goodwill ROIC (13.8%)
is still **below** its beta-capped WACC (14.5%), so AMD has *no* crossover — it must keep
qualifying via the unchanged 0.30 floor. The crossover only *lowers* the floor, never
replaces the gate. Verified across a 12-name basket: only VST newly fires; AMD/AVGO/CRM/ETN/
ORCL/CSCO unchanged (0.30 path), MSFT/NVDA/GOOGL/META untouched, and **INTC** (17% goodwill,
tangible ROIC 1.6% ≪ WACC 13.6%, no crossover) correctly stays unrescued — the negative
control proving it doesn't over-fire on genuine value-destroyers. Screener-only; FV untouched.
