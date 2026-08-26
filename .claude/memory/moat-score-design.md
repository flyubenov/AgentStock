---
name: moat-score-design
description: "Moat Score (durability-of-economic-profit, 0–100) — DONE + MERGED to local master (13 commits, fd7c241..aa59556), NOT pushed."
metadata:
  node_type: memory
  type: project
  originSessionId: cd567975-3d92-49b9-95bc-462fcb83e2cb
  modified: 2026-08-25T09:02:16.794Z
---

Moat Score = a **pure durability-of-economic-profit** score (0–100, numeric only, no
Wide/Narrow bands), a 4th rating alongside FV / Quality / R-R. Shown as one
sortable/filterable Database grid column. Rides the Screener pipeline as a pure
function over the `ScreenerMetrics` the Screener already computes — **zero extra
yfinance I/O**.

**DONE + MERGED to local `master`** (fast-forward, fd7c241..`aa59556`, 13 commits;
543 tests). **NOT pushed** — master is ahead 13 of origin/main; stale `origin/moat`
remote branch is 13 behind (local `moat` branch deleted after merge). Executed via
`superpowers:subagent-driven-development` (10-task TDD plan). Spec:
`docs/superpowers/specs/2026-08-24-moat-score-design.md`. Plan:
`docs/superpowers/plans/2026-08-24-moat-score.md`. Calibration report:
`docs/analysis/2026-08-24-moat-calibration/README.md`. SDD ledger (gitignored):
`.superpowers/sdd/2026-08-24-moat-score/progress.md`.

**Model:** Magnitude 40 (A1 ROIC/ROTE 5y level 20 + A2 ROIC−WACC spread blend 20)
/ Durability 50 (B1 persistence %yrs>hurdle 25 + B2 consistency/CoV 10 + B3 margin
durability stability+non-erosion 15) / Cash-backing 10 (C1 FCF/EBITDA). Structural:
economic-profit **gate** (`level ≤ hurdle` → cap ≤ MOAT_GATE_CEIL 35), reuse
acquisition ex-goodwill ROIC (`_acquisition_distorted` → TANGIBLE_ROIC axis),
**financials variant = ROTE − FINANCIAL_COE 8.5%** (deliberate, not inherited from
Quality), C1 + B3 both excluded for FINANCIALS (B3 exclusion added in calibration —
a bank's yfinance Gross Profit row is a net-interest proxy), C1 also excluded for
heavy-capex, renormalize over available points, coverage floor MOAT_MIN_YEARS 3 /
MOAT_MIN_PILLARS 3.

**Calibration (Task 10, user-approved 2026-08-25):** swept 22-ticker stratified
subset. Distribution matches intent (wide-moat 81–100, banks sane on ROTE, burners
gated). Two fixes applied, band tables kept as-is: (1) **B1 thin-spread cap**
(`B1_THIN_SPREAD_PP=2.0`/`B1_THIN_SPREAD_CAP=15.0` — cap B1 at 15 when blended
spread <2pp so stability can't masquerade as moat; latent in-sample); (2) **B3
excluded for FINANCIALS** (OPFI 66.9→66.2, all else byte-identical).

**Code:** new `backend/moat/` (`metrics.py` stats: mean/pstdev/persistence_fraction/
coef_of_variation; `scoring.py` model — public `score(m, profile) -> (float|None,
dict)`, no `moat/models.py`, folded into `ScreenerResult`). 7 series stored on
`ScreenerMetrics` (Task 1, percent-scaled, latest-first: roic_series,
roic_series_ex_goodwill, rote_series, rote_5y_avg, gross_margin_series,
op_margin_series, gross_margin_trajectory). Computed in `screener/engine.py` after
quality. Persistence: Screener tab gains trailing "Moat Score"+"Moat Breakdown";
Database **column S** (`DATABASE_MOAT_COL`), read range A:R→A:S; `DatabaseRow.moat_score`.
Frontend: `moatScoreColor` (≥70 grn/≥50 blu/≥35 yel/<35 red), Database grid column +
`moat` in watchlists `SerializedFilters`.

**DEFERRED (own branches, out of scope):** (a) V (Visa) blanks — genuine yfinance
gap (no EBIT row → roic_series empty → coverage floor), shared with Quality's
roic_ttm; fix = Operating-Income fallback in `screener.metrics.roic()`, a
Quality-engine change with wider blast radius. (b) CRWV dodges the gate via
`wacc=None` (no beta → level≤hurdle never fires). (c) fetch-once shared per-ticker
data context across all 3 pipelines (removes lru_cache reliance + ev_ebitda
double-pull) — relates to [[recalculate-all-flow-control]], [[yfinance-dedicated-pool]].

Related: [[wacc-mos-moat-margin-design]] (shares WACC/spread plumbing),
[[opfi-rim-roe-cap-gap]] (OPFI regulatory tail = unmodelable moat caveat).
