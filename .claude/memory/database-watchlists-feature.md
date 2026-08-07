---
name: database-watchlists-feature
description: "PAUSED mid-brainstorm — Database watchlists feature. Spec written & committed, awaiting user review/approval before writing-plans."
metadata: 
  node_type: memory
  type: project
  originSessionId: 83ed4cba-1943-4540-b2b7-859d1a6bcef4
  modified: 2026-08-02T11:09:06.562Z
---

Database "watchlists" feature (save/load named filter views on the Database screen) + scoped Recalculate All. **DONE + MERGED to `master` (no-ff `95271b4`), LOCAL only — not pushed to origin.** Built via SDD on branch `optimizations` (KEPT — user continues optimization work in it). All 7 tasks + whole-branch review + 1 follow-up fix. Manual browser smoke-test PASSED. Backend 421/421. `optimizations` @ `9de45e2` (merged range `1c5ca12^..9de45e2`). NOTE: local `master` tracks `origin/main`; neither pushed.

**Commits:** T1 `1c5ca12` (Watchlist model + watchlist_sheets serialization/bootstrap), T2 `321973e` (read/save/delete upsert-by-name preserve-Created), T3 `9f91fcc` (routers/watchlists GET/PUT/DELETE + main.py), T4 `2ed43dc` (frontend lib/watchlists.ts client+types), T5 `fc5b93d` (Database.tsx header control: native <select> + Save as… + Delete), T6 `ce8a779` (backend optional {tickers} body on /api/recalculate-all — present+non-empty→scoped, absent/empty→whole DB), T7 `fc1918d` (frontend scope Recalculate button via anyActive + "Recalculate N shown" label), fix `9de45e2` (guard zero-row active filter from silent full-DB recalc). Every commit reviewed clean (0 Crit/0 Imp per task); whole-branch opus review confirmed all FE↔BE contracts + serialize round-trip + Sheets idioms.

**Deferred Minors (not bugs):** watchlist name with `/` → `%2F` path-param routing (use `{name:path}` if it ever matters); case-change overwrite rewrites the stored Name cell (harmless); header-row collision only if a watchlist is literally named "Name" (out of scope).

**Spec:** `docs/superpowers/specs/2026-08-01-database-watchlists-design.md` @ `de2d32f`. **Plan:** `docs/superpowers/plans/2026-08-01-database-watchlists.md` @ `c716f7f`. **SDD ledger:** `.superpowers/sdd/2026-08-01-database-watchlists/progress.md`.

**Plan = 7 tasks** (scoped-recalc folded in @ `7e696a9`): (1) `Watchlist` model + `services/watchlist_sheets.py` serialization/tab-bootstrap, (2) sheets read/save/delete (upsert by case-insensitive name, preserve Created), (3) `routers/watchlists.py` GET/PUT/DELETE + wire `main.py`, (4) `frontend/src/lib/watchlists.ts` types+API client, (5) `Database.tsx` header control, (6) BACKEND optional `{tickers}` body on `/api/recalculate-all` (present→scope, absent/empty→whole DB), (7) FRONTEND scope Recalculate button via existing `anyActive` (= filter applied OR watchlist selected, since a watchlist just sets filters) + relabel "Recalculate N shown". Backend TDD; frontend has NO test framework → `npm run build` (tsc -b) + `npm run lint` + manual. One flagged deviation: watchlist delete UX is native `<select>` + Delete-active button, NOT per-row 🗑 (less code, same capability).

**Locked decisions:**
- Watchlist = **dynamic filter definition** (re-runs against current data on load), NOT a frozen ticker set.
- **Filter-only selection** — reuses the existing Database column filters (`Filters` object in `frontend/src/pages/Database.tsx`); NO checkbox column. Hand-picking = the existing Ticker multi-select filter.
- **Storage = Google Sheets**, new `Watchlists` tab `[Name(key), Filter JSON, Created]`; backend treats the filter blob as **opaque JSON** (decoupled from frontend schema).
- **Save-as = simple `window.prompt` name**; **save BLOCKED when no filter active** (reuse existing `anyActive`); name is unique key (overwrite on dup).

**Planned pieces:** new `backend/services/watchlist_sheets.py` (clone of `screener_sheets.py` pattern — reuses `_get_service/_sheet_id/_execute/_run_sheets`), new `backend/routers/watchlists.py` (GET/PUT/DELETE `/watchlists`, wired in `main.py` under `/api`), `Watchlist` model in `models.py`, and Database.tsx header dropdown + Save-as + serialize/deserialize helpers (Sets↔arrays, per-field defaults). Backend TDD; frontend has NO test framework (eslint only) → tsc + lint + manual run.

**Gotcha:** `sheets.py` already has `delete_watchlist_row` — a MISNOMER targeting the `Tickers` input list, NOT this feature. Leave it; name all new code around the `Watchlists` tab.

**NEXT STEP when resuming:** execute the plan via `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans`. Consider an isolated git worktree/branch off `optimizations` first.
