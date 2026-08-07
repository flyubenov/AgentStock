---
name: yfinance-dedicated-pool
description: Backend froze whole-server on batch runs; yfinance blocking retries starved the default asyncio executor. Fixed with a dedicated bounded pool (services/yf_pool.py).
metadata: 
  node_type: memory
  type: project
  originSessionId: 7f67cc83-7660-438a-a388-4f38f8e00117
---

A batch (e.g. QCOM+TSLA on 2026-07-13) froze the *entire* backend — not just the job. Every endpoint hung (even a lightweight `GET /api/database` timed out), because the yfinance rate-limit retries do a blocking `time.sleep` while holding a worker in the **shared default asyncio executor** (`run_in_executor(None, …)`). A batch fans a dozen+ blocking fetches out at once (FV + screener × info/3 statements/treasury/price/EV-EBITDA); under a rate-limit they all sleep and saturate the default pool that FastAPI/Starlette also depend on → the SSE stream `Progress.tsx` waits on never emits `completed`, so the UI sits frozen.

**Fix:** `backend/services/yf_pool.py` — a dedicated bounded `ThreadPoolExecutor` (`YF_MAX_WORKERS`, default 8) + `run_yf(fn, *args)`. All yfinance fetches route through it (`fetch_ticker_info`, `fetch_ticker_cashflow`, `fetch_ev_ebitda_history` in yahoo.py; the statements bundle in screener/data.py). Backoff capped 8→3s base (worst case 3+6=9s, was 8+16+24=48s). Guarded by tests/test_yf_pool.py (5 tests, incl. a saturated-pool-stays-responsive regression test). 208 tests pass.

**How to apply:** never send yfinance/blocking work to the default executor — always use `run_yf`. Google Sheets writes (services/sheets.py, screener_sheets.py) intentionally stay on the default pool so yfinance can't starve them. The backend is launched `python3 -m uvicorn main:app --reload --port 8000`. Related: [[iren-opmargin-capex-reroute]].
