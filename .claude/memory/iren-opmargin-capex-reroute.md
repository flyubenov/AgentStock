---
name: iren-opmargin-capex-reroute
description: "IREN 4.0/no-FV fix — broken yfinance info fields; spec done on branch, plan + implementation still pending"
metadata: 
  node_type: memory
  type: project
  originSessionId: a691983a-92a7-4c8b-8d2b-3d976d9ecf2c
---

IREN (bitcoin miner / AI data-centre) scored **4.0 with no FV**. Root cause: yfinance `info`
fields are broken for IREN while the statements are correct — `operatingMargins` −64.5% (real
statement +4.4%) and `revenueGrowth` −0.0% (real +167.7% YoY). Same villain poisons both pipelines.

**Design (approved 2026-07-12), branch `iren-opmargin-capex-reroute` off master:**
- **Fix #1 screener** (`metrics.py`, `scoring.py`, `models.py`): op_margin statement-primary
  (Operating Income / Total Revenue) with info fallback; add `revenue_growth_yoy` and make
  `_rule_of_40` prefer it. → score **4.0 → 4.7** (Section II 0.75 stays, correct). Side effect:
  `_heavy_capex_distortion` then fires (like AMZN [[distorted-earnings-dual-cap]]).
- **Fix #2 valuation** (`engine.py`, `services/yahoo.py`): reroute deeply-negative-FCF names onto
  EV/EBITDA+P/E (0.70/0.30) when **EBITDA>0 AND OCF>0** (OCF>0 = investing not burning; EPS
  deliberately excluded — accrual, inflated by non-cash BTC gains). Plus a statement revenue-growth
  fallback in `build_scenarios` (via extending `fetch_ev_ebitda_history`) or the FV is understated
  at the 7% default. → FV **none → ~$15 (−63% vs $41)**; correct = valued+expensive, not cheap.

**Weights updated 2026-07-13:** reroute is **0.85 EV/EBITDA / 0.15 P/E** (was 0.70/0.30) — the
gate excludes EPS (BTC-inflated NI), so don't trust it for 30% of the value. Positive-FCF reroute
(AMZN, clean earnings) stays 0.70/0.30, untouched. (spec commit 30aaaf9)

**Status: DONE + MERGED to `master` (2026-07-13, fast-forward, HEAD `6ca7049`), feature branch deleted,
full backend suite 203 pass. Trunk is `master` (no `main`, no git remote).** All 9 tasks executed via subagent-driven-development
(per-task TDD + review, final opus whole-branch review = Ready to merge, 0 Critical/Important).
Commits 46cfd1f→6ca7049. Screener op_margin/revenue_growth_yoy/rule-of-40; valuation
`_statement_revenue_yoy` (fraction) + build_scenarios fallback + 0.85/0.15 reroute gate in
`evaluate` + run() plumbs `ocf_ttm`/`revenue_growth_stmt`.

**Gotchas that surfaced:** (1) the reroute gate broke existing `test_evaluate_pre_profit_guard_fires`
(its `_large_cap_fin` has OCF>0 → would reroute); rewritten to a genuine burn (OCF<0). (2) The IREN
end-to-end test was initially non-discriminating — info OCF == statement OCF (both 246M) and a loose
FV band — so it couldn't catch a wiring typo; fixed by diverging info `operatingCashflow` to −50M
(broken, statement is truth) + tightening FV bound to `>20`; falsification-proven (remove either
plumbing line → test FAILS). (3) `_statement_revenue_yoy` takes `rows` not a DataFrame (testable).
Synthetic IREN-shaped fixtures; no live fetch. Next: merge (finishing-a-development-branch).

Related no-FV/data-quality fixes: [[sofi-lender-crypto-misclassification]],
[[nflx-ebitda-basis-mismatch]] (statement-consistent EBITDA base this design relies on).
