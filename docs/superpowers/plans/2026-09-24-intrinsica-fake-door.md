# Intrinsica Fake-Door Landing Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a public smoke-test funnel that runs a real four-assessment analysis on visitor-chosen tickers, presents the plans, and measures how many visitors click "Proceed to payment" — a button that never charges and discloses honestly.

**Architecture:** A new light-themed landing route (`/`) and checkout route (`/checkout`) in the existing React app, rendered outside the current dark `Layout`. They are fed by two new FastAPI endpoints: `POST /api/landing/analyze` (runs the existing three-pipeline orchestrator for up to 3 tickers and maps the engine output into a presentation contract) and `POST /api/events` (fire-and-forget funnel analytics appended to a Sheets tab). One backend refactor is required: Quality currently discards its per-metric scores inside `_mean(...)`, and the breakdown table cannot be built without them.

**Tech Stack:** FastAPI + Pydantic + pytest (backend, existing); React 19 + Vite + TypeScript + Tailwind + react-router (frontend, existing); Vitest + React Testing Library + jsdom (frontend tests — **new, this plan installs them**); Google Sheets via the existing `services/sheets.py` helpers.

**Spec:** `docs/superpowers/specs/2026-09-23-intrinsica-fake-door-design.md`

## Assumptions locked by this plan

These were not stated in the spec. They are decisions, not guesses — raise them before execution if any is wrong.

1. **The landing page takes `/`.** The existing analyst Home page moves to `/app`. `/database`, `/progress/:jobId`, `/results/:jobId`, `/ticker/:jobId/:ticker` are unchanged.
2. **The landing and checkout routes render outside `Layout`.** `frontend/src/index.css` sets `color-scheme: dark` and a dark `body` background globally; the light landing page scopes its own theme on a wrapper element instead of changing those globals, so the existing app is untouched.
3. **The rename is scoped to user-visible copy and titles only.** `DEPLOY.md` deployment identifiers (`agentstock-backend` Cloud Run service, the Vercel hostname, `CORS_ORIGINS` examples) are **left alone** — renaming them breaks a live deployment. `.claude/memory/*` and `.claude/skills/validating-agent-stock/` are historical records and a skill id; they are **not** renamed.
4. **The demo runs the real engines**, via the existing `orchestrator.batch._run_one`, capped at 3 tickers per request, as spec §10 describes.
5. **Sample/marquee ticker is AAPL** (spec §12.4 is unresolved; AAPL is the current default and changing it is a one-line constant).

## Global Constraints

Every task's requirements implicitly include this section. Values are copied verbatim from spec §8 and §2.

- **The word "signal" is banned in user-facing copy** — use **assessment** (Reward/Risk uses "factors").
- **The label is "Reward/Risk", never "Risk/Reward"** — also "R/R", "R-R", and axis labels.
- **Never publish scoring thresholds, bands or curves.** Weights, point maxima, metric names and outcome bands are public; the mapping from a raw metric to a score is internal.
- **No internal identifiers in the UI** — every classifier code (`TECH_GROWTH`, `MEGA_CAP`, …) passes through a human label map.
- **Fair Value is an exact number.** No ranges anywhere on this page.
- **No invented moat sources** — no brand, network effects or switching costs.
- **No card, payment, address or name input may exist anywhere in the funnel's DOM.**
- **`free_plan_clicked` is a separate analytics event** and is never counted in paid-intent conversion.
- **Demo cap: 3 tickers per analysis run.**
- Analytics is exactly the event list in spec §9 — no scroll tracking, no click tracking, **no billing-toggle event**.

## Review Focus

Input classes the spec implies but which no task's happy path exercises. Each line names the input and the expected behavior; each has a test pinned to the task that owns the code.

1. **One engine fails while the others succeed** (`_run_one` gathers with `return_exceptions`, so `screener` or `risk_reward` can be `None`) — the row must render with blank cells for the missing assessment, never crash or show `NaN`. → Task 5.
2. **Fair value is absent** (engine declined: non-positive composite, pre-profit guard) — `% vs Price` must render as `—`, never divide by `None` or print `Infinity%`. → Task 5.
3. **A calibration excludes metrics from a category** (`FINANCIALS`, heavy-capex, acquisition-distorted) — the excluded metric shows struck-through at 0% and the surviving metrics' weights must still sum to the category weight. → Task 4.
4. **More than 3 tickers, an empty input, or an unresolvable ticker** — the request is capped/rejected with a readable message and never starts a 50-ticker engine run. → Task 6.
5. **The analytics endpoint is down, slow, or blocked by an ad blocker** — every funnel interaction must still work; `track()` must never throw, never block navigation, and never leave a button disabled. → Task 3.

---

## File Structure

**Backend — created**

| File | Responsibility |
|---|---|
| `backend/screener/models.py` (modify) | add `MetricDetail` — one scored Quality metric (label, raw, score, excluded) |
| `backend/screener/scoring.py` (modify) | add `section_metric_details()`; make `section_scores()` derive from it so they cannot drift |
| `backend/landing/__init__.py` | package marker |
| `backend/landing/labels.py` | classifier code → human label map (`humanize`) |
| `backend/landing/contract.py` | map the orchestrator's combined dict → the presentation payload the page consumes |
| `backend/routers/landing.py` | `POST /api/landing/analyze` — validate, cap at 3, run, map |
| `backend/routers/events.py` | `POST /api/events` — fire-and-forget funnel analytics |
| `backend/services/events_sheets.py` | queued/batched append of event rows to the `Events` tab |
| `backend/main.py` (modify) | register both routers; rename the FastAPI title |

**Frontend — created**

| File | Responsibility |
|---|---|
| `frontend/src/lib/analytics.ts` | `visitorId()` + `track()` — never throws, never blocks |
| `frontend/src/landing/types.ts` | TypeScript mirror of the backend contract |
| `frontend/src/landing/theme.css` | the light design tokens, scoped to `.intrinsica` |
| `frontend/src/landing/content/framework.ts` | the four assessments' categories, weights, metric lists, scores-high/low lines, notes, calibrations |
| `frontend/src/landing/content/plans.ts` | plan cards + the 17-row compare matrix |
| `frontend/src/landing/components/*.tsx` | `Nav`, `Hero`, `ResultGrid`, `Breakdown`, `Framework`, `Why`, `Workflow`, `Pricing`, `ComparePlans`, `SiteFooter` |
| `frontend/src/landing/LandingPage.tsx` | composes the sections, owns analyze state |
| `frontend/src/landing/CheckoutPage.tsx` | plan summary, Proceed to payment, post-click disclosure |
| `frontend/src/App.tsx` (modify) | landing at `/`, checkout at `/checkout`, existing Home at `/app` |

**Frontend — test infrastructure (new to this repo)**

`frontend/vitest.config.ts`, `frontend/src/test/setup.ts`, and a `test` script in `frontend/package.json`.

---

## Task 1: Rename to Intrinsica and drop the "AI-Powered" claim

The landing page's central claim is that the analysis is *not* an AI opinion. The existing shell currently says "AI-Powered Analysis" in the header, which contradicts it on the same domain.

**Files:**
- Modify: `frontend/index.html:7`
- Modify: `frontend/src/components/Layout.tsx:21-22`
- Modify: `backend/main.py:11`
- Modify: `DEPLOY.md:1,3` (prose only — **not** the service names or URLs)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing importable. Later tasks assume the document title is `Intrinsica`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_app_metadata.py`:

```python
from main import app


def test_app_is_named_intrinsica():
    assert app.title == "Intrinsica"
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd backend && python -m pytest tests/test_app_metadata.py -v`
Expected: FAIL — `assert 'Fair Value Batch Calculator' == 'Intrinsica'`

- [ ] **Step 3: Rename the API title**

In `backend/main.py`:

```python
app = FastAPI(title="Intrinsica")
```

- [ ] **Step 4: Run it and watch it pass**

Run: `cd backend && python -m pytest tests/test_app_metadata.py -v`
Expected: PASS

- [ ] **Step 5: Rename the user-visible frontend strings**

`frontend/index.html` line 7:

```html
    <title>Intrinsica</title>
```

`frontend/src/components/Layout.tsx`, replacing the two brand spans:

```tsx
            <span className="text-blue-400 font-bold text-lg tracking-wider">INTRINSICA</span>
            <span className="text-slate-600 text-xs">Fundamental Stock Analysis</span>
```

- [ ] **Step 6: Rename the prose in DEPLOY.md**

Change the heading `# Deploying Agent Stock` to `# Deploying Intrinsica` and the first sentence's `Agent Stock is two deployables` to `Intrinsica is two deployables`. **Leave every `agentstock-*` service name, hostname and `CORS_ORIGINS` example exactly as it is** — they name live infrastructure.

- [ ] **Step 7: Verify nothing user-facing still says the old name**

Run: `grep -rn "Agent Stock" frontend/src frontend/index.html backend --include="*.py" --include="*.tsx" --include="*.ts" --include="*.html"`
Expected: no output.

- [ ] **Step 8: Commit**

```bash
git add frontend/index.html frontend/src/components/Layout.tsx backend/main.py backend/tests/test_app_metadata.py DEPLOY.md
git commit -m "refactor: rename Agent Stock to Intrinsica in user-visible copy"
```

---

## Task 2: Analytics events endpoint and Sheets sink

**Files:**
- Create: `backend/services/events_sheets.py`
- Create: `backend/routers/events.py`
- Modify: `backend/models.py` (append `AnalyticsEvent`)
- Modify: `backend/main.py` (register the router)
- Test: `backend/tests/test_events_router.py`

**Interfaces:**
- Consumes: `services.sheets._get_service`, `_sheet_id`, `_execute`, `_run_sheets` (existing helpers).
- Produces:
  - `models.AnalyticsEvent(event: str, visitor_id: str, ts: str | None, props: dict)`
  - `services.events_sheets.record_event(ev: AnalyticsEvent) -> None` (async; queues)
  - `services.events_sheets.flush_events() -> int` (async; appends queued rows, returns the count written)
  - `POST /api/events` returning `{"recorded": True}`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_events_router.py`:

```python
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_event_is_recorded():
    with patch("routers.events.record_event", new=AsyncMock()) as rec:
        resp = client.post("/api/events", json={
            "event": "payment_button_clicked",
            "visitor_id": "v-123",
            "props": {"plan": "Pro", "billing": "annual"},
        })
    assert resp.status_code == 200
    assert resp.json() == {"recorded": True}
    assert rec.await_count == 1
    assert rec.await_args.args[0].event == "payment_button_clicked"


def test_event_gets_a_timestamp_when_the_client_omits_one():
    with patch("routers.events.record_event", new=AsyncMock()) as rec:
        client.post("/api/events", json={"event": "page_view", "visitor_id": "v-1"})
    assert rec.await_args.args[0].ts


def test_a_sink_failure_never_fails_the_request():
    with patch("routers.events.record_event",
               new=AsyncMock(side_effect=RuntimeError("sheets down"))):
        resp = client.post("/api/events", json={"event": "page_view", "visitor_id": "v-1"})
    assert resp.status_code == 200
    assert resp.json() == {"recorded": False}


def test_an_unnamed_event_is_rejected():
    resp = client.post("/api/events", json={"event": "  ", "visitor_id": "v-1"})
    assert resp.json() == {"recorded": False, "error": "event name is required"}
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd backend && python -m pytest tests/test_events_router.py -v`
Expected: FAIL — 404, because `/api/events` does not exist.

- [ ] **Step 3: Add the model**

Append to `backend/models.py`:

```python
class AnalyticsEvent(BaseModel):
    event: str
    visitor_id: str
    ts: str | None = None
    props: dict = {}
```

- [ ] **Step 4: Write the Sheets sink**

Create `backend/services/events_sheets.py`:

```python
from __future__ import annotations
import asyncio, json, os
from datetime import datetime, timezone

from models import AnalyticsEvent
from services.sheets import _get_service, _sheet_id, _execute, _run_sheets

_EVENTS_TAB = "Events"
_EVENTS_HEADERS = ["Timestamp", "Event", "VisitorId", "Props"]

# Sheets rate-limits writes, so events are queued and appended in batches rather
# than one API call per click. The queue is flushed when it reaches the batch size
# or when flush_events() is called explicitly.
_BATCH_SIZE = int(os.getenv("EVENTS_BATCH_SIZE", "10"))
_queue: list[list[str]] = []
_lock = asyncio.Lock()


def _to_row(ev: AnalyticsEvent) -> list[str]:
    return [ev.ts or "", ev.event, ev.visitor_id, json.dumps(ev.props or {})]


def _ensure_events_sheet(svc, sheet_id: str) -> None:
    meta = _execute(svc.spreadsheets().get(spreadsheetId=sheet_id))
    titles = {s["properties"]["title"] for s in meta.get("sheets", [])}
    if _EVENTS_TAB in titles:
        return
    _execute(svc.spreadsheets().batchUpdate(
        spreadsheetId=sheet_id,
        body={"requests": [{"addSheet": {"properties": {"title": _EVENTS_TAB}}}]},
    ))
    _execute(svc.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=f"{_EVENTS_TAB}!A1",
        valueInputOption="RAW", body={"values": [_EVENTS_HEADERS]},
    ))


def _append_sync(rows: list[list[str]]) -> None:
    svc = _get_service()
    sheet_id = _sheet_id()
    _ensure_events_sheet(svc, sheet_id)
    _execute(svc.spreadsheets().values().append(
        spreadsheetId=sheet_id, range=f"{_EVENTS_TAB}!A:D",
        valueInputOption="RAW", insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ))


async def record_event(ev: AnalyticsEvent) -> None:
    """Queue one event. Flushes automatically once a batch has accumulated."""
    async with _lock:
        _queue.append(_to_row(ev))
        ready = len(_queue) >= _BATCH_SIZE
    if ready:
        await flush_events()


async def flush_events() -> int:
    """Append everything queued. Returns the number of rows written."""
    async with _lock:
        rows, _queue[:] = list(_queue), []
    if not rows:
        return 0
    try:
        await _run_sheets(_append_sync, rows)
    except Exception:
        # Never lose the funnel to a Sheets outage — put them back for the next flush.
        async with _lock:
            _queue[:0] = rows
        raise
    return len(rows)
```

- [ ] **Step 5: Write the router**

Create `backend/routers/events.py`:

```python
from __future__ import annotations
from datetime import datetime, timezone
from fastapi import APIRouter

from models import AnalyticsEvent
from services.events_sheets import record_event

router = APIRouter()


@router.post("/events")
async def post_event(ev: AnalyticsEvent):
    """Fire-and-forget funnel analytics. This endpoint must never make the funnel
    fail: a bad payload or a dead sink returns 200 with recorded=False."""
    if not ev.event.strip():
        return {"recorded": False, "error": "event name is required"}
    ev.ts = ev.ts or datetime.now(timezone.utc).isoformat()
    try:
        await record_event(ev)
    except Exception as e:
        return {"recorded": False, "error": str(e)}
    return {"recorded": True}
```

- [ ] **Step 6: Register the router**

In `backend/main.py`, beside the existing imports and includes:

```python
from routers.events import router as events_router
...
app.include_router(events_router, prefix="/api")
```

- [ ] **Step 7: Run the tests and watch them pass**

Run: `cd backend && python -m pytest tests/test_events_router.py -v`
Expected: 4 passed.

- [ ] **Step 8: Commit**

```bash
git add backend/models.py backend/routers/events.py backend/services/events_sheets.py backend/main.py backend/tests/test_events_router.py
git commit -m "feat(analytics): POST /api/events with batched Sheets sink"
```

---

## Task 3: Analytics client — `track()` that can never break the funnel

This task also installs the frontend test runner, which this repo does not have. That scaffolding belongs here because this is the first frontend unit under test.

**Files:**
- Modify: `frontend/package.json` (devDependencies + `test` script)
- Create: `frontend/vitest.config.ts`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/lib/analytics.ts`
- Test: `frontend/src/lib/analytics.test.ts`

**Interfaces:**
- Consumes: `API_BASE` from `frontend/src/lib/api.ts`.
- Produces:
  - `visitorId(): string` — stable per browser, stored in `localStorage` under `intrinsica_vid`
  - `track(event: string, props?: Record<string, unknown>): void` — fire-and-forget, returns synchronously, never throws
  - `EVENTS` — the frozen event-name constants every later task uses

- [ ] **Step 1: Install the test runner**

Run: `cd frontend && npm install -D vitest@^3 @testing-library/react@^16 @testing-library/jest-dom@^6 @testing-library/user-event@^14 jsdom@^25`

Then add to the `scripts` block of `frontend/package.json`:

```json
    "test": "vitest run",
    "test:watch": "vitest"
```

- [ ] **Step 2: Configure Vitest**

Create `frontend/vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
```

Create `frontend/src/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

beforeEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

afterEach(() => {
  cleanup()
})
```

- [ ] **Step 3: Write the failing tests**

Create `frontend/src/lib/analytics.test.ts`:

```ts
import { describe, it, expect, vi } from 'vitest'
import { track, visitorId, EVENTS } from './analytics'

describe('visitorId', () => {
  it('is stable across calls', () => {
    expect(visitorId()).toBe(visitorId())
  })

  it('survives a localStorage that throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(visitorId()).toMatch(/^v-/)
  })
})

describe('track', () => {
  it('posts the event to /api/events', () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', fetchMock)

    track(EVENTS.paymentButtonClicked, { plan: 'Pro', billing: 'annual' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toMatch(/\/api\/events$/)
    const body = JSON.parse(init.body)
    expect(body.event).toBe('payment_button_clicked')
    expect(body.props).toEqual({ plan: 'Pro', billing: 'annual' })
    expect(body.visitor_id).toBe(visitorId())
  })

  it('does not throw when the network rejects', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    expect(() => track(EVENTS.pageView)).not.toThrow()
    await Promise.resolve()
  })

  it('does not throw when fetch itself is unavailable', () => {
    vi.stubGlobal('fetch', undefined)
    expect(() => track(EVENTS.pageView)).not.toThrow()
  })

  it('returns synchronously so a click handler is never awaited', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})))
    expect(track(EVENTS.checkoutStarted, { plan: 'Pro' })).toBeUndefined()
  })
})
```

- [ ] **Step 4: Run them and watch them fail**

Run: `cd frontend && npm test -- src/lib/analytics.test.ts`
Expected: FAIL — cannot resolve `./analytics`.

- [ ] **Step 5: Write the client**

Create `frontend/src/lib/analytics.ts`:

```ts
import { API_BASE } from './api'

/** The complete funnel event list (spec section 9). There is deliberately no
 *  scroll, hover, or billing-toggle event: the chosen billing period rides on
 *  plan_selected. */
export const EVENTS = Object.freeze({
  pageView: 'page_view',
  analysisStarted: 'analysis_started',
  analysisCompleted: 'analysis_completed',
  breakdownOpened: 'breakdown_opened',
  methodologyViewed: 'methodology_viewed',
  pricingViewed: 'pricing_viewed',
  planSelected: 'plan_selected',
  checkoutStarted: 'checkout_started',
  paymentButtonClicked: 'payment_button_clicked',
  emailSubmitted: 'email_submitted',
  /** Kept apart from the paid funnel on purpose — never counted in paid-intent
   *  conversion. */
  freePlanClicked: 'free_plan_clicked',
})

const KEY = 'intrinsica_vid'
let cached: string | null = null

function newId(): string {
  return `v-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

/** A stable per-browser id. Private mode, cleared storage and blocked storage all
 *  degrade to a per-session id rather than throwing. */
export function visitorId(): string {
  if (cached) return cached
  try {
    const stored = localStorage.getItem(KEY)
    if (stored) {
      cached = stored
      return cached
    }
    cached = newId()
    localStorage.setItem(KEY, cached)
    return cached
  } catch {
    cached = cached ?? newId()
    return cached
  }
}

/** Fire-and-forget. Returns immediately and swallows every failure: a dead
 *  endpoint, an ad blocker or an offline browser must never break the funnel. */
export function track(event: string, props: Record<string, unknown> = {}): void {
  try {
    if (typeof fetch !== 'function') return
    void fetch(`${API_BASE}/api/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event,
        visitor_id: visitorId(),
        ts: new Date().toISOString(),
        props,
      }),
      keepalive: true,
    }).catch(() => {})
  } catch {
    /* analytics is never load-bearing */
  }
}
```

- [ ] **Step 6: Run the tests and watch them pass**

Run: `cd frontend && npm test -- src/lib/analytics.test.ts`
Expected: 6 passed.

- [ ] **Step 7: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts frontend/src/test/setup.ts frontend/src/lib/analytics.ts frontend/src/lib/analytics.test.ts
git commit -m "feat(analytics): add fire-and-forget track() and the Vitest harness"
```

---

## Task 4: Expose Quality's per-metric scores

`section_scores()` builds each section with `_mean([score_high(...), ...])` and throws the individual metric scores away, so the `Factor | Data | Score | Weight` table cannot be built. This task adds a detail-producing function and makes `section_scores()` derive from it, so the two can never disagree.

**Files:**
- Modify: `backend/screener/models.py` (add `MetricDetail`)
- Modify: `backend/screener/scoring.py:269` (`section_scores` rebuilt on `section_metric_details`)
- Test: `backend/tests/test_screener_metric_details.py`

**Interfaces:**
- Consumes: the existing `ScreenerMetrics`, `score_high`, `score_low`, `_mean`, and the existing exclusion predicates `_heavy_capex_distortion`, `_earnings_distorted`, `_acq_margin_distorted`, `_acquisition_distorted`.
- Produces:
  - `screener.models.MetricDetail(label: str, raw: float | None, score: float | None, excluded: bool, excluded_by: str | None)`
  - `screener.scoring.section_metric_details(m: ScreenerMetrics, profile: str) -> dict[str, list[MetricDetail]]`, keyed `"I" | "II" | "III" | "IV"`
  - `section_scores()` keeps its existing signature and return type exactly.

- [ ] **Step 1: Read the current implementation before touching it**

Run: `cd backend && sed -n '269,340p' screener/scoring.py`

Write down the exact band-constant name and argument order used for every metric. The rewrite in Step 4 must reuse them verbatim — **do not rename or retune a band**; this task changes only where the per-metric score lands.

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_screener_metric_details.py`:

```python
from screener.models import ScreenerMetrics
from screener.scoring import section_metric_details, section_scores, _mean


def _tech_metrics() -> ScreenerMetrics:
    return ScreenerMetrics(
        revenue_cagr_3y=0.25, eps_cagr_3y=0.30, fcf_cagr_3y=0.22, fcf_margin=0.28,
        op_margin=0.31, op_margin_trajectory=0.02, gross_margin=0.46,
        roic_ttm=0.55, roic_5y_avg=0.48, wacc=0.09, roic_wacc_spread=0.46, rote=0.60,
        net_debt_ebitda=0.4, net_debt_fcf=0.5, ocf_capex=6.0,
        shares_cagr_3y=-0.03, sbc_pct_rev=0.04, earnings_quality=1.05,
        insider_ownership=0.01, shareholder_yield=0.04,
    )


def test_every_section_reports_its_metrics():
    details = section_metric_details(_tech_metrics(), "TECH_GROWTH")
    assert [len(details[k]) for k in ("I", "II", "III", "IV")] == [7, 4, 3, 5]
    assert all(d.label for d in details["I"])


def test_the_section_score_is_the_mean_of_its_metric_scores():
    m, profile = _tech_metrics(), "TECH_GROWTH"
    details = section_metric_details(m, profile)
    sections = section_scores(m, profile)
    for key in ("I", "II", "III", "IV"):
        assert sections[key] == _mean([d.score for d in details[key]])


def test_an_excluded_metric_is_flagged_and_scoreless():
    details = section_metric_details(_tech_metrics(), "FINANCIALS")
    fcf_metrics = [d for d in details["I"] if "FCF" in d.label]
    assert fcf_metrics, "expected FCF metrics in section I"
    assert all(d.excluded and d.score is None for d in fcf_metrics)
    assert all(d.excluded_by for d in fcf_metrics)


def test_an_excluded_metric_does_not_drag_the_section_score_down():
    m, profile = _tech_metrics(), "FINANCIALS"
    details = section_metric_details(m, profile)
    scored = [d.score for d in details["I"] if not d.excluded]
    assert section_scores(m, profile)["I"] == _mean(scored)


def test_the_raw_figure_travels_with_the_score():
    details = section_metric_details(_tech_metrics(), "TECH_GROWTH")
    roic = next(d for d in details["II"] if d.label.startswith("ROIC (trailing)"))
    assert roic.raw == 0.55
```

- [ ] **Step 3: Run them and watch them fail**

Run: `cd backend && python -m pytest tests/test_screener_metric_details.py -v`
Expected: FAIL — `ImportError: cannot import name 'section_metric_details'`.

- [ ] **Step 4: Add the model**

Append to `backend/screener/models.py`:

```python
class MetricDetail(BaseModel):
    """One scored metric inside a Quality section. `score` is None exactly when the
    metric was excluded or its input was missing — the same condition `_mean` skips,
    which is what keeps the section score and this list in agreement."""
    label: str
    raw: float | None = None
    score: float | None = None
    excluded: bool = False
    excluded_by: str | None = None
```

- [ ] **Step 5: Rebuild `section_scores` on top of the details**

In `backend/screener/scoring.py`, add `MetricDetail` to the `from screener.models import ...` line, then replace the `section_scores` body with the following. Band constants and argument order come from what you recorded in Step 1.

```python
def _detail(label, raw, score, excluded_by=None) -> MetricDetail:
    """A metric excluded by a calibration carries no score, so `_mean` skips it and the
    surviving metrics in its section re-weight automatically."""
    if excluded_by:
        return MetricDetail(label=label, raw=raw, score=None,
                            excluded=True, excluded_by=excluded_by)
    return MetricDetail(label=label, raw=raw, score=score)


def section_metric_details(m: ScreenerMetrics,
                           profile: str) -> dict[str, list[MetricDetail]]:
    """Per-metric label, raw figure and 0-10 score for each Quality section.
    `section_scores` is derived from this, so the headline and the breakdown table
    cannot drift apart."""
    is_fin = profile == "FINANCIALS"
    heavy_capex = _heavy_capex_distortion(m)
    exclude_fcf = ("Financials basis" if is_fin else
                   "Heavy-capex FCF exclusion" if heavy_capex else None)
    exclude_eps = "Forward-EPS swap" if _earnings_distorted(m) else None
    exclude_acq = "Dominant fresh-acquisition" if _acq_margin_distorted(m) else None

    section_i = [
        _detail("Revenue growth (3-yr)", m.revenue_cagr_3y,
                score_high(m.revenue_cagr_3y, GROWTH_BANDS, 0)),
        _detail("EPS growth (3-yr)", m.eps_cagr_3y,
                score_high(m.eps_cagr_3y, GROWTH_BANDS, 0), exclude_eps),
        _detail("FCF growth (3-yr)", m.fcf_cagr_3y,
                score_high(m.fcf_cagr_3y, FCF_CAGR_BANDS, 1), exclude_fcf),
        _detail("FCF margin", m.fcf_margin,
                score_high(m.fcf_margin, FCF_MARGIN_BANDS, 0), exclude_fcf),
        _detail("Operating margin", m.op_margin,
                score_high(m.op_margin, MARGIN_LEVEL_BANDS, 0), exclude_acq),
        _detail("Operating-margin trajectory", m.op_margin_trajectory,
                score_high(m.op_margin_trajectory, TRAJECTORY_BANDS, 1), exclude_acq),
        _detail("Gross margin", m.gross_margin,
                score_high(m.gross_margin, GROSS_MARGIN_BANDS, 2)),
    ]

    # Acquisition-distorted names score ROIC and its WACC spread on tangible invested
    # capital, exactly as the current implementation does.
    if _acquisition_distorted(m):
        roic_ttm_val = m.roic_ex_goodwill
        roic_5y_val = (m.roic_5y_ex_goodwill if m.roic_5y_ex_goodwill is not None
                       else m.roic_5y_avg)
        spread_val = ((m.roic_ex_goodwill - m.wacc) if m.wacc is not None
                      else m.roic_wacc_spread)
    else:
        roic_ttm_val, roic_5y_val = m.roic_ttm, m.roic_5y_avg
        spread_val = m.roic_wacc_spread

    section_ii = [
        _detail("ROIC (trailing)", roic_ttm_val,
                score_high(roic_ttm_val, ROIC_BANDS, 0)),
        _detail("ROIC (5-yr average)", roic_5y_val,
                score_high(roic_5y_val, ROIC_BANDS, 0)),
        _detail("Economic spread (ROIC - WACC)", spread_val,
                score_high(spread_val, SPREAD_BANDS, 0)),
        _detail("Return on tangible equity", m.rote,
                score_high(m.rote, ROTE_BANDS, 0)),
    ]

    lender = "Financials basis" if is_fin else None
    section_iii = [
        _detail("Net debt / EBITDA", m.net_debt_ebitda,
                score_low(m.net_debt_ebitda, NET_DEBT_EBITDA_BANDS, 0), lender),
        _detail("Net debt / FCF", m.net_debt_fcf,
                score_low(m.net_debt_fcf, NET_DEBT_FCF_BANDS, 0), exclude_fcf or lender),
        _detail("Operating cash flow / capex", m.ocf_capex,
                score_high(m.ocf_capex, OCF_CAPEX_BANDS, 0), exclude_fcf or lender),
    ]

    section_iv = [
        _detail("Share-count trend (3-yr)", m.shares_cagr_3y,
                score_low(m.shares_cagr_3y, SHARES_BANDS, 0)),
        _detail("Stock comp % of revenue", m.sbc_pct_rev,
                score_low(m.sbc_pct_rev, SBC_BANDS, 0)),
        _detail("Earnings quality (FCF / net income)", m.earnings_quality,
                score_high(m.earnings_quality, EARNINGS_QUALITY_BANDS, 0), exclude_fcf),
        _detail("Insider ownership", m.insider_ownership,
                score_high(m.insider_ownership, INSIDER_BANDS, 0)),
        _detail("Shareholder yield", m.shareholder_yield,
                score_high(m.shareholder_yield, SHAREHOLDER_YIELD_BANDS, 0)),
    ]

    return {"I": section_i, "II": section_ii, "III": section_iii, "IV": section_iv}


def section_scores(m: ScreenerMetrics, profile: str) -> dict[str, float | None]:
    details = section_metric_details(m, profile)
    return {k: _mean([d.score for d in v]) for k, v in details.items()}
```

- [ ] **Step 6: Run the new tests and watch them pass**

Run: `cd backend && python -m pytest tests/test_screener_metric_details.py -v`
Expected: 5 passed.

- [ ] **Step 7: Prove the refactor moved no score**

Run: `cd backend && python -m pytest tests/ -v`
Expected: the full suite passes exactly as before. A failure here means the rewrite changed a band or an argument order — fix the rewrite, never the assertion.

- [ ] **Step 8: Commit**

```bash
git add backend/screener/models.py backend/screener/scoring.py backend/tests/test_screener_metric_details.py
git commit -m "feat(screener): expose per-metric Quality detail behind section_scores"
```

---

## Task 5: The presentation contract

Turns the orchestrator's combined dict into the exact shape the page renders. This is where spec §7 lives: per-metric weights are derived here (category weight ÷ active metric count), classifier codes are humanized here, and a missing engine degrades to `null` here rather than in a component.

**Files:**
- Create: `backend/landing/__init__.py` (empty)
- Create: `backend/landing/labels.py`
- Create: `backend/landing/contract.py`
- Test: `backend/tests/test_landing_contract.py`

**Interfaces:**
- Consumes: the dict returned by `orchestrator.batch._run_one(ticker)["result"]` — a `TickerResult` dump with `screener` and `risk_reward` sub-dicts attached; `risk_reward.config.CONFIG.weights`.
- Produces:
  - `landing.labels.humanize(code: str | None) -> str | None` — `TECH_GROWTH` → `Tech / Growth`, unknown codes Title-Cased, `None` → `None`
  - `landing.labels.METHOD_LABELS`, `MOAT_FACTOR_LABELS`, `RR_FACTOR_LABELS` — `dict[str, str]`
  - `landing.contract.build_ticker_payload(result: dict) -> dict` with the keys
    `ticker, company_name, price, quality, moat, fair_value, reward_risk, calibrations, errors`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_landing_contract.py`:

```python
import pytest
from landing.contract import build_ticker_payload
from landing.labels import humanize


def _result(**over) -> dict:
    base = {
        "ticker": "AAPL", "company_name": "Apple Inc.", "current_price": 232.0,
        "stock_type": "MEGA_CAP", "fair_value": 211.0, "price_vs_fair_value_pct": -9.05,
        "fair_value_breakdown": {
            "dcf": {"fair_value": 205.0, "weight": 0.55},
            "ev_ebitda": {"fair_value": 220.0, "weight": 0.35},
            "pe": {"fair_value": 208.0, "weight": 0.10},
        },
        "status": "completed", "errors": [],
        "screener": {
            "quality_score": 9.1, "sector_profile": "TECH_GROWTH",
            "section_scores": {"I": 8.0, "II": 10.0, "III": 9.0, "IV": 9.0},
            "score_breakdown": {"section_weights": {"I": 0.35, "II": 0.30,
                                                    "III": 0.15, "IV": 0.20}},
            "metric_details": {
                "I": [{"label": "Revenue growth (3-yr)", "raw": 0.08, "score": 6.0,
                       "excluded": False, "excluded_by": None},
                      {"label": "Gross margin", "raw": 0.46, "score": 10.0,
                       "excluded": False, "excluded_by": None}],
                "II": [], "III": [], "IV": [],
            },
            "moat_score": 90.0,
            "moat_breakdown": {"pillars": {"A1": 18.0, "A2": 17.0, "B1": 25.0},
                               "maxima": {"A1": 20, "A2": 20, "B1": 25},
                               "gated": False, "excluded": []},
        },
        "risk_reward": {
            "ratio": 0.9, "tier": "Balanced", "reward_score": 2.8, "risk_score": 3.1,
            "metric_scores": {
                "discount": {"raw": 0.05, "score": 2.0, "weight": 0.24, "dropped": False},
                "volatility": {"raw": 0.3, "score": 3.0, "weight": 0.22, "dropped": False},
            },
            "status": "completed",
        },
    }
    base.update(over)
    return base


def test_headline_values_are_carried_through():
    p = build_ticker_payload(_result())
    assert p["ticker"] == "AAPL"
    assert p["quality"]["score"] == 9.1
    assert p["moat"]["score"] == 90.0
    assert p["fair_value"]["value"] == 211.0
    assert p["reward_risk"]["ratio"] == 0.9


def test_no_internal_classifier_code_survives():
    p = build_ticker_payload(_result())
    assert p["quality"]["profile_label"] == "Tech / Growth"
    assert p["fair_value"]["type_label"] == "Mega Cap"
    assert "TECH_GROWTH" not in repr(p)
    assert "MEGA_CAP" not in repr(p)


def test_metric_weights_split_the_category_weight_evenly():
    p = build_ticker_payload(_result())
    cat = next(c for c in p["quality"]["categories"] if c["key"] == "I")
    assert cat["weight_pct"] == 35.0
    assert [m["weight_pct"] for m in cat["metrics"]] == [17.5, 17.5]


def test_an_excluded_metric_is_zero_weighted_and_the_rest_reweight():
    r = _result()
    r["screener"]["metric_details"]["I"].append(
        {"label": "FCF margin", "raw": None, "score": None,
         "excluded": True, "excluded_by": "Financials basis"})
    p = build_ticker_payload(r)
    cat = next(c for c in p["quality"]["categories"] if c["key"] == "I")
    excluded = [m for m in cat["metrics"] if m["excluded"]]
    active = [m for m in cat["metrics"] if not m["excluded"]]
    assert [m["weight_pct"] for m in excluded] == [0.0]
    assert sum(m["weight_pct"] for m in active) == pytest.approx(35.0)


def test_the_quality_headline_equals_what_its_categories_roll_up_to():
    """The grid shows the headline and the breakdown shows the categories; if these two
    could disagree, the page would be lying about its own arithmetic."""
    p = build_ticker_payload(_result())
    rolled = sum(c["score"] * c["weight_pct"] / 100 for c in p["quality"]["categories"])
    assert rolled == pytest.approx(p["quality"]["score"], abs=0.05)


def test_fair_value_methods_carry_value_weight_and_contribution():
    p = build_ticker_payload(_result())
    dcf = next(m for m in p["fair_value"]["methods"] if m["label"] == "Discounted cash flow")
    assert dcf["weight_pct"] == 55.0
    assert dcf["contribution"] == pytest.approx(205.0 * 0.55)
    assert sum(m["contribution"] for m in p["fair_value"]["methods"]) == pytest.approx(211.0, abs=0.5)


def test_moat_factor_weight_is_its_share_of_the_available_points():
    p = build_ticker_payload(_result())
    a1 = next(f for f in p["moat"]["factors"] if f["label"].startswith("ROIC level"))
    assert (a1["points"], a1["max_points"]) == (18.0, 20)
    assert a1["weight_pct"] == pytest.approx(20 / 65 * 100)


def test_reward_and_risk_factors_are_split_by_axis():
    p = build_ticker_payload(_result())
    assert [f["label"] for f in p["reward_risk"]["reward"]] == ["Discount to 52-week high"]
    assert [f["label"] for f in p["reward_risk"]["risk"]] == ["Volatility"]
    assert p["reward_risk"]["reward"][0]["weight_pct"] == 24.0


# --- Review Focus 1: one engine fails, the others do not ---
def test_a_missing_engine_becomes_null_not_a_crash():
    p = build_ticker_payload(_result(screener=None, risk_reward=None))
    assert p["quality"] is None and p["moat"] is None and p["reward_risk"] is None
    assert p["fair_value"]["value"] == 211.0


# --- Review Focus 2: no fair value ---
def test_a_declined_fair_value_yields_no_value_and_no_gap():
    p = build_ticker_payload(_result(fair_value=None, price_vs_fair_value_pct=None,
                                     fair_value_breakdown={}))
    assert p["fair_value"] is None
    assert p["price"] == 232.0


def test_a_gap_is_never_computed_without_a_price():
    p = build_ticker_payload(_result(current_price=None, price_vs_fair_value_pct=None))
    assert p["fair_value"]["gap_pct"] is None


def test_humanize_falls_back_to_title_case_for_an_unmapped_code():
    assert humanize("SOME_NEW_TYPE") == "Some New Type"
    assert humanize(None) is None
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd backend && python -m pytest tests/test_landing_contract.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'landing'`.

- [ ] **Step 3: Write the label maps**

Create `backend/landing/__init__.py` (empty file) and `backend/landing/labels.py`:

```python
from __future__ import annotations

# Spec section 8 rule 5: no internal identifier ever reaches the UI. Anything not
# mapped here still gets Title-Cased rather than leaking an ALL_CAPS code.
PROFILE_LABELS = {
    "TECH_GROWTH": "Tech / Growth",
    "BALANCED": "Balanced",
    "DEFENSIVE_INCOME": "Defensive / Income",
    "INDUSTRIAL_CYCLICAL": "Industrial / Cyclical",
    "FINANCIALS": "Financials",
    "REIT": "REIT",
}

STOCK_TYPE_LABELS = {
    "MEGA_CAP": "Mega Cap", "LARGE_CAP": "Large Cap", "MID_CAP": "Mid Cap",
    "GROWTH": "Growth", "EARLY_GROWTH": "Early Growth", "DIVIDEND": "Dividend Payer",
    "CYCLICAL": "Cyclical", "FINANCIAL": "Lender / Insurer",
    "ASSET_HEAVY": "Asset-Heavy",
}

METHOD_LABELS = {
    "dcf": "Discounted cash flow", "fcfe": "Free cash flow to equity",
    "ev_ebitda": "EV / EBITDA", "pe": "P / E", "ev_sales": "EV / Sales",
    "ddm": "Dividend discount", "pb": "Price / book", "rim": "Residual income",
    "nav": "Net asset value", "sotp": "Sum of the parts",
}

# Moat pillar codes. Concept only — the point bands stay internal (spec section 8 rule 3).
MOAT_FACTOR_LABELS = {
    "A1": "ROIC level", "A2": "Economic spread (ROIC - WACC)",
    "B1": "Persistence of economic profit", "B2": "Consistency of returns",
    "B3": "Margin durability", "C1": "Free-cash-flow conversion",
}

RR_FACTOR_LABELS = {
    "valuation": "Valuation", "growth": "Growth", "profitability": "Profitability",
    "analyst_upside": "Analyst upside", "discount": "Discount to 52-week high",
    "rsi": "RSI (14-day)",
    "leverage": "Leverage", "burn": "Burn / margin", "liquidity": "Liquidity",
    "volatility": "Volatility", "trend": "Trend vs 200-day", "beta": "Beta",
}

CATEGORY_LABELS = {
    "I": "Growth & Margins", "II": "Returns on Capital",
    "III": "Balance-Sheet Strength", "IV": "Shareholder Alignment",
}

_ALL = {**PROFILE_LABELS, **STOCK_TYPE_LABELS}


def humanize(code: str | None) -> str | None:
    """Map an internal classifier code to its display label, Title-Casing anything
    unmapped so a new engine constant degrades into readable text rather than shouting
    TECH_GROWTH at a visitor."""
    if not code:
        return None
    if code in _ALL:
        return _ALL[code]
    return " ".join(w.capitalize() for w in str(code).replace("-", "_").split("_") if w)
```

- [ ] **Step 4: Write the contract builder**

Create `backend/landing/contract.py`:

```python
from __future__ import annotations

from risk_reward.config import CONFIG, REWARD_SLOTS, RISK_SLOTS
from landing.labels import (
    CATEGORY_LABELS, METHOD_LABELS, MOAT_FACTOR_LABELS, RR_FACTOR_LABELS, humanize,
)

# Fallback category weights when the engine did not report renormalized ones.
_DEFAULT_CATEGORY_WEIGHTS = {"I": 0.35, "II": 0.30, "III": 0.15, "IV": 0.20}


def _round(v, n=2):
    return None if v is None else round(v, n)


def _quality(sc: dict | None) -> dict | None:
    if not sc or sc.get("quality_score") is None:
        return None
    weights = (sc.get("score_breakdown") or {}).get("section_weights") \
        or _DEFAULT_CATEGORY_WEIGHTS
    details = sc.get("metric_details") or {}
    categories = []
    for key in ("I", "II", "III", "IV"):
        weight_pct = round(float(weights.get(key, 0.0)) * 100, 2)
        metrics = details.get(key) or []
        # Metrics are averaged inside a category (`_mean`), so each scored metric
        # carries an equal share of the category weight and an excluded one carries
        # none — which is what re-weights the survivors.
        active = [m for m in metrics if not m.get("excluded") and m.get("score") is not None]
        share = round(weight_pct / len(active), 2) if active else 0.0
        categories.append({
            "key": key,
            "name": CATEGORY_LABELS[key],
            "weight_pct": weight_pct,
            "score": _round((sc.get("section_scores") or {}).get(key)),
            "metrics": [{
                "label": m.get("label"),
                "raw": m.get("raw"),
                "score": _round(m.get("score")),
                "weight_pct": 0.0 if (m.get("excluded") or m.get("score") is None) else share,
                "excluded": bool(m.get("excluded")),
                "excluded_by": m.get("excluded_by"),
            } for m in metrics],
        })
    return {
        "score": _round(sc.get("quality_score"), 1),
        "profile_label": humanize(sc.get("sector_profile")),
        "categories": categories,
    }


def _moat(sc: dict | None) -> dict | None:
    if not sc or sc.get("moat_score") is None:
        return None
    bd = sc.get("moat_breakdown") or {}
    pillars, maxima = bd.get("pillars") or {}, bd.get("maxima") or {}
    available = sum(maxima.values()) or 100
    factors = [{
        "label": MOAT_FACTOR_LABELS.get(code, humanize(code)),
        "points": _round(points),
        "max_points": maxima.get(code),
        "weight_pct": round(maxima.get(code, 0) / available * 100, 2),
    } for code, points in pillars.items()]
    return {
        "score": _round(sc.get("moat_score"), 1),
        "gated": bool(bd.get("gated")),
        "excluded": bd.get("excluded") or [],
        "factors": factors,
    }


def _fair_value(res: dict) -> dict | None:
    if res.get("fair_value") is None:
        return None
    bd = res.get("fair_value_breakdown") or {}
    methods = [{
        "label": METHOD_LABELS.get(mid, humanize(mid)),
        "value": _round(leg.get("fair_value")),
        "weight_pct": round(float(leg.get("weight", 0.0)) * 100, 2),
        "contribution": _round(float(leg.get("weight", 0.0)) * float(leg.get("fair_value") or 0.0)),
    } for mid, leg in bd.items()]
    return {
        # One exact blended number — never a range (spec section 8 rule 7).
        "value": _round(res.get("fair_value")),
        "gap_pct": _round(res.get("price_vs_fair_value_pct")),
        "type_label": humanize(res.get("stock_type")),
        "methods": methods,
    }


def _reward_risk(rr: dict | None) -> dict | None:
    if not rr or rr.get("ratio") is None:
        return None
    scores = rr.get("metric_scores") or {}
    def factors(slots):
        out = []
        for slot in slots:
            ms = scores.get(slot)
            if not ms:
                continue
            out.append({
                "label": RR_FACTOR_LABELS.get(slot, humanize(slot)),
                "raw": ms.get("raw"),
                "score": _round(ms.get("score")),
                "weight_pct": round(float(ms.get("weight", CONFIG.weights.get(slot, 0.0))) * 100, 2),
                "dropped": bool(ms.get("dropped")),
            })
        return out
    return {
        "ratio": _round(rr.get("ratio"), 2),
        "tier": rr.get("tier"),
        "reward_score": _round(rr.get("reward_score")),
        "risk_score": _round(rr.get("risk_score")),
        "reward": factors(REWARD_SLOTS),
        "risk": factors(RISK_SLOTS),
    }


def _calibrations(res: dict, sc: dict | None) -> list[str]:
    """Only the calibrations that actually fired, by name."""
    fired: list[str] = []
    bd = (sc or {}).get("score_breakdown") or {}
    if bd.get("sector_adjustment"):
        fired.append("Financials basis")
    if bd.get("capex_adjustment"):
        fired.append("Heavy-capex FCF exclusion")
    for cat in (sc or {}).get("metric_details", {}).values():
        for m in cat or []:
            name = m.get("excluded_by")
            if name and name not in fired:
                fired.append(name)
    if ((sc or {}).get("moat_breakdown") or {}).get("gated"):
        fired.append("Economic-profit gate")
    return fired


def build_ticker_payload(result: dict) -> dict:
    """Map one orchestrator result into the shape the landing page renders. Every
    headline the grid shows is present here alongside the factors it was derived
    from, so the grid and the breakdown cannot disagree."""
    sc = result.get("screener")
    rr = result.get("risk_reward")
    return {
        "ticker": result.get("ticker"),
        "company_name": result.get("company_name"),
        "price": _round(result.get("current_price")),
        "quality": _quality(sc),
        "moat": _moat(sc),
        "fair_value": _fair_value(result),
        "reward_risk": _reward_risk(rr),
        "calibrations": _calibrations(result, sc),
        "errors": result.get("errors") or [],
    }
```

- [ ] **Step 5: Carry the metric details through the screener result**

`build_ticker_payload` reads `screener.metric_details`, which the engine does not yet emit. Add the field to `backend/screener/models.py` on `ScreenerResult`:

```python
    metric_details: dict = {}
```

and populate it in `backend/screener/engine.py`, in **both** `ScreenerResult(...)` constructions (the failed branch at line ~26 and the completed one at line ~34), beside the existing `section_scores=sections`:

```python
        metric_details={k: [d.model_dump() for d in v]
                        for k, v in section_metric_details(metrics, profile).items()},
```

Import it at the top of `engine.py`: `from screener.scoring import section_metric_details`.

- [ ] **Step 6: Run the tests and watch them pass**

Run: `cd backend && python -m pytest tests/test_landing_contract.py -v`
Expected: 12 passed.

- [ ] **Step 7: Confirm the engine still round-trips**

Run: `cd backend && python -m pytest tests/test_screener_engine.py tests/test_batch_screener.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/landing backend/screener/models.py backend/screener/engine.py backend/tests/test_landing_contract.py
git commit -m "feat(landing): presentation contract mapping engines to the page payload"
```

---

## Task 6: `POST /api/landing/analyze`

**Files:**
- Create: `backend/routers/landing.py`
- Modify: `backend/main.py` (register the router)
- Test: `backend/tests/test_landing_router.py`

**Interfaces:**
- Consumes: `orchestrator.batch._run_one`, `services.yahoo.validate_ticker`, `landing.contract.build_ticker_payload`.
- Produces: `POST /api/landing/analyze` taking `{"tickers": ["AAPL", "AMD"]}` and returning
  `{"results": [<payload>, ...], "invalid": [...], "error": str | None}`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_landing_router.py`:

```python
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

MAX = 3


def _ok(ticker: str) -> dict:
    return {"result": {"ticker": ticker, "company_name": f"{ticker} Inc.",
                       "current_price": 100.0, "stock_type": "MEGA_CAP",
                       "fair_value": 110.0, "price_vs_fair_value_pct": 10.0,
                       "fair_value_breakdown": {"dcf": {"fair_value": 110.0, "weight": 1.0}},
                       "status": "completed", "errors": [],
                       "screener": None, "risk_reward": None}}


def test_a_single_ticker_comes_back_mapped():
    with patch("routers.landing.validate_ticker", new=AsyncMock(return_value=True)), \
         patch("routers.landing._run_one", new=AsyncMock(side_effect=lambda t: _ok(t))):
        resp = client.post("/api/landing/analyze", json={"tickers": ["aapl"]})
    body = resp.json()
    assert [r["ticker"] for r in body["results"]] == ["AAPL"]
    assert body["results"][0]["fair_value"]["value"] == 110.0


# --- Review Focus 4: too many tickers, empty input, unresolvable ticker ---
def test_more_than_three_tickers_are_rejected_before_any_engine_runs():
    run = AsyncMock(side_effect=lambda t: _ok(t))
    with patch("routers.landing._run_one", new=run):
        resp = client.post("/api/landing/analyze",
                           json={"tickers": ["A", "B", "C", "D"]})
    assert resp.json()["error"] == "Up to 3 tickers per analysis run."
    assert run.await_count == 0


def test_an_empty_request_is_rejected():
    resp = client.post("/api/landing/analyze", json={"tickers": ["  ", ""]})
    assert resp.json()["error"] == "Enter at least one ticker."


def test_an_unresolvable_ticker_is_reported_not_run():
    run = AsyncMock(side_effect=lambda t: _ok(t))
    with patch("routers.landing.validate_ticker", new=AsyncMock(return_value=False)), \
         patch("routers.landing._run_one", new=run):
        resp = client.post("/api/landing/analyze", json={"tickers": ["ZZZZ"]})
    body = resp.json()
    assert body["invalid"] == ["ZZZZ"]
    assert body["results"] == []
    assert run.await_count == 0


def test_duplicates_are_collapsed():
    run = AsyncMock(side_effect=lambda t: _ok(t))
    with patch("routers.landing.validate_ticker", new=AsyncMock(return_value=True)), \
         patch("routers.landing._run_one", new=run):
        resp = client.post("/api/landing/analyze", json={"tickers": ["AAPL", "aapl"]})
    assert len(resp.json()["results"]) == 1
    assert run.await_count == 1


def test_one_failing_ticker_does_not_sink_the_others():
    async def flaky(t):
        if t == "BAD":
            raise RuntimeError("yahoo down")
        return _ok(t)

    with patch("routers.landing.validate_ticker", new=AsyncMock(return_value=True)), \
         patch("routers.landing._run_one", new=AsyncMock(side_effect=flaky)):
        resp = client.post("/api/landing/analyze", json={"tickers": ["AAPL", "BAD"]})
    body = resp.json()
    tickers = {r["ticker"]: r for r in body["results"]}
    assert tickers["AAPL"]["fair_value"]["value"] == 110.0
    assert tickers["BAD"]["errors"]
    assert tickers["BAD"]["quality"] is None
```

- [ ] **Step 2: Run them and watch them fail**

Run: `cd backend && python -m pytest tests/test_landing_router.py -v`
Expected: FAIL — 404.

- [ ] **Step 3: Write the router**

Create `backend/routers/landing.py`:

```python
from __future__ import annotations
import asyncio
from fastapi import APIRouter
from pydantic import BaseModel

from services.yahoo import validate_ticker
from orchestrator.batch import _run_one
from landing.contract import build_ticker_payload

router = APIRouter()

# The demo allowance (spec section 10). It is also the Free plan's per-run cap.
MAX_TICKERS = 3


class LandingAnalyzeRequest(BaseModel):
    tickers: list[str] = []


@router.post("/landing/analyze")
async def analyze(req: LandingAnalyzeRequest):
    seen: list[str] = []
    for raw in req.tickers:
        t = raw.strip().upper()
        if t and t not in seen:
            seen.append(t)

    if not seen:
        return {"results": [], "invalid": [], "error": "Enter at least one ticker."}
    if len(seen) > MAX_TICKERS:
        # Checked before validation so an oversized request never costs an engine run.
        return {"results": [], "invalid": [],
                "error": f"Up to {MAX_TICKERS} tickers per analysis run."}

    checks = await asyncio.gather(*[validate_ticker(t) for t in seen])
    valid = [t for t, ok in zip(seen, checks) if ok]
    invalid = [t for t, ok in zip(seen, checks) if not ok]
    if not valid:
        return {"results": [], "invalid": invalid, "error": None}

    runs = await asyncio.gather(*[_run_one(t) for t in valid], return_exceptions=True)

    results = []
    for ticker, run in zip(valid, runs):
        if isinstance(run, Exception):
            # One dead pipeline must not sink the whole grid.
            results.append(build_ticker_payload(
                {"ticker": ticker, "errors": [str(run)], "status": "failed"}))
        else:
            results.append(build_ticker_payload(run["result"]))

    return {"results": results, "invalid": invalid, "error": None}
```

- [ ] **Step 4: Register the router**

In `backend/main.py`:

```python
from routers.landing import router as landing_router
...
app.include_router(landing_router, prefix="/api")
```

- [ ] **Step 5: Run the tests and watch them pass**

Run: `cd backend && python -m pytest tests/test_landing_router.py -v`
Expected: 6 passed.

- [ ] **Step 6: Run the whole backend suite**

Run: `cd backend && python -m pytest tests/ -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/routers/landing.py backend/main.py backend/tests/test_landing_router.py
git commit -m "feat(landing): POST /api/landing/analyze capped at three tickers"
```

---

## Task 7: Landing shell — routes, scoped light theme, nav and footer

`frontend/src/index.css` sets `color-scheme: dark` and a dark `body` globally, and `Layout` wraps every route. The landing page is light, so it renders **outside** `Layout` and scopes its own theme on a wrapper.

**Files:**
- Create: `frontend/src/landing/types.ts`
- Create: `frontend/src/landing/theme.css`
- Create: `frontend/src/landing/components/Nav.tsx`
- Create: `frontend/src/landing/components/SiteFooter.tsx`
- Create: `frontend/src/landing/LandingPage.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/landing/LandingPage.test.tsx`

**Interfaces:**
- Consumes: `track`, `EVENTS` from `../lib/analytics`.
- Produces:
  - `landing/types.ts`: `TickerPayload`, `QualityBlock`, `MoatBlock`, `FairValueBlock`, `RewardRiskBlock`, `MetricRow`, `AnalyzeResponse`
  - `<Nav />` — the six anchors
  - `<SiteFooter />`
  - `<LandingPage />` at `/`; the existing analyst `Home` moves to `/app`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/landing/LandingPage.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import LandingPage from './LandingPage'

vi.mock('../lib/analytics', () => ({
  track: vi.fn(),
  visitorId: () => 'v-test',
  EVENTS: { pageView: 'page_view' },
}))

function renderPage() {
  return render(<MemoryRouter><LandingPage /></MemoryRouter>)
}

describe('LandingPage shell', () => {
  it('links to every section from the nav', () => {
    renderPage()
    const hrefs = screen.getAllByRole('link').map(a => a.getAttribute('href'))
    for (const anchor of ['#analyze', '#how', '#why', '#workflow', '#pricing']) {
      expect(hrefs).toContain(anchor)
    }
  })

  it('scopes its own light theme instead of changing the global dark one', () => {
    const { container } = renderPage()
    expect(container.querySelector('.intrinsica')).toBeInTheDocument()
    expect(document.body.style.backgroundColor).toBe('')
  })

  it('records a page view once', async () => {
    const { track } = await import('../lib/analytics')
    renderPage()
    expect(track).toHaveBeenCalledWith('page_view')
  })

  it('carries no card or payment input', () => {
    const { container } = renderPage()
    const inputs = Array.from(container.querySelectorAll('input'))
    expect(inputs.some(i => /card|cvc|cvv|payment|expiry/i.test(i.outerHTML))).toBe(false)
  })
})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd frontend && npm test -- src/landing/LandingPage.test.tsx`
Expected: FAIL — cannot resolve `./LandingPage`.

- [ ] **Step 3: Write the contract types**

Create `frontend/src/landing/types.ts`:

```ts
/** Mirrors backend/landing/contract.py — keep the two in step. */
export interface MetricRow {
  label: string
  raw: number | null
  score: number | null
  weight_pct: number
  excluded: boolean
  excluded_by: string | null
}

export interface QualityCategory {
  key: 'I' | 'II' | 'III' | 'IV'
  name: string
  weight_pct: number
  score: number | null
  metrics: MetricRow[]
}

export interface QualityBlock {
  score: number | null
  profile_label: string | null
  categories: QualityCategory[]
}

export interface MoatBlock {
  score: number | null
  gated: boolean
  excluded: string[]
  factors: { label: string; points: number | null; max_points: number; weight_pct: number }[]
}

export interface FairValueBlock {
  value: number | null
  gap_pct: number | null
  type_label: string | null
  methods: { label: string; value: number | null; weight_pct: number; contribution: number | null }[]
}

export interface RewardRiskFactor {
  label: string
  raw: number | null
  score: number | null
  weight_pct: number
  dropped: boolean
}

export interface RewardRiskBlock {
  ratio: number | null
  tier: string | null
  reward_score: number | null
  risk_score: number | null
  reward: RewardRiskFactor[]
  risk: RewardRiskFactor[]
}

export interface TickerPayload {
  ticker: string
  company_name: string | null
  price: number | null
  quality: QualityBlock | null
  moat: MoatBlock | null
  fair_value: FairValueBlock | null
  reward_risk: RewardRiskBlock | null
  calibrations: string[]
  errors: string[]
}

export interface AnalyzeResponse {
  results: TickerPayload[]
  invalid: string[]
  error: string | null
}

/** The four assessments, in page order. Index doubles as the framework tab id. */
export type AssessmentId = 0 | 1 | 2 | 3
```

- [ ] **Step 4: Write the scoped theme**

Create `frontend/src/landing/theme.css`:

```css
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

/* Scoped to .intrinsica so the existing dark analyst app is untouched. */
.intrinsica {
  --bg: #ffffff;
  --stage: #f7f8fb;
  --text: #0f1222;
  --dim: #454b63;
  --mute: #7b819a;
  --line: #e6e8f0;
  --accent: #4f46e5;
  --accent-soft: #eef0fe;
  --q: #22c55e;
  --mo: #3b82f6;
  --fv: #4f46e5;
  --rr: #f59e0b;
  --pos: #16a34a;
  --warn: #d97706;
  --neg: #dc2626;
  --fh: 'Space Grotesk', system-ui, sans-serif;
  --fb: 'Inter', system-ui, sans-serif;
  --fm: 'JetBrains Mono', monospace;

  color-scheme: light;
  background: var(--bg);
  color: var(--text);
  font-family: var(--fb);
  min-height: 100vh;
}

.intrinsica h1, .intrinsica h2, .intrinsica h3, .intrinsica h4 { font-family: var(--fh); }
.intrinsica .section { padding: 56px 0; }
.intrinsica .section.stage { background: var(--stage); }
.intrinsica .container { max-width: 1120px; margin: 0 auto; padding: 0 16px; }
.intrinsica .nav { position: sticky; top: 0; z-index: 20; background: rgba(255,255,255,.92);
  backdrop-filter: blur(8px); border-bottom: 1px solid var(--line); }
.intrinsica .nav-in { max-width: 1120px; margin: 0 auto; padding: 12px 16px;
  display: flex; align-items: center; justify-content: space-between; }
.intrinsica .links { display: flex; gap: 18px; align-items: center; flex-wrap: wrap; }
.intrinsica .links a { color: var(--dim); text-decoration: none; font-size: 14px; cursor: pointer; }
.intrinsica .links a:hover { color: var(--text); }
.intrinsica .links a.cta { background: var(--accent); color: #fff; border-radius: 8px; padding: 7px 14px; }
@media (max-width: 700px) { .intrinsica .links { gap: 12px; } .intrinsica .section { padding: 36px 0; } }
```

- [ ] **Step 5: Write the nav and footer**

Create `frontend/src/landing/components/Nav.tsx`:

```tsx
const SECTIONS = [
  { href: '#analyze', label: 'Analyze' },
  { href: '#how', label: 'Methodology' },
  { href: '#why', label: 'Why Intrinsica' },
  { href: '#workflow', label: 'Workflow' },
  { href: '#pricing', label: 'Pricing' },
]

export default function Nav() {
  return (
    <nav className="nav">
      <div className="nav-in">
        <div className="logo">Intrinsica</div>
        <div className="links">
          {SECTIONS.map(s => (
            <a key={s.href} href={s.href}>{s.label}</a>
          ))}
          <a className="cta" href="#pricing">Sign up</a>
        </div>
      </div>
    </nav>
  )
}
```

Create `frontend/src/landing/components/SiteFooter.tsx`:

```tsx
export default function SiteFooter() {
  return (
    <footer className="footer">
      <div className="container">
        <p className="legal">
          <b>Intrinsica</b> provides automated quantitative financial-data modeling tools
          for informational analysis. Nothing on this platform constitutes personalized
          investment advice.
        </p>
        <p className="sec">
          Intrinsica provides systematic analysis and scoring of individual stocks to help
          investors conduct their own fundamental research and make informed decisions.
        </p>
      </div>
    </footer>
  )
}
```

- [ ] **Step 6: Write the page shell**

Create `frontend/src/landing/LandingPage.tsx`:

```tsx
import { useEffect } from 'react'
import './theme.css'
import Nav from './components/Nav'
import SiteFooter from './components/SiteFooter'
import { track, EVENTS } from '../lib/analytics'

export default function LandingPage() {
  useEffect(() => {
    track(EVENTS.pageView)
  }, [])

  return (
    <div className="intrinsica">
      <Nav />
      <main>
        {/* Hero, results, methodology, why, workflow and pricing are added by the
            tasks that follow; each mounts into this main element. */}
      </main>
      <SiteFooter />
    </div>
  )
}
```

- [ ] **Step 7: Move the analyst app off `/` and mount the landing page**

Replace `frontend/src/App.tsx` with:

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Progress from './pages/Progress'
import Results from './pages/Results'
import TickerDetail from './pages/TickerDetail'
import Database from './pages/Database'
import LandingPage from './landing/LandingPage'

/** The landing page owns `/` and renders outside Layout: Layout is the dark analyst
 *  chrome, and the landing page is light. The analyst app moves to /app. */
export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/app" element={<Layout><Home /></Layout>} />
        <Route path="/progress/:jobId" element={<Layout><Progress /></Layout>} />
        <Route path="/results/:jobId" element={<Layout><Results /></Layout>} />
        <Route path="/ticker/:jobId/:ticker" element={<Layout><TickerDetail /></Layout>} />
        <Route path="/database" element={<Layout><Database /></Layout>} />
      </Routes>
    </BrowserRouter>
  )
}
```

Then update the two links in `frontend/src/components/Layout.tsx` so `Analyse` points at `/app` instead of `/`:

```tsx
  const navItems = [
    { href: '/app', label: 'Analyse' },
    { href: '/database', label: 'Database' },
  ]
```

- [ ] **Step 8: Run the tests and watch them pass**

Run: `cd frontend && npm test`
Expected: all pass (4 new + the analytics suite).

- [ ] **Step 9: Verify the build still type-checks**

Run: `cd frontend && npm run build`
Expected: succeeds.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/landing frontend/src/App.tsx frontend/src/components/Layout.tsx
git commit -m "feat(landing): route, scoped light theme, nav and footer"
```

---

## Task 8: Hero, the four assessments, and the analyzer

**Files:**
- Create: `frontend/src/landing/components/Hero.tsx`
- Modify: `frontend/src/landing/LandingPage.tsx`
- Test: `frontend/src/landing/components/Hero.test.tsx`

**Interfaces:**
- Consumes: `AssessmentId` from `../types`.
- Produces: `<Hero onAnalyze={(tickers: string[]) => void} onSelectAssessment={(id: AssessmentId) => void} busy={boolean} />`
  and the exported constant `ASSESSMENTS: { name: string; question: string; color: string }[]`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/landing/components/Hero.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Hero, { ASSESSMENTS } from './Hero'

const noop = () => {}

describe('Hero', () => {
  it('shows the four assessments with their questions', () => {
    render(<Hero onAnalyze={noop} onSelectAssessment={noop} busy={false} />)
    expect(ASSESSMENTS.map(a => a.name)).toEqual(
      ['Quality', 'Moat', 'Fair Value', 'Reward / Risk'])
    for (const a of ASSESSMENTS) {
      expect(screen.getByText(a.question)).toBeInTheDocument()
    }
  })

  it('selects that assessment when one is clicked', async () => {
    const onSelect = vi.fn()
    render(<Hero onAnalyze={noop} onSelectAssessment={onSelect} busy={false} />)
    await userEvent.click(screen.getByRole('button', { name: /Moat/ }))
    expect(onSelect).toHaveBeenCalledWith(1)
  })

  it('splits a comma-separated list, upper-cases it and drops blanks', async () => {
    const onAnalyze = vi.fn()
    render(<Hero onAnalyze={onAnalyze} onSelectAssessment={noop} busy={false} />)
    await userEvent.type(screen.getByRole('textbox'), 'nvda, amd ,, avgo')
    await userEvent.click(screen.getByRole('button', { name: /Analyze/ }))
    expect(onAnalyze).toHaveBeenCalledWith(['NVDA', 'AMD', 'AVGO'])
  })

  it('refuses a fourth ticker with a readable message and does not submit', async () => {
    const onAnalyze = vi.fn()
    render(<Hero onAnalyze={onAnalyze} onSelectAssessment={noop} busy={false} />)
    await userEvent.type(screen.getByRole('textbox'), 'A,B,C,D')
    await userEvent.click(screen.getByRole('button', { name: /Analyze/ }))
    expect(onAnalyze).not.toHaveBeenCalled()
    expect(screen.getByText('Up to 3 tickers per analysis run.')).toBeInTheDocument()
  })

  it('does not submit an empty field', async () => {
    const onAnalyze = vi.fn()
    render(<Hero onAnalyze={onAnalyze} onSelectAssessment={noop} busy={false} />)
    await userEvent.click(screen.getByRole('button', { name: /Analyze/ }))
    expect(onAnalyze).not.toHaveBeenCalled()
  })

  it('never uses the word signal', () => {
    const { container } = render(
      <Hero onAnalyze={noop} onSelectAssessment={noop} busy={false} />)
    expect(container.textContent).not.toMatch(/signal/i)
  })
})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd frontend && npm test -- src/landing/components/Hero.test.tsx`
Expected: FAIL — cannot resolve `./Hero`.

- [ ] **Step 3: Write the component**

Create `frontend/src/landing/components/Hero.tsx`:

```tsx
import { useState } from 'react'
import type { AssessmentId } from '../types'

export const MAX_TICKERS = 3

export const ASSESSMENTS = [
  { name: 'Quality', color: 'var(--q)',
    question: 'How strong is the underlying business?' },
  { name: 'Moat', color: 'var(--mo)',
    question: 'How durable are its competitive advantages?' },
  { name: 'Fair Value', color: 'var(--fv)',
    question: 'What is the business worth based on its fundamentals and valuation methods?' },
  { name: 'Reward / Risk', color: 'var(--rr)',
    question: 'How attractive is the current price relative to intrinsic value and downside risk?' },
]

interface Props {
  onAnalyze: (tickers: string[]) => void
  onSelectAssessment: (id: AssessmentId) => void
  busy: boolean
}

export default function Hero({ onAnalyze, onSelectAssessment, busy }: Props) {
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)

  function submit() {
    const tickers = value.split(',').map(t => t.trim().toUpperCase()).filter(Boolean)
    if (tickers.length === 0) {
      setError('Enter at least one ticker.')
      return
    }
    if (tickers.length > MAX_TICKERS) {
      setError(`Up to ${MAX_TICKERS} tickers per analysis run.`)
      return
    }
    setError(null)
    onAnalyze(tickers)
  }

  return (
    <header className="hero">
      <div className="container">
        <div className="brand">Intrinsica</div>
        <div className="h3">Fundamental Stock Analysis</div>

        <div className="assess4">
          {ASSESSMENTS.map((a, i) => (
            <button
              key={a.name}
              type="button"
              className="it"
              onClick={() => onSelectAssessment(i as AssessmentId)}
            >
              <span className="nm">
                <span className="dot" style={{ background: a.color }} />
                {a.name} <span className="go">→</span>
              </span>
              <span className="q">{a.question}</span>
            </button>
          ))}
        </div>

        <p className="sub">
          Evaluate stocks using a consistent, transparent fundamental framework.
        </p>

        <div className="analyzer" id="analyze">
          <div className="an-row">
            <div className="an-field">
              <input
                value={value}
                onChange={e => setValue(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') submit() }}
                placeholder="Enter one or more tickers — e.g. NVDA, AMD, AVGO"
              />
            </div>
            <button className="an-btn" type="button" onClick={submit} disabled={busy}>
              {busy ? 'Analyzing…' : 'Analyze →'}
            </button>
          </div>
          {error && <p className="an-error">{error}</p>}
        </div>
      </div>
    </header>
  )
}
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `cd frontend && npm test -- src/landing/components/Hero.test.tsx`
Expected: 6 passed.

- [ ] **Step 5: Mount it and wire the analyze call**

In `frontend/src/landing/LandingPage.tsx`, add the analyze state and render the hero:

```tsx
import { useCallback, useEffect, useState } from 'react'
import './theme.css'
import Nav from './components/Nav'
import Hero from './components/Hero'
import SiteFooter from './components/SiteFooter'
import { track, EVENTS } from '../lib/analytics'
import { API_BASE } from '../lib/api'
import type { AnalyzeResponse, AssessmentId, TickerPayload } from './types'

const SAMPLE = 'AAPL'

export default function LandingPage() {
  const [rows, setRows] = useState<TickerPayload[]>([])
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [assessment, setAssessment] = useState<AssessmentId>(0)

  const analyze = useCallback(async (tickers: string[]) => {
    setBusy(true)
    setNotice(null)
    track(EVENTS.analysisStarted, { tickers, count: tickers.length })
    const started = Date.now()
    try {
      const resp = await fetch(`${API_BASE}/api/landing/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tickers }),
      })
      const body: AnalyzeResponse = await resp.json()
      if (body.error) setNotice(body.error)
      else if (body.invalid.length) setNotice(`Not recognised: ${body.invalid.join(', ')}`)
      setRows(body.results)
      track(EVENTS.analysisCompleted, { duration_ms: Date.now() - started,
                                        count: body.results.length })
    } catch {
      setNotice('The analysis could not be reached. Please try again.')
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => {
    track(EVENTS.pageView)
    void analyze([SAMPLE])
  }, [analyze])

  return (
    <div className="intrinsica">
      <Nav />
      <main>
        <Hero onAnalyze={analyze} onSelectAssessment={setAssessment} busy={busy} />
        {notice && <p className="notice container">{notice}</p>}
        {/* The results grid, methodology, why, workflow and pricing sections mount
            here in the tasks that follow; `rows` and `assessment` feed them. */}
      </main>
      <SiteFooter />
    </div>
  )
}
```

Update `LandingPage.test.tsx`'s analytics mock to include the events the page now fires, and stub `fetch` so the sample run does not hit the network:

```tsx
vi.mock('../lib/analytics', () => ({
  track: vi.fn(),
  visitorId: () => 'v-test',
  EVENTS: {
    pageView: 'page_view',
    analysisStarted: 'analysis_started',
    analysisCompleted: 'analysis_completed',
  },
}))

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    json: async () => ({ results: [], invalid: [], error: null }),
  }))
})
```

- [ ] **Step 6: Run the full frontend suite**

Run: `cd frontend && npm test`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/landing
git commit -m "feat(landing): hero with the four assessments and the analyzer"
```

---

## Task 9: The results grid

Style B · Institutional: values only, units in the header, `% vs Price` colour-banded, one row per ticker, expandable. Headline numbers are read from the payload the breakdown also renders, so the two cannot disagree.

**Files:**
- Create: `frontend/src/landing/format.ts`
- Create: `frontend/src/landing/components/ResultGrid.tsx`
- Modify: `frontend/src/landing/LandingPage.tsx`
- Test: `frontend/src/landing/format.test.ts`
- Test: `frontend/src/landing/components/ResultGrid.test.tsx`

**Interfaces:**
- Consumes: `TickerPayload` from `../types`.
- Produces:
  - `format.ts`: `money(v: number | null): string`, `num(v: number | null, dp?: number): string`, `pct(v: number | null): string`, `gapClass(v: number | null): string`
  - `<ResultGrid rows={TickerPayload[]} open={Record<string, boolean>} onToggle={(t: string) => void} renderBreakdown={(row: TickerPayload) => ReactNode} />`

- [ ] **Step 1: Write the failing formatter tests**

Create `frontend/src/landing/format.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { money, num, pct, gapClass } from './format'

describe('formatters', () => {
  it('renders an em dash for every absent value', () => {
    expect(money(null)).toBe('—')
    expect(num(null)).toBe('—')
    expect(pct(null)).toBe('—')
  })

  it('formats money and percentages', () => {
    expect(money(211)).toBe('$211.00')
    expect(pct(-9.05)).toBe('-9.1%')
    expect(pct(17)).toBe('+17.0%')
  })

  it('rounds numbers to the requested precision', () => {
    expect(num(9.14, 1)).toBe('9.1')
    expect(num(0.92, 2)).toBe('0.92')
  })

  it('never emits NaN or Infinity', () => {
    expect(num(NaN)).toBe('—')
    expect(pct(Infinity)).toBe('—')
    expect(money(-Infinity)).toBe('—')
  })

  it('bands the fair-value gap by size and direction', () => {
    expect(gapClass(12)).toBe('gap-pos')
    expect(gapClass(4)).toBe('gap-near')
    expect(gapClass(-4)).toBe('gap-warn')
    expect(gapClass(-18)).toBe('gap-neg')
    expect(gapClass(null)).toBe('gap-none')
  })
})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd frontend && npm test -- src/landing/format.test.ts`
Expected: FAIL — cannot resolve `./format`.

- [ ] **Step 3: Write the formatters**

Create `frontend/src/landing/format.ts`:

```ts
/** Every absent, non-finite or engine-declined value renders as an em dash. A grid
 *  cell must never show NaN, Infinity or "null". */
const DASH = '—'

function finite(v: number | null | undefined): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}

export function money(v: number | null): string {
  return finite(v) ? `$${v.toFixed(2)}` : DASH
}

export function num(v: number | null, dp = 1): string {
  return finite(v) ? v.toFixed(dp) : DASH
}

export function pct(v: number | null): string {
  if (!finite(v)) return DASH
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
}

/** Spec section 5.2: >= +10% green, 0..+10% blue, -10..0 amber, < -10% red. */
export function gapClass(v: number | null): string {
  if (!finite(v)) return 'gap-none'
  if (v >= 10) return 'gap-pos'
  if (v >= 0) return 'gap-near'
  if (v >= -10) return 'gap-warn'
  return 'gap-neg'
}
```

- [ ] **Step 4: Run the formatter tests and watch them pass**

Run: `cd frontend && npm test -- src/landing/format.test.ts`
Expected: 5 passed.

- [ ] **Step 5: Write the failing grid tests**

Create `frontend/src/landing/components/ResultGrid.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ResultGrid from './ResultGrid'
import type { TickerPayload } from '../types'

function row(over: Partial<TickerPayload> = {}): TickerPayload {
  return {
    ticker: 'AAPL', company_name: 'Apple Inc.', price: 232,
    quality: { score: 9.1, profile_label: 'Tech / Growth', categories: [] },
    moat: { score: 90, gated: false, excluded: [], factors: [] },
    fair_value: { value: 211, gap_pct: -9.05, type_label: 'Mega Cap', methods: [] },
    reward_risk: { ratio: 0.9, tier: 'Balanced', reward_score: 2.8, risk_score: 3.1,
                   reward: [], risk: [] },
    calibrations: [], errors: [],
    ...over,
  }
}

const render1 = (rows: TickerPayload[], open = {}) =>
  render(<ResultGrid rows={rows} open={open} onToggle={vi.fn()}
                     renderBreakdown={() => <div>BREAKDOWN</div>} />)

describe('ResultGrid', () => {
  it('puts the units in the header, not the cells', () => {
    render1([row()])
    const header = screen.getAllByRole('row')[0]
    expect(within(header).getByText(/Quality/)).toHaveTextContent('/10')
    expect(within(header).getByText(/Moat/)).toHaveTextContent('/100')
    expect(within(header).getByText(/Reward\/Risk/)).toBeInTheDocument()
    const cells = screen.getAllByRole('cell').map(c => c.textContent)
    expect(cells).toContain('9.1')
    expect(cells).toContain('90')
  })

  it('never labels the ratio Risk/Reward', () => {
    const { container } = render1([row()])
    expect(container.textContent).not.toMatch(/Risk\/Reward|Risk \/ Reward/)
  })

  it('shows no tier word in the grid', () => {
    const { container } = render1([row()])
    expect(container.textContent).not.toMatch(/Balanced/)
  })

  it('colour-bands the fair-value gap', () => {
    const { container } = render1([row()])
    expect(container.querySelector('.gap-warn')).toBeInTheDocument()
  })

  // --- Review Focus 1: one engine failed ---
  it('renders a row whose quality and moat are missing', () => {
    const { container } = render1([row({ quality: null, moat: null })])
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/NaN|null|undefined/)
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(2)
  })

  // --- Review Focus 2: no fair value ---
  it('renders a row with no fair value without inventing a gap', () => {
    const { container } = render1([row({ fair_value: null })])
    expect(container.textContent).not.toMatch(/NaN|Infinity/)
    expect(container.querySelector('.gap-none')).toBeInTheDocument()
  })

  it('expands a row on click and shows its breakdown', async () => {
    const onToggle = vi.fn()
    render(<ResultGrid rows={[row()]} open={{}} onToggle={onToggle}
                       renderBreakdown={() => <div>BREAKDOWN</div>} />)
    await userEvent.click(screen.getByText('AAPL'))
    expect(onToggle).toHaveBeenCalledWith('AAPL')
    expect(screen.queryByText('BREAKDOWN')).not.toBeInTheDocument()
  })

  it('shows the breakdown for an already-open row', () => {
    render1([row()], { AAPL: true })
    expect(screen.getByText('BREAKDOWN')).toBeInTheDocument()
  })
})
```

- [ ] **Step 6: Run them and watch them fail**

Run: `cd frontend && npm test -- src/landing/components/ResultGrid.test.tsx`
Expected: FAIL — cannot resolve `./ResultGrid`.

- [ ] **Step 7: Write the grid**

Create `frontend/src/landing/components/ResultGrid.tsx`:

```tsx
import { Fragment, type ReactNode } from 'react'
import type { TickerPayload } from '../types'
import { gapClass, money, num, pct } from '../format'

interface Props {
  rows: TickerPayload[]
  open: Record<string, boolean>
  onToggle: (ticker: string) => void
  renderBreakdown: (row: TickerPayload) => ReactNode
}

/** Units live in the header so the cells stay numeric (style B). Tier words such as
 *  "Balanced" belong in the breakdown, never here. */
const HEAD: { label: string; unit?: string }[] = [
  { label: 'Company' },
  { label: 'Quality', unit: '/10' },
  { label: 'Moat', unit: '/100' },
  { label: 'Fair Value' },
  { label: '% vs Price' },
  { label: 'Price' },
  { label: 'Reward/Risk', unit: '×' },
  { label: '' },
]

export default function ResultGrid({ rows, open, onToggle, renderBreakdown }: Props) {
  if (rows.length === 0) return null

  return (
    <div className="tB">
      <table className="g">
        <thead>
          <tr>
            {HEAD.map(h => (
              <th key={h.label}>
                {h.label}
                {h.unit && <u> {h.unit}</u>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(r => {
            const isOpen = !!open[r.ticker]
            return (
              <Fragment key={r.ticker}>
                <tr className={isOpen ? 'row open' : 'row'}
                    onClick={() => onToggle(r.ticker)}>
                  <td className="co">
                    <b>{r.ticker}</b>
                    <span className="cn">{r.company_name ?? ''}</span>
                  </td>
                  <td>{num(r.quality?.score ?? null, 1)}</td>
                  <td>{num(r.moat?.score ?? null, 0)}</td>
                  <td>{money(r.fair_value?.value ?? null)}</td>
                  <td className={gapClass(r.fair_value?.gap_pct ?? null)}>
                    {pct(r.fair_value?.gap_pct ?? null)}
                  </td>
                  <td>{money(r.price)}</td>
                  <td>{num(r.reward_risk?.ratio ?? null, 1)}</td>
                  <td className="ex">{isOpen ? '▴' : '▾'}</td>
                </tr>
                {isOpen && (
                  <tr className="exp">
                    <td colSpan={HEAD.length}>{renderBreakdown(r)}</td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 8: Run the grid tests and watch them pass**

Run: `cd frontend && npm test -- src/landing/components/ResultGrid.test.tsx`
Expected: 8 passed.

- [ ] **Step 9: Mount the grid in the page**

In `frontend/src/landing/LandingPage.tsx`, add the open-row state and render the grid below the hero:

```tsx
  const [open, setOpen] = useState<Record<string, boolean>>({})

  const toggle = useCallback((ticker: string) => {
    setOpen(prev => {
      const next = { ...prev, [ticker]: !prev[ticker] }
      if (next[ticker]) track(EVENTS.breakdownOpened, { ticker })
      return next
    })
  }, [])
```

and inside `<main>`, after `<Hero ... />`:

```tsx
        <section className="section" id="result">
          <div className="container">
            <ResultGrid
              rows={rows}
              open={open}
              onToggle={toggle}
              renderBreakdown={() => null}
            />
            <p className="free-note">
              <b>Everything here is the real analysis — full depth, nothing blurred.</b>{' '}
              The demo is open to everyone: up to 3 tickers per run, no account needed.
              At launch the <b>Free</b> plan keeps that depth with about 5 analyses a
              month; <b>Pro</b> removes the cap and adds the research workflow.
            </p>
          </div>
        </section>
```

Add `breakdownOpened: 'breakdown_opened'` to the analytics mock in `LandingPage.test.tsx`.

- [ ] **Step 10: Run the full frontend suite**

Run: `cd frontend && npm test`
Expected: all pass.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/landing
git commit -m "feat(landing): institutional results grid with banded fair-value gap"
```

---

## Task 10: The breakdown panel

Full-width slim tabs over one `Factor | Data | Score | Weight` table per assessment.

**Files:**
- Create: `frontend/src/landing/components/Breakdown.tsx`
- Modify: `frontend/src/landing/LandingPage.tsx` (pass a real `renderBreakdown`)
- Test: `frontend/src/landing/components/Breakdown.test.tsx`

**Interfaces:**
- Consumes: `TickerPayload`, `AssessmentId`, the formatters from `../format`.
- Produces: `<Breakdown row={TickerPayload} tab={AssessmentId} onTab={(id: AssessmentId) => void} />`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/landing/components/Breakdown.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Breakdown from './Breakdown'
import type { TickerPayload } from '../types'

function payload(over: Partial<TickerPayload> = {}): TickerPayload {
  return {
    ticker: 'AAPL', company_name: 'Apple Inc.', price: 232,
    quality: {
      score: 9.1, profile_label: 'Tech / Growth',
      categories: [{
        key: 'I', name: 'Growth & Margins', weight_pct: 35, score: 8,
        metrics: [
          { label: 'Revenue growth (3-yr)', raw: 0.08, score: 6, weight_pct: 17.5,
            excluded: false, excluded_by: null },
          { label: 'FCF margin', raw: null, score: null, weight_pct: 0,
            excluded: true, excluded_by: 'Heavy-capex FCF exclusion' },
        ],
      }],
    },
    moat: {
      score: 90, gated: false, excluded: [],
      factors: [{ label: 'ROIC level', points: 18, max_points: 20, weight_pct: 20 }],
    },
    fair_value: {
      value: 211, gap_pct: -9.05, type_label: 'Mega Cap',
      methods: [{ label: 'Discounted cash flow', value: 205, weight_pct: 55,
                  contribution: 112.75 }],
    },
    reward_risk: {
      ratio: 0.9, tier: 'Balanced', reward_score: 2.8, risk_score: 3.1,
      reward: [{ label: 'Discount to 52-week high', raw: 0.05, score: 2,
                 weight_pct: 24, dropped: false }],
      risk: [{ label: 'Volatility', raw: 0.3, score: 3, weight_pct: 22, dropped: false }],
    },
    calibrations: ['Heavy-capex FCF exclusion'], errors: [],
    ...over,
  }
}

const show = (p = payload(), tab: 0 | 1 | 2 | 3 = 0) =>
  render(<Breakdown row={p} tab={tab} onTab={vi.fn()} />)

describe('Breakdown', () => {
  it('offers a tab per assessment, labelled Reward/Risk', () => {
    show()
    for (const name of ['Quality', 'Moat', 'Fair Value', 'Reward / Risk']) {
      expect(screen.getByRole('button', { name })).toBeInTheDocument()
    }
  })

  it('shows the four columns and the category weight', () => {
    show()
    for (const h of ['Factor', 'Data', 'Score', 'Weight']) {
      expect(screen.getByText(h)).toBeInTheDocument()
    }
    expect(screen.getByText(/Growth & Margins/)).toBeInTheDocument()
    expect(screen.getByText('35%')).toBeInTheDocument()
  })

  // --- Review Focus 3, rendered side ---
  it('strikes an excluded metric through at zero weight and names the calibration', () => {
    const { container } = show()
    const excluded = container.querySelector('.metric.excluded')
    expect(excluded).toHaveTextContent('FCF margin')
    expect(excluded).toHaveTextContent('0%')
    expect(excluded).toHaveTextContent('Heavy-capex FCF exclusion')
  })

  it('switches to the requested tab', async () => {
    const onTab = vi.fn()
    render(<Breakdown row={payload()} tab={0} onTab={onTab} />)
    await userEvent.click(screen.getByRole('button', { name: 'Moat' }))
    expect(onTab).toHaveBeenCalledWith(1)
  })

  it('shows moat factors as points over their max', () => {
    show(payload(), 1)
    expect(screen.getByText('18 / 20')).toBeInTheDocument()
  })

  it('shows the fair-value blend as one exact number, not a range', () => {
    const { container } = show(payload(), 2)
    expect(screen.getByText('Discounted cash flow')).toBeInTheDocument()
    expect(screen.getByText('$211.00')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/\$\d[\d.]*\s*[–-]\s*\$\d/)
  })

  it('states the ratio direction and shows both axes', () => {
    show(payload(), 3)
    expect(screen.getByText(/Reward ÷ Risk/)).toHaveTextContent('higher is better')
    expect(screen.getByText('Discount to 52-week high')).toBeInTheDocument()
    expect(screen.getByText('Volatility')).toBeInTheDocument()
    expect(screen.getByText('Balanced')).toBeInTheDocument()
  })

  it('lists only the calibrations that fired', () => {
    show()
    expect(screen.getByText(/Heavy-capex FCF exclusion/)).toBeInTheDocument()
  })

  it('renders a missing assessment as a note rather than an empty table', () => {
    show(payload({ moat: null }), 1)
    expect(screen.getByText(/could not be computed/i)).toBeInTheDocument()
  })

  it('leaks no internal classifier code', () => {
    const { container } = show()
    expect(container.textContent).not.toMatch(/[A-Z]{3,}_[A-Z]{3,}/)
  })
})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd frontend && npm test -- src/landing/components/Breakdown.test.tsx`
Expected: FAIL — cannot resolve `./Breakdown`.

- [ ] **Step 3: Write the component**

Create `frontend/src/landing/components/Breakdown.tsx`:

```tsx
import type { AssessmentId, TickerPayload } from '../types'
import { money, num } from '../format'

const TABS = ['Quality', 'Moat', 'Fair Value', 'Reward / Risk']

const pctLabel = (v: number) => `${Number.isInteger(v) ? v : v.toFixed(1)}%`
const raw = (v: number | null) => (v === null || !Number.isFinite(v) ? '—' : String(v))

function Missing({ what }: { what: string }) {
  return <p className="bd-missing">{what} could not be computed for this company.</p>
}

function Table({ children }: { children: React.ReactNode }) {
  return (
    <table className="bt">
      <thead>
        <tr><th>Factor</th><th>Data</th><th>Score</th><th>Weight</th></tr>
      </thead>
      <tbody>{children}</tbody>
    </table>
  )
}

export default function Breakdown({ row, tab, onTab }: {
  row: TickerPayload
  tab: AssessmentId
  onTab: (id: AssessmentId) => void
}) {
  return (
    <div className="bd">
      <div className="tabs">
        {TABS.map((t, i) => (
          <button key={t} type="button" className={i === tab ? 'on' : ''}
                  onClick={() => onTab(i as AssessmentId)}>
            {t}
          </button>
        ))}
      </div>

      {tab === 0 && (!row.quality ? <Missing what="Quality" /> : (
        <>
          <p className="bd-sum">
            Scored for its profile: <b>{row.quality.profile_label}</b>
          </p>
          {row.quality.categories.map(c => (
            <div key={c.key} className="cat">
              <div className="cat-h">
                {c.name}
                <span className="wt">{pctLabel(c.weight_pct)}</span>
                <span className="cs">{num(c.score, 1)} / 10</span>
              </div>
              <Table>
                {c.metrics.map(m => (
                  <tr key={m.label} className={m.excluded ? 'metric excluded' : 'metric'}>
                    <td>
                      {m.label}
                      {m.excluded && m.excluded_by &&
                        <span className="xn">{m.excluded_by}</span>}
                    </td>
                    <td>{raw(m.raw)}</td>
                    <td>{m.excluded ? '—' : `${num(m.score, 1)} / 10`}</td>
                    <td>{pctLabel(m.weight_pct)}</td>
                  </tr>
                ))}
              </Table>
            </div>
          ))}
        </>
      ))}

      {tab === 1 && (!row.moat ? <Missing what="Moat" /> : (
        <>
          <p className="bd-sum">
            Durability of economic profit — <b>{num(row.moat.score, 0)} / 100</b>
            {row.moat.gated && <span className="xn">Economic-profit gate applied</span>}
          </p>
          <Table>
            {row.moat.factors.map(f => (
              <tr key={f.label} className="metric">
                <td>{f.label}</td>
                <td>{`${num(f.points, 0)} / ${f.max_points}`}</td>
                <td>{num(f.points, 0)}</td>
                <td>{pctLabel(f.weight_pct)}</td>
              </tr>
            ))}
          </Table>
        </>
      ))}

      {tab === 2 && (!row.fair_value ? <Missing what="Fair Value" /> : (
        <>
          <p className="bd-sum">
            Valued as <b>{row.fair_value.type_label}</b> — blended fair value{' '}
            <b>{money(row.fair_value.value)}</b>
          </p>
          <table className="bt">
            <thead>
              <tr><th>Method</th><th>Value</th><th>Contribution</th><th>Weight</th></tr>
            </thead>
            <tbody>
              {row.fair_value.methods.map(m => (
                <tr key={m.label} className="metric">
                  <td>{m.label}</td>
                  <td>{money(m.value)}</td>
                  <td>{money(m.contribution)}</td>
                  <td>{pctLabel(m.weight_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ))}

      {tab === 3 && (!row.reward_risk ? <Missing what="Reward / Risk" /> : (
        <>
          <p className="bd-sum rr-pill">
            Reward ÷ Risk · range 0.2×–5.0× · higher is better —{' '}
            <b>{num(row.reward_risk.ratio, 1)}×</b> <span>{row.reward_risk.tier}</span>
          </p>
          <div className="cat">
            <div className="cat-h">
              Reward axis<span className="cs">{num(row.reward_risk.reward_score, 1)} / 5</span>
            </div>
            <Table>
              {row.reward_risk.reward.map(f => (
                <tr key={f.label} className={f.dropped ? 'metric excluded' : 'metric'}>
                  <td>{f.label}</td>
                  <td>{raw(f.raw)}</td>
                  <td>{`${num(f.score, 1)} / 5`}</td>
                  <td>{pctLabel(f.weight_pct)}</td>
                </tr>
              ))}
            </Table>
          </div>
          <div className="cat">
            <div className="cat-h">
              Risk axis · a high score here is the bad one
              <span className="cs">{num(row.reward_risk.risk_score, 1)} / 5</span>
            </div>
            <Table>
              {row.reward_risk.risk.map(f => (
                <tr key={f.label} className={f.dropped ? 'metric excluded' : 'metric'}>
                  <td>{f.label}</td>
                  <td>{raw(f.raw)}</td>
                  <td>{`${num(f.score, 1)} / 5`}</td>
                  <td>{pctLabel(f.weight_pct)}</td>
                </tr>
              ))}
            </Table>
          </div>
        </>
      ))}

      {row.calibrations.length > 0 && (
        <div className="cals">
          <span className="cals-h">Calibrations applied:</span>
          {row.calibrations.map(c => <span key={c} className="chip">{c}</span>)}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Run the tests and watch them pass**

Run: `cd frontend && npm test -- src/landing/components/Breakdown.test.tsx`
Expected: 10 passed.

- [ ] **Step 5: Wire it into the grid**

In `frontend/src/landing/LandingPage.tsx`, replace `renderBreakdown={() => null}` with:

```tsx
              renderBreakdown={r => (
                <Breakdown row={r} tab={assessment} onTab={setAssessment} />
              )}
```

and import `Breakdown from './components/Breakdown'`.

- [ ] **Step 6: Run the full frontend suite**

Run: `cd frontend && npm test`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/landing
git commit -m "feat(landing): factor-level breakdown panel for all four assessments"
```

---

## Task 11: The "How Intrinsica works" framework section

The overview card, four assessment cards, and a detail panel with identical shape for all four. Copy is content data, not markup, so the consistency requirement is structural.

**Files:**
- Create: `frontend/src/landing/content/framework.ts`
- Create: `frontend/src/landing/components/Framework.tsx`
- Modify: `frontend/src/landing/LandingPage.tsx`
- Test: `frontend/src/landing/content/framework.test.ts`
- Test: `frontend/src/landing/components/Framework.test.tsx`

**Interfaces:**
- Consumes: `AssessmentId` from `../types`.
- Produces:
  - `content/framework.ts`: `FRAMEWORK: AssessmentContent[]` and `CALIBRATIONS: Calibration[]`, where
    `AssessmentContent = { name, color, question, scale, what, hiLabel, loLabel, groups: { title, weight, metrics, hi, lo }[], note }`
    and `Calibration = { name, summary, when, effect, affects: string[], guarded: boolean, example?: string }`
  - `<Framework tab={AssessmentId} onTab={(id: AssessmentId) => void} />`

- [ ] **Step 1: Write the failing content test**

Create `frontend/src/landing/content/framework.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { FRAMEWORK, CALIBRATIONS } from './framework'

describe('framework content', () => {
  it('covers the four assessments in page order', () => {
    expect(FRAMEWORK.map(a => a.name)).toEqual(
      ['Quality', 'Moat', 'Fair Value', 'Reward / Risk'])
  })

  it('gives every assessment the same shape', () => {
    for (const a of FRAMEWORK) {
      expect(a.question).toBeTruthy()
      expect(a.scale).toBeTruthy()
      expect(a.what).toBeTruthy()
      expect(a.note).toBeTruthy()
      expect(a.groups.length).toBeGreaterThan(0)
      for (const g of a.groups) {
        expect(g.title).toBeTruthy()
        expect(g.weight).toBeTruthy()
        expect(g.metrics).toBeTruthy()
        expect(g.hi).toBeTruthy()
        expect(g.lo).toBeTruthy()
      }
    }
  })

  it('uses the scores-high / scores-low vocabulary', () => {
    expect(FRAMEWORK.map(a => a.hiLabel)).toEqual(
      ['Scores high', 'Scores high', 'Weighted up', 'Scores high'])
    expect(FRAMEWORK[2].loLabel).toBe('Weighted down')
  })

  it('never says signal, and never says Risk/Reward', () => {
    const text = JSON.stringify(FRAMEWORK) + JSON.stringify(CALIBRATIONS)
    expect(text).not.toMatch(/signal/i)
    expect(text).not.toMatch(/Risk\s*\/\s*Reward/)
  })

  it('names no moat source it cannot measure', () => {
    const moat = JSON.stringify(FRAMEWORK[1])
    expect(moat).not.toMatch(/network effect|switching cost|brand/i)
  })

  it('attaches every calibration to at least one assessment', () => {
    const names = new Set(FRAMEWORK.map(a => a.name))
    expect(CALIBRATIONS.length).toBeGreaterThan(0)
    for (const c of CALIBRATIONS) {
      expect(c.affects.length).toBeGreaterThan(0)
      for (const target of c.affects) expect(names.has(target)).toBe(true)
    }
  })
})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd frontend && npm test -- src/landing/content/framework.test.ts`
Expected: FAIL — cannot resolve `./framework`.

- [ ] **Step 3: Write the content**

Create `frontend/src/landing/content/framework.ts`. The copy below is final — it is the approved wording from the design mock. Weights and point maxima are public; scoring thresholds are not, so no band or cut-off appears in any string.

```ts
export interface AssessmentGroup {
  title: string
  weight: string
  metrics: string
  hi: string
  lo: string
}

export interface AssessmentContent {
  name: string
  color: string
  question: string
  scale: string
  what: string
  hiLabel: string
  loLabel: string
  groups: AssessmentGroup[]
  note: string
}

export interface Calibration {
  name: string
  summary: string
  when: string
  effect: string
  affects: string[]
  guarded: boolean
  example?: string
}

export const FRAMEWORK: AssessmentContent[] = [
  {
    name: 'Quality', color: 'var(--q)',
    question: 'How strong is the underlying business?',
    scale: '0–10 · sector-aware',
    what: 'A composite of the fundamentals that make a business good, weighted to the sector profile of the company.',
    hiLabel: 'Scores high', loLabel: 'Scores low',
    groups: [
      { title: 'Growth & Margins', weight: '35% of the score · 7 metrics',
        metrics: 'Revenue / EPS / FCF growth (3-yr) · operating & gross margin · margin trend · FCF margin',
        hi: 'revenue compounds and margins hold or widen while it does.',
        lo: 'growth stalls, or margins slide to pay for it.' },
      { title: 'Returns on Capital', weight: '30% of the score · 4 metrics',
        metrics: 'ROIC (trailing & 5-yr) · ROIC − WACC spread · return on tangible equity',
        hi: 'the business earns well above what its capital costs, year after year.',
        lo: 'returns merely match the cost of capital.' },
      { title: 'Balance-Sheet Strength', weight: '15% of the score · 3 metrics',
        metrics: 'Net debt / EBITDA · net debt / FCF · operating cash flow / capex',
        hi: 'little net debt, with cash flow covering capex several times over.',
        lo: 'leverage that depends on the cycle staying friendly.' },
      { title: 'Shareholder Alignment', weight: '20% of the score · 5 metrics',
        metrics: 'Share-count trend · stock comp % of revenue · earnings quality (FCF / net income) · insider ownership · shareholder yield',
        hi: 'a shrinking share count, modest stock comp, earnings that arrive as cash.',
        lo: 'steady dilution, or earnings that never become cash.' },
    ],
    note: 'Every metric is scored against fixed thresholds and averaged inside its category; the categories are then weighted by profile — Tech / Growth (shown), Balanced, Defensive / Income, Industrial / Cyclical, Financials, REIT. As a rough read: 9+ is top-decile, 8–9 excellent, 7–8 strong, below 5 weak.',
  },
  {
    name: 'Moat', color: 'var(--mo)',
    question: 'How durable are its competitive advantages?',
    scale: '0–100',
    what: 'Durability of economic profit — how consistently the business out-earns its cost of capital. Not a brand-narrative score.',
    hiLabel: 'Scores high', loLabel: 'Scores low',
    groups: [
      { title: 'Magnitude', weight: '40 of 100 points',
        metrics: 'ROIC level (up to 20 pts) · economic spread, ROIC − WACC (up to 20 pts)',
        hi: 'returns far above the cost of capital.',
        lo: 'returns that merely match it.' },
      { title: 'Durability', weight: '50 of 100 points',
        metrics: 'Persistence of economic profit (25 pts) · consistency of returns (10 pts) · margin durability (15 pts)',
        hi: 'a decade of above-cost returns, with margins that hold.',
        lo: 'a good couple of years inside a cyclical swing.' },
      { title: 'Cash-backing', weight: '10 of 100 points',
        metrics: 'Free-cash-flow conversion (10 pts)',
        hi: 'profit that turns into cash.',
        lo: 'profit that never leaves the income statement.' },
    ],
    note: 'Points add up to the 0–100 score: roughly 80+ reads as a wide moat, 60–79 established, 40–59 narrow, below 40 little or none. An economic-profit gate caps any company that does not out-earn its cost of capital.',
  },
  {
    name: 'Fair Value', color: 'var(--fv)',
    question: 'What is a share actually worth?',
    scale: '$ per share',
    what: 'An estimate of what one share is worth judged on the fundamentals of the business itself — its cash flows, earnings and assets — rather than on what the market happens to be paying today. Comparing that estimate with the live price is what tells you whether the stock looks cheap or expensive.',
    hiLabel: 'Weighted up', loLabel: 'Weighted down',
    groups: [
      { title: 'Cash-flow models', weight: 'typically 40–60% of the blend',
        metrics: 'Discounted cash flow · free cash flow to equity',
        hi: 'cash flows are established and predictable — the anchor for most profitable businesses.',
        lo: 'cash flows are erratic, or the company is pre-profit.' },
      { title: 'Earnings multiples', weight: 'typically 20–40%',
        metrics: 'EV / EBITDA · P / E (forward earnings when trailing ones are distorted)',
        hi: 'profits are meaningful and comparable across peers.',
        lo: 'earnings are negative, or distorted by acquisition amortization.' },
      { title: 'Sales multiples', weight: '0–20%',
        metrics: 'EV / Sales',
        hi: 'a fast-growing company is not earning yet.',
        lo: 'the company is mature and profitable.' },
      { title: 'Income & asset models', weight: '0–60%',
        metrics: 'Dividend discount · price / book · residual income · net asset value',
        hi: 'the company is a dividend payer, a lender or asset-heavy.',
        lo: 'the business is asset-light.' },
    ],
    note: 'The company is classified first, and the classification sets the blend — a mega cap leans on cash-flow models plus EV / EBITDA, a bank on price / book plus residual income, an asset-heavy name on net asset value. Every analysis shows the exact blend it used and what each method returned.',
  },
  {
    name: 'Reward / Risk', color: 'var(--rr)',
    question: 'Is the price today worth the downside?',
    scale: 'ratio · 0.2–5.0×',
    what: 'Connects intrinsic value to the live market price and the downside — a great business is not automatically a great investment at any price.',
    hiLabel: 'Scores high', loLabel: 'Scores low',
    groups: [
      { title: 'Reward axis', weight: '6 factors · scored 1–5',
        metrics: 'Discount to 52-week high (24%) · valuation (18%) · growth (18%) · RSI (16%) · profitability (12%) · analyst upside (8–18%, weighted by how many analysts agree)',
        hi: 'a growing, profitable business is trading well below its highs.',
        lo: 'the price is full, with little left to re-rate.' },
      { title: 'Risk axis · a high score here is the bad one', weight: '6 factors · scored 1–5',
        metrics: 'Volatility (22%) · leverage (18%) · trend vs 200-day (18%) · burn / margin (15%) · beta (15%) · liquidity (12%)',
        hi: 'leverage and volatility stack up.',
        lo: 'light debt, a steady price, a business that funds itself.' },
    ],
    note: 'Reward ÷ risk, clamped to 0.2–5.0×. Roughly: 2.0× and above is Asymmetric Upside, 1.3–2.0× Reward-Favored, 0.8–1.3× Balanced, 0.5–0.8× Risk-Favored, below that a Value Trap.',
  },
]

export const OVERVIEW = {
  lead: 'Four independent engines read the latest fundamentals and score the company live. They stay separate — no single blended rating — because whether a business is good and whether its price is fair are different questions. The calculations are explicit formulas rather than an AI opinion: the same company on the same data always returns the same result.',
  points: [
    { title: 'Scored for its sector.', body: 'Quality category weights shift with the company profile, so a software business is not judged by the standards of a REIT or a bank.' },
    { title: 'Valued for its type.', body: 'The company is classified first, and that decides which of nine valuation methods carry weight — cash-flow models for a mega cap, price / book and residual income for a lender, net asset value for an asset-heavy name.' },
    { title: 'Calibrated for distortions.', body: 'Data-triggered adjustments handle acquisition goodwill, amortization-depressed earnings, heavy capex, cyclicals and pre-profit growth. Every calibration that fires is named on the result, with the reason.' },
    { title: 'Built to run in parallel.', body: 'One ticker or a hundred are computed concurrently — the same engine behind a single lookup, a watchlist re-run and a screen across the universe.' },
  ],
  tail: 'Click any assessment below for its categories, weights and calibrations.',
}

export const CALIBRATIONS: Calibration[] = [
  { name: 'Tangible-ROIC (ex-goodwill)', summary: 'Capital efficiency without acquisition goodwill.',
    when: 'Only when goodwill & intangibles are a large share of invested capital, tangible ROIC is higher than reported, and trailing earnings are amortization-depressed.',
    effect: 'ROIC is scored on tangible invested capital, so a past acquisition is not misread as poor capital efficiency.',
    affects: ['Quality', 'Moat'], guarded: true, example: 'AMD after the Xilinx acquisition.' },
  { name: 'Forward-EPS swap', summary: 'Forward earnings when trailing EPS is depressed.',
    when: 'Only when trailing P/E runs far above forward P/E — trailing GAAP earnings depressed by amortization or a one-off trough.',
    effect: 'The P/E leg and the EPS-growth metric use forward (normalized) earnings.',
    affects: ['Fair Value', 'Quality'], guarded: true, example: 'AVGO after the VMware acquisition.' },
  { name: 'Heavy-capex FCF exclusion', summary: 'Ignores FCF metrics when capex is deliberately consuming cash.',
    when: 'Only when a profitable company’s trailing FCF is a tiny fraction of EBITDA due to heavy reinvestment.',
    effect: 'FCF-derived metrics are excluded; the balance sheet is judged on EBITDA leverage.',
    affects: ['Quality'], guarded: true, example: 'A hyperscaler during a data-centre build-out.' },
  { name: 'Financials basis', summary: 'Return-on-equity & book-value methods for lenders.',
    when: 'Automatically for banks, lenders and insurers.',
    effect: 'Moat uses ROTE vs cost of equity; Fair Value uses P/B + residual income; metrics that do not fit a lender are excluded.',
    affects: ['Quality', 'Moat', 'Fair Value'], guarded: false },
  { name: 'De-financialization', summary: 'Re-classifies miners & payment networks mis-tagged "Financial Services".',
    when: 'When a Financial-Services name is really a crypto miner, data-centre operator or asset-light payment network with no loan book.',
    effect: 'Book-value methods are dropped; the company is valued by the rules that fit it.',
    affects: ['Fair Value'], guarded: false },
  { name: 'Dominant fresh-acquisition', summary: 'Handles a just-closed deal that dominates the balance sheet.',
    when: 'When goodwill & intangibles are the overwhelming majority of invested capital right after a large acquisition.',
    effect: 'Amortization-depressed margin and mismatched leverage are excluded.',
    affects: ['Quality'], guarded: true, example: 'Synopsys after the Ansys deal.' },
  { name: 'Cyclical normalization', summary: 'Normalizes peak/trough earnings.',
    when: 'For cyclical sectors (energy, materials) or names that trade like cyclicals.',
    effect: 'Earnings are normalized across the cycle and confidence in the valuation is lowered.',
    affects: ['Fair Value', 'Reward / Risk'], guarded: false },
  { name: 'Economic-profit gate', summary: 'Caps the moat of businesses that do not beat their cost of capital.',
    when: 'When returns do not exceed cost of capital.',
    effect: 'The moat score is capped — no durable advantage without economic profit.',
    affects: ['Moat'], guarded: false },
  { name: 'Unprofitable cap & pre-profit path', summary: 'Growth + cash-runway scoring for pre-profit names, capped.',
    when: 'When net income or free cash flow is negative.',
    effect: 'Quality is capped and, for operating losses, blended with a Rule-of-40 + cash-runway read.',
    affects: ['Quality'], guarded: false },
  { name: 'Analyst-confidence weighting', summary: 'Weights the analyst-upside factor by coverage & agreement.',
    when: 'When a stock has analyst coverage.',
    effect: 'The analyst-upside factor counts for more when many analysts cover it and agree.',
    affects: ['Reward / Risk'], guarded: false },
  { name: 'Statement-corroboration guard', summary: 'Cross-checks growth and burn against annual statements.',
    when: 'For capex-heavy names where quarterly figures understate the annual reality.',
    effect: 'Growth & burn factors are overridden by the annual statement only when it reads materially better — never worse.',
    affects: ['Reward / Risk'], guarded: true },
]
```

- [ ] **Step 4: Run the content test and watch it pass**

Run: `cd frontend && npm test -- src/landing/content/framework.test.ts`
Expected: 6 passed.

- [ ] **Step 5: Write the failing component test**

Create `frontend/src/landing/components/Framework.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Framework from './Framework'

describe('Framework', () => {
  it('shows the overview highlights and the closing line', () => {
    render(<Framework tab={0} onTab={vi.fn()} />)
    expect(screen.getByText(/Scored for its sector\./)).toBeInTheDocument()
    expect(screen.getByText(/Built to run in parallel\./)).toBeInTheDocument()
    expect(screen.getByText(/Click any assessment below/)).toBeInTheDocument()
  })

  it('shows the selected assessment with its weights and scores-high pair', () => {
    render(<Framework tab={0} onTab={vi.fn()} />)
    expect(screen.getByText('35% of the score · 7 metrics')).toBeInTheDocument()
    expect(screen.getAllByText(/Scores high:/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Scores low:/).length).toBeGreaterThan(0)
  })

  it('switches assessment when a card is clicked', async () => {
    const onTab = vi.fn()
    render(<Framework tab={0} onTab={onTab} />)
    await userEvent.click(screen.getByRole('button', { name: /Fair Value/ }))
    expect(onTab).toHaveBeenCalledWith(2)
  })

  it('lists only the calibrations that touch the selected assessment', () => {
    render(<Framework tab={1} onTab={vi.fn()} />)
    expect(screen.getByText('Economic-profit gate')).toBeInTheDocument()
    expect(screen.queryByText('De-financialization')).not.toBeInTheDocument()
  })

  it('keeps calibration detail collapsed until asked', async () => {
    render(<Framework tab={1} onTab={vi.fn()} />)
    expect(screen.queryByText(/When it applies/)).not.toBeInTheDocument()
    await userEvent.click(screen.getByText('Economic-profit gate'))
    expect(screen.getByText(/When it applies/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 6: Run it and watch it fail**

Run: `cd frontend && npm test -- src/landing/components/Framework.test.tsx`
Expected: FAIL — cannot resolve `./Framework`.

- [ ] **Step 7: Write the component**

Create `frontend/src/landing/components/Framework.tsx`:

```tsx
import { useState } from 'react'
import { CALIBRATIONS, FRAMEWORK, OVERVIEW } from '../content/framework'
import type { AssessmentId } from '../types'

export default function Framework({ tab, onTab }: {
  tab: AssessmentId
  onTab: (id: AssessmentId) => void
}) {
  const [openCal, setOpenCal] = useState<string | null>(null)
  const a = FRAMEWORK[tab]
  const cals = CALIBRATIONS.filter(c => c.affects.includes(a.name))

  return (
    <section className="section stage" id="how">
      <div className="container">
        <div className="ovcard">
          <div className="kicker">The framework</div>
          <h2 className="stitle">How Intrinsica works</h2>
          <p className="ssub">{OVERVIEW.lead}</p>
          <div className="ovpts">
            {OVERVIEW.points.map(p => (
              <div key={p.title}><b>{p.title}</b> {p.body}</div>
            ))}
          </div>
          <p className="ovtail">{OVERVIEW.tail}</p>
        </div>

        <div className="mcards">
          {FRAMEWORK.map((x, i) => (
            <button key={x.name} type="button"
                    className={i === tab ? 'mcard on' : 'mcard'}
                    onClick={() => onTab(i as AssessmentId)}>
              <span className="cn">
                <span className="dot" style={{ background: x.color }} />{x.name}
              </span>
              <span className="cq">{x.question}</span>
              <span className="cs">{x.scale}</span>
            </button>
          ))}
        </div>

        <div className="mdetail">
          <div className="dh">
            <span className="dot" style={{ background: a.color }} />
            {a.name} <span className="scale">{a.scale}</span>
          </div>
          <p className="d-what">{a.what}</p>

          {a.groups.map(g => (
            <div key={g.title} className="grpblock">
              <div className="grp">{g.title}<span className="wt2">{g.weight}</span></div>
              <div className="gmetrics">{g.metrics}</div>
              <div className="gwhen"><b className="up">{a.hiLabel}:</b> {g.hi}</div>
              <div className="gwhen"><b className="dn">{a.loLabel}:</b> {g.lo}</div>
            </div>
          ))}

          <p className="note">{a.note}</p>

          <div className="cal-wrap">
            <div className="cal-title">
              ◆ Calibrations for {a.name} — data-triggered, click to see when
            </div>
            {cals.map(c => {
              const open = openCal === c.name
              return (
                <div key={c.name} className={open ? 'arow open' : 'arow'}>
                  <button type="button" className="ah"
                          onClick={() => setOpenCal(open ? null : c.name)}>
                    <span className="nm">{c.name}</span>
                    <span className="sm">{c.summary}</span>
                  </button>
                  {open && (
                    <div className="ab">
                      <div className="kv"><div className="k when">◆ When it applies</div>
                        <p>{c.when}</p></div>
                      <div className="kv"><div className="k">What it does</div>
                        <p>{c.effect}</p></div>
                      {c.example && <div className="ex"><b>Example:</b> {c.example}</div>}
                      <div className="tags">
                        <span className="tg cond" title="Not always on — this calibration fires only when the company's data matches a specific pattern.">Conditional</span>
                        {c.guarded && <span className="tg guard" title="Guarded: it can only ever correct a distortion — never inflate a score.">Guarded</span>}
                        <span className="tg live" title="Whether it fired for a given stock is shown on that stock's result.">Shown live</span>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 8: Run the component test and watch it pass**

Run: `cd frontend && npm test -- src/landing/components/Framework.test.tsx`
Expected: 5 passed.

- [ ] **Step 9: Mount it and fire the methodology event**

In `frontend/src/landing/LandingPage.tsx`, add below the result section:

```tsx
        <Framework
          tab={assessment}
          onTab={id => {
            setAssessment(id)
            track(EVENTS.methodologyViewed, { assessment: FRAMEWORK[id].name })
          }}
        />
```

Import `Framework from './components/Framework'` and `{ FRAMEWORK } from './content/framework'`, and add `methodologyViewed: 'methodology_viewed'` to the analytics mock in `LandingPage.test.tsx`.

Because the hero's assessment click also sets `assessment`, add a test to `LandingPage.test.tsx` proving the jump works end to end:

```tsx
  it('selects the clicked hero assessment in the methodology section', async () => {
    renderPage()
    await userEvent.click(screen.getByRole('button', { name: /Moat/ }))
    expect(screen.getByText('How durable are its competitive advantages?')).toBeInTheDocument()
    expect(screen.getByText('40 of 100 points')).toBeInTheDocument()
  })
```

- [ ] **Step 10: Run the full frontend suite**

Run: `cd frontend && npm test`
Expected: all pass.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/landing
git commit -m "feat(landing): framework section with consistent assessment detail"
```

---

## Task 12: Why Intrinsica and the workflow

**Files:**
- Create: `frontend/src/landing/components/Why.tsx`
- Create: `frontend/src/landing/components/Workflow.tsx`
- Modify: `frontend/src/landing/LandingPage.tsx`
- Test: `frontend/src/landing/components/WhyWorkflow.test.tsx`

**Interfaces:**
- Consumes: nothing beyond React.
- Produces: `<Why />` and `<Workflow />` — both content-only, no props.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/landing/components/WhyWorkflow.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import Why from './Why'
import Workflow from './Workflow'

describe('Why Intrinsica', () => {
  it('explains why the four assessments must be read together', () => {
    const { container } = render(<Why />)
    expect(container.textContent).toMatch(/read together/i)
    expect(container.textContent).toMatch(/wrong price/i)
  })

  it('shows both labelled rows', () => {
    render(<Why />)
    expect(screen.getByText('Trust the analysis')).toBeInTheDocument()
    expect(screen.getByText('Put it to work at scale')).toBeInTheDocument()
  })

  it('carries no plan pill on the scale row', () => {
    const { container } = render(<Why />)
    expect(container.querySelector('.why-row .pill')).toBeNull()
    expect(container.textContent).not.toMatch(/\bUnlimited\b\s*$/m)
  })
})

describe('Workflow', () => {
  it('has four steps ending at monitor and automate', () => {
    render(<Workflow />)
    const steps = screen.getAllByText(/^STEP \d$/)
    expect(steps).toHaveLength(4)
    expect(screen.getByText('Analyze or discover')).toBeInTheDocument()
    expect(screen.getByText('Monitor & automate')).toBeInTheDocument()
  })

  it('does not present Discover as its own step', () => {
    const { container } = render(<Workflow />)
    expect(container.textContent).not.toMatch(/STEP 5/)
    expect(screen.queryByText('Discover')).not.toBeInTheDocument()
  })

  it('shows no per-tier limit strip', () => {
    const { container } = render(<Workflow />)
    expect(container.querySelector('.tiers')).toBeNull()
    expect(container.textContent).not.toMatch(/feeds back into Analyze/)
  })
})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd frontend && npm test -- src/landing/components/WhyWorkflow.test.tsx`
Expected: FAIL — cannot resolve `./Why`.

- [ ] **Step 3: Write `Why.tsx`**

```tsx
const TRUST = [
  { icon: '⚙️', title: 'Deterministic & reproducible',
    body: 'Explicit formulas and calibrated thresholds — not an LLM opinion. Same inputs, same output, every time.' },
  { icon: '🔍', title: 'Transparent to the last detail',
    body: 'Every weight, driver, valuation method and calibration is shown — nothing hidden behind a single rating.' },
  { icon: '🛠️', title: 'Calibrated for real companies',
    body: 'Handles acquisition goodwill, cyclicals, heavy capex, banks and pre-profit growth — each rule verified against real cases.' },
]

const SCALE = [
  { icon: '⚡', title: 'Re-evaluate whole watchlists',
    body: 'Run 25, 50 or 100+ stocks in parallel — every holding re-scored on fresh fundamentals in seconds.' },
  { icon: '🧭', title: 'Discover what fits your criteria',
    body: 'Screen hundreds of stocks by Quality, Moat, Fair Value and Reward/Risk — e.g. “Moat ≥ 80 and trading below fair value”.' },
  { icon: '🔔', title: 'Automated monitoring',
    body: 'Intrinsica re-checks your universe on a schedule and flags “What changed?” when an assessment crosses your threshold.' },
]

function Row({ label, cards }: { label: string; cards: typeof TRUST }) {
  return (
    <div className="why-row">
      <div className="why-lbl">{label}</div>
      <div className="diff-grid">
        {cards.map(c => (
          <div key={c.title} className="diff">
            <div className="ic">{c.icon}</div>
            <h4>{c.title}</h4>
            <p>{c.body}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Why() {
  return (
    <section className="section" id="why">
      <div className="container">
        <div className="kicker">Why Intrinsica</div>
        <h2 className="stitle">A rigorous engine — built to work at scale.</h2>
        <p className="ssub">
          Four questions decide most of the outcome of an investment: is the business any
          good (<b>Quality</b>), can it stay good (<b>Moat</b>), what is a share actually
          worth (<b>Fair Value</b>), and is today's price worth the downside
          (<b>Reward/Risk</b>). A good business bought at the wrong price is still a bad
          investment, and a cheap price means nothing if the business is eroding — which is
          why all four have to be read together.
        </p>
        <p className="ssub">
          Answering them properly means hours of statement work per company. Intrinsica
          computes all four from the fundamentals in seconds, the same way every time — and
          repeats it across your whole watchlist, or the market.
        </p>
        <Row label="Trust the analysis" cards={TRUST} />
        <Row label="Put it to work at scale" cards={SCALE} />
      </div>
    </section>
  )
}
```

- [ ] **Step 4: Write `Workflow.tsx`**

```tsx
const STEPS = [
  { title: 'Analyze or discover',
    body: 'Start from tickers you already follow — or find new ones by screening the universe on the four assessments. Either way you get the full breakdown.' },
  { title: 'Compare', body: 'Rank stocks side by side, computed in parallel.' },
  { title: 'Watch & re-evaluate',
    body: 'Save watchlists and re-score them in one bulk, parallel run.' },
  { title: 'Monitor & automate',
    body: 'Scheduled re-checks, alerts and “What changed?” when scores move.' },
]

export default function Workflow() {
  return (
    <section className="section stage" id="workflow">
      <div className="container">
        <div className="kicker">The workflow</div>
        <h2 className="stitle">Analyze → Compare → Watch → Monitor</h2>
        <p className="ssub">
          A recurring research loop, not a one-off “what's it worth?” lookup. Every step
          uses the same full-depth analysis; plans differ in how much you can do and how
          much runs automatically.
        </p>
        <div className="workflow">
          {STEPS.map((s, i) => (
            <div key={s.title} className="wf">
              <div className="step">{`STEP ${i + 1}`}</div>
              <h4>{s.title}</h4>
              <p>{s.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 5: Run the tests and watch them pass**

Run: `cd frontend && npm test -- src/landing/components/WhyWorkflow.test.tsx`
Expected: 6 passed.

- [ ] **Step 6: Mount both sections**

In `LandingPage.tsx`, after `<Framework ... />`:

```tsx
        <Why />
        <Workflow />
```

with the matching imports.

- [ ] **Step 7: Run the full frontend suite and commit**

Run: `cd frontend && npm test`

```bash
git add frontend/src/landing
git commit -m "feat(landing): why-Intrinsica and four-step workflow sections"
```

---

## Task 13: Pricing cards and the compare matrix

**Files:**
- Create: `frontend/src/landing/content/plans.ts`
- Create: `frontend/src/landing/components/Pricing.tsx`
- Modify: `frontend/src/landing/LandingPage.tsx`
- Test: `frontend/src/landing/content/plans.test.ts`
- Test: `frontend/src/landing/components/Pricing.test.tsx`

**Interfaces:**
- Consumes: `track`, `EVENTS`.
- Produces:
  - `content/plans.ts`: `PLANS: Plan[]`, `COMPARE_ROWS: CompareRow[]`, `type Billing = 'annual' | 'monthly'`, `priceFor(plan: Plan, billing: Billing): { headline: string; sub: string }`, `totalFor(planName: string, billing: Billing): string`
  - `<Pricing billing={Billing} onBilling={(b: Billing) => void} onChoose={(plan: string, billing: Billing) => void} onView={() => void} />` — `onView` fires once, when the section scrolls into view

- [ ] **Step 1: Write the failing content test**

Create `frontend/src/landing/content/plans.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { PLANS, COMPARE_ROWS, priceFor, totalFor } from './plans'

describe('plans', () => {
  it('offers exactly Free, Pro and Unlimited, with Pro featured', () => {
    expect(PLANS.map(p => p.name)).toEqual(['Free', 'Pro', 'Unlimited'])
    expect(PLANS.filter(p => p.featured).map(p => p.name)).toEqual(['Pro'])
  })

  it('shows the effective monthly price on annual billing', () => {
    const pro = PLANS[1]
    expect(priceFor(pro, 'annual').headline).toBe('$18.00')
    expect(priceFor(pro, 'annual').sub).toBe('billed annually · $216/yr · save 18%')
    expect(priceFor(pro, 'monthly').headline).toBe('$21.99')
  })

  it('prices Unlimited at $25 effective and $29.99 monthly', () => {
    const unlimited = PLANS[2]
    expect(priceFor(unlimited, 'annual').headline).toBe('$25.00')
    expect(priceFor(unlimited, 'annual').sub).toBe('billed annually · $300/yr · save 17%')
    expect(priceFor(unlimited, 'monthly').headline).toBe('$29.99')
  })

  it('states the checkout total per plan and billing period', () => {
    expect(totalFor('Pro', 'annual')).toBe('$216 / year ($18.00/mo)')
    expect(totalFor('Pro', 'monthly')).toBe('$21.99 / month')
    expect(totalFor('Unlimited', 'annual')).toBe('$300 / year ($25.00/mo)')
    expect(totalFor('Free', 'annual')).toBe('$0 — free plan')
  })

  it('carries all seventeen compare rows with the split compare feature', () => {
    expect(COMPARE_ROWS).toHaveLength(17)
    const labels = COMPARE_ROWS.map(r => r.label)
    expect(labels).toContain('Tickers per analysis run')
    expect(labels).toContain('Side-by-side breakdown')
    const sbs = COMPARE_ROWS.find(r => r.label === 'Side-by-side breakdown')!
    expect(sbs.values).toEqual(['—', 'Up to 3', 'Up to 3'])
  })

  it('caps the Free tier the way the spec does', () => {
    const byLabel = (l: string) => COMPARE_ROWS.find(r => r.label === l)!.values[0]
    expect(byLabel('Analyses per month')).toBe('~5')
    expect(byLabel('Tickers per analysis run')).toBe('3')
    expect(byLabel('Watchlists')).toBe('1')
    expect(byLabel('Stocks per watchlist')).toBe('5')
    expect(byLabel('Score history')).toBe('6 months')
    expect(byLabel('Score-history charts')).toBe('6 months')
  })

  it('never calls Free the full product', () => {
    const free = PLANS[0]
    expect(free.forLine).toBe('Full-depth analysis, small volume.')
    expect(JSON.stringify(free)).not.toMatch(/full product/i)
  })
})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd frontend && npm test -- src/landing/content/plans.test.ts`
Expected: FAIL — cannot resolve `./plans`.

- [ ] **Step 3: Write the plan content**

Create `frontend/src/landing/content/plans.ts`:

```ts
export type Billing = 'annual' | 'monthly'

export interface Plan {
  name: 'Free' | 'Pro' | 'Unlimited'
  title: string
  forLine: string
  featured?: boolean
  cta: string
  annual?: { effective: string; sub: string }
  monthly?: { effective: string; sub: string }
  features: string[]
}

export interface CompareRow {
  label: string
  note?: string
  values: [string, string, string]
}

export const PLANS: Plan[] = [
  {
    name: 'Free', title: 'Try Intrinsica',
    forLine: 'Full-depth analysis, small volume.',
    cta: 'Start free',
    features: [
      '~5 full-depth analyses / month',
      'Every analysis complete — Quality, Moat, Fair Value & Reward/Risk with the full breakdown, nothing blurred',
      'Up to 3 tickers per analysis run',
      '1 watchlist, up to 5 stocks',
      '6 months of score history (2 quarters)',
      'Discovery: see the filters, results locked',
    ],
  },
  {
    name: 'Pro', title: 'Deep Stock Analysis',
    forLine: 'Unlimited analysis & your research workflow.',
    featured: true, cta: 'Choose Pro',
    annual: { effective: '$18.00', sub: 'billed annually · $216/yr · save 18%' },
    monthly: { effective: '$21.99', sub: 'billed monthly · $21.99/mo' },
    features: [
      'Everything in Free (same full depth), plus:',
      'Unlimited analyses — no monthly cap',
      'Up to 10 tickers per analysis run · side-by-side breakdown of 3',
      '5–10 watchlists of 50 stocks · ~2 years of score history & charts',
      'Score-change alerts (10–20) · CSV / PDF export · basic portfolio analysis',
    ],
  },
  {
    name: 'Unlimited', title: 'Discover, Monitor & Automate at Scale',
    forLine: 'Automated, systematic research across your universe.',
    cta: 'Choose Unlimited',
    annual: { effective: '$25.00', sub: 'billed annually · $300/yr · save 17%' },
    monthly: { effective: '$29.99', sub: 'billed monthly · $29.99/mo' },
    features: [
      'Everything in Pro, plus:',
      'Bulk / parallel analysis — 25, 50, 100+ tickers in one run',
      'Screen on Quality/Moat/FV/Reward-Risk across hundreds of stocks',
      'Unlimited watchlists · advanced portfolio analysis',
      'Full score-history evolution & “What Changed?”',
      'Automated monitoring · unlimited alerts · bulk exports',
    ],
  },
]

export function priceFor(plan: Plan, billing: Billing): { headline: string; sub: string } {
  if (plan.name === 'Free') return { headline: '$0', sub: 'No card, ever' }
  const band = billing === 'annual' ? plan.annual! : plan.monthly!
  return { headline: band.effective, sub: band.sub }
}

export function totalFor(planName: string, billing: Billing): string {
  if (planName === 'Free') return '$0 — free plan'
  if (planName === 'Pro') {
    return billing === 'annual' ? '$216 / year ($18.00/mo)' : '$21.99 / month'
  }
  return billing === 'annual' ? '$300 / year ($25.00/mo)' : '$29.99 / month'
}

export const COMPARE_ROWS: CompareRow[] = [
  { label: 'Full-depth analysis (Quality · Moat · Fair Value · Reward/Risk)',
    values: ['Full', 'Full', 'Full'] },
  { label: 'Breakdown, methodology & calibrations', values: ['Full', 'Full', 'Full'] },
  { label: 'Analyses per month', values: ['~5', 'Unlimited', 'Unlimited'] },
  { label: 'Tickers per analysis run',
    note: 'They come back in one results grid, ranked side by side',
    values: ['3', '10', '100+ (bulk)'] },
  { label: 'Side-by-side breakdown',
    note: 'Full factor tables of 3 companies in one view',
    values: ['—', 'Up to 3', 'Up to 3'] },
  { label: 'Watchlists', values: ['1', '5–10', 'Unlimited'] },
  { label: 'Stocks per watchlist', values: ['5', '50', 'Unlimited'] },
  { label: 'Portfolio analysis', values: ['—', 'Basic', 'Advanced'] },
  { label: 'Score history', values: ['6 months', '~2 years', 'Full history'] },
  { label: 'Score-history charts', values: ['6 months', 'Yes', 'Advanced'] },
  { label: 'Bulk / parallel analysis', values: ['—', '—', 'Yes'] },
  { label: 'Discovery — screen on Quality/Moat/FV/Reward-Risk',
    note: 'Preview = the filters are visible, running them is locked',
    values: ['Preview', 'Preview', 'Full'] },
  { label: 'Full stock universe', values: ['Preview', 'Preview', 'Yes'] },
  { label: 'Score-change alerts',
    note: 'You are told when a score crosses a threshold you set',
    values: ['—', '10–20', 'Unlimited'] },
  { label: 'Automated monitoring',
    note: 'Intrinsica re-runs your watchlists on a schedule, unprompted',
    values: ['—', '—', 'Yes'] },
  { label: '“What Changed?”',
    note: 'Which factor moved a score, this run versus the last',
    values: ['—', '—', 'Yes'] },
  { label: 'Exports', values: ['—', 'CSV / PDF', 'Bulk'] },
]
```

- [ ] **Step 4: Run the content test and watch it pass**

Run: `cd frontend && npm test -- src/landing/content/plans.test.ts`
Expected: 7 passed.

- [ ] **Step 5: Write the failing component test**

Create `frontend/src/landing/components/Pricing.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Pricing from './Pricing'

const show = (billing: 'annual' | 'monthly' = 'annual', onChoose = vi.fn(),
              onBilling = vi.fn()) => {
  render(<Pricing billing={billing} onBilling={onBilling} onChoose={onChoose} />)
  return { onChoose, onBilling }
}

describe('Pricing', () => {
  it('shows the annual effective prices by default', () => {
    show()
    expect(screen.getByText('$18.00')).toBeInTheDocument()
    expect(screen.getByText('$25.00')).toBeInTheDocument()
  })

  it('switches to monthly prices', () => {
    show('monthly')
    expect(screen.getByText('$21.99')).toBeInTheDocument()
    expect(screen.getByText('$29.99')).toBeInTheDocument()
  })

  it('reports the chosen plan and billing period', async () => {
    const { onChoose } = show('annual')
    await userEvent.click(screen.getByRole('button', { name: 'Choose Pro' }))
    expect(onChoose).toHaveBeenCalledWith('Pro', 'annual')
  })

  it('routes Free through the same chooser', async () => {
    const { onChoose } = show()
    await userEvent.click(screen.getByRole('button', { name: 'Start free' }))
    expect(onChoose).toHaveBeenCalledWith('Free', 'annual')
  })

  it('renders the whole compare matrix', () => {
    show()
    expect(screen.getByText('Stocks per watchlist')).toBeInTheDocument()
    expect(screen.getByText(/Preview = the filters are visible/)).toBeInTheDocument()
    expect(screen.getByText(/Free sells the framework/)).toBeInTheDocument()
  })

  it('exposes no card or payment field', () => {
    const { container } = render(
      <Pricing billing="annual" onBilling={vi.fn()} onChoose={vi.fn()} />)
    expect(container.querySelectorAll('input[type="password"]').length).toBe(0)
    expect(container.textContent).not.toMatch(/card number|cvc|expiry/i)
  })

  it('reports the section as viewed once it scrolls into view', () => {
    const observers: ((entries: { isIntersecting: boolean }[]) => void)[] = []
    vi.stubGlobal('IntersectionObserver', class {
      constructor(cb: (entries: { isIntersecting: boolean }[]) => void) {
        observers.push(cb)
      }
      observe() {}
      disconnect() {}
    })
    const onView = vi.fn()
    render(<Pricing billing="annual" onBilling={vi.fn()} onChoose={vi.fn()}
                    onView={onView} />)
    expect(onView).not.toHaveBeenCalled()

    observers[0]([{ isIntersecting: true }])
    observers[0]([{ isIntersecting: true }])
    expect(onView).toHaveBeenCalledTimes(1)
  })

  it('does not break where IntersectionObserver is unavailable', () => {
    vi.stubGlobal('IntersectionObserver', undefined)
    expect(() => render(
      <Pricing billing="annual" onBilling={vi.fn()} onChoose={vi.fn()}
               onView={vi.fn()} />)).not.toThrow()
  })
})
```

- [ ] **Step 6: Run it and watch it fail**

Run: `cd frontend && npm test -- src/landing/components/Pricing.test.tsx`
Expected: FAIL — cannot resolve `./Pricing`.

- [ ] **Step 7: Write the component**

Create `frontend/src/landing/components/Pricing.tsx`:

```tsx
import { useEffect, useRef } from 'react'
import { COMPARE_ROWS, PLANS, priceFor, type Billing } from '../content/plans'

const WHO = [
  { tag: 'Free · Try', title: 'Experience the framework',
    who: 'For the curious investor judging the framework on stocks they already know.',
    focus: 'every analysis is complete and nothing is blurred — but volume, watchlists, history and discovery are capped.' },
  { tag: 'Pro · Depth', title: 'Deep individual research',
    who: 'For the serious individual investor researching the stocks they care about.',
    focus: 'unlimited analysis on the names you pick, plus your research workflow.' },
  { tag: 'Unlimited · Scale', title: 'Systematic & automated',
    who: 'For investors scanning & monitoring a whole universe or portfolio.',
    focus: 'discover across the market and let Intrinsica monitor it for you.' },
]

export default function Pricing({ billing, onBilling, onChoose, onView }: {
  billing: Billing
  onBilling: (b: Billing) => void
  onChoose: (plan: string, billing: Billing) => void
  onView?: () => void
}) {
  const section = useRef<HTMLElement | null>(null)
  const reported = useRef(false)

  // "Viewed" means scrolled to, not merely mounted — the pricing section renders with
  // the page. Where IntersectionObserver is unavailable the event is simply skipped;
  // analytics is never load-bearing.
  useEffect(() => {
    if (!onView || typeof IntersectionObserver !== 'function' || !section.current) return
    const io = new IntersectionObserver(entries => {
      if (entries.some(e => e.isIntersecting) && !reported.current) {
        reported.current = true
        onView()
      }
    })
    io.observe(section.current)
    return () => io.disconnect()
  }, [onView])

  return (
    <section className="section" id="pricing" ref={section}>
      <div className="container">
        <div className="kicker">Pricing</div>
        <h2 className="stitle">Choose your plan</h2>
        <p className="ssub">
          Every plan gets the same full-depth analysis. Upgrade to Pro for unlimited
          analysis — or Unlimited to discover, monitor & automate at scale.
        </p>

        <div className="billing-toggle">
          <button type="button" className={billing === 'annual' ? 'on' : ''}
                  onClick={() => onBilling('annual')}>
            Annual <span className="save">save ~17%</span>
          </button>
          <button type="button" className={billing === 'monthly' ? 'on' : ''}
                  onClick={() => onBilling('monthly')}>
            Monthly
          </button>
        </div>

        <div className="price-grid">
          {PLANS.map(p => {
            const price = priceFor(p, billing)
            return (
              <div key={p.name} className={p.featured ? 'price-card featured' : 'price-card'}>
                <div className={p.name === 'Free' ? 'pc-badge free' : 'pc-badge'}>{p.name}</div>
                <h3>{p.title}</h3>
                <div className="pc-for">{p.forLine}</div>
                <div className="price">{price.headline}<span className="per">/mo</span></div>
                <div className="price-alt">{price.sub}</div>
                <ul className="feature-list">
                  {p.features.map(f => <li key={f}>{f}</li>)}
                </ul>
                <button type="button" className="btn-plan"
                        onClick={() => onChoose(p.name, billing)}>
                  {p.cta}
                </button>
              </div>
            )
          })}
        </div>

        <div className="compare">
          <h3 className="compare-h">Compare plans</h3>
          <p className="compare-sub">
            The same deep analysis in every tier — you unlock more <b>volume</b>, then{' '}
            <b>scale & automation</b>.
          </p>
          <div className="who">
            {WHO.map(w => (
              <div key={w.tag} className="who-card">
                <div className="wtag">{w.tag}</div>
                <div className="wt">{w.title}</div>
                <div className="wfor">{w.who}</div>
                <div className="wfocus"><b>Focus:</b> {w.focus}</div>
              </div>
            ))}
          </div>
          <div className="cmp-wrap">
            <table className="cmp-plans">
              <thead>
                <tr><th>Feature</th><th>Free</th><th>Pro</th><th className="u">Unlimited</th></tr>
              </thead>
              <tbody>
                {COMPARE_ROWS.map(r => (
                  <tr key={r.label}>
                    <td>
                      {r.label}
                      {r.note && <span className="sub">{r.note}</span>}
                    </td>
                    {r.values.map((v, i) => (
                      <td key={i} className={v === '—' ? 'no' : undefined}>{v}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="compare-note">
            Free sells the framework · Pro sells depth & unlimited use · Unlimited sells
            scale, discovery & automation.
          </p>
        </div>
      </div>
    </section>
  )
}
```

- [ ] **Step 8: Run the component test and watch it pass**

Run: `cd frontend && npm test -- src/landing/components/Pricing.test.tsx`
Expected: 8 passed.

- [ ] **Step 9: Mount it, with the plan-selection events**

In `LandingPage.tsx`:

```tsx
  const navigate = useNavigate()
  const [billing, setBilling] = useState<Billing>('annual')

  const choosePlan = useCallback((plan: string, b: Billing) => {
    // A free click is its own event and is never part of paid-intent conversion.
    track(plan === 'Free' ? EVENTS.freePlanClicked : EVENTS.planSelected,
          { plan, billing: b })
    navigate(`/checkout?plan=${encodeURIComponent(plan)}&billing=${b}`)
  }, [navigate])
```

Render it after `<Workflow />`:

```tsx
        <Pricing
          billing={billing}
          onBilling={setBilling}
          onChoose={choosePlan}
          onView={() => track(EVENTS.pricingViewed)}
        />
```

Import `useNavigate` from `react-router-dom`, `Pricing`, and `type Billing` from `./content/plans`. Add `planSelected`, `freePlanClicked` and `pricingViewed` to the analytics mock in `LandingPage.test.tsx`.

- [ ] **Step 10: Run the full frontend suite and commit**

Run: `cd frontend && npm test`

```bash
git add frontend/src/landing
git commit -m "feat(landing): pricing cards and the plan comparison matrix"
```

---

## Task 14: The checkout page and the honest disclosure

**Files:**
- Create: `frontend/src/landing/CheckoutPage.tsx`
- Modify: `frontend/src/App.tsx` (add `/checkout`)
- Test: `frontend/src/landing/CheckoutPage.test.tsx`

**Interfaces:**
- Consumes: `totalFor`, `type Billing` from `./content/plans`; `track`, `EVENTS`; `useSearchParams` from react-router.
- Produces: `<CheckoutPage />` at `/checkout?plan=Pro&billing=annual`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/landing/CheckoutPage.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import CheckoutPage from './CheckoutPage'

vi.mock('../lib/analytics', () => ({
  track: vi.fn(),
  visitorId: () => 'v-test',
  EVENTS: {
    checkoutStarted: 'checkout_started',
    paymentButtonClicked: 'payment_button_clicked',
    emailSubmitted: 'email_submitted',
  },
}))

function show(query = '?plan=Pro&billing=annual') {
  return render(
    <MemoryRouter initialEntries={[`/checkout${query}`]}>
      <CheckoutPage />
    </MemoryRouter>,
  )
}

beforeEach(() => vi.clearAllMocks())

describe('CheckoutPage', () => {
  it('summarises the chosen plan, billing and total', () => {
    show()
    expect(screen.getByText('Pro')).toBeInTheDocument()
    expect(screen.getByText('Annual')).toBeInTheDocument()
    expect(screen.getByText('$216 / year ($18.00/mo)')).toBeInTheDocument()
  })

  it('labels the paid button Proceed to payment', () => {
    show()
    expect(screen.getByRole('button', { name: 'Proceed to payment' })).toBeInTheDocument()
  })

  it('has no card, address or name field anywhere', () => {
    const { container } = show()
    const inputs = Array.from(container.querySelectorAll('input'))
    expect(inputs).toHaveLength(1)
    expect(inputs[0]).toHaveAttribute('type', 'email')
    expect(container.textContent).not.toMatch(/card number|cvc|cvv|expiry|billing address/i)
  })

  it('hides the no-card fine print until after the click', async () => {
    show()
    expect(screen.queryByText(/you won't be charged/i)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Proceed to payment' }))
    expect(screen.getByText(/you won't be charged/i)).toBeInTheDocument()
  })

  it('discloses honestly and records the click', async () => {
    const { track } = await import('../lib/analytics')
    show()
    await userEvent.click(screen.getByRole('button', { name: 'Proceed to payment' }))
    expect(screen.getByText(/founding list/i)).toBeInTheDocument()
    expect(screen.getByText(/no payment was taken/i)).toBeInTheDocument()
    expect(track).toHaveBeenCalledWith('payment_button_clicked',
                                       { plan: 'Pro', billing: 'annual' })
  })

  it('words the free path as an invite and creates no account', async () => {
    show('?plan=Free&billing=annual')
    expect(screen.getByRole('button', { name: 'Create free account' })).toBeInTheDocument()
    expect(screen.getByText('$0 — free plan')).toBeInTheDocument()
    expect(screen.getByText('No billing')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Create free account' }))
    expect(screen.getByText(/no account was created/i)).toBeInTheDocument()
  })

  it('keeps the email optional', async () => {
    show()
    await userEvent.click(screen.getByRole('button', { name: 'Proceed to payment' }))
    expect(screen.getByText(/Optional/i)).toBeInTheDocument()
    expect(screen.getByRole('textbox')).not.toBeRequired()
  })

  it('records the checkout view once on arrival', async () => {
    const { track } = await import('../lib/analytics')
    show()
    expect(track).toHaveBeenCalledWith('checkout_started',
                                       { plan: 'Pro', billing: 'annual' })
  })

  it('offers a way back to pricing', () => {
    show()
    expect(screen.getByRole('link', { name: /Back to pricing/ }))
      .toHaveAttribute('href', '/#pricing')
  })
})
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd frontend && npm test -- src/landing/CheckoutPage.test.tsx`
Expected: FAIL — cannot resolve `./CheckoutPage`.

- [ ] **Step 3: Write the page**

Create `frontend/src/landing/CheckoutPage.tsx`:

```tsx
import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import './theme.css'
import { totalFor, type Billing } from './content/plans'
import { track, EVENTS } from '../lib/analytics'

export default function CheckoutPage() {
  const [params] = useSearchParams()
  const plan = params.get('plan') ?? 'Pro'
  const billing = (params.get('billing') === 'monthly' ? 'monthly' : 'annual') as Billing
  const free = plan === 'Free'

  const [clicked, setClicked] = useState(false)
  const [email, setEmail] = useState('')

  useEffect(() => {
    track(EVENTS.checkoutStarted, { plan, billing })
  }, [plan, billing])

  function proceed() {
    // The whole measurement: reaching and pressing this button. Nothing is charged
    // and no card was ever requested.
    track(free ? EVENTS.freePlanClicked : EVENTS.paymentButtonClicked, { plan, billing })
    setClicked(true)
  }

  return (
    <div className="intrinsica">
      <nav className="nav">
        <div className="nav-in">
          <div className="logo">Intrinsica</div>
          <div className="links"><a href="/#pricing">← Back to pricing</a></div>
        </div>
      </nav>

      <section className="section stage" id="checkout">
        <div className="container">
          <div className="kicker">Checkout</div>
          <h2 className="stitle">{free ? 'Create your free account' : 'Confirm your plan'}</h2>

          <div className="checkout">
            <div className="co-line"><span className="lab">Plan</span>
              <span className="val">{plan}</span></div>
            <div className="co-line"><span className="lab">Billing</span>
              <span className="val">
                {free ? 'No billing' : billing === 'annual' ? 'Annual' : 'Monthly'}
              </span></div>
            <div className="co-total"><span>Total</span>
              <span className="val">{totalFor(plan, billing)}</span></div>

            <button type="button" className="btn-buy" onClick={proceed}>
              {free ? 'Create free account' : 'Proceed to payment'}
            </button>

            {clicked && (
              <>
                <div className="disclosure show">
                  <h4>
                    {free
                      ? "✓ You're on the Intrinsica early-access list"
                      : "✓ You're on the Intrinsica founding list"}
                  </h4>
                  <p>
                    {free ? (
                      <>
                        Accounts aren't open yet, so <b>no account was created</b>. We've
                        recorded your interest in <b>the Free plan</b> and will invite you
                        when early access opens. In the meantime the demo stays open — up
                        to 3 tickers per run, no account needed.
                      </>
                    ) : (
                      <>
                        Intrinsica isn't commercially available yet, so{' '}
                        <b>no payment was taken</b>. We've recorded your request for{' '}
                        <b>{plan} — {billing === 'annual' ? 'Annual' : 'Monthly'}</b> and
                        will contact you when early access opens.
                      </>
                    )}
                  </p>
                  <div className="email">
                    <input type="email" value={email} placeholder="you@email.com (optional)"
                           onChange={e => setEmail(e.target.value)} />
                    <button type="button"
                            onClick={() => track(EVENTS.emailSubmitted, { plan, billing })}>
                      Notify me
                    </button>
                  </div>
                  <div className="opt">Optional — add your email for an early-access invite.</div>
                </div>

                {/* Deliberately after the click: telling people up front that there is
                    nothing to pay removes the commitment this test measures. */}
                <div className="co-fine show">
                  {free
                    ? 'No card required — the free plan never asks for one.'
                    : "No card required. This is a pre-launch validation — you won't be charged."}
                </div>
              </>
            )}
          </div>
        </div>
      </section>

      <footer className="footer">
        <div className="container">
          <p className="legal">
            <b>Intrinsica</b> provides automated quantitative financial-data modeling tools
            for informational analysis. Nothing on this platform constitutes personalized
            investment advice.
          </p>
        </div>
      </footer>
    </div>
  )
}
```

Add `freePlanClicked: 'free_plan_clicked'` to the test's analytics mock so the free path resolves.

- [ ] **Step 4: Add the route**

In `frontend/src/App.tsx`:

```tsx
import CheckoutPage from './landing/CheckoutPage'
...
        <Route path="/checkout" element={<CheckoutPage />} />
```

- [ ] **Step 5: Run the tests and watch them pass**

Run: `cd frontend && npm test -- src/landing/CheckoutPage.test.tsx`
Expected: 9 passed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/landing frontend/src/App.tsx
git commit -m "feat(checkout): separate checkout page with post-click disclosure"
```

---

## Task 15: The copy-guard lint

A standing test that fails the build if banned vocabulary reaches user-facing strings. It is the only thing stopping "signal" or "Risk/Reward" creeping back in during a later edit.

**Files:**
- Create: `frontend/src/landing/copy-guard.test.ts`

**Interfaces:**
- Consumes: the landing source tree via `import.meta.glob`.
- Produces: nothing importable.

- [ ] **Step 1: Write the test**

Create `frontend/src/landing/copy-guard.test.ts`:

```ts
import { describe, it, expect } from 'vitest'

/** Every landing source file, raw. Test files are excluded: they assert *against*
 *  the banned words and would trip the guard on themselves. */
const files = import.meta.glob('./**/*.{ts,tsx}', { eager: true, as: 'raw' }) as
  Record<string, string>

const sources = Object.entries(files).filter(([path]) => !path.includes('.test.'))

function offenders(pattern: RegExp): string[] {
  return sources
    .filter(([, text]) => pattern.test(text))
    .map(([path]) => path)
}

describe('copy guard', () => {
  it('finds landing sources to check', () => {
    expect(sources.length).toBeGreaterThan(5)
  })

  it('never says "signal"', () => {
    expect(offenders(/signal/i)).toEqual([])
  })

  it('never says "Risk/Reward" — the ratio is reward over risk', () => {
    expect(offenders(/Risk\s*[/-]\s*Reward/i)).toEqual([])
    expect(offenders(/\bR\s*[/-]\s*R\b/)).toEqual([])
  })

  it('leaks no internal classifier code', () => {
    // Allows SCREAMING_CASE in code (const names) by only matching inside quotes.
    expect(offenders(/['"`][^'"`]*\b[A-Z]{3,}_[A-Z]{3,}\b[^'"`]*['"`]/)).toEqual([])
  })

  it('never promises a fair-value range', () => {
    expect(offenders(/fair[- ]value range|value range/i)).toEqual([])
  })

  it('asks for no card details', () => {
    expect(offenders(/card number|cardholder|cvc|cvv|expiry date/i)).toEqual([])
  })
})
```

- [ ] **Step 2: Run it**

Run: `cd frontend && npm test -- src/landing/copy-guard.test.ts`
Expected: 6 passed. If a check fails, fix the **copy**, not the guard — the guard encodes a decision from spec §8.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/landing/copy-guard.test.ts
git commit -m "test(landing): copy guard for the banned-vocabulary rules"
```

---

## Task 16: The funnel end-to-end test

Walks a visitor from the landing page to the payment click, asserting the events fire in order, once each, and that the DOM never contains a payment input.

**Files:**
- Create: `frontend/src/landing/funnel.test.tsx`

**Interfaces:**
- Consumes: `App` from `../App`; the real `analytics` module with `fetch` stubbed, so the actual event names are exercised rather than a mock's.

- [ ] **Step 1: Write the test**

Create `frontend/src/landing/funnel.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App'

/** Captures the real event names the real analytics module posts. */
function captureEvents() {
  const seen: { event: string; props: Record<string, unknown> }[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (String(url).endsWith('/api/events')) {
      seen.push(JSON.parse(String(init?.body)))
      return { ok: true, json: async () => ({ recorded: true }) }
    }
    return { ok: true, json: async () => ({ results: [], invalid: [], error: null }) }
  }))
  return seen
}

beforeEach(() => {
  window.history.pushState({}, '', '/')
})

describe('the fake-door funnel', () => {
  it('records each step once, in order, ending at the payment click', async () => {
    const seen = captureEvents()
    render(<App />)

    await waitFor(() => expect(seen.some(e => e.event === 'page_view')).toBe(true))

    await userEvent.click(screen.getByRole('button', { name: 'Choose Pro' }))
    await screen.findByRole('button', { name: 'Proceed to payment' })
    await userEvent.click(screen.getByRole('button', { name: 'Proceed to payment' }))

    const names = seen.map(e => e.event)
    expect(names.filter(n => n === 'payment_button_clicked')).toHaveLength(1)
    expect(names.indexOf('plan_selected')).toBeLessThan(names.indexOf('checkout_started'))
    expect(names.indexOf('checkout_started'))
      .toBeLessThan(names.indexOf('payment_button_clicked'))

    const click = seen.find(e => e.event === 'payment_button_clicked')!
    expect(click.props).toEqual({ plan: 'Pro', billing: 'annual' })
  })

  it('keeps a free click out of the paid funnel', async () => {
    const seen = captureEvents()
    render(<App />)

    await userEvent.click(screen.getByRole('button', { name: 'Start free' }))
    await screen.findByRole('button', { name: 'Create free account' })
    await userEvent.click(screen.getByRole('button', { name: 'Create free account' }))

    const names = seen.map(e => e.event)
    expect(names).toContain('free_plan_clicked')
    expect(names).not.toContain('payment_button_clicked')
    expect(names).not.toContain('plan_selected')
  })

  it('never renders a payment input anywhere in the funnel', async () => {
    captureEvents()
    const { container } = render(<App />)

    const noPaymentInput = () => {
      const inputs = Array.from(container.querySelectorAll('input'))
      for (const i of inputs) {
        expect(i.getAttribute('type')).not.toBe('password')
        expect(i.outerHTML).not.toMatch(/card|cvc|cvv|expiry|iban|account.?number/i)
      }
      expect(container.textContent).not.toMatch(/card number|cvc|cvv|expiry date/i)
    }

    noPaymentInput()
    await userEvent.click(screen.getByRole('button', { name: 'Choose Unlimited' }))
    await screen.findByRole('button', { name: 'Proceed to payment' })
    noPaymentInput()
    await userEvent.click(screen.getByRole('button', { name: 'Proceed to payment' }))
    noPaymentInput()
  })

  // --- Review Focus 5: analytics is down ---
  it('completes the funnel with the events endpoint failing', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (String(url).endsWith('/api/events')) throw new Error('blocked')
      return { ok: true, json: async () => ({ results: [], invalid: [], error: null }) }
    }))
    render(<App />)

    await userEvent.click(screen.getByRole('button', { name: 'Choose Pro' }))
    const button = await screen.findByRole('button', { name: 'Proceed to payment' })
    expect(button).toBeEnabled()
    await userEvent.click(button)
    expect(await screen.findByText(/no payment was taken/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run it**

Run: `cd frontend && npm test -- src/landing/funnel.test.tsx`
Expected: 4 passed. A failure here is a real funnel defect — fix the page, not the test.

- [ ] **Step 3: Run everything**

Run: `cd frontend && npm test` and `cd backend && python -m pytest tests/ -q`
Expected: both suites green.

- [ ] **Step 4: Verify the production build**

Run: `cd frontend && npm run build`
Expected: succeeds with no type errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/landing/funnel.test.tsx
git commit -m "test(landing): end-to-end funnel and no-payment-input guarantee"
```

---

## Done means

- `cd backend && python -m pytest tests/ -q` — green, including the pre-existing suite unchanged by the Quality refactor.
- `cd frontend && npm test` — green, including the copy guard and the funnel test.
- `cd frontend && npm run build` — clean.
- Visiting `/` runs a real AAPL analysis on load, expands into a factor-level breakdown, and every nav anchor resolves.
- Choosing any plan lands on `/checkout`, where the only input on the page is an optional email.

## Not in this plan

Deliberately excluded, with the spec section that defers them:

- The per-IP cache-miss throttle (spec §10). The demo cap and the engine cache bound the cost; add the throttle when traffic justifies it.
- Everything the plans describe but the fake door does not build: accounts, watchlists, alerts, history, portfolio, discovery, exports (spec §2).
- The four open items in spec §12 — pre-computed universe vs on-demand, Portfolio analysis Basic/Advanced, merging the two score-history rows, and the AAPL-vs-NVDA marquee. §12.1 in particular can change the plan matrix in Task 13; if it is settled first, update `content/plans.ts` and its test together.
