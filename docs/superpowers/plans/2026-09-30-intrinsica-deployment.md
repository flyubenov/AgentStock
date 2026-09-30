# Intrinsica Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the repo deployable as one always-on Cloud Run service at `https://intrinsica.io`, built and deployed automatically by Cloud Build on every push to `main`.

**Architecture:**
- A root multi-stage Dockerfile builds the React app. The FastAPI backend then serves it next to `/api` (a single origin).
- Public mode strips the Agent Stock analyst routes and pages. Sheets access falls back to the Cloud Run identity (no keys).
- `cloudbuild.yaml` (deploy) and `cloudbuild-pr.yaml` (PR tests) carry all service config.
- The one-time cloud setup is the manual guide in `DEPLOY.md`. It is not part of this plan's code tasks.

**Tech Stack:** FastAPI 0.115 / Starlette, Python 3.12 (container) and 3.14 (local), pytest 9 + pytest-asyncio, React 19 + react-router-dom 7, Vite 8, Vitest, Docker, Google Cloud Build, Cloud Run.

**Spec:** `docs/superpowers/specs/2026-09-30-intrinsica-deployment-design.md`

## Global Constraints

- Region `europe-west1`; service `intrinsica`; Artifact Registry repo `intrinsica`; image `europe-west1-docker.pkg.dev/$PROJECT_ID/intrinsica/app`.
- Runtime SA `intrinsica-run@$PROJECT_ID.iam.gserviceaccount.com`; build SA `intrinsica-build@…`.
- Cloud Run: min 1, max 3, 1 vCPU, 1 GiB, request-based billing (`--cpu-throttling`), `--cpu-boost`, concurrency 80, timeout 300 s, `--allow-unauthenticated`.
- Production env (`--set-env-vars`, repo is the source of truth):
  - `INTRINSICA_PUBLIC_MODE=1`
  - `CANONICAL_HOST=intrinsica.io`
  - `CORS_ORIGINS=https://intrinsica.io`
  - `INTRINSICA_EVENTS_SHEET_ID=1e4U4roainSuDJPHwsxkVrZezlA2InDPHV1zaQHuCzqY`
  - `LANDING_SLOW_TTL=604800`
  - `LANDING_FAST_TTL=14400`
  - `LANDING_CACHE_MAX_ENTRIES=256`
  - `LANDING_RATE_LIMIT=20`
  - `LANDING_RATE_WINDOW_SECONDS=60`
- `INTRINSICA_STATIC_DIR=/app/static` is baked into the image.
- **Never** set `GOOGLE_SHEETS_ID`, `GOOGLE_SHEETS_CREDS_JSON` or `GOOGLE_SHEETS_CREDS_PATH` in production. No Agent Stock identifiers anywhere in the deploy config.
- Local dev (flags unset) must behave exactly as today: `./start.sh`, Vite on `:5173`, and the backend on `:8000` with the analyst app.
- Gates:
  - backend `pytest` all green (baseline 694 passed);
  - frontend `vitest run` all green (baseline 395);
  - `tsc -b` clean;
  - eslint at its baseline of **6** findings, never more.
- Branch: `02-deployment`. `main` is changed only through a PR; `gh` is not installed, so give the compare URL.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Do not commit `backend/tests/__pycache__/*` or `brand/`.
- Backend commands run from `backend/` with `python -m pytest`. Frontend commands run from `frontend/`.

## Review Focus

1. **A path-traversal URL** (`/%2e%2e/secret.txt`, `/assets/..%2f..%2fsecret.txt`) must never serve a file outside the static dir; it gets `index.html`. The test is in Task 6.
2. **An unknown or wrong-method `/api/...` request** must answer JSON 404/405, never `index.html` with 200. Otherwise the frontend would parse HTML as JSON and show the generic "could not be reached" message. The test is in Task 6.
3. **The production bundle must call the API same-origin.** A leftover `http://localhost:8000` in `dist/` would break every analysis on the live site. The check is in Task 8 step 7 and Task 9 step 4.
4. **A forged `X-Forwarded-For` prefix** must not dodge the new landing limiter; the right-most entry is the key. The test is in Task 2.
5. **The `www` redirect** must keep the path and query, must not fire for the apex or when `CANONICAL_HOST` is unset, and must ignore a `:port` suffix. The test is in Task 7.

---

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `backend/services/rate_limit.py` | create | `RateLimiter` (sliding window per client key) and `client_key(request)` |
| `backend/routers/events.py` | modify | Use the shared limiter; behaviour unchanged |
| `backend/routers/landing.py` | modify | Per-IP limit → 429 with a reader-facing `error` |
| `backend/landing/cache.py` | modify | `MAX_ENTRIES` from `LANDING_CACHE_MAX_ENTRIES` (default 256) |
| `backend/services/sheets.py` | modify | ADC fallback when there is no JSON and no key file |
| `backend/spa.py` | create | `mount_spa(app, static_dir)`: serve `dist/` files, the index fallback, the `/api` 404 |
| `backend/canonical.py` | create | `add_canonical_host_redirect(app, host)`: `www` → apex 301 |
| `backend/main.py` | modify | `create_app(...)` factory: public-mode router gating, SPA and redirect wiring |
| `backend/requirements-dev.txt` | create | Test-only deps for CI (`pytest`, `pytest-asyncio`) |
| `backend/tests/test_rate_limit.py` | create | Limiter unit tests |
| `backend/tests/test_events_router.py` | modify | Point at the shared limiter |
| `backend/tests/test_landing_router.py` | modify | Limiter reset fixture plus 429 tests |
| `backend/tests/test_landing_cache.py` | modify | Env-driven cap test |
| `backend/tests/test_landing_marquee_sync.py` | create | Chip list ↔ pre-warm list |
| `backend/tests/test_sheets_credentials.py` | create | Credential-resolution order |
| `backend/tests/test_public_mode.py` | create | Router gating |
| `backend/tests/test_spa.py` | create | Static/SPA serving |
| `backend/tests/test_canonical.py` | create | `www` redirect |
| `frontend/src/lib/api.ts` | modify | Production builds default to same-origin |
| `frontend/src/App.tsx` | modify | `VITE_PUBLIC_MODE` route gating |
| `frontend/src/vite-env.d.ts` | modify | Type for `VITE_PUBLIC_MODE` |
| `frontend/src/App.test.tsx` | create | Public-mode routing tests |
| `frontend/src/landing/LandingPage.test.tsx` | modify | 429 notice test |
| `Dockerfile`, `.dockerignore` (root) | create | The single image |
| `backend/Dockerfile`, `backend/.dockerignore` | delete | Superseded |
| `cloudbuild.yaml`, `cloudbuild-pr.yaml` (root) | create | CI/CD |
| `frontend/vercel.json`, `backend/railway.json`, `render.yaml` | delete | Single provider |
| `DEPLOY.md`, `backend/.env.example`, `frontend/.env.example` | rewrite | Docs and config reference |

---

### Task 1: Shared rate limiter

**Files:**
- Create: `backend/services/rate_limit.py`
- Modify: `backend/routers/events.py` (lines 1–70: the limiter state, `_client_key` and `_rate_limited`; plus its use in `post_event`)
- Test: `backend/tests/test_rate_limit.py` (new), `backend/tests/test_events_router.py` (fixture lines 14–19 and tests at lines 141–183)

**Interfaces:**
- Produces:
  - `class RateLimiter(limit: int, window_seconds: float, max_clients: int = 10_000, now: Callable[[], float] = time.monotonic)` with the attributes `limit`, `window_seconds`, `max_clients`, `now` and `hits: OrderedDict[str, deque[float]]`, and the methods `limited(key: str) -> bool` (True means refuse; a refused call is not recorded) and `clear() -> None`.
  - `client_key(request: fastapi.Request) -> str`.
  - `routers.events._limiter: RateLimiter`.

- [ ] **Step 1: Write the failing unit tests** in `backend/tests/test_rate_limit.py`:

```python
from types import SimpleNamespace

from services.rate_limit import RateLimiter, client_key


def _req(headers: dict[str, str] | None = None, host: str | None = "127.0.0.1"):
    return SimpleNamespace(headers=headers or {},
                           client=SimpleNamespace(host=host) if host else None)


def test_allows_up_to_the_limit_then_refuses():
    lim = RateLimiter(limit=2, window_seconds=60, now=lambda: 100.0)
    assert not lim.limited("ip")
    assert not lim.limited("ip")
    assert lim.limited("ip")


def test_the_limit_frees_up_once_the_window_passes():
    t = [100.0]
    lim = RateLimiter(limit=2, window_seconds=60, now=lambda: t[0])
    assert not lim.limited("ip")
    assert not lim.limited("ip")
    assert lim.limited("ip")
    t[0] += 60
    assert not lim.limited("ip")


def test_clients_are_counted_separately():
    lim = RateLimiter(limit=1, window_seconds=60, now=lambda: 0.0)
    assert not lim.limited("a")
    assert lim.limited("a")
    assert not lim.limited("b")


def test_forgets_the_least_recent_client_past_its_bound():
    lim = RateLimiter(limit=5, window_seconds=60, max_clients=3, now=lambda: 0.0)
    for ip in ["a", "b", "c", "d"]:
        lim.limited(ip)
    assert list(lim.hits) == ["b", "c", "d"]


def test_clear_forgets_everyone():
    lim = RateLimiter(limit=1, window_seconds=60, now=lambda: 0.0)
    lim.limited("a")
    lim.clear()
    assert not lim.limited("a")


def test_client_key_uses_the_right_most_forwarded_for_entry():
    # Cloud Run's front end APPENDS the address it saw; anything left of it is client-supplied.
    assert client_key(_req({"x-forwarded-for": "10.0.0.1, 203.0.113.7"})) == "203.0.113.7"


def test_client_key_falls_back_to_the_socket_peer_then_unknown():
    assert client_key(_req()) == "127.0.0.1"
    assert client_key(_req(host=None)) == "unknown"
```

- [ ] **Step 2: Run them to verify they fail.**
Run: `cd backend && python -m pytest tests/test_rate_limit.py -q`
Expected: collection error `ModuleNotFoundError: No module named 'services.rate_limit'`.

- [ ] **Step 3: Implement `backend/services/rate_limit.py`:**

```python
from __future__ import annotations
import time
from collections import OrderedDict, deque
from typing import Callable

from fastapi import Request


def client_key(request: Request) -> str:
    """The caller's IP. Behind Cloud Run the Google front end APPENDS the address it
    saw to X-Forwarded-For, so the right-most entry is the one a client cannot forge;
    anything to its left came from the client itself."""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd.strip():
        return fwd.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """A sliding-window limit per client key, held in process memory. With min
    instances 1 / max 3 each instance counts on its own, which is fine for a light
    abuse brake. The client table is bounded: past max_clients the least recently
    seen client is forgotten."""

    def __init__(self, limit: int, window_seconds: float, max_clients: int = 10_000,
                 now: Callable[[], float] = time.monotonic) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self.now = now                  # indirection so tests can move the clock
        self.hits: "OrderedDict[str, deque[float]]" = OrderedDict()

    def limited(self, key: str) -> bool:
        """True when this call is over the limit. A refused call is not recorded."""
        now = self.now()
        q = self.hits.get(key)
        if q is None:
            q = deque()
            self.hits[key] = q
            while len(self.hits) > self.max_clients:
                self.hits.popitem(last=False)
        else:
            self.hits.move_to_end(key)
        while q and now - q[0] >= self.window_seconds:
            q.popleft()
        if len(q) >= self.limit:
            return True
        q.append(now)
        return False

    def clear(self) -> None:
        self.hits.clear()
```

- [ ] **Step 4: Run the unit tests.** `python -m pytest tests/test_rate_limit.py -q` → 7 passed.

- [ ] **Step 5: Switch `routers/events.py` to the shared limiter.**
  1. Delete `_RATE_LIMIT`, `_RATE_WINDOW_SECONDS`, `_MAX_CLIENTS`, `_hits`, `_now`, `_client_key` and `_rate_limited`. Keep the comment about the light per-client limit.
  2. Add:

```python
from services.rate_limit import RateLimiter, client_key

# A light per-client limit. One real visit posts about a dozen events over minutes;
# this allows several times that per minute, so it only ever bites a script.
_limiter = RateLimiter(int(os.getenv("EVENTS_RATE_LIMIT", "60")),
                       float(os.getenv("EVENTS_RATE_WINDOW_SECONDS", "60")))
```

  3. In `post_event`, replace `if _rate_limited(_client_key(request)):` with `if _limiter.limited(client_key(request)):`.
  4. Remove any import that is now unused. Check with `grep -n "time\.\|OrderedDict\|deque" routers/events.py` (the `time` module, `OrderedDict` and `deque` are likely unused after the change).

- [ ] **Step 6: Update `backend/tests/test_events_router.py`.**
  1. Fixture: replace `events_router._hits.clear()` (both lines) with `events_router._limiter.clear()`.
  2. In `test_one_client_is_rate_limited_and_another_is_not` and `test_a_forged_forwarded_for_prefix_does_not_dodge_the_limit`, replace `monkeypatch.setattr(events_router, "_RATE_LIMIT", N)` with `monkeypatch.setattr(events_router._limiter, "limit", N)`.
  3. **Delete** `test_the_limit_frees_up_once_the_window_passes` and `test_the_limiter_forgets_the_least_recent_client_past_its_bound`; they now live in `test_rate_limit.py`.

- [ ] **Step 7: Run the events and limiter tests.**
`python -m pytest tests/test_events_router.py tests/test_rate_limit.py tests/test_events_sheets.py -q` → all pass.

- [ ] **Step 8: Commit.**

```bash
git add backend/services/rate_limit.py backend/routers/events.py backend/tests/test_rate_limit.py backend/tests/test_events_router.py
git commit -m "refactor(events): extract the per-client limiter into services/rate_limit.py

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Per-IP limit on the live analysis endpoint

**Files:**
- Modify: `backend/routers/landing.py`
- Test: `backend/tests/test_landing_router.py`, `frontend/src/landing/LandingPage.test.tsx`

**Interfaces:**
- Consumes: `RateLimiter` and `client_key` (Task 1).
- Produces:
  - `routers.landing._limiter: RateLimiter` and `routers.landing.RATE_LIMIT_MESSAGE: str`.
  - A 429 response body with the normal shape `{"results": [], "invalid": [], "error": RATE_LIMIT_MESSAGE}`. The frontend already renders `error` verbatim and does not count a run with an error, so **no frontend code change is needed**, only a test.

- [ ] **Step 1: Write the failing backend tests.**
  1. Add `import routers.landing as landing_router` to the imports of `backend/tests/test_landing_router.py`.
  2. Add a second autouse fixture below `_isolated_landing_cache`:

```python
@pytest.fixture(autouse=True)
def _reset_landing_limiter():
    landing_router._limiter.clear()
    yield
    landing_router._limiter.clear()
```

  3. Add at the end of the file (an empty ticker list is the cheapest valid request; no engine runs):

```python
# --- Deployment spec §5.2: a per-IP brake on the live, expensive endpoint ---

def _post(ip: str) -> "object":
    return client.post("/api/landing/analyze", json={"tickers": []},
                       headers={"x-forwarded-for": ip})


def test_one_ip_is_limited_with_a_readable_429_and_another_is_not(monkeypatch):
    monkeypatch.setattr(landing_router._limiter, "limit", 2)
    first, second, third = (_post("203.0.113.7") for _ in range(3))
    assert first.status_code == 200 and second.status_code == 200
    assert third.status_code == 429
    assert third.json() == {"results": [], "invalid": [],
                            "error": landing_router.RATE_LIMIT_MESSAGE}
    assert _post("198.51.100.9").status_code == 200


def test_a_forged_forwarded_for_prefix_does_not_dodge_the_landing_limit(monkeypatch):
    monkeypatch.setattr(landing_router._limiter, "limit", 2)
    codes = [client.post("/api/landing/analyze", json={"tickers": []},
                         headers={"x-forwarded-for": f"10.0.0.{i}, 203.0.113.7"}).status_code
             for i in range(3)]
    assert codes == [200, 200, 429]


def test_a_limited_request_never_reaches_the_engines(monkeypatch):
    monkeypatch.setattr(landing_router._limiter, "limit", 0)
    with patch("routers.landing.get_analysis", new=AsyncMock()) as ga, \
         patch("routers.landing.validate_ticker", new=AsyncMock(return_value=True)) as vt:
        resp = client.post("/api/landing/analyze", json={"tickers": ["AAPL"]})
    assert resp.status_code == 429
    ga.assert_not_awaited()
    vt.assert_not_awaited()


def test_the_default_limit_is_twenty_per_minute():
    assert landing_router._limiter.limit == 20
    assert landing_router._limiter.window_seconds == 60
```

- [ ] **Step 2: Run them to verify they fail.**
`cd backend && python -m pytest tests/test_landing_router.py -q` → FAIL (`AttributeError: module 'routers.landing' has no attribute '_limiter'`).

- [ ] **Step 3: Implement it in `backend/routers/landing.py`.**
  1. Imports:

```python
import asyncio
import os
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from services.rate_limit import RateLimiter, client_key
```

  2. Below `MAX_TICKERS = 3`:

```python
# A per-IP brake on this public endpoint: an uncached ticker runs all four engines
# against Yahoo. A real visitor runs a handful per minute; this only bites a script.
RATE_LIMIT_MESSAGE = "Too many analyses from your network. Please wait a minute and try again."
_limiter = RateLimiter(int(os.getenv("LANDING_RATE_LIMIT", "20")),
                       float(os.getenv("LANDING_RATE_WINDOW_SECONDS", "60")))
```

  3. Change the signature and add the check as the first statement:

```python
@router.post("/landing/analyze")
async def analyze(req: LandingAnalyzeRequest, request: Request):
    if _limiter.limited(client_key(request)):
        # Same three-key shape as every other return: the page renders `error` verbatim.
        return JSONResponse(status_code=429, content={
            "results": [], "invalid": [], "error": RATE_LIMIT_MESSAGE})
```

  4. In the existing comment above `runs = await asyncio.gather(...)`, change "serves fundamentals from a 3-day cache" to "serves fundamentals from a multi-day cache (LANDING_SLOW_TTL; 7 days in production)".

- [ ] **Step 4: Run the landing router tests.** `python -m pytest tests/test_landing_router.py -q` → all pass.

- [ ] **Step 5: Add the frontend 429 test.** Add it inside `describe('LandingPage analyze (fix round 2)', …)` in `frontend/src/landing/LandingPage.test.tsx`, next to "does not count a typed run when the server returns an error":

```tsx
  it('shows the rate-limit message from a 429 and does not count the run', async () => {
    await renderSettled()
    const limited = 'Too many analyses from your network. Please wait a minute and try again.'
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 429,
      json: async () => ({ results: [], invalid: [], error: limited }),
    }))

    await userEvent.type(screen.getByRole('textbox'), 'NVDA')
    await userEvent.click(screen.getByRole('button', { name: 'Analyze →' }))
    await waitFor(() => {
      expect(screen.getByText(limited)).toBeInTheDocument()
    })

    expect(runsUsed()).toBe(0)
  })
```

- [ ] **Step 6: Run it.** `cd frontend && npx vitest run src/landing/LandingPage.test.tsx` → all pass. It passes without a code change, which documents that the existing error path already covers a 429.

- [ ] **Step 7: Commit.**

```bash
git add backend/routers/landing.py backend/tests/test_landing_router.py frontend/src/landing/LandingPage.test.tsx
git commit -m "feat(landing): per-IP rate limit on /api/landing/analyze (429, readable message)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Cache cap from env (256) and the chip-list sync guard

**Files:**
- Modify: `backend/landing/cache.py:62-68`
- Test: `backend/tests/test_landing_cache.py` (append), `backend/tests/test_landing_marquee_sync.py` (new)

**Interfaces:**
- Produces: `landing.cache.MAX_ENTRIES: int`, read from `LANDING_CACHE_MAX_ENTRIES` (default `256`) at import.
- Consumes: `main.LANDING_MARQUEE_TICKERS` (unchanged: `["AAPL", "MSFT", "NVDA"]`).

- [ ] **Step 1: Write the failing tests.**
  1. Append to `backend/tests/test_landing_cache.py`:

```python
def test_the_cache_cap_defaults_to_256_and_follows_its_env_var():
    import subprocess, sys
    from pathlib import Path
    backend = Path(__file__).resolve().parents[1]
    probe = "import landing.cache as c; print(c.MAX_ENTRIES)"
    env_default = {k: v for k, v in __import__("os").environ.items()
                   if k != "LANDING_CACHE_MAX_ENTRIES"}
    out = subprocess.run([sys.executable, "-c", probe], cwd=backend, env=env_default,
                         capture_output=True, text=True, check=True).stdout.strip()
    assert out == "256"
    out = subprocess.run([sys.executable, "-c", probe], cwd=backend,
                         env={**env_default, "LANDING_CACHE_MAX_ENTRIES": "7"},
                         capture_output=True, text=True, check=True).stdout.strip()
    assert out == "7"
```

  2. Create `backend/tests/test_landing_marquee_sync.py`:

```python
import re
from pathlib import Path

import main


def test_backend_prewarms_exactly_the_frontend_compare_chips():
    # Two hand-kept copies of one list drift: a chip missing from the backend list is
    # silently never pre-warmed, so its first visitor after each deploy waits.
    src = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "landing"
           / "components" / "Hero.tsx").read_text(encoding="utf-8")
    m = re.search(r"export const COMPARE_TICKERS = \[([^\]]*)\]", src)
    assert m, "COMPARE_TICKERS not found in Hero.tsx"
    chips = re.findall(r"'([A-Z][A-Z.\-]*)'", m.group(1))
    assert chips == main.LANDING_MARQUEE_TICKERS
```

- [ ] **Step 2: Run them.**
`cd backend && python -m pytest tests/test_landing_cache.py -k cache_cap tests/test_landing_marquee_sync.py -q`
Expected: the cap test FAILS (prints `64`); the sync test PASSES already (it's a guard, and that's fine).

- [ ] **Step 3: Implement it.** In `backend/landing/cache.py`, replace `MAX_ENTRIES = 64` with the line below and keep the existing comment above it, adding one sentence to it:

```python
# 256 by default (deployment spec §6): an entry is a few tens of KB, so 256 fits easily
# in a 1 GiB instance and keeps most demo tickers for their full TTL.
MAX_ENTRIES = int(os.getenv("LANDING_CACHE_MAX_ENTRIES", "256"))
```

  Also change the comment line `SLOW_TTL = ...   # 3 days` to `# 3 days by default; production sets 7 days`, and after `FAST_TTL` add the comment `# 1 hour by default; production sets 4 hours (LANDING_FAST_TTL=14400)`.

- [ ] **Step 4: Run the whole cache file plus the sync test.**
`python -m pytest tests/test_landing_cache.py tests/test_landing_marquee_sync.py -q` → all pass. The existing LRU test loops `MAX_ENTRIES` times; it is still fast because the engines are mocked.

- [ ] **Step 5: Commit.**

```bash
git add backend/landing/cache.py backend/tests/test_landing_cache.py backend/tests/test_landing_marquee_sync.py
git commit -m "feat(landing): cache cap from LANDING_CACHE_MAX_ENTRIES (256); guard chip/pre-warm list sync

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Key-free Sheets access (ADC fallback)

**Files:**
- Modify: `backend/services/sheets.py` (imports at lines 1–9; `_get_service` at lines 48–63)
- Test: `backend/tests/test_sheets_credentials.py` (new)

**Interfaces:**
- Produces: `services.sheets._get_service()`. Credential order: `GOOGLE_SHEETS_CREDS_JSON` → the key file at `GOOGLE_SHEETS_CREDS_PATH` (default `./credentials/service_account.json`) **if it exists** → `google.auth.default(scopes=SCOPES)`. `services/events_sheets.py` already calls this, so it is unchanged.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_sheets_credentials.py`:

```python
from unittest.mock import MagicMock, patch

import services.sheets as sheets


def _fresh(monkeypatch):
    monkeypatch.setattr(sheets, "_service", None)
    monkeypatch.delenv("GOOGLE_SHEETS_CREDS_JSON", raising=False)


def test_falls_back_to_the_runtime_identity_without_json_or_key_file(monkeypatch, tmp_path):
    # Cloud Run: no key exists anywhere; the runtime service account is the identity.
    _fresh(monkeypatch)
    monkeypatch.setenv("GOOGLE_SHEETS_CREDS_PATH", str(tmp_path / "missing.json"))
    adc = MagicMock(name="adc-creds")
    with patch("services.sheets.google.auth.default", return_value=(adc, "proj")) as default, \
         patch("services.sheets.build") as build:
        sheets._get_service()
    default.assert_called_once_with(scopes=sheets.SCOPES)
    assert build.call_args.kwargs["credentials"] is adc


def test_a_present_key_file_still_wins_over_the_runtime_identity(monkeypatch, tmp_path):
    _fresh(monkeypatch)
    key = tmp_path / "sa.json"
    key.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_SHEETS_CREDS_PATH", str(key))
    with patch("services.sheets.service_account.Credentials.from_service_account_file",
               return_value="file-creds") as from_file, \
         patch("services.sheets.google.auth.default") as default, \
         patch("services.sheets.build") as build:
        sheets._get_service()
    from_file.assert_called_once_with(str(key), scopes=sheets.SCOPES)
    default.assert_not_called()
    assert build.call_args.kwargs["credentials"] == "file-creds"


def test_the_json_env_var_wins_over_everything(monkeypatch):
    _fresh(monkeypatch)
    monkeypatch.setenv("GOOGLE_SHEETS_CREDS_JSON", '{"type": "service_account"}')
    with patch("services.sheets.service_account.Credentials.from_service_account_info",
               return_value="json-creds") as from_info, \
         patch("services.sheets.google.auth.default") as default, \
         patch("services.sheets.build"):
        sheets._get_service()
    from_info.assert_called_once_with({"type": "service_account"}, scopes=sheets.SCOPES)
    default.assert_not_called()
```

- [ ] **Step 2: Run them to verify they fail.**
`cd backend && python -m pytest tests/test_sheets_credentials.py -q` → the first test FAILS: `AttributeError: module 'services.sheets' has no attribute 'google'`, or a `FileNotFoundError` from the missing key file.

- [ ] **Step 3: Implement it.**
  1. In `backend/services/sheets.py` add `import google.auth` next to `from google.oauth2 import service_account`.
  2. Replace the body of `_get_service`:

```python
def _get_service():
    global _service
    if _service is None:
        # Resolution order: the raw JSON env var (any host), then the on-disk key file
        # (local dev, GOOGLE_SHEETS_CREDS_PATH, default ./credentials/), then
        # Application Default Credentials — on Cloud Run that is the service's runtime
        # service account, so production holds no key at all (deployment spec §5.1).
        creds_json = os.environ.get("GOOGLE_SHEETS_CREDS_JSON")
        creds_path = os.environ.get("GOOGLE_SHEETS_CREDS_PATH", "./credentials/service_account.json")
        if creds_json:
            creds = service_account.Credentials.from_service_account_info(
                json.loads(creds_json), scopes=SCOPES)
        elif os.path.exists(creds_path):
            creds = service_account.Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        else:
            creds, _ = google.auth.default(scopes=SCOPES)
        _service = build("sheets", "v4", credentials=creds)
    return _service
```

- [ ] **Step 4: Run the new tests plus the Sheets suites.**
`python -m pytest tests/test_sheets_credentials.py tests/test_events_sheets.py tests/test_sheets_concurrency.py -q` → all pass.

- [ ] **Step 5: Commit.**

```bash
git add backend/services/sheets.py backend/tests/test_sheets_credentials.py
git commit -m "feat(sheets): fall back to Application Default Credentials (key-free on Cloud Run)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: `create_app` factory and backend public mode

**Files:**
- Modify: `backend/main.py`
- Test: `backend/tests/test_public_mode.py` (new)

**Interfaces:**
- Produces: `main.create_app(*, public_mode: bool | None = None, static_dir: str | None = None, canonical_host: str | None = None) -> FastAPI`.
  - `None` means "read the env": `INTRINSICA_PUBLIC_MODE == "1"`, `INTRINSICA_STATIC_DIR`, `CANONICAL_HOST`.
  - `static_dir` and `canonical_host` are accepted now but only wired in Tasks 6 and 7.
- `main.app = create_app()` stays, so `uvicorn main:app` and every test that imports `main.app` keep working.
- `main.lifespan`, `main.seed` and `main.LANDING_MARQUEE_TICKERS` stay module-level. `test_events_sheets.py` monkeypatches `main.seed`.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_public_mode.py`:

```python
from fastapi.testclient import TestClient

from main import create_app

# The Agent Stock analyst routes (routers/analysis.py, database.py, watchlists.py).
ANALYST_PATHS = {
    "/api/analyse", "/api/ticker/{ticker}/recalculate", "/api/recalculate-all",
    "/api/stream/{job_id}", "/api/cancel/{job_id}", "/api/database",
    "/api/database/{ticker}", "/api/screener/{ticker}", "/api/risk-reward/{ticker}",
    "/api/watchlists", "/api/watchlists/{name}",
}
FAKE_DOOR_PATHS = {"/api/landing/analyze", "/api/events", "/api/health"}


def _paths(app) -> set[str]:
    return {getattr(r, "path", "") for r in app.routes}


def test_public_mode_mounts_only_the_fake_door_apis():
    paths = _paths(create_app(public_mode=True, static_dir="", canonical_host=""))
    assert FAKE_DOOR_PATHS <= paths
    assert not (ANALYST_PATHS & paths)


def test_public_mode_answers_404_for_an_analyst_api():
    client = TestClient(create_app(public_mode=True, static_dir="", canonical_host=""))
    assert client.get("/api/database").status_code == 404
    assert client.get("/api/health").json() == {"status": "ok"}


def test_local_dev_keeps_the_analyst_apis():
    paths = _paths(create_app(public_mode=False, static_dir="", canonical_host=""))
    assert ANALYST_PATHS <= paths
    assert FAKE_DOOR_PATHS <= paths


def test_public_mode_reads_its_env_var(monkeypatch):
    monkeypatch.setenv("INTRINSICA_PUBLIC_MODE", "1")
    assert not (ANALYST_PATHS & _paths(create_app(static_dir="", canonical_host="")))
    monkeypatch.setenv("INTRINSICA_PUBLIC_MODE", "0")
    assert ANALYST_PATHS <= _paths(create_app(static_dir="", canonical_host=""))
```

- [ ] **Step 2: Run them to verify they fail.**
`cd backend && python -m pytest tests/test_public_mode.py -q` → `ImportError: cannot import name 'create_app'`.

- [ ] **Step 3: Implement it.** Replace everything in `backend/main.py` from `app = FastAPI(title="Intrinsica", lifespan=lifespan)` to the end of the file with the code below. The imports, `load_dotenv()`, `LANDING_MARQUEE_TICKERS`, the task globals and `lifespan` are unchanged.

```python
def _cors_origins() -> list[str]:
    # Comma-separated allowed frontend origins. Defaults to the local Vite dev server;
    # production sets CORS_ORIGINS=https://intrinsica.io (the page is same-origin, so
    # this only stops other sites' pages from calling the API).
    return [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
            if o.strip()]


def create_app(*, public_mode: bool | None = None, static_dir: str | None = None,
               canonical_host: str | None = None) -> FastAPI:
    """Build the app. Each argument left as None is read from the environment:
    INTRINSICA_PUBLIC_MODE ("1" = production: only the fake-door APIs exist — the
    Agent Stock analyst routers are never mounted), INTRINSICA_STATIC_DIR (the built
    frontend to serve) and CANONICAL_HOST (www → apex redirect). Unset, all three
    leave local dev exactly as it was."""
    if public_mode is None:
        public_mode = os.getenv("INTRINSICA_PUBLIC_MODE", "") == "1"
    if static_dir is None:
        static_dir = os.getenv("INTRINSICA_STATIC_DIR", "")
    if canonical_host is None:
        canonical_host = os.getenv("CANONICAL_HOST", "")

    app = FastAPI(title="Intrinsica", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if not public_mode:
        app.include_router(analysis_router, prefix="/api")
        app.include_router(database_router, prefix="/api")
        app.include_router(watchlists_router, prefix="/api")
    app.include_router(events_router, prefix="/api")
    app.include_router(landing_router, prefix="/api")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
```

- [ ] **Step 4: Run the new tests plus everything that imports `main`.**
`python -m pytest tests/test_public_mode.py tests/test_app_metadata.py tests/test_events_sheets.py tests/test_events_router.py tests/test_landing_router.py tests/test_analysis_endpoints.py tests/test_database_router.py tests/test_watchlists_router.py -q` → all pass. (The analyst router tests use `main.app`, which is not in public mode locally.)

- [ ] **Step 5: Commit.**

```bash
git add backend/main.py backend/tests/test_public_mode.py
git commit -m "feat(app): create_app factory; public mode mounts only the fake-door APIs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: FastAPI serves the built frontend (SPA)

**Files:**
- Create: `backend/spa.py`
- Modify: `backend/main.py` (inside `create_app`, just before `return app`)
- Test: `backend/tests/test_spa.py` (new)

**Interfaces:**
- Consumes: `create_app(..., static_dir=...)` (Task 5).
- Produces: `spa.mount_spa(app: FastAPI, static_dir: str) -> bool`. It registers a catch-all `GET /{path:path}` and returns False (registering nothing) when `static_dir` is empty or has no `index.html`. **It must be the last route registered.**

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_spa.py`:

```python
import pytest
from fastapi.testclient import TestClient

from main import create_app


@pytest.fixture
def static_dir(tmp_path):
    site = tmp_path / "site"
    (site / "assets").mkdir(parents=True)
    (site / "index.html").write_text("<!doctype html><title>Intrinsica</title>", encoding="utf-8")
    (site / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (site / "og-image.png").write_bytes(b"\x89PNG fake")
    (tmp_path / "secret.txt").write_text("TOP-SECRET", encoding="utf-8")   # outside the site
    return site


@pytest.fixture
def client(static_dir):
    return TestClient(create_app(public_mode=True, static_dir=str(static_dir), canonical_host=""))


def test_root_serves_index_and_is_never_cached(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "<title>Intrinsica</title>" in r.text
    assert r.headers["cache-control"] == "no-cache"


@pytest.mark.parametrize("path", ["/checkout", "/t/AMZN", "/app", "/database"])
def test_client_side_routes_fall_back_to_index(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert "<title>Intrinsica</title>" in r.text


def test_hashed_assets_are_cached_for_a_year(client):
    r = client.get("/assets/index-abc123.js")
    assert r.status_code == 200
    assert r.text == "console.log(1)"
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_other_real_files_get_a_short_cache(client):
    r = client.get("/og-image.png")
    assert r.status_code == 200
    assert r.content == b"\x89PNG fake"
    assert r.headers["cache-control"] == "public, max-age=3600"


@pytest.mark.parametrize("path", ["/api", "/api/nope", "/api/database", "/api/landing/analyze"])
def test_api_paths_never_fall_back_to_the_page(client, path):
    # /api/landing/analyze is POST-only: a GET must not be answered with index.html.
    r = client.get(path)
    assert r.status_code in (404, 405)
    assert "text/html" not in r.headers.get("content-type", "")


def test_real_api_routes_still_win(client):
    assert client.get("/api/health").json() == {"status": "ok"}


@pytest.mark.parametrize("path", ["/%2e%2e/secret.txt", "/assets/..%2f..%2f..%2fsecret.txt",
                                  "/..%5c..%5csecret.txt"])
def test_path_traversal_cannot_leave_the_static_dir(client, path):
    r = client.get(path)
    assert "TOP-SECRET" not in r.text


def test_no_static_dir_registers_no_frontend_routes():
    client = TestClient(create_app(public_mode=True, static_dir="", canonical_host=""))
    assert client.get("/").status_code == 404


def test_a_static_dir_without_index_is_ignored(tmp_path):
    client = TestClient(create_app(public_mode=True, static_dir=str(tmp_path), canonical_host=""))
    assert client.get("/").status_code == 404
```

- [ ] **Step 2: Run them to verify they fail.**
`cd backend && python -m pytest tests/test_spa.py -q` → the index and asset tests FAIL with 404.

- [ ] **Step 3: Implement `backend/spa.py`:**

```python
from __future__ import annotations
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

# Vite fingerprints everything under assets/, so a changed file gets a new name and
# can be cached for good. index.html must always be revalidated, or a deploy would not
# reach returning visitors. Other root files (og-image.png, favicon) get an hour.
_IMMUTABLE = "public, max-age=31536000, immutable"
_SHORT = "public, max-age=3600"
_NO_CACHE = "no-cache"


def mount_spa(app: FastAPI, static_dir: str) -> bool:
    """Serve the built frontend from static_dir: real files as-is, every other non-/api
    path as index.html (React Router takes it from there — including future /t/AMZN
    share links). /api/* never falls back to the page: an unknown API path is a JSON
    404, so the frontend never parses HTML as JSON. Register this LAST: its catch-all
    would otherwise shadow later routes. Returns False, registering nothing, when
    static_dir is unset or has no index.html (local dev, where Vite serves the page)."""
    if not static_dir:
        return False
    root = Path(static_dir).resolve()
    index = root / "index.html"
    if not index.is_file():
        return False
    assets = root / "assets"

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path == "api" or path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        if path:
            candidate = (root / path).resolve()
            # resolve() collapses ../ and follows links; is_relative_to then refuses
            # anything that ended up outside the static dir (path traversal).
            if candidate.is_relative_to(root) and candidate.is_file() and candidate != index:
                cache = _IMMUTABLE if candidate.is_relative_to(assets) else _SHORT
                return FileResponse(candidate, headers={"Cache-Control": cache})
        return FileResponse(index, headers={"Cache-Control": _NO_CACHE})

    return True
```

- [ ] **Step 4: Wire it in.** In `backend/main.py`, add `from spa import mount_spa` to the imports, and in `create_app` directly before `return app`:

```python
    # Last: the SPA catch-all must not shadow any API route registered above.
    mount_spa(app, static_dir)
```

- [ ] **Step 5: Run the tests.** `python -m pytest tests/test_spa.py tests/test_public_mode.py -q` → all pass.
  - If a traversal case returns 404 instead of 200, that is fine; the assertion only requires that the secret is not served.
  - If `GET /api/landing/analyze` returns 405, that is fine too (Starlette's method mismatch).

- [ ] **Step 6: Commit.**

```bash
git add backend/spa.py backend/main.py backend/tests/test_spa.py
git commit -m "feat(app): serve the built frontend from FastAPI (SPA fallback, /api 404, cache headers)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: `www` → apex redirect

**Files:**
- Create: `backend/canonical.py`
- Modify: `backend/main.py` (inside `create_app`, right after the CORS middleware)
- Test: `backend/tests/test_canonical.py` (new)

**Interfaces:**
- Consumes: `create_app(..., canonical_host=...)` (Task 5).
- Produces: `canonical.add_canonical_host_redirect(app: FastAPI, canonical_host: str) -> None`. It does nothing when `canonical_host` is empty.

- [ ] **Step 1: Write the failing tests** in `backend/tests/test_canonical.py`:

```python
from fastapi.testclient import TestClient

from main import create_app


def _client(host: str = "intrinsica.io") -> TestClient:
    return TestClient(create_app(public_mode=True, static_dir="", canonical_host=host))


def test_www_is_permanently_redirected_to_the_apex_keeping_path_and_query():
    r = _client().get("/t/AMZN?ref=x", headers={"host": "www.intrinsica.io"},
                      follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://intrinsica.io/t/AMZN?ref=x"


def test_www_with_a_port_is_still_redirected():
    r = _client().get("/", headers={"host": "www.intrinsica.io:443"}, follow_redirects=False)
    assert r.status_code == 301
    assert r.headers["location"] == "https://intrinsica.io/"


def test_the_apex_is_served_not_redirected():
    r = _client().get("/api/health", headers={"host": "intrinsica.io"}, follow_redirects=False)
    assert r.status_code == 200


def test_no_canonical_host_means_no_redirect():
    r = _client(host="").get("/api/health", headers={"host": "www.intrinsica.io"},
                             follow_redirects=False)
    assert r.status_code == 200
```

- [ ] **Step 2: Run them to verify they fail.**
`cd backend && python -m pytest tests/test_canonical.py -q` → the first two FAIL (status 200/404 instead of 301).

- [ ] **Step 3: Implement `backend/canonical.py`:**

```python
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse


def add_canonical_host_redirect(app: FastAPI, canonical_host: str) -> None:
    """301 www.<canonical_host> to https://<canonical_host>, keeping path and query, so
    every shared link and og:url has one address. Both hosts are mapped to the same
    Cloud Run service; only www is redirected (never the apex, so no loop). A no-op
    when canonical_host is empty (local dev)."""
    if not canonical_host:
        return
    www = f"www.{canonical_host}".lower()

    @app.middleware("http")
    async def _to_canonical(request: Request, call_next):
        host = request.headers.get("host", "").split(":")[0].lower()
        if host == www:
            target = f"https://{canonical_host}{request.url.path}"
            if request.url.query:
                target += f"?{request.url.query}"
            return RedirectResponse(target, status_code=301)
        return await call_next(request)
```

- [ ] **Step 4: Wire it in.** In `backend/main.py` add `from canonical import add_canonical_host_redirect`, and in `create_app` directly after the `app.add_middleware(CORSMiddleware, ...)` call:

```python
    add_canonical_host_redirect(app, canonical_host)
```

- [ ] **Step 5: Run the tests.** `python -m pytest tests/test_canonical.py tests/test_spa.py tests/test_public_mode.py -q` → all pass.

- [ ] **Step 6: Commit.**

```bash
git add backend/canonical.py backend/main.py backend/tests/test_canonical.py
git commit -m "feat(app): 301 www.intrinsica.io to the apex (CANONICAL_HOST)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Frontend public mode and same-origin API in production

**Files:**
- Modify: `frontend/src/App.tsx`, `frontend/src/vite-env.d.ts`, `frontend/src/lib/api.ts`
- Test: `frontend/src/App.test.tsx` (new)

**Interfaces:**
- Produces:
  - `VITE_PUBLIC_MODE=1` at build time: only `/`, `/checkout` and a catch-all `*` → `LandingPage` exist.
  - `API_BASE`: `VITE_API_BASE` if set; otherwise `''` (same-origin) in production builds and `http://localhost:8000` in dev and test.
  - **Deviation from spec §2.2 (same outcome):** the Dockerfile needs no `VITE_API_BASE` build arg, because a production build defaults to same-origin by itself.

- [ ] **Step 1: Write the failing tests** in `frontend/src/App.test.tsx`:

```tsx
import type { ReactNode } from 'react'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./landing/LandingPage', () => ({ default: () => <div>landing-page</div> }))
vi.mock('./landing/CheckoutPage', () => ({ default: () => <div>checkout-page</div> }))
vi.mock('./pages/Home', () => ({ default: () => <div>home-page</div> }))
vi.mock('./pages/Database', () => ({ default: () => <div>database-page</div> }))
vi.mock('./pages/Progress', () => ({ default: () => <div>progress-page</div> }))
vi.mock('./pages/Results', () => ({ default: () => <div>results-page</div> }))
vi.mock('./pages/TickerDetail', () => ({ default: () => <div>ticker-page</div> }))
vi.mock('./components/Layout', () => ({
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}))

// App reads VITE_PUBLIC_MODE once at module load (so a production build can drop the
// analyst pages), so each case re-imports it after stubbing the env.
async function renderAt(path: string) {
  window.history.pushState({}, '', path)
  vi.resetModules()
  const { default: App } = await import('./App')
  render(<App />)
}

afterEach(() => {
  vi.unstubAllEnvs()
  window.history.pushState({}, '', '/')
})

describe('App routes in public mode (production)', () => {
  it.each(['/app', '/database', '/results/j1', '/progress/j1', '/ticker/j1/AAPL'])(
    'shows the landing page instead of the analyst page at %s', async (path) => {
      vi.stubEnv('VITE_PUBLIC_MODE', '1')
      await renderAt(path)
      expect(screen.getByText('landing-page')).toBeInTheDocument()
      expect(screen.queryByText(/^(home|database|progress|results|ticker)-page$/)).toBeNull()
    })

  it('shows the landing page for unknown paths such as future share links', async () => {
    vi.stubEnv('VITE_PUBLIC_MODE', '1')
    await renderAt('/t/AMZN')
    expect(screen.getByText('landing-page')).toBeInTheDocument()
  })

  it('keeps the checkout page', async () => {
    vi.stubEnv('VITE_PUBLIC_MODE', '1')
    await renderAt('/checkout')
    expect(screen.getByText('checkout-page')).toBeInTheDocument()
  })
})

describe('App routes in local dev (flag unset)', () => {
  it('still serves the analyst app', async () => {
    vi.stubEnv('VITE_PUBLIC_MODE', '')
    await renderAt('/database')
    expect(screen.getByText('database-page')).toBeInTheDocument()
    expect(screen.queryByText('landing-page')).toBeNull()
  })
})
```

- [ ] **Step 2: Run them to verify they fail.**
`cd frontend && npx vitest run src/App.test.tsx` → the public-mode cases FAIL (the analyst pages render; `/t/AMZN` renders nothing).

- [ ] **Step 3: Implement the routes.**
  1. In `frontend/src/vite-env.d.ts`, add `readonly VITE_PUBLIC_MODE?: string` to `ImportMetaEnv`.
  2. In `frontend/src/App.tsx`, add below the imports:

```tsx
/** Production builds set VITE_PUBLIC_MODE=1: intrinsica.io serves only the fake door.
 *  The Agent Stock analyst pages are not registered, and because Vite inlines this
 *  constant at build time Rollup drops them from the bundle. Every other path shows
 *  the landing page (future /t/{TICKER} share links included). Unset in local dev. */
const PUBLIC_MODE = import.meta.env.VITE_PUBLIC_MODE === '1'
```

  3. Replace the `<Routes>` body with:

```tsx
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/checkout" element={<CheckoutPage />} />
        {PUBLIC_MODE ? (
          <Route path="*" element={<LandingPage />} />
        ) : (
          <>
            <Route path="/app" element={<Layout><Home /></Layout>} />
            <Route path="/progress/:jobId" element={<Layout><Progress /></Layout>} />
            <Route path="/results/:jobId" element={<Layout><Results /></Layout>} />
            <Route path="/ticker/:jobId/:ticker" element={<Layout><TickerDetail /></Layout>} />
            <Route path="/database" element={<Layout><Database /></Layout>} />
          </>
        )}
      </Routes>
```

  4. Extend the component's doc comment with one line: "In public mode (production) only `/` and `/checkout` exist; see PUBLIC_MODE."

- [ ] **Step 4: Implement the same-origin default.** Replace `frontend/src/lib/api.ts` with:

```ts
// Backend API base URL. VITE_API_BASE overrides it at build time. Otherwise a
// production build calls its own origin (the Cloud Run service serves the page and
// /api together), and dev/test fall back to the local backend so `npm run dev` +
// start.sh keep working with no config.
export const API_BASE =
  import.meta.env.VITE_API_BASE ?? (import.meta.env.PROD ? '' : 'http://localhost:8000')
```

- [ ] **Step 5: Run the frontend suite and type check.**
`npx vitest run` → all pass (395 plus the new ones). Then `npx tsc -b` → clean.

- [ ] **Step 6: Run the lint baseline.** `npx eslint . 2>&1 | tail -3` → at most **6** problems. If the count grew, fix the new finding before committing.

- [ ] **Step 7: Check the production bundle** (Review Focus 3):

```bash
cd frontend
VITE_PUBLIC_MODE=1 npm run build
grep -l "localhost:8000" dist/assets/*.js || echo "OK: no localhost API base"
grep -l "Apply a filter before saving a watchlist" dist/assets/*.js || echo "OK: analyst pages dropped"
```

  Expected: both `OK` lines.
  - If the second grep finds a file, Rollup kept the analyst pages. Switch the five analyst imports in `App.tsx` to `React.lazy(() => import('./pages/X'))`, wrap the analyst branch's elements in `<Suspense fallback={null}>`, rebuild, and confirm that no chunk containing that string is imported from the entry chunk (`grep -l "pages/Database" dist/assets/index-*.js` → none).
  - Then run `npm run build` once **without** the flag, so a local `dist/` is not left in public mode by accident. `dist/` is gitignored either way.

- [ ] **Step 8: Commit.**

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/vite-env.d.ts frontend/src/lib/api.ts
git commit -m "feat(frontend): public mode drops the analyst pages; production calls the API same-origin

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: The single container image

**Files:**
- Create: `Dockerfile` (root), `.dockerignore` (root), `backend/requirements-dev.txt`
- Delete: `backend/Dockerfile`, `backend/.dockerignore`

**Interfaces:**
- Consumes: `INTRINSICA_STATIC_DIR` (Task 6), `VITE_PUBLIC_MODE` (Task 8).
- Produces: an image that listens on `$PORT` (8080) and serves the page and `/api`. `backend/requirements-dev.txt` is used by the Task 10 CI steps.

- [ ] **Step 1: Create `backend/requirements-dev.txt`:**

```
# Test-only dependencies (CI and local). Never installed in the production image.
pytest==9.0.3
pytest-asyncio==1.3.0
```

- [ ] **Step 2: Create the root `Dockerfile`:**

```dockerfile
# Intrinsica — ONE image for Cloud Run: the React build is served by the FastAPI
# backend next to /api (deployment spec §2.2). Build context is the repo root.

# ---- Stage 1: build the frontend -------------------------------------------------
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Public mode: only the fake door is built in. The API base needs no arg — a
# production build calls its own origin (src/lib/api.ts).
ENV VITE_PUBLIC_MODE=1
RUN npm run build

# ---- Stage 2: the backend, serving the build -------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first so the layer is cached across code-only changes.
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ .
COPY --from=frontend /frontend/dist /app/static

ENV INTRINSICA_STATIC_DIR=/app/static \
    PORT=8080
EXPOSE 8080

# Shell form so ${PORT} (injected by Cloud Run) is expanded. No --reload in production.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
```

- [ ] **Step 3: Create the root `.dockerignore`, then delete the old backend files:**

```
# Keep the build context small and never bake secrets in.
.git
.github
.claude
.superpowers
brand
docs
MonetizationPlan
**/node_modules
**/__pycache__
**/*.pyc
**/.pytest_cache
frontend/dist
frontend/.env
frontend/.env.*
!frontend/.env.example
backend/.env
backend/credentials
backend/jobs
backend/tests
*.ps1
```

```bash
git rm backend/Dockerfile backend/.dockerignore
```

- [ ] **Step 4: Simulate the container locally.** Docker is not installed on this machine, so the image itself is first built by Cloud Build.

```bash
cd frontend && VITE_PUBLIC_MODE=1 npm run build && cd ../backend
INTRINSICA_PUBLIC_MODE=1 INTRINSICA_STATIC_DIR=../frontend/dist CANONICAL_HOST=intrinsica.io \
  python -m uvicorn main:app --port 8080
```

  Run that in the background, then check:

```bash
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" localhost:8080/            # 200 text/html
curl -s localhost:8080/api/health                                                     # {"status":"ok"}
curl -s -o /dev/null -w "%{http_code}\n" localhost:8080/api/database                  # 404
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" localhost:8080/t/AMZN        # 200 text/html
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" -H "Host: www.intrinsica.io" localhost:8080/t/AMZN  # 301 https://intrinsica.io/t/AMZN
curl -s -X POST localhost:8080/api/landing/analyze -H "Content-Type: application/json" -d '{"tickers":["AAPL"]}' | head -c 200   # JSON results (live Yahoo)
```

  Then open `http://localhost:8080/` in a browser: the landing page renders, and the AAPL card loads via a same-origin `/api/landing/analyze` (DevTools → Network). Stop uvicorn afterwards and rebuild `dist/` without the flag.

- [ ] **Step 5: Commit.**

```bash
git add Dockerfile .dockerignore backend/requirements-dev.txt
git commit -m "build: one root multi-stage image (frontend build served by FastAPI); drop backend-only Dockerfile

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Cloud Build pipelines

**Files:**
- Create: `cloudbuild.yaml`, `cloudbuild-pr.yaml` (repo root)

**Interfaces:**
- Consumes: the root `Dockerfile` (Task 9), `backend/requirements-dev.txt` (Task 9), and the service accounts and Artifact Registry created by the guide (`DEPLOY.md` steps 3–4).
- Produces: the trigger config files named in `DEPLOY.md` step 6: `/cloudbuild.yaml` (the `intrinsica-deploy` trigger, substitution `_SMOKE_URL`) and `/cloudbuild-pr.yaml` (the `intrinsica-pr` trigger).

- [ ] **Step 1: Create `cloudbuild.yaml`:**

```yaml
# Deploy pipeline — trigger "intrinsica-deploy" (push to ^main$). See DEPLOY.md.
# Tests gate everything: a failure in steps 1-5 leaves the running revision untouched.
# All service config lives here and is applied on every deploy (--set-env-vars), so
# the repo is the single source of truth; console edits are overwritten.
substitutions:
  _REGION: europe-west1
  _SERVICE: intrinsica
  _IMAGE: europe-west1-docker.pkg.dev/${PROJECT_ID}/intrinsica/app
  _SMOKE_URL: ""   # set to https://intrinsica.io on the trigger once the domain serves

options:
  logging: CLOUD_LOGGING_ONLY          # required with a user-specified build service account
  dynamicSubstitutions: true

steps:
  - id: backend-tests
    name: python:3.12-slim
    dir: backend
    entrypoint: bash
    args: ["-c", "pip install -q -r requirements.txt -r requirements-dev.txt && python -m pytest -q"]

  - id: frontend-tests
    name: node:22-slim
    dir: frontend
    entrypoint: bash
    args: ["-c", "npm ci && npx vitest run"]
    waitFor: ["-"]

  - id: build
    name: gcr.io/cloud-builders/docker
    args: ["build", "-t", "${_IMAGE}:${SHORT_SHA}", "."]
    waitFor: ["backend-tests", "frontend-tests"]

  - id: push
    name: gcr.io/cloud-builders/docker
    args: ["push", "${_IMAGE}:${SHORT_SHA}"]

  - id: deploy
    name: gcr.io/google.com/cloudsdktool/cloud-sdk:slim
    entrypoint: gcloud
    args:
      - run
      - deploy
      - ${_SERVICE}
      - --image=${_IMAGE}:${SHORT_SHA}
      - --region=${_REGION}
      - --service-account=intrinsica-run@${PROJECT_ID}.iam.gserviceaccount.com
      - --allow-unauthenticated
      - --min-instances=1
      - --max-instances=3
      - --cpu=1
      - --memory=1Gi
      - --cpu-throttling
      - --cpu-boost
      - --concurrency=80
      - --timeout=300
      - --set-env-vars=INTRINSICA_PUBLIC_MODE=1,CANONICAL_HOST=intrinsica.io,CORS_ORIGINS=https://intrinsica.io,INTRINSICA_EVENTS_SHEET_ID=1e4U4roainSuDJPHwsxkVrZezlA2InDPHV1zaQHuCzqY,LANDING_SLOW_TTL=604800,LANDING_FAST_TTL=14400,LANDING_CACHE_MAX_ENTRIES=256,LANDING_RATE_LIMIT=20,LANDING_RATE_WINDOW_SECONDS=60

  - id: smoke
    name: curlimages/curl
    entrypoint: sh
    args:
      - -c
      - |
        if [ -z "${_SMOKE_URL}" ]; then echo "Smoke check skipped: _SMOKE_URL is empty."; exit 0; fi
        for attempt in 1 2 3 4 5; do
          if curl -fsS "${_SMOKE_URL}/api/health" | grep -q '"status":"ok"'; then
            echo "Healthy: ${_SMOKE_URL}"; exit 0
          fi
          sleep 10
        done
        echo "Smoke check FAILED for ${_SMOKE_URL}: roll back per DEPLOY.md (Operations)."; exit 1
```

- [ ] **Step 2: Create `cloudbuild-pr.yaml`:**

```yaml
# PR checks — trigger "intrinsica-pr" (pull request into ^main$). Tests and the
# frontend type-check/build only: nothing is pushed or deployed.
options:
  logging: CLOUD_LOGGING_ONLY

steps:
  - id: backend-tests
    name: python:3.12-slim
    dir: backend
    entrypoint: bash
    args: ["-c", "pip install -q -r requirements.txt -r requirements-dev.txt && python -m pytest -q"]

  - id: frontend-tests-and-build
    name: node:22-slim
    dir: frontend
    entrypoint: bash
    args: ["-c", "npm ci && npx vitest run && VITE_PUBLIC_MODE=1 npm run build"]
    waitFor: ["-"]
```

- [ ] **Step 3: Validate both files.** YAML parses, the pinned values match the Global Constraints, and there are no Agent Stock identifiers:

```bash
python -c "import yaml,sys; [yaml.safe_load(open(f)) for f in ('cloudbuild.yaml','cloudbuild-pr.yaml')]; print('yaml ok')"
grep -n -i "agent\|agentstock\|493915\|GOOGLE_SHEETS" cloudbuild.yaml cloudbuild-pr.yaml || echo "OK: no Agent Stock identifiers"
```

  If PyYAML is missing: `python -m pip install pyyaml` (local only; not a project dependency).

- [ ] **Step 4: Commit.**

```bash
git add cloudbuild.yaml cloudbuild-pr.yaml
git commit -m "ci: Cloud Build deploy pipeline (tests → image → Cloud Run → smoke) and PR checks

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Single-provider cleanup and the deployment guide

**Files:**
- Delete: `frontend/vercel.json`, `backend/railway.json`, `render.yaml`
- Rewrite: `DEPLOY.md`, `backend/.env.example`, `frontend/.env.example`

**Interfaces:**
- Consumes: the file names, trigger names and substitution names from Tasks 9–10, and spec §2.6 and §8.

- [ ] **Step 1: Delete the other hosts' configs.**

```bash
git rm frontend/vercel.json backend/railway.json render.yaml
grep -rn -i "vercel\|railway\|render\.yaml\|agentstock" --include=*.py --include=*.ts --include=*.tsx --include=*.md --include=*.sh --include=*.example . \
  | grep -v node_modules | grep -v "docs/superpowers" || echo "OK"
```

  Fix any remaining hits outside `docs/superpowers/`, for example the comment in `backend/services/sheets.py` or `start.sh`. Historical specs and plans stay as they are.

- [ ] **Step 2: Rewrite `DEPLOY.md`.** Structure, in this order:
  1. `# Deploying Intrinsica`, then a 3-sentence overview: one Cloud Run service `intrinsica` in `europe-west1` serves the page and `/api` from one image. Every push to `main` deploys through Cloud Build. PRs run tests.
  2. `## How it works`: the architecture diagram from spec §2 (copy it verbatim).
  3. `## Configuration`: the env-var table from spec §2.6, copied verbatim, with its two notes. Add one sentence: "To change a value, edit `cloudbuild.yaml` in a PR."
  4. `## One-time setup`: spec §8 steps 1–12, **copied verbatim** (commands, tables and checks). In step 6, the prerequisite line becomes "Prerequisite: this repo's `main` contains `cloudbuild.yaml` and `cloudbuild-pr.yaml`."
  5. `## Operations`: spec §8 step 13, copied verbatim.
  6. `## Local development`: "Unchanged: `./start.sh` runs the backend on `:8000` (analyst app included, events kept in memory unless `INTRINSICA_EVENTS_SHEET_ID` is set) and the frontend on `:5173`. To preview production locally: `cd frontend && VITE_PUBLIC_MODE=1 npm run build`, then `cd backend && INTRINSICA_PUBLIC_MODE=1 INTRINSICA_STATIC_DIR=../frontend/dist python -m uvicorn main:app --port 8080`."

- [ ] **Step 3: Rewrite `backend/.env.example`:**

```bash
# Backend environment variables for LOCAL development. Copy to `.env` (loaded by
# python-dotenv). Production config is NOT set here: it lives in cloudbuild.yaml
# (see DEPLOY.md), and production uses no key file and no GOOGLE_SHEETS_ID.

# --- Local analyst app only (never set in production) ---
# The spreadsheet the local analyst app (/app, /database) reads and writes.
GOOGLE_SHEETS_ID=your-spreadsheet-id-here

# Credentials, resolved in this order:
#   1. GOOGLE_SHEETS_CREDS_JSON: the entire service-account JSON as one line;
#   2. the key file at GOOGLE_SHEETS_CREDS_PATH, if it exists (default below);
#   3. Application Default Credentials (on Cloud Run: the runtime service account).
GOOGLE_SHEETS_CREDS_PATH=./credentials/service_account.json
# GOOGLE_SHEETS_CREDS_JSON={"type":"service_account","project_id":"...", ...}

# --- Landing page (fake door) ---
# The dedicated Intrinsica events spreadsheet. Leave it UNSET locally: events then stay
# in memory and never pollute the demo sheet. Production sets it in cloudbuild.yaml.
INTRINSICA_EVENTS_SHEET_ID=

# --- Production switches (set by cloudbuild.yaml; leave unset locally) ---
# INTRINSICA_PUBLIC_MODE=1           # only the fake-door APIs exist
# INTRINSICA_STATIC_DIR=/app/static  # serve the built frontend (set in the Dockerfile)
# CANONICAL_HOST=intrinsica.io       # 301 www.<host> to the apex

# Comma-separated allowed frontend origins (defaults to the local Vite dev server).
CORS_ORIGINS=http://localhost:5173

# --- Optional tuning (defaults shown; production values are in cloudbuild.yaml) ---
# LANDING_SLOW_TTL=259200            # fundamentals cache, seconds (production: 604800 = 7 days)
# LANDING_FAST_TTL=3600              # price and R/R cache, seconds (production: 14400 = 4 hours)
# LANDING_CACHE_MAX_ENTRIES=256
# LANDING_RATE_LIMIT=20              # /api/landing/analyze requests per IP per window
# LANDING_RATE_WINDOW_SECONDS=60
# YF_MAX_WORKERS=8
# RECALC_CONCURRENCY=3
# SHEETS_MAX_RETRIES=6
```

- [ ] **Step 4: Rewrite `frontend/.env.example`:**

```bash
# Frontend build-time environment for LOCAL development. Copy to `.env`.
# Vite only exposes vars prefixed with VITE_. Production needs neither of these set:
# the Dockerfile sets VITE_PUBLIC_MODE=1, and a production build calls its own origin.

# Backend API base URL. Unset: dev uses http://localhost:8000, a production build uses
# its own origin (the Cloud Run service serves the page and /api together).
# VITE_API_BASE=http://localhost:8000

# 1 = build only the public fake door (/ and /checkout; the analyst pages are dropped).
# VITE_PUBLIC_MODE=1
```

- [ ] **Step 5: Commit.**

```bash
git add -A DEPLOY.md backend/.env.example frontend/.env.example frontend/vercel.json backend/railway.json render.yaml
git status --short   # confirm brand/ and backend/tests/__pycache__ are NOT staged
git commit -m "docs(deploy): single-provider DEPLOY.md guide; drop Vercel/Railway/Render configs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: Full gate, push, and PR

**Files:** none (verification and hand-off).

- [ ] **Step 1: Backend suite.** `cd backend && python -m pytest -q` → all pass (694 baseline plus the new tests), 0 failures.
- [ ] **Step 2: Frontend suite.** `cd frontend && npx vitest run && npx tsc -b && npx eslint . 2>&1 | tail -3` → all pass, tsc clean, eslint ≤ 6 problems.
- [ ] **Step 3: Production bundle checks.** Re-run Task 8 step 7's two greps → both `OK`. Then rebuild without the flag.
- [ ] **Step 4: Spec cross-check.** For each row of spec §2.6, confirm the value appears in `cloudbuild.yaml` (or in the Dockerfile for `INTRINSICA_STATIC_DIR`) exactly as written. For each item in spec §9, point to its commit.
- [ ] **Step 5: Push the branch.** `git push -u origin 02-deployment`
- [ ] **Step 6: Hand off.** Give the user:
  - the compare URL `https://github.com/intrinsica-io/intrinsica/compare/main...02-deployment` to open the PR (`gh` is not installed);
  - the note that **merging does not deploy anything yet**: the Cloud Build triggers do not exist until they follow `DEPLOY.md` steps 1–6, and step 7 is the first deploy;
  - the note that the first `intrinsica-pr` run is the first run of the backend suite on Python 3.12 (local is 3.14). If it fails on a version difference, fix it in a follow-up PR before step 7.
