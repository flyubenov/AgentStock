# Fair Value Batch Calculator — Design Spec

**Date:** 2026-06-21
**Status:** Approved (brainstorming) — pending spec review
**Project:** Agent Stock

## Goal

Convert Agent Stock from an AI-agent stock-scoring app into a **free, unattended, parallel fair-value batch calculator**. It takes a list of stock tickers and outputs a fair value per ticker. All paid/AI functionality is removed; the valuation engine is replaced with `fairvalue3`'s adaptive, sector-aware methodology, adapted to run server-side over Agent Stock's existing batch + Google Sheets + progress-UI pipeline.

### What this delivers
- **No cost:** the Anthropic API dependency and all AI agents are deleted. The only external calls are to Yahoo Finance (`yfinance`, free) and Google Sheets (free within quota).
- **Better methodology:** `fairvalue3`'s classifier picks the right valuation models per company type (e.g. RIM/P-B for banks, SOTP/NAV for conglomerates) instead of applying a fixed model mix to every stock.
- **Unattended batch:** keeps Agent Stock's per-stock auto growth, Sheets in/out, parallel execution, and SSE progress.

## Background: the two source apps

- **Agent Stock** (this repo): batch harness (ticker list → parallel run → Sheets), per-stock growth derived from yfinance and capped [2%, 20%], multiple-capping for robustness. Weakness: a fixed three-engine model mix applied to every stock regardless of type (e.g. runs DCF on banks), plus the AI scoring agents that cost money.
- **fairvalue3** (`C:\Users\f_lub\proj\fairvalue3`): an adaptive valuation system — an 8-type classifier assigns a tailored model set + weights per stock. 10 models. Weakness for this use case: valuation math lives in the browser (TypeScript), single-ticker, stateless, and its default growth is a flat 15% for every stock (designed for interactive human tuning). Its `ev_ebitda_5yr_median` field is mislabeled — the normalizer maps it to the **current spot** `enterpriseToEbitda` (not a real historical median).

**Strategy:** Agent Stock is the base (its batch/pipeline shell is exactly the target shape); `fairvalue3`'s classifier + model engine is ported into it server-side.

## Resolved design decisions

1. **Growth (req #2):** Keep `fairvalue3`'s three-scenario engine but make scenarios **per-stock and capped**. `base = clamp(earnings_growth or revenue_growth or 0.07, 2%, 20%)`; `realistic = base`, `optimistic = min(base+5%, 25%)`, `pessimistic = max(base−4%, 2%)`. (This mirrors Agent Stock's current `calculator_1._scenarios`.)
2. **Pipeline:** Keep **Google Sheets as input and output**, and keep the **async streaming job + SSE progress** flow. The Anthropic *Batch API* path is removed entirely (it only existed for the agents); the streaming path (`orchestrator/batch.py`) provides the job/progress experience.
3. **Multiples:** Keep **spot multiples + capping** (EV/EBITDA ≤ 20, EV/Sales ≤ 8). The cap neutralizes most point-in-time distortion at near-zero cost. The misleading "5yr_median" field name is dropped. True historical medians are a future enhancement, out of scope.
4. **EV/EBITDA vs EV/Sales (req #4):** Never use both for one company. The rule arbitrates **only when the stock type weights both** (only LARGE_CAP and GROWTH do): use **EV/Sales** if EBITDA is null/≤0 **or** EBITDA margin (EBITDA ÷ revenue) < 8%, otherwise **EV/EBITDA**, and the loser's weight **folds into the winner**. If the type weights only one of the two, that one stands as-is (and if its input is missing — e.g. EV/EBITDA on a negative-EBITDA cyclical — it simply returns null and drops out via the normal insufficient-data path; the rule does not inject the other multiple into a type that didn't weight it).
5. **Weights (req #5):** Use `fairvalue3`'s classifier weight-assignment logic unchanged (8 stock types, per-type model weights).
6. **Capex → CFO (req #6):** `capex = operatingCashflow − freeCashflow`. If `CFO > 0` and `capex/CFO > 50%`, the **DCF (FCFF) model uses CFO** as its cash-flow base instead of FCF; otherwise FCF.

Thresholds (8% margin, 50% capex) are single tunable constants.

## Architecture

### Backend — delete
- `agents/` (all 7 files) and `prompts/` (all `.md`)
- `services/batch_service.py` (Anthropic Batch API) and `routers/jobs.py` (its endpoints) — *confirm during planning that `jobs.py` serves only the Batch API path*
- `services/normalizer.py` (agent-score normalization only)
- `valuation/calculator_1.py`, `valuation/calculator_2.py`, `valuation/gemini_fv.py`
- `anthropic` from `requirements.txt`
- Tests: `test_base_agent_parse.py`, `test_batch_service.py`, `test_normalizer_prescreener.py`

### Backend — keep (with edits)
- `services/yahoo.py` — extend `extract_financials` with fields the new models/classifier need: return on equity, payout ratio, interest expense, effective tax rate, sector, industry, long business summary, market cap, dividend rate, **operatingCashflow** (for the capex rule), trailing P/E, dividend yield.
- `orchestrator/batch.py` — replace per-ticker work (agent fan-out + 3 calculators) with a single `engine.run(ticker)`; keep grouping, concurrency, SSE events, and Sheets upsert as-is.
- `orchestrator/aggregator.py` — strip all agent-score logic; reduce to mapping one composite fair value + breakdown onto `TickerResult`.
- `services/sheets.py` — new Database column schema (below).
- `routers/analysis.py`, `routers/database.py`, `main.py`, `models.py` — strip agent wiring/fields; simplify `AnalyseRequest.mode` (only the streaming path remains).

### Backend — new `valuation/` package
- `valuation/classifier.py` — `fairvalue3`'s 8-type classifier, ported nearly verbatim (already Python). Uses **raw, uncapped** growth/margins for type detection.
- `valuation/models.py` — the 10 model functions ported from `fairvalue3/frontend/src/engine/valuation.ts`, each applying 10% MoS internally; EV/EBITDA and EV/Sales add spot-multiple caps (≤ 20 / ≤ 8).
- `valuation/engine.py` — orchestration (pipeline below).

### `engine.run(ticker)` pipeline
1. `fetch_ticker_info` → `extract_financials` → `fin` dict.
2. `classify(fin)` → `stock_type` + per-model weights.
3. Build per-stock capped scenarios (decision #1).
4. EV multiple selection + weight folding (decision #4).
5. DCF cash-flow base selection: FCF or CFO (decision #6).
6. Compute each enabled model (scenarios where applicable; single value for P/B, SOTP, NAV); each applies 10% MoS.
7. Drop null models (insufficient data); renormalize surviving weights to sum 1.0; composite = weighted average (post-MoS).
8. Return composite + `stock_type` + per-model breakdown.

### The 10 models
| Model | Type | Notes |
|---|---|---|
| DCF (FCFF) | scenarios | 10yr @ 10% discount, 3% terminal; base = FCF or CFO per decision #6 |
| EV/EBITDA | scenarios | spot multiple capped ≤ 20 |
| EV/Sales | scenarios | spot multiple capped ≤ 8 |
| P/E (justified) | scenarios | payout / (r − g) |
| DDM | scenarios | Gordon growth |
| RIM | scenarios | residual income, cost of equity 10% |
| P/B (justified) | single | ROE / r × BV |
| SOTP | single | EV/EBITDA × 0.85 conglomerate discount |
| NAV | single | BV − net debt/share |
| FCFE | scenarios | **dormant** — no stock type weights it; ported for completeness |

Constants (from `fairvalue3`): discount rate 10%, terminal growth 3%, horizon 10yr, MoS 10% per model, cost of equity 10%. No WACC (removing `calculator_2` removes the WACC computation and its divide-by-zero edge cases).

## Data model (`models.py`)

Delete `AgentResult` and `BatchJobFile`. Reshape the per-ticker result:

```
TickerResult:
  ticker, company_name, current_price, last_evaluated
  stock_type                      # e.g. "FINANCIAL"
  fair_value                      # composite, post-MoS
  price_vs_fair_value_pct
  fair_value_breakdown: dict[model_id -> {weight, fair_value, scenarios{opt,real,pess}, is_approx}]
  status: "completed" | "failed"
  errors: list[str]
```
Dropped: all `*_score` fields, `overall_*`, `agent_results`, `fair_value_results`, `fair_value_gemini/calculator_1/calculator_2`, `blended_fair_value`. `AnalyseRequest` and `JobStatus` stay.

## Google Sheets schema (`services/sheets.py`)

"Tickers" input tab: unchanged. "Database" output tab — core columns + one column per model (blank where a model didn't apply):

```
Ticker | Company Name | Last Evaluated | Stock Type | Fair Value |
Current Price | Price vs Fair Value % |
DCF | EV/EBITDA | EV/Sales | P/E | DDM | RIM | P/B | SOTP | NAV
```
FCFE omitted (dormant). Weights/scenarios live in the UI, not the sheet. `_DB_HEADERS`, `_result_to_row`, `_read_database_sync` update accordingly; upsert stays keyed by ticker.

## Data flow (shape unchanged)

Read tickers from "Tickers" → `run_batch` groups them → `engine.run(ticker)` in parallel → upsert each result to "Database" → SSE progress to the UI.

## Frontend (`frontend/src`)

### Delete
- `components/AgentCard.tsx`, `components/ScoreBadge.tsx`
- `pages/JobStatus.tsx` and the `/jobs/:jobId` route (Batch-API job page)

### Adjust
- **Home** — ticker input / "load from Sheet" + start run; drop the live/batch mode toggle.
- **Progress** — SSE progress bar unchanged (event shape identical).
- **Results** — replace agent-score cards with a valuation card per ticker: composite fair value, stock-type badge, current price, price-vs-fair-value % (color-coded under/over-valued), plus the per-model breakdown via `FairValuePanel`.
- **FairValuePanel** — render the new breakdown: one row per contributing model with weight, value, and opt/real/pess spread; SOTP and NAV flagged as approximations. (May borrow `fairvalue3`'s `ModelCard` layout; keep Agent Stock styling.)
- **TickerDetail** — full single-ticker breakdown (stock type, all models, scenarios).
- **Database** — table swaps agent-score columns for Stock Type, Fair Value, Current Price, Price vs FV %, and per-model values; stays sortable.
- **types.ts** — replace `TickerResult` shape (drop scores; add `stock_type`, `fair_value`, `fair_value_breakdown`); a small valuation badge (under/fairly/over-valued) replaces `ScoreBadge`.

*Exact per-file frontend edits (App.tsx routes, full component list) finalized during planning.*

## Error handling

- **yfinance fetch failure** → `failed` `TickerResult` (`"yfinance data unavailable"`); existing rate-limit backoff + per-ticker caching in `yahoo.py` retained.
- **Per-model insufficient data is normal** — null model dropped, weights renormalize. Only if **no** model resolves → `status="failed"` (`"insufficient data for any model"`).
- **Engine exceptions** caught per-ticker by `run_batch` (`return_exceptions`, `ticker_error` event) — one bad ticker never kills the batch.
- **Sheets write failure** stays non-fatal — appended to `result.errors`, run continues.
- **Rule guards:** capex→CFO only when CFO > 0 and both CFO/FCF present (else FCF); EV pick defaults to EV/Sales when EBITDA null/≤0.

## Testing

Backend (pytest, **static financial fixtures — no live yfinance calls**):
- `test_classifier.py` — each of the 8 stock types triggers on representative inputs (port `fairvalue3`'s cases).
- `test_models.py` — each model's math vs known inputs/outputs, including 10% MoS and the EV caps (≤ 20 / ≤ 8).
- `test_engine.py` — (a) per-stock capped scenario construction; (b) EV/EBITDA-vs-EV/Sales selection + weight folding; (c) capex→CFO swap above/below the 50% gate; weight renormalization on model drop; composite blend on a fixture; insufficient-data → failed path.
- Extend `test_yahoo_block.py` for the new `extract_financials` fields.
- **Golden-file** test: one fixed financials fixture → expected composite (blend regression guard).

Frontend (vitest): light — smoke + a `FairValuePanel` render test. The valuation logic `fairvalue3` unit-tested in `valuation.test.ts` is re-homed to backend `test_models.py`.

## Out of scope (future enhancements)
- True 5-year median multiples from historical data (v1 uses spot + caps).
- Maintenance-capex normalization for the DCF base (v1 uses raw CFO above the capex gate).
- The dormant FCFE model is ported but unused until a stock type weights it.

## Open items to confirm during planning
- Confirm `routers/jobs.py` serves only the Batch API path (nothing FV-related depends on it).
- Final per-file frontend edits (App.tsx routing, complete component inventory).
