# Database Watchlists Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user save and load named watchlists on the Database screen, where a watchlist is a saved, dynamically-reapplied column-filter definition persisted to Google Sheets.

**Architecture:** A watchlist = a name + a serialized copy of the grid's `Filters` object, stored as opaque JSON in a new `Watchlists` Sheets tab. Backend gains a `Watchlist` model, a `watchlist_sheets.py` service (cloned from `screener_sheets.py`'s pattern), and a `routers/watchlists.py` with GET/PUT/DELETE. Frontend gains a small `lib/watchlists.ts` (types + API client) and a header control in `Database.tsx` that saves the active filter and reloads a saved one. The plan also scopes the existing **Recalculate All** button: when a filter is active (or a watchlist is selected), it recalculates only the tickers currently shown; with no filter active it recalculates the whole database as before.

**Tech Stack:** Backend — Python, FastAPI, `pytest`, Google Sheets API (via existing `services/sheets.py` helpers). Frontend — React + TypeScript + Vite + TailwindCSS.

## Global Constraints

- **No new dependencies** — backend or frontend. Reuse existing helpers only.
- **Sheets access goes through the shared helpers** in `services/sheets.py`: `_get_service`, `_sheet_id`, `_execute`, `_run_sheets`, `_tab_gid`. Never call the Google client directly, and never send Sheets work to the default executor.
- **API endpoints are registered under the `/api` prefix** (done in `main.py`). Frontend API base is `http://localhost:8000`.
- **The backend treats the filter blob as opaque JSON** — it stores/returns the value and never interprets its shape.
- **Routers catch exceptions and return `{"error": str(e), ...}`** rather than raising, matching `routers/database.py`.
- **The pre-existing `delete_watchlist_row` in `services/sheets.py` is a misnomer** (it targets the `Tickers` input list). Do NOT touch it. All new code names itself around the `Watchlists` tab.
- **Every commit message ends with the repo's standard footer** (two lines):
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01FGytQG64Qx65CuF24WHyxb
  ```
- **Backend tests run from the `backend/` directory** (imports are top-level, e.g. `from main import app`): `cd backend && python -m pytest tests/<file> -v`.

---

### Task 1: `Watchlist` model + `watchlist_sheets.py` serialization & tab bootstrap

**Files:**
- Modify: `backend/models.py` (add `Watchlist`)
- Create: `backend/services/watchlist_sheets.py`
- Test: `backend/tests/test_watchlist_sheets.py`

**Interfaces:**
- Consumes: `services.sheets._get_service`, `_sheet_id`, `_execute`, `_run_sheets`, `_tab_gid`.
- Produces (for Tasks 2 & 3):
  - `models.Watchlist(name: str, filter: dict = {}, created: str = "")`
  - `watchlist_sheets._WATCHLIST_TAB = "Watchlists"`
  - `watchlist_sheets._WATCHLIST_HEADERS = ["Name", "Filter", "Created"]`
  - `watchlist_sheets._watchlist_to_row(w: Watchlist) -> list`
  - `watchlist_sheets._row_to_watchlist(row: list) -> Watchlist`
  - `watchlist_sheets._ensure_watchlist_sheet(svc, sheet_id) -> None`

- [ ] **Step 1: Add the `Watchlist` model**

In `backend/models.py`, after the existing models, add:

```python
class Watchlist(BaseModel):
    name: str
    filter: dict = {}     # opaque serialized Filters blob (frontend owns the shape)
    created: str = ""
```

- [ ] **Step 2: Write the failing serialization + ensure-sheet tests**

Create `backend/tests/test_watchlist_sheets.py`:

```python
from unittest.mock import MagicMock

from models import Watchlist
from services.watchlist_sheets import (
    _watchlist_to_row, _row_to_watchlist, _ensure_watchlist_sheet,
    _WATCHLIST_HEADERS, _WATCHLIST_TAB,
)


def _wl():
    return Watchlist(
        name="Cheap quality",
        filter={"tickers": ["NVDA", "AMD"], "stockTypes": [],
                "quality": {"min": 8, "max": None},
                "gap": {"min": None, "max": -20}},
        created="2026-08-01T12:00:00Z",
    )


def test_row_length_and_json_column():
    row = _watchlist_to_row(_wl())
    assert len(row) == len(_WATCHLIST_HEADERS)
    assert row[0] == "Cheap quality"
    assert row[2] == "2026-08-01T12:00:00Z"
    # column B is JSON text, not a dict
    assert isinstance(row[1], str) and '"tickers"' in row[1]


def test_round_trip_preserves_filter():
    r = _row_to_watchlist(_watchlist_to_row(_wl()))
    assert r.name == "Cheap quality"
    assert r.filter["quality"] == {"min": 8, "max": None}
    assert r.filter["tickers"] == ["NVDA", "AMD"]
    assert r.created == "2026-08-01T12:00:00Z"


def test_row_to_watchlist_tolerates_short_and_garbage_rows():
    # a row missing the Created column
    r = _row_to_watchlist(["Momentum", '{"tickers":["MSFT"]}'])
    assert r.name == "Momentum" and r.created == ""
    assert r.filter["tickers"] == ["MSFT"]
    # a row whose JSON is malformed -> empty filter, still loads
    r2 = _row_to_watchlist(["Broken", "{not json", ""])
    assert r2.name == "Broken" and r2.filter == {}


def test_ensure_watchlist_sheet_creates_tab_and_header():
    svc = MagicMock()
    svc.spreadsheets.return_value.get.return_value.execute.return_value = {"sheets": []}
    _ensure_watchlist_sheet(svc, "sid")
    # tab added
    batch_calls = svc.spreadsheets.return_value.batchUpdate.call_args_list
    assert any(
        req.get("addSheet", {}).get("properties", {}).get("title") == _WATCHLIST_TAB
        for call in batch_calls
        for req in call.kwargs.get("body", {}).get("requests", [])
    )
    # header row written to A1
    update_calls = svc.spreadsheets.return_value.values.return_value.update.call_args_list
    assert any(
        call.kwargs.get("body", {}).get("values") == [_WATCHLIST_HEADERS]
        for call in update_calls
    )


def test_ensure_watchlist_sheet_noop_when_header_present():
    svc = MagicMock()
    svc.spreadsheets.return_value.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": _WATCHLIST_TAB, "sheetId": 7}}]
    }
    svc.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": [_WATCHLIST_HEADERS]
    }
    _ensure_watchlist_sheet(svc, "sid")
    svc.spreadsheets.return_value.batchUpdate.assert_not_called()
    svc.spreadsheets.return_value.values.return_value.update.assert_not_called()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_watchlist_sheets.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'services.watchlist_sheets'`.

- [ ] **Step 4: Implement the serialization + ensure-sheet code**

Create `backend/services/watchlist_sheets.py`:

```python
from __future__ import annotations
import json
from datetime import datetime, timezone

from models import Watchlist
from services.sheets import (
    _get_service, _sheet_id, _execute, _run_sheets, _tab_gid,
)

_WATCHLIST_TAB = "Watchlists"
_WATCHLIST_HEADERS = ["Name", "Filter", "Created"]


def _watchlist_to_row(w: Watchlist) -> list:
    return [w.name, json.dumps(w.filter or {}), w.created or ""]


def _parse_filter(v) -> dict:
    if not v:
        return {}
    try:
        parsed = json.loads(v)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _row_to_watchlist(row: list) -> Watchlist:
    row = list(row) + [""] * (len(_WATCHLIST_HEADERS) - len(row))
    return Watchlist(name=row[0], filter=_parse_filter(row[1]), created=row[2] or "")


def _ensure_watchlist_sheet(svc, sheet_id: str) -> None:
    """Create the 'Watchlists' tab + header row if missing; repair a tab whose row 1
    is data rather than the header (mirrors _ensure_screener_sheet, minus the
    outdated-schema refresh — these three headers never change)."""
    meta = _execute(svc.spreadsheets().get(spreadsheetId=sheet_id))
    props = {s["properties"]["title"]: s["properties"] for s in meta.get("sheets", [])}
    if _WATCHLIST_TAB not in props:
        _execute(svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": _WATCHLIST_TAB}}}]},
        ))
        _execute(svc.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=f"{_WATCHLIST_TAB}!A1",
            valueInputOption="RAW", body={"values": [_WATCHLIST_HEADERS]},
        ))
        return
    first = _execute(svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{_WATCHLIST_TAB}!1:1")).get("values", [])
    row1 = first[0] if first else []
    if row1 and row1[0] == _WATCHLIST_HEADERS[0]:
        return
    if row1:
        _execute(svc.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": [{"insertDimension": {
                "range": {"sheetId": props[_WATCHLIST_TAB]["sheetId"],
                          "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
                "inheritFromBefore": False}}]},
        ))
    _execute(svc.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=f"{_WATCHLIST_TAB}!A1",
        valueInputOption="RAW", body={"values": [_WATCHLIST_HEADERS]},
    ))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_watchlist_sheets.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/models.py backend/services/watchlist_sheets.py backend/tests/test_watchlist_sheets.py
git commit -m "feat(watchlists): Watchlist model + sheets serialization and tab bootstrap"
```

---

### Task 2: `watchlist_sheets.py` read / save / delete operations

**Files:**
- Modify: `backend/services/watchlist_sheets.py`
- Test: `backend/tests/test_watchlist_sheets.py` (append)

**Interfaces:**
- Consumes: everything from Task 1.
- Produces (for Task 3):
  - `async read_watchlists() -> list[Watchlist]`
  - `async save_watchlist(name: str, filter_obj: dict) -> Watchlist` (upsert by case-insensitive name; preserves the original `Created` on overwrite)
  - `async delete_watchlist(name: str) -> bool`

- [ ] **Step 1: Write the failing read/save/delete tests**

Append to `backend/tests/test_watchlist_sheets.py`:

```python
from unittest.mock import patch


def _fake_service_with_rows(rows):
    """Fake Sheets service: metadata reports the Watchlists tab (gid 7); the A:C
    (and A:A) value reads return `rows` including the header row."""
    svc = MagicMock()
    svc.spreadsheets.return_value.get.return_value.execute.return_value = {
        "sheets": [{"properties": {"title": _WATCHLIST_TAB, "sheetId": 7}}]
    }
    svc.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
        "values": rows
    }
    return svc


def test_read_sync_skips_header_and_parses_rows():
    from services.watchlist_sheets import _read_sync
    rows = [_WATCHLIST_HEADERS,
            ["Cheap quality", '{"quality":{"min":8,"max":null}}', "2026-08-01T00:00:00Z"]]
    svc = _fake_service_with_rows(rows)
    with patch("services.watchlist_sheets._get_service", return_value=svc), \
         patch("services.watchlist_sheets._sheet_id", return_value="sid"):
        out = _read_sync()
    assert len(out) == 1
    assert out[0].name == "Cheap quality"
    assert out[0].filter["quality"] == {"min": 8, "max": None}


def test_read_sync_swallows_missing_tab_only():
    from services.watchlist_sheets import _read_sync
    svc = MagicMock()
    svc.spreadsheets.return_value.get.return_value.execute.return_value = {"sheets": []}
    svc.spreadsheets.return_value.values.return_value.get.return_value.execute.side_effect = \
        Exception("Unable to parse range: Watchlists!A:C")
    with patch("services.watchlist_sheets._get_service", return_value=svc), \
         patch("services.watchlist_sheets._sheet_id", return_value="sid"):
        assert _read_sync() == []


def test_save_sync_appends_new_row():
    from services.watchlist_sheets import _save_sync
    svc = _fake_service_with_rows([_WATCHLIST_HEADERS])   # no data rows yet
    with patch("services.watchlist_sheets._get_service", return_value=svc), \
         patch("services.watchlist_sheets._sheet_id", return_value="sid"):
        w = _save_sync("New list", {"tickers": ["MSFT"]})
    assert w.name == "New list" and w.created  # created stamped
    svc.spreadsheets.return_value.values.return_value.append.assert_called_once()
    svc.spreadsheets.return_value.values.return_value.update.assert_not_called()


def test_save_sync_overwrites_and_preserves_created():
    from services.watchlist_sheets import _save_sync
    rows = [_WATCHLIST_HEADERS,
            ["Cheap quality", '{"quality":{"min":7}}', "2026-07-01T00:00:00Z"]]
    svc = _fake_service_with_rows(rows)
    with patch("services.watchlist_sheets._get_service", return_value=svc), \
         patch("services.watchlist_sheets._sheet_id", return_value="sid"):
        w = _save_sync("cheap QUALITY", {"quality": {"min": 9}})  # case-insensitive match
    assert w.created == "2026-07-01T00:00:00Z"                    # original created kept
    # updated in place at row 2 (A2), not appended
    upd = svc.spreadsheets.return_value.values.return_value.update
    assert upd.call_args.kwargs["range"] == "Watchlists!A2"
    svc.spreadsheets.return_value.values.return_value.append.assert_not_called()


def test_delete_sync_removes_matching_row():
    from services.watchlist_sheets import _delete_sync
    rows = [_WATCHLIST_HEADERS, ["Keep", "{}", ""], ["Drop", "{}", ""]]
    svc = _fake_service_with_rows(rows)
    with patch("services.watchlist_sheets._get_service", return_value=svc), \
         patch("services.watchlist_sheets._sheet_id", return_value="sid"):
        assert _delete_sync("drop") is True     # case-insensitive
    # deleted row index 2 (0-based) via deleteDimension on gid 7
    batch = svc.spreadsheets.return_value.batchUpdate.call_args
    rng = batch.kwargs["body"]["requests"][0]["deleteDimension"]["range"]
    assert rng == {"sheetId": 7, "dimension": "ROWS", "startIndex": 2, "endIndex": 3}


def test_delete_sync_returns_false_when_absent():
    from services.watchlist_sheets import _delete_sync
    svc = _fake_service_with_rows([_WATCHLIST_HEADERS, ["Keep", "{}", ""]])
    with patch("services.watchlist_sheets._get_service", return_value=svc), \
         patch("services.watchlist_sheets._sheet_id", return_value="sid"):
        assert _delete_sync("nope") is False
    svc.spreadsheets.return_value.batchUpdate.assert_not_called()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_watchlist_sheets.py -v`
Expected: FAIL with `ImportError: cannot import name '_read_sync'` (etc.).

- [ ] **Step 3: Implement read / save / delete**

Append to `backend/services/watchlist_sheets.py`:

```python
def _read_sync() -> list[Watchlist]:
    svc = _get_service()
    sheet_id = _sheet_id()
    try:
        result = _execute(svc.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=f"{_WATCHLIST_TAB}!A:C"))
    except Exception as e:
        if "Unable to parse range" in str(e):
            _ensure_watchlist_sheet(svc, sheet_id)
            return []
        raise
    rows = result.get("values", [])
    return [_row_to_watchlist(r) for r in rows[1:]] if len(rows) >= 2 else []


async def read_watchlists() -> list[Watchlist]:
    return await _run_sheets(_read_sync)


def _save_sync(name: str, filter_obj: dict) -> Watchlist:
    svc = _get_service()
    sheet_id = _sheet_id()
    _ensure_watchlist_sheet(svc, sheet_id)
    rows = _execute(svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{_WATCHLIST_TAB}!A:C")).get("values", [])
    target = None                       # 1-based sheet row to overwrite
    created = datetime.now(timezone.utc).isoformat()
    for i, row in enumerate(rows[1:], start=2):     # row 1 is the header
        if row and row[0].strip().lower() == name.strip().lower():
            target = i
            if len(row) >= 3 and row[2]:
                created = row[2]                    # preserve original Created
            break
    w = Watchlist(name=name, filter=filter_obj, created=created)
    new_row = _watchlist_to_row(w)
    if target is None:
        _execute(svc.spreadsheets().values().append(
            spreadsheetId=sheet_id, range=f"{_WATCHLIST_TAB}!A:A",
            valueInputOption="RAW", insertDataOption="INSERT_ROWS",
            body={"values": [new_row]}))
    else:
        _execute(svc.spreadsheets().values().update(
            spreadsheetId=sheet_id, range=f"{_WATCHLIST_TAB}!A{target}",
            valueInputOption="RAW", body={"values": [new_row]}))
    return w


async def save_watchlist(name: str, filter_obj: dict) -> Watchlist:
    return await _run_sheets(_save_sync, name, filter_obj)


def _delete_sync(name: str) -> bool:
    svc = _get_service()
    sheet_id = _sheet_id()
    gid = _tab_gid(svc, sheet_id, _WATCHLIST_TAB)
    if gid is None:
        return False
    rows = _execute(svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=f"{_WATCHLIST_TAB}!A:A")).get("values", [])
    target = None                       # 0-based row index for deleteDimension
    for i, row in enumerate(rows):
        if row and row[0].strip().lower() == name.strip().lower():
            target = i
            break
    if target is None:
        return False
    _execute(svc.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": [{"deleteDimension": {"range": {
            "sheetId": gid, "dimension": "ROWS",
            "startIndex": target, "endIndex": target + 1}}}]}))
    return True


async def delete_watchlist(name: str) -> bool:
    return await _run_sheets(_delete_sync, name)
```

> Note: `_delete_sync` matches on the header row only if a watchlist is literally named "Name"; that collision is acceptable and out of scope. The save/delete name match is case-insensitive to align with the frontend's unique-name expectation.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_watchlist_sheets.py -v`
Expected: PASS (all Task 1 + Task 2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/services/watchlist_sheets.py backend/tests/test_watchlist_sheets.py
git commit -m "feat(watchlists): read/save/delete sheet operations (upsert by name, preserve created)"
```

---

### Task 3: `routers/watchlists.py` + wire into `main.py`

**Files:**
- Create: `backend/routers/watchlists.py`
- Modify: `backend/main.py` (import + `include_router`)
- Test: `backend/tests/test_watchlists_router.py`

**Interfaces:**
- Consumes: `watchlist_sheets.read_watchlists / save_watchlist / delete_watchlist`, `models.Watchlist`.
- Produces (for the frontend):
  - `GET /api/watchlists` → `{"results": [{name, filter, created}, ...]}`
  - `PUT /api/watchlists/{name}` (body `{"filter": {...}}`) → `{"saved": true, name, filter, created}` or `{"saved": false, "error": ...}`
  - `DELETE /api/watchlists/{name}` → `{"deleted": bool, "name": ...}` or `{"deleted": false, "error": ...}`

- [ ] **Step 1: Write the failing router tests**

Create `backend/tests/test_watchlists_router.py`:

```python
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app
from models import Watchlist

client = TestClient(app)


def test_get_watchlists_returns_results():
    wls = [Watchlist(name="Cheap quality", filter={"quality": {"min": 8}}, created="t")]
    with patch("routers.watchlists.read_watchlists", new=AsyncMock(return_value=wls)):
        resp = client.get("/api/watchlists")
    body = resp.json()
    assert body["results"][0]["name"] == "Cheap quality"
    assert body["results"][0]["filter"] == {"quality": {"min": 8}}


def test_get_watchlists_surfaces_error():
    with patch("routers.watchlists.read_watchlists",
               new=AsyncMock(side_effect=Exception("quota exceeded"))):
        resp = client.get("/api/watchlists")
    body = resp.json()
    assert "quota exceeded" in body["error"] and body["results"] == []


def test_put_watchlist_saves():
    saved = Watchlist(name="Momentum", filter={"gap": {"max": -20}}, created="t")
    with patch("routers.watchlists.save_watchlist",
               new=AsyncMock(return_value=saved)) as m:
        resp = client.put("/api/watchlists/Momentum",
                          json={"filter": {"gap": {"max": -20}}})
    body = resp.json()
    assert body["saved"] is True and body["name"] == "Momentum"
    m.assert_awaited_once_with("Momentum", {"gap": {"max": -20}})


def test_put_watchlist_rejects_blank_name():
    with patch("routers.watchlists.save_watchlist", new=AsyncMock()) as m:
        resp = client.put("/api/watchlists/%20", json={"filter": {}})
    body = resp.json()
    assert body["saved"] is False and "name" in body["error"].lower()
    m.assert_not_awaited()


def test_delete_watchlist_removes():
    with patch("routers.watchlists.delete_watchlist",
               new=AsyncMock(return_value=True)):
        resp = client.delete("/api/watchlists/Momentum")
    assert resp.json() == {"deleted": True, "name": "Momentum"}


def test_delete_watchlist_not_found():
    with patch("routers.watchlists.delete_watchlist",
               new=AsyncMock(return_value=False)):
        resp = client.delete("/api/watchlists/Nope")
    body = resp.json()
    assert body["deleted"] is False and "Nope" in body["error"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_watchlists_router.py -v`
Expected: FAIL — the `/api/watchlists` routes 404 (router not registered).

- [ ] **Step 3: Create the router**

Create `backend/routers/watchlists.py`:

```python
from fastapi import APIRouter
from pydantic import BaseModel
from services.watchlist_sheets import (
    read_watchlists, save_watchlist, delete_watchlist,
)

router = APIRouter()


class WatchlistBody(BaseModel):
    filter: dict = {}


@router.get("/watchlists")
async def get_watchlists():
    try:
        results = await read_watchlists()
        return {"results": [w.model_dump() for w in results]}
    except Exception as e:
        return {"error": str(e), "results": []}


@router.put("/watchlists/{name}")
async def put_watchlist(name: str, body: WatchlistBody):
    n = name.strip()
    if not n:
        return {"saved": False, "error": "Watchlist name is required"}
    try:
        w = await save_watchlist(n, body.filter)
        return {"saved": True, **w.model_dump()}
    except Exception as e:
        return {"saved": False, "error": str(e)}


@router.delete("/watchlists/{name}")
async def remove_watchlist(name: str):
    n = name.strip()
    try:
        removed = await delete_watchlist(n)
        if not removed:
            return {"deleted": False, "error": f"No watchlist named {n!r}"}
        return {"deleted": True, "name": n}
    except Exception as e:
        return {"deleted": False, "error": str(e)}
```

- [ ] **Step 4: Wire the router into `main.py`**

In `backend/main.py`, alongside the existing router imports/registrations:

```python
from routers.watchlists import router as watchlists_router
```
```python
app.include_router(watchlists_router, prefix="/api")
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_watchlists_router.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Run the full backend suite (no regressions)**

Run: `cd backend && python -m pytest -q`
Expected: all pass (existing count + the new watchlist tests).

- [ ] **Step 7: Commit**

```bash
git add backend/routers/watchlists.py backend/main.py backend/tests/test_watchlists_router.py
git commit -m "feat(watchlists): GET/PUT/DELETE /api/watchlists router"
```

---

### Task 4: Frontend `lib/watchlists.ts` — types + API client

**Files:**
- Create: `frontend/src/lib/watchlists.ts`

**Interfaces:**
- Consumes: backend `/api/watchlists` endpoints from Task 3.
- Produces (for Task 5):
  - `type NumRange = { min: number | null; max: number | null }`
  - `interface SerializedFilters { tickers: string[]; stockTypes: string[]; quality: NumRange; gap: NumRange }`
  - `interface Watchlist { name: string; filter: SerializedFilters; created: string }`
  - `async fetchWatchlists(): Promise<Watchlist[]>`
  - `async saveWatchlist(name: string, filter: SerializedFilters): Promise<void>`
  - `async deleteWatchlist(name: string): Promise<void>`

> Frontend note: `frontend/` has no unit-test framework (eslint + `tsc` via `npm run build` only). These two frontend tasks are verified by type-check, lint, and a manual run — there is no red/green test cycle.

- [ ] **Step 1: Create the module**

Create `frontend/src/lib/watchlists.ts`:

```ts
const API = 'http://localhost:8000'

export type NumRange = { min: number | null; max: number | null }

export interface SerializedFilters {
  tickers: string[]
  stockTypes: string[]
  quality: NumRange
  gap: NumRange
}

export interface Watchlist {
  name: string
  filter: SerializedFilters
  created: string
}

export async function fetchWatchlists(): Promise<Watchlist[]> {
  const res = await fetch(`${API}/api/watchlists`)
  const data = await res.json()
  if (data.error) throw new Error(data.error)
  return (data.results ?? []) as Watchlist[]
}

export async function saveWatchlist(name: string, filter: SerializedFilters): Promise<void> {
  const res = await fetch(`${API}/api/watchlists/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filter }),
  })
  const data = await res.json()
  if (!data.saved) throw new Error(data.error || 'Failed to save watchlist')
}

export async function deleteWatchlist(name: string): Promise<void> {
  const res = await fetch(`${API}/api/watchlists/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
  const data = await res.json()
  if (!data.deleted) throw new Error(data.error || 'Failed to delete watchlist')
}
```

- [ ] **Step 2: Type-check and lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build succeeds (no TS errors), lint clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/watchlists.ts
git commit -m "feat(watchlists): frontend API client + serialized-filter types"
```

---

### Task 5: `Database.tsx` — watchlist header control + state wiring

**Files:**
- Modify: `frontend/src/pages/Database.tsx`

**Interfaces:**
- Consumes: `lib/watchlists.ts` (`fetchWatchlists`, `saveWatchlist`, `deleteWatchlist`, `Watchlist`, `SerializedFilters`); existing `Filters` / `EMPTY_FILTERS` / `anyActive` in `Database.tsx`.
- Produces: user-facing save/load/delete UI. No downstream consumers.

**UI decision (small deviation from the spec mockup):** rather than a custom dropdown with a per-row 🗑, use a native `<select>` to choose a watchlist plus a **Delete** button that removes the currently-selected one. Same capability, far less UI code, and it reuses the browser's native menu. Everything else matches the spec.

- [ ] **Step 1: Add the import**

At the top of `frontend/src/pages/Database.tsx`, add:

```ts
import { fetchWatchlists, saveWatchlist, deleteWatchlist } from '../lib/watchlists'
import type { Watchlist, SerializedFilters } from '../lib/watchlists'
```

- [ ] **Step 2: Add the serialize/deserialize helpers**

In `Database.tsx`, near `EMPTY_FILTERS` (module scope), add:

```ts
const serializeFilters = (f: Filters): SerializedFilters => ({
  tickers: [...f.tickers].sort(),
  stockTypes: [...f.stockTypes].sort(),
  quality: f.quality,
  gap: f.gap,
})

const deserializeFilters = (s: Partial<SerializedFilters> | undefined): Filters => ({
  tickers: new Set(s?.tickers ?? []),
  stockTypes: new Set(s?.stockTypes ?? []),
  quality: s?.quality ?? { min: null, max: null },
  gap: s?.gap ?? { min: null, max: null },
})
```

- [ ] **Step 3: Add state + load-on-mount**

Inside the `Database` component, alongside the existing `useState` hooks:

```ts
const [watchlists, setWatchlists] = useState<Watchlist[]>([])
const [activeWatchlist, setActiveWatchlist] = useState<string>('')  // '' = (none)
```

Add a load effect (a new `useEffect`, next to the existing `useEffect(() => { load() }, [])`):

```ts
const loadWatchlists = async () => {
  try {
    setWatchlists(await fetchWatchlists())
  } catch (e) {
    setError(e instanceof Error ? e.message : 'Failed to load watchlists')
  }
}
useEffect(() => { loadWatchlists() }, [])
```

- [ ] **Step 4: Add the select / save / delete handlers**

Inside the component, near the other handlers (`clearAll`, etc.):

```ts
const selectWatchlist = (name: string) => {
  setActiveWatchlist(name)
  if (!name) { setFilters(EMPTY_FILTERS); return }
  const wl = watchlists.find(w => w.name === name)
  if (wl) setFilters(deserializeFilters(wl.filter))
}

const saveCurrentAsWatchlist = async () => {
  if (!anyActive) { setError('Apply a filter before saving a watchlist.'); return }
  const name = window.prompt('Watchlist name')?.trim()
  if (!name) return
  const exists = watchlists.some(w => w.name.toLowerCase() === name.toLowerCase())
  if (exists && !confirm(`Overwrite the existing watchlist "${name}"?`)) return
  try {
    await saveWatchlist(name, serializeFilters(filters))
    await loadWatchlists()
    setActiveWatchlist(name)
  } catch (e) {
    setError(e instanceof Error ? e.message : 'Failed to save watchlist')
  }
}

const deleteActiveWatchlist = async () => {
  if (!activeWatchlist) return
  if (!confirm(`Delete watchlist "${activeWatchlist}"?`)) return
  try {
    await deleteWatchlist(activeWatchlist)
    setActiveWatchlist('')
    await loadWatchlists()
  } catch (e) {
    setError(e instanceof Error ? e.message : 'Failed to delete watchlist')
  }
}
```

- [ ] **Step 5: Render the control in the header**

In the header actions `<div className="flex items-center gap-2">` (the one holding "Clear filters"/"Recalculate All"/"Refresh"), add, before the existing `{anyActive && (...)}` block:

```tsx
<select
  value={activeWatchlist}
  onChange={e => selectWatchlist(e.target.value)}
  title="Load a saved watchlist"
  className="text-sm bg-[#16161e] text-slate-300 border border-[#1e1e2a] px-2 py-1.5 rounded focus:outline-none focus:border-blue-500"
>
  <option value="">Watchlist… (none)</option>
  {watchlists.map(w => (
    <option key={w.name} value={w.name}>{w.name}</option>
  ))}
</select>
<button
  onClick={saveCurrentAsWatchlist}
  className="text-sm text-slate-300 hover:text-white border border-[#1e1e2a] px-3 py-1.5 rounded"
>
  Save as…
</button>
{activeWatchlist && (
  <button
    onClick={deleteActiveWatchlist}
    title={`Delete watchlist "${activeWatchlist}"`}
    className="text-sm text-slate-500 hover:text-red-400 border border-[#1e1e2a] px-3 py-1.5 rounded"
  >
    Delete
  </button>
)}
```

- [ ] **Step 6: Keep the selector honest when filters are cleared manually**

The existing `clearAll` should also drop the active-watchlist label. Change:

```ts
const clearAll = () => setFilters(EMPTY_FILTERS)
```
to:
```ts
const clearAll = () => { setFilters(EMPTY_FILTERS); setActiveWatchlist('') }
```

- [ ] **Step 7: Type-check and lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build succeeds, lint clean.

- [ ] **Step 8: Manual verification (run the app)**

With the backend running (`cd backend && uvicorn main:app --reload`) and the frontend (`cd frontend && npm run dev`):
1. On the Database screen, apply a filter (e.g. Quality ≥ 8).
2. Click **Save as…**, name it "Cheap quality".
3. Reload the page — the watchlist appears in the dropdown.
4. Clear filters, then select "Cheap quality" — the grid re-applies the filter.
5. Click **Delete** — the watchlist disappears from the dropdown.
6. With no filter active, **Save as…** shows the "Apply a filter…" notice and saves nothing.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/Database.tsx
git commit -m "feat(watchlists): Database header control to save/load/delete watchlists"
```

---

### Task 6: Backend — optional scoped tickers on `/api/recalculate-all`

**Files:**
- Modify: `backend/routers/analysis.py:63-76` (the `recalculate_all` endpoint)
- Test: `backend/tests/test_analysis_endpoints.py` (append)

**Interfaces:**
- Consumes: existing `read_database`, `_run_job`, `_jobs`, `_cancel_events` machinery in `analysis.py`.
- Produces (for Task 7): `POST /api/recalculate-all` now accepts an **optional** JSON body `{"tickers": [...]}`.
  - Body present with a non-empty `tickers` → recalc exactly those (upper-cased, blanks dropped, de-duplicated, order preserved); `read_database` is NOT called.
  - Body absent, or `tickers` null/empty → recalc every Database row (unchanged behavior).
  - Returns `{"job_id", "total"}` as before; `{"error": ...}` when the resulting list is empty.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_analysis_endpoints.py`:

```python
def test_recalculate_all_scoped_to_body_tickers_skips_database():
    """A body with tickers recalculates exactly those and never reads the DB."""
    from unittest.mock import patch, AsyncMock
    import routers.analysis as analysis
    with patch("routers.analysis.read_database", new=AsyncMock()) as read_db, \
         patch("routers.analysis._run_job", new=AsyncMock()):
        resp = client.post("/api/recalculate-all", json={"tickers": ["aapl", " msft "]})
    body = resp.json()
    assert resp.status_code == 200
    assert body["total"] == 2 and "job_id" in body
    read_db.assert_not_awaited()                       # scoped path: DB untouched
    analysis._cancel_events.pop(body["job_id"], None)
    analysis._jobs.pop(body["job_id"], None)


def test_recalculate_all_scoped_normalizes_and_dedupes():
    from unittest.mock import patch, AsyncMock
    import routers.analysis as analysis
    with patch("routers.analysis._run_job", new=AsyncMock()):
        resp = client.post("/api/recalculate-all",
                          json={"tickers": ["AAPL", "aapl", " ", "MSFT"]})
    body = resp.json()
    assert body["total"] == 2                          # AAPL, MSFT (deduped, blank dropped)
    analysis._cancel_events.pop(body["job_id"], None)
    analysis._jobs.pop(body["job_id"], None)


def test_recalculate_all_empty_body_tickers_falls_back_to_database():
    """An empty tickers list behaves like no scope: recalc the whole DB."""
    from unittest.mock import patch, AsyncMock
    from models import DatabaseRow
    import routers.analysis as analysis
    rows = [DatabaseRow(ticker="AAPL"), DatabaseRow(ticker="MSFT")]
    with patch("routers.analysis.read_database", new=AsyncMock(return_value=rows)), \
         patch("routers.analysis._run_job", new=AsyncMock()):
        resp = client.post("/api/recalculate-all", json={"tickers": []})
    body = resp.json()
    assert body["total"] == 2
    analysis._cancel_events.pop(body["job_id"], None)
    analysis._jobs.pop(body["job_id"], None)
```

> The existing `test_recalculate_all_starts_job` (no body → total 2 from the DB) and `test_recalculate_all_empty_database` must keep passing — they cover the unscoped path.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_analysis_endpoints.py -v`
Expected: the three new tests FAIL (the endpoint takes no body, so `total` reflects the DB read, and `read_database` is awaited on the scoped test).

- [ ] **Step 3: Implement the optional body**

In `backend/routers/analysis.py`, add a request model near the top (after the `router = APIRouter()` line):

```python
from pydantic import BaseModel


class RecalcRequest(BaseModel):
    tickers: list[str] | None = None
```

Replace the `recalculate_all` endpoint (lines 63-76) with:

```python
@router.post("/recalculate-all")
async def recalculate_all(req: RecalcRequest | None = None):
    if req and req.tickers:
        seen: set[str] = set()
        tickers: list[str] = []
        for t in req.tickers:
            u = t.strip().upper()
            if u and u not in seen:
                seen.add(u)
                tickers.append(u)
    else:
        rows = await read_database()
        tickers = [r.ticker.strip().upper() for r in rows if r.ticker and r.ticker.strip()]
    if not tickers:
        return {"error": "No tickers to recalculate"}
    job_id = str(uuid.uuid4())
    cancel_event = asyncio.Event()
    _cancel_events[job_id] = cancel_event
    _jobs[job_id] = {"status": "running", "total": len(tickers),
                     "completed": 0, "failed": 0, "results": [], "invalid": [],
                     "running": []}
    asyncio.create_task(_run_job(job_id, tickers, cancel_event))
    return {"job_id": job_id, "total": len(tickers)}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_analysis_endpoints.py -v`
Expected: all pass, including the two pre-existing recalculate-all tests.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/analysis.py backend/tests/test_analysis_endpoints.py
git commit -m "feat(recalc): accept optional scoped tickers on /api/recalculate-all"
```

---

### Task 7: Frontend — scope the Recalculate button to the shown tickers

**Files:**
- Modify: `frontend/src/pages/Database.tsx`

**Interfaces:**
- Consumes: Task 6's optional-body endpoint; the existing `anyActive` flag and `sorted` array in `Database.tsx`.
- Produces: user-facing scoped-recalc behavior. No downstream consumers.

Because selecting a watchlist sets the filters (Task 5), `anyActive` already means "a filter is applied **or** a watchlist is selected" — the exact condition for scoping. No separate watchlist check is needed.

- [ ] **Step 1: Send the shown tickers when a filter is active**

In `Database.tsx`, replace the body of `recalcEverything` (the `fetch` call) so it posts the filtered tickers when `anyActive`:

```ts
const recalcEverything = async () => {
  setRecalcAll(true)
  try {
    const scoped = anyActive ? { tickers: sorted.map(r => r.ticker) } : null
    const res = await fetch(`${API}/api/recalculate-all`, {
      method: 'POST',
      ...(scoped
        ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(scoped) }
        : {}),
    })
    const data = await res.json()
    if (data.error) setError(data.error)
    else if (data.job_id) navigate(`/progress/${data.job_id}`, { state: { total: data.total } })
  } catch {
    setError('Failed to start recalculate-all. Is the backend running?')
  } finally {
    setRecalcAll(false)
  }
}
```

- [ ] **Step 2: Make the button label reflect the scope**

In the "Recalculate All" button (the one bound to `recalcEverything`), change the label expression:

```tsx
{recalcAll ? 'Starting…' : anyActive ? `Recalculate ${sorted.length} shown` : 'Recalculate All'}
```

(Optionally widen the button's `title` similarly; not required.)

- [ ] **Step 3: Type-check and lint**

Run: `cd frontend && npm run build && npm run lint`
Expected: build succeeds, lint clean.

- [ ] **Step 4: Manual verification (run the app)**

With backend + frontend running:
1. No filter → button reads "Recalculate All"; clicking recalculates everything (progress `total` = full DB count).
2. Apply a filter (or select a watchlist) → button reads "Recalculate N shown"; clicking recalculates only those N (progress `total` = N).
3. Clear the filter → button returns to "Recalculate All".

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Database.tsx
git commit -m "feat(recalc): scope Recalculate button to filtered/watchlist tickers"
```

---

## Self-Review Notes

**Spec coverage:**
- Dynamic filter definition → Tasks 1–2 store opaque JSON; Task 5 `deserializeFilters` + `setFilters` re-applies on load. ✓
- Filter-only selection (no checkbox column) → Task 5 reuses existing `Filters`; no grid column added. ✓
- Google Sheets `Watchlists` tab, opaque JSON → Tasks 1–2. ✓
- Save-as name prompt → Task 5 `window.prompt`. ✓
- Save blocked when no filter active → Task 5 `anyActive` guard. ✓
- Unique name / overwrite → Task 2 case-insensitive upsert; Task 5 overwrite confirm. ✓
- Tolerate missing/garbage blob keys → Task 1 `_parse_filter` + Task 5 `deserializeFilters` per-field defaults. ✓
- Backend TDD; frontend tsc+lint+manual → reflected per task. ✓
- Scoped recalculate (filter/watchlist → shown tickers only; no filter → whole DB) → Task 6 (optional body, unscoped fallback preserved) + Task 7 (`anyActive` predicate + dynamic label). ✓ *(Extends beyond the original watchlist spec — folded in at user request; see the spec addendum.)*

**Deviation from spec:** the delete UX is "select then Delete" (native `<select>` + Delete button) instead of a per-row 🗑 in a custom dropdown — noted in Task 5. Same capability, less code. Flag for the reviewer.

**Type consistency:** `SerializedFilters` / `Watchlist` / `NumRange` defined in `lib/watchlists.ts` (Task 4) and consumed unchanged in Task 5; `Filters` (Set-based) stays in `Database.tsx`; the serialize/deserialize pair bridges the two. Backend `save_watchlist(name, filter_obj)` signature matches the router call and the Task 2 tests.
