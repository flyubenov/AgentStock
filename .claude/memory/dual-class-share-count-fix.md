---
name: dual-class-share-count-fix
description: multi-class per-share FV was inflated (KVYO 2.1x) by yfinance sharesOutstanding returning one class; gated market_cap/price correction
metadata: 
  node_type: memory
  type: project
  originSessionId: 6c83de08-c7a4-4e71-8086-a5ffe0bdb9e3
  modified: 2026-07-23T21:12:38.717Z
---

DONE + MERGED to master (no-ff `6005fbc`): validating KVYO surfaced a +236% "undervalued" that was a **share-count data artifact**. yfinance `info["sharesOutstanding"]` returns only ONE class (usually the Class A float) for multi-class companies, while `info["marketCap"]` / `impliedSharesOutstanding` capitalize ALL classes. Every FV leg in models.py divides an absolute equity value (FCF/revenue/net-debt) by `fin["shares_outstanding"]`, so per-share FV was inflated by `true_shares/reported_shares` (KVYO 140.9M vs 299.3M → 2.12x; FV $54.19→$25.51).

**Fix** (`services/yahoo.py`): new `_effective_shares(info, price)` helper + `_SHARE_GATE_RATIO = 1.03`, wired into `extract_financials`. Denominator sourced from `market_cap/price` (Option A — always present, makes the per-share divide consistent with the market_cap used by fade bands / MEGA-LARGE floors). **Upward-only + 3%-gated**: adopt implied only when `implied > reported*1.03`; single-class names diverge ≤0.1% (rounding) so stay byte-identical, smallest real multi-class gap is PLTR ~4.2%. Falls back to reported when mc/price missing or reported None/0. **Clean terminal rescale — NO valuation constant re-derived** (every cap/ceiling/fade/scenario constant operates on rates/multiples/market_cap BEFORE the per-share divide, so they keep doing their job). 375 tests, final opus review Ready-to-merge 0 Crit/0 Imp.

**Blast radius** (FV only; Quality is ratio-based, untouched). Live sweep verdict flips ALL directionally correct (toward "less cheap"): KVYO +236%→+59%; GOOGL BUY→SELL (−37%, now aligns with mega peers AAPL/AVGO/NVDA — the old +17% BUY was the artifact); META HOLD→SELL; CRWV HOLD→SELL (canary: must-not-flip-to-BUY held, moved FURTHER into SELL); V→mild HOLD; NBIS/HOOD/DDOG/PLTR small trims same verdict; APP BUY→BUY. **12 single-class canaries byte-identical**: IREN, KLAC, AAPL, JPM, NVDA, SNPS, ANET, TEM, BWXT, KO, NFLX, AVGO.

**KEY INSIGHT** (from final review): GOOGL's residual ratio is 0.535 not the 0.48 share ratio — because the weight-.10 P/E leg is already full-diluted-EPS-native (`eps*pe`, no share divide) so only the DCF/EV legs rescale. The fix IMPROVES internal consistency (pre-fix DCF/EV were inflated while P/E was already right). So per-share-native legs (P/E, DDM, P/B/RIM/NAV via yfinance bvps) are correctly untouched.

**CARRY-FORWARD gaps (out of scope, documented in spec):** (1) `book_value_per_share` (yfinance `bookValue`) is STILL single-class-inflated for the P/B / RIM / NAV legs — no in-scope multi-class name currently sits on a bvps-weighted tier; revisit if a FINANCIAL/P/B-tier multi-class name surfaces. (2) `screener/metrics.py:164` `tangible_bv_per_share` falls back to `info["sharesOutstanding"]` when the statement's `"Ordinary Shares Number"` is absent (Quality pipeline, untouched by design). Relates to [[app-serves-persisted-rows-not-live-compute]] — this is a live-compute fix; stored Sheets rows keep the old inflated FV until /recalculate.
