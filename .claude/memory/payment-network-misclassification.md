---
name: payment-network-misclassification
description: "DONE + MERGED to master (no-ff 3739b48): Visa/Mastercard were book-value-crushed (V FV $137/-61%) by the FINANCIAL bucket via yfinance 'Credit Services'; fixed by de-financializing pure payment networks -> V GROWTH FV $330"
metadata: 
  node_type: memory
  type: project
  originSessionId: f864a523-1eae-4d6e-a999-72b060eec317
---

**Symptom:** Visa (V) FV was $137.10 (−61.5% vs price $356) while Quality Score 8.6
was sound. FV was a misclassification artifact, not a real overvaluation call.

**Root cause:** `classifier._detect_type` tags V as `FINANCIAL` because its yfinance
industry is `"Credit Services"`, which is in `CORE_FINANCIAL_INDUSTRIES`. FINANCIAL
weights are book-value-anchored: P/B 0.35 + RIM 0.45 = 80% weight. For an asset-light
payment network (book value $18.64/sh vs 60% ROE, 71% EBITDA margin) that structurally
crushes FV. Only the P/E leg ($216) was methodologically valid. `"Credit Services"` is
a MIXED yfinance bucket: real balance-sheet lenders (Synchrony/Capital One/SoFi — loan
book IS the business, P/B+RIM fit) AND asset-light networks (Visa/Mastercard — toll-takers,
no loan book). Mirror image of [[sofi-lender-crypto-misclassification]] (SOFI wrongly
EJECTED from FINANCIAL; V wrongly TRAPPED in it).

**Fix (branch `fix/payment-network-classification`, off master, NOT merged):**
Added `PAYMENT_NETWORK_KEYWORDS` + `LENDER_KEYWORDS` + `_is_payment_network(summary)`:
a pure network = network/processor language present AND no deposit/loan-book language.
Gated the Financial-Services branch with `and not _is_payment_network(summary)`, so a
pure network falls through to the normal size/growth rules. V then lands in GROWTH at
rule 5 (17% growth, eps>0, yield 0.75%<1%, mcap $677B<$1T) BEFORE the LARGE_CAP default
at rule 8. No special-casing — just removed the trap and let existing rules route it.

**Discriminator validated on live data (P/B column proves it):**
- ROUTE OUT (book trivial): V (P/B 19×)→GROWTH FV $330, MA (71×)→GROWTH FV $483, PYPL (2.1×, asset-light processor)
- STAY FINANCIAL (real book): AXP (7.1×, "deposits and non-card lending" → `lending` keyword catches the hybrid), SYF (1.6×), COF (1.2×), SOFI (2.2×, FV $4.87 unchanged)

`"lending"` was the keyword added to keep the AXP network+loan-book hybrid in FINANCIAL.

**GROWTH vs LARGE_CAP (user asked):** GROWTH is where V lands under existing rules AND
the better fit — EV/Sales leg suits a 71%-margin grower, size-coupled fade tempers base
rate. LARGE_CAP is only the >$100B fallback for names matching no other bucket; a >$1T
network WOULD be LARGE_CAP (guard test encodes this boundary). FV ~$330 either way.

**Tests:** 4 classifier tests + 1 engine e2e guard. Full suite 234 passed (was 229).
Commits: 2bd66b0 (fix), 0d85f4f (e2e guard). MERGED to master @3739b48 (no-ff) on 2026-07-15; 234 passed on master. Branch `fix/payment-network-classification` kept.

Related: [[sofi-lender-crypto-misclassification]], [[amd-acquisition-roic-distortion]].
