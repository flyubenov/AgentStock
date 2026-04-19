# Stock Ticker Evaluation Web App — Design Spec
**Date:** 2026-04-20
**Status:** Approved
**Source PRD:** `StockApp_PRD_v1.0.docx`

---

## 1. Overview

An AI-powered stock analysis platform that runs 9 agents simultaneously (6 scoring + 3 fair value) against any set of tickers, consolidates results into an Overall Final Score and Blended Fair Value, and persists all results to Google Sheets. Runs locally on a single machine.

---

## 2. Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite + TypeScript + Tailwind CSS + shadcn/ui |
| Backend | Python 3.x + FastAPI + uvicorn |
| AI Agents | Anthropic Claude API (`claude-opus-4-6`) with `web_search_20250305` tool |
| Financial Data | yfinance (Yahoo Finance) — primary; Alpha Vantage / FMP free tier as fallback |
| Persistent Storage | Google Sheets API v4 (service account auth) |
| Real-time Updates | Server-Sent Events (SSE) |
| UI Theme | Dark, Bloomberg-lite, monospace numbers, colour-coded score badges |

---

## 3. Project Structure

```
Agent Stock/
├── backend/
│   ├── main.py                    # FastAPI app, CORS, SSE endpoint
│   ├── requirements.txt
│   ├── .env                       # ANTHROPIC_API_KEY, GOOGLE_SHEETS_CREDS_PATH, GOOGLE_SHEETS_ID
│   ├── agents/
│   │   ├── base_agent.py          # BaseAgent: API client, retry logic, parsing scaffold
│   │   ├── buffett_munger.py
│   │   ├── lynch_garp.py
│   │   ├── growth_stock.py
│   │   ├── business_engine.py
│   │   ├── canslim.py
│   │   └── pre_screener.py
│   ├── prompts/                   # Agent system prompts as .md files
│   │   ├── buffett_munger.md
│   │   ├── lynch_garp.md
│   │   ├── growth_stock.md
│   │   ├── business_engine.md
│   │   ├── canslim.md
│   │   └── pre_screener.md
│   ├── valuation/
│   │   ├── gemini_fv.py           # Revised Graham + P/E + EV/EBITDA
│   │   ├── calculator_1.py        # DCF + EV/EBITDA + P/E + P/FCF + DDM (scenario-based)
│   │   └── calculator_2.py        # DCF/WACC + P/E + EV/EBITDA + EV/Sales + PEG + RIM/EVA
│   ├── services/
│   │   ├── yahoo.py               # Async yfinance wrapper
│   │   ├── sheets.py              # Google Sheets read (tickers) + upsert (DB)
│   │   └── normalizer.py          # Score normalisation formulas + Pre-Screener derived score
│   ├── orchestrator/
│   │   ├── batch.py               # Batch partitioning (10/group), semaphore, queue
│   │   └── aggregator.py          # Overall Final Score, Blended Fair Value, FV gap %
│   └── routers/
│       ├── analysis.py            # POST /api/analyse, GET /api/stream/{job_id}
│       └── database.py            # GET /api/database
└── frontend/
    ├── package.json
    └── src/
        ├── pages/
        │   ├── Home.tsx
        │   ├── Progress.tsx
        │   ├── Results.tsx
        │   ├── TickerDetail.tsx
        │   └── Database.tsx
        ├── components/
        │   ├── ScoreBadge.tsx
        │   ├── AgentCard.tsx
        │   ├── FairValuePanel.tsx
        │   └── ProgressBar.tsx
        ├── hooks/
        │   └── useAnalysisStream.ts
        └── types.ts
```

---

## 4. Agent Architecture

### 4.1 Analysis Agents (6 — Claude API)

All six agents extend `BaseAgent`:

```python
class BaseAgent:
    model = "claude-opus-4-6"
    max_tokens = 4000  # 2000–4000 per agent based on expected output
    tools = [{"type": "web_search_20250305", "name": "web_search"}]

    def load_prompt(self) -> str          # reads prompts/<agent>.md
    async def run(self, ticker: str) -> AgentResult
    def parse_score(self, response: str) -> tuple[float | None, str | None]
    # retry: 3 attempts, exponential back-off (2s base, ×2, max 30s)
```

Each agent's system prompt is loaded from `prompts/<agent>.md`, ported from the original Gemini Gem definitions in the PRD. Agents use `web_search` for all real-time financial data retrieval — no static data injection.

| Agent | Score Scale | Normalisation | Recommendation Output |
|-------|------------|---------------|----------------------|
| Buffett-Munger Value Analyst | 1–5 | Direct | STRONG BUY / BUY / WATCHLIST / PASS |
| Lynch GARP Analyst | 1–5 | Direct | BUY / HOLD / SELL |
| Growth Stock Analyzer | 0–100 | `(score / 100) × 5` | Excellent / Good / Uncertain / Speculative |
| Business Engine Analyst | 1–5 | Direct | Business grade + Red Flag |
| CANSLIM Stock Analyzer Pro | 7–35 | `((score − 7) / 28) × 4 + 1` | BUY / HOLD / SELL |
| Stock Pre-Screener | Derived 1–5 | Direct (after derivation) | BUY / HOLD / SELL + Growth Potential |

**Pre-Screener derived scoring:**
1. Map recommendation: BUY = 5, HOLD = 3, SELL = 1
2. Apply Growth Potential modifier: High = +0, Moderate = −0.5, Low = −1.0
3. Apply Financial State modifier: Bad = −0.5, otherwise 0
4. Clamp result to [1, 5]

### 4.2 Fair Value Scripts (3 — Python + yfinance)

Each script is both a callable module and a CLI tool:

```python
# Module usage (orchestrator): await gemini_fv.run("AAPL") → FairValueResult
# CLI usage (standalone test):  python gemini_fv.py --ticker AAPL  → JSON stdout
```

All three apply 10% MOS. Output schema:
```json
{
  "ticker": "AAPL",
  "method_name": "...",
  "pre_mos_value": 210.50,
  "post_mos_value": 189.45,
  "methods_breakdown": {...},
  "data_sources": ["yfinance"]
}
```

| Script | Methods |
|--------|---------|
| `gemini_fv.py` | Revised Graham Formula, P/E Multiples, EV/EBITDA |
| `calculator_1.py` | DCF (40–45%), EV/EBITDA (20–25%), P/E (15%), P/FCF (10–15%), DDM (15% if yield ≥1.5%); Optimistic / Realistic / Pessimistic scenarios |
| `calculator_2.py` | DCF with WACC stress-test, P/E, EV/EBITDA, EV/Sales, PEG (vs. peers), Capital-Return Profile, Residual Income / EVA |

---

## 5. Data Flow

### Single ticker:
```
submit ticker
  └─► validate ticker (yfinance lookup — reject unknowns)
  └─► orchestrator spawns 9 coroutines concurrently (asyncio.gather)
        ├─ 6 × BaseAgent.run(ticker)         → Claude API + web_search
        └─ 3 × valuation_script.run(ticker)  → yfinance → math
  └─► aggregator.normalise_scores()          → all 6 scores to 1–5
  └─► aggregator.compute_overall()           → simple average, round 2dp, apply label
  └─► aggregator.compute_blended_fv()        → avg of 3 post-MOS values
  └─► aggregator.compute_fv_gap()            → (blended_fv − price) / price × 100
  └─► sheets.upsert(ticker, result)          → Google Sheets DB write
  └─► SSE event emitted to frontend
```

### Batch (up to 150 tickers):
- Partition tickers into groups of 10 (configurable via `BATCH_SIZE` env var)
- Groups processed sequentially; within each group all 10 tickers run concurrently
- `asyncio.Semaphore(5)` caps simultaneous Claude API calls (configurable via `MAX_CONCURRENT_LLM_CALLS`)
- Failed tickers: marked `status: "failed"`, excluded from batch, never block progress
- Google Sheets batch write: all results accumulated, flushed with single `values.batchUpdate` per ticker completion

---

## 6. Google Sheets Integration

**Auth:** Service account JSON key. Path stored in `.env` as `GOOGLE_SHEETS_CREDS_PATH`. Sheet ID stored as `GOOGLE_SHEETS_ID`. Scope: `https://www.googleapis.com/auth/spreadsheets`.

**Sheet tabs:**

| Tab | Purpose | Operation |
|-----|---------|-----------|
| `Tickers` | Input source — column A contains ticker symbols | Read-only on job start |
| `Database` | Persistent evaluation history | Upsert (match Ticker col, overwrite or append) |

**Database schema — full column set:**

| Column | Type | Notes |
|--------|------|-------|
| Ticker | String | Primary key |
| Company Name | String | |
| Last Evaluated | Timestamp | ISO 8601 |
| Buffett-Munger Score | Float (1–5) | Normalised |
| Lynch GARP Score | Float (1–5) | Normalised |
| Growth Analyzer Score | Float (1–5) | Normalised |
| Business Engine Score | Float (1–5) | Normalised |
| CANSLIM Score | Float (1–5) | Normalised |
| Pre-Screener Score | Float (1–5) | Derived + normalised |
| Overall Final Score | Float (1–5) | Average of 6 agent scores |
| Fair Value — Gemini | Float (USD) | Post-MOS |
| Fair Value — Calculator 1 | Float (USD) | Post-MOS weighted blend |
| Fair Value — Calculator 2 | Float (USD) | Post-MOS blended average |
| Blended Fair Value | Float (USD) | Average of 3 FV values |
| Current Price at Eval | Float (USD) | |
| Price vs Fair Value % | Float (%) | Positive = undervalued |

---

## 7. Frontend UI

**Theme:** Dark background, monospace numbers, colour-coded score badges, data-dense tables. shadcn/ui components with Tailwind CSS.

### Pages

**Home** — ticker input (comma-separated) and/or Google Sheets URL field. "Analyse" CTA → `POST /api/analyse` → redirect to Progress with `job_id`.

**Progress** — SSE-driven live view:
- Overall bar: `Analysed 42 / 150 tickers`
- Per-ticker status chips: `queued → running → done / failed`
- Preview results table populates as tickers complete
- Cancel button

**Results** — sortable/filterable table:
- Columns: Ticker, Company, Overall Score (badge), Buffett-Munger, Lynch GARP, Growth Analyzer, Business Engine, CANSLIM, Pre-Screener, Blended FV, Current Price, FV Gap %, Last Evaluated
- Click row → Ticker Detail
- CSV export button

**Ticker Detail** — full breakdown:
- Header: company, ticker, price, overall score badge, timestamp
- Agent Score Summary table (all 6 scores + recommendations)
- Fair Value panel: per-method pre-MOS + post-MOS values, blended average, price gap %
- Collapsible agent sections: full qualitative report, scorecard tables, metric breakdowns
- Historical note if ticker existed in DB before this run

**Database Viewer** — same table as Results, loaded from `GET /api/database`. Re-run button per row. Read-only otherwise. Link to Google Sheets source.

### Score Badge Colours

| Range | Label | Colour |
|-------|-------|--------|
| 4.5–5.0 | Strong Buy | Green |
| 3.5–4.4 | Buy | Blue |
| 2.5–3.4 | Hold / Watch | Yellow |
| 1.5–2.4 | Underperform | Orange |
| 1.0–1.4 | Sell / Avoid | Red |

### Key UI Behaviours
- `TickerResult` TypeScript type is the single source of truth for both live SSE data and DB-loaded data — UI rendering is identical for both paths
- Loading skeletons while analysis runs
- Per-ticker inline error messages for failures
- Responsive: desktop (1280px+) and tablet (768px+)
- Financial disclaimer footer on all pages

---

## 8. Error Handling

| Failure | Behaviour |
|---------|-----------|
| Invalid ticker | Rejected before queuing with per-ticker error message |
| Single agent fails | Score = `null`, excluded from average, ticker marked `Partial` |
| All agents fail for ticker | Ticker marked `Failed`, shown inline with error |
| yfinance returns no data | Fair value script returns `null` values, logs warning |
| Claude API rate limit | Exponential back-off (2s base, ×2, max 30s), 3 retries, then fail agent |
| Score parsing fails | `parse_score` returns `null`, raw response logged |
| Google Sheets write fails | Retry once, log error — analysis result still returned to UI |

`asyncio.Semaphore(5)` prevents rate limit storms on Claude API. Configurable via `MAX_CONCURRENT_LLM_CALLS`.

---

## 9. Testing Strategy

| Layer | Approach |
|-------|----------|
| Valuation scripts | Unit tests with fixed yfinance fixtures — verify DCF, Graham, EV/EBITDA math |
| Score normalisation | Unit tests for all 6 formulas + Pre-Screener derived scoring edge cases |
| Agent score parsing | Unit tests with sample LLM response strings per agent regex parser |
| Orchestrator | Integration test: single ticker end-to-end with mocked Claude API + real yfinance |
| Sheets service | Integration test against test Google Sheet with known data |
| API routes | FastAPI `TestClient` for `/api/analyse` and `/api/database` |

---

## 10. Configuration (.env)

```
ANTHROPIC_API_KEY=...
GOOGLE_SHEETS_CREDS_PATH=./credentials/service_account.json
GOOGLE_SHEETS_ID=...
BATCH_SIZE=10
MAX_CONCURRENT_LLM_CALLS=5
```

---

## 11. Development Milestones (from PRD)

| Phase | Deliverables | Target |
|-------|-------------|--------|
| 1 | 3 fair value scripts, yfinance integration, JSON output, unit tests | Week 1–2 |
| 2 | 6 Claude agents, system prompts ported from Gemini Gems, score parsers, BaseAgent | Week 3–4 |
| 3 | Batch queue, async parallel execution, rate limiting, score normalisation, aggregation | Week 5 |
| 4 | Google Sheets read (ticker input) + write (DB upsert), batch write optimisation | Week 6 |
| 5 | Frontend: Home, Progress, Results, Ticker Detail, Database Viewer, CSV export | Week 7–8 |
| 6 | End-to-end tests (150-ticker batch), error handling, disclaimer copy, final polish | Week 9–10 |

---

*All outputs are for informational and educational purposes only and do not constitute investment advice.*
