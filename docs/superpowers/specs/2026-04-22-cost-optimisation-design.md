# Agent Cost Optimisation — Design Spec
**Date:** 2026-04-22
**Status:** Approved
**Builds on:** `docs/superpowers/specs/2026-04-20-stock-app-design.md`

---

## 1. Problem

A single ticker analysis costs ~$2.50, driven by:
- `web_search_20250305` agentic loops: 6 agents × ~8 searches each → accumulated context of 20,000–65,000 input tokens per agent
- All 6 agents independently search for overlapping quantitative data (P/E, EPS, margins, etc.)
- Sonnet 4.6 used for all agents including purely formulaic ones (CANSLIM, Pre-Screener, Lynch GARP)
- Output max_tokens set to 2,000–3,000 per agent; only scores and recommendations are actually used

**Target:** ~$0.21/ticker (batch) or ~$0.34/ticker (live). 100 tickers × 4 runs/year = ~$84/year (down from ~$1,000).

---

## 2. Solution Overview — Option C: Everything Combined

Four levers applied together:

| Lever | Mechanism | Savings |
|---|---|---|
| yfinance data injection | Pre-fetch ~25 metrics per ticker; inject into all agent prompts | Eliminates most searches |
| Model tiering | Haiku 4.5 for 3 formulaic agents; Sonnet 4.6 for 3 judgment agents | ~15% |
| Score-only output | Trim max_tokens to 300–400; output score + 1-sentence rationale only | ~10% |
| Batch API (default mode) | 50% discount on all token costs | ~35–45% on remaining |
| Prompt caching | Cache static system prompts across tickers in a run | ~3% bonus |

---

## 3. Two-Path Architecture

Every analysis job runs through one of two paths, selected by a UI toggle on the Home page (Batch is default):

```
POST /api/analyse  { tickers: [...], mode: "batch" | "live" }

"live" path (Run now):
  yfinance pre-fetch all tickers
  → 6 agents run concurrently per ticker (existing SSE pipeline, optimised)
  → SSE stream to frontend
  → Google Sheets upsert on completion
  Cost: ~$0.34/ticker

"batch" path (Batch — cheaper, default):
  yfinance pre-fetch all tickers
  → build N×6 Batch API requests
  → submit to Anthropic Message Batches API → receive batch_id
  → return job_id to client
  → client polls GET /api/jobs/{job_id}/status every 30s
  → when ended: fetch results, aggregate, upsert to Sheets
  Cost: ~$0.21/ticker
```

---

## 4. yfinance Data Injection

### 4.1 New function: `format_financial_block(ticker) -> str`

Added to `backend/services/yahoo.py`. Fetches ~25 metrics via the existing yfinance client and returns a structured markdown block:

```
## Pre-fetched Financial Data for {TICKER} (via yfinance, {date})
- Current Price: $189.45 | Market Cap: $2.9T
- P/E (TTM): 28.5 | Forward P/E: 24.2 | PEG: 1.8
- EPS (TTM): $6.64 | EPS Growth YoY: +12.3%
- Revenue (TTM): $391B | Revenue Growth YoY: +4.1%
- Gross Margin: 45.2% | Operating Margin: 29.5%
- FCF (TTM): $99B | FCF Yield: 3.4%
- ROE: 147% | ROIC: 55% | Debt/Equity: 1.87
- 52-week High: $220.19 | 52-week Low: $164.08
- Price vs 200-day MA: +8.2% | Beta: 1.24
- Dividend Yield: 0.5% | Institutional Ownership: 61%
- Analyst Consensus: Buy | Avg Price Target: $215
```

Individual fields that return `None` from yfinance render as `N/A`. The block is fetched once per ticker and shared across all 6 agents.

### 4.2 Pre-fetch failure behaviour

If the yfinance fetch fails entirely for a ticker (network error, unknown ticker, etc.):
- The ticker is **aborted immediately**
- Marked `Failed` with error `"yfinance data unavailable"`
- No agents are run — no web search fallback
- Shown inline in Results / Job Status with the error message
- Other tickers in the batch are unaffected

### 4.3 Injection point

The block is prepended to the user message for every agent:

```python
user_message = f"{financial_block}\n\n{agent_specific_prompt.replace('{{TICKER}}', ticker)}"
```

---

## 5. Agent Changes

### 5.1 Model tiering

| Agent | Model | Web search | Max tokens |
|---|---|---|---|
| CANSLIM | `claude-haiku-4-5-20251001` | Removed | 300 |
| Pre-Screener | `claude-haiku-4-5-20251001` | Removed | 300 |
| Lynch GARP | `claude-haiku-4-5-20251001` | Removed | 300 |
| Buffett-Munger | `claude-sonnet-4-6` | Kept, capped at 3 | 400 |
| Business Engine | `claude-sonnet-4-6` | Kept, capped at 3 | 400 |
| Growth Stock | `claude-sonnet-4-6` | Kept, capped at 3 | 400 |

### 5.2 Prompt changes (all 6 agents)

**Haiku agents:** Remove the "Research Instructions / use web search" section entirely. Agents score purely from the injected yfinance block.

**Sonnet agents:** Replace the research instructions section with:
> "The pre-fetched data above covers quantitative metrics. Use web search a maximum of 3 times for qualitative context only — management commentary, recent news, competitive developments not captured in the financial data."

**Note:** The 3-search cap is prompt-level guidance only — the model is instructed to self-limit. It is not enforced at the API level. In practice this is sufficient; adding a hard code-level cap (counting tool_use blocks and truncating) is not worth the complexity.

**All agents — output format trimmed to:**
```
SCORE: [number]
RECOMMENDATION: [label]
RATIONALE: [one sentence, max 20 words]
```

No multi-paragraph analysis. The `RATIONALE` field is stored in `AgentResult` and displayed as a subtitle on each agent card in Ticker Detail.

### 5.3 Prompt caching

All agent calls add `cache_control: {"type": "ephemeral"}` to the system prompt content block. Within a single batch run (100 tickers), after the first ~4 calls per agent type the static system prompt is served from cache at 10% of normal input cost.

```python
"system": [{"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}}]
```

**Implementation note:** Currently `base_agent.py` passes the entire prompt as a user message with no `system` param. To enable caching, `BaseAgent` must be restructured: the static agent instructions become the `system` parameter (cacheable), and the user message becomes the yfinance data block + the ticker placeholder text only. This split is required for `cache_control` to take effect.

---

## 6. Batch API Integration

### 6.1 Submitting a batch

```python
client.messages.batches.create(requests=[
    {
        "custom_id": f"{job_id}__{ticker}__{agent_name}",
        "params": {
            "model": agent.model,
            "max_tokens": agent.max_tokens,
            "tools": agent.tools,   # empty list [] for Haiku agents
            "system": [{"type": "text", "text": system_prompt,
                        "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": user_message}]
        }
    }
    for ticker in tickers
    for agent_name, agent in _AGENTS.items()
])
```

`custom_id` encodes `job_id`, `ticker`, and `agent_name` separated by `__` — enough to reconstruct all results without extra state.

### 6.2 Job lifecycle

```
POST /api/analyse (mode=batch)
  → yfinance pre-fetch all tickers (abort failed tickers)
  → submit batch → receive anthropic_batch_id
  → write job file: backend/jobs/{job_id}.json
     { job_id, batch_id, tickers, status: "processing", submitted_at }
  → return { job_id } to client

GET /api/jobs/{job_id}/status   ← polled every 30s by frontend
  → client.messages.batches.retrieve(batch_id)
  → return { status, request_counts: { processing, succeeded, errored } }

GET /api/jobs/{job_id}/results  ← called once when status == "ended"
  → stream client.messages.batches.results(batch_id)
  → parse custom_id → reconstruct AgentResult per request
  → run aggregator + normaliser (same logic as live path)
  → upsert all results to Google Sheets
  → update job file: status "completed", results written
  → return TickerResult list
```

Job files in `backend/jobs/` persist across server restarts. The status page resumes polling automatically on next visit using the `job_id` from the URL.

### 6.3 New backend files

- `backend/routers/jobs.py` — `GET /api/jobs/{job_id}/status`, `GET /api/jobs/{job_id}/results`, `DELETE /api/jobs/{job_id}` (cancel)
- `backend/services/batch_service.py` — batch request builder, result parser, aggregation bridge
- `backend/jobs/` — directory for per-job JSON files

`backend/routers/analysis.py` gains a `mode` query param and routes to the existing live path or the new batch path.

### 6.4 Cancellation

`DELETE /api/jobs/{job_id}` calls `client.messages.batches.cancel(batch_id)`. Completed requests within the cancelled batch are still parsed and saved to Sheets — partial results are preserved.

---

## 7. UI Changes

### 7.1 Home page — mode toggle

Above the "Analyse" button:
```
[⚡ Run now]   [💰 Batch — cheaper  ✓]
```
- Batch selected by default
- Selection persisted in `localStorage`
- Button label: "Analyse now" (live) or "Submit batch" (batch)

### 7.2 New page: Job Status (`/jobs/:jobId`)

For batch jobs only. The existing SSE Progress page (`/progress/:jobId`) is unchanged for live mode.

- Shows submitted timestamp and "Batch jobs typically complete in 15–60 min"
- Polls `/api/jobs/{job_id}/status` every 30 seconds
- Progress bar: `(succeeded + errored) / total` requests (total = N tickers × 6 agents)
- Counter: "342 / 600 agent calls complete"
- "Check now" button for manual poll
- When `status = "ended"`: fetches results, transitions inline to the Results table view
- Cancel button

### 7.3 Ticker Detail page

- Full qualitative report section removed (agents no longer generate it)
- Each agent card shows: score badge + `RATIONALE` as a one-line subtitle
- Fair Value panel unchanged

### 7.4 No other page changes

Results, Database Viewer, and CSV export are unchanged — all consume the same `TickerResult` type regardless of path.

---

## 8. Error Handling

| Failure | Behaviour |
|---|---|
| yfinance pre-fetch fails for a ticker | Ticker aborted immediately. Marked `Failed` with `"yfinance data unavailable"`. No agents run, no web search fallback. |
| yfinance field returns `None` | Renders as `N/A` in injected block; agents skip it in scoring |
| Individual batch request fails | Agent score = `null`; ticker marked `Partial` if some agents succeed |
| All 6 agents fail for a ticker | Ticker marked `Failed` |
| Batch takes >2 hours | Warning banner on Job Status page: "Taking longer than expected. Wait or cancel and resubmit as Run now." |
| Server restart mid-batch | Job file preserves `batch_id`; status page resumes polling on next visit |
| Batch cancelled | Completed requests within the batch are parsed and saved to Sheets |
| Haiku score parsing fails | `null` score, ticker marked `Partial` |
| Google Sheets write fails | Retry once, log error; result still returned to UI |

---

## 9. Files Changed

| File | Change |
|---|---|
| `backend/services/yahoo.py` | Add `format_financial_block()` |
| `backend/agents/base_agent.py` | Add prompt caching header; expose model/max_tokens/tools per subclass |
| `backend/agents/canslim.py` | Switch to Haiku, remove tools |
| `backend/agents/pre_screener.py` | Switch to Haiku, remove tools |
| `backend/agents/lynch_garp.py` | Switch to Haiku, remove tools |
| `backend/agents/buffett_munger.py` | Cap web search at 3; update max_tokens to 400 |
| `backend/agents/business_engine.py` | Cap web search at 3; update max_tokens to 400 |
| `backend/agents/growth_stock.py` | Cap web search at 3; update max_tokens to 400 |
| `backend/prompts/*.md` (all 6) | Inject data block point; trim output format; update search instructions |
| `backend/orchestrator/batch.py` | Add batch submission + result parsing path |
| `backend/routers/analysis.py` | Accept `mode` param; route to live or batch |
| `backend/routers/jobs.py` (new) | Status, results, cancel endpoints |
| `backend/services/batch_service.py` (new) | Batch request builder and result parser |
| `backend/jobs/` (new dir) | Per-job JSON persistence |
| `backend/models.py` | Add `rationale` field to `AgentResult`; add `JobStatus` model |
| `frontend/src/pages/Home.tsx` | Mode toggle |
| `frontend/src/pages/JobStatus.tsx` (new) | Polling UI for batch jobs |
| `frontend/src/pages/TickerDetail.tsx` | Remove report section; add rationale subtitle |
| `frontend/src/App.tsx` | Add `/jobs/:jobId` route |
| `frontend/src/types.ts` | Add `rationale` to agent result type; add `JobStatus` type |

---

## 10. Cost Summary

| Mode | Cost/ticker | 100 tickers × 4 runs/year |
|---|---|---|
| Current (baseline) | ~$2.50 | ~$1,000/year |
| Live (Run now), optimised | ~$0.34 | ~$136/year |
| Batch (default), optimised | ~$0.21 | ~$84/year |

*All outputs are for informational and educational purposes only and do not constitute investment advice.*
