---
name: lyft-earnings-inflated-guard
description: "LYFT FV +329% inflated by a one-time deferred-tax gain driving projected growth; added _earnings_inflated guard to re-source growth from revenue; TDD'd, LYFT-only blast radius, NOT yet committed"
metadata: 
  node_type: memory
  type: project
  originSessionId: b5a02239-c606-41f1-85c3-1d321ae001c2
  modified: 2026-07-23T07:55:49.052Z
---

Validated LYFT on 2026-07-23 (FINANCIAL/GROWTH tier). FV **$62.96 / +329%** was NOT a defensible center. Two causes, different fixability — **only the first is a bug**:

1. **BUG (fixed):** LYFT's FY2025 net income includes a one-time **~$2.9B deferred-tax valuation-allowance release** (non-cash). That inflated trailing `eps_ttm` to 6.60 (forward 2.09), `earnings_growth` to +489%, `return_on_equity` to 148% — all artifacts. `build_scenarios`' `else` branch sourced growth from that 489% (capped to 0.20), projecting a decade of 20% growth off a tax benefit. The fingerprint is the **inverse** of the AVGO depressed-trailing signal (`_normalized_forward_eps`): forward P/E far ABOVE trailing (7.02 vs 2.22, ratio 3.16) AND forward EPS BELOW trailing.
2. **MODEL LIMITATION (left, not a bug):** even fully de-poisoned, the DCF reads LYFT cheap because it takes ~$1.1B reported FCF as owner earnings (inflated by insurance-reserve float + SBC addback) and is blind to AV/robotaxi disruption. No clean signal to haircut on — the model working as designed on cheap multiples, not a defect. This is why the residual is still +211%.

**FIX — `_earnings_inflated(fin)` guard in engine.py** (mirrors `_earnings_distorted`; the positive-earnings twin of it). Fires when `earnings_growth > 0` AND `forward_pe/trailing_pe > DEPRESSED_PE_RATIO` (**reused** the 1.5 constant — no new knob, symmetric with the depressed signal) AND `forward_eps < eps_ttm`. Then re-sources `raw = min(revenue_growth, distorted_cap)` like the distorted path. Placed as an `elif` AFTER `_earnings_non_operating` so the operating-line signal wins when a statement reading exists (LYFT has none — `ev_ebitda_history` null — so it lands here).

**Why both conditions matter:** `feps < teps` alone catches a genuine soft year; the P/E-ratio threshold demands the market price a decline far steeper than a soft patch — the signature of a non-recurring trailing gain. The two positive-earnings guards partition cleanly against real growers: MU (eg 13.7 but forward EPS 153 >> trailing 43, forward P/E BELOW trailing) has `feps >= teps` and never fires.

**Blast radius = LYFT ONLY.** 37-ticker live sweep (canaries + megas + cyclicals + one-time-gain candidates): LYFT was the sole name to fire at any threshold (1.5/2.0/2.5). `eg > 0` excludes the loss-recoverers (F/INTC/WBD/IREN/NBIS/CRWV/TEM — negative trailing eps) and the amortization names (ABBV/SNPS/ETN/HON — eg<0); `feps < teps` excludes every genuine grower (their forward earnings are higher → ratio<1). Nearest non-firing `eg>0` name by ratio: JPM 0.95. HON has the only other ratio>1.3 (1.30) but eg<0. For every non-firing name the guard returns False at the first gate, so `evaluate` is byte-identical — the canaries are provably untouched (verified IREN $23.31 / NBIS $68.66 / KLAC $66.60 live, all inert).

**Result:** LYFT **$62.96 → $45.63 (+329% → +211%)**; DCF $102→$74, EV/Sales $33→$19, P/E leg unchanged ($41.69 — always forward-based, robust to the inflated trailing). 345 tests pass (338 + 7 new in test_engine.py). **DONE + MERGED to master (no-ff `dc43972`)**; fix @ `26af890`, edge pin tests @ `e4a5af2` (revenue_growth None floors to 0.02; DDM path bounds to SUSTAINABLE_CEIL). 347 tests pass. Inline Opus-subagent review (NOT the paid ultrareview — see [[no-paid-features-without-approval]]) came back **0 defects**: verified no div-by-zero, safe sign/None handling, the three guards partition cleanly (distorted eg<0 vs inflated eg>0, non-operating wins when present), re-sourcing byte-identical to the distorted path incl. DDM SUSTAINABLE_CEIL bound, band signal can't leak 489% into the optimistic leg. Three non-defect notes: feps<teps largely redundant with the P/E-ratio gate; guard can't fire if forward_eps/forward_pe missing (yfinance limit, not a bug); two correct-by-inspection edges untested (revenue_growth None/neg for an inflated name, DDM path).

**Quality 6.1 — SOUND, left as-is** (~0.5pt inflated by the DTA-poisoned `rote 107%`, but Section II held to 2.5 by three negative ROIC metrics; the poison is contained). See [[opfi-rim-roe-cap-gap]] (prior session's validation), [[bwxt-non-operating-growth-source]] (the sibling `_earnings_non_operating` guard), [[avgo-forward-eps-pe]] (the depressed-trailing signal this inverts), [[app-serves-persisted-rows-not-live-compute]].
