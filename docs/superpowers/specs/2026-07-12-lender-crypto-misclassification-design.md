# FINANCIAL Classifier: Industry Allowlist for Crypto-Offering Lenders

**Date:** 2026-07-12
**Status:** Approved
**Area:** `backend/valuation/classifier.py`

## Problem

The Fair-Value engine returns **no FV** for SOFI (SoFi Technologies), failing with a
`PRE_PROFIT` decline: *"Negative free cash flow (pre-profit / heavy investment phase) —
trailing financials don't support a reliable valuation."*

SOFI is a **profitable lender** ($481M net income, EPS $0.45, ROE 6.6%). Its FCF is
structurally negative (−$3.99B, −102% of revenue) because originating loans consumes
operating cash — loan-book growth, not a cash burn. The decline is a false positive.

### Root cause: a misclassification chain

1. SOFI is a lender (industry: "Credit Services"). It should classify as **FINANCIAL**
   and be valued on book-value/earnings methods (P/B 0.35 + RIM 0.45 + P/E 0.20), with
   **DCF weight 0**.
2. The classifier's FINANCIAL rule rejects "Financial Services" names whose business
   summary contains `NON_FINANCIAL_KEYWORDS` (`crypto`, `digital asset`, `data center`,
   `bitcoin`, `mining`, …). That filter exists to catch **crypto miners and data-center
   operators** mis-tagged as Financial Services — genuinely not book-value businesses.
3. SOFI's summary says *"…and sofi crypto, a new **digital asset** trading platform."*
   Both `crypto` and `digital asset` match, so a real bank is ejected from FINANCIAL.
4. Ejected, SOFI falls through to **EARLY_GROWTH** (rule #4: revenue growth > 20% and
   no positive EBITDA), which carries **DCF weight 0.35**.
5. The DCF-weighted **pre-profit guard** then sees the −102% FCF margin and declines.

The **screener** classifies SOFI correctly (its `SECTOR_TO_PROFILE` maps "financial
services" → FINANCIALS with no keyword filter, and it has an explicit test that a
profitable negative-FCF lender is not treated as a burn). Only the FV classifier has the
crypto-keyword filter, and it can't distinguish "a crypto miner mis-tagged as a financial"
from "a real lender that merely offers a crypto product."

## Approach (chosen)

**Industry allowlist.** A genuine lending/banking/insurance *industry* keeps FINANCIAL
regardless of a passing crypto mention; the keyword override applies only to
Financial-Services names that are NOT a core-financial industry. Industry is a reliable
field and cleanly separates SOFI (a lender) from a crypto miner (no lending industry).

Rejected alternatives: *keyword precision* (fragile — depends on summary prose; SOFI's
phrasing would still trip it) and *infer-lender-from-financials* (indirect; the industry
tag states it directly).

### The change — `valuation/classifier.py`

```python
# Industries where the FINANCIAL valuation methods (P/B + RIM + P/E) genuinely fit —
# balance-sheet lenders/banks/insurers. A name in one of these stays FINANCIAL even
# when it also offers a crypto product (e.g. SoFi), overriding NON_FINANCIAL_KEYWORDS,
# which targets crypto miners / data-center operators mis-tagged as Financial Services.
CORE_FINANCIAL_INDUSTRIES = ("bank", "credit services", "mortgage", "insurance")
```

In `_detect_type`, rule #1 becomes (`industry` is already lowercased):

```python
if sector == "Financial Services":
    is_core_financial = any(kw in industry for kw in CORE_FINANCIAL_INDUSTRIES)
    if is_core_financial or not any(kw in summary for kw in NON_FINANCIAL_KEYWORDS):
        return "FINANCIAL"
```

No other file changes. Once SOFI is FINANCIAL its DCF weight is 0, so the pre-profit
guard is never reached — the classifier fix alone resolves the bug (guard logic untouched,
per scope decision).

## Behavior preserved

- **SOFI** — industry "credit services" → FINANCIAL (the fix).
- **Crypto miner / data-center** (`test_crypto_miner_not_financial`, no lending industry,
  summary mentions bitcoin mining) → keyword filter still fires → not FINANCIAL.
- **Real bank** (`test_real_bank_still_financial`, no keywords) → FINANCIAL via the normal
  path.
- **Exchanges / asset managers** (industry "Capital Markets", not in the allowlist) →
  unchanged; keyword override still applies. No scope creep.

## Expected outcome for SOFI

FV engine returns `completed` with **FV ≈ $4.78** (P/E $8.51 · P/B $5.01 · RIM $2.94),
versus the $18.78 price. The value is deliberately conservative — SOFI earns ROE ~6.6%,
below its ~10% cost of equity, and trades at ~2.2× book / ~42× trailing earnings, so the
book-value/RIM methods place it around/below book. This is the correct, honest financial
read; the fix is that the engine now *produces* it instead of declining.

The screener Quality Score (5.4) is unaffected and was already sound (elite growth offset
by modest ROTE 5.7% and heavy dilution) — out of scope here.

## Testing

- New: SOFI-like (Financial Services + industry "credit services" + crypto summary) →
  FINANCIAL.
- New: a Financial-Services crypto/data-center name with NO lending industry → still not
  FINANCIAL (guards against over-broadening).
- Keep `test_crypto_miner_not_financial` and `test_real_bank_still_financial` green.
- End-to-end: SOFI FV engine returns `completed` with a fair value (no PRE_PROFIT decline).

## Non-goals

- No change to the pre-profit guard, the FINANCIAL method weights, or the screener.
- No attempt to re-value fee-based financials (exchanges, asset managers) — they keep
  current behavior.
