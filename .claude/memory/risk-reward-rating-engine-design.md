---
name: risk-reward-rating-engine-design
description: "Risk-Reward Rating Engine (branch feat/risk-reward) — spec APPROVED+committed eaf515e, PLAN COMPLETE+committed a22e115 (14 tasks). Awaiting user's execution-approach choice before any implementation."
metadata: 
  node_type: memory
  type: project
  originSessionId: 31de67ef-da8c-40f1-a892-3af5f28621ed
  modified: 2026-08-07T19:50:00.000Z
---

Brainstorm (superpowers) for a **Risk-Reward Rating Engine** on branch `feat/risk-reward`. Design AGREED + SPEC WRITTEN & COMMITTED `eaf515e` (`docs/superpowers/specs/2026-08-06-risk-reward-rating-design.md`, spec APPROVED by user). **PLAN COMPLETE + COMMITTED `a22e115`** (`docs/superpowers/plans/2026-08-06-risk-reward-rating-engine.md`, 2103 lines, **14 tasks** — collapsed from 15 because the read endpoint folded into Task 9 mirroring the Screener). Tasks: 1 config, 2 models, 3 interpolation scorer, 4 indicators, 5 extraction, 6 aggregation, 7 data fetch, 8 engine, 9 Sheets tab+Database-col-R mirror+read endpoint+delete wiring, 10 `sheets.py` read A:Q→A:R + `DatabaseRow.risk_reward_ratio`, 11 orchestrator `batch._run_one` 3rd gather task (attach `fv_dump["risk_reward"]`, upsert gated on status=="completed", isolation tests), 12 frontend `types.ts` (`RiskRewardResult`/`RiskRewardMetricScore` ifaces + `riskRewardRatio/Tier/Color/BadgeClass` helpers), 13 Results.tsx+Database.tsx R/R column (sort+RangeFilter+watchlist `SerializedFilters.riskReward`), 14 RiskRewardPanel.tsx + TickerDetail 3rd tab. writing-plans self-review DONE (spec §1–§13 all mapped; §11 endpoint deviation documented inline — read `GET /api/risk-reward/{ticker}` in database.py per Screener idiom, compute-on-demand served by POST recalculate, `sector_override` deferred to §14 future; §13 archetypes covered by Task 6 boundary tests + Task 8 pipeline test; no placeholders; slot keys/types consistent backend↔frontend).

**ANALYST-WEIGHT DECISION — RESOLVED + COMMITTED `9da38e9` (2026-08-07).** User APPROVED **confidence-scaled** analyst weight as-is (explicitly said to IGNORE leaning MORE on analyst optimism for pre-profit names — they stay at the floor). Magnitude stays in the SCORE; WEIGHT scales with analyst *coverage + agreement*: `numberOfAnalystOpinions` ramp 0 at ≤3 → 1 at ≥20, dispersion `(targetHigh−targetLow)/targetMean` ramp 1 at ≤20% spread → 0 at ≥80%, `c=min(coverage,agreement)`, `weight=0.08+0.10·c` → [0.08,0.18], base ~12% at c≈0.4. **Missing any input collapses that factor→0 → 8% floor** (thin/hype/pre-profit muted, never dropped if targetMean present). Implemented NOT via `_ramp` (that helper is FV-side) but as plain clamp-lerp helpers `_analyst_confidence`/`_analyst_weight` in scoring.py. NO new RiskRewardInputs fields — the 3 fields ride the existing `info` dict, so Task 7/data.py unchanged. Weight computed at metric-build time in `build_metric_scores` (analyst_upside slot only); Task 6 `aggregate` renormalization UNCHANGED (already divides by active-weight sum). Nominal base 0.12 kept in `weights` for the config sum-to-1 invariant. AMENDED: spec §4.1(row+footnote†)/§4.3/§6(info fields)/§8(config), plan Task 1 (6 knobs `analyst_weight_floor 0.08`/`_span 0.10`/`_coverage_lo 3`/`_hi 20`/`_spread_lo 0.20`/`_hi 0.80` + test, count 3→4) and Task 5 (helpers + 3 tests, count 5→8).

**RESUME HERE:** design is fully locked & committed (spec `eaf515e`+`9da38e9`, plan `a22e115`+`9da38e9`). NEXT ACTION = offer the execution-approach choice — (a) subagent-driven-development (fresh subagent/task per task, two-stage review — RECOMMENDED) vs (b) executing-plans (inline batch w/ checkpoints). Do NOT start implementation until the user picks. Standing instruction each pause: "ask me for approve next time." (I offered this choice at the end of the 2026-08-07 session; awaiting the pick.)

**Plan build decisions (verified against code):** use frozen `pydantic.BaseModel`+`os.getenv` (NOT pydantic-settings — not installed); backend tests `cd backend && python -m pytest` (`asyncio_mode=auto`); frontend has NO unit runner → verify via `npm run build` (tsc). Database mirror col = **R** (Q=Quality mirror); `read_database` range A:Q→A:R, `_row_to_database_row` pad 17→18, parse row[17]. Batch attaches `fv_dump["risk_reward"]=rr_dump` as a dict key (like `["screener"]`), NOT a model field. Frontend quality/screener split pattern to mirror: nested obj in Results (`r.risk_reward.ratio`), mirrored number in Database (`r.risk_reward_ratio`). `run_yf(fn,*args)` forwards args. `score_metric` verified: PEG 1.25→4.0.

**Source PRD:** `Risk-Reward Rating-PRD.pdf` (repo root, untracked); text extracted to `scratch_prd.txt` (untracked). User said DO NOT follow it strictly — validate & improve.

**PRD validation verdict:** KEEP linear-interpolation scoring, graceful degradation (drop+reweight), local 200MA from 250d history, zero-hardcoding config. REJECT the headline formula `FR/FK × (1+(TM-3)/10)` — it's unbounded and self-contradictory (PRD's own worked example = 1.94 by the formula but sample payload says 1.42), and it divides by risk scored as "safe=5" (backwards). PEG/ROE collapse on the zero-earnings universe (NBIS/CRWV/ASTS/IREN) — needs fallbacks.

**AGREED MODEL — Reward ÷ Risk ratio (Approach A):**
- Risk scored in the **danger** direction (5 = dangerous) so `Ratio = Reward ÷ Risk` is meaningful. Clamp **[0.2, 5.0]**, neutral **1.0**.
- Tiers (configurable): ≥2.0 *Asymmetric Upside* · 1.3–2.0 *Reward-Favored* · 0.8–1.3 *Balanced* · 0.5–0.8 *Risk-Favored* · <0.5 *Value Trap*.
- **Approach A** = technicals live INSIDE both axes (volatility/beta/trend → risk; discount/RSI → reward), NOT a ±modifier. (Rejected Approach B modifier, and rejected bounded 1-10/1-5 composite options — user wanted an explicit tradeoff ratio.)
- Weighting: **Balanced ~40% tech** — Reward axis 60/40 fund/tech, Risk axis 45/55. **Exact per-metric defaults (config, tunable, re-normalized on drop):** REWARD = Valuation 18 / Growth 18 / Profitability 12 / Analyst-upside 12 / Discount-from-52Whigh 24 / RSI14 16 (=100). RISK = Leverage 18 / Burn 15 / Liquidity 12 / Volatility 22 / Trend-vs-200MA 18 / Beta 15 (=100). (Chose tilted over equal-within-group.)
- Analyst-upside metric = yfinance `targetMeanPrice` (**1-year** sell-side consensus, confirmed keep as-is); value=(target−price)/price, ≥30/10/≤0% → 5/3/1.
- Each metric → 1–5 by linear interpolation between 5/3/1 boundaries; missing metric dropped & its axis re-normalized; **coverage floor**: need ≥2 reward AND ≥2 risk else result = **N/A** (never a fake ratio, never a 500).

**Metric roster (fallback chains):**
- REWARD (5=high upside): Valuation PEG→fwdEarningsYield→P/S (PEG≤1/1.5/≥3); Growth revGrowth→epsGrowth (≥25/10/≤0%); Profitability ROE→ROA (≥20/12/≤5%); **Analyst upside targetMean vs price (≥30/10/≤0%) — user explicitly wants this IN**; Tech discount = dist below 52W high (≥25/12/≤3%); Tech RSI14 oversold (≤30/50/≥70).
- RISK (5=dangerous): Leverage D/E→netDebt/EBITDA (≥150/90/≤40%); Liquidity currentRatio→quickRatio (≤0.9/1.3/≥2.0); Burn op/net margin (≤−15/0/≥15%); Volatility annualized σ of 250d returns (≥70/40/≤20%); Beta (≥2.0/1.2/≤0.8); Trend price vs 200MA (≤−15/0/≥+8%). (Momentum & max-drawdown deliberately dropped as redundant.)

**Integration (all agreed):**
- Third **isolated** pipeline; **never touches Fair Value or Quality Score** code/columns; RR defaults to N/A. Mirrors the Screener pipeline exactly.
- Module layout `backend/risk_reward/{config,models,scoring,engine}.py` (mirrors `backend/screener/`); config = Pydantic BaseSettings with ALL thresholds/weights/tiers/clamp (zero-hardcoding).
- Data: reuse `services/yf_pool` (never default executor), one `info` fetch + one 250d history fetch; compute 200MA/50MA/RSI/vol/trend locally.
- Orchestrator: add a 3rd `asyncio.gather` task in `orchestrator/batch._run_one`, attach result to payload as `risk_reward` (like `screener`); independent failure isolation. Runs on EVERY batch + single-ticker recalc.
- Persistence: `services/risk_reward_sheets.py` — own `Risk-Reward` Sheets tab + ONE mirrored Database column (headline ratio+tier). Default N/A.
- Endpoint: `GET /api/analysis/risk-reward/{ticker}` (app mounts at `/api`, NOT the PRD's `/api/v1`), PRD-style payload + per-metric detail.
- Frontend (IN SCOPE now): add `risk_reward?` to `TickerResult` in `types.ts` + `riskRewardColor()/riskRewardBadgeClass()` helpers (mirror `qualityScoreColor`); new **Risk-Reward** column in BOTH `Results.tsx` and `Database.tsx`; breakdown in `TickerDetail.tsx`.
- TDD throughout (interpolation boundaries, drop-and-reweight, clamp, tier mapping, coverage-floor→N/A, golden tickers: safe profitable / volatile pre-profit burner / value-trap).

Related: [[app-serves-persisted-rows-not-live-compute]] (UI reads stored Sheets rows; only recalc recomputes), [[no-paid-features-without-approval]].
