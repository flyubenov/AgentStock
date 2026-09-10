---
name: cf-cyclical-peak-dcf-overvaluation
description: "WATCH/OPEN — CF (CYCLICAL) FV $264 = 2x price; DCF/EV compound a cyclical-PEAK base at peak growth, no mean-reversion. Brainstorm pending."
metadata: 
  node_type: memory
  type: project
  originSessionId: 1a28f24e-ac84-40ac-bd94-212cae977174
  modified: 2026-08-31T21:05:30.954Z
---

CF Industries (nitrogen fertilizer, `CYCLICAL`, Basic Materials) validated 2026-08-31 — user flagged FV "twice current price." **Confirmed overstated, but DELIBERATELY NOT FIXED — user's call (2026-08-31): leave it, watch for recurrence, and revisit the fix only when another company hits the same cyclical-peak trap.** Treat this as a CLASS of bug, not a one-ticker fix.

**Recurrence signature — how to recognize the next case:** a `CYCLICAL` name (Energy / Basic Materials, or the low-P/E + low-growth classifier trigger) whose FV runs far above both price AND analyst target, where **`forward_pe > trailing_pe`** (forward EPS < trailing EPS → earnings expected to FALL) yet the DCF/EV legs still project the trailing FCF/EBITDA peak forward at a positive trailing growth rate. When another ticker shows this, come back here — the diagnosis and levers below already apply; then loop the user in on the fix.

**The gap (a real logic gap, not a defensible-expensive verdict):** live FV **$264.51 vs price $125.79 (+110%)**. Reconciles: 0.40·dcf$461.81 + 0.20·evE$222.54 + 0.25·pe$119.50 + 0.15·nav$36.02. The two projection legs (DCF 40% + EV/EBITDA 20% = 60% weight) **compound a cycle-PEAK base at a cycle-PEAK growth rate with NO mean-reversion**: DCF grows peak FCF $1.8B at 17.6% for 5y; EV/EBITDA grows peak EBITDA $3.87B at 17.6%.
- 17.6% realistic growth = revenue_growth; the `earnings_outpaces_revenue` guard fired (earnings +99.6% vs rev +17.6%, a cyclical recovery yr) and correctly re-sourced from revenue — but 17.6% is ITSELF a peak reading.
- Contradiction the model ignores: **forward EPS $10.46 < trailing $13.48 = 22% expected earnings DECLINE**. Market prices CF at 9.3x trailing (looks "cheap") *because* earnings are peaking; DCF reads cheap+growing and doubles it.
- Corroboration all ≈ price: analyst mean target **$125.77** (19 analysts) ≈ price; R-R `analyst_upside`≈0; R-R tier "Asymmetric Upside" 2.36 leans on same peak illusion (PEG 0.42→5.0).
- Sane anchors (P/E $119.50 ≈ price; NAV $36) only 40% weight.

**Growth-sensitivity probe (peak base held, realistic growth swapped, read-only monkeypatch of `build_scenarios`):** 17.6%→$264 · 5%→$143 · 2%(flat/mean-reverted)→$125 · −5%→$93. FV collapses onto the P/E leg / analyst target the moment peak growth stops. **Defensible range ~$120–150, not $264.**

**FULL 136-TICKER LIVE SWEEP (2026-09-01) — confirmed blast radius is TINY:** only **3 names classify CYCLICAL** in the whole universe: **CF** (+104%, tPE 9.6<fPE 12.5, f/t 1.30 → OVERSTATED, the bug), **HON** (−17%, tPE 8.2<fPE 21.3, f/t 2.60 → peak-flagged but NOT overstated = the **canary a fix must not push lower**; its low trailing P/E looks one-off-inflated, not a commodity peak), **CCJ** (−81%, tPE 170>fPE 53, f/t 0.31 → trough, signature correctly skips it). So today CF is the SOLE live casualty. Note: the signal `forward_pe>trailing_pe` fires on HON too → **necessary but NOT sufficient**; the fix's ACTION (and/or extra corroboration) must leave HON alone — the #1 open design problem. (ZETA errored in sweep = trailing_pe Infinity + a separate pre-existing str/int bug in its QUALITY pipeline; it's EARLY_GROWTH/Technology, not cyclical.)

**Root cause:** NO mid-cycle normalization for `CYCLICAL` anywhere — the tier (`classifier.py:55`, `CYCLICAL_SECTORS={Energy,Basic Materials}` line 3, trigger line 122) only sets method weights. `_normalized_forward_eps` (`models.py:535`) handles the OPPOSITE case (depressed trailing EPS, only-help) — nothing catches a peak.

**Levers (worked):**
1. **RECOMMENDED — normalize base/growth at cyclical peaks.** Mirror the *detection* shape of `_normalized_forward_eps`: when `forward_pe > trailing_pe` (earnings expected to fall; CF 12.02>9.33) treat trailing FCF/EBITDA as a peak and cap DCF/EV realistic growth to mean-reversion (or rebase to forward-implied). 17.6%→~2% gives **$264→$125**. Broad cross-classification blast radius: ALL Energy + Basic Materials names + low-P/E-triggered CYCLICALs — MUST sweep first.
2. Reweight CYCLICAL off projection legs (dcf .40→.20, pe .25→.45, nav .15→.20) → **$264→$187**. Only dilutes; doesn't fix mechanism. Not recommended alone.

**WHEN IT RECURS (the fix path, deferred until then):** open `superpowers:brainstorming` (design fork: cap-growth vs rebase-base vs forward-EPS anchor; which peak signal to trigger on) + read-only sweep of Energy/Basic-Materials universe before any TDD. Reuse-before-invent: start from `_normalized_forward_eps` detection shape. Regression canaries: IREN/NBIS/KLAC + any Energy/Materials names in tests. Related: [[app-serves-persisted-rows-not-live-compute]].
