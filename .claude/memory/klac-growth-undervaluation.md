---
name: klac-growth-undervaluation
description: KLAC's "bad" valuation was a STOCK SPLIT (10:1, 2026-06-12), not data corruption — my guards misfired on it
metadata: 
  node_type: memory
  type: project
  originSessionId: cfe0d507-a709-4d95-b8c6-c0e9325cfa18
---

**RESOLVED + CORRECTION (2026-06-28).** KLAC's apparently-broken fair value was caused by a **10:1 stock split on 2026-06-12**, NOT data corruption. yfinance had split-adjusted the live quote (price $248.64, shares 1.306e9, trailingEps $3.53, P/E ~70x — all correct/consistent) but its **financial statements still carry pre-split per-share figures** (diluted shares 136M, EPS ~$35). The two views are 10x apart purely because of the split.

**The real, correct KLAC fair value is ~$87** (post-split, consistent data, no guards): dcf $76.66 / ev_ebitda $102.2 / pe $74.98, vs price $248.64 = -65%. At ~70x P/E KLAC is expensive, so FV < price is coherent (same shape as AMAT at -48%). The user's intuition ($90-115) was right; my earlier "corrected" $735/$488 were the artifact.

**Mistake to avoid repeating:** I diagnosed a split as corruption and built three things on it, all of which MISFIRE on recently-split stocks (statements lag the split):
- EPS-sanity guard (committed 0f150e4): "fixes" correct post-split EPS to the stale pre-split quarterly sum.
- Share-count guard (committed 644a900): "fixes" correct post-split shares to stale pre-split statement shares.
- Historical EV/EBITDA reconstruction: mixes split-adjusted prices with pre-split shares -> garbage 2.3x.

**How to apply:** Before treating a trailing-vs-statement divergence as data corruption, **check `yf.Ticker(t).splits` for a split AFTER the latest statement date** — if present, the divergence is expected and the info-dict is the correct source; do NOT substitute. The committed guards need to be made split-aware or reverted (they were built for a non-problem). The core forward-P/E + uncompressed-EV/EBITDA feature is fine on non-split names (AMAT ~$324). Related: [[eps-sanity-guard]], [[share-count-guard]], [[historical-evebitda-forward-pe]].
