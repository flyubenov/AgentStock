---
name: snps-dominant-acquisition-normalization
description: SNPS quality 6.5 too low — op-margin & leverage crushed by just-closed Ansys mega-deal; screener now normalizes both when goodwill dominates invested capital
metadata: 
  node_type: memory
  type: project
  originSessionId: ec5242b2-7a13-4470-8ffa-486fe30c76ec
---

SNPS scored quality **6.5** (too low) and FV **$275.95** (understated) — both distorted by the ~$35B Ansys acquisition that closed mid-2025. The engine already handled the ROIC side ([[amd-acquisition-roic-distortion]]: goodwill 95% of invested capital → reported ROIC 4.2 vs tangible 79.1, Section II lifted to 10) but NOT operating margin (12.97%, amortization-depressed), op-margin trajectory (−12.16), or leverage (net-debt/EBITDA 6.25x, net-debt/FCF 7.85x — full deal debt over pre-consolidation trailing EBITDA that excludes most of Ansys).

**Fix (DONE + MERGED to master, no-ff `4904585`; branch `feat/acq-opmargin-leverage-normalization` from master @71edda1, work commit 9153ea7):** mirror the ROIC fix in `screener/scoring.py`. New `_dominant_acquisition(m)` = `_acquisition_distorted` AND goodwill_intangible_share ≥ `DOMINANT_ACQUISITION_GOODWILL_SHARE` (0.70, set above AMD 0.63 / VST 0.23). When it fires, exclude the distorted metrics and let each section renormalize:
- Section I: exclude op_margin + op_margin_trajectory — gated by `_acq_margin_distorted` (requires trajectory < 0, so AMD +5.3 / VST +20.1 keep the metric).
- Section III: exclude net_debt_ebitda + net_debt_fcf via `_section_iii(exclude_acq_leverage=...)` — gated by `_acq_leverage_distorted` (requires net-levered, so net-cash AMD keeps its favourable score).

Guards are strictly one-way (can only remove a drag). Breakdown key `acquisition_consolidation_adjustment`. **SNPS 6.5→7.8** (I 5.71→6.6, III 3.33→10.0); AMD 7.2 & VST 5.7 unchanged; 259 tests pass (5 new TDD).

**FV side (DONE + MERGED to master, no-ff `3f671d5`; branch `feat/acq-dcf-forward-rebase` work commit @de60e7f):** the root cause was the DCF leg ($181) anchoring to trough trailing FCF ($1.35B, full Ansys deal cost but only a stub of Ansys earnings). Fix in `valuation/models.py` + `engine.py`: for a forward-tier name in a SEVERE earnings trough (`rebased_dcf_base`: forward EPS ≥ `TROUGH_REBASE_RATIO` 2.5× trailing EPS), rebase the DCF base onto forward run-rate owner earnings (forward_eps × shares; FCF ≈ owner earnings for these mature franchises), **capped at the forward-P/E leg value** so the rebased DCF can't run above that anchor. Wired in `evaluate` via `calc_dcf(base_override=, value_cap=)`, gated `is_forward_tier and dcf weight>0`.

Guards (user picked "rebase + cap" over uncapped/reroute via AskUserQuestion): ratio ≥ 2.5 excludes ongoing-amortization/SBC names with representative FCF (CDNS 2.18×, AVGO 3.24×); economic-sanity rejects run-rate > revenue (AVGO's glitched forward-EPS feed implies ~$92B > ~$75B rev — likely split-mangled, cf. [[klac-growth-undervaluation]]); only-help (base > trailing FCF); cap-at-PE. **SNPS FV $275.95 (−35%) → $356.62 (−16%)**: DCF leg $181→$383 (capped == P/E leg), EV/EBITDA $317 unchanged as conservative anchor. Live-verified surgical: ONLY SNPS moves; AVGO/CDNS/MSFT/AAPL/NVDA/KLAC untouched. 269 tests pass (8 new TDD). Note: capping collapses SNPS's 3 DCF scenarios flat to the P/E value (no spread) — acceptable, that's what "cap at anchor" means.
