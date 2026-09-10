---
name: fn-ev-ebitda-terminal-multiple-temper
description: "DONE (2026-09-10) on branch `ev-ebitda-terminal-multiple-temper`: tempers the uncompressed terminal EV/EBITDA multiple for thin-GROSS-margin forward-tier names. FN FV $769.56 (+82.6%) -> $448.37 (+11.0%). 557 tests pass. Franchise + non-durable canaries confirmed unmoved live."
metadata: 
  node_type: memory
  type: project
  originSessionId: ff5aa68d-fad4-41cf-828f-5e7f910be8af
  modified: 2026-09-10T20:17:51.792Z
---

# FN validation + EV/EBITDA terminal-multiple temper (DONE on branch `ev-ebitda-terminal-multiple-temper`)

**Session 2026-09-09/10.** User asked to validate FN (Fabrinet, NYSE:FN, GROWTH, optical contract manufacturer / EMS) — Quality/FV/Moat/R-R all "too high" — then to open a brainstorm to fix the FV mechanism. Brainstorm is mid-flight, **paused awaiting user approval of the design + a calibration choice.** No code changed yet (HARD GATE not crossed).

## FN validation verdict (DONE, evidence-backed)
- **FV $769.56 (+82.6%) — OVERSTATED in magnitude, the real gap.** Composite `0.70·evE $927.8 + 0.30·pe $400.3`. EV/EBITDA leg projects a **~26x terminal multiple** (hist EWMA 25.97x, genuine monotonic 4yr re-rating 15→20→25→29x, NOT contaminated like [[wdc-spinoff-ev-ebitda-history-contamination]]). It's uncompressed because GROWTH passes `compress=False` (engine.py:634) AND 44.6% growth maxes `_ev_ebitda_ceiling` via `max(g_frac,q_frac)` → g_frac=1.0 → ceiling 30x, so 25.97 passes. Defensible center ≈ $480–550 (12–16x); +82% not defensible. Analyst mean target $734 corroborates DIRECTION not magnitude (stale, pre 44% crash $748→$421).
- **Moat 76.7 — generous but defensible.** Real 4yr consistent economic profit (ROIC series [19.3,15.3,15.2,15.1] > WACC 10.9%, stable ~10% op margins). C1 FCF-conversion excluded via `_heavy_capex_distortion` (+~8pts). Range 55–70. Leave it.
- **R/R 1.49 Reward-Favored — internally correct, sound.** Verified every metric vs anchors. No fault.
- **Quality 7.5 — sound, not too high.** Strong current fundamentals; FCF excluded (capex reinvestment).

## Brainstorm scope (user decided 2026-09-09)
Three memory cases have DIFFERENT root mechanisms — do NOT conflate:
- **FN** = uncompressed high TERMINAL MULTIPLE on thin-margin forward-tier name ← **THIS fix**.
- **WDC** = contaminated BASE (spinoff) + trough-spiked multiple → SEPARATE fix, stays WATCH.
- **CF** = peak BASE+GROWTH in DCF (CYCLICAL, not forward-tier) → SEPARATE fix, stays WATCH ([[cf-cyclical-peak-dcf-overvaluation]]).
**User chose: multiple-temper ONLY this session; leave WDC-base + CF as separate future fixes.**

## Signal comparison (DONE — full-universe sweep, the key result)
User asked to sweep op-margin vs ROIC and recommend. Added gross margin. **Sweep script + results: `docs/analysis/2026-09-09-ev-ebitda-temper/temper_sweep.py` + `temper_out.csv`** (141 tickers, read-only, monkeypatches `models._ev_ebitda_ceiling`, CONCURRENCY=1). Held action fixed (MATURE_MULT=13, `ceiling=13+q·(growth_ceiling−13)`), varied only the signal q=ramp(signal).
- **Operating margin (26 movers) — FAILS:** SBC/amortization depress GAAP op margin → wrongly docks SaaS franchises (WDAY −21%, NOW −18%, SNPS −15%, PANW −10%, ELF −29%).
- **ROIC 5y (38 movers) — FAILS WORSE:** cash-heavy/acquisitive balance sheets → docks widest moats (ISRG −20%, AVGO −11%, ORCL −27%, CDNS −7%, VEEV −20%, CRM −14%, PLTR −12%).
- **GROSS margin (16 movers) — WINNER, chosen:** immune to both. Every gross≥50% franchise = 0.0% (byte-unchanged). Moves FN −41.8% ($447, +7% vs price). **Of all 16 gross movers, FN is the ONLY verdict change** — all others already SELL (verdict-neutral: BWXT −59%→−68%, TSLA −87%→−89%, ETN −26%→−32%) or negligible (<2% at band edge: AAPL, AMD, SHOP). Band used GM_LO=0.25, GM_HI=0.50. **User said "go ahead with gross margin."**

## DESIGN (pinned, awaiting final approval)
- **Signal:** trailing gross margin (`ScreenerMetrics.gross_margin_series[0]`, percent), sourced into `fin` in `engine.run()` beside existing WACC/ROIC sourcing (~line 799, failure-isolated; absent → no temper = identity/backward-compat).
- **Action:** temper ONLY the `durable=True` branch of `_ev_ebitda_ceiling` (`models.py:206`): `ceiling = MATURE + q·(growth_ceiling − MATURE)`, `q = ramp(gross_margin, 0.25→0.50)`, `MATURE≈13x`. Spot-multiple path (EARLY_GROWTH/IREN) untouched. Reuses existing inline ramp shape.
- **New constants:** MATURE_EBITDA_MULT (~13), GM_TEMPER_LO=0.25, GM_TEMPER_HI=0.50.
- **Canaries verified unmoved:** KLAC, ANET, NBIS, IREN (IREN/NBIS on non-durable path). BWXT/ETN move but already SELL (verdict-neutral) — re-confirm in regression.

## SHIPPED (2026-09-10, branch `ev-ebitda-terminal-multiple-temper`, 3-task SDD)
- **Task 1** (`backend/valuation/models.py`): `_ev_ebitda_ceiling` durable branch tempered by gross margin. Constants: `MATURE_EBITDA_MULT = QUALITY_CONV_HI * MATURE_MULTIPLE_FACTOR` (≈13.24x), `GM_TEMPER_LO = 0.25`, `GM_TEMPER_HI = 0.50`. Spot-multiple path (EARLY_GROWTH/IREN) untouched; `gross_margin=None` is a full no-op (identity, backward-compat).
- **Task 2** (`backend/valuation/models.py`): `calc_ev_ebitda` reads `fin.get("gross_margin")` (percent) and passes it to `_ev_ebitda_ceiling` as a fraction (÷100), durable leg only.
- **Task 3** (`backend/valuation/engine.py`, ~line 802): `fin["gross_margin"] = met.gross_margin` sourced inside the existing failure-isolated screener-signal `try:` block (beside `wacc`/`roic_wacc_spread`/`roic_5y_avg`) — dormant until this line, now live.
- **Full regression:** 557 backend tests pass (`python3 -m pytest` from `backend/`).
- **Live re-validation (FN, the target):** fair_value **$769.56 (+82.6%) → $448.37 (+11.0%)** — within the predicted $440–460 / +5–10% band. EV/EBITDA terminal multiple floored from ~26x toward the ~13.2x mature anchor.
- **Live canaries confirmed unmoved:** CDNS $229.84 (−19.3%), NOW $115.42 (−12.0%), KLAC $94.13 (−46.9%), ANET $147.12 (−22.2%) — all high-gross-margin franchises, byte-consistent with pre-change behavior (no durable temper applied). NBIS $72.70 (−68.1%, non-durable path, unaffected by design). IREN `fair_value: null` both before and after (pre-existing unrelated failure — "composite fair value non-positive", IREN misclassified FINANCIALS — confirmed identical via git-stash A/B, not caused by this change).
- No concerns; scope held to multiple-temper only (WDC-base + CF stay separate per-memory WATCH items, untouched).
