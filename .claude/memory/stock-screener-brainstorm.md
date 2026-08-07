---
name: stock-screener-brainstorm
description: "Stock Screener integration (deterministic no-AI quality score, isolated from Fair Value) — DONE + MERGED to master (ed3360a); Sheets round-trip now VERIFIED live (2026-07-16), no label drift"
metadata:
  node_type: memory
  type: project
  originSessionId: 8b0551d5-7845-4a75-b6c8-d249342dabfa
---

`Stock_Screener.md` integrated into Agent Stock as a **deterministic, no-AI, yfinance-only** 1-10 Business Quality Score, **isolated** from the Fair Value pipeline. Built via superpowers **subagent-driven-development** across 23 tasks / 9 phases (branch `screener-integration`, off master @ 1aa6920). **All 23 tasks done; final whole-branch review returned "Ship after fixes" with ZERO Critical findings; the one Important finding is fixed.** **MERGED to master via `--no-ff` merge commit `ed3360a` (2026-07-10); feature branch deleted; 152 backend tests pass on merged master.**

**Artifacts:** spec `docs/superpowers/specs/2026-07-08-stock-screener-integration-design.md`; plan `docs/superpowers/plans/2026-07-08-stock-screener-integration.md`; ledger `.superpowers/sdd/progress.md` (git-ignored, authoritative — per-task records, all 5 approved deviations, deferred Minors, final-review verdict).

**Verified:** 152 backend tests pass; `npm run build` clean; live read-only yfinance run scored AAPL 7.8 / MSFT 8.3 / KO 8.0 / NEE 4.1 / JPM 5.0 / O 6.2, with JPM → `FINANCIALS` (Section III `None`) and O → `REIT` as designed.

**RESOLVED 2026-07-16 — the Sheets round-trip HAS now run live.** Screener rows read back through `GET /api/screener/{ticker}` (AAPL 7.8/TECH_GROWTH, NBIS 4.6/BALANCED) and the batch write-path upserts fine. **The feared yfinance label drift did NOT happen**: fresh non-null metric counts are at or above the baselines below — AAPL 38, MSFT 41, JPM 29 (the model has since grown to 41 fields, so the old 37/35/27 numbers read low). AAPL's 3 nulls are the tangible-ROIC/goodwill fields (no material goodwill — correct). Watch item: a STORED AAPL row read back only 30 non-null vs 38 fresh, i.e. persisted rows predate newer fields — recalculate before trusting stored metric counts. Original warning, kept for the label list:

~~The Google Sheets round-trip has NEVER run live~~ — `_ensure_screener_sheet` (tab creation), the 40-col `Screener!A:AN` write, and `_mirror_quality_score` (Database col Q) are mock-tested only. Biggest real risk is **yfinance row-label drift** (metrics.py keys off exact labels like "Invested Capital", "Net Debt", "Repurchase Of Capital Stock"): a renamed label silently yields `None`, and under 6 sub-scores the score becomes `None`. On the first live analyse, check the Screener header lands in A1:AN1 with data from row 2, that `Database!Q1` reads "Quality Score" with values aligned to the right tickers, and that non-null metric counts still match the baseline (AAPL/MSFT/KO 37, NEE/O 35, JPM 27).

**Five user-approved deviations from the plan text** (all in the ledger): (1) revenue denominator = annual statement first, TTM fallback; (2) screener `_read_sync` swallows only the missing-tab error; (3) FV-exception path emits a full `TickerResult.model_dump()`; (4) a ticker counts as failed **only when both pipelines fail**; (5) `_run_job` was silently using a contradicting FV-only rule and now applies (4) too.

**Locked design:** output = ONLY the 1-10 score (no BUY/HOLD/SELL — user decides buys from the two isolated evaluations). One Analyse screen, tabbed FV|Screener. `screener/` never imports `valuation/`; FV `_result_to_row`/`_DB_HEADERS` stay 16 cols A:P; screener owns Database col Q + its own Screener tab. Sector-weighted threshold bands, sector-relative leverage pivots, deterministic sector nudge, Unprofitable Cap Rule. Related: [[size-coupled-growth-fade]].
