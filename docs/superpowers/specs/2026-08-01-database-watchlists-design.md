# Database Watchlists — Design

**Date:** 2026-08-01
**Status:** Approved (design), pending implementation plan

## Goal

Let the user save and load named **watchlists** on the Database screen. A watchlist
captures the grid's current column-filter state under a name. Re-selecting a saved
watchlist re-applies that filter, so the grid shows the matching tickers and hides
the rest.

## Key decisions (locked)

1. **A watchlist is a dynamic filter definition, not a frozen ticker set.** Loading a
   watchlist re-runs its saved filter against current Database rows. Membership can
   therefore change over time as data updates (a newly-matching ticker appears; a
   ticker whose Quality/Gap moves out of range drops off). This is intended.
2. **Selection is filter-only — no new checkbox column.** Hand-picking specific
   tickers is done through the *existing* Ticker column filter (which already stores a
   set of chosen tickers). A hand-picked watchlist is simply a saved filter whose
   `tickers` set is populated.
3. **Storage is Google Sheets** — a new `Watchlists` tab — consistent with how
   Database/Screener/Tickers already persist, and durable across browser-cache clears.
4. **Save-as flow is a simple name prompt.** No dedicated modal/form.
5. **Saving is blocked when no filter is active** — there is nothing meaningful to
   save (an empty filter matches everything).

## Data model

A watchlist = a name + a serialized copy of the Database grid's `Filters` object.

The frontend `Filters` shape (unchanged, in `Database.tsx`):

```ts
Filters = {
  tickers: Set<string>
  stockTypes: Set<string>
  quality: { min: number | null; max: number | null }
  gap:     { min: number | null; max: number | null }
}
```

`Set`s are not JSON-serializable, so they persist as arrays. Serialized form:

```json
{
  "tickers": ["NVDA", "AMD"],
  "stockTypes": [],
  "quality": { "min": 8, "max": null },
  "gap": { "min": null, "max": -20 }
}
```

**The backend treats this filter blob as opaque JSON** — it stores and returns the
string, never parsing its shape. This decouples the backend from the frontend filter
schema: adding a future filter column requires no backend change.

## Storage — `Watchlists` Sheets tab

| Column A: Name (key) | Column B: Filter JSON | Column C: Created |
|---|---|---|
| `Cheap quality` | `{"quality":{"min":8,"max":null},...}` | `2026-08-01T12:00:00Z` |

- **Name is the unique key.** Saving an existing name overwrites that row (upsert).
- Header row is `["Name", "Filter", "Created"]`.

New module `backend/services/watchlist_sheets.py`, cloned from the structure of
`backend/services/screener_sheets.py`. It reuses the shared helpers already exported
from `services/sheets.py` (`_get_service`, `_sheet_id`, `_execute`, `_run_sheets`) and
provides:

- `_ensure_watchlist_sheet(svc, sheet_id)` — create the tab + header row if missing
  (mirror `_ensure_screener_sheet`, including the "repair a headerless tab" guard).
- `read_watchlists() -> list[Watchlist]` — read all rows (skip header).
- `save_watchlist(name, filter_json) -> Watchlist` — upsert by name; stamps `Created`
  on first insert, preserves it on overwrite.
- `delete_watchlist(name) -> bool` — remove the row whose column A matches `name`.

> **Naming note.** `services/sheets.py` already defines `delete_watchlist_row`, which
> despite its name targets the **Tickers** input list (a pre-existing misnomer). It is
> left untouched. All new code is named around the `Watchlists` tab
> (`save_watchlist` / `read_watchlists` / `delete_watchlist`) to keep the two
> concepts distinct.

## Backend API — new `routers/watchlists.py` (registered under `/api`)

| Method | Path | Body | Returns |
|---|---|---|---|
| GET | `/watchlists` | — | `{ "results": [{name, filter, created}, ...] }` |
| PUT | `/watchlists/{name}` | `{ "filter": {...} }` | `{ "saved": true, name, filter, created }` |
| DELETE | `/watchlists/{name}` | — | `{ "deleted": bool, name }` |

Error handling matches the existing routers: catch exceptions and return
`{"error": str(e), ...}` rather than raising, so the frontend surfaces a message.

`main.py` gains `from routers.watchlists import router as watchlists_router` and
`app.include_router(watchlists_router, prefix="/api")`.

`models.py` gains:

```python
class Watchlist(BaseModel):
    name: str
    filter: dict          # opaque serialized Filters blob
    created: str
```

## Frontend — `Database.tsx`

### New header control

Placed left of the existing "Clear filters" button:

```
Database — 12 of 240 records   [ Watchlist: Cheap quality ▾ ]  [ Save as… ]  [Clear filters] [Recalculate All] [Refresh]
                                  ├ (none)
                                  ├ Cheap quality        🗑
                                  └ Momentum names       🗑
```

### State additions

- `watchlists: Watchlist[]` — fetched from `/api/watchlists` on mount.
- `activeWatchlist: string | null` — the currently-selected name (for the dropdown
  label / highlight).

### Behavior

- **Load:** selecting a watchlist → `setFilters(deserializeFilters(wl.filter))` and set
  `activeWatchlist`. The grid's existing `rowMatches`/`sorted` pipeline re-runs
  automatically — no other change needed.
- **(none):** clears filters (`setFilters(EMPTY_FILTERS)`) and `activeWatchlist = null`.
- **Save as…:** `window.prompt('Watchlist name')` → `serializeFilters(filters)` →
  `PUT /api/watchlists/{name}` → re-fetch list → set active to the saved name.
  Guarded by `anyActive` (the existing "any filter active" flag): if no filter is
  active, show a brief notice and do not save.
- **Delete (🗑):** confirm → `DELETE /api/watchlists/{name}` → re-fetch list; if the
  deleted name was active, reset `activeWatchlist` (filters left as-is).

### Serialization helpers (module-local in `Database.tsx`)

- `serializeFilters(f: Filters) => object` — Sets → sorted arrays; ranges passthrough.
- `deserializeFilters(o: unknown) => Filters` — arrays → Sets; **per-field defaults**
  fall back to `EMPTY_FILTERS` for any missing/malformed key, so blobs saved before a
  future schema change still load.

## Edge cases

- **Empty filter** → save blocked (guarded by `anyActive`).
- **Duplicate name** → overwrite; confirm before replacing an existing name.
- **Saved ticker no longer in the DB** → silently absent (dynamic model — expected).
- **Unknown / missing keys in a stored blob** → ignored via `deserializeFilters`
  per-field defaults; the watchlist still loads with whatever it can.
- **Backend/Sheets unavailable** → endpoints return `{"error": ...}`; the frontend
  shows the message and leaves existing grid state intact.

## Testing

- **Backend (TDD):**
  - `test_watchlist_sheets.py` — save/read/delete round-trip and upsert-overwrite,
    against a fake Sheets service, mirroring `test_screener_sheets.py`.
  - Router tests for the three endpoints, mirroring `test_database_router.py`
    (including the empty-name / not-found / error paths).
- **Frontend:** no test framework exists in `frontend/` (eslint only). Verification =
  `tsc` type-check + eslint + a manual run of the app (save a filter, reload the page,
  re-select the watchlist, confirm the grid filters, delete it).

## Addendum — scoped Recalculate All (added 2026-08-01)

Folded in alongside watchlists. Today the **Recalculate All** button always recomputes
every ticker in the Database tab, ignoring any applied filter. New behavior:

- **Filter applied or watchlist selected** → recalculate **only the tickers currently
  shown**.
- **No filter active / no watchlist selected** → recalculate the **entire database**
  (unchanged).

Since selecting a watchlist sets the grid filters, the single predicate `anyActive`
("any filter dimension is set") captures both cases. Implementation: `POST
/api/recalculate-all` gains an **optional** `{"tickers": [...]}` body — present ⇒ scope
to those, absent/empty ⇒ whole DB. The frontend sends the shown tickers when
`anyActive` and relabels the button "Recalculate N shown". Backend change is TDD.

## Out of scope (YAGNI)

- Row checkbox multi-select (superseded by filter-only selection).
- Renaming the pre-existing `delete_watchlist_row` misnomer.
- Sharing/exporting watchlists, ordering, or folders.
- Any change to the valuation/screener pipeline (scoped recalc reuses the existing
  batch job; it does not alter scoring/valuation logic).
