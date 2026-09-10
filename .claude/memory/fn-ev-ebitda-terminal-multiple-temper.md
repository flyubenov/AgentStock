---
name: fn-ev-ebitda-terminal-multiple-temper
description: "IN-PROGRESS brainstorm (paused 2026-09-10, awaiting user): temper the uncompressed terminal EV/EBITDA multiple for thin-GROSS-margin forward-tier names. Signal CHOSEN (gross margin) + blast-radius swept; design pinned; next = pick MATURE anchor, write spec, TDD."
metadata: 
  node_type: memory
  type: project
  originSessionId: ff5aa68d-fad4-41cf-828f-5e7f910be8af
  modified: 2026-09-09T21:14:55.174Z
---

# FN validation + EV/EBITDA terminal-multiple temper (brainstorm PAUSED, resume here)

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

## NEXT STEPS (resume here)
1. **User to decide MATURE anchor:** 13x → FN +7% (fair); 14–15x → FN keeps modest ~+15–25% premium (reflects real 44% growth). (Also minor: band top 0.50→0.45 to zero out AAPL's −1.6%.)
2. Then: write spec to `docs/superpowers/specs/2026-09-XX-ev-ebitda-terminal-multiple-temper-design.md` → user reviews → `superpowers:writing-plans` → TDD (`superpowers:test-driven-development`). Establish green first; re-validate FN + canaries after.
3. Architectural path (new constant/mechanism, shared models.py). Record fix in memory when landed.
