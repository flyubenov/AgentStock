# Risk-Reward Rating Engine — Design Spec

**Date:** 2026-08-06
**Branch:** `feat/risk-reward`
**Status:** Approved design; ready for implementation planning.

## 1. Objective

Add a third, fully isolated scoring pipeline to the existing FastAPI + yfinance app
that rates a stock's **reward-versus-risk tradeoff at the current price**. It answers a
different question than the existing engines: not "what is it worth?" (Fair Value) or
"how good is the business?" (Quality Score), but **"is the potential reward worth the
risk of buying it right now?"**

The output is a single **Reward ÷ Risk ratio**, clamped to `[0.2, 5.0]` (neutral `1.0`),
with a tier label, three-level sub-scores, and a raw-data snapshot for auditing. It is
computed on every batch and single-ticker calculation and shown in the Results and
Database grids.

## 2. Scope and non-goals

**In scope**
- New `backend/risk_reward/` package (config, models, scoring, engine).
- New `services/risk_reward_sheets.py` (own Sheets tab + one mirrored Database column).
- Integration as a third parallel task in `orchestrator/batch._run_one`.
- On-demand endpoint `GET /api/analysis/risk-reward/{ticker}`.
- Frontend: `risk_reward` on `TickerResult`, tier helpers, a Risk-Reward column in the
  Results and Database grids, and a breakdown panel in the ticker detail view.
- TDD unit + integration coverage.

**Non-goals / hard constraints**
- **Total isolation from Fair Value and Quality Score.** This engine reads its own
  yfinance data, writes its own columns, and never imports, mutates, or depends on
  `valuation/` or `screener/`. Its failure must never fail either of the other two
  pipelines (independent `asyncio.gather` task, exceptions captured per-pipeline).
- **Defaults to N/A**, never a fabricated number. Thin data → `N/A`, not a fake ratio.
- **Zero hardcoding.** Every threshold, weight, tier boundary, and clamp lives in a
  Pydantic `BaseSettings` config object.
- No changes to the Fair Value or Quality Score columns, tabs, or grid cells.

## 3. Scoring model

### 3.1 Two axes, ratio output (Approach A)

Every metric is scored to a bounded float in `[1.0, 5.0]` by **linear interpolation**
between three raw anchor points (the values that map to scores 5, 3, 1). There are two
axes:

- **Reward** — higher metric score = more upside. Axis value = weighted average of its
  active metric scores.
- **Risk** — higher metric score = **more danger** (this is the key fix over the source
  PRD, which scored risk as "safe = 5" and then divided by it, inverting the ratio).
  Axis value = weighted average of its active metric scores.

**Technical/price-action metrics are distributed into both axes** (Approach A), not
applied as a separate modifier: price discount and RSI feed Reward; volatility, beta,
and trend feed Risk.

```
Reward = Σ(wᵢ · scoreᵢ)   over active reward metrics   (weights renormalized to 1)
Risk   = Σ(wⱼ · scoreⱼ)   over active risk metrics     (weights renormalized to 1)
Ratio  = clamp(Reward / Risk, 0.2, 5.0)
```

Because each axis is in `[1, 5]`, the raw ratio naturally lands in `[0.2, 5.0]` with a
neutral point of `1.0` (equal reward and risk). The clamp is a guardrail against edge
cases, not the primary bound.

### 3.2 Tiers

Mapped from the clamped ratio (boundaries configurable):

| Ratio | Tier |
|---|---|
| ≥ 2.0 | Asymmetric Upside |
| 1.3 – 2.0 | Reward-Favored |
| 0.8 – 1.3 | Balanced |
| 0.5 – 0.8 | Risk-Favored |
| < 0.5 | Value Trap |

### 3.3 Interpolation scorer

A single pure function scores every metric:

```
score(raw, a5, a3, a1) -> float in [1, 5]
```

`a5`, `a3`, `a1` are the raw values mapping to scores 5, 3, 1. They may be increasing
(higher-is-better metrics) or decreasing (lower-is-better / danger metrics); the function
is direction-agnostic. It performs piecewise-linear interpolation across the breakpoints
`[(a1, 1), (a3, 3), (a5, 5)]` — i.e. the two segments `(a1→1, a3→3)` and `(a3→3, a5→5)` —
and clamps the result to `[1, 5]` (values beyond `a5` or `a1` saturate). `None`/`NaN`
raw input returns `None` (metric is dropped; see §5).

## 4. Metric roster

Each metric has a **fallback chain**: if the primary source is missing, the next source
is tried before the metric is dropped. Anchors below are the **config defaults**
(tunable). `D/E` is read as yfinance reports it (a percentage, e.g. `85.3`).

### 4.1 Reward axis (higher score = more reward)

| Slot | Source → fallbacks | Direction | a5 | a3 | a1 | Weight |
|---|---|---|---|---|---|---|
| Valuation | `pegRatio`/`trailingPegRatio` → fwd earnings yield (`1/forwardPE`) → `1/priceToSalesTrailing12M` | lower PEG better | 1.0 | 1.5 | 3.0 | 18% |
| Growth | `revenueGrowth` → `earningsGrowth` | higher better | 25% | 10% | 0% | 18% |
| Profitability | `returnOnEquity` → `returnOnAssets` | higher better | 20% | 12% | 5% | 12% |
| Analyst upside | `(targetMeanPrice − price)/price` (1-yr consensus) | higher better | 30% | 10% | 0% | 8–18%† |
| Tech: discount | `(52W_high − price)/52W_high` | bigger discount better | 25% | 12% | 3% | 24% |
| Tech: RSI | RSI(14) from history | oversold better | 30 | 50 | 70 | 16% |

Fund 60 / Tech 40, summing to 100% at the Analyst-upside **base** weight (12%).

**† Analyst upside uses a confidence-scaled weight, not a static one.** The upside
*magnitude* is already fully captured by the score (anchors 30/10/0% → 5/3/1). What varies
per ticker is how much that score is *trusted*, driven by **analyst coverage and agreement**
— never by the size of the upside (weighting by magnitude would double-count it and hand the
most influence to the least-corroborated names). Two factors, each in `[0,1]`:

- **Coverage** — `numberOfAnalystOpinions`, ramping from 0 at ≤ `analyst_coverage_lo` (3)
  analysts to 1 at ≥ `analyst_coverage_hi` (20).
- **Agreement** — target dispersion `(targetHighPrice − targetLowPrice)/targetMeanPrice`,
  ramping from 1 at ≤ `analyst_spread_lo` (20% spread) down to 0 at ≥ `analyst_spread_hi`
  (80% spread).

Confidence `c = min(coverage, agreement)` (a signal is only as strong as its weaker leg),
and `weight = analyst_weight_floor + analyst_weight_span · c` = `0.08 + 0.10·c`, i.e. a
floor of 8%, base ≈ 12% (c ≈ 0.4), cap 18%. **Missing inputs collapse the affected factor
to 0** → the metric falls to the 8% floor (never dropped if it still has a `targetMeanPrice`
to score). This is deliberate for thinly-covered pre-profit names (NBIS/CRWV/ASTS/IREN),
where a lone price target is the least reliable input in the model — they sit at the floor,
they are **not** given extra analyst weight. The weight is computed per ticker at metric-build
time; the axis renormalization in §5 handles the rest, so no other metric's weight changes.

For the Valuation fallbacks, the anchors are re-expressed per source (earnings-yield
anchors ~8%/5%/2%; P/S-yield anchors are configured separately). Each fallback carries
its own anchor triple in config.

### 4.2 Risk axis (higher score = more danger)

| Slot | Source → fallbacks | Direction | a5 | a3 | a1 | Weight |
|---|---|---|---|---|---|---|
| Leverage | `debtToEquity` → net-debt/EBITDA | higher worse | 150% | 90% | 40% | 18% |
| Burn | `operatingMargins` → `profitMargins` | more negative worse | −15% | 0% | 15% | 15% |
| Liquidity | `currentRatio` → `quickRatio` | lower worse | 0.9 | 1.3 | 2.0 | 12% |
| Tech: volatility | annualized σ of daily returns (250d) | higher worse | 70% | 40% | 20% | 22% |
| Tech: trend | `(price − 200MA)/200MA` | further below worse | −15% | 0% | +8% | 18% |
| Tech: beta | `beta` | higher worse | 2.0 | 1.2 | 0.8 | 15% |

Fund 45 / Tech 55, summing to 100%. Net-debt/EBITDA fallback carries anchors ~4.0/2.5/1.0.

### 4.3 Deliberate design choices

- **Profitability appears on both axes** by design: high ROE adds reward; deep negative
  margins add risk. This covers both profitable and pre-profit names.
- **Momentum and max-drawdown are excluded** as redundant with discount + trend + volatility.
- **Analyst upside is a 1-year consensus** (`targetMeanPrice`) — the one sub-multi-year
  input, kept intentionally and weighted modestly (base ≈ 12%, confidence-scaled 8–18%; see
  §4.1†); it is a herd/sentiment signal and is muted to the 8% floor for thinly-covered or
  wildly-dispersed names rather than dropped outright.

## 5. Graceful degradation and coverage floor

- A metric with no value after its fallback chain is **dropped**, and the remaining
  weights **within that axis are renormalized to sum to 1** so the axis average stays on
  the `[1, 5]` scale.
- **Coverage floor:** a valid rating requires **≥ 2 active Reward metrics AND ≥ 2 active
  Risk metrics**. Otherwise the result is `N/A` with `status = "insufficient_data"`.
- The engine never raises on missing/NaN yfinance fields and never returns a 500 for data
  gaps; only genuine fetch failures (ticker doesn't resolve, network error after retries)
  produce `status = "failed"`.

## 6. Data ingestion

Two fetches per ticker, both through the dedicated `services/yf_pool` (never the default
executor — see the yf-pool memory), reusing the existing retry/backoff/timeout patterns:

1. **Info** — `services.yahoo.fetch_ticker_info(ticker)` (already cached per process).
   Fields consumed: `pegRatio`/`trailingPegRatio`, `forwardPE`, `priceToSalesTrailing12M`,
   `revenueGrowth`, `earningsGrowth`, `returnOnEquity`, `returnOnAssets`, `targetMeanPrice`,
   `targetHighPrice`, `targetLowPrice`, `numberOfAnalystOpinions` (the last three feed the
   confidence-scaled analyst weight, §4.1†), `currentPrice`/`regularMarketPrice`,
   `fiftyTwoWeekHigh`, `debtToEquity`, `totalDebt`, `totalCash`, `ebitda`, `operatingMargins`,
   `profitMargins`, `currentRatio`, `quickRatio`, `beta`. (All arrive in the single `info`
   dict — no extra fetch, and `RiskRewardInputs` needs no new fields to carry them.)
2. **Daily price history** — a new pooled helper (mirroring `_fetch_ev_ebitda_history_sync`)
   pulling `tk.history(period="1y", interval="1d", timeout=_HISTORY_TIMEOUT)` (~250 rows).
   Computed **locally** from the close series (per the PRD's freshness requirement):
   - **200-day MA** and **50-day MA** (simple moving averages).
   - **RSI(14)** (Wilder smoothing).
   - **Realized volatility** — annualized standard deviation of daily log returns
     (`σ_daily · √252`).
   - Fallbacks for `price` (last close) and `52W high` (rolling max) when the info
     fields are missing.

If the history fetch fails, all history-derived metrics drop and the fundamentals still
score (subject to the coverage floor).

## 7. Module layout and data models

```
backend/risk_reward/
  __init__.py
  config.py     # RiskRewardConfig(BaseSettings): anchors, weights, tier bounds, clamp, coverage floor
  models.py     # Pydantic: RiskRewardInputs, MetricScore, RiskRewardResult
  scoring.py    # interpolation scorer, axis aggregation, ratio/clamp/tier, insight text
  engine.py     # async run(ticker) -> RiskRewardResult  (fetch → derive → score → aggregate)
backend/services/
  risk_reward_sheets.py   # own tab + Database mirror column (mirrors screener_sheets.py)
```

`RiskRewardResult` (Pydantic) fields:

```
ticker: str
company_name: str | None
current_price: float | None
last_evaluated: str | None            # ISO timestamp
ratio: float | None                   # None when N/A
tier: str | None                      # e.g. "Reward-Favored", or None
reward_score: float | None            # axis average in [1,5]
risk_score: float | None              # axis average in [1,5]
actionable_insight: str | None        # templated from tier + dominant axis
metric_scores: dict[str, MetricScore] # per-metric: raw value, source used, score, weight
raw_snapshot: dict                    # audit: price, peg, d/e, dist_200ma_pct, rsi, vol, ...
status: Literal["completed", "insufficient_data", "failed"]
errors: list[str]
```

`MetricScore`: `{ raw: float | None, source: str | None, score: float | None,
weight: float, dropped: bool }`.

## 8. Configuration (`RiskRewardConfig`)

A Pydantic `BaseSettings` object holding: per-metric anchor triples (including per-fallback
anchors), per-metric weights (per axis, the Analyst-upside entry being the **nominal base**
that the confidence scaling overrides at runtime), the confidence-scaled analyst-weight knobs
(`analyst_weight_floor=0.08`, `analyst_weight_span=0.10`, `analyst_coverage_lo=3`,
`analyst_coverage_hi=20`, `analyst_spread_lo=0.20`, `analyst_spread_hi=0.80`), the fund/tech
split is expressed implicitly by the weights, `ratio_clamp = (0.2, 5.0)`, tier boundaries, the
coverage floor (`min_reward=2`, `min_risk=2`), RSI period (14), volatility annualization factor
(252), and history window (`period="1y"`). All overridable via environment variables.

## 9. Orchestration integration

In `orchestrator/batch._run_one`, add a third task alongside the FV and Screener tasks:

```
fv_task = asyncio.create_task(engine_run(ticker))
sc_task = asyncio.create_task(screener_run(ticker))
rr_task = asyncio.create_task(risk_reward_run(ticker))
fv_res, sc_res, rr_res = await asyncio.gather(fv_task, sc_task, rr_task,
                                              return_exceptions=True)
```

- `rr_res` is handled independently: on success, upsert to the Risk-Reward tab and mirror
  the headline to the Database column; on exception, record an error string and continue.
  A Risk-Reward failure never affects the FV or Screener persistence or the ticker's
  overall pass/fail accounting.
- The result dict gains `fv_dump["risk_reward"] = rr_dump` (mirroring the existing
  `fv_dump["screener"] = sc_dump` attachment), so the SSE stream and Results grid receive
  it with no stream-shape change.
- Runs on **every** path: `/analyse` (batch), `/recalculate-all`, and
  `/ticker/{ticker}/recalculate` all flow through `_run_one`.

## 10. Persistence

`services/risk_reward_sheets.py`, mirroring `screener_sheets.py`:

- Own **`Risk-Reward`** Sheets tab: `Ticker, Company, Last Evaluated, Ratio, Tier,
  Reward Score, Risk Score, <per-metric scores>, Raw Snapshot (JSON)`. Header
  auto-created/repaired exactly as `_ensure_screener_sheet` does.
- **Database mirror:** one new Database column, **`Risk-Reward`**, holding the numeric
  ratio (the UI derives the tier from the ratio via the tier helper, exactly as the
  Quality Score column holds a single number). Written for the ticker's row following the
  `_mirror_quality_score` pattern (find row by ticker in column A, ensure the header, write
  the cell). Uses a fresh, currently-unused Database column; **does not touch** the Fair
  Value or Quality Score columns. `N/A`/blank when not `completed`.
- `N/A`/blank when `status != "completed"`.
- Read path (`read_risk_reward`, `read_risk_reward_one`) for the endpoint and Database grid.

## 11. API endpoint

`GET /api/analysis/risk-reward/{ticker}` (added to `routers/analysis.py`; the app mounts
routers at `/api`, so this is the codebase-consistent form of the PRD's `/api/v1/...`).

- On-demand: runs `risk_reward.engine.run(ticker)` and returns the `RiskRewardResult` as
  JSON (ratio, tier, insight, sub-scores, per-metric detail, raw snapshot).
- Does **not** require a prior batch; useful for debugging and spot checks.
- Optional query param `sector_override: str | None = None` is accepted for forward
  compatibility (unused in v1; reserved for future sector-relative anchors).
- yfinance connection failures surface as a clean `HTTPException` (502-class) describing
  vendor degradation, not a raw 500.

## 12. Frontend

- **Types** (`frontend/src/types.ts`): add `risk_reward?: RiskRewardResult | null` to
  `TickerResult`; define `RiskRewardResult`; add `riskRewardColor(ratio)` and
  `riskRewardBadgeClass(ratio)` helpers (mirroring `qualityScoreColor` /
  `qualityScoreBadgeClass`), banding by tier boundaries (green ≥2.0 … red <0.5), with a
  neutral style for `N/A`.
- **Results grid** (`pages/Results.tsx`) and **Database grid** (`pages/Database.tsx`):
  add a **Risk-Reward** column rendering the ratio (e.g. `1.85×`) + tier badge; `N/A`
  when unscored. Database reads it from the mirrored value.
- **Ticker detail** (`pages/TickerDetail.tsx`): a small Risk-Reward panel showing the
  ratio, tier, the Reward/Risk sub-scores, and the per-metric contributions (score,
  weight, which source/fallback was used) for auditing.

## 13. Testing (TDD)

Unit (pure, no network):
- Interpolation scorer at each anchor (returns exactly 5/3/1), between anchors (linear),
  and beyond anchors (saturates at 5/1); `None`/`NaN` → `None`.
- Direction handling for both increasing (reward) and decreasing/danger (risk) anchors.
- Fallback chains select the next source when the primary is missing.
- Drop-and-renormalize keeps an axis average in `[1, 5]` when metrics are missing.
- Ratio computation, clamp to `[0.2, 5.0]`, and tier mapping at each boundary.
- Coverage floor: < 2 reward or < 2 risk active → `status = "insufficient_data"`, `ratio = None`.
- Local indicators: 200MA/50MA, RSI(14), realized volatility on a known synthetic series.

Integration (mocked yfinance info + history fixtures):
- A safe, profitable, reasonably-valued name → mid/high ratio, "Reward-Favored"/"Balanced".
- A volatile pre-profit burner → risk-heavy denominator, low ratio, still scored (burn +
  volatility present) or `N/A` if reward coverage < 2.
- A value-trap (cheap but leveraged, downtrend, negative margins) → ratio < 0.8.
- Isolation test: a Risk-Reward engine exception in `_run_one` leaves FV and Screener
  results and persistence intact.

## 14. Open items / future (not in v1)

- `sector_override` → sector-relative anchors (accepted but unused now).
- Optional richer insight text / natural-language rationale.
- Possible net-debt/EBITDA promotion from fallback to primary once EBITDA coverage is
  validated across the universe.
