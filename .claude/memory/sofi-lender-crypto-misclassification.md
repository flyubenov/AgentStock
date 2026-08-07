---
name: sofi-lender-crypto-misclassification
description: SOFI returned no FV because a crypto-keyword filter ejected the lender from the FINANCIAL bucket; fixed with a core-financial industry allowlist
metadata: 
  node_type: memory
  type: project
  originSessionId: ea25e0a9-65a1-45de-bc36-6155c47ebbed
---

SOFI (SoFi) returned **no Fair Value** — the FV engine declined it as `PRE_PROFIT`
("negative FCF / heavy investment") off its −$3.99B FCF (−102% of revenue). But SOFI is a
**profitable lender** ($481M NI, ROE 6.6%); that negative FCF is structural loan-book
growth, not a cash burn.

Root cause was a misclassification chain in `valuation/classifier.py`: SOFI's summary says
"sofi crypto, a new **digital asset** trading platform", which tripped
`NON_FINANCIAL_KEYWORDS` (built to catch crypto **miners / data-center ops** mis-tagged as
Financial Services). SOFI was ejected from **FINANCIAL** → fell through to **EARLY_GROWTH**
(DCF weight 0.35) → the DCF **pre-profit guard** (FCF/rev < −0.25) then declined it.

Fix (branch `screener-fixes`, 2026-07-12): added `CORE_FINANCIAL_INDUSTRIES =
("bank","credit services","mortgage","insurance")`. A genuine balance-sheet lender's
*industry* keeps it FINANCIAL even with a crypto mention, overriding the keyword filter.
Classifier-only change — once FINANCIAL, DCF weight is 0 so the guard is never reached.
Crypto miners (no lending industry) and exchanges/asset managers (Capital Markets, not in
allowlist) unchanged. SOFI now gets P/B+RIM+P/E → **FV $4.78** vs $18.78 price
(conservative: ROE 6.6% < ~10% cost of equity, ~2.2× book).

Note the **screener already handled SOFI correctly** (its `SECTOR_TO_PROFILE` maps
"financial services" → FINANCIALS with no keyword filter; screener score 5.4 is sound —
elite growth offset by modest ROTE 5.7% + heavy dilution). Only the FV classifier had the
crypto filter. Spec: `docs/superpowers/specs/2026-07-12-lender-crypto-misclassification-design.md`.
Same session as [[amd-acquisition-roic-distortion]].
