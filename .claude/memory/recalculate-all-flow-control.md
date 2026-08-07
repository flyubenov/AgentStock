---
name: recalculate-all-flow-control
description: "Recalculate All froze at ~6 tickers. REAL cause was the Google Sheets write path (concurrent use of the single non-thread-safe googleapiclient service), NOT yfinance. Fixed by serializing Sheets I/O on one thread + 429 backoff. run_batch was also hardened."
metadata: 
  node_type: memory
  type: project
  originSessionId: 7205805a-6289-44ac-ad99-7f58947d284c
  modified: 2026-07-23T20:32:08.283Z
---

## CORRECTION — the actual root cause was Google Sheets, not yfinance

My FIRST diagnosis (below) blamed yfinance throttling and rewrote run_batch — it was WRONG and did NOT fix the freeze ("froze again at 6"). I'd fixed by reasoning without ever observing the hang. Two credential-free isolation probes proved it:
- **Sequential raw-fetch probe** (25 tickers × 5 fetches = 125 yfinance calls): all fine, `rate_limit_pressure=False` throughout, zero throttle. yfinance is NOT the problem.
- **Real run_batch, real concurrency + fetches + engine compute, ONLY the two Sheets writes stubbed**: 25 tickers in 27s, 0 failed, no freeze → the freeze is entirely in the Sheets writes.

**Mechanism:** `google-api-python-client` is built on `httplib2`, which is NOT thread-safe. `services/sheets.py` builds ONE module-level `_service`; the batch runs many `_run_one` tasks concurrently, each doing ~10 Sheets API calls (2 upserts/ticker) through that shared service on the DEFAULT multi-thread executor. Concurrent threads on the one httplib2 connection corrupt it and hang the run after ~6 tickers (~6 reads/ticker also crosses the ~60-read/min quota right there).

**Fix (DONE + LIVE-CONFIRMED @`_pending_commit_`, +5 tests → 364):** `services/sheets.py` — dedicated single-thread `_SHEETS_EXECUTOR` + `_run_sheets()` (serializes every Sheets call so the shared client is touched by one thread only) and `_execute(request)` (retries 429/500/503 with capped exponential backoff so a full recalc self-throttles under quota). Every `.execute()` and `run_in_executor(None,…)` in sheets.py + screener_sheets.py routed through them. **Live: full 105-ticker Recalculate All against the real sheet → 105/105 completed, 0 failed.** LESSON (reinforces [[app-serves-persisted-rows-not-live-compute]]): never "fix" a freeze without reproducing/observing it; isolate the failing component with a probe BEFORE touching code. Deferred speed win (not needed for the fix): ~10 Sheets calls/ticker is wasteful (per-ticker metadata GETs, redundant A:A reads, Q1 header rewritten every ticker) — cache ensure/header once per run to cut quota + time.

---

## Original flow-control hardening (kept — useful, but was NOT the freeze fix)

Recalculate All processed a few names then got slower and froze. First (WRONG) diagnosis — thought root causes were all in the batch/fetch path:
1. **No pacing.** Old `run_batch` fired a whole `BATCH_SIZE=10` group at once; each ticker fans ~10 blocking yfinance fetches → ~100 calls/group onto the 8-thread yf_pool with zero inter-ticker delay → progressive Yahoo per-IP throttling.
2. **Head-of-line await.** It awaited tasks in *submission* order (`for ticker, task: await task`), so one slow ticker blocked emission of every finished ticker behind it → progress counter froze even while work happened.
3. **No timeout** on `.history()` yfinance calls → a stuck socket held a pool thread forever; enough starve the pool → true freeze.
4. **429 signal invisible** to the batch layer (fetches swallow it into retries → None), so it kept hammering.

**Fix (DONE + COMMITTED to master @`4d09516`, 359 tests pass, +12 new):**
- `orchestrator/batch.py`: replaced group-chunking with a fixed pool of `MAX_CONCURRENCY` (env `RECALC_CONCURRENCY`, default **3** — user chose "Balanced") workers consuming a work queue, emitting each result via an events queue in **completion order**. Added `_pacing_delay()` (base `RECALC_PACING_SECONDS`=0.4s, ×`RECALC_PACING_PRESSURE_MULT`=6 while throttled) and `_run_one_guarded` = `_run_one` under `asyncio.wait_for(PER_TICKER_TIMEOUT=120s)`. `_run_one` itself UNCHANGED. `BATCH_SIZE` removed.
- `services/yf_pool.py`: added `note_rate_limit()` / `rate_limit_pressure()` (20s window) — the adaptive-slowdown signal.
- `services/yahoo.py` + `services/statements.py`: call `note_rate_limit()` on 429 detection; `timeout=YF_HISTORY_TIMEOUT`(30s) on all `.history()` calls.
- `routers/analysis.py`: `_run_job` now tracks a `job["running"]` set from `ticker_start`/clears on done/error; `stream_job` forwards `running[]` in the SSE status payload. Job dicts init `"running": []`.
- Frontend `useAnalysisStream.ts`: consumes `running`, marks those chips 'running' (never overrides done/failed). `Progress.tsx`: "Now evaluating: X, Y" pulsing line.

Tunable via env if 3-in-flight still throttles: lower `RECALC_CONCURRENCY`, raise `RECALC_PACING_SECONDS`. Verified via tests (real `run_batch` logic); a live Recalculate All is the end-to-end confirmation — can't unit-test actual Yahoo throttling. Related: [[yfinance-dedicated-pool]], [[app-serves-persisted-rows-not-live-compute]].
