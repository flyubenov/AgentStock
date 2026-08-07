---
name: bwxt-non-operating-growth-source
description: BWXT projected 20% growth off earnings whose whole increment came from JV equity income while operating income fell; fixed by sourcing growth from the operating line — and the first cut compared a QUARTERLY info rate to an ANNUAL statement one
metadata:
  node_type: memory
  type: project
  originSessionId: aeef9c29-8bb7-4fc5-8aea-4e7a5c8d7f4d
---

BWXT validation, 2026-07-17. DONE + COMMITTED to master @`d2397df` (302 tests).

**The gap:** `build_scenarios` took `raw = fin["earnings_growth"]` as a proxy for future
cash-flow growth without asking whether the OPERATING business produced it. BWXT: +20.7%
earnings growth, but FY25 operating income FELL 1.4% (329.1 -> 324.6M) on +18.3% revenue;
operating income has gone nowhere for four years (308 -> 333 -> 329 -> 325M, 3y CAGR
+1.7%) while revenue grew 43%; operating margin compressed every year (13.8 -> 13.4 ->
12.2 -> 10.1%). The entire earnings increment came from BELOW the operating line — JV
equity income (55.9 -> 74.9M, up every single year; BWXT runs DOE site work through
unconsolidated JVs) plus other non-operating. The screener ALREADY caught this
(`op_margin_trajectory` -3.65 -> Section I 5.71); the valuation didn't. **When the two
pipelines disagree about one company, one of them is wrong — check which.**

**Fix:** `_earnings_non_operating` — mirror image of `_earnings_distorted`. There earnings
UNDERSTATE a healthy business (amortization; revenue stands in); here they OVERSTATE one
whose operating line is flat/shrinking, so source from the operating line itself. Revenue
is the WRONG fallback here — BWXT's top line grew precisely WHILE margins compressed, so
it overstates cash-flow growth for the same reason the earnings figure does. Existing
`max(0.02, ...)` floor stops a decline projecting negative growth. Sign-triggered (a
declining operating line is a real cliff; "earnings grew somewhat faster" is an arbitrary
threshold). BWXT $113.31 -> **$54.97 (-68.4%)**; 1 of 88 names moves.

**THE BUG I ALMOST SHIPPED — timeframe mismatch.** First cut tested `info['earningsGrowth']`
(latest-QUARTER YoY) against an ANNUAL statement operating change. Incoherent, and it
worked on BWXT only by luck. The universe scan caught it: it also fired on **CEG** (positive
quarterly bounce, but annual net income had FALLEN 38% and operating income had gone -408M
-> 4,198M over 3 years) and **DDOG** (operating income oscillating -59/-33/+54/-44M on a
-1.3% margin — the YoY is noise, not a trajectory; the ASTS tiny-base lesson again). Fixed
by making BOTH sides statement-annual from the same rows (`net_income_growth_stmt` vs
`op_income_growth_stmt`); the three YoY helpers collapsed into one `_statement_yoy(rows,
field)` so every reading shares a timeframe BY CONSTRUCTION. That single change dropped the
blast radius 4 -> 1 name. **Memory already recorded that yfinance's growth fields are
quarterly ([[tem-sign-artifact-bugs]]) and I walked into it anyway — when comparing two
rates, verify they share a timeframe before trusting the comparison.**

Statement rows now carry `operating_income` + `net_income` and ride the existing
`fetch_ev_ebitda_history` call (no extra yfinance round-trip — rate limits). Inherits its
bail-to-None when the EV/EBITDA median is uncomputable; the guard reads that as "unknown"
and leaves the source alone.

**Other BWXT findings, NOT fixed (reported, not authorised):**
- **Beta never reaches the valuation.** `extract_financials` hardcodes `cost_of_equity:
  0.10`, and that field only feeds the P/B + RIM legs (financials). Every non-financial
  DCF/EV leg discounts at the flat `DISCOUNT_RATE = 0.10` regardless of beta. BWXT's beta
  is 0.737 and the SCREENER computes a 7.53% WACC for it. At 7.53% BWXT's FV was $152.67
  (-12.1%) vs $113.31 (-34.8%). Biggest single lever in the model; universe-wide change,
  interacts with `MOS` and `MATURE_MULTIPLE_FACTOR`. See [[financial-coe-growth-pb]] (the
  same problem, solved only for banks).
- **`EV_EBITDA_CAP = 20.0` makes the historical multiple nearly irrelevant** for
  high-multiple names: BWXT hist 19.11x -> $113.31, but 22x/25x/28x/30.6x ALL give
  identically $116.04. Don't reason about multiple mean-reversion without checking the cap.
- **Screener leverage uses the outlier EBITDA basis.** `metrics.py` `m.ebitda =
  info.get("ebitda")` = 464.6M vs yfinance's own statement 551.5M / normalized 546.5M /
  TTM-quarterly-sum 568.9M. `net_debt_ebitda` = 3.26 (info) vs 2.67 (statement) — they
  STRADDLE the 3.0 pivot, so `leverage_score` 4.5 vs 7.0, Section III 5.0 vs 5.83, Quality
  6.0 vs ~6.25. Twin of [[nflx-ebitda-basis-mismatch]], which fixed only the valuation's
  multiple leg. Genuinely ambiguous which basis is right — the gap is JV equity income,
  real and recurring but NON-CASH, and excluding non-cash JV income from a debt-service
  ratio is defensible. Needs a judgment call, not a drive-by fix.
- **TSLA still extrapolates a quarterly bounce.** Its operating income fell 3 straight
  years (13,832 -> 4,849M) but annual NI fell too, so this guard correctly doesn't fire —
  the normal path still takes info's positive quarterly `earningsGrowth`. Pre-existing.

**CAUTION: BWXT now stacks 2% growth against the too-harsh flat 10% discount rate.** Two
conservatisms compounding — exactly the EG_CAP_CEIL-vs-stale-base trap
([[tem-sign-artifact-bugs]]). -68.4% is not a point estimate. BWXT already carries FOUR
stacked conservatisms: 10% DR, MOS 0.90, `MATURE_PE_CAP` 21, `EV_EBITDA_CAP` 20.

Related: [[app-serves-persisted-rows-not-live-compute]] (rows are stale until recalculated).
