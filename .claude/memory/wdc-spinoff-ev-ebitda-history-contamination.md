---
name: wdc-spinoff-ev-ebitda-history-contamination
description: "WATCH/OPEN (not fixed) — CLASS of bug: ev_ebitda_history has no spinoff/divestiture guard (only a split guard). WDC FV +44% fake, driven by corrupt EV/EBITDA leg. Revisit if another post-spinoff/cyclical name recurs."
metadata: 
  node_type: memory
  type: project
  originSessionId: 1a28f24e-ac84-40ac-bd94-212cae977174
  modified: 2026-08-31T21:46:37.817Z
---

WDC (Western Digital, `GROWTH`, Technology/Computer Hardware) validated 2026-09-01 — user flagged FV, focus Moat+FV. **Confirmed FV is NOT trustworthy; DELIBERATELY NOT FIXED — save as watch/open item, revisit when another post-spinoff or deep-cyclical name hits the same EV/EBITDA-history contamination.** Treat as a CLASS of bug (structural, broad blast radius), not a one-ticker patch.

**FV: $650.41 vs price $450.55 (+44%) — fake discount.** Reconciles 0.4·dcf$296.39 + 0.4·evE$1148.18 + 0.2·pe$362.91. Legs are internally INCOHERENT (4x spread): DCF $296 and P/E $363 both sit BELOW price; only the corrupt **EV/EBITDA leg ($1148, realistic $1060.81) drags composite to $650**. A fair value that averages a reasonable leg with a 4x-outlier is not a defensible center.

**The EV/EBITDA leg is broken on TWO counts (WDC is a forward tier → anchors to hist median, uncompressed):**
1. **Spinoff-contaminated base:** projects from `hist_ebitda_base` **$10.445B**, NOT current TTM EBITDA **$5.0B** (~2x too big, implied margin >50% = impossible for hardware). WDC **spun off SanDisk Feb 2025**; latest FY statements still carry the divested NAND business + one-time spinoff gains (also shows up as ROE 131%, net/profit margin 73%, earnings_growth 984% — all one-off-inflated).
2. **Cyclical-trough multiple:** the **28.76x** anchor (6y EWMA of annual EV/EBITDA, `ev_ebitda_history_ewma`) averages in memory-downturn years where EBITDA collapsed and EV/EBITDA spiked to 30–100x. Storage normally 5–8x. (Ceiling capped it only at 30x.)

**ROOT CAUSE (real logic gap):** `_fetch_ev_ebitda_history_sync` (`services/yahoo.py:264`) has a SPLIT guard (`statements_predate_split`, line 283) but **NO spinoff/divestiture guard**. A mid-history spinoff contaminates BOTH `latest_statement_ebitda(rows)` (the base) AND the EWMA multiple (historical EVs include the divested unit + disposal gains). Same class as the split guard, uncovered. Related basis-mismatch precedents: [[nflx-ebitda-basis-mismatch]] (statement-consistent base), [[strl-ev-ebitda-trend-lag]] (EWMA design), split-aware history (KLAC).

**Worked corrections (read-only probes, monkeypatch calc_ev_ebitda):** baseline FV $650 → fix base to TTM $5.0B (keep 28.76x) **$411** → drop evE leg **$319** → base TTM + sane 7x **$245**. **Defensible model range ~$245–410; WDC reads fair-to-overvalued at $450, NOT +44% undervalued.**

**Recurrence signature — how to recognize the next case:** a name whose EV/EBITDA leg is a large multiple of its DCF/P/E legs (internal incoherence), where `hist_ebitda_base` implies an impossible margin (≫ the sector norm) or is ~2x current TTM EBITDA — typically after a **spinoff/divestiture** or in a **deep cyclical** (memory/storage/semis) whose historical EV/EBITDA is trough-spiked.

**WHINKLE (don't over-claim "model too high"):** analyst mean target **$664.92** (24 analysts, high $1050) — street is bullish on an AI-storage supercycle, so broken $650 lands near consensus by COINCIDENCE. Not validation; DCF says $296, legs disagree 4x. If the supercycle thesis is real, rebuild the bull case on a defensible FORWARD-EBITDA basis, not the corrupt historical one.

**MOAT: 59.2 (ROIC variant, not gated) — right shape, modestly generous, far less broken than FV.** A1 20/20, A2 20/20 (magnitude MAXED, Section II quality 10.0 — riding the same spinoff/cycle-inflated ROE 131%/margins), B1 6.25/25 + B2 0/10 (durability WEAK — correctly captures no through-cycle durable economic profit), B3 5/15, C1 8/10. The correctly-low durability pillars restrain a spuriously-maxed magnitude → 59 lands in a defensible "narrow/moderate moat" band (HDD duopoly gives some moat). Normalized-earnings magnitude would score lower (~mid-40s–low-50s). Leave it, with caveat. NOT a bug the way the FV leg is.

**WHEN IT RECURS (fix path, deferred):** open `superpowers:brainstorming` — options: (a) spinoff/corporate-action guard in `ev_ebitda_history` (HARD: no clean spinoff-date feed from yfinance like `tk.splits`), (b) margin-sanity guard rejecting a `hist_ebitda_base` whose implied EBITDA/revenue is impossible (>~50%) — reuse-before-invent candidate, mirrors basis-consistency intent, (c) cyclical-multiple handling. Broad blast radius: every ticker's `ev_ebitda_history` → sweep STRL/NFLX/KLAC neighbors + canaries IREN/NBIS/KLAC before TDD. Related: [[app-serves-persisted-rows-not-live-compute]], [[cf-cyclical-peak-dcf-overvaluation]] (sibling cyclical-mishandling class).
