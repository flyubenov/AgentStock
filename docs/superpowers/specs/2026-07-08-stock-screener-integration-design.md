# Stock Screener Integration — Design Spec

**Date:** 2026-07-08
**Status:** Draft for review
**Author:** brainstormed with Claude

## 1. Overview

Integrate the `Stock_Screener.md` evaluation framework (originally a Google Gemini Gem)
into Agent Stock as a **fully deterministic, no-AI, yfinance-only** pipeline that produces a
**1–10 Business Quality Score** for each ticker.

The screener runs **alongside** the existing Fair Value pipeline but is **architecturally
isolated** from it: separate modules, classes, types, storage, and scoring. The two pipelines
share only the low-level yfinance data-access layer (for network efficiency) and the UI shell.
The user makes their own buy/sell decisions by reading the two independent lenses side by side.

### Goals
- Deterministic 1–10 Quality Score per ticker, computed purely from yfinance data.
- No AI anywhere in the flow.
- Full isolation from the Fair Value pipeline (own engine, models, scoring, storage).
- Preserve the existing parallel per-ticker batch execution.
- Persist results and surface them in the Database grid + a Screener detail tab.

### Non-Goals (explicitly out of scope)
- **No BUY/HOLD/SELL verdict** and **no "Growth Potential" label.** The headline output is the
  Quality Score only. The user combines the two lenses manually.
- **No moat / risk / narrative text** — non-deterministic, requires judgment. Dropped.
- **No peer-comparison columns** (`{{peer_*}}` in the template) — no reliable peer set from
  yfinance. Replaced by static "Rule of Thumb" thresholds baked into the scoring bands.
- No AI, no LLM calls, no external data sources beyond yfinance (+ `^TNX` for the risk-free rate).
- The score is **not investment advice** (existing app disclaimer applies).

## 2. Data Feasibility (verified live vs yfinance 1.3.0)

~90% of the numeric screener is deterministic from yfinance. Annual statements return ~5 years
(e.g. AAPL 2021–2025). Confirmed-present statement rows: `Invested Capital`, `Tangible Book
Value`, `Net Debt`, `Stock Based Compensation`, `Repurchase Of Capital Stock`, `Cash Dividends
Paid`, `Diluted EPS`, `EBIT`, `Operating Cash Flow`, `Free Cash Flow`, `Capital Expenditure`,
`Total Assets`, `Gross Profit`, `Operating Income`, `EBITDA`, `Total Revenue`, `Tax Rate For
Calcs`, `Diluted Average Shares`, `Ordinary Shares Number`.

- `.info`: `trailingPE`, `forwardPE`, `trailingPegRatio`, `priceToSalesTrailing12Months`,
  `heldPercentInsiders`, `grossMargins`, `operatingMargins`, `returnOnEquity`, `ebitda`,
  `totalDebt`, `totalCash`, `enterpriseValue`, `marketCap`, `sharesOutstanding`, `beta`,
  `freeCashflow`, `operatingCashflow`, `totalRevenue`.
- Risk-free rate: `^TNX` last close ÷ 10 = 10-year Treasury yield %.
- Price CAGRs: `.history(period="6y", interval="1mo")`.

### Known data caveats (design must handle)
1. **"5-Year" CAGRs are really ~4-year.** Statements give 5 annual columns (some tickers only 4).
   A true 5Y CAGR needs 6 points. Compute over the **available span** and label it (`5y*`),
   falling back gracefully. 3Y CAGRs are always safe.
2. **WACC needs an assumed constant** — a hard-coded equity-risk-premium (default **5.0%**).
3. **Per-field `None` is normal** (transient yfinance gaps). Every metric degrades gracefully.
4. **Financials (banks/insurers)** — debt and EV/EBITDA-style metrics are not meaningful. The
   scoring uses a dedicated sector profile that down-weights those; flagged as a known limitation.

## 3. Architecture

New isolated package `backend/screener/`, mirroring the shape of `backend/valuation/`:

```
backend/
  screener/
    __init__.py
    models.py       # ScreenerInputs, ScreenerMetrics, ScreenerResult (own types)
    data.py         # fetch_screener_inputs(ticker) -> ScreenerInputs
    metrics.py      # pure functions: raw inputs -> ScreenerMetrics
    scoring.py      # threshold bands, section rollup, sector weights, caps -> quality_score
    engine.py       # run(ticker) -> ScreenerResult  (async IO wrapper)
  services/
    statements.py   # NEW shared, cached low-level yfinance statement fetchers
    screener_sheets.py  # NEW: Screener tab I/O + Database-tab score mirror
```

**Shared layer (network efficiency, not domain coupling):** `services/statements.py` provides
`@lru_cache`d fetchers for `income_stmt`, `balance_sheet`, and full multi-year `cashflow` as
plain dicts/lists of primitives. Both pipelines call these, so running both for a ticker does
**not** double-hit the network (`.info` is already cached in `services/yahoo.py`). Each domain
maps the primitives into its **own** types — no shared domain classes.

**Isolation guarantees:**
- `screener/` never imports from `valuation/` and vice versa.
- Screener has its own result type (`ScreenerResult`), its own sheet tab, its own scoring constants.
- The Database grid is a **read-side join** composed in the router — neither domain type learns
  about the other.

### Data flow
```
ticker
  -> screener.data.fetch_screener_inputs   (info + 5y statements + ^TNX + price history)
  -> screener.metrics.compute              (ScreenerMetrics: Sections I-V, all deterministic)
  -> screener.scoring.score                (1-10 quality_score + section sub-scores)
  -> ScreenerResult
  -> screener_sheets.upsert                (Screener tab full + mirror score to Database tab)
```

## 4. Metric Definitions

All metrics are computed by `screener/metrics.py` as pure functions over `ScreenerInputs`.
CAGR helper: `(end/start)**(1/years) - 1`, requiring both endpoints > 0; else `None`.

### Section I — Growth & Operational Trajectory  *(scored)*
| Metric | Formula / source |
|---|---|
| Revenue CAGR 3Y | `Total Revenue` 3y CAGR |
| EPS CAGR 3Y | `Diluted EPS` 3y CAGR |
| FCF CAGR 3Y | `Free Cash Flow` 3y CAGR |
| **FCF margin** (cash-quality) | `Free Cash Flow` / `Total Revenue` (TTM) |
| Operating margin level | `operatingMargins` |
| Operating margin trajectory | current OM − OM 3–5y ago (pp) |
| Gross margin level | `grossMargins` (moat proxy) |

### Section II — Capital Efficiency & Value Creation  *(scored)*
| Metric | Formula / source |
|---|---|
| ROIC (TTM) | `EBIT`×(1−tax) / `Invested Capital` |
| 5-yr Avg ROIC | mean of annual ROIC over available years |
| ROIC − WACC spread | ROIC_TTM − WACC |
| ROTE | `Net Income` / `Tangible Book Value` |
| WACC (input to spread) | CAPM: `rf(^TNX) + beta×ERP(5%)` for equity; `interest/TotalDebt×(1−tax)` for debt; capital-weighted |

### Section III — Balance Sheet & Solvency  *(scored, with Dual-Check)*
| Metric | Formula / source |
|---|---|
| Net Debt / EBITDA | `Net Debt` / `ebitda` |
| Net Debt / FCF | `Net Debt` / `Free Cash Flow` |
| OCF / CapEx | `Operating Cash Flow` / abs(`Capital Expenditure`) |
| Tangible Book Value / Share | `Tangible Book Value` / shares *(reference)* |

### Section IV — Shareholder Dilution, Quality & Ownership  *(scored)*
| Metric | Formula / source |
|---|---|
| Outstanding Shares CAGR 3Y | `Diluted Average Shares` 3y CAGR (negative = buyback) |
| SBC % of Revenue | `Stock Based Compensation` / `Total Revenue` |
| Earnings Quality | `Operating Cash Flow` / `Net Income` |
| Insider Ownership | `heldPercentInsiders` |
| Shareholder Yield | (abs(`Repurchase Of Capital Stock`) + abs(`Cash Dividends Paid`)) / `marketCap` |

### Section V — Valuation  *(computed & stored, NEVER scored — price-isolated)*
Trailing/Forward P/E, PEG, Price/FCF, Price/Sales, **FCF Yield (FCF/EV)**, Owner-Earnings-Yield
vs 10Y Treasury, Price CAGR 3Y/5Y. Displayed for the user's own judgment; excluded from the score.

> **FCF Yield decision:** FCF Yield (FCF/EV) has price in the denominator, so scoring it would
> re-couple quality to price. The price-isolated cash-quality signal — **FCF margin (FCF/Revenue)**
> — is scored in Section I instead. FCF Yield remains in Section V as reference only.

## 5. Quality Score Rubric (deterministic)

**Approach: weighted threshold-band scoring with sector weights** (chosen over points-checklist
and relative/percentile).

### 5.1 Per-metric sub-scores (0–10 via threshold bands)
Each scored metric maps to a 0–10 sub-score via explicit bands. v1 bands (tunable constants in
`scoring.py`):

```
ROIC (TTM / 5yr avg):   >20→10  15-20→8.5  10-15→6.5  5-10→4  0-5→2  <0→0
ROIC−WACC spread (pp):  >10→10  5-10→8  0-5→5.5  -5-0→2.5  <-5→0
ROTE:                   >25→10  20-25→8.5  15-20→7  10-15→5  5-10→3  <5→1
Revenue CAGR 3Y:        >20→10  15-20→8.5  10-15→7  5-10→5  2-5→3  0-2→1.5  <0→0
EPS CAGR 3Y:            (same shape as Revenue CAGR)
FCF CAGR 3Y:            >15→10  10-15→8  5-10→6  0-5→4  <0→1
FCF margin:             >20→10  15-20→8.5  10-15→7  5-10→5  0-5→3  <0→0
Op margin level:        >25→10  15-25→8  8-15→6  0-8→3  <0→0
Op margin trajectory:   >+2pp→10  0..+2→7  -2..0→4  <-2→1
Gross margin level:     >60→10  40-60→8  25-40→6  10-25→4  <10→2
Net Debt/EBITDA:        SECTOR-RELATIVE (pivot P, see §5.3.1)
Net Debt/FCF:           SECTOR-RELATIVE (pivot Q, see §5.3.1)
OCF/CapEx:              >5→10  3-5→8  2-3→6  1.5-2→4  1-1.5→2  <1→0
Shares CAGR 3Y:         <-3→10  -3..-1→8.5  -1..0→7  0..+1→5  +1..+3→3  >+3→1
SBC % Rev:              <2→10  2-5→8  5-10→6  10-15→3.5  15-20→1.5  >20→0
Earnings Quality:       >1.2→10  1.0-1.2→8.5  0.8-1.0→6  0.6-0.8→4  <0.6→1.5   (clamp if NI≈0)
Insider Ownership %:    >10→10  5-10→8  2-5→6  0.5-2→4  <0.5→2
Shareholder Yield %:    >6→10  4-6→8.5  2-4→6.5  0-2→4  <0→1.5
```

### 5.2 Section rollup
Each section score = **mean of its available metric sub-scores** (missing metrics excluded, so a
section renormalizes over what exists). If a whole section has no data, its weight is
redistributed proportionally across the sections that do.

### 5.3 Sector profiles, leverage pivots, and the metric nudge

#### 5.3.1 Profiles (weights over the 4 scored sections, sum = 1) + leverage pivots
Weights are deliberately **moderated** (roughly [0.15, 0.40]) so a wrong sector label has bounded
impact. Each profile carries **sector-relative leverage pivots** `P` (Net Debt/EBITDA) and `Q`
(Net Debt/FCF) so structurally-levered sectors are judged on their own scale rather than a global
band. `FINANCIALS` drops Section III entirely (debt/EV metrics meaningless for banks); its 0.00
weight renormalizes onto I/II/IV.

| Profile | Sectors (yfinance) | I | II | III | IV | P (ND/EBITDA) | Q (ND/FCF) |
|---|---|---|---|---|---|---|---|
| TECH_GROWTH | Technology | 0.35 | 0.30 | 0.15 | 0.20 | 2.5 | 3 |
| BALANCED *(default)* | Consumer Cyclical, Healthcare, Communication Services, unknown/blank | 0.30 | 0.30 | 0.20 | 0.20 | 2.5 | 3 |
| DEFENSIVE_INCOME | Utilities, Consumer Defensive | 0.15 | 0.25 | 0.35 | 0.25 | 4.5 | 6 |
| INDUSTRIAL_CYCLICAL | Industrials, Basic Materials, Energy | 0.25 | 0.30 | 0.30 | 0.15 | 3.0 | 4 |
| FINANCIALS | Financial Services | 0.35 | 0.40 | 0.00 | 0.25 | — (skip) | — (skip) |
| REIT | Real Estate | 0.30 | 0.20 | 0.25 | 0.25 | 6.5 | 8 |

**Sector-relative leverage sub-score** (applied to both Net Debt/EBITDA with pivot `P` and Net
Debt/FCF with pivot `Q`; let `r` be the ratio, `V` the pivot):
```
r <= 0 (net cash) → 10
0 < r <= 0.5V     → 9
0.5V < r <= V     → 7     (comfortable up to the sector pivot)
V < r <= 1.4V     → 4.5
1.4V < r <= 1.8V  → 2
r > 1.8V          → 0
```
So a utility (`P=4.5`) at 4.5× scores 7; at 7× scores ~2. A tech firm (`P=2.5`) at 4.5× scores ~2.
Section III now *discriminates* within a sector instead of blanket-penalizing it.

**Sector string handling:** normalize (trim, case-insensitive) and match against the canonical
set above; anything unrecognized or blank → `BALANCED` (the least-opinionated profile). The raw
`sector` and the final applied profile are both stored on the result (§6) for transparency.

#### 5.3.2 Deterministic metric nudge (own data can correct a wrong/heterogeneous label)
After the sector selects a **base** profile, the company's own metrics may override it. Fully
deterministic; the base profile, the trigger, and the final profile are all recorded:
1. **Growth override** — if base is `BALANCED` **and** Revenue CAGR 3Y ≥ 15% **and** net cash
   (Net Debt < 0) → switch to `TECH_GROWTH`. Fixes heterogeneous Communication Services
   (GOOGL/META land on growth weighting; levered telecoms stay on BALANCED) and mislabeled growth.
2. **Special-profile data-fit fallback** — if base is `FINANCIALS` or `REIT` but the data
   contradicts it (EBITDA present, positive, and material: EBITDA/Revenue ≥ 8%, **and** a
   normal Net Debt/EBITDA < 4) → fall back to `BALANCED`. Stops a wrong `Financial Services` /
   `Real Estate` label from silently distorting the score.

Nudges are applied in order; at most one fires.

#### 5.3.3 Composite
`composite_raw = Σ (section_score × sector_weight)` → 0–10, using the final profile's weights.

### 5.4 Cap rules & adjustments (applied after composite)
1. **Unprofitable Cap Rule** — if `Net Income < 0` OR `FCF < 0`:
   - Cap composite at **8.0**.
   - Compute **Rule of 40** = revenue growth % + FCF margin % (fallback operating margin %), and
     **Cash Runway (months)** = `totalCash` / monthly burn, where monthly burn =
     `abs(min(FCF, 0)) / 12` (companies with positive FCF have effectively infinite runway).
   - **Elite** (Rule of 40 ≥ 40 AND runway ≥ 24) → keep capped score (≤ 8.0), floor 7.0.
   - **Fails** (Rule of 40 < 40 OR runway < 12) → force `min(score, 5.0)`.
2. **Balance-Sheet Dual-Check** — when Net Debt/FCF scores far worse than Net Debt/EBITDA AND
   `Net Debt/EBITDA < 2.5`, treat the FCF-based debt metric as noise from a capex cycle: use the
   EBITDA-based sub-score as the debt-safety component of Section III (prevents false negatives).

**Final:** round to 1 decimal, clamp to **[1.0, 10.0]**.

### 5.5 Insufficient data
If fewer than a minimum number of scored metrics are available (e.g. `< 6`, or income statement
missing entirely), `ScreenerResult.status = "failed"` with a reason; `quality_score = None`.
This is independent of the Fair Value pipeline — FV may still succeed for the same ticker.

## 6. Persistence (Google Sheets)

### New "Screener" tab (full detail, keyed by Ticker)
Columns: `Ticker, Company, Last Evaluated, Quality Score, Sector, Sector Profile (applied),
Section I Score, Section II Score, Section III Score, Section IV Score`, then all Section I–V
metric values (~35 columns). Storing both the raw `Sector` and the **applied** profile (which may
differ from the base after a §5.3.2 nudge) makes the weighting auditable. Upsert semantics identical to the existing Database tab
(find-by-ticker → append or overwrite). Tab auto-created if missing (mirrors
`_ensure_database_sheet`).

### "Database" tab mirror
Append **one** column: `Quality Score` (column Q). Update `_DB_HEADERS`, the read range
(`A:P` → `A:Q`), and `_read_database_sync`. The Fair Value columns are otherwise untouched.

### Read paths (the mirror avoids a join for the grid)
Because the Quality Score is mirrored into the Database tab, the **summary grid reads only the
Database tab** — `_read_database_sync` reads `A:Q` and returns a **grid DTO** (`DatabaseRow`) =
Fair Value fields + `quality_score`. No cross-tab join is needed for the grid. The **full**
Screener detail (all metrics + section scores) is read from the Screener tab via
`services/screener_sheets.py` `read_screener()` / `read_screener_one(ticker)`, used only by the
detail endpoint. `upsert_screener_result()` writes the Screener tab **and** mirrors the score to
Database column Q. Domain types (`TickerResult`, `ScreenerResult`) stay isolated; `DatabaseRow`
is a thin read-side view type.

## 7. Orchestration & API

### Batch — run both pipelines in parallel
`orchestrator/batch.py`: for each ticker in a group, `asyncio.gather(valuation.engine.run(t),
screener.engine.run(t))`; upsert each result to its own tab; emit a combined `ticker_done` event
carrying both results. Existing `BATCH_SIZE` grouping and cancellation preserved. A failure in one
pipeline does not fail the other.

### Endpoints (`routers/analysis.py`, `routers/database.py`)
| Endpoint | Behavior |
|---|---|
| `POST /api/analyse` | **Unchanged trigger, new behavior:** one job runs **both** pipelines for all tickers. |
| `GET /api/stream/{job_id}` | SSE now streams combined per-ticker results (FV + screener). |
| `POST /api/ticker/{ticker}/recalculate` | **NEW.** Re-run **both** pipelines for one ticker; upsert; return the combined `DatabaseRow`. Powers the per-row grid button. |
| `POST /api/recalculate-all` | **NEW.** Read all tickers from the Database tab, start a batch job (both pipelines), return `job_id`. Powers the top-of-grid button; streams like `/analyse`. |
| `GET /api/database` | Returns joined `DatabaseRow[]` (FV + quality score). |
| `GET /api/screener/{ticker}` | **NEW.** Full `ScreenerResult` (all metrics + section scores) for the detail tab. |

## 8. Frontend

- **Nav** unchanged (Analyse, Database).
- **Analyse (Home):** unchanged input; one run triggers both pipelines.
- **Results / TickerDetail:** add a **tabbed view — `Fair Value | Screener`**. The Screener tab
  shows the big Quality Score, the four section sub-scores, and the full Section I–V metrics table
  with threshold-band color coding (green/amber/red per band).
- **Database grid (`Database.tsx`):**
  - New **Quality Score** column, color-coded by band.
  - **Per-row `↻` button** → `POST /api/ticker/{ticker}/recalculate`; row shows a spinner, then
    refreshes in place.
  - **Top-of-grid "Recalculate All" button** → `POST /api/recalculate-all`; navigates to the
    progress view (or inline progress) and refreshes on completion.
- **`types.ts`:** add `ScreenerResult`, `ScreenerMetrics`; extend the grid row type with
  `quality_score`. Add a `qualityScoreColor(score)` helper (mirrors `fvGapColor`).

## 9. Error Handling & Degradation
- Missing individual metric → excluded from its section (renormalized).
- Missing whole statement set → screener `status="failed"` with reason; FV unaffected; grid shows
  FV columns with a blank Quality Score.
- yfinance rate limits → handled by the existing retry/backoff in the shared cached fetchers.
- `^TNX` unavailable → WACC/owner-earnings fall back to a hard-coded risk-free default (e.g. 4.3%),
  flagged in `errors`.
- Financials sector → FINANCIALS profile; debt/EV metrics scored but flagged as low-confidence.

## 10. Testing Strategy
- **`metrics`**: CAGR (incl. missing-endpoint None), ROIC/NOPAT, WACC, margin trajectory,
  shareholder yield — against synthetic statement fixtures.
- **`scoring`**: each threshold band boundary, section rollup + renormalization, sector-profile
  selection, Unprofitable Cap Rule (elite vs fail), Balance-Sheet Dual-Check, final clamp,
  insufficient-data path.
- **`engine`**: `screener.engine.run` smoke test with mocked inputs.
- **`screener_sheets`**: row serialization/round-trip (mirrors `test_sheets_row.py`).
- **Isolation regression:** existing Fair Value tests remain green and untouched.

## 11. Open Questions / Future Work
- Threshold bands, sector weights, and leverage pivots (`P`/`Q`) are **v1** and tunable;
  calibrate against a basket of known-good/known-bad names per sector after first run.
- Financials scoring is approximate (Section III dropped; debt/EV metrics weak for banks) —
  possible dedicated financial-institution metric set later.
- REIT scoring leans on distorted GAAP metrics (FFO/AFFO not modeled); flagged low-confidence.
  A future FFO-based REIT path is possible.
- The metric nudge (§5.3.2) is a targeted heuristic for the common mislabel/heterogeneity cases,
  not a general classifier; the stored applied-profile makes any surprise auditable.
- "5Y" CAGRs limited to the available statement span; a future paid data source could extend it.
- Optional later: expose the per-metric threshold band a value fell into, for explainability.
