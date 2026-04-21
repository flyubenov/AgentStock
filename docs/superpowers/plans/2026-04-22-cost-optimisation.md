# Agent Cost Optimisation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce per-ticker analysis cost from ~$2.50 to ~$0.21 (batch) / ~$0.34 (live) by injecting yfinance data into agent prompts, switching three agents to Haiku, trimming output to score+rationale only, adding prompt caching, and routing default runs through the Anthropic Message Batches API.

**Architecture:** Two paths: "live" (existing SSE pipeline, optimised) and "batch" (Anthropic Batch API, default). Every agent receives a pre-fetched yfinance data block instead of performing redundant web searches. Haiku handles formulaic agents (CANSLIM, Pre-Screener, Lynch GARP); Sonnet handles judgment agents (Buffett-Munger, Business Engine, Growth Stock) with web search capped at 3 calls. A new `/api/jobs` router manages batch job lifecycle with JSON-file persistence.

**Tech Stack:** Python 3.11, FastAPI, `anthropic` SDK (messages.batches), yfinance, pytest, pytest-asyncio, React 18, TypeScript

**Design spec:** `docs/superpowers/specs/2026-04-22-cost-optimisation-design.md`

---

## File Map

| File | Action | Change |
|---|---|---|
| `backend/models.py` | Modify | Add `rationale`, `BatchJobFile` |
| `backend/services/yahoo.py` | Modify | Add `format_financial_block()` |
| `backend/services/normalizer.py` | Modify | Add pre_screener normalizer (bug fix) |
| `backend/agents/base_agent.py` | Modify | system/user split, `financial_block` param, 3-tuple parse_score |
| `backend/agents/pre_screener.py` | Modify | 3-tuple parse_score, Haiku, max_tokens 300 |
| `backend/agents/canslim.py` | Modify | Haiku, tools=[], max_tokens 300 |
| `backend/agents/lynch_garp.py` | Modify | Haiku, tools=[], max_tokens 300 |
| `backend/agents/buffett_munger.py` | Modify | max_tokens 400 |
| `backend/agents/business_engine.py` | Modify | max_tokens 400 |
| `backend/agents/growth_stock.py` | Modify | max_tokens 400 |
| `backend/prompts/canslim.md` | Modify | Remove research section, trim output |
| `backend/prompts/lynch_garp.md` | Modify | Remove research section, trim output |
| `backend/prompts/pre_screener.md` | Modify | Remove research section, trim output + RATIONALE |
| `backend/prompts/buffett_munger.md` | Modify | 3-search cap, trim output |
| `backend/prompts/business_engine.md` | Modify | 3-search cap, trim output |
| `backend/prompts/growth_stock.md` | Modify | 3-search cap, trim output |
| `backend/orchestrator/batch.py` | Modify | Pre-fetch financial block per ticker |
| `backend/routers/analysis.py` | Modify | `mode` field, batch routing |
| `backend/main.py` | Modify | Register jobs router |
| `backend/services/batch_service.py` | **Create** | Request builder, submit, status, cancel, results |
| `backend/routers/jobs.py` | **Create** | `/api/jobs/{job_id}/*` endpoints |
| `backend/tests/__init__.py` | **Create** | Empty |
| `backend/tests/conftest.py` | **Create** | asyncio mode config |
| `backend/tests/test_yahoo_block.py` | **Create** | Tests for `format_financial_block` |
| `backend/tests/test_normalizer_prescreener.py` | **Create** | Tests for pre_screener normalizer |
| `backend/tests/test_base_agent_parse.py` | **Create** | Tests for 3-tuple parse_score |
| `backend/tests/test_batch_service.py` | **Create** | Tests for request building and custom_id parsing |
| `frontend/src/types.ts` | Modify | Add `rationale`, `BatchJobStatus` |
| `frontend/src/pages/Home.tsx` | Modify | Mode toggle, batch navigation |
| `frontend/src/pages/TickerDetail.tsx` | Modify | Remove collapsible report sections |
| `frontend/src/components/AgentCard.tsx` | Modify | Show `rationale` subtitle |
| `frontend/src/App.tsx` | Modify | Add `/jobs/:jobId` route |
| `frontend/src/pages/JobStatus.tsx` | **Create** | Batch job polling page |

---

## Task 1: Fix pre_screener normalizer bug + add rationale to AgentResult

The pre_screener agent score is never included in the overall score because `normalised_score` is never set (pre_screener is missing from `_NORMALIZERS`). Fix this and add `rationale` to `AgentResult` and `BatchJobFile` to `models.py`.

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/services/normalizer.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_normalizer_prescreener.py`

- [ ] **Step 1: Install test dependencies**

```bash
cd backend
pip install pytest pytest-asyncio
```

- [ ] **Step 2: Create test infrastructure**

Create `backend/tests/__init__.py` (empty file).

Create `backend/tests/conftest.py`:
```python
import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")
```

- [ ] **Step 3: Write the failing test**

Create `backend/tests/test_normalizer_prescreener.py`:
```python
from services.normalizer import apply_normalisation
from models import AgentResult


def test_pre_screener_normalisation_sets_normalised_score():
    ar = AgentResult(agent_name="pre_screener", ticker="AAPL", raw_score=4.0)
    result = apply_normalisation("pre_screener", ar)
    assert result.normalised_score == 4.0


def test_pre_screener_normalisation_clamps_above_5():
    ar = AgentResult(agent_name="pre_screener", ticker="AAPL", raw_score=5.5)
    result = apply_normalisation("pre_screener", ar)
    assert result.normalised_score == 5.0


def test_pre_screener_normalisation_clamps_below_1():
    ar = AgentResult(agent_name="pre_screener", ticker="AAPL", raw_score=0.5)
    result = apply_normalisation("pre_screener", ar)
    assert result.normalised_score == 1.0


def test_other_agents_unaffected():
    ar = AgentResult(agent_name="buffett_munger", ticker="AAPL", raw_score=4.0)
    result = apply_normalisation("buffett_munger", ar)
    assert result.normalised_score == 4.0
```

- [ ] **Step 4: Run tests to confirm they fail**

```bash
cd backend
python -m pytest tests/test_normalizer_prescreener.py -v
```
Expected: `FAILED` — `AssertionError: assert None == 4.0`

- [ ] **Step 5: Fix normalizer.py**

In `backend/services/normalizer.py`, replace the `_NORMALIZERS` dict:
```python
_NORMALIZERS = {
    "buffett_munger": normalise_buffett_munger,
    "lynch_garp": normalise_lynch_garp,
    "growth_stock": normalise_growth_stock,
    "business_engine": normalise_business_engine,
    "canslim": normalise_canslim,
    "pre_screener": lambda x: max(1.0, min(5.0, x)),
}
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
cd backend
python -m pytest tests/test_normalizer_prescreener.py -v
```
Expected: 4 passed

- [ ] **Step 7: Add rationale field and BatchJobFile to models.py**

In `backend/models.py`, make these two changes:

Add `rationale` field to `AgentResult` (after `recommendation`):
```python
class AgentResult(BaseModel):
    agent_name: str
    ticker: str
    raw_score: float | None = None
    normalised_score: float | None = None
    recommendation: str | None = None
    rationale: str | None = None
    raw_response: str = ""
    report: str = ""
    status: Literal["completed", "failed"] = "completed"
    error: str | None = None
```

Add `BatchJobFile` model at the end of the file:
```python
class BatchJobFile(BaseModel):
    job_id: str
    batch_id: str
    tickers: list[str]
    failed_prefetch: list[str] = []
    status: Literal["processing", "completed", "cancelled"] = "processing"
    submitted_at: str
```

- [ ] **Step 8: Commit**

```bash
cd backend
git add services/normalizer.py models.py tests/
git commit -m "fix: pre_screener normalizer bug; add rationale to AgentResult; add BatchJobFile model"
```

---

## Task 2: Add format_financial_block to yahoo.py

**Files:**
- Modify: `backend/services/yahoo.py`
- Create: `backend/tests/test_yahoo_block.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_yahoo_block.py`:
```python
import pytest
from unittest.mock import patch
from services.yahoo import format_financial_block

_MOCK_INFO = {
    "symbol": "AAPL",
    "shortName": "Apple Inc.",
    "currentPrice": 189.45,
    "marketCap": 2_900_000_000_000,
    "trailingPE": 28.5,
    "forwardPE": 24.2,
    "pegRatio": 1.8,
    "trailingEps": 6.64,
    "earningsGrowth": 0.123,
    "totalRevenue": 391_000_000_000,
    "revenueGrowth": 0.041,
    "grossMargins": 0.452,
    "operatingMargins": 0.295,
    "freeCashflow": 99_000_000_000,
    "returnOnEquity": 1.47,
    "debtToEquity": 187.0,
    "fiftyTwoWeekHigh": 220.19,
    "fiftyTwoWeekLow": 164.08,
    "beta": 1.24,
    "dividendYield": 0.005,
    "heldPercentInstitutions": 0.61,
    "recommendationKey": "buy",
    "targetMeanPrice": 215.0,
    "twoHundredDayAverage": 175.0,
}


@pytest.mark.asyncio
async def test_format_financial_block_returns_string():
    with patch("services.yahoo._fetch_sync", return_value=_MOCK_INFO):
        block = await format_financial_block("AAPL")
    assert isinstance(block, str)
    assert "AAPL" in block
    assert "$189.45" in block
    assert "28.50" in block  # trailingPE


@pytest.mark.asyncio
async def test_format_financial_block_returns_none_on_exception():
    with patch("services.yahoo._fetch_sync", side_effect=ValueError("not found")):
        block = await format_financial_block("BADINPUT")
    assert block is None


@pytest.mark.asyncio
async def test_format_financial_block_handles_none_fields():
    sparse_info = {"symbol": "AAPL", "shortName": "Apple", "currentPrice": 100.0}
    with patch("services.yahoo._fetch_sync", return_value=sparse_info):
        block = await format_financial_block("AAPL")
    assert block is not None
    assert "N/A" in block
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend
python -m pytest tests/test_yahoo_block.py -v
```
Expected: `FAILED` — `ImportError` or `AttributeError: module has no attribute 'format_financial_block'`

- [ ] **Step 3: Implement format_financial_block in yahoo.py**

Append to `backend/services/yahoo.py`:
```python
from datetime import date as _date


async def format_financial_block(ticker: str) -> str | None:
    """Fetch ~20 financial metrics and format as a structured markdown block.
    Returns None if the fetch fails — callers must abort the ticker in that case."""
    try:
        info = await fetch_ticker_info(ticker)
    except Exception:
        return None

    def _p(val: float | None, prefix: str = "$") -> str:
        if val is None:
            return "N/A"
        return f"{prefix}{val:,.2f}"

    def _pct(val: float | None) -> str:
        if val is None:
            return "N/A"
        return f"{val * 100:.1f}%"

    def _large(val: float | None) -> str:
        if val is None:
            return "N/A"
        if val >= 1e12:
            return f"${val / 1e12:.2f}T"
        if val >= 1e9:
            return f"${val / 1e9:.2f}B"
        return f"${val / 1e6:.2f}M"

    def _n(val: float | None, d: int = 2) -> str:
        return "N/A" if val is None else f"{val:.{d}f}"

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    mkt_cap = info.get("marketCap")
    ma200 = info.get("twoHundredDayAverage")
    fcf = info.get("freeCashflow")

    price_vs_ma = None
    if price and ma200 and ma200 > 0:
        price_vs_ma = (price - ma200) / ma200 * 100

    fcf_yield = None
    if fcf and mkt_cap and mkt_cap > 0:
        fcf_yield = fcf / mkt_cap * 100

    rec = (info.get("recommendationKey") or "N/A").upper()

    return (
        f"## Pre-fetched Financial Data for {ticker} (via yfinance, {_date.today()})\n"
        f"- Current Price: {_p(price)} | Market Cap: {_large(mkt_cap)}\n"
        f"- P/E (TTM): {_n(info.get('trailingPE'))} | Forward P/E: {_n(info.get('forwardPE'))} | PEG: {_n(info.get('pegRatio'))}\n"
        f"- EPS (TTM): {_p(info.get('trailingEps'))} | EPS Growth YoY: {_pct(info.get('earningsGrowth'))}\n"
        f"- Revenue (TTM): {_large(info.get('totalRevenue'))} | Revenue Growth YoY: {_pct(info.get('revenueGrowth'))}\n"
        f"- Gross Margin: {_pct(info.get('grossMargins'))} | Operating Margin: {_pct(info.get('operatingMargins'))}\n"
        f"- FCF (TTM): {_large(fcf)} | FCF Yield: {'N/A' if fcf_yield is None else f'{fcf_yield:.1f}%'}\n"
        f"- ROE: {_pct(info.get('returnOnEquity'))} | Debt/Equity: {_n(info.get('debtToEquity'))}\n"
        f"- 52w High: {_p(info.get('fiftyTwoWeekHigh'))} | 52w Low: {_p(info.get('fiftyTwoWeekLow'))} | Beta: {_n(info.get('beta'))}\n"
        f"- Price vs 200-day MA: {'N/A' if price_vs_ma is None else f'{price_vs_ma:+.1f}%'}\n"
        f"- Dividend Yield: {_pct(info.get('dividendYield'))} | Institutional Ownership: {_pct(info.get('heldPercentInstitutions'))}\n"
        f"- Analyst Consensus: {rec} | Avg Target: {_p(info.get('targetMeanPrice'))}"
    )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend
python -m pytest tests/test_yahoo_block.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add services/yahoo.py tests/test_yahoo_block.py
git commit -m "feat: add format_financial_block to yahoo.py"
```

---

## Task 3: Update Haiku agent prompts (canslim, lynch_garp, pre_screener)

These prompts remove the "Research Instructions / web search" section entirely, since Haiku agents will score purely from the injected yfinance block. The `{{TICKER}}` placeholder is removed from the prompt body — the ticker is now in the user message, not the system prompt. Output is trimmed to score + rationale.

**Files:**
- Modify: `backend/prompts/canslim.md`
- Modify: `backend/prompts/lynch_garp.md`
- Modify: `backend/prompts/pre_screener.md`

- [ ] **Step 1: Replace canslim.md entirely**

```markdown
You are a CANSLIM Stock Analyzer Pro following William O'Neil's CANSLIM methodology.

## CANSLIM Framework

Using the pre-fetched financial data provided, score the ticker on each CANSLIM criterion (1–5 each, total 7–35):

**C — Current Quarterly Earnings** (1–5)
- EPS growth vs. same quarter last year. >25% = 5, 15–25% = 4, 5–15% = 3, flat = 2, negative = 1

**A — Annual Earnings Growth** (1–5)
- 3-year EPS growth rate. >25%/yr = 5, 15–25% = 4, 10–15% = 3, 5–10% = 2, <5% = 1

**N — New Products/Services/Management** (1–5)
- Score based on novelty signals visible in the financial data. Use analyst consensus and revenue acceleration as proxies.

**S — Supply and Demand** (1–5)
- Infer from price vs. 52-week range and institutional ownership trends.

**L — Leader or Laggard** (1–5)
- Use price vs. 200-day MA and analyst consensus as relative strength proxies.

**I — Institutional Sponsorship** (1–5)
- Institutional ownership percentage. >70% and growing = 5, 50–70% = 4, 30–50% = 3, <30% = 2.

**M — Market Direction** (1–5)
- Based on general context in analyst consensus and beta. Score 3 if uncertain.

## Output Format

End your response with exactly:

SCORE: [7–35, integer or one decimal]
RECOMMENDATION: [BUY / HOLD / SELL]
RATIONALE: [one sentence, max 20 words explaining the dominant factor]
```

- [ ] **Step 2: Replace lynch_garp.md entirely**

```markdown
You are a Lynch GARP (Growth at a Reasonable Price) Analyst following Peter Lynch's investment philosophy.

## Framework

Using the pre-fetched financial data provided, analyze the ticker through Peter Lynch's lens:

1. **PEG Ratio** — Is the PEG ratio below 1.0 (price reasonable relative to growth)?
2. **Growth Rate** — What is the earnings growth rate? Lynch preferred 15–30% growers.
3. **Business Story** — Based on sector/industry and revenue trends, is the business model simple and predictable?
4. **Institutional Ownership** — Low institutional ownership can signal an undiscovered gem.
5. **Balance Sheet** — Is the company financially sound? Check debt/equity and FCF.
6. **Category** — Classify as Slow Grower, Stalwart, Fast Grower, Cyclical, Asset Play, or Turnaround.
7. **Ten-Bagger Potential** — Does the growth rate and valuation leave room for significant appreciation?

## Scoring

Assign a score from **1 to 5**:
- **5** = Classic Lynch "10-bagger" candidate — strong growth, reasonable valuation, clear story
- **4** = Good GARP opportunity with solid fundamentals
- **3** = Hold — decent growth but valuation stretched, or growth slowing
- **2** = Overvalued for its growth rate, or growth story broken
- **1** = Sell — deteriorating fundamentals or severely overvalued

## Output Format

End your response with exactly:

SCORE: [1–5, can be decimal like 3.5]
RECOMMENDATION: [BUY / HOLD / SELL]
RATIONALE: [one sentence, max 20 words]
```

- [ ] **Step 3: Replace pre_screener.md entirely**

```markdown
You are a Stock Pre-Screener. Your role is to perform a rapid initial assessment of the provided ticker using the pre-fetched financial data.

## Screening Criteria

### Fundamental Screen
- P/E ratio: reasonable vs. growth rate?
- Revenue growth: positive and sustained?
- Profitability: positive operating margin?
- Debt load: debt/equity < 2x?
- Free cash flow: positive FCF?

### Technical Screen
- Price vs. 52-week high and low: where in its range?
- Price vs. 200-day MA: above or below?
- Beta: high or low volatility?

### Quality Screen
- Return on equity: > 10%?
- Analyst consensus and price target vs. current price

### Growth Potential Assessment
Classify as:
- **High** — Revenue growing >15%, expanding margins, strong analyst consensus
- **Moderate** — Revenue growing 5–15%, stable margins
- **Low** — Revenue growing <5%, margin pressure, or declining

### Financial State Assessment
Classify as:
- **Good** — Positive FCF, manageable debt (D/E < 1.5), strong ROE
- **Average** — Some financial concerns but manageable
- **Bad** — Negative FCF, high debt, or going-concern risk

## Output Format

End your response with exactly these lines:

RECOMMENDATION: [BUY / HOLD / SELL]
GROWTH POTENTIAL: [High / Moderate / Low]
FINANCIAL STATE: [Good / Average / Bad]
RATIONALE: [one sentence, max 20 words]
```

- [ ] **Step 4: Commit**

```bash
git add prompts/canslim.md prompts/lynch_garp.md prompts/pre_screener.md
git commit -m "feat: update Haiku agent prompts — remove web search, trim output to score+rationale"
```

---

## Task 4: Update Sonnet agent prompts (buffett_munger, business_engine, growth_stock)

These prompts keep the web search capability but cap it at 3 calls and trim the output format. The `{{TICKER}}` placeholder is removed from the prompt body.

**Files:**
- Modify: `backend/prompts/buffett_munger.md`
- Modify: `backend/prompts/business_engine.md`
- Modify: `backend/prompts/growth_stock.md`

- [ ] **Step 1: Replace buffett_munger.md entirely**

```markdown
You are a Buffett-Munger Value Analyst. Your role is to evaluate stocks through the lens of Warren Buffett and Charlie Munger's value investing philosophy.

## Your Framework

The user message includes pre-fetched financial data for the ticker. Use web search a maximum of 3 times for qualitative context not captured in that data — management commentary, recent news, competitive developments, or red flags.

Analyze these criteria:

1. **Business Moat** — Durable competitive advantage (brand, network effects, switching costs, cost advantages)?
2. **Management Quality** — Honest, shareholder-friendly, strong capital allocation?
3. **Financial Strength** — ROE >15% consistently, low debt, strong FCF, growing earnings?
4. **Valuation** — Reasonable price relative to intrinsic value? Use the pre-fetched P/E, P/FCF, and PEG ratios.
5. **Predictability** — Simple, understandable business model predictable over 10 years?

## Scoring

Assign a score from **1 to 5**:
- **5** = Exceptional Buffett-Munger quality business at fair or better price
- **4** = Good quality business at reasonable price
- **3** = Acceptable business or good business at high price
- **2** = Below-average business or good business at very high price
- **1** = Poor quality business or severely overvalued

## Output Format

End your response with exactly:

SCORE: [1–5, can be decimal like 3.5]
RECOMMENDATION: [STRONG BUY / BUY / WATCHLIST / PASS]
RATIONALE: [one sentence, max 20 words]
```

- [ ] **Step 2: Replace business_engine.md entirely**

```markdown
You are a Business Engine Analyst. Your role is to evaluate the underlying quality and durability of a company's business model.

## Your Framework

The user message includes pre-fetched financial data for the ticker. Use web search a maximum of 3 times for qualitative context — pricing actions, customer retention signals, management commentary, or structural business changes.

Analyze across these dimensions:

1. **Pricing Power** — Can the company raise prices without losing customers?
2. **Capital Efficiency** — ROIC, ROE, asset turnover — good returns on capital?
3. **Customer Retention & Loyalty** — Churn, repeat purchase, switching costs?
4. **Operating Leverage** — Does revenue growth accelerate profit growth?
5. **Recurring Revenue Quality** — What % is subscription/recurring vs. one-time?
6. **Brand & Intangibles** — Brand value, IP, proprietary technology?
7. **Supply Chain & Operations** — Margin stability, cost control?

## Scoring

Assign a business grade from **1 to 5**:
- **5** = Elite business engine — pricing power, high ROIC, strong recurring revenue
- **4** = Strong business with one or two weaknesses
- **3** = Average business — decent but not exceptional on most dimensions
- **2** = Below-average — structural weaknesses in the business model
- **1** = Poor business engine — commoditized, low ROIC, no pricing power

## Output Format

End your response with exactly:

SCORE: [1–5, can be decimal like 3.5]
RECOMMENDATION: [Business Grade A / B / C / D]
RATIONALE: [one sentence, max 20 words]
```

- [ ] **Step 3: Replace growth_stock.md entirely**

```markdown
You are a Growth Stock Analyzer. Your role is to evaluate high-growth technology and innovation companies.

## Your Framework

The user message includes pre-fetched financial data for the ticker. Use web search a maximum of 3 times for qualitative context — NRR/NDR data, competitive wins/losses, recent product launches, or guidance changes not in the financial data.

Score the ticker on these 10 factors (0–10 each, total 0–100):

1. **Revenue Growth** (0–10) — YoY revenue growth rate (>30% = 10, 20–30% = 8, 10–20% = 6, <10% = 4)
2. **Revenue Acceleration** (0–10) — Accelerating or decelerating quarter over quarter?
3. **Gross Margin Expansion** (0–10) — Gross margins expanding? Use the pre-fetched gross margin data.
4. **TAM & Market Position** (0–10) — Total addressable market size and positioning.
5. **Net Revenue Retention** (0–10) — For SaaS/recurring: NRR >120% = 10, 110–120% = 8, 100–110% = 6
6. **Management & Execution** (0–10) — Analyst consensus and target vs. price as proxy for credibility.
7. **Competitive Moat** (0–10) — Network effects, switching costs, platform advantages?
8. **Path to Profitability** (0–10) — FCF yield and operating margin as signals. Already FCF positive = 10.
9. **Balance Sheet** (0–10) — Positive FCF, manageable debt/equity, dividend yield (if any).
10. **Valuation vs. Growth** (0–10) — PEG ratio and revenue growth rate combined (Rule of 40 proxy).

## Output Format

End your response with exactly:

SCORE: [0–100]
RECOMMENDATION: [Excellent / Good / Uncertain / Speculative]
RATIONALE: [one sentence, max 20 words]
```

- [ ] **Step 4: Commit**

```bash
git add prompts/buffett_munger.md prompts/business_engine.md prompts/growth_stock.md
git commit -m "feat: update Sonnet agent prompts — 3-search cap, trim output to score+rationale"
```

---

## Task 5: Restructure BaseAgent (system/user split, financial_block param, 3-tuple parse_score)

**Files:**
- Modify: `backend/agents/base_agent.py`
- Create: `backend/tests/test_base_agent_parse.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_base_agent_parse.py`:
```python
from agents.base_agent import BaseAgent


def _make_agent() -> BaseAgent:
    agent = object.__new__(BaseAgent)
    return agent


def test_parse_score_returns_three_tuple():
    agent = _make_agent()
    response = "Analysis.\nSCORE: 3.5\nRECOMMENDATION: BUY\nRATIONALE: Strong moat but valuation is stretched."
    score, rec, rationale = agent.parse_score(response)
    assert score == 3.5
    assert rec == "BUY"
    assert rationale == "Strong moat but valuation is stretched."


def test_parse_score_handles_missing_rationale():
    agent = _make_agent()
    response = "SCORE: 4.0\nRECOMMENDATION: WATCHLIST"
    score, rec, rationale = agent.parse_score(response)
    assert score == 4.0
    assert rec == "WATCHLIST"
    assert rationale is None


def test_parse_score_handles_missing_score():
    agent = _make_agent()
    response = "No score here."
    score, rec, rationale = agent.parse_score(response)
    assert score is None
    assert rec is None
    assert rationale is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend
python -m pytest tests/test_base_agent_parse.py -v
```
Expected: `FAILED` — `not enough values to unpack (expected 3, got 2)`

- [ ] **Step 3: Replace base_agent.py entirely**

```python
from __future__ import annotations
import asyncio, os, re
from pathlib import Path
import anthropic
from models import AgentResult

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_BACKOFF_BASE = 15.0
_MAX_BACKOFF = 120.0
_MAX_RETRIES = 5


class BaseAgent:
    agent_name: str = "base"
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 4000
    tools: list = [{"type": "web_search_20250305", "name": "web_search"}]

    def __init__(self):
        self._client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self._system_prompt = (
            _PROMPTS_DIR / f"{self.agent_name}.md"
        ).read_text(encoding="utf-8")

    async def run(self, ticker: str, financial_block: str) -> AgentResult:
        user_content = f"Analyze ticker: {ticker}\n\n{financial_block}"
        last_error: str | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                kwargs: dict = {
                    "model": self.model,
                    "max_tokens": self.max_tokens,
                    "system": [
                        {
                            "type": "text",
                            "text": self._system_prompt,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    "messages": [{"role": "user", "content": user_content}],
                }
                if self.tools:
                    kwargs["tools"] = self.tools

                response = await self._client.messages.create(**kwargs)
                full_text = self._extract_text(response)
                raw_score, recommendation, rationale = self.parse_score(full_text)
                return AgentResult(
                    agent_name=self.agent_name,
                    ticker=ticker,
                    raw_score=raw_score,
                    recommendation=recommendation,
                    rationale=rationale,
                    raw_response=full_text,
                    report=self._extract_report(full_text),
                )

            except anthropic.RateLimitError as e:
                last_error = str(e)
                wait = min(_BACKOFF_BASE * (2**attempt), _MAX_BACKOFF)
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
        return "\n".join(
            block.text for block in response.content if hasattr(block, "text")
        )

    def _extract_report(self, text: str) -> str:
        skip = re.compile(
            r"^(SCORE|RECOMMENDATION|GROWTH POTENTIAL|FINANCIAL STATE|RATIONALE):",
            re.IGNORECASE,
        )
        lines = [l for l in text.strip().splitlines() if not skip.match(l.strip())]
        return "\n".join(lines).strip()

    def parse_score(self, response: str) -> tuple[float | None, str | None, str | None]:
        score_m = re.search(r"SCORE:\s*([\d.]+)", response, re.IGNORECASE)
        rec_m = re.search(r"RECOMMENDATION:\s*(.+)", response, re.IGNORECASE)
        rat_m = re.search(r"RATIONALE:\s*(.+)", response, re.IGNORECASE)
        score = float(score_m.group(1)) if score_m else None
        rec = rec_m.group(1).strip() if rec_m else None
        rationale = rat_m.group(1).strip() if rat_m else None
        return score, rec, rationale
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend
python -m pytest tests/test_base_agent_parse.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add agents/base_agent.py tests/test_base_agent_parse.py
git commit -m "feat: restructure BaseAgent — system/user split, prompt caching, financial_block param, rationale"
```

---

## Task 6: Update PreScreenerAgent (3-tuple parse_score, Haiku, max_tokens 300)

**Files:**
- Modify: `backend/agents/pre_screener.py`

- [ ] **Step 1: Replace pre_screener.py entirely**

```python
from __future__ import annotations
import re
from agents.base_agent import BaseAgent
from models import AgentResult
from services.normalizer import derive_pre_screener


class PreScreenerAgent(BaseAgent):
    agent_name = "pre_screener"
    model = "claude-haiku-4-5-20251001"
    max_tokens = 300
    tools: list = []

    def parse_score(self, response: str) -> tuple[float | None, str | None, str | None]:
        rec_m = re.search(r"RECOMMENDATION:\s*(.+)", response, re.IGNORECASE)
        growth_m = re.search(r"GROWTH POTENTIAL:\s*(.+)", response, re.IGNORECASE)
        fin_m = re.search(r"FINANCIAL STATE:\s*(.+)", response, re.IGNORECASE)
        rat_m = re.search(r"RATIONALE:\s*(.+)", response, re.IGNORECASE)

        rec = rec_m.group(1).strip() if rec_m else None
        growth = growth_m.group(1).strip() if growth_m else None
        fin = fin_m.group(1).strip() if fin_m else None
        rationale = rat_m.group(1).strip() if rat_m else None

        derived = derive_pre_screener(rec, growth, fin)
        return derived, rec, rationale
```

- [ ] **Step 2: Verify existing normalizer tests still pass**

```bash
cd backend
python -m pytest tests/ -v
```
Expected: all existing tests pass

- [ ] **Step 3: Commit**

```bash
git add agents/pre_screener.py
git commit -m "feat: PreScreenerAgent → Haiku, no tools, 3-tuple parse_score"
```

---

## Task 7: Update remaining 5 agent classes

**Files:**
- Modify: `backend/agents/canslim.py`
- Modify: `backend/agents/lynch_garp.py`
- Modify: `backend/agents/buffett_munger.py`
- Modify: `backend/agents/business_engine.py`
- Modify: `backend/agents/growth_stock.py`

- [ ] **Step 1: Replace canslim.py**

```python
from agents.base_agent import BaseAgent


class CANSLIMAgent(BaseAgent):
    agent_name = "canslim"
    model = "claude-haiku-4-5-20251001"
    max_tokens = 300
    tools: list = []
```

- [ ] **Step 2: Replace lynch_garp.py**

```python
from agents.base_agent import BaseAgent


class LynchGarpAgent(BaseAgent):
    agent_name = "lynch_garp"
    model = "claude-haiku-4-5-20251001"
    max_tokens = 300
    tools: list = []
```

- [ ] **Step 3: Replace buffett_munger.py**

```python
from agents.base_agent import BaseAgent


class BuffettMungerAgent(BaseAgent):
    agent_name = "buffett_munger"
    max_tokens = 400
```

- [ ] **Step 4: Replace business_engine.py**

```python
from agents.base_agent import BaseAgent


class BusinessEngineAgent(BaseAgent):
    agent_name = "business_engine"
    max_tokens = 400
```

- [ ] **Step 5: Replace growth_stock.py**

```python
from agents.base_agent import BaseAgent


class GrowthStockAgent(BaseAgent):
    agent_name = "growth_stock"
    max_tokens = 400
```

- [ ] **Step 6: Run all tests**

```bash
cd backend
python -m pytest tests/ -v
```
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add agents/canslim.py agents/lynch_garp.py agents/buffett_munger.py agents/business_engine.py agents/growth_stock.py
git commit -m "feat: model tiering — Haiku for CANSLIM/Lynch/PreScreener; Sonnet stays for BM/BE/GS"
```

---

## Task 8: Update orchestrator/batch.py (pre-fetch financial block, abort on failure)

`analyse_ticker` must pre-fetch the financial block and pass it to every agent. If the pre-fetch fails, return a `failed` TickerResult immediately without running any agents.

**Files:**
- Modify: `backend/orchestrator/batch.py`

- [ ] **Step 1: Replace batch.py entirely**

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
from services.yahoo import fetch_ticker_info, extract_financials, format_financial_block
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


async def _run_agent(key: str, cls, ticker: str, financial_block: str) -> tuple[str, AgentResult]:
    async with _semaphore:
        agent = cls()
        result = await agent.run(ticker, financial_block)
        result = apply_normalisation(key, result)
        return key, result


async def _run_fv(key: str, fn, ticker: str) -> tuple[str, FairValueResult]:
    return key, await fn(ticker)


async def analyse_ticker(ticker: str) -> TickerResult:
    """Run all 9 analyses for a single ticker. Aborts if yfinance pre-fetch fails."""
    financial_block = await format_financial_block(ticker)
    if financial_block is None:
        return TickerResult(
            ticker=ticker,
            status="failed",
            errors=["yfinance data unavailable"],
        )

    agent_tasks = [_run_agent(k, cls, ticker, financial_block) for k, cls in _AGENTS.items()]
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

    groups = [tickers[i : i + BATCH_SIZE] for i in range(0, len(tickers), BATCH_SIZE)]

    for group in groups:
        if cancel_event.is_set():
            break

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

- [ ] **Step 2: Run all backend tests**

```bash
cd backend
python -m pytest tests/ -v
```
Expected: all pass

- [ ] **Step 3: Smoke-test the live path manually (optional but recommended)**

Start uvicorn and test a single ticker via curl:
```bash
uvicorn main:app --reload
curl -X POST http://localhost:8000/api/analyse \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["AAPL"], "mode": "live"}'
```
(mode field doesn't exist yet — that's Task 11. This just confirms the live path still boots.)

- [ ] **Step 4: Commit**

```bash
git add orchestrator/batch.py
git commit -m "feat: orchestrator pre-fetches yfinance block per ticker; aborts on failure"
```

---

## Task 9: Build batch_service.py

Handles building Anthropic Batch API requests, submitting the job, polling status, cancelling, and aggregating results when done.

**Files:**
- Create: `backend/services/batch_service.py`
- Create: `backend/tests/test_batch_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_batch_service.py`:
```python
from services.batch_service import build_batch_requests, _parse_custom_id


def test_build_batch_requests_generates_six_per_ticker():
    blocks = {"AAPL": "## Financial Data..."}
    requests = build_batch_requests("job123", blocks)
    assert len(requests) == 6


def test_build_batch_requests_encodes_custom_id():
    blocks = {"AAPL": "## Financial Data..."}
    requests = build_batch_requests("job123", blocks)
    ids = {r["custom_id"] for r in requests}
    assert "job123__AAPL__buffett_munger" in ids
    assert "job123__AAPL__canslim" in ids
    assert "job123__AAPL__pre_screener" in ids


def test_build_batch_requests_haiku_agents_have_no_tools():
    blocks = {"AAPL": "## Financial Data..."}
    requests = build_batch_requests("job123", blocks)
    haiku_agents = {"canslim", "lynch_garp", "pre_screener"}
    for req in requests:
        _, _, agent_name = _parse_custom_id(req["custom_id"])
        if agent_name in haiku_agents:
            assert "tools" not in req["params"] or req["params"].get("tools") == []


def test_parse_custom_id():
    job_id, ticker, agent_name = _parse_custom_id("job123__AAPL__buffett_munger")
    assert job_id == "job123"
    assert ticker == "AAPL"
    assert agent_name == "buffett_munger"


def test_build_batch_requests_multiple_tickers():
    blocks = {"AAPL": "data1", "MSFT": "data2"}
    requests = build_batch_requests("job1", blocks)
    assert len(requests) == 12  # 2 tickers × 6 agents
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend
python -m pytest tests/test_batch_service.py -v
```
Expected: `FAILED` — `ModuleNotFoundError: No module named 'services.batch_service'`

- [ ] **Step 3: Create batch_service.py**

Create `backend/services/batch_service.py`:
```python
from __future__ import annotations
import asyncio, json, os
from datetime import datetime, timezone
from pathlib import Path
import anthropic
from models import AgentResult, FairValueResult, TickerResult, BatchJobFile
from agents.buffett_munger import BuffettMungerAgent
from agents.lynch_garp import LynchGarpAgent
from agents.growth_stock import GrowthStockAgent
from agents.business_engine import BusinessEngineAgent
from agents.canslim import CANSLIMAgent
from agents.pre_screener import PreScreenerAgent
from valuation.gemini_fv import run as gemini_fv_run
from valuation.calculator_1 import run as calc1_run
from valuation.calculator_2 import run as calc2_run
from services.yahoo import fetch_ticker_info, extract_financials, format_financial_block
from services.normalizer import apply_normalisation
from services.sheets import upsert_result
from orchestrator.aggregator import aggregate

_JOBS_DIR = Path(__file__).parent.parent / "jobs"

_AGENTS = {
    "buffett_munger": BuffettMungerAgent,
    "lynch_garp": LynchGarpAgent,
    "growth_stock": GrowthStockAgent,
    "business_engine": BusinessEngineAgent,
    "canslim": CANSLIMAgent,
    "pre_screener": PreScreenerAgent,
}


# ── Job file helpers ──────────────────────────────────────────────────────────

def _jobs_dir() -> Path:
    _JOBS_DIR.mkdir(exist_ok=True)
    return _JOBS_DIR


def write_job_file(job: BatchJobFile) -> None:
    path = _jobs_dir() / f"{job.job_id}.json"
    path.write_text(job.model_dump_json(), encoding="utf-8")


def read_job_file(job_id: str) -> BatchJobFile | None:
    path = _jobs_dir() / f"{job_id}.json"
    if not path.exists():
        return None
    return BatchJobFile.model_validate_json(path.read_text(encoding="utf-8"))


def update_job_status(job_id: str, status: str) -> None:
    job = read_job_file(job_id)
    if job:
        job.status = status
        write_job_file(job)


# ── Batch request building ────────────────────────────────────────────────────

def _parse_custom_id(custom_id: str) -> tuple[str, str, str]:
    parts = custom_id.split("__")
    return parts[0], parts[1], parts[2]


def build_batch_requests(
    job_id: str,
    ticker_blocks: dict[str, str],
) -> list[dict]:
    requests = []
    for ticker, financial_block in ticker_blocks.items():
        for agent_name, agent_cls in _AGENTS.items():
            agent = agent_cls()
            user_content = f"Analyze ticker: {ticker}\n\n{financial_block}"
            params: dict = {
                "model": agent.model,
                "max_tokens": agent.max_tokens,
                "system": [
                    {
                        "type": "text",
                        "text": agent._system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                "messages": [{"role": "user", "content": user_content}],
            }
            if agent.tools:
                params["tools"] = agent.tools
            requests.append({
                "custom_id": f"{job_id}__{ticker}__{agent_name}",
                "params": params,
            })
    return requests


# ── Submit / status / cancel ──────────────────────────────────────────────────

async def submit_batch_job(
    job_id: str,
    tickers: list[str],
) -> dict:
    """Pre-fetch yfinance blocks, submit batch, write job file. Returns {job_id, failed_prefetch}."""
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    ticker_blocks: dict[str, str] = {}
    failed_prefetch: list[str] = []

    for ticker in tickers:
        block = await format_financial_block(ticker)
        if block is None:
            failed_prefetch.append(ticker)
        else:
            ticker_blocks[ticker] = block

    if not ticker_blocks:
        raise ValueError("All tickers failed yfinance pre-fetch")

    requests = build_batch_requests(job_id, ticker_blocks)
    batch = await client.messages.batches.create(requests=requests)

    job = BatchJobFile(
        job_id=job_id,
        batch_id=batch.id,
        tickers=list(ticker_blocks.keys()),
        failed_prefetch=failed_prefetch,
        status="processing",
        submitted_at=datetime.now(timezone.utc).isoformat(),
    )
    write_job_file(job)

    return {"job_id": job_id, "failed_prefetch": failed_prefetch}


async def get_batch_status(job_id: str) -> dict:
    job = read_job_file(job_id)
    if not job:
        return {"error": "job not found"}

    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    batch = await client.messages.batches.retrieve(job.batch_id)

    counts = batch.request_counts
    total = counts.processing + counts.succeeded + counts.errored
    return {
        "job_id": job_id,
        "status": batch.processing_status,
        "submitted_at": job.submitted_at,
        "failed_prefetch": job.failed_prefetch,
        "request_counts": {
            "processing": counts.processing,
            "succeeded": counts.succeeded,
            "errored": counts.errored,
            "total": total,
        },
    }


async def cancel_batch_job(job_id: str) -> bool:
    job = read_job_file(job_id)
    if not job:
        return False
    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    await client.messages.batches.cancel(job.batch_id)
    update_job_status(job_id, "cancelled")
    return True


# ── Results ───────────────────────────────────────────────────────────────────

async def fetch_and_aggregate_results(job_id: str) -> list[TickerResult]:
    """Parse Anthropic batch results, run FV scripts, aggregate per ticker, upsert to Sheets."""
    job = read_job_file(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    # Collect raw agent results per ticker
    agent_results_by_ticker: dict[str, dict[str, AgentResult]] = {
        t: {} for t in job.tickers
    }

    async for result in client.messages.batches.results(job.batch_id):
        job_id_parsed, ticker, agent_name = _parse_custom_id(result.custom_id)
        if ticker not in agent_results_by_ticker:
            continue

        if result.result.type == "succeeded":
            msg = result.result.message
            full_text = "\n".join(
                b.text for b in msg.content if hasattr(b, "text")
            )
            agent_cls = _AGENTS.get(agent_name)
            if agent_cls:
                agent = agent_cls()
                raw_score, recommendation, rationale = agent.parse_score(full_text)
                ar = AgentResult(
                    agent_name=agent_name,
                    ticker=ticker,
                    raw_score=raw_score,
                    recommendation=recommendation,
                    rationale=rationale,
                    raw_response=full_text,
                )
                ar = apply_normalisation(agent_name, ar)
                agent_results_by_ticker[ticker][agent_name] = ar
        else:
            agent_results_by_ticker[ticker][agent_name] = AgentResult(
                agent_name=agent_name,
                ticker=ticker,
                status="failed",
                error=f"batch result: {result.result.type}",
            )

    # For each ticker: run FV scripts + fetch company info concurrently, then aggregate
    ticker_results: list[TickerResult] = []

    async def _process_ticker(ticker: str) -> TickerResult:
        fv_tasks = [
            asyncio.create_task(_run_fv("gemini_fv", gemini_fv_run, ticker)),
            asyncio.create_task(_run_fv("calculator_1", calc1_run, ticker)),
            asyncio.create_task(_run_fv("calculator_2", calc2_run, ticker)),
        ]
        fv_raw = await asyncio.gather(*fv_tasks, return_exceptions=True)

        fv_results: dict[str, FairValueResult] = {}
        for i, res in enumerate(fv_raw):
            key = ["gemini_fv", "calculator_1", "calculator_2"][i]
            if isinstance(res, Exception):
                fv_results[key] = FairValueResult(
                    ticker=ticker, method_name=key, status="failed", error=str(res)
                )
            else:
                _, fvr = res
                fv_results[key] = fvr

        company_name = None
        current_price = None
        try:
            info = await fetch_ticker_info(ticker)
            fin = extract_financials(info)
            company_name = fin.get("company_name")
            current_price = fin.get("current_price")
        except Exception:
            pass

        return aggregate(
            ticker,
            company_name,
            current_price,
            agent_results_by_ticker[ticker],
            fv_results,
        )

    results = await asyncio.gather(
        *[_process_ticker(t) for t in job.tickers], return_exceptions=True
    )

    for res in results:
        if isinstance(res, Exception):
            continue
        ticker_results.append(res)
        if res.status != "failed":
            try:
                await upsert_result(res)
            except Exception:
                pass

    update_job_status(job_id, "completed")
    return ticker_results


async def _run_fv(key: str, fn, ticker: str):
    return key, await fn(ticker)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd backend
python -m pytest tests/test_batch_service.py -v
```
Expected: 5 passed

- [ ] **Step 5: Run full test suite**

```bash
cd backend
python -m pytest tests/ -v
```
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add services/batch_service.py tests/test_batch_service.py
git commit -m "feat: batch_service — submit/status/cancel/results with yfinance pre-fetch and FV aggregation"
```

---

## Task 10: Build routers/jobs.py

**Files:**
- Create: `backend/routers/jobs.py`

- [ ] **Step 1: Create routers/jobs.py**

```python
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from services.batch_service import get_batch_status, cancel_batch_job, fetch_and_aggregate_results, read_job_file

router = APIRouter()


@router.get("/jobs/{job_id}/status")
async def job_status(job_id: str):
    result = await get_batch_status(job_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/jobs/{job_id}/results")
async def job_results(job_id: str):
    job = read_job_file(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == "processing":
        raise HTTPException(status_code=202, detail="Batch still processing")
    try:
        ticker_results = await fetch_and_aggregate_results(job_id)
        return {
            "job_id": job_id,
            "ticker_results": [r.model_dump() for r in ticker_results],
            "failed_prefetch": job.failed_prefetch,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/jobs/{job_id}")
async def cancel_job(job_id: str):
    cancelled = await cancel_batch_job(job_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"cancelled": True}
```

- [ ] **Step 2: Commit**

```bash
git add routers/jobs.py
git commit -m "feat: jobs router — status, results, cancel endpoints"
```

---

## Task 11: Update analysis.py + register jobs router in main.py

**Files:**
- Modify: `backend/routers/analysis.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Add mode field to AnalyseRequest in models.py**

In `backend/models.py`, update `AnalyseRequest`:
```python
from typing import Literal

class AnalyseRequest(BaseModel):
    tickers: list[str] = []
    sheets_url: str | None = None
    mode: Literal["live", "batch"] = "batch"
```

- [ ] **Step 2: Update analysis.py to route batch jobs**

Replace `backend/routers/analysis.py` entirely:
```python
from __future__ import annotations
import asyncio, json, uuid
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
from models import AnalyseRequest
from services.yahoo import validate_ticker
from services.sheets import read_tickers
from services.batch_service import submit_batch_job
from orchestrator.batch import run_batch

router = APIRouter()

_jobs: dict[str, dict] = {}
_cancel_events: dict[str, asyncio.Event] = {}


@router.post("/analyse")
async def start_analysis(request: AnalyseRequest):
    tickers: list[str] = []

    if request.tickers:
        tickers.extend([t.strip().upper() for t in request.tickers if t.strip()])

    if request.sheets_url and not request.tickers:
        try:
            sheet_tickers = await read_tickers()
            tickers.extend([t.upper() for t in sheet_tickers if t not in tickers])
        except Exception as e:
            if not tickers:
                return {"error": f"No tickers provided and Sheets read failed: {e}"}

    if not tickers:
        return {"error": "No tickers provided"}

    valid_results = await asyncio.gather(*[validate_ticker(t) for t in tickers])
    valid_tickers = [t for t, ok in zip(tickers, valid_results) if ok]
    invalid_tickers = [t for t, ok in zip(tickers, valid_results) if not ok]

    if not valid_tickers:
        return {"error": "No valid tickers found", "invalid": invalid_tickers}

    job_id = str(uuid.uuid4())

    if request.mode == "batch":
        try:
            result = await submit_batch_job(job_id, valid_tickers)
            return {
                "job_id": job_id,
                "mode": "batch",
                "total": len(valid_tickers),
                "invalid": invalid_tickers,
                "failed_prefetch": result.get("failed_prefetch", []),
            }
        except ValueError as e:
            return {"error": str(e)}

    # Live mode (SSE)
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
    asyncio.create_task(_run_job(job_id, valid_tickers, cancel_event))
    return {"job_id": job_id, "mode": "live", "total": len(valid_tickers), "invalid": invalid_tickers}


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
            for result in results[last_sent:]:
                yield {"event": "ticker_done", "data": json.dumps(result)}
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

- [ ] **Step 3: Register jobs router in main.py**

In `backend/main.py`, add the jobs router:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers.analysis import router as analysis_router
from routers.database import router as database_router
from routers.jobs import router as jobs_router

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
app.include_router(jobs_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Run all backend tests**

```bash
cd backend
python -m pytest tests/ -v
```
Expected: all pass

- [ ] **Step 5: Smoke-test batch submission**

```bash
uvicorn main:app --reload
curl -X POST http://localhost:8000/api/analyse \
  -H "Content-Type: application/json" \
  -d '{"tickers": ["AAPL"], "mode": "batch"}'
```
Expected: `{"job_id": "...", "mode": "batch", "total": 1, "invalid": [], "failed_prefetch": []}`

Then poll status:
```bash
curl http://localhost:8000/api/jobs/{job_id}/status
```
Expected: `{"job_id": "...", "status": "in_progress", "request_counts": {...}}`

- [ ] **Step 6: Commit**

```bash
git add routers/analysis.py main.py models.py
git commit -m "feat: analysis router routes to batch or live path via mode field; register jobs router"
```

---

## Task 12: Frontend — update types.ts

**Files:**
- Modify: `frontend/src/types.ts`

- [ ] **Step 1: Add rationale to AgentResult and add BatchJobStatus**

In `frontend/src/types.ts`, update `AgentResult` and add `BatchJobStatus`:

```typescript
export interface AgentResult {
  agent_name: string
  ticker: string
  raw_score: number | null
  normalised_score: number | null
  recommendation: string | null
  rationale: string | null
  raw_response: string
  report: string
  status: 'completed' | 'failed'
  error: string | null
}
```

Add after the existing `JobStatus` interface:
```typescript
export interface BatchRequestCounts {
  processing: number
  succeeded: number
  errored: number
  total: number
}

export interface BatchJobStatus {
  job_id: string
  status: 'in_progress' | 'ended' | 'canceling' | 'canceled'
  submitted_at: string
  failed_prefetch: string[]
  request_counts: BatchRequestCounts
}

export interface BatchJobResults {
  job_id: string
  ticker_results: TickerResult[]
  failed_prefetch: string[]
}
```

- [ ] **Step 2: Commit**

```bash
cd frontend
git add src/types.ts
git commit -m "feat: add rationale to AgentResult; add BatchJobStatus and BatchJobResults types"
```

---

## Task 13: Frontend — Home.tsx mode toggle

**Files:**
- Modify: `frontend/src/pages/Home.tsx`

- [ ] **Step 1: Replace Home.tsx entirely**

```tsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const API = 'http://localhost:8000'
const MODE_KEY = 'analysis_mode'

export default function Home() {
  const [tickers, setTickers] = useState('')
  const [useSheets, setUseSheets] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mode, setMode] = useState<'batch' | 'live'>(() => {
    return (localStorage.getItem(MODE_KEY) as 'batch' | 'live') ?? 'batch'
  })
  const navigate = useNavigate()

  useEffect(() => {
    localStorage.setItem(MODE_KEY, mode)
  }, [mode])

  const handleAnalyse = async () => {
    setLoading(true)
    setError(null)
    try {
      const tickerList = tickers
        .split(/[\s,]+/)
        .map(t => t.trim().toUpperCase())
        .filter(Boolean)

      const body: Record<string, unknown> = { mode }
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
      } else if (data.mode === 'batch') {
        navigate(`/jobs/${data.job_id}`, {
          state: { total: data.total, invalid: data.invalid, failedPrefetch: data.failed_prefetch },
        })
      } else {
        navigate(`/progress/${data.job_id}`, { state: { total: data.total, invalid: data.invalid } })
      }
    } catch {
      setError('Failed to connect to backend. Is uvicorn running on port 8000?')
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

        {/* Mode toggle */}
        <div>
          <label className="block text-xs text-slate-500 uppercase tracking-wide mb-2">
            Analysis Mode
          </label>
          <div className="flex rounded overflow-hidden border border-[#1e1e2a]">
            <button
              onClick={() => setMode('live')}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${
                mode === 'live'
                  ? 'bg-blue-700 text-white'
                  : 'bg-[#0a0a0f] text-slate-400 hover:text-slate-200'
              }`}
            >
              ⚡ Run now
            </button>
            <button
              onClick={() => setMode('batch')}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${
                mode === 'batch'
                  ? 'bg-green-800 text-white'
                  : 'bg-[#0a0a0f] text-slate-400 hover:text-slate-200'
              }`}
            >
              💰 Batch — cheaper
            </button>
          </div>
          <p className="text-xs text-slate-600 mt-1">
            {mode === 'batch'
              ? 'Results ready in 15–60 min. ~$0.21/ticker.'
              : 'Live streaming results. ~$0.34/ticker.'}
          </p>
        </div>

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
          {loading ? 'Submitting...' : mode === 'batch' ? 'Submit Batch' : 'Analyse Now'}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
cd frontend
git add src/pages/Home.tsx
git commit -m "feat: Home.tsx — mode toggle (Batch default), navigate to /jobs/:jobId for batch"
```

---

## Task 14: Frontend — JobStatus.tsx (new page)

**Files:**
- Create: `frontend/src/pages/JobStatus.tsx`

- [ ] **Step 1: Create JobStatus.tsx**

```tsx
import { useState, useEffect, useCallback } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import type { BatchJobStatus, BatchJobResults, TickerResult } from '../types'
import ScoreBadge from '../components/ScoreBadge'

const API = 'http://localhost:8000'
const POLL_INTERVAL_MS = 30_000

export default function JobStatus() {
  const { jobId } = useParams<{ jobId: string }>()
  const location = useLocation()
  const navigate = useNavigate()
  const [status, setStatus] = useState<BatchJobStatus | null>(null)
  const [results, setResults] = useState<TickerResult[] | null>(null)
  const [failedPrefetch, setFailedPrefetch] = useState<string[]>(
    location.state?.failedPrefetch ?? []
  )
  const [error, setError] = useState<string | null>(null)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)
  const [cancelling, setCancelling] = useState(false)

  const fetchStatus = useCallback(async () => {
    if (!jobId) return
    try {
      const res = await fetch(`${API}/api/jobs/${jobId}/status`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: BatchJobStatus = await res.json()
      setStatus(data)
      setLastChecked(new Date())
      if (data.status === 'ended') {
        await fetchResults()
      }
    } catch (e) {
      setError(String(e))
    }
  }, [jobId])

  const fetchResults = useCallback(async () => {
    if (!jobId) return
    try {
      const res = await fetch(`${API}/api/jobs/${jobId}/results`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: BatchJobResults = await res.json()
      setResults(data.ticker_results)
      setFailedPrefetch(data.failed_prefetch)
    } catch (e) {
      setError(String(e))
    }
  }, [jobId])

  const handleCancel = async () => {
    if (!jobId || cancelling) return
    setCancelling(true)
    await fetch(`${API}/api/jobs/${jobId}`, { method: 'DELETE' })
    setCancelling(false)
    navigate('/')
  }

  // Initial fetch + polling
  useEffect(() => {
    fetchStatus()
    const interval = setInterval(() => {
      if (!results) fetchStatus()
    }, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [fetchStatus, results])

  const progress = status?.request_counts
    ? Math.round(
        ((status.request_counts.succeeded + status.request_counts.errored) /
          Math.max(status.request_counts.total, 1)) *
          100
      )
    : 0

  const isDone = status?.status === 'ended' || status?.status === 'canceled'

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-xl font-bold text-slate-100 mb-1">Batch Job</h1>
      <p className="text-xs text-slate-500 font-mono mb-6">{jobId}</p>

      {!isDone && (
        <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg p-6 mb-6">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-slate-300">
              {status ? (
                <>
                  {status.request_counts.succeeded + status.request_counts.errored} /{' '}
                  {status.request_counts.total} agent calls complete
                </>
              ) : (
                'Checking status...'
              )}
            </span>
            <span className="text-xs text-slate-500">{progress}%</span>
          </div>

          <div className="w-full bg-[#0a0a0f] rounded-full h-2 mb-4">
            <div
              className="bg-green-600 h-2 rounded-full transition-all duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>

          <p className="text-xs text-slate-500 mb-4">
            Batch jobs typically complete in 15–60 min. Submitted:{' '}
            {status?.submitted_at
              ? new Date(status.submitted_at).toLocaleTimeString()
              : '—'}
          </p>

          {error && (
            <div className="text-red-400 text-sm bg-red-900/20 border border-red-900 rounded px-3 py-2 mb-3">
              {error}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={fetchStatus}
              className="px-4 py-2 text-sm bg-[#1e1e2a] hover:bg-[#2a2a3a] text-slate-300 rounded transition-colors"
            >
              Check now
            </button>
            <button
              onClick={handleCancel}
              disabled={cancelling}
              className="px-4 py-2 text-sm bg-red-900/30 hover:bg-red-900/50 text-red-400 rounded transition-colors"
            >
              {cancelling ? 'Cancelling...' : 'Cancel'}
            </button>
          </div>

          {lastChecked && (
            <p className="text-xs text-slate-600 mt-2">
              Last checked: {lastChecked.toLocaleTimeString()}
            </p>
          )}

          {/* >2 hour warning */}
          {status?.submitted_at && (() => {
            const elapsed = Date.now() - new Date(status.submitted_at).getTime()
            return elapsed > 2 * 60 * 60 * 1000 ? (
              <div className="mt-3 text-yellow-400 text-xs bg-yellow-900/20 border border-yellow-900/50 rounded px-3 py-2">
                This batch is taking longer than expected. You can wait or cancel and resubmit as Run now.
              </div>
            ) : null
          })()}
        </div>
      )}

      {failedPrefetch.length > 0 && (
        <div className="bg-red-900/10 border border-red-900/50 rounded-lg p-4 mb-6">
          <p className="text-xs text-red-400 font-semibold mb-1">
            Tickers aborted (yfinance data unavailable):
          </p>
          <p className="text-xs text-red-300 font-mono">{failedPrefetch.join(', ')}</p>
        </div>
      )}

      {results && (
        <div>
          <h2 className="text-lg font-semibold text-slate-200 mb-4">
            Results — {results.length} ticker{results.length !== 1 ? 's' : ''}
          </h2>
          <div className="bg-[#16161e] border border-[#1e1e2a] rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#1e1e2a] text-xs text-slate-500 uppercase">
                  <th className="text-left px-4 py-3">Ticker</th>
                  <th className="text-left px-4 py-3">Company</th>
                  <th className="text-left px-4 py-3">Score</th>
                  <th className="text-right px-4 py-3">Price</th>
                  <th className="text-right px-4 py-3">FV Gap %</th>
                  <th className="text-left px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {results.map(r => (
                  <tr
                    key={r.ticker}
                    className="border-b border-[#1e1e2a] hover:bg-[#1e1e2a] cursor-pointer"
                    onClick={() =>
                      navigate(`/ticker/batch/${r.ticker}`, { state: { result: r } })
                    }
                  >
                    <td className="px-4 py-3 font-mono font-bold text-slate-100">{r.ticker}</td>
                    <td className="px-4 py-3 text-slate-400 max-w-[180px] truncate">
                      {r.company_name ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      <ScoreBadge score={r.overall_final_score} />
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-slate-300">
                      {r.current_price != null ? `$${r.current_price.toFixed(2)}` : '—'}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      {r.price_vs_fair_value_pct != null ? (
                        <span
                          className={
                            r.price_vs_fair_value_pct > 0 ? 'text-green-400' : 'text-red-400'
                          }
                        >
                          {r.price_vs_fair_value_pct > 0 ? '+' : ''}
                          {r.price_vs_fair_value_pct.toFixed(1)}%
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-xs px-2 py-0.5 rounded ${
                          r.status === 'completed'
                            ? 'bg-green-900/30 text-green-400'
                            : r.status === 'partial'
                            ? 'bg-yellow-900/30 text-yellow-400'
                            : 'bg-red-900/30 text-red-400'
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
cd frontend
git add src/pages/JobStatus.tsx
git commit -m "feat: JobStatus page — polls batch job status every 30s, shows results table when done"
```

---

## Task 15: Frontend — AgentCard.tsx (show rationale) + TickerDetail.tsx (remove collapsibles)

**Files:**
- Modify: `frontend/src/components/AgentCard.tsx`
- Modify: `frontend/src/pages/TickerDetail.tsx`

- [ ] **Step 1: Update AgentCard.tsx to show rationale**

Replace `frontend/src/components/AgentCard.tsx` entirely:
```tsx
import type { AgentResult } from '../types'
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
    <div
      className={cn(
        'bg-[#16161e] border rounded-lg p-4',
        result.status === 'failed' ? 'border-red-900' : 'border-[#1e1e2a]'
      )}
    >
      <div className="text-xs text-slate-500 mb-1 uppercase tracking-wide">{label}</div>
      {result.status === 'failed' ? (
        <div className="text-red-400 text-sm">Failed</div>
      ) : (
        <>
          <ScoreBadge score={result.normalised_score} size="lg" />
          {result.recommendation && (
            <div className="text-xs text-slate-400 mt-1">{result.recommendation}</div>
          )}
          {result.rationale && (
            <div className="text-xs text-slate-500 mt-1 italic leading-snug">
              {result.rationale}
            </div>
          )}
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Read the full TickerDetail.tsx before editing**

Read `frontend/src/pages/TickerDetail.tsx` to see the complete file, then remove the `expandedAgent` state and the collapsible sections that render the full `raw_response` / `report`. Keep the agent card grid and fair value panel. The file currently has an `expandedAgent` state and renders collapsible report blocks — remove those. The resulting file should be:

```tsx
import { useParams, useLocation, Link } from 'react-router-dom'
import type { TickerResult } from '../types'
import ScoreBadge from '../components/ScoreBadge'
import AgentCard from '../components/AgentCard'
import FairValuePanel from '../components/FairValuePanel'

const AGENTS = ['buffett_munger', 'lynch_garp', 'growth_stock', 'business_engine', 'canslim', 'pre_screener']

export default function TickerDetail() {
  const { jobId } = useParams()
  const location = useLocation()
  const result: TickerResult | undefined = location.state?.result

  if (!result) {
    return (
      <div className="text-slate-500 text-center py-20">
        Result not found. <Link to="/" className="text-blue-400">Go home</Link>.
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="mb-4">
        <button
          onClick={() => window.history.back()}
          className="text-xs text-slate-500 hover:text-slate-300"
        >
          ← Back
        </button>
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
            {result.overall_label && (
              <div className="text-xs text-slate-500 mt-1">{result.overall_label}</div>
            )}
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

      <FairValuePanel result={result} />

      {result.errors.length > 0 && (
        <div className="mt-6 bg-red-900/10 border border-red-900/50 rounded-lg p-4">
          <p className="text-xs text-red-400 font-semibold mb-2">Errors</p>
          <ul className="text-xs text-red-300 space-y-1">
            {result.errors.map((e, i) => <li key={i}>{e}</li>)}
          </ul>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
cd frontend
git add src/components/AgentCard.tsx src/pages/TickerDetail.tsx
git commit -m "feat: AgentCard shows rationale; TickerDetail removes collapsible report sections"
```

---

## Task 16: Frontend — App.tsx routing

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add /jobs/:jobId route**

Replace `frontend/src/App.tsx` entirely:
```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Progress from './pages/Progress'
import Results from './pages/Results'
import TickerDetail from './pages/TickerDetail'
import Database from './pages/Database'
import JobStatus from './pages/JobStatus'

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/progress/:jobId" element={<Progress />} />
          <Route path="/results/:jobId" element={<Results />} />
          <Route path="/jobs/:jobId" element={<JobStatus />} />
          <Route path="/ticker/:jobId/:ticker" element={<TickerDetail />} />
          <Route path="/database" element={<Database />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  )
}
```

- [ ] **Step 2: Run TypeScript check**

```bash
cd frontend
npm run build
```
Expected: builds without errors

- [ ] **Step 3: Commit**

```bash
git add src/App.tsx
git commit -m "feat: add /jobs/:jobId route for batch job status page"
```

---

## Task 17: End-to-end smoke test

- [ ] **Step 1: Start the app**

```bash
# Terminal 1
cd backend && uvicorn main:app --reload

# Terminal 2
cd frontend && npm run dev
```

- [ ] **Step 2: Test live mode**

1. Open `http://localhost:5173`
2. Select "⚡ Run now"
3. Enter a single ticker (e.g. `MSFT`)
4. Click "Analyse Now"
5. Confirm redirect to `/progress/...` and SSE streaming works as before

- [ ] **Step 3: Test batch mode (default)**

1. Select "💰 Batch — cheaper" (should be default)
2. Enter a ticker (e.g. `AAPL`)
3. Click "Submit Batch"
4. Confirm redirect to `/jobs/{job_id}`
5. Confirm progress bar appears and "Check now" button works
6. Confirm `GET /api/jobs/{job_id}/status` returns valid request counts

- [ ] **Step 4: Confirm AgentCard shows rationale**

Once any live-mode result completes, open Ticker Detail and verify each AgentCard shows a one-sentence rationale below the recommendation.

- [ ] **Step 5: Verify yfinance abort behaviour**

Submit an invalid ticker (e.g. `XXXXXX`) in batch mode. Confirm it appears in `failed_prefetch` on the JobStatus page rather than triggering an agent call.

- [ ] **Step 6: Run full backend test suite one last time**

```bash
cd backend
python -m pytest tests/ -v
```
Expected: all pass

- [ ] **Step 7: Final commit**

```bash
git add -A
git commit -m "chore: end-to-end verification complete — cost optimisation shipped"
```
