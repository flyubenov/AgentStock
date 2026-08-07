---
name: app-serves-persisted-rows-not-live-compute
description: "The Agent Stock UI reads stored Google Sheets rows and never computes on page load; the uvicorn --reload dev server also silently served 90-minute-old code — verify fixes via a fresh process, not the running app"
metadata: 
  node_type: memory
  type: project
  originSessionId: aeef9c29-8bb7-4fc5-8aea-4e7a5c8d7f4d
---

**A code fix does NOT change what the app shows.** Two independent layers cache, and both
bit at once on 2026-07-16 (TEM/NBIS work — see [[tem-sign-artifact-bugs]]):

1. **The UI never computes on page load.** `routers/database.py` → `services/sheets.read_database`
   and `read_screener_one` read PERSISTED rows from Google Sheets. Only
   `POST /api/ticker/{t}/recalculate` and `POST /api/recalculate-all` recompute
   (`orchestrator/batch._run_one` → `upsert_result` + `upsert_screener_result`). So after any
   engine/scoring change the stored rows are stale until recalculated — and a screener change
   affects every name matching it, so per-ticker recalc under-propagates. Note stored rows can
   also predate newer metric fields (a stored AAPL row read 30 non-null vs 38 fresh).

2. **`uvicorn --reload` silently did not reload.** start.sh runs
   `python3.exe -m uvicorn main:app --reload --port 8000` from `backend/`. The worker ran for
   ~90 minutes across three commits and never restarted, serving stale code, with watchfiles 1.1.1
   installed and the watch root correct. Symptom: NBIS recalculated 82 seconds AFTER the merge
   still returned the pre-fix PRE_PROFIT / 4.6. Root cause not found — treat `--reload` as
   unreliable here and restart explicitly after changes.

3. **A DECLINED valuation used to not overwrite its stored row — the stale FV was immortal.**
   `batch._run_one` gated the upsert on `status != "failed" or stock_type == "PRE_PROFIT"`,
   assuming every decline rewrites stock_type to that literal. The pre-profit guard does; the
   sub-floor EV/Sales guard and the non-positive-composite clamp keep the REAL tier, so their
   declines matched neither arm → upsert skipped → Sheets kept serving the exact FV the guard
   had just rejected, and NO amount of recalculating could clear it (ASTS stuck at $1.15 after
   the engine declined it). Self-concealing: the UI showed a number no code path would still
   produce. FIXED @`84a2051` — gate on identity (`current_price is not None`) not tier name;
   a true failure (ticker never resolved → no price) is still skipped. **Any future decline
   path is now covered automatically.**

**How to apply:** never validate a fix against the running app or a stored row. **And verifying
the API response is NOT enough — check the STORED row** (`GET /api/database` → `.results`, 88
rows; note the payload is `{"results": [...]}`, not a bare list). I confirmed the engine declined
ASTS via `POST /api/ticker/ASTS/recalculate` and called it verified; the user still saw $1.15,
because I'd checked the compute layer and the bug was in the persist layer. Verify by calling
`valuation.engine.run` / `screener.engine.run` in a FRESH process (this is what the live-basket
before/after diff does). To make the app agree: restart the backend, THEN recalculate. Check the
worker's start time against your commit times before believing live output —
`Get-CimInstance Win32_Process -Filter "Name LIKE '%python%'" | Select ProcessId,ParentProcessId,CreationDate`
(uvicorn spawns a reloader parent + worker child; the child is the one that must be newer).
