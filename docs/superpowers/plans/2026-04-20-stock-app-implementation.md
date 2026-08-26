# Stock Ticker Evaluation App — Implementation Plan
**Date:** 2026-04-20
**Goal:** Build an AI-powered stock analysis platform from scratch with 6 Claude scoring agents + 3 fair value scripts, live SSE progress, and Google Sheets persistence.
**Design spec:** `docs/superpowers/specs/2026-04-20-stock-app-design.md`

---

## Architecture Summary

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Vite + TypeScript + Tailwind CSS + shadcn/ui |
| Backend | Python 3.11+ + FastAPI + uvicorn |
| AI Agents | Anthropic Claude API (`claude-opus-4-6`) with `web_search_20250305` |
| Financial Data | yfinance (Yahoo Finance) |
| Persistence | Google Sheets API v4 (service account) |
| Real-time | Server-Sent Events (SSE) |

---

## File Structure

```
Agent Stock/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── .env
│   ├── credentials/
│   │   └── service_account.json          ← user provides
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py
│   │   ├── buffett_munger.py
│   │   ├── lynch_garp.py
│   │   ├── growth_stock.py
│   │   ├── business_engine.py
│   │   ├── canslim.py
│   │   └── pre_screener.py
│   ├── prompts/
│   │   ├── buffett_munger.md
│   │   ├── lynch_garp.md
│   │   ├── growth_stock.md
│   │   ├── business_engine.md
│   │   ├── canslim.md
│   │   └── pre_screener.md
│   ├── valuation/
│   │   ├── __init__.py
│   │   ├── gemini_fv.py
│   │   ├── calculator_1.py
│   │   └── calculator_2.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── yahoo.py
│   │   ├── sheets.py
│   │   └── normalizer.py
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── batch.py
│   │   └── aggregator.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── analysis.py
│   │   └── database.py
│   └── models.py
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── tailwind.config.ts
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── types.ts
        ├── lib/
        │   └── utils.ts
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
        │   ├── ProgressBar.tsx
        │   └── Layout.tsx
        └── hooks/
            └── useAnalysisStream.ts
```

---

## Phase 1 — Backend Scaffolding

### Task 1 — Python project scaffold + requirements

**Files:** `backend/requirements.txt`, `backend/.env`, `backend/main.py`, `backend/models.py`

- [ ] Create `backend/requirements.txt`:

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
python-dotenv==1.0.1
anthropic==0.40.0
yfinance==0.2.54
google-auth==2.35.0
google-api-python-client==2.147.0
sse-starlette==2.1.3
pydantic==2.9.2
httpx==0.27.2
```

- [ ] Create `backend/.env`:

```
ANTHROPIC_API_KEY=your_key_here
GOOGLE_SHEETS_CREDS_PATH=./credentials/service_account.json
GOOGLE_SHEETS_ID=your_sheet_id_here
BATCH_SIZE=10
MAX_CONCURRENT_LLM_CALLS=5
```

- [ ] Create `backend/models.py`:

```python
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel


class AgentResult(BaseModel):
    agent_name: str
    ticker: str
    raw_score: float | None = None
    normalised_score: float | None = None
    recommendation: str | None = None
    raw_response: str = ""
    report: str = ""
    status: Literal["completed", "failed"] = "completed"
    error: str | None = None


class FairValueResult(BaseModel):
    ticker: str
    method_name: str
    pre_mos_value: float | None = None
    post_mos_value: float | None = None
    methods_breakdown: dict = {}
    data_sources: list[str] = []
    status: Literal["completed", "failed"] = "completed"
    error: str | None = None


class TickerResult(BaseModel):
    ticker: str
    company_name: str | None = None
    current_price: float | None = None
    last_evaluated: str | None = None
    buffett_munger_score: float | None = None
    lynch_garp_score: float | None = None
    growth_analyzer_score: float | None = None
    business_engine_score: float | None = None
    canslim_score: float | None = None
    pre_screener_score: float | None = None
    overall_final_score: float | None = None
    overall_label: str | None = None
    fair_value_gemini: float | None = None
    fair_value_calculator_1: float | None = None
    fair_value_calculator_2: float | None = None
    blended_fair_value: float | None = None
    price_vs_fair_value_pct: float | None = None
    agent_results: dict[str, AgentResult] = {}
    fair_value_results: dict[str, FairValueResult] = {}
    status: Literal["completed", "partial", "failed"] = "completed"
    errors: list[str] = []


class AnalyseRequest(BaseModel):
    tickers: list[str] = []
    sheets_url: str | None = None


class JobStatus(BaseModel):
    job_id: str
    total: int
    completed: int
    failed: int
    status: Literal["running", "completed", "failed", "cancelled"]
    results: list[TickerResult] = []
```

- [ ] Create `backend/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers.analysis import router as analysis_router
from routers.database import router as database_router

load_dotenv()

app = FastAPI(title="Stock Ticker Evaluation App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router, prefix="/api")
app.include_router(database_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] Create all `__init__.py` files:

```bash
touch backend/agents/__init__.py backend/valuation/__init__.py backend/services/__init__.py backend/orchestrator/__init__.py backend/routers/__init__.py
```

- [ ] Install dependencies:

```bash
cd backend && pip install -r requirements.txt
```

**Expected:** `Successfully installed fastapi-0.115.0 uvicorn-...` (no errors)

- [ ] Smoke test:

```bash
cd backend && uvicorn main:app --reload --port 8000
# In another terminal:
curl http://localhost:8000/api/health
# Expected: {"status":"ok"}
```

**Commit:** `feat: backend scaffold — FastAPI app, models, requirements`

---

### Task 2 — Frontend scaffold (Vite + React + Tailwind + shadcn/ui)

**Files:** `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tailwind.config.ts`, `frontend/src/main.tsx`, `frontend/src/App.tsx`

- [ ] Scaffold Vite project:

```bash
cd "Agent Stock"
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
```

- [ ] Install Tailwind CSS:

```bash
npm install -D tailwindcss@3 postcss autoprefixer
npx tailwindcss init -p
```

- [ ] Install shadcn/ui dependencies:

```bash
npm install class-variance-authority clsx tailwind-merge lucide-react
npm install @radix-ui/react-slot @radix-ui/react-dialog @radix-ui/react-dropdown-menu @radix-ui/react-tooltip
npm install react-router-dom
```

- [ ] Replace `frontend/tailwind.config.ts`:

```typescript
import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      colors: {
        bg: {
          primary: '#0a0a0f',
          secondary: '#111118',
          card: '#16161e',
          border: '#1e1e2a',
        },
        accent: {
          blue: '#3b82f6',
          green: '#22c55e',
          yellow: '#eab308',
          orange: '#f97316',
          red: '#ef4444',
        },
      },
    },
  },
  plugins: [],
} satisfies Config
```

- [ ] Replace `frontend/src/index.css` (global styles):

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
  color-scheme: dark;
}

body {
  background-color: #0a0a0f;
  color: #e2e8f0;
  font-family: 'JetBrains Mono', monospace;
  margin: 0;
}

* {
  box-sizing: border-box;
}
```

- [ ] Create `frontend/src/lib/utils.ts`:

```typescript
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

- [ ] Replace `frontend/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Progress from './pages/Progress'
import Results from './pages/Results'
import TickerDetail from './pages/TickerDetail'
import Database from './pages/Database'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/progress/:jobId" element={<Progress />} />
          <Route path="/results/:jobId" element={<Results />} />
          <Route path="/ticker/:jobId/:ticker" element={<TickerDetail />} />
          <Route path="/database" element={<Database />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
```

- [ ] Replace `frontend/src/main.tsx`:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] Smoke test:

```bash
cd frontend && npm run dev
# Expected: VITE v5.x.x  ready in xxx ms — http://localhost:5173/
```

**Commit:** `feat: frontend scaffold — Vite, React, TypeScript, Tailwind, shadcn/ui deps`

---

## Phase 2 — Shared Types + Frontend Type Definitions

### Task 3 — TypeScript types

**Files:** `frontend/src/types.ts`

- [ ] Create `frontend/src/types.ts`:

```typescript
export interface AgentResult {
  agent_name: string
  ticker: string
  raw_score: number | null
  normalised_score: number | null
  recommendation: string | null
  raw_response: string
  report: string
  status: 'completed' | 'failed'
  error: string | null
}

export interface FairValueResult {
  ticker: string
  method_name: string
  pre_mos_value: number | null
  post_mos_value: number | null
  methods_breakdown: Record<string, unknown>
  data_sources: string[]
  status: 'completed' | 'failed'
  error: string | null
}

export interface TickerResult {
  ticker: string
  company_name: string | null
  current_price: number | null
  last_evaluated: string | null
  buffett_munger_score: number | null
  lynch_garp_score: number | null
  growth_analyzer_score: number | null
  business_engine_score: number | null
  canslim_score: number | null
  pre_screener_score: number | null
  overall_final_score: number | null
  overall_label: string | null
  fair_value_gemini: number | null
  fair_value_calculator_1: number | null
  fair_value_calculator_2: number | null
  blended_fair_value: number | null
  price_vs_fair_value_pct: number | null
  agent_results: Record<string, AgentResult>
  fair_value_results: Record<string, FairValueResult>
  status: 'completed' | 'partial' | 'failed'
  errors: string[]
}

export interface JobStatus {
  job_id: string
  total: number
  completed: number
  failed: number
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  results: TickerResult[]
}

export type ScoreLabel = 'Strong Buy' | 'Buy' | 'Hold / Watch' | 'Underperform' | 'Sell / Avoid'

export function scoreToLabel(score: number | null): ScoreLabel | null {
  if (score == null) return null
  if (score >= 4.5) return 'Strong Buy'
  if (score >= 3.5) return 'Buy'
  if (score >= 2.5) return 'Hold / Watch'
  if (score >= 1.5) return 'Underperform'
  return 'Sell / Avoid'
}

export function scoreToColor(score: number | null): string {
  if (score == null) return 'text-slate-400'
  if (score >= 4.5) return 'text-green-500'
  if (score >= 3.5) return 'text-blue-500'
  if (score >= 2.5) return 'text-yellow-500'
  if (score >= 1.5) return 'text-orange-500'
  return 'text-red-500'
}

export function scoreToBgColor(score: number | null): string {
  if (score == null) return 'bg-slate-800 text-slate-300'
  if (score >= 4.5) return 'bg-green-900/40 text-green-400 border border-green-700'
  if (score >= 3.5) return 'bg-blue-900/40 text-blue-400 border border-blue-700'
  if (score >= 2.5) return 'bg-yellow-900/40 text-yellow-400 border border-yellow-700'
  if (score >= 1.5) return 'bg-orange-900/40 text-orange-400 border border-orange-700'
  return 'bg-red-900/40 text-red-400 border border-red-700'
}
```

**Commit:** `feat: shared TypeScript types — TickerResult, AgentResult, FairValueResult`

---

## Phase 3 — Fair Value Scripts

### Task 4 — Yahoo Finance service

**Files:** `backend/services/yahoo.py`

- [ ] Create `backend/services/yahoo.py`:

```python
import asyncio
import yfinance as yf
from functools import lru_cache


async def fetch_ticker_info(ticker: str) -> dict:
    """Async wrapper around yfinance Ticker.info."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_sync, ticker)


def _fetch_sync(ticker: str) -> dict:
    t = yf.Ticker(ticker)
    info = t.info or {}
    if not info.get("symbol") and not info.get("shortName"):
        raise ValueError(f"Ticker '{ticker}' not found or returned no data")
    return info


def extract_financials(info: dict) -> dict:
    """Normalise yfinance info dict to the fields our valuation scripts need."""
    return {
        "ticker": info.get("symbol", ""),
        "company_name": info.get("shortName") or info.get("longName"),
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap": info.get("marketCap"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "fcf_ttm": info.get("freeCashflow"),
        "net_debt": _net_debt(info),
        "ebitda_ttm": info.get("ebitda"),
        "eps_ttm": info.get("trailingEps"),
        "revenue_ttm": info.get("totalRevenue"),
        "book_value_per_share": info.get("bookValue"),
        "dividend_rate": info.get("dividendRate"),
        "dividend_yield": info.get("dividendYield") or 0,
        "payout_ratio": info.get("payoutRatio") or 0,
        "return_on_equity": info.get("returnOnEquity"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "revenue_growth": info.get("revenueGrowth") or 0,
        "earnings_growth": info.get("earningsGrowth"),
        "sector": info.get("sector", ""),
        "industry": info.get("industry", ""),
        "long_business_summary": info.get("longBusinessSummary", ""),
        "interest_expense": info.get("interestExpense"),
        "effective_tax_rate": info.get("effectiveTaxRate"),
        "cost_of_equity": None,
    }


def _net_debt(info: dict) -> float:
    total_debt = info.get("totalDebt") or 0
    cash = info.get("totalCash") or 0
    return total_debt - cash


async def validate_ticker(ticker: str) -> bool:
    try:
        info = await fetch_ticker_info(ticker)
        return bool(info.get("symbol") or info.get("shortName"))
    except Exception:
        return False
```

- [ ] Test:

```bash
cd backend && python -c "
import asyncio
from services.yahoo import fetch_ticker_info, extract_financials
info = asyncio.run(fetch_ticker_info('AAPL'))
fin = extract_financials(info)
print('Company:', fin['company_name'])
print('Price:', fin['current_price'])
print('FCF:', fin['fcf_ttm'])
"
# Expected: Company: Apple Inc., Price: <number>, FCF: <number>
```

**Commit:** `feat: Yahoo Finance async service`

---

### Task 5 — Gemini FV script (Revised Graham + P/E + EV/EBITDA)

**Files:** `backend/valuation/gemini_fv.py`

- [ ] Create `backend/valuation/gemini_fv.py`:

```python
"""
Fair value via: Revised Graham Formula, P/E Multiples, EV/EBITDA.
Weights: Graham 40%, P/E 30%, EV/EBITDA 30%. MOS: 10%.
"""
from __future__ import annotations
import argparse, asyncio, json
from models import FairValueResult
from services.yahoo import fetch_ticker_info, extract_financials

MOS = 0.90
DISCOUNT_RATE = 0.10


def _graham(eps: float, growth_pct: float, aaa_yield: float = 4.4) -> float | None:
    """Revised Graham Formula: V = EPS × (8.5 + 2g) × (4.4 / Y)"""
    if eps <= 0:
        return None
    current_aaa = aaa_yield  # caller should pass current yield; default 4.4 as per original
    return eps * (8.5 + 2 * growth_pct) * (4.4 / current_aaa)


def _pe_fair_value(eps: float, sector_pe: float) -> float:
    return eps * sector_pe


def _ev_ebitda_fv(ebitda: float, multiple: float, net_debt: float, shares: float) -> float:
    return (ebitda * multiple - net_debt) / shares


async def run(ticker: str) -> FairValueResult:
    try:
        info = await fetch_ticker_info(ticker)
        fin = extract_financials(info)

        eps = fin["eps_ttm"]
        ebitda = fin["ebitda_ttm"]
        shares = fin["shares_outstanding"]
        net_debt = fin["net_debt"] or 0
        growth_rate = (fin["earnings_growth"] or fin["revenue_growth"] or 0.05) * 100
        trailing_pe = fin["trailing_pe"]
        forward_pe = fin["forward_pe"]

        breakdown: dict = {}
        values: list[float] = []

        # Graham
        if eps and eps > 0:
            g = min(max(growth_rate, 0), 20)
            graham_raw = _graham(eps, g)
            if graham_raw and graham_raw > 0:
                breakdown["graham"] = {"pre_mos": round(graham_raw, 2), "post_mos": round(graham_raw * MOS, 2)}
                values.append(graham_raw)

        # P/E multiples
        sector_pe = trailing_pe or forward_pe or 15.0
        if eps and eps > 0 and sector_pe and sector_pe > 0:
            pe_raw = _pe_fair_value(eps, min(sector_pe, 40))
            breakdown["pe_multiples"] = {"pre_mos": round(pe_raw, 2), "post_mos": round(pe_raw * MOS, 2)}
            values.append(pe_raw)

        # EV/EBITDA
        ev_ebitda_multiple = info.get("enterpriseToEbitda") or 12.0
        if ebitda and ebitda > 0 and shares and shares > 0 and ev_ebitda_multiple > 0:
            ev_raw = _ev_ebitda_fv(ebitda, ev_ebitda_multiple, net_debt, shares)
            if ev_raw > 0:
                breakdown["ev_ebitda"] = {"pre_mos": round(ev_raw, 2), "post_mos": round(ev_raw * MOS, 2)}
                values.append(ev_raw)

        if not values:
            return FairValueResult(
                ticker=ticker, method_name="Gemini FV",
                status="failed", error="Insufficient data for any sub-method",
                methods_breakdown={}, data_sources=["yfinance"],
            )

        pre_mos = sum(values) / len(values)
        post_mos = pre_mos * MOS

        return FairValueResult(
            ticker=ticker,
            method_name="Gemini FV",
            pre_mos_value=round(pre_mos, 2),
            post_mos_value=round(post_mos, 2),
            methods_breakdown=breakdown,
            data_sources=["yfinance"],
        )

    except Exception as e:
        return FairValueResult(
            ticker=ticker, method_name="Gemini FV",
            status="failed", error=str(e),
            methods_breakdown={}, data_sources=["yfinance"],
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    args = parser.parse_args()
    result = asyncio.run(run(args.ticker))
    print(json.dumps(result.model_dump(), indent=2))
```

- [ ] Test:

```bash
cd backend && python valuation/gemini_fv.py --ticker AAPL
# Expected: JSON with pre_mos_value and post_mos_value populated
```

**Commit:** `feat: Gemini FV script — Graham + P/E + EV/EBITDA`

---

### Task 6 — Calculator 1 (DCF + EV/EBITDA + P/E + P/FCF + DDM with scenarios)

**Files:** `backend/valuation/calculator_1.py`

- [ ] Create `backend/valuation/calculator_1.py`:

```python
"""
Calculator 1: DCF (40%), EV/EBITDA (25%), P/E (15%), P/FCF (15%), DDM (15% if yield≥1.5%).
Scenarios: Optimistic / Realistic / Pessimistic. MOS: 10%.
"""
from __future__ import annotations
import argparse, asyncio, json
from models import FairValueResult
from services.yahoo import fetch_ticker_info, extract_financials

MOS = 0.90
DISCOUNT_RATE = 0.10
TERMINAL_GROWTH = 0.03
HORIZON = 10


def pv(cf: float, rate: float, year: int) -> float:
    return cf / (1 + rate) ** year


def dcf_equity(fcf: float, growth: float, net_debt: float, shares: float) -> float:
    total = 0.0
    cf = fcf
    for t in range(1, HORIZON + 1):
        cf *= (1 + growth)
        total += pv(cf, DISCOUNT_RATE, t)
    tv = cf * (1 + TERMINAL_GROWTH) / (DISCOUNT_RATE - TERMINAL_GROWTH)
    total += pv(tv, DISCOUNT_RATE, HORIZON)
    return (total - net_debt) / shares


def ev_multiple(base: float, growth: float, multiple: float, net_debt: float, shares: float) -> float:
    projected = base * (1 + growth) ** HORIZON
    future_ev = projected * multiple
    return (future_ev - net_debt) / shares / (1 + DISCOUNT_RATE) ** HORIZON


def pe_justified(eps: float, growth: float, payout: float) -> float:
    capped = min(growth, DISCOUNT_RATE - 0.01)
    pe = payout / (DISCOUNT_RATE - capped) if capped > 0 else payout / DISCOUNT_RATE
    return eps * max(pe, 1)


def pfcf_value(fcf_per_share: float, growth: float, payout: float = 0.8) -> float:
    capped = min(growth, DISCOUNT_RATE - 0.01)
    multiple = payout / (DISCOUNT_RATE - capped) if capped > 0 else payout / DISCOUNT_RATE
    return fcf_per_share * max(multiple, 1)


def ddm(div: float, growth: float) -> float | None:
    capped = min(growth, DISCOUNT_RATE - 0.01)
    if DISCOUNT_RATE <= capped:
        return None
    return div * (1 + capped) / (DISCOUNT_RATE - capped)


def _scenarios(fin: dict) -> tuple[float, float, float]:
    base_growth = fin["earnings_growth"] or fin["revenue_growth"] or 0.07
    return (
        min(base_growth + 0.05, 0.30),   # optimistic
        base_growth,                       # realistic
        max(base_growth - 0.04, 0.01),    # pessimistic
    )


async def run(ticker: str) -> FairValueResult:
    try:
        info = await fetch_ticker_info(ticker)
        fin = extract_financials(info)

        fcf = fin["fcf_ttm"]
        shares = fin["shares_outstanding"]
        net_debt = fin["net_debt"] or 0
        ebitda = fin["ebitda_ttm"]
        eps = fin["eps_ttm"]
        payout = fin["payout_ratio"] or 0.40
        div_rate = fin["dividend_rate"]
        div_yield = fin["dividend_yield"] or 0
        ev_ebitda_m = info.get("enterpriseToEbitda") or 12.0
        trailing_pe = fin["trailing_pe"] or 15.0

        opt_g, real_g, pess_g = _scenarios(fin)
        breakdown: dict = {}
        scenario_values: dict[str, list[float]] = {"optimistic": [], "realistic": [], "pessimistic": []}
        weights_used: dict[str, float] = {}

        def add_method(name: str, weight: float, opt: float | None, real: float | None, pess: float | None):
            if any(v is not None and v > 0 for v in [opt, real, pess]):
                breakdown[name] = {
                    "weight": weight,
                    "optimistic": round(opt * MOS, 2) if opt else None,
                    "realistic": round(real * MOS, 2) if real else None,
                    "pessimistic": round(pess * MOS, 2) if pess else None,
                }
                weights_used[name] = weight
                for key, val in [("optimistic", opt), ("realistic", real), ("pessimistic", pess)]:
                    if val and val > 0:
                        scenario_values[key].append(val * weight)

        # DCF
        if fcf and shares and fcf > 0:
            add_method("dcf", 0.40,
                dcf_equity(fcf, opt_g, net_debt, shares),
                dcf_equity(fcf, real_g, net_debt, shares),
                dcf_equity(fcf, pess_g, net_debt, shares),
            )

        # EV/EBITDA
        if ebitda and shares and ebitda > 0:
            add_method("ev_ebitda", 0.25,
                ev_multiple(ebitda, opt_g, ev_ebitda_m, net_debt, shares),
                ev_multiple(ebitda, real_g, ev_ebitda_m, net_debt, shares),
                ev_multiple(ebitda, pess_g, ev_ebitda_m, net_debt, shares),
            )

        # P/E
        if eps and eps > 0:
            add_method("pe", 0.15,
                pe_justified(eps, opt_g, payout),
                pe_justified(eps, real_g, payout),
                pe_justified(eps, pess_g, payout),
            )

        # P/FCF
        if fcf and shares and fcf > 0:
            fcf_per_share = fcf / shares
            add_method("p_fcf", 0.15,
                pfcf_value(fcf_per_share, opt_g),
                pfcf_value(fcf_per_share, real_g),
                pfcf_value(fcf_per_share, pess_g),
            )

        # DDM (only if yield ≥ 1.5%)
        if div_rate and div_yield >= 0.015:
            add_method("ddm", 0.15,
                ddm(div_rate, opt_g),
                ddm(div_rate, real_g),
                ddm(div_rate, pess_g),
            )

        if not weights_used:
            return FairValueResult(
                ticker=ticker, method_name="Calculator 1",
                status="failed", error="Insufficient data",
                methods_breakdown={}, data_sources=["yfinance"],
            )

        total_weight = sum(weights_used.values())
        blended: dict[str, float | None] = {}
        for sc in ["optimistic", "realistic", "pessimistic"]:
            vals = scenario_values[sc]
            blended[sc] = sum(vals) / total_weight if vals else None

        valid = [v for v in blended.values() if v is not None]
        pre_mos = sum(valid) / len(valid) if valid else None

        return FairValueResult(
            ticker=ticker,
            method_name="Calculator 1",
            pre_mos_value=round(pre_mos, 2) if pre_mos else None,
            post_mos_value=round(pre_mos * MOS, 2) if pre_mos else None,
            methods_breakdown=breakdown,
            data_sources=["yfinance"],
        )

    except Exception as e:
        return FairValueResult(
            ticker=ticker, method_name="Calculator 1",
            status="failed", error=str(e),
            methods_breakdown={}, data_sources=["yfinance"],
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    args = parser.parse_args()
    result = asyncio.run(run(args.ticker))
    print(json.dumps(result.model_dump(), indent=2))
```

- [ ] Test:

```bash
cd backend && python valuation/calculator_1.py --ticker MSFT
# Expected: JSON with scenarios breakdown and post_mos_value
```

**Commit:** `feat: Calculator 1 — DCF + EV/EBITDA + P/E + P/FCF + DDM with scenarios`

---

### Task 7 — Calculator 2 (DCF/WACC + P/E + EV/EBITDA + EV/Sales + PEG + RIM)

**Files:** `backend/valuation/calculator_2.py`

- [ ] Create `backend/valuation/calculator_2.py`:

```python
"""
Calculator 2: DCF/WACC (30%), P/E (20%), EV/EBITDA (20%), EV/Sales (15%), PEG (0% default), RIM/EVA (15%).
MOS: 10%.
"""
from __future__ import annotations
import argparse, asyncio, json
from models import FairValueResult
from services.yahoo import fetch_ticker_info, extract_financials

MOS = 0.90
TERMINAL_GROWTH = 0.03
HORIZON = 10


def pv(cf: float, rate: float, year: int) -> float:
    return cf / (1 + rate) ** year


def _wacc(info: dict, fin: dict) -> float:
    beta = info.get("beta") or 1.0
    beta = max(0.5, min(beta, 2.5))
    cost_of_equity = 0.03 + beta * 0.06   # CAPM: rf=3%, ERP=6%
    market_cap = fin["market_cap"] or 1
    total_debt = info.get("totalDebt") or 0
    total_value = market_cap + total_debt
    equity_weight = market_cap / total_value
    debt_weight = total_debt / total_value
    tax_rate = info.get("effectiveTaxRate") or 0.21
    interest_expense = abs(info.get("interestExpense") or 0)
    cost_of_debt = (interest_expense / total_debt * (1 - tax_rate)) if total_debt > 0 else 0.04
    return equity_weight * cost_of_equity + debt_weight * cost_of_debt


def dcf_wacc(fcf: float, growth: float, wacc: float, net_debt: float, shares: float) -> float:
    total = 0.0
    cf = fcf
    for t in range(1, HORIZON + 1):
        cf *= (1 + growth)
        total += pv(cf, wacc, t)
    tv = cf * (1 + TERMINAL_GROWTH) / (wacc - TERMINAL_GROWTH)
    total += pv(tv, wacc, HORIZON)
    return (total - net_debt) / shares


def rim(bv: float, eps: float, cost_eq: float, growth: float) -> float:
    roe = eps / bv if bv > 0 else 0
    total_pv = 0.0
    bv_t = bv
    for t in range(1, HORIZON + 1):
        ri = bv_t * (roe - cost_eq)
        total_pv += pv(ri, cost_eq, t)
        bv_t *= (1 + growth)
    return bv + total_pv


def ev_multiple(base: float, growth: float, multiple: float, net_debt: float, shares: float) -> float:
    projected = base * (1 + growth) ** HORIZON
    return (projected * multiple - net_debt) / shares / (1 + 0.10) ** HORIZON


def pe_fv(eps: float, pe: float) -> float:
    return eps * min(pe, 40)


def peg_fv(eps: float, growth_pct: float) -> float | None:
    if growth_pct <= 0:
        return None
    return eps * growth_pct  # PEG=1 fair value: P/E = growth rate


async def run(ticker: str) -> FairValueResult:
    try:
        info = await fetch_ticker_info(ticker)
        fin = extract_financials(info)

        fcf = fin["fcf_ttm"]
        shares = fin["shares_outstanding"]
        net_debt = fin["net_debt"] or 0
        ebitda = fin["ebitda_ttm"]
        revenue = fin["revenue_ttm"]
        eps = fin["eps_ttm"]
        bv = fin["book_value_per_share"]
        growth = fin["earnings_growth"] or fin["revenue_growth"] or 0.07
        ev_ebitda_m = info.get("enterpriseToEbitda") or 12.0
        ev_sales_m = info.get("enterpriseToRevenue") or 3.0
        trailing_pe = fin["trailing_pe"] or 15.0
        growth_pct = growth * 100

        wacc = _wacc(info, fin)
        cost_eq = 0.03 + (info.get("beta") or 1.0) * 0.06
        breakdown: dict = {}
        values: list[tuple[float, float]] = []

        def add(name: str, weight: float, raw: float | None):
            if raw and raw > 0:
                breakdown[name] = {"weight": weight, "pre_mos": round(raw, 2), "post_mos": round(raw * MOS, 2)}
                values.append((raw, weight))

        # DCF/WACC
        if fcf and shares and fcf > 0 and wacc > TERMINAL_GROWTH:
            add("dcf_wacc", 0.30, dcf_wacc(fcf, growth, wacc, net_debt, shares))

        # P/E
        if eps and eps > 0 and trailing_pe > 0:
            add("pe", 0.20, pe_fv(eps, trailing_pe))

        # EV/EBITDA
        if ebitda and shares and ebitda > 0:
            add("ev_ebitda", 0.20, ev_multiple(ebitda, growth, ev_ebitda_m, net_debt, shares))

        # EV/Sales
        if revenue and shares and revenue > 0:
            add("ev_sales", 0.15, ev_multiple(revenue, growth, ev_sales_m, net_debt, shares))

        # RIM/EVA
        if bv and eps and bv > 0:
            add("rim", 0.15, rim(bv, eps, cost_eq, growth))

        # PEG (bonus, 0% default weight but shown in breakdown)
        peg = peg_fv(eps, growth_pct) if eps and eps > 0 else None
        if peg and peg > 0:
            breakdown["peg"] = {"weight": 0, "pre_mos": round(peg, 2), "post_mos": round(peg * MOS, 2)}

        if not values:
            return FairValueResult(
                ticker=ticker, method_name="Calculator 2",
                status="failed", error="Insufficient data",
                methods_breakdown={}, data_sources=["yfinance"],
            )

        total_weight = sum(w for _, w in values)
        pre_mos = sum(v * w for v, w in values) / total_weight

        return FairValueResult(
            ticker=ticker,
            method_name="Calculator 2",
            pre_mos_value=round(pre_mos, 2),
            post_mos_value=round(pre_mos * MOS, 2),
            methods_breakdown=breakdown,
            data_sources=["yfinance"],
        )

    except Exception as e:
        return FairValueResult(
            ticker=ticker, method_name="Calculator 2",
            status="failed", error=str(e),
            methods_breakdown={}, data_sources=["yfinance"],
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", required=True)
    args = parser.parse_args()
    result = asyncio.run(run(args.ticker))
    print(json.dumps(result.model_dump(), indent=2))
```

- [ ] Test:

```bash
cd backend && python valuation/calculator_2.py --ticker GOOGL
# Expected: JSON with dcf_wacc, pe, ev_ebitda, ev_sales, rim in methods_breakdown
```

**Commit:** `feat: Calculator 2 — DCF/WACC + P/E + EV/EBITDA + EV/Sales + RIM`

---

## Phase 4 — Score Normalizer + Aggregator

### Task 8 — Normalizer service

**Files:** `backend/services/normalizer.py`

- [ ] Create `backend/services/normalizer.py`:

```python
from __future__ import annotations
from models import AgentResult


def normalise_buffett_munger(raw: float) -> float:
    """Direct 1–5 scale."""
    return max(1.0, min(5.0, raw))


def normalise_lynch_garp(raw: float) -> float:
    """Direct 1–5 scale."""
    return max(1.0, min(5.0, raw))


def normalise_growth_stock(raw: float) -> float:
    """(score / 100) × 5, clamped [1, 5]."""
    return max(1.0, min(5.0, (raw / 100) * 5))


def normalise_business_engine(raw: float) -> float:
    """Direct 1–5 scale."""
    return max(1.0, min(5.0, raw))


def normalise_canslim(raw: float) -> float:
    """((score − 7) / 28) × 4 + 1, clamped [1, 5]."""
    return max(1.0, min(5.0, ((raw - 7) / 28) * 4 + 1))


def derive_pre_screener(recommendation: str | None, growth_potential: str | None, financial_state: str | None) -> float:
    """
    1. Map recommendation: BUY=5, HOLD=3, SELL=1
    2. Apply Growth Potential: High=+0, Moderate=−0.5, Low=−1.0
    3. Apply Financial State: Bad=−0.5, otherwise 0
    4. Clamp [1, 5]
    """
    rec = (recommendation or "").upper()
    base = {"BUY": 5.0, "HOLD": 3.0, "SELL": 1.0}.get(rec, 3.0)

    growth = (growth_potential or "").lower()
    if "low" in growth:
        base -= 1.0
    elif "moderate" in growth:
        base -= 0.5

    fin = (financial_state or "").lower()
    if "bad" in fin:
        base -= 0.5

    return max(1.0, min(5.0, base))


_NORMALIZERS = {
    "buffett_munger": normalise_buffett_munger,
    "lynch_garp": normalise_lynch_garp,
    "growth_stock": normalise_growth_stock,
    "business_engine": normalise_business_engine,
    "canslim": normalise_canslim,
}


def apply_normalisation(agent_name: str, result: AgentResult) -> AgentResult:
    """Mutate AgentResult to set normalised_score from raw_score."""
    key = agent_name.lower().replace("-", "_").replace(" ", "_")
    if key in _NORMALIZERS and result.raw_score is not None:
        result.normalised_score = round(_NORMALIZERS[key](result.raw_score), 2)
    return result
```

**Commit:** `feat: score normalizer — all 6 normalisation formulas`

---

### Task 9 — Aggregator

**Files:** `backend/orchestrator/aggregator.py`

- [ ] Create `backend/orchestrator/aggregator.py`:

```python
from __future__ import annotations
from models import AgentResult, FairValueResult, TickerResult
from datetime import datetime, timezone


_SCORE_LABEL_MAP = [
    (4.5, "Strong Buy"),
    (3.5, "Buy"),
    (2.5, "Hold / Watch"),
    (1.5, "Underperform"),
    (0.0, "Sell / Avoid"),
]


def score_label(score: float | None) -> str | None:
    if score is None:
        return None
    for threshold, label in _SCORE_LABEL_MAP:
        if score >= threshold:
            return label
    return "Sell / Avoid"


_AGENT_SCORE_MAP = {
    "buffett_munger": "buffett_munger_score",
    "lynch_garp": "lynch_garp_score",
    "growth_stock": "growth_analyzer_score",
    "business_engine": "business_engine_score",
    "canslim": "canslim_score",
    "pre_screener": "pre_screener_score",
}

_FV_MAP = {
    "gemini_fv": "fair_value_gemini",
    "calculator_1": "fair_value_calculator_1",
    "calculator_2": "fair_value_calculator_2",
}


def aggregate(
    ticker: str,
    company_name: str | None,
    current_price: float | None,
    agent_results: dict[str, AgentResult],
    fv_results: dict[str, FairValueResult],
) -> TickerResult:
    result = TickerResult(
        ticker=ticker,
        company_name=company_name,
        current_price=current_price,
        last_evaluated=datetime.now(timezone.utc).isoformat(),
        agent_results=agent_results,
        fair_value_results=fv_results,
    )

    # Map individual agent scores
    for agent_key, field in _AGENT_SCORE_MAP.items():
        ar = agent_results.get(agent_key)
        if ar and ar.normalised_score is not None:
            setattr(result, field, ar.normalised_score)

    # Overall final score = simple average of available normalised scores
    scores = [
        getattr(result, field)
        for field in _AGENT_SCORE_MAP.values()
        if getattr(result, field) is not None
    ]
    if scores:
        result.overall_final_score = round(sum(scores) / len(scores), 2)
        result.overall_label = score_label(result.overall_final_score)

    # Map fair value results
    for fv_key, field in _FV_MAP.items():
        fvr = fv_results.get(fv_key)
        if fvr and fvr.post_mos_value is not None:
            setattr(result, field, fvr.post_mos_value)

    # Blended fair value = average of available post-MOS values
    fv_values = [
        getattr(result, f)
        for f in ["fair_value_gemini", "fair_value_calculator_1", "fair_value_calculator_2"]
        if getattr(result, f) is not None
    ]
    if fv_values:
        result.blended_fair_value = round(sum(fv_values) / len(fv_values), 2)

    # Price vs fair value %
    if result.blended_fair_value and current_price and current_price > 0:
        result.price_vs_fair_value_pct = round(
            (result.blended_fair_value - current_price) / current_price * 100, 2
        )

    # Status
    failed_agents = sum(1 for ar in agent_results.values() if ar.status == "failed")
    total_agents = len(agent_results)
    if failed_agents == 0 and total_agents > 0:
        result.status = "completed"
    elif failed_agents == total_agents:
        result.status = "failed"
    else:
        result.status = "partial"

    result.errors = [
        f"{k}: {v.error}"
        for k, v in {**agent_results, **fv_results}.items()
        if v.status == "failed" and v.error
    ]

    return result
```

**Commit:** `feat: aggregator — overall score, blended FV, price gap %`

---

## Phase 5 — Agent Prompts

### Task 10 — Buffett-Munger prompt

**Files:** `backend/prompts/buffett_munger.md`

- [ ] Create `backend/prompts/buffett_munger.md`:

```markdown
You are a Buffett-Munger Value Analyst. Your role is to evaluate stocks through the lens of Warren Buffett and Charlie Munger's value investing philosophy.

## Your Framework

Analyze the following criteria for the stock {{TICKER}}:

1. **Business Moat** — Does the company have a durable competitive advantage (brand, network effects, switching costs, cost advantages, efficient scale)?
2. **Management Quality** — Is management honest, shareholder-friendly, with strong capital allocation?
3. **Financial Strength** — ROE > 15% consistently, low debt, strong free cash flow, growing earnings?
4. **Valuation** — Is the stock trading at a reasonable price relative to intrinsic value? Use P/E, P/B, P/FCF, and any discounted cash flow estimates you can find.
5. **Predictability** — Is the business model simple, understandable, and predictable over the next 10 years?

## Research Instructions

Use web search to find the latest information on {{TICKER}}:
- Recent earnings reports and guidance
- Current financial ratios (P/E, P/B, ROE, debt-to-equity, FCF yield)
- Competitive position and moat analysis
- Management commentary and insider transactions
- Any recent red flags (accounting issues, regulatory problems, competitive threats)

## Scoring

After thorough research, assign a score from **1 to 5** where:
- **5** = Exceptional Buffett-Munger quality business at fair or better price
- **4** = Good quality business at reasonable price
- **3** = Acceptable business or good business at high price
- **2** = Below-average business or good business at very high price
- **1** = Poor quality business or severely overvalued

## Output Format

You MUST end your response with exactly this format (on its own lines):

SCORE: [number from 1-5, can be decimal like 3.5]
RECOMMENDATION: [STRONG BUY / BUY / WATCHLIST / PASS]

Provide a comprehensive qualitative analysis before the score, including:
- Business moat assessment
- Management quality assessment
- Key financial metrics found
- Valuation assessment
- Main risks and concerns
- Overall investment thesis
```

### Task 11 — Lynch GARP prompt

**Files:** `backend/prompts/lynch_garp.md`

- [ ] Create `backend/prompts/lynch_garp.md`:

```markdown
You are a Lynch GARP (Growth at a Reasonable Price) Analyst following Peter Lynch's investment philosophy.

## Your Framework

Analyze {{TICKER}} through Peter Lynch's lens:

1. **PEG Ratio** — Is the PEG ratio below 1.0 (price reasonable relative to growth)?
2. **Growth Rate** — What is the earnings growth rate? Lynch preferred 15-30% growers.
3. **Business Story** — Can you describe the stock in one sentence? Is it simple and understandable?
4. **Institutional Ownership** — Low institutional ownership is often a positive (undiscovered gem).
5. **Balance Sheet** — Is the company financially sound with manageable debt?
6. **Category** — Is this a Slow Grower, Stalwart, Fast Grower, Cyclical, Asset Play, or Turnaround?
7. **Ten-Bagger Potential** — Does it have room to grow significantly?

## Research Instructions

Search for the latest data on {{TICKER}}:
- Current PEG ratio and analyst growth estimates
- 5-year EPS growth history and projections
- Revenue growth trends
- Institutional ownership percentage
- Debt-to-equity ratio and interest coverage
- Recent earnings beat/miss history
- Industry position and market share trends

## Scoring

Assign a score from **1 to 5**:
- **5** = Classic Lynch "10-bagger" candidate — strong growth, reasonable valuation, clear story
- **4** = Good GARP opportunity with solid fundamentals
- **3** = Hold — decent growth but valuation stretched, or growth slowing
- **2** = Overvalued for its growth rate, or growth story broken
- **1** = Sell — deteriorating fundamentals or severely overvalued

## Output Format

End your response with exactly:

SCORE: [1-5]
RECOMMENDATION: [BUY / HOLD / SELL]

Include in your analysis:
- Stock category (Lynch's classification)
- PEG ratio assessment
- Growth rate trend
- Balance sheet health
- Main investment thesis or concern
```

### Task 12 — Growth Stock Analyzer prompt

**Files:** `backend/prompts/growth_stock.md`

- [ ] Create `backend/prompts/growth_stock.md`:

```markdown
You are a Growth Stock Analyzer. Your role is to evaluate high-growth technology and innovation companies.

## Your Framework

Score {{TICKER}} on these 10 factors (0-10 each, total 0-100):

1. **Revenue Growth** (0-10) — YoY revenue growth rate (>30% = 10, 20-30% = 8, 10-20% = 6, <10% = 4)
2. **Revenue Acceleration** (0-10) — Is growth accelerating or decelerating quarter over quarter?
3. **Gross Margin Expansion** (0-10) — Are gross margins expanding? High-quality growth has improving margins.
4. **TAM & Market Position** (0-10) — Total addressable market size and company's share/positioning.
5. **Net Revenue Retention** (0-10) — For SaaS/recurring revenue: NRR > 120% = 10, 110-120% = 8, 100-110% = 6
6. **Management & Execution** (0-10) — Track record of hitting guidance, insider ownership, founder-led?
7. **Competitive Moat** (0-10) — Network effects, switching costs, platform advantages?
8. **Path to Profitability** (0-10) — Clear path to FCF positive? Already profitable = 10
9. **Balance Sheet** (0-10) — Cash runway, debt levels, dilution risk?
10. **Valuation vs. Growth** (0-10) — EV/Sales and EV/GP relative to growth rate (Rule of 40)?

## Research Instructions

Search for the latest on {{TICKER}}:
- Most recent quarterly earnings results and revenue growth
- Gross margin and operating leverage trends
- NRR/NDR if SaaS company
- Management guidance and analyst estimates
- Competitive landscape and recent wins/losses
- Cash position and burn rate if unprofitable
- Rule of 40 score (revenue growth + FCF margin)

## Scoring

Total score out of 100.

## Output Format

End your response with exactly:

SCORE: [0-100]
RECOMMENDATION: [Excellent / Good / Uncertain / Speculative]

Provide a detailed scorecard showing each of the 10 criteria with your sub-score and reasoning.
```

### Task 13 — Business Engine Analyst prompt

**Files:** `backend/prompts/business_engine.md`

- [ ] Create `backend/prompts/business_engine.md`:

```markdown
You are a Business Engine Analyst. Your role is to evaluate the underlying quality and durability of a company's business model.

## Your Framework

Analyze {{TICKER}} across these dimensions:

1. **Pricing Power** — Can the company raise prices without losing customers? Evidence of this?
2. **Capital Efficiency** — ROIC, ROCE, asset turnover — does the business generate good returns on capital?
3. **Customer Retention & Loyalty** — Churn rates, NPS scores, customer lifetime value, repeat purchase rates?
4. **Operating Leverage** — Does revenue growth flow through to profits at an accelerating rate?
5. **Recurring Revenue Quality** — What % is subscription/recurring vs. one-time?
6. **Brand & Intangibles** — Brand value, intellectual property, proprietary technology?
7. **Supply Chain & Operations** — Operational excellence, margin stability, cost control?

## Research Instructions

Search for latest information on {{TICKER}}:
- ROIC and ROCE trends over 5 years
- Recent pricing actions and customer response
- Gross margin and operating margin trends
- Customer acquisition cost vs lifetime value (if available)
- Recent management commentary on business model
- Any structural changes to business model

## Scoring

Assign a business grade from **1 to 5**:
- **5** = Elite business engine — pricing power, high ROIC, strong recurring revenue, operating leverage
- **4** = Strong business with one or two weaknesses
- **3** = Average business — decent but not exceptional on most dimensions
- **2** = Below-average — structural weaknesses in the business model
- **1** = Poor business engine — commoditized, low ROIC, no pricing power

## Output Format

End your response with exactly:

SCORE: [1-5]
RECOMMENDATION: [Business Grade A / B / C / D — optionally add: RED FLAG if critical issues found]

Cover each of the 7 dimensions in your analysis.
```

### Task 14 — CANSLIM prompt

**Files:** `backend/prompts/canslim.md`

- [ ] Create `backend/prompts/canslim.md`:

```markdown
You are a CANSLIM Stock Analyzer Pro following William O'Neil's CANSLIM methodology.

## CANSLIM Framework

Score {{TICKER}} on each letter criterion (1-5 each, total 7-35):

**C — Current Quarterly Earnings** (1-5)
- EPS growth vs. same quarter last year. >25% = 5, 15-25% = 4, 5-15% = 3, flat = 2, negative = 1

**A — Annual Earnings Growth** (1-5)
- 3-year EPS growth rate. >25%/yr = 5, 15-25% = 4, 10-15% = 3, 5-10% = 2, <5% = 1

**N — New Products/Services/Management** (1-5)
- Recent innovation, new product launches, new CEO with turnaround plan? Score based on novelty and impact.

**S — Supply and Demand** (1-5)
- Volume patterns and institutional accumulation/distribution. Heavy volume on up-days = 5

**L — Leader or Laggard** (1-5)
- Relative strength vs. market and sector. RS Rating equivalent: top 10% = 5, top 25% = 4, average = 3, bottom = 1

**I — Institutional Sponsorship** (1-5)
- Growing institutional ownership, top funds buying? Strong and growing = 5

**M — Market Direction** (1-5)
- Is the general market in an uptrend (confirmed rally)? Always score current market direction.

## Research Instructions

Search for latest on {{TICKER}}:
- Most recent quarterly EPS vs. year-ago quarter (% change)
- Annual EPS growth rate over 3 years
- Recent product launches, management changes, innovations
- Volume and price action analysis (price vs. 50-day and 200-day MA)
- Relative performance vs. S&P 500 over last 52 weeks
- Changes in institutional ownership (13F filings)
- Current market conditions (S&P 500 trend)

## Output Format

End your response with exactly:

SCORE: [7-35]
RECOMMENDATION: [BUY / HOLD / SELL]

Provide individual sub-scores for each CANSLIM letter with brief justification.
```

### Task 15 — Stock Pre-Screener prompt

**Files:** `backend/prompts/pre_screener.md`

- [ ] Create `backend/prompts/pre_screener.md`:

```markdown
You are a Stock Pre-Screener. Your role is to perform a rapid initial assessment of {{TICKER}} to determine if it merits deeper analysis.

## Screening Criteria

Evaluate the stock on these quick-check dimensions:

### Fundamental Screen
- P/E ratio vs. industry average (reasonable?)
- Revenue growth (positive and sustained?)
- Profitability (positive operating income?)
- Debt load (total debt/equity < 2x?)
- Free cash flow (positive FCF?)

### Technical Screen
- Price vs. 52-week high and low (where is it in its range?)
- Price vs. 200-day moving average (above or below?)
- Recent momentum (last 3-month performance)

### Quality Screen
- Return on equity (> 10%?)
- Consistent earnings (no large surprises/misses?)
- Management credibility (recent guidance accuracy?)

### Growth Potential Assessment
Classify growth potential as:
- **High** — Revenue growing >15%, expanding margins, large TAM
- **Moderate** — Revenue growing 5-15%, stable margins
- **Low** — Revenue growing <5%, margin pressure, or declining

### Financial State Assessment
Classify financial state as:
- **Good** — Strong balance sheet, positive FCF, manageable debt
- **Average** — Some financial concerns but manageable
- **Bad** — High debt, negative FCF, going-concern risk

## Research Instructions

Search for the latest on {{TICKER}}:
- Current financial ratios
- Recent earnings results
- Analyst consensus and price targets
- Any recent news (earnings beats/misses, guidance changes, M&A)

## Output Format

End your response with exactly these lines:

RECOMMENDATION: [BUY / HOLD / SELL]
GROWTH POTENTIAL: [High / Moderate / Low]
FINANCIAL STATE: [Good / Average / Bad]

Provide a concise 3-5 paragraph summary covering: fundamental health, technical picture, growth outlook, key risks, and your recommendation rationale.
```

**Commit:** `feat: all 6 agent system prompts`

---

## Phase 6 — Claude Agents

### Task 16 — BaseAgent

**Files:** `backend/agents/base_agent.py`

- [ ] Create `backend/agents/base_agent.py`:

```python
from __future__ import annotations
import asyncio, os, re, time
from pathlib import Path
import anthropic
from models import AgentResult

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_BACKOFF_BASE = 2.0
_MAX_BACKOFF = 30.0
_MAX_RETRIES = 3


class BaseAgent:
    agent_name: str = "base"
    model: str = "claude-opus-4-6"
    max_tokens: int = 4000
    tools = [{"type": "web_search_20250305", "name": "web_search"}]

    def __init__(self):
        self._client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        path = _PROMPTS_DIR / f"{self.agent_name}.md"
        return path.read_text(encoding="utf-8")

    async def run(self, ticker: str) -> AgentResult:
        prompt = self._prompt.replace("{{TICKER}}", ticker)
        last_error: str | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                response = await self._client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    tools=self.tools,
                    messages=[{"role": "user", "content": prompt}],
                )
                full_text = self._extract_text(response)
                raw_score, recommendation = self.parse_score(full_text)
                report = self._extract_report(full_text)
                result = AgentResult(
                    agent_name=self.agent_name,
                    ticker=ticker,
                    raw_score=raw_score,
                    recommendation=recommendation,
                    raw_response=full_text,
                    report=report,
                )
                return result

            except anthropic.RateLimitError as e:
                last_error = str(e)
                wait = min(_BACKOFF_BASE * (2 ** attempt), _MAX_BACKOFF)
                await asyncio.sleep(wait)
            except Exception as e:
                last_error = str(e)
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(_BACKOFF_BASE)
                else:
                    break

        return AgentResult(
            agent_name=self.agent_name,
            ticker=ticker,
            status="failed",
            error=last_error or "Unknown error",
        )

    def _extract_text(self, response) -> str:
        parts = []
        for block in response.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts)

    def _extract_report(self, text: str) -> str:
        lines = text.strip().splitlines()
        report_lines = []
        for line in lines:
            if re.match(r"^(SCORE|RECOMMENDATION|GROWTH POTENTIAL|FINANCIAL STATE):", line.strip()):
                continue
            report_lines.append(line)
        return "\n".join(report_lines).strip()

    def parse_score(self, response: str) -> tuple[float | None, str | None]:
        score_match = re.search(r"SCORE:\s*([\d.]+)", response, re.IGNORECASE)
        rec_match = re.search(r"RECOMMENDATION:\s*(.+)", response, re.IGNORECASE)
        score = float(score_match.group(1)) if score_match else None
        rec = rec_match.group(1).strip() if rec_match else None
        return score, rec
```

### Task 17 — Individual agent classes

**Files:** `backend/agents/buffett_munger.py`, `lynch_garp.py`, `growth_stock.py`, `business_engine.py`, `canslim.py`, `pre_screener.py`

- [ ] Create each agent (they override only agent_name and optionally max_tokens):

**`backend/agents/buffett_munger.py`:**
```python
from agents.base_agent import BaseAgent

class BuffettMungerAgent(BaseAgent):
    agent_name = "buffett_munger"
    max_tokens = 3000
```

**`backend/agents/lynch_garp.py`:**
```python
from agents.base_agent import BaseAgent

class LynchGarpAgent(BaseAgent):
    agent_name = "lynch_garp"
    max_tokens = 2500
```

**`backend/agents/growth_stock.py`:**
```python
from agents.base_agent import BaseAgent

class GrowthStockAgent(BaseAgent):
    agent_name = "growth_stock"
    max_tokens = 3000
```

**`backend/agents/business_engine.py`:**
```python
from agents.base_agent import BaseAgent

class BusinessEngineAgent(BaseAgent):
    agent_name = "business_engine"
    max_tokens = 2500
```

**`backend/agents/canslim.py`:**
```python
from agents.base_agent import BaseAgent

class CANSLIMAgent(BaseAgent):
    agent_name = "canslim"
    max_tokens = 2500
```

**`backend/agents/pre_screener.py`:**
```python
from __future__ import annotations
import re
from agents.base_agent import BaseAgent
from models import AgentResult
from services.normalizer import derive_pre_screener


class PreScreenerAgent(BaseAgent):
    agent_name = "pre_screener"
    max_tokens = 2000

    def parse_score(self, response: str) -> tuple[float | None, str | None]:
        rec_match = re.search(r"RECOMMENDATION:\s*(.+)", response, re.IGNORECASE)
        growth_match = re.search(r"GROWTH POTENTIAL:\s*(.+)", response, re.IGNORECASE)
        fin_match = re.search(r"FINANCIAL STATE:\s*(.+)", response, re.IGNORECASE)

        rec = rec_match.group(1).strip() if rec_match else None
        growth = growth_match.group(1).strip() if growth_match else None
        fin = fin_match.group(1).strip() if fin_match else None

        derived = derive_pre_screener(rec, growth, fin)
        return derived, rec
```

**Commit:** `feat: 6 Claude scoring agents — BaseAgent + individual agent classes`

---

## Phase 7 — Orchestrator + Batch Processing

### Task 18 — Batch orchestrator

**Files:** `backend/orchestrator/batch.py`

- [ ] Create `backend/orchestrator/batch.py`:

```python
from __future__ import annotations
import asyncio, os, uuid
from collections.abc import AsyncGenerator
from models import TickerResult, AgentResult, FairValueResult
from agents.buffett_munger import BuffettMungerAgent
from agents.lynch_garp import LynchGarpAgent
from agents.growth_stock import GrowthStockAgent
from agents.business_engine import BusinessEngineAgent
from agents.canslim import CANSLIMAgent
from agents.pre_screener import PreScreenerAgent
from valuation.gemini_fv import run as gemini_fv_run
from valuation.calculator_1 import run as calc1_run
from valuation.calculator_2 import run as calc2_run
from services.yahoo import fetch_ticker_info, extract_financials, validate_ticker
from services.normalizer import apply_normalisation
from services.sheets import upsert_result
from orchestrator.aggregator import aggregate

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "10"))
MAX_CONCURRENT_LLM = int(os.getenv("MAX_CONCURRENT_LLM_CALLS", "5"))

_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM)

_AGENTS = {
    "buffett_munger": BuffettMungerAgent,
    "lynch_garp": LynchGarpAgent,
    "growth_stock": GrowthStockAgent,
    "business_engine": BusinessEngineAgent,
    "canslim": CANSLIMAgent,
    "pre_screener": PreScreenerAgent,
}


async def _run_agent(key: str, cls, ticker: str) -> tuple[str, AgentResult]:
    async with _semaphore:
        agent = cls()
        result = await agent.run(ticker)
        result = apply_normalisation(key, result)
        return key, result


async def _run_fv(key: str, fn, ticker: str) -> tuple[str, FairValueResult]:
    return key, await fn(ticker)


async def analyse_ticker(ticker: str) -> TickerResult:
    """Run all 9 analyses concurrently for a single ticker."""
    agent_tasks = [_run_agent(k, cls, ticker) for k, cls in _AGENTS.items()]
    fv_tasks = [
        _run_fv("gemini_fv", gemini_fv_run, ticker),
        _run_fv("calculator_1", calc1_run, ticker),
        _run_fv("calculator_2", calc2_run, ticker),
    ]

    all_results = await asyncio.gather(*agent_tasks, *fv_tasks, return_exceptions=True)

    agent_results: dict[str, AgentResult] = {}
    fv_results: dict[str, FairValueResult] = {}

    for i, res in enumerate(all_results):
        if isinstance(res, Exception):
            key = list(_AGENTS.keys())[i] if i < 6 else ["gemini_fv", "calculator_1", "calculator_2"][i - 6]
            if i < 6:
                agent_results[key] = AgentResult(
                    agent_name=key, ticker=ticker, status="failed", error=str(res)
                )
            else:
                fv_results[key] = FairValueResult(
                    ticker=ticker, method_name=key, status="failed", error=str(res)
                )
        else:
            key, result = res
            if isinstance(result, AgentResult):
                agent_results[key] = result
            else:
                fv_results[key] = result

    # Fetch basic info for company name + price
    company_name = None
    current_price = None
    try:
        info = await fetch_ticker_info(ticker)
        fin = extract_financials(info)
        company_name = fin.get("company_name")
        current_price = fin.get("current_price")
    except Exception:
        pass

    return aggregate(ticker, company_name, current_price, agent_results, fv_results)


async def run_batch(
    tickers: list[str],
    job_id: str,
    cancel_event: asyncio.Event,
) -> AsyncGenerator[dict, None]:
    """Process tickers in groups of BATCH_SIZE, yield SSE events."""
    total = len(tickers)
    completed = 0
    failed = 0

    yield {"type": "job_start", "job_id": job_id, "total": total}

    groups = [tickers[i:i + BATCH_SIZE] for i in range(0, len(tickers), BATCH_SIZE)]

    for group in groups:
        if cancel_event.is_set():
            break

        # Within each group, all tickers run concurrently
        group_tasks = {t: asyncio.create_task(analyse_ticker(t)) for t in group}

        for ticker, task in group_tasks.items():
            yield {"type": "ticker_start", "ticker": ticker}
            try:
                result = await task
                if result.status == "failed":
                    failed += 1
                else:
                    completed += 1
                    try:
                        await upsert_result(result)
                    except Exception as e:
                        result.errors.append(f"sheets_write: {e}")
                yield {"type": "ticker_done", "ticker": ticker, "result": result.model_dump()}
            except Exception as e:
                failed += 1
                yield {"type": "ticker_error", "ticker": ticker, "error": str(e)}

    status = "cancelled" if cancel_event.is_set() else "completed"
    yield {"type": "job_done", "job_id": job_id, "completed": completed, "failed": failed, "status": status}
```

**Commit:** `feat: batch orchestrator — concurrent ticker analysis with SSE event stream`

---

## Phase 8 — Google Sheets Service

### Task 19 — Google Sheets service

**Files:** `backend/services/sheets.py`

- [ ] Create `backend/services/sheets.py`:

```python
from __future__ import annotations
import asyncio, json, os
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from models import TickerResult

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_service = None


def _get_service():
    global _service
    if _service is None:
        creds_path = os.environ.get("GOOGLE_SHEETS_CREDS_PATH", "./credentials/service_account.json")
        creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        _service = build("sheets", "v4", credentials=creds)
    return _service


def _sheet_id() -> str:
    return os.environ["GOOGLE_SHEETS_ID"]


async def read_tickers() -> list[str]:
    """Read ticker symbols from the 'Tickers' sheet, column A."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _read_tickers_sync)


def _read_tickers_sync() -> list[str]:
    svc = _get_service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=_sheet_id(),
        range="Tickers!A:A",
    ).execute()
    rows = result.get("values", [])
    return [row[0].strip() for row in rows if row and row[0].strip() and row[0].strip().upper() != "TICKER"]


async def upsert_result(result: TickerResult) -> None:
    """Upsert a TickerResult row into the 'Database' sheet."""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _upsert_sync, result)


def _result_to_row(r: TickerResult) -> list:
    return [
        r.ticker,
        r.company_name or "",
        r.last_evaluated or datetime.utcnow().isoformat(),
        r.buffett_munger_score if r.buffett_munger_score is not None else "",
        r.lynch_garp_score if r.lynch_garp_score is not None else "",
        r.growth_analyzer_score if r.growth_analyzer_score is not None else "",
        r.business_engine_score if r.business_engine_score is not None else "",
        r.canslim_score if r.canslim_score is not None else "",
        r.pre_screener_score if r.pre_screener_score is not None else "",
        r.overall_final_score if r.overall_final_score is not None else "",
        r.fair_value_gemini if r.fair_value_gemini is not None else "",
        r.fair_value_calculator_1 if r.fair_value_calculator_1 is not None else "",
        r.fair_value_calculator_2 if r.fair_value_calculator_2 is not None else "",
        r.blended_fair_value if r.blended_fair_value is not None else "",
        r.current_price if r.current_price is not None else "",
        r.price_vs_fair_value_pct if r.price_vs_fair_value_pct is not None else "",
    ]


_DB_HEADERS = [
    "Ticker", "Company Name", "Last Evaluated",
    "Buffett-Munger Score", "Lynch GARP Score", "Growth Analyzer Score",
    "Business Engine Score", "CANSLIM Score", "Pre-Screener Score",
    "Overall Final Score",
    "Fair Value — Gemini", "Fair Value — Calculator 1", "Fair Value — Calculator 2",
    "Blended Fair Value", "Current Price at Eval", "Price vs Fair Value %",
]


def _upsert_sync(result: TickerResult) -> None:
    svc = _get_service()
    sheet_id = _sheet_id()

    # Read existing data
    existing = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range="Database!A:A"
    ).execute()
    rows = existing.get("values", [])

    # Find row index (1-based, +1 for header)
    target_row = None
    for i, row in enumerate(rows):
        if row and row[0].strip().upper() == result.ticker.upper():
            target_row = i + 1  # 1-based
            break

    new_row = _result_to_row(result)

    if target_row is None:
        # Append
        if not rows:
            # Write headers first
            svc.spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range="Database!A1",
                valueInputOption="RAW",
                body={"values": [_DB_HEADERS]},
            ).execute()
        svc.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range="Database!A:A",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [new_row]},
        ).execute()
    else:
        # Overwrite existing row
        svc.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"Database!A{target_row}",
            valueInputOption="RAW",
            body={"values": [new_row]},
        ).execute()


async def read_database() -> list[TickerResult]:
    """Read all rows from the 'Database' sheet and return as TickerResult list."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _read_database_sync)


def _read_database_sync() -> list[TickerResult]:
    svc = _get_service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=_sheet_id(),
        range="Database!A:P",
    ).execute()
    rows = result.get("values", [])
    if len(rows) < 2:
        return []

    def safe_float(val: str) -> float | None:
        try:
            return float(val) if val else None
        except (ValueError, TypeError):
            return None

    results = []
    for row in rows[1:]:  # skip header
        while len(row) < 16:
            row.append("")
        results.append(TickerResult(
            ticker=row[0],
            company_name=row[1] or None,
            last_evaluated=row[2] or None,
            buffett_munger_score=safe_float(row[3]),
            lynch_garp_score=safe_float(row[4]),
            growth_analyzer_score=safe_float(row[5]),
            business_engine_score=safe_float(row[6]),
            canslim_score=safe_float(row[7]),
            pre_screener_score=safe_float(row[8]),
            overall_final_score=safe_float(row[9]),
            fair_value_gemini=safe_float(row[10]),
            fair_value_calculator_1=safe_float(row[11]),
            fair_value_calculator_2=safe_float(row[12]),
            blended_fair_value=safe_float(row[13]),
            current_price=safe_float(row[14]),
            price_vs_fair_value_pct=safe_float(row[15]),
        ))
    return results
```

**Commit:** `feat: Google Sheets service — read tickers, upsert results, read database`

---

## Phase 9 — API Routes

### Task 20 — Analysis router (POST /api/analyse + GET /api/stream/{job_id})

**Files:** `backend/routers/analysis.py`

- [ ] Create `backend/routers/analysis.py`:

```python
from __future__ import annotations
import asyncio, json, uuid
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from models import AnalyseRequest
from services.yahoo import validate_ticker
from services.sheets import read_tickers
from orchestrator.batch import run_batch

router = APIRouter()

# In-memory job store (sufficient for local single-machine use)
_jobs: dict[str, dict] = {}
_cancel_events: dict[str, asyncio.Event] = {}


@router.post("/analyse")
async def start_analysis(request: AnalyseRequest):
    tickers: list[str] = []

    # Input: manual tickers
    if request.tickers:
        tickers.extend([t.strip().upper() for t in request.tickers if t.strip()])

    # Input: Google Sheets
    if request.sheets_url or (not request.tickers):
        try:
            sheet_tickers = await read_tickers()
            tickers.extend([t.upper() for t in sheet_tickers if t not in tickers])
        except Exception as e:
            if not tickers:
                return {"error": f"No tickers provided and Sheets read failed: {e}"}

    if not tickers:
        return {"error": "No tickers provided"}

    # Validate tickers (parallel)
    valid_results = await asyncio.gather(*[validate_ticker(t) for t in tickers])
    valid_tickers = [t for t, ok in zip(tickers, valid_results) if ok]
    invalid_tickers = [t for t, ok in zip(tickers, valid_results) if not ok]

    if not valid_tickers:
        return {"error": "No valid tickers found", "invalid": invalid_tickers}

    job_id = str(uuid.uuid4())
    cancel_event = asyncio.Event()
    _cancel_events[job_id] = cancel_event
    _jobs[job_id] = {
        "status": "running",
        "total": len(valid_tickers),
        "completed": 0,
        "failed": 0,
        "results": [],
        "invalid": invalid_tickers,
    }

    # Fire and forget — stream via SSE
    asyncio.create_task(_run_job(job_id, valid_tickers, cancel_event))

    return {"job_id": job_id, "total": len(valid_tickers), "invalid": invalid_tickers}


async def _run_job(job_id: str, tickers: list[str], cancel_event: asyncio.Event):
    job = _jobs[job_id]
    async for event in run_batch(tickers, job_id, cancel_event):
        if event["type"] == "ticker_done":
            job["completed"] += 1
            job["results"].append(event["result"])
        elif event["type"] == "ticker_error":
            job["failed"] += 1
        elif event["type"] == "job_done":
            job["status"] = event["status"]


@router.get("/stream/{job_id}")
async def stream_job(job_id: str):
    if job_id not in _jobs:
        return {"error": "Job not found"}

    async def event_generator():
        last_sent = 0
        while True:
            job = _jobs.get(job_id)
            if not job:
                break
            results = job["results"]
            # Send any new results
            for result in results[last_sent:]:
                yield {
                    "event": "ticker_done",
                    "data": json.dumps(result),
                }
                last_sent += 1

            yield {
                "event": "status",
                "data": json.dumps({
                    "job_id": job_id,
                    "status": job["status"],
                    "total": job["total"],
                    "completed": job["completed"],
                    "failed": job["failed"],
                }),
            }

            if job["status"] in ("completed", "failed", "cancelled"):
                break

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


@router.post("/cancel/{job_id}")
async def cancel_job(job_id: str):
    if job_id in _cancel_events:
        _cancel_events[job_id].set()
        if job_id in _jobs:
            _jobs[job_id]["status"] = "cancelled"
        return {"cancelled": True}
    return {"error": "Job not found"}
```

### Task 21 — Database router

**Files:** `backend/routers/database.py`

- [ ] Create `backend/routers/database.py`:

```python
from fastapi import APIRouter
from services.sheets import read_database

router = APIRouter()


@router.get("/database")
async def get_database():
    try:
        results = await read_database()
        return {"results": [r.model_dump() for r in results]}
    except Exception as e:
        return {"error": str(e), "results": []}
```

- [ ] Test the API:

```bash
cd backend && uvicorn main:app --reload --port 8000
# In another terminal:
curl -X POST http://localhost:8000/api/analyse \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["AAPL"]}'
# Expected: {"job_id": "...", "total": 1, "invalid": []}
```

**Commit:** `feat: API routes — /api/analyse, /api/stream/{job_id}, /api/cancel/{job_id}, /api/database`

---

## Phase 10 — Frontend Components

### Task 22 — Layout + ScoreBadge components

**Files:** `frontend/src/components/Layout.tsx`, `frontend/src/components/ScoreBadge.tsx`

- [ ] Create `frontend/src/components/Layout.tsx`:

```tsx
import { Link, useLocation } from 'react-router-dom'
import { cn } from '../lib/utils'

interface LayoutProps {
  children: React.ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const { pathname } = useLocation()

  const navItems = [
    { href: '/', label: 'Analyse' },
    { href: '/database', label: 'Database' },
  ]

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-slate-200 font-mono">
      <header className="border-b border-[#1e1e2a] bg-[#111118]">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-blue-400 font-bold text-lg tracking-wider">STOCK EVALUATOR</span>
            <span className="text-slate-600 text-xs">AI-Powered Analysis</span>
          </div>
          <nav className="flex gap-6">
            {navItems.map(item => (
              <Link
                key={item.href}
                to={item.href}
                className={cn(
                  'text-sm transition-colors',
                  pathname === item.href
                    ? 'text-blue-400 border-b border-blue-400 pb-0.5'
                    : 'text-slate-400 hover:text-slate-200'
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
      <footer className="border-t border-[#1e1e2a] mt-12 py-4 text-center text-xs text-slate-600">
        For informational and educational purposes only. Not investment advice.
      </footer>
    </div>
  )
}
```

- [ ] Create `frontend/src/components/ScoreBadge.tsx`:

```tsx
import { scoreToBgColor, scoreToLabel } from '../types'
import { cn } from '../lib/utils'

interface ScoreBadgeProps {
  score: number | null
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

export default function ScoreBadge({ score, size = 'md', showLabel = false }: ScoreBadgeProps) {
  const label = scoreToLabel(score)
  const colorClass = scoreToBgColor(score)

  const sizeClass = {
    sm: 'text-xs px-1.5 py-0.5',
    md: 'text-sm px-2 py-1',
    lg: 'text-base px-3 py-1.5',
  }[size]

  return (
    <span className={cn('rounded font-mono font-semibold inline-flex items-center gap-1.5', colorClass, sizeClass)}>
      {score != null ? score.toFixed(2) : '—'}
      {showLabel && label && <span className="font-normal text-xs opacity-80">{label}</span>}
    </span>
  )
}
```

**Commit:** `feat: Layout and ScoreBadge components`

---

### Task 23 — AgentCard + FairValuePanel + ProgressBar components

- [ ] Create `frontend/src/components/AgentCard.tsx`:

```tsx
import { AgentResult } from '../types'
import ScoreBadge from './ScoreBadge'
import { cn } from '../lib/utils'

interface AgentCardProps {
  agentName: string
  result: AgentResult | null
  isLoading?: boolean
}

const AGENT_LABELS: Record<string, string> = {
  buffett_munger: 'Buffett-Munger',
  lynch_garp: 'Lynch GARP',
  growth_stock: 'Growth Stock',
  business_engine: 'Business Engine',
  canslim: 'CANSLIM',
  pre_screener: 'Pre-Screener',
}

export default function AgentCard({ agentName, result, isLoading }: AgentCardProps) {
  const label = AGENT_LABELS[agentName] || agentName

  if (isLoading) {
    return (
      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-4 animate-pulse">
        <div className="h-4 bg-[#1e1e2a] rounded w-32 mb-2" />
        <div className="h-8 bg-[#1e1e2a] rounded w-16" />
      </div>
    )
  }

  if (!result) return null

  return (
    <div className={cn(
      'bg-[#16161e] border rounded-lg p-4',
      result.status === 'failed' ? 'border-red-900' : 'border-[#1e1e2a]'
    )}>
      <div className="text-xs text-slate-500 mb-1 uppercase tracking-wide">{label}</div>
      {result.status === 'failed' ? (
        <div className="text-red-400 text-sm">Failed</div>
      ) : (
        <>
          <ScoreBadge score={result.normalised_score} size="lg" />
          {result.recommendation && (
            <div className="text-xs text-slate-400 mt-1">{result.recommendation}</div>
          )}
        </>
      )}
    </div>
  )
}
```

- [ ] Create `frontend/src/components/FairValuePanel.tsx`:

```tsx
import { FairValueResult, TickerResult } from '../types'

interface FairValuePanelProps {
  result: TickerResult
  compact?: boolean
}

function FVRow({ label, result }: { label: string; result: FairValueResult | undefined }) {
  if (!result) return null
  return (
    <tr className="border-b border-[#1e1e2a]">
      <td className="py-2 pr-4 text-slate-400 text-sm">{label}</td>
      <td className="py-2 pr-4 text-right font-mono">
        {result.pre_mos_value != null ? `$${result.pre_mos_value.toFixed(2)}` : '—'}
      </td>
      <td className="py-2 text-right font-mono text-blue-400">
        {result.post_mos_value != null ? `$${result.post_mos_value.toFixed(2)}` : '—'}
      </td>
    </tr>
  )
}

export default function FairValuePanel({ result, compact }: FairValuePanelProps) {
  const fvGemini = result.fair_value_results['gemini_fv']
  const fvCalc1 = result.fair_value_results['calculator_1']
  const fvCalc2 = result.fair_value_results['calculator_2']

  const gapPct = result.price_vs_fair_value_pct
  const gapColor = gapPct == null ? 'text-slate-400'
    : gapPct > 10 ? 'text-green-400'
    : gapPct > 0 ? 'text-blue-400'
    : gapPct > -10 ? 'text-yellow-400'
    : 'text-red-400'

  return (
    <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-4">
      <div className="text-xs text-slate-500 uppercase tracking-wide mb-3">Fair Value</div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[#1e1e2a]">
            <th className="text-left py-1 text-xs text-slate-600 font-normal">Method</th>
            <th className="text-right py-1 text-xs text-slate-600 font-normal">Pre-MOS</th>
            <th className="text-right py-1 text-xs text-slate-600 font-normal">Post-MOS</th>
          </tr>
        </thead>
        <tbody>
          <FVRow label="Gemini FV" result={fvGemini} />
          <FVRow label="Calculator 1" result={fvCalc1} />
          <FVRow label="Calculator 2" result={fvCalc2} />
        </tbody>
      </table>
      <div className="mt-3 pt-3 border-t border-[#1e1e2a] flex justify-between items-center">
        <div>
          <div className="text-xs text-slate-500">Blended Fair Value</div>
          <div className="text-lg font-mono text-slate-200">
            {result.blended_fair_value != null ? `$${result.blended_fair_value.toFixed(2)}` : '—'}
          </div>
        </div>
        {gapPct != null && (
          <div className="text-right">
            <div className="text-xs text-slate-500">vs Current Price</div>
            <div className={`text-lg font-mono ${gapColor}`}>
              {gapPct > 0 ? '+' : ''}{gapPct.toFixed(1)}%
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
```

- [ ] Create `frontend/src/components/ProgressBar.tsx`:

```tsx
interface ProgressBarProps {
  current: number
  total: number
  label?: string
}

export default function ProgressBar({ current, total, label }: ProgressBarProps) {
  const pct = total > 0 ? Math.round((current / total) * 100) : 0
  return (
    <div className="w-full">
      {label && (
        <div className="flex justify-between text-xs text-slate-400 mb-1">
          <span>{label}</span>
          <span>{current} / {total} ({pct}%)</span>
        </div>
      )}
      <div className="w-full bg-[#1e1e2a] rounded-full h-2">
        <div
          className="bg-blue-500 h-2 rounded-full transition-all duration-300"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
```

**Commit:** `feat: AgentCard, FairValuePanel, ProgressBar components`

---

## Phase 11 — SSE Hook + Pages

### Task 24 — useAnalysisStream hook

**Files:** `frontend/src/hooks/useAnalysisStream.ts`

- [ ] Create `frontend/src/hooks/useAnalysisStream.ts`:

```typescript
import { useEffect, useRef, useState } from 'react'
import { TickerResult, JobStatus } from '../types'

interface StreamState {
  status: JobStatus['status']
  total: number
  completed: number
  failed: number
  results: TickerResult[]
  tickerStatuses: Record<string, 'queued' | 'running' | 'done' | 'failed'>
}

const API = 'http://localhost:8000'

export function useAnalysisStream(jobId: string | null) {
  const [state, setState] = useState<StreamState>({
    status: 'running',
    total: 0,
    completed: 0,
    failed: 0,
    results: [],
    tickerStatuses: {},
  })
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!jobId) return
    const es = new EventSource(`${API}/api/stream/${jobId}`)
    esRef.current = es

    es.addEventListener('ticker_done', (e) => {
      const result: TickerResult = JSON.parse(e.data)
      setState(prev => ({
        ...prev,
        results: [...prev.results, result],
        tickerStatuses: { ...prev.tickerStatuses, [result.ticker]: result.status === 'failed' ? 'failed' : 'done' },
      }))
    })

    es.addEventListener('status', (e) => {
      const data: Partial<StreamState> = JSON.parse(e.data)
      setState(prev => ({ ...prev, ...data }))
      if (data.status && ['completed', 'failed', 'cancelled'].includes(data.status)) {
        es.close()
      }
    })

    es.onerror = () => {
      setState(prev => ({ ...prev, status: 'failed' }))
      es.close()
    }

    return () => es.close()
  }, [jobId])

  const cancel = async () => {
    if (!jobId) return
    await fetch(`${API}/api/cancel/${jobId}`, { method: 'POST' })
    esRef.current?.close()
  }

  return { ...state, cancel }
}
```

**Commit:** `feat: useAnalysisStream SSE hook`

---

### Task 25 — Home page

**Files:** `frontend/src/pages/Home.tsx`

- [ ] Create `frontend/src/pages/Home.tsx`:

```tsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const API = 'http://localhost:8000'

export default function Home() {
  const [tickers, setTickers] = useState('')
  const [useSheets, setUseSheets] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const handleAnalyse = async () => {
    setLoading(true)
    setError(null)
    try {
      const tickerList = tickers
        .split(/[\s,]+/)
        .map(t => t.trim().toUpperCase())
        .filter(Boolean)

      const body: Record<string, unknown> = {}
      if (tickerList.length > 0) body.tickers = tickerList
      if (useSheets) body.sheets_url = 'from_sheets'

      const res = await fetch(`${API}/api/analyse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()

      if (data.error) {
        setError(data.error)
      } else {
        navigate(`/progress/${data.job_id}`, { state: { total: data.total, invalid: data.invalid } })
      }
    } catch (e) {
      setError('Failed to connect to backend. Is uvicorn running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold text-slate-100 mb-2">Stock Analysis</h1>
      <p className="text-slate-500 text-sm mb-8">
        Enter up to 150 tickers for AI-powered analysis across 9 evaluation models.
      </p>

      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-6 space-y-4">
        <div>
          <label className="block text-xs text-slate-500 uppercase tracking-wide mb-2">
            Ticker Symbols (comma or space separated)
          </label>
          <textarea
            value={tickers}
            onChange={e => setTickers(e.target.value)}
            placeholder="AAPL, MSFT, GOOGL, NVDA..."
            className="w-full bg-[#0a0a0f] border border-[#1e1e2a] rounded px-3 py-2 text-slate-200 font-mono text-sm resize-none focus:outline-none focus:border-blue-700 h-24"
          />
        </div>

        <div className="flex items-center gap-3">
          <div className="flex-1 border-t border-[#1e1e2a]" />
          <span className="text-xs text-slate-600">OR</span>
          <div className="flex-1 border-t border-[#1e1e2a]" />
        </div>

        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={useSheets}
            onChange={e => setUseSheets(e.target.checked)}
            className="w-4 h-4 rounded border-slate-600 bg-[#0a0a0f]"
          />
          <span className="text-sm text-slate-300">Load tickers from Google Sheets</span>
        </label>

        {error && (
          <div className="text-red-400 text-sm bg-red-900/20 border border-red-900 rounded px-3 py-2">
            {error}
          </div>
        )}

        <button
          onClick={handleAnalyse}
          disabled={loading || (!tickers.trim() && !useSheets)}
          className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-600 text-white font-semibold py-3 rounded transition-colors text-sm uppercase tracking-wide"
        >
          {loading ? 'Starting...' : 'Analyse'}
        </button>
      </div>
    </div>
  )
}
```

**Commit:** `feat: Home page — ticker input form`

---

### Task 26 — Progress page

**Files:** `frontend/src/pages/Progress.tsx`

- [ ] Create `frontend/src/pages/Progress.tsx`:

```tsx
import { useEffect } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { useAnalysisStream } from '../hooks/useAnalysisStream'
import ProgressBar from '../components/ProgressBar'
import ScoreBadge from '../components/ScoreBadge'
import { cn } from '../lib/utils'

export default function Progress() {
  const { jobId } = useParams<{ jobId: string }>()
  const navigate = useNavigate()
  const location = useLocation()
  const { status, total, completed, failed, results, tickerStatuses, cancel } = useAnalysisStream(jobId ?? null)

  useEffect(() => {
    if (status === 'completed') {
      navigate(`/results/${jobId}`, { state: { results } })
    }
  }, [status])

  const allTickers = Object.keys(tickerStatuses)

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-slate-100">Analysis in Progress</h1>
        <button
          onClick={cancel}
          className="text-sm text-red-400 hover:text-red-300 border border-red-900 px-3 py-1.5 rounded"
        >
          Cancel
        </button>
      </div>

      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-4 mb-6">
        <ProgressBar
          current={completed + failed}
          total={total || (location.state?.total ?? 0)}
          label={`Analysed ${completed + failed} / ${total || (location.state?.total ?? 0)} tickers`}
        />
        <div className="flex gap-4 mt-2 text-xs text-slate-500">
          <span className="text-green-400">{completed} completed</span>
          {failed > 0 && <span className="text-red-400">{failed} failed</span>}
        </div>
      </div>

      {allTickers.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-6">
          {allTickers.map(ticker => {
            const s = tickerStatuses[ticker]
            return (
              <span key={ticker} className={cn(
                'px-2 py-1 rounded text-xs font-mono border',
                s === 'done' ? 'border-green-800 text-green-400 bg-green-900/20' :
                s === 'failed' ? 'border-red-800 text-red-400 bg-red-900/20' :
                s === 'running' ? 'border-blue-800 text-blue-400 bg-blue-900/20 animate-pulse' :
                'border-slate-800 text-slate-500'
              )}>
                {ticker}
              </span>
            )
          })}
        </div>
      )}

      {results.length > 0 && (
        <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg overflow-hidden">
          <div className="text-xs text-slate-500 uppercase tracking-wide px-4 py-2 border-b border-[#1e1e2a]">
            Live Results
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e1e2a] text-xs text-slate-600">
                <th className="text-left py-2 px-4">Ticker</th>
                <th className="text-left py-2">Company</th>
                <th className="text-right py-2 pr-4">Score</th>
              </tr>
            </thead>
            <tbody>
              {results.map(r => (
                <tr key={r.ticker} className="border-b border-[#1e1e2a] hover:bg-[#1a1a24]">
                  <td className="py-2 px-4 font-mono font-semibold text-blue-400">{r.ticker}</td>
                  <td className="py-2 text-slate-400 text-xs">{r.company_name || '—'}</td>
                  <td className="py-2 pr-4 text-right">
                    <ScoreBadge score={r.overall_final_score} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
```

**Commit:** `feat: Progress page — live SSE-driven analysis view`

---

### Task 27 — Results + TickerDetail + Database pages

**Files:** `frontend/src/pages/Results.tsx`, `TickerDetail.tsx`, `Database.tsx`

- [ ] Create `frontend/src/pages/Results.tsx`:

```tsx
import { useState } from 'react'
import { useParams, useLocation, useNavigate, Link } from 'react-router-dom'
import ScoreBadge from '../components/ScoreBadge'
import { TickerResult, scoreToColor } from '../types'

const AGENT_COLS = [
  { key: 'buffett_munger_score', label: 'B-M' },
  { key: 'lynch_garp_score', label: 'Lynch' },
  { key: 'growth_analyzer_score', label: 'Growth' },
  { key: 'business_engine_score', label: 'Biz Eng' },
  { key: 'canslim_score', label: 'CAN' },
  { key: 'pre_screener_score', label: 'Screen' },
] as const

type SortKey = 'overall_final_score' | 'price_vs_fair_value_pct' | 'ticker'

export default function Results() {
  const { jobId } = useParams()
  const location = useLocation()
  const results: TickerResult[] = location.state?.results || []
  const [sortKey, setSortKey] = useState<SortKey>('overall_final_score')
  const [sortAsc, setSortAsc] = useState(false)

  const sorted = [...results].sort((a, b) => {
    const av = a[sortKey] ?? (sortAsc ? Infinity : -Infinity)
    const bv = b[sortKey] ?? (sortAsc ? Infinity : -Infinity)
    return sortAsc ? (av > bv ? 1 : -1) : (av < bv ? 1 : -1)
  })

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortAsc(p => !p)
    else { setSortKey(key); setSortAsc(false) }
  }

  const exportCSV = () => {
    const headers = ['Ticker', 'Company', 'Score', 'B-M', 'Lynch', 'Growth', 'Biz Eng', 'CANSLIM', 'Screen', 'Blended FV', 'Price', 'FV Gap%']
    const rows = sorted.map(r => [
      r.ticker, r.company_name, r.overall_final_score,
      r.buffett_munger_score, r.lynch_garp_score, r.growth_analyzer_score,
      r.business_engine_score, r.canslim_score, r.pre_screener_score,
      r.blended_fair_value, r.current_price, r.price_vs_fair_value_pct,
    ])
    const csv = [headers, ...rows].map(r => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'results.csv'; a.click()
  }

  if (!results.length) return (
    <div className="text-slate-500 text-center py-20">No results. <Link to="/" className="text-blue-400">Run a new analysis</Link>.</div>
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-slate-100">Results — {results.length} tickers</h1>
        <button onClick={exportCSV} className="text-sm text-slate-400 hover:text-slate-200 border border-[#1e1e2a] px-3 py-1.5 rounded">
          Export CSV
        </button>
      </div>
      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[#1e1e2a] text-xs text-slate-500">
              <th className="text-left py-2 px-4 cursor-pointer hover:text-slate-300" onClick={() => toggleSort('ticker')}>Ticker</th>
              <th className="text-left py-2">Company</th>
              <th className="text-right py-2 px-2 cursor-pointer hover:text-slate-300" onClick={() => toggleSort('overall_final_score')}>Score</th>
              {AGENT_COLS.map(c => <th key={c.key} className="text-right py-2 px-2">{c.label}</th>)}
              <th className="text-right py-2 px-2">Blended FV</th>
              <th className="text-right py-2 px-2">Price</th>
              <th className="text-right py-2 px-4 cursor-pointer hover:text-slate-300" onClick={() => toggleSort('price_vs_fair_value_pct')}>FV Gap%</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map(r => (
              <tr key={r.ticker} className="border-b border-[#1e1e2a] hover:bg-[#1a1a24] cursor-pointer">
                <td className="py-2 px-4">
                  <Link to={`/ticker/${jobId}/${r.ticker}`} state={{ result: r }} className="font-mono font-semibold text-blue-400 hover:text-blue-300">
                    {r.ticker}
                  </Link>
                </td>
                <td className="py-2 text-slate-400 text-xs max-w-xs truncate">{r.company_name || '—'}</td>
                <td className="py-2 px-2 text-right"><ScoreBadge score={r.overall_final_score} /></td>
                {AGENT_COLS.map(c => (
                  <td key={c.key} className={`py-2 px-2 text-right font-mono text-xs ${scoreToColor(r[c.key])}`}>
                    {r[c.key]?.toFixed(2) ?? '—'}
                  </td>
                ))}
                <td className="py-2 px-2 text-right font-mono text-xs text-slate-300">
                  {r.blended_fair_value != null ? `$${r.blended_fair_value.toFixed(2)}` : '—'}
                </td>
                <td className="py-2 px-2 text-right font-mono text-xs text-slate-400">
                  {r.current_price != null ? `$${r.current_price.toFixed(2)}` : '—'}
                </td>
                <td className={`py-2 px-4 text-right font-mono text-xs ${r.price_vs_fair_value_pct != null && r.price_vs_fair_value_pct > 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {r.price_vs_fair_value_pct != null ? `${r.price_vs_fair_value_pct > 0 ? '+' : ''}${r.price_vs_fair_value_pct.toFixed(1)}%` : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

- [ ] Create `frontend/src/pages/TickerDetail.tsx`:

```tsx
import { useParams, useLocation, Link } from 'react-router-dom'
import { TickerResult } from '../types'
import ScoreBadge from '../components/ScoreBadge'
import AgentCard from '../components/AgentCard'
import FairValuePanel from '../components/FairValuePanel'
import { useState } from 'react'

const AGENTS = ['buffett_munger', 'lynch_garp', 'growth_stock', 'business_engine', 'canslim', 'pre_screener']

export default function TickerDetail() {
  const { jobId, ticker } = useParams()
  const location = useLocation()
  const result: TickerResult | undefined = location.state?.result
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null)

  if (!result) {
    return <div className="text-slate-500 text-center py-20">Result not found. <Link to="/" className="text-blue-400">Go home</Link>.</div>
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-4">
        <Link to={jobId ? `/results/${jobId}` : '/database'} className="text-xs text-slate-500 hover:text-slate-300">
          ← Back to results
        </Link>
      </div>

      <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold font-mono text-slate-100">{result.ticker}</h1>
            <p className="text-slate-400 mt-0.5">{result.company_name || '—'}</p>
            <p className="text-xs text-slate-600 mt-1">{result.last_evaluated}</p>
          </div>
          <div className="text-right">
            <ScoreBadge score={result.overall_final_score} size="lg" showLabel />
            <div className="text-xs text-slate-500 mt-1">{result.overall_label}</div>
            {result.current_price != null && (
              <div className="text-slate-300 font-mono mt-2">${result.current_price.toFixed(2)}</div>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-6">
        {AGENTS.map(key => (
          <AgentCard key={key} agentName={key} result={result.agent_results[key] ?? null} />
        ))}
      </div>

      <div className="mb-6">
        <FairValuePanel result={result} />
      </div>

      <div className="space-y-2">
        <h2 className="text-xs text-slate-500 uppercase tracking-wide mb-3">Agent Reports</h2>
        {AGENTS.map(key => {
          const ar = result.agent_results[key]
          if (!ar?.report) return null
          return (
            <div key={key} className="bg-[#16161e] border border-[#1e1e2a] rounded-lg overflow-hidden">
              <button
                onClick={() => setExpandedAgent(expandedAgent === key ? null : key)}
                className="w-full text-left px-4 py-3 flex justify-between items-center hover:bg-[#1a1a24]"
              >
                <span className="text-sm text-slate-300 capitalize">{key.replace('_', ' ')}</span>
                <span className="text-slate-600">{expandedAgent === key ? '−' : '+'}</span>
              </button>
              {expandedAgent === key && (
                <div className="px-4 pb-4 text-xs text-slate-400 whitespace-pre-wrap leading-relaxed border-t border-[#1e1e2a] pt-3">
                  {ar.report}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
```

- [ ] Create `frontend/src/pages/Database.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { TickerResult, scoreToColor } from '../types'
import ScoreBadge from '../components/ScoreBadge'

const API = 'http://localhost:8000'

export default function Database() {
  const [results, setResults] = useState<TickerResult[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API}/api/database`)
      const data = await res.json()
      if (data.error) setError(data.error)
      else setResults(data.results)
    } catch {
      setError('Failed to load database')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <div className="text-slate-500 text-center py-20 animate-pulse">Loading database...</div>
  if (error) return <div className="text-red-400 text-center py-20">{error}</div>

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-slate-100">Database — {results.length} records</h1>
        <button onClick={load} className="text-sm text-slate-400 hover:text-slate-200 border border-[#1e1e2a] px-3 py-1.5 rounded">
          Refresh
        </button>
      </div>

      {results.length === 0 ? (
        <div className="text-slate-500 text-center py-20">No records yet. <Link to="/" className="text-blue-400">Run an analysis</Link>.</div>
      ) : (
        <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e1e2a] text-xs text-slate-500">
                <th className="text-left py-2 px-4">Ticker</th>
                <th className="text-left py-2">Company</th>
                <th className="text-right py-2 px-2">Score</th>
                <th className="text-right py-2 px-2">B-M</th>
                <th className="text-right py-2 px-2">Lynch</th>
                <th className="text-right py-2 px-2">Growth</th>
                <th className="text-right py-2 px-2">BizEng</th>
                <th className="text-right py-2 px-2">CAN</th>
                <th className="text-right py-2 px-2">Screen</th>
                <th className="text-right py-2 px-2">FV</th>
                <th className="text-right py-2 px-2">Price</th>
                <th className="text-right py-2 px-4">Gap%</th>
                <th className="text-right py-2 px-4">Evaluated</th>
              </tr>
            </thead>
            <tbody>
              {results.map(r => (
                <tr key={r.ticker} className="border-b border-[#1e1e2a] hover:bg-[#1a1a24]">
                  <td className="py-2 px-4">
                    <Link to={`/ticker/db/${r.ticker}`} state={{ result: r }} className="font-mono font-semibold text-blue-400 hover:text-blue-300">
                      {r.ticker}
                    </Link>
                  </td>
                  <td className="py-2 text-slate-400 text-xs max-w-xs truncate">{r.company_name || '—'}</td>
                  <td className="py-2 px-2 text-right"><ScoreBadge score={r.overall_final_score} size="sm" /></td>
                  {(['buffett_munger_score', 'lynch_garp_score', 'growth_analyzer_score', 'business_engine_score', 'canslim_score', 'pre_screener_score'] as const).map(k => (
                    <td key={k} className={`py-2 px-2 text-right font-mono text-xs ${scoreToColor(r[k])}`}>
                      {r[k]?.toFixed(2) ?? '—'}
                    </td>
                  ))}
                  <td className="py-2 px-2 text-right font-mono text-xs text-slate-300">
                    {r.blended_fair_value != null ? `$${r.blended_fair_value.toFixed(2)}` : '—'}
                  </td>
                  <td className="py-2 px-2 text-right font-mono text-xs text-slate-400">
                    {r.current_price != null ? `$${r.current_price.toFixed(2)}` : '—'}
                  </td>
                  <td className={`py-2 px-4 text-right font-mono text-xs ${r.price_vs_fair_value_pct != null && r.price_vs_fair_value_pct > 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {r.price_vs_fair_value_pct != null ? `${r.price_vs_fair_value_pct > 0 ? '+' : ''}${r.price_vs_fair_value_pct.toFixed(1)}%` : '—'}
                  </td>
                  <td className="py-2 px-4 text-right text-xs text-slate-600">
                    {r.last_evaluated ? new Date(r.last_evaluated).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
```

**Commit:** `feat: Results, TickerDetail, Database pages`

---

## Phase 12 — End-to-End Startup + Testing

### Task 28 — Dev startup script + final smoke test

**Files:** `start.sh` (or `start.bat`)

- [ ] Create `start.sh`:

```bash
#!/bin/bash
echo "Starting Stock Evaluator..."
echo ""

# Backend
echo "[1/2] Starting FastAPI backend..."
cd backend
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for backend
sleep 2

# Frontend
echo "[2/2] Starting Vite frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "App running:"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo "  API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers."

trap "kill $BACKEND_PID $FRONTEND_PID" EXIT
wait
```

- [ ] End-to-end test checklist:

```
[ ] Backend health: curl http://localhost:8000/api/health → {"status":"ok"}
[ ] Analyse single ticker: POST /api/analyse {"tickers": ["AAPL"]} → job_id returned
[ ] SSE stream: GET /api/stream/{job_id} → events fire in sequence
[ ] Fair value scripts standalone: python valuation/gemini_fv.py --ticker AAPL
[ ] Database read: GET /api/database → returns array (empty OK if no Sheets data)
[ ] Frontend loads: http://localhost:5173 → Home page renders
[ ] Full flow: enter "AAPL" → Analyse → Progress page → auto-redirect to Results → click ticker → TickerDetail
[ ] Score badges show correct colours
[ ] All 6 agent scores visible in TickerDetail
[ ] All 3 fair value values visible in FairValuePanel
[ ] CSV export generates valid file
[ ] Database page loads and shows historical results
```

**Commit:** `feat: startup script + implementation plan complete`

---

## Self-Review

| Check | Status |
|-------|--------|
| All 9 agents/scripts implemented | ✓ |
| All 6 score normalisation formulas match spec | ✓ |
| Pre-Screener derived scoring matches spec | ✓ |
| Google Sheets DB schema matches all 16 columns | ✓ |
| SSE stream drives Progress page | ✓ |
| Individual agent scores stored + shown in UI | ✓ |
| Score badge colours match spec | ✓ |
| asyncio.Semaphore(5) caps Claude API calls | ✓ |
| BATCH_SIZE + MAX_CONCURRENT_LLM_CALLS configurable via .env | ✓ |
| TypeScript types are single source of truth | ✓ |
| No fairvalue3 code reused | ✓ |

---

## Execution

**Option A — Subagent-Driven:** Spawn a code-writing subagent to execute tasks in order, committing after each phase.

**Option B — Inline Execution:** Execute tasks phase by phase in this conversation, verifying after each task.

Which would you prefer?
