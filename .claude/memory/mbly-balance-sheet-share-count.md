---
name: mbly-balance-sheet-share-count
description: MBLY +193% was a dual-class share-count artifact yfinance marketCap ALSO undercounts; fixed via balance-sheet Ordinary Shares fold-in to _effective_shares
metadata: 
  node_type: memory
  type: project
  originSessionId: ac192cf8-a59c-4810-9fb7-6b791dabd9f0
  modified: 2026-07-31T20:54:48.072Z
---

DONE + MERGED to master (no-ff `b4b6f99`; fix @ `396f5ed`; TDD) — validating MBLY (Mobileye) surfaced a **+193% "undervalued"** ($23.27 vs price $7.94) that was a share-count artifact, NOT a real signal. True FV ≈ **$7.21 / −9.2%** (roughly fairly valued, slightly overvalued).

**Root cause — the inverse blind spot of [[dual-class-share-count-fix]].** MBLY is an Intel dual-class subsidiary (Intel holds ~715M Class B). yfinance reports BOTH `marketCap` ($2.0B) AND `sharesOutstanding` (252.4M) on the ~252M Class A count, so `market_cap/price == reported` and the existing `_effective_shares` implied-path gate can't see the hidden class. The balance sheet's `Ordinary Shares Number` / `Share Issued` = **814,748,862** is the only field carrying all classes. Every per-share leg (DCF, EV/Sales, …) divided whole-company FCF/EV by 31% of the shares → per-share FV inflated by 814.7/252.4 = **3.23×** (clean linear scaling; DCF $34.60→$10.72, ev_sales $10.52→$3.26). Tier unaffected (corrected mktcap ~$6.47B, still MID_CAP).

**Fix (TDD, 398 tests):** extended `_effective_shares(info, price, balance_sheet_shares=None)` in `services/yahoo.py` to fold a third full-class estimate into the SAME upward-only, 3%-gated max. Balance-sheet total rides the existing `fetch_ev_ebitda_history` balance-sheet fetch (new `_latest_ordinary_shares(bs)` helper, prefers `Ordinary Shares Number` = net of treasury over `Share Issued`); `engine.run` re-calls `_effective_shares` with it inside the `hist is not None` block. NO extra yfinance round-trip (mirrors the op-income-growth ride-along pattern). REUSE not invent: extended the existing dual-class helper rather than a new mechanism.

**Blast radius = MBLY-only (11-name probe).** Canaries byte-identical: IREN's balance-sheet count is SMALLER (0.722× — stale annual, pre-dilution) and upward-only correctly IGNORES it (the key downward-staleness protection); NBIS/GOOGL already handled by the implied path (bs agrees, no double-correction); AAPL/KLAC/MSFT/JPM/AVGO/NVDA/META all within the 3% gate because `Ordinary Shares Number` nets treasury and tracks the current count. Non-firing names get `shares_outstanding` reassigned to the identical value; `hist is None` names untouched.

**Carry-forward (same as [[dual-class-share-count-fix]]):** `book_value_per_share` is still on the single-class basis, so a hypothetical dual-class name valued on a P/B/RIM/NAV leg would be inconsistent. Inert for MBLY (MID_CAP = dcf+ev_sales only, no book leg). Latent limitation: the correction rides the EV/EBITDA-history fetch, which bails across a recent split — a name that is BOTH dual-class AND recently split would miss the correction (graceful fallback to reported).
