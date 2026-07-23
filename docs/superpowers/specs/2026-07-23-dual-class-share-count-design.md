# Dual-Class Share-Count Correction — Design

**Date:** 2026-07-23
**Branch:** `dual-class-share-count-fix` (off master `4d09516`)
**Scope:** FV pipeline only. Quality/screener untouched.

## Problem

Every valuation leg in `models.py` computes an absolute equity value (FCF, revenue,
net debt are all dollar amounts) and divides it by `fin["shares_outstanding"]` at the
end to get a per-share fair value. That denominator comes from
`extract_financials` → `info["sharesOutstanding"]` (`yahoo.py:302`).

For **multi-class companies**, yfinance's `sharesOutstanding` returns only one class
(typically the Class A float), while `info["marketCap"]` and
`info["impliedSharesOutstanding"]` reflect the full as-converted count across all
classes. The per-share FV is therefore inflated by `true_shares / reported_shares`.

The data is internally inconsistent: for KVYO, `marketCap / price` = 299.3M shares but
`sharesOutstanding` = 140.9M (≈ Class A float; `floatShares` = 139.9M). yfinance's own
`impliedSharesOutstanding` = 299.3M confirms the full count.

### Measured impact (live, 2026-07-23)

| Ticker | ratio (rep/true) | FV before → after | verdict before → after |
|---|---|---|---|
| KVYO | 0.47 | 54.19 → 25.52 | BUY +237% → BUY +59% |
| GOOGL | 0.48 | 374.19 → 200.10 | BUY +17% → SELL −37% |
| META | 0.87 | 557.26 → 487.57 | HOLD −8% → SELL −20% |
| CRWV | 0.82 | 71.38 → 58.56 | HOLD −15% → SELL −30% |
| V | 0.87 | 377.02 → 335.23 | HOLD +8% → HOLD −4% |
| NBIS | 0.87 | 68.66 → 59.61 | SELL −70% → SELL −74% |
| HOOD | 0.88 | 29.14 → 26.97 | SELL −72% → SELL −74% |
| APP | 0.91 | 583.12 → 537.20 | BUY +45% → BUY +34% |
| DDOG | 0.93 | 133.60 → 130.97 | SELL −46% → SELL −47% |
| PLTR | 0.96 | 55.62 → 54.20 | SELL −55% → SELL −56% |
| single-class (IREN, KLAC, AAPL, JPM, NVDA, SNPS, ANET, TEM, BWXT, KO, NFLX, AVGO) | 1.00 | unchanged | unchanged |

Every verdict flip moves *toward "less cheap"* (removing an inflation bug). GOOGL's
BUY → SELL is the fix working: it now reads like its mega-cap peers (AAPL −43%, AVGO
−40%, NVDA −9%) instead of appearing uniquely cheap because its FV was doubled.

## The fix

In `extract_financials` (`yahoo.py`), replace the raw denominator with a small gated
helper. Source the corrected count from `market_cap / current_price` (Option A —
robust: both fields are already required across the model and used for tiering; makes
the per-share denominator definitionally consistent with the `market_cap` used by fade
bands and the MEGA/LARGE floors).

```
reported = info["sharesOutstanding"]
if not (market_cap and current_price):     # can't derive implied → keep reported
    return reported
implied = market_cap / current_price       # count the market is capitalizing
if not reported or reported <= 0:          # no usable reported count → adopt implied
    return implied
if implied > reported * 1.03:              # hidden share class → correct upward
    return implied
return reported                            # single-class / within tolerance → unchanged
```

Properties:

- **Upward-only.** We never adopt a *smaller* denominator than reported, so the fix can
  only *remove* inflation, never introduce it.
- **3%-gated.** Single-class names diverge ≤ 0.1% (rounding); the smallest real
  multi-class gap is PLTR at ~4.2%. A 3% threshold sits in the empty band between them —
  above intraday `market_cap`/`price` staleness (~1–2%), below the smallest real gap.
  Single-class names stay **byte-identical**.
- **Leg math unchanged.** Every leg keeps dividing by `fin["shares_outstanding"]`; only
  the value flowing into that field changes.

## Blast radius & re-derivation stance

**This is a clean terminal rescale — no calibrated constant needs re-deriving.**

- Every tuned constant — `GROWTH_CAP*`, `EG_CAP*`, `_ev_ebitda_ceiling`,
  `_fade_hold_years`, the scenario band (`SCEN_*`), leverage tempers — operates on
  **growth rates, multiples, or `market_cap`**, all *before* the final per-share divide.
  The fix rescales only that terminal divide, so each constant keeps doing its job.
- The one share-*dependent* guard, `rebased_dcf_base`'s `base = forward_eps × shares`
  economic-sanity check (`base > revenue` ⇒ reject), only becomes **more correct**:
  forward EPS is reported on the full diluted count, so `feps × true_shares` ≈ true
  total forward earnings. In practice it only touches SEVERE-trough **single-class**
  names (e.g. SNPS, ratio 1.00), which are unaffected.
- No documented fix ever tuned a constant to *hit* a per-share FV target for a
  multi-class name. V's $330 came from a **classification** change; NBIS's 0.35 EARLY
  ceiling from a **stale-base** fix. Per-share FV was always an *output*, never a target
  a constant chased — so nothing absorbed the share error.

Plan: **apply the rescale, re-baseline reported verdicts, verify via the universe
sweep — do not pre-emptively re-tune anything.** A canary flipping the *wrong* way
(a name becoming spuriously cheap) would flag a hidden dependency; the sweep above
shows none — every flip is toward "less cheap," and CRWV (the must-not-flip-to-BUY
canary) moves further into SELL.

## Testing

1. **TDD the gate** in `test_yahoo_block.py`:
   - dual-class info (`marketCap/price` ≫ `sharesOutstanding`) → corrected (larger) count.
   - single-class (implied within 3% of reported) → keeps `sharesOutstanding`.
   - missing `marketCap` or `currentPrice` → falls back to `sharesOutstanding`.
   - `sharesOutstanding` None/0 with valid `marketCap`/price → adopts implied (no crash).
   - implied *below* reported → keeps reported (never corrects downward).
2. **Full `pytest` stays green.** Engine/models tests build synthetic `fin` dicts and
   call `evaluate()` directly, bypassing `extract_financials` — they do not move. The
   only test sharing the changed function, `test_extract_financials_adds_valuation_fields`,
   has no `marketCap` in its `info`, so the gate no-ops and it still passes.
3. **Read-only universe sweep** post-change: confirm every single-class canary is
   byte-identical, every multi-class name moved by ~its ratio, and no BUY/SELL flip
   beyond the intended re-ratings (CRWV stays SELL; IREN/KLAC/NBIS canaries sane).

## Out of scope

- Re-tuning any growth cap, ceiling, fade, or scenario constant (see stance above).
- Quality/screener pipeline (ratio-based; share-count independent).
- `book_value_per_share` (a yfinance-provided per-share figure, not derived from
  `shares_outstanding`; the FV legs that would use it — P/B, RIM — are not on the
  affected multi-class names' tiers here). If a future validation surfaces a P/B-tier
  multi-class name, revisit then.
