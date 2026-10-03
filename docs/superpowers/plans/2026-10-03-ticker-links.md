# Ticker links `/t/{TICKER}`: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `intrinsica.io/t/NVDA` lands on the landing page with NVDA as the featured result. It gets a per-ticker teal preview card for X and chat apps, a Share button on results, and self-hosted fonts.

**Architecture:**
- The SPA gets a `/t/:ticker` route that passes `linkTicker` into `LandingPage`.
- The backend adds three things:
  - a small SEC ticker list (`landing/tickers.py`);
  - a `GET /api/landing/ticker/{raw}` check;
  - a Pillow-drawn card at `/og/{T}.png`.
- `spa.py` swaps the preview `<meta>` tags for known tickers. The frontend owns the allowance rule, the fallback and the Share button.

**Tech stack:**
- **Backend:** FastAPI, httpx, Pillow, pytest.
- **Frontend:** React 19, react-router 7, Vitest + Testing Library, `@fontsource/*`.

**Spec:** `docs/superpowers/specs/2026-10-03-ticker-links-design.md`. Read it first; every task argues from it.

## Global constraints

- **Branch:** `06-Intrinsica_Fake_Door_Launch_Checklist`. Commit with **explicit paths only**. Never stage `*.pyc`, `brand/`, `MonetizationPlan/` or `.superpowers/`.
- **Every commit message** ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Tickers:**
  - Regex `^[A-Z]{1,5}([.-][A-Z]{1,2})?$` after trim and upper-case.
  - Canonical form uses a **dot** (`BRK.B`). The SEC key uses a **dash** (`BRK-B`).
  - One ticker per link.
- **Free allowance (D5):**
  - A link always shows its stock.
  - It calls `recordRun()` only when `canAnalyze()` was true before the run and the run produced a usable row.
  - There is no per-ticker memory anywhere.
- **Events (closed list):** add exactly `ticker_link_opened` and `share_clicked`. `AnalyzeSource` gains `'link'`.
- **Share link:** `https://intrinsica.io/t/{T}?ref=share`. Share text: `{T} on Intrinsica: quality business? Durable moat? Fair price?`
- **Card copy:**
  - headline `Quality business?` / `Durable moat?` / `Fair price?`;
  - small line `Quality · Moat · Fair Value · Reward/Risk, scored from fundamentals`;
  - `intrinsica.io`.
- **Card colours:**
  - gradient `#17696f` → `#0a3a3e`;
  - dots `#66fff7`, `#3d8bff`, `#fae842`;
  - small line `#cfe6e4`;
  - rule: white at 18%.
- **Link title:** `{T}: quality business? Durable moat? Fair price? · Intrinsica`. **Document title on the page:** `{T}: Quality, Moat, Fair Value · Intrinsica`.
- **Fallback notice:** `We couldn't find {LABEL}. Here's an example instead.`
- **Pill text for link runs:** `Live analysis · computed just now`. **Input placeholder in link mode:** `Try another ticker…`.
- **Phone layout** uses the existing 900px single-column breakpoint.
- **No Google Fonts** (`fonts.googleapis.com` / `fonts.gstatic.com`) anywhere under `frontend/src` or `frontend/index.html` once Task 9 lands.
- **Verification commands:**
  - backend: `cd backend && python -m pytest -q -p no:warnings`;
  - frontend: `cd frontend && npx vitest run`, `npx tsc -b --force`, and `npx eslint <touched files>`. Three lint errors in `LandingPage.tsx` predate this work. Don't add more, and don't "fix" them in passing.

## Review focus

1. **Arbitrary text on a branded image.** `/og/<anything>.png` for a string not on the SEC list must never draw that string. It must 302 to `/og-image.png`. Pinned in Task 4.
2. **Tag injection.** The `/t/` path is attacker-controlled. Only canonical tickers on the SEC list are inserted into HTML, and they are escaped anyway. Pinned in Task 5 with `/t/%22%3E%3Cscript%3E`.
3. **The free wall must never hide the linked stock.** With 5/5 used, `/t/NVDA` still renders NVDA and does not increment the counter. Pinned in Task 7.
4. **The fallback must not remount the page.** It uses `history.replaceState`, not `navigate`, so the notice and the sample run survive. Pinned in Task 7.
5. **The SEC list being unreachable must not break ad landings.** The endpoint answers `known: true` for any valid format, and the card degrades to generic. Pinned in Tasks 2 and 3.

---

### Task 1: Ticker normalisation (Python + TypeScript, one shared case table)

**Files:**
- Create: `frontend/src/landing/ticker-cases.json`
- Create: `frontend/src/landing/ticker.ts`
- Create: `frontend/src/landing/ticker.test.ts`
- Create: `backend/landing/tickers.py` (normalisation part only; Task 2 adds the list)
- Test: `backend/tests/test_landing_tickers.py`

**Interfaces:**
- Produces (TS):
  - `normalizeTicker(raw: string): string | null`, which returns the canonical dot form or null;
  - `noticeLabel(raw: string): string`, which returns the cleaned label used in the fallback notice.
- Produces (Py):
  - `normalize(raw: str) -> str | None`;
  - `sec_key(ticker: str) -> str`, where `"BRK.B"` returns `"BRK-B"`.

- [ ] **Step 1: Write the shared case table**

`frontend/src/landing/ticker-cases.json`:
```json
[
  ["nvda", "NVDA"],
  [" msft ", "MSFT"],
  ["BRK.B", "BRK.B"],
  ["brk-b", "BRK.B"],
  ["GOOGL", "GOOGL"],
  ["a,b", null],
  ["", null],
  ["<x>", null],
  ["NVDA AMD", null],
  ["TOOLONGX", null],
  ["BRK.BBB", null],
  ["1ABC", null],
  ["%22%3E", null]
]
```

- [ ] **Step 2: Write the failing tests**

`frontend/src/landing/ticker.test.ts`:
```ts
import { describe, it, expect } from 'vitest'
import cases from './ticker-cases.json'
import { normalizeTicker, noticeLabel } from './ticker'

describe('normalizeTicker', () => {
  it.each(cases as [string, string | null][])('%j → %j', (raw, want) => {
    expect(normalizeTicker(raw)).toBe(want)
  })
})

describe('noticeLabel', () => {
  it('uses the canonical form when there is one', () => {
    expect(noticeLabel('brk-b')).toBe('BRK.B')
  })
  it('strips anything but letters, digits, dot and dash, and cuts at 12', () => {
    expect(noticeLabel('<script>alert(1)</script>')).toBe('SCRIPTALERT1')
    expect(noticeLabel('a,b')).toBe('AB')
  })
  it('never returns an empty label', () => {
    expect(noticeLabel('<<>>')).toBe('that ticker')
  })
})
```

`backend/tests/test_landing_tickers.py`:
```python
import json
from pathlib import Path

import pytest

from landing.tickers import normalize, sec_key

_CASES = json.loads((Path(__file__).resolve().parents[2]
                     / "frontend/src/landing/ticker-cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("raw,want", _CASES)
def test_normalize_matches_the_shared_table(raw, want):
    assert normalize(raw) == want


def test_sec_key_uses_the_dash_form():
    assert sec_key("BRK.B") == "BRK-B"
    assert sec_key("NVDA") == "NVDA"
```

- [ ] **Step 3: Run them and see them fail**

Run: `cd frontend && npx vitest run src/landing/ticker.test.ts`. Expected: FAIL, cannot resolve `./ticker`.
Run: `cd backend && python -m pytest tests/test_landing_tickers.py -q`. Expected: FAIL, `ModuleNotFoundError: landing.tickers`.

- [ ] **Step 4: Implement**

`frontend/src/landing/ticker.ts`:
```ts
/** Ticker-link normalisation (spec 2026-10-03 §3). Mirrors backend/landing/tickers.py;
 *  ticker-cases.json pins both. Canonical form uses a dot (BRK.B) because
 *  /api/landing/analyze validates that shape and rejects the dash form. */
const SHAPE = /^[A-Z]{1,5}([.-][A-Z]{1,2})?$/

export function normalizeTicker(raw: string): string | null {
  const t = raw.trim().toUpperCase()
  return SHAPE.test(t) ? t.replace('-', '.') : null
}

/** What the fallback notice calls a link it could not use. Never echoes markup. */
export function noticeLabel(raw: string): string {
  const t = normalizeTicker(raw)
  if (t) return t
  const cleaned = raw.toUpperCase().replace(/[^A-Z0-9.-]/g, '').slice(0, 12)
  return cleaned || 'that ticker'
}
```

`backend/landing/tickers.py`:
```python
"""Ticker-link support (spec 2026-10-03 §3): normalisation, and (Task 2) the SEC list
of known US tickers. Mirrors frontend/src/landing/ticker.ts; ticker-cases.json pins
both. Canonical form uses a dot (BRK.B) because /api/landing/analyze validates that
shape; the SEC list is keyed by the dash form."""
from __future__ import annotations
import re

_SHAPE = re.compile(r"^[A-Z]{1,5}([.-][A-Z]{1,2})?$")


def normalize(raw: str) -> str | None:
    t = (raw or "").strip().upper()
    return t.replace("-", ".") if _SHAPE.match(t) else None


def sec_key(ticker: str) -> str:
    return ticker.replace(".", "-")
```

- [ ] **Step 5: Run the tests and see them pass**

Run both commands from Step 3. Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/landing/ticker-cases.json frontend/src/landing/ticker.ts frontend/src/landing/ticker.test.ts backend/landing/tickers.py backend/tests/test_landing_tickers.py
git commit -m "feat(links): ticker normalisation shared by frontend and backend

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: SEC known-ticker list

**Files:**
- Modify: `backend/landing/tickers.py`
- Create: `backend/tests/fixtures/sec_company_tickers_sample.json`
- Test: `backend/tests/test_landing_tickers.py`

**Interfaces:**
- Consumes: `normalize` and `sec_key` (Task 1).
- Produces:
  - `async def lookup(ticker: str) -> tuple[bool, str | None]`, which returns `(known, title)` for a canonical ticker;
  - `async def list_available() -> bool`;
  - `def _reset() -> None` (tests only).
  - On failure or a missing User-Agent the list is treated as **unavailable**: `lookup` returns `(False, None)` and `list_available()` returns False.

- [ ] **Step 1: Write the fixture**

`backend/tests/fixtures/sec_company_tickers_sample.json`, in the real file's shape:
```json
{"0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
 "1": {"cik_str": 1067983, "ticker": "BRK-B", "title": "BERKSHIRE HATHAWAY INC"},
 "2": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
```

- [ ] **Step 2: Write the failing tests** (append to `test_landing_tickers.py`)

```python
import asyncio
from unittest.mock import AsyncMock, patch

import landing.tickers as tickers

_SAMPLE = json.loads((Path(__file__).parent / "fixtures/sec_company_tickers_sample.json")
                     .read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _fresh_list(monkeypatch):
    tickers._reset()
    monkeypatch.setenv("SEC_USER_AGENT", "Intrinsica contact@intrinsica.io")
    yield
    tickers._reset()


def _fetch_ok():
    return patch("landing.tickers._fetch_json", new=AsyncMock(return_value=_SAMPLE))


def test_a_listed_ticker_is_known_with_its_title():
    with _fetch_ok():
        assert asyncio.run(tickers.lookup("NVDA")) == (True, "NVIDIA CORP")


def test_a_class_share_is_found_by_its_dash_key():
    with _fetch_ok():
        assert asyncio.run(tickers.lookup("BRK.B")) == (True, "BERKSHIRE HATHAWAY INC")


def test_an_unlisted_ticker_is_not_known():
    with _fetch_ok():
        assert asyncio.run(tickers.lookup("XYZQ")) == (False, None)


def test_the_list_is_fetched_once_and_cached():
    with _fetch_ok() as fetch:
        asyncio.run(tickers.lookup("NVDA"))
        asyncio.run(tickers.lookup("AAPL"))
        assert fetch.await_count == 1


def test_the_cache_expires_after_seven_days(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(tickers, "_now", lambda: clock[0])
    with _fetch_ok() as fetch:
        asyncio.run(tickers.lookup("NVDA"))
        clock[0] += 7 * 24 * 3600 + 1
        asyncio.run(tickers.lookup("NVDA"))
        assert fetch.await_count == 2


def test_a_failed_fetch_means_unavailable_not_a_crash():
    with patch("landing.tickers._fetch_json", new=AsyncMock(side_effect=RuntimeError("down"))):
        assert asyncio.run(tickers.lookup("NVDA")) == (False, None)
        assert asyncio.run(tickers.list_available()) is False


def test_without_a_user_agent_the_sec_is_never_called(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    with _fetch_ok() as fetch:
        assert asyncio.run(tickers.list_available()) is False
        fetch.assert_not_awaited()
```

- [ ] **Step 3: Run them and see them fail**

Run: `cd backend && python -m pytest tests/test_landing_tickers.py -q`. Expected: the new tests FAIL (`_reset` / `lookup` missing).

- [ ] **Step 4: Implement** (append to `backend/landing/tickers.py`)

```python
import asyncio, logging, os, time

import httpx

log = logging.getLogger(__name__)

_URL = "https://www.sec.gov/files/company_tickers.json"
_TTL = 7 * 24 * 3600
# A failed fetch is retried after this long, not on every request: a crawler burst
# during an SEC outage must not turn into an SEC request per hit.
_RETRY_AFTER = 15 * 60
_now = time.monotonic

_titles: dict[str, str] | None = None   # sec_key -> title
_loaded_at = 0.0
_failed_at: float | None = None
_warned = False
_lock = asyncio.Lock()


def _reset() -> None:
    global _titles, _loaded_at, _failed_at, _warned
    _titles, _loaded_at, _failed_at, _warned = None, 0.0, None, False


async def _fetch_json(user_agent: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(_URL, headers={"User-Agent": user_agent})
        r.raise_for_status()
        return r.json()


async def _ensure() -> dict[str, str] | None:
    """The list, fetching it when missing or older than _TTL. None = unavailable."""
    global _titles, _loaded_at, _failed_at, _warned
    now = _now()
    if _titles is not None and now - _loaded_at < _TTL:
        return _titles
    if _failed_at is not None and now - _failed_at < _RETRY_AFTER:
        return _titles      # possibly stale, possibly None
    ua = os.getenv("SEC_USER_AGENT", "").strip()
    if not ua:
        if not _warned:
            log.warning("SEC_USER_AGENT is not set; ticker links use the generic card")
            _warned = True
        return None
    async with _lock:
        if _titles is not None and _now() - _loaded_at < _TTL:
            return _titles
        try:
            raw = await _fetch_json(ua)
            _titles = {str(v["ticker"]).upper(): str(v.get("title") or "")
                       for v in raw.values() if v.get("ticker")}
            _loaded_at, _failed_at = _now(), None
        except Exception as exc:      # network, HTTP status, bad JSON
            _failed_at = _now()
            log.warning("SEC ticker list unavailable: %s", type(exc).__name__)
    return _titles


async def list_available() -> bool:
    return await _ensure() is not None


async def lookup(ticker: str) -> tuple[bool, str | None]:
    titles = await _ensure()
    if titles is None:
        return False, None
    title = titles.get(sec_key(ticker))
    return (True, title) if title is not None else (False, None)
```

Note for later: branch `05-yfinance-replacement` has `services/sec/edgar_client.py` with the same CIK map. When both branches are on `main`, switch `_fetch_json` to that client. Put that sentence as a comment above `_fetch_json`.

- [ ] **Step 5: Run the tests and see them pass**

Run: `cd backend && python -m pytest tests/test_landing_tickers.py -q`. Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/landing/tickers.py backend/tests/test_landing_tickers.py backend/tests/fixtures/sec_company_tickers_sample.json
git commit -m "feat(links): SEC known-ticker list with 7-day cache

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: `GET /api/landing/ticker/{raw}`

**Files:**
- Modify: `backend/routers/landing.py`
- Test: `backend/tests/test_landing_router.py`

**Interfaces:**
- Consumes: `normalize`, `lookup` and `list_available` (Tasks 1–2).
- Produces: JSON `{"ticker": str | None, "known": bool, "name": str | None}`. Task 7 calls it.

- [ ] **Step 1: Write the failing tests** (append to `test_landing_router.py`)

```python
from unittest.mock import AsyncMock, patch


def _list(known: dict[str, str] | None):
    """Patch the SEC list: a dict of canonical ticker -> title, or None = unavailable."""
    async def lookup(t):
        if known is None:
            return False, None
        return (True, known[t]) if t in known else (False, None)
    return (patch("routers.landing.lookup", new=lookup),
            patch("routers.landing.list_available", new=AsyncMock(return_value=known is not None)))


def test_ticker_check_knows_a_listed_ticker():
    a, b = _list({"BRK.B": "BERKSHIRE HATHAWAY INC"})
    with a, b:
        r = client.get("/api/landing/ticker/brk-b")
    assert r.json() == {"ticker": "BRK.B", "known": True, "name": "BERKSHIRE HATHAWAY INC"}


def test_ticker_check_rejects_an_unlisted_ticker():
    a, b = _list({"NVDA": "NVIDIA CORP"})
    with a, b:
        r = client.get("/api/landing/ticker/XYZQ")
    assert r.json() == {"ticker": "XYZQ", "known": False, "name": None}


def test_ticker_check_rejects_a_malformed_ticker():
    a, b = _list({"NVDA": "NVIDIA CORP"})
    with a, b:
        r = client.get("/api/landing/ticker/a,b")
    assert r.json() == {"ticker": None, "known": False, "name": None}


def test_ticker_check_lets_a_valid_shape_through_when_the_list_is_down():
    a, b = _list(None)
    with a, b:
        r = client.get("/api/landing/ticker/NVDA")
    assert r.json() == {"ticker": "NVDA", "known": True, "name": None}


def test_ticker_check_is_rate_limited(monkeypatch):
    monkeypatch.setattr(landing_router._limiter, "limited", lambda key: True)
    r = client.get("/api/landing/ticker/NVDA")
    assert r.status_code == 429
```

- [ ] **Step 2: Run them and see them fail**

Run: `cd backend && python -m pytest tests/test_landing_router.py -q -k ticker_check`. Expected: FAIL with 404 / AttributeError.

- [ ] **Step 3: Implement** (in `backend/routers/landing.py`)

```python
from landing.tickers import normalize, lookup, list_available


@router.get("/landing/ticker/{raw}")
async def ticker_check(raw: str, request: Request):
    """Is this /t/ link a real US ticker (spec 2026-10-03 §3)? While the SEC list is
    unavailable, any well-formed ticker reads as known: the page then tries the
    analysis and falls back only if that fails, so an SEC outage never breaks an
    ad landing. Only the card generator treats "list unavailable" as unknown."""
    if _limiter.limited(client_key(request)):
        return JSONResponse(status_code=429, content={"ticker": None, "known": False, "name": None})
    t = normalize(raw)
    if t is None:
        return {"ticker": None, "known": False, "name": None}
    if not await list_available():
        return {"ticker": t, "known": True, "name": None}
    known, name = await lookup(t)
    return {"ticker": t, "known": known, "name": name}
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `cd backend && python -m pytest tests/test_landing_router.py -q`. Expected: PASS, including the old tests.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/landing.py backend/tests/test_landing_router.py
git commit -m "feat(links): ticker check endpoint for /t/ links

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: The share-card image `/og/{T}.png`

**Files:**
- Modify: `backend/requirements.txt` (add `Pillow`)
- Create: `backend/assets/fonts/SpaceGrotesk[wght].ttf`, `backend/assets/fonts/Inter[opsz,wght].ttf` and `backend/assets/fonts/OFL.txt`
- Create: `backend/landing/og_card.py`
- Create: `backend/routers/og.py`
- Modify: `backend/main.py` (include `og_router` before `mount_spa`)
- Test: `backend/tests/test_og_card.py`

**Interfaces:**
- Consumes: `normalize` and `lookup` (Tasks 1–2).
- Produces:
  - `render_card(ticker: str) -> bytes`, a PNG;
  - the route `GET /og/{name}`, where `name` = `{T}.png`;
  - `CARD_COLOURS: dict[str, str]`, read by the colour-sync test.

- [ ] **Step 1: Add Pillow and the fonts**

Run:
```bash
cd backend && pip install Pillow && python -c "import PIL; print(PIL.__version__)"
```
Add `Pillow==<printed version>` to `backend/requirements.txt`, on its own line after `httpx`.

Download the OFL fonts:
```bash
mkdir -p backend/assets/fonts
curl -L -o "backend/assets/fonts/SpaceGrotesk[wght].ttf" "https://github.com/google/fonts/raw/main/ofl/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf"
curl -L -o "backend/assets/fonts/Inter[opsz,wght].ttf" "https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bopsz,wght%5D.ttf"
curl -L -o backend/assets/fonts/OFL.txt "https://github.com/google/fonts/raw/main/ofl/spacegrotesk/OFL.txt"
python -c "from PIL import ImageFont as F; f=F.truetype('backend/assets/fonts/Inter[opsz,wght].ttf',20); print(f.get_variation_axes())"
```
Expected: the last command prints two axes, `opsz` and `wght`. If a URL 404s, find the file on `https://github.com/google/fonts/tree/main/ofl/<family>` and use that exact name everywhere below.

- [ ] **Step 2: Write the failing tests**

`backend/tests/test_og_card.py`:
```python
import io
import re
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from landing import og_card
from main import create_app


async def _known(t):
    return (True, "X") if t in {"NVDA", "BRK.B", "GOOGL"} else (False, None)


@pytest.fixture
def client():
    og_card._cache.clear()
    with patch("routers.og.lookup", new=_known):
        yield TestClient(create_app(public_mode=True, static_dir="", canonical_host=""))
    og_card._cache.clear()


def test_a_known_ticker_gets_a_1200_by_630_png(client):
    r = client.get("/og/NVDA.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "public, max-age=86400"
    assert Image.open(io.BytesIO(r.content)).size == (1200, 630)


def test_a_class_share_is_served_by_its_canonical_name(client):
    assert client.get("/og/brk-b.png").status_code == 200


@pytest.mark.parametrize("name", ["XYZQ.png", "a,b.png", "%3Cscript%3E.png", "NVDA.jpg", "NVDA"])
def test_anything_unknown_redirects_to_the_generic_card_and_is_never_drawn(client, name):
    with patch.object(og_card, "render_card", side_effect=AssertionError("must not draw")):
        r = client.get(f"/og/{name}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/og-image.png"


def test_a_drawn_card_is_reused(client):
    with patch.object(og_card, "_draw", wraps=og_card._draw) as draw:
        client.get("/og/NVDA.png")
        client.get("/og/NVDA.png")
        assert draw.call_count == 1


def test_the_longest_ticker_fits():
    img = Image.open(io.BytesIO(og_card.render_card("GOOGL.AB")))
    assert img.size == (1200, 630)
    assert og_card.ticker_width("GOOGL.AB") <= 0.6 * 1200


def test_the_mark_colours_match_the_frontend_logo():
    mark_ts = (Path(__file__).resolve().parents[2]
               / "frontend/src/landing/components/mark.ts").read_text(encoding="utf-8")
    for key in ("plateTop", "plateBot", "q", "mo", "fv", "rr"):
        ts = re.search(rf"{key}: '(#[0-9a-f]{{6}})'", mark_ts).group(1)
        assert og_card.CARD_COLOURS[key] == ts, key
```

- [ ] **Step 3: Run them and see them fail**

Run: `cd backend && python -m pytest tests/test_og_card.py -q`. Expected: FAIL, `ImportError: og_card`.

- [ ] **Step 4: Implement `backend/landing/og_card.py`**

```python
"""The /t/{TICKER} share card (spec 2026-10-03 §5): a 1200x630 teal PNG with the
ticker and the three questions, no numbers. Drawn on first request and kept in a
small LRU. Callers must only pass tickers that are on the SEC list (routers/og.py)."""
from __future__ import annotations
import io
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
_FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_GROTESK = _FONTS / "SpaceGrotesk[wght].ttf"
_INTER = _FONTS / "Inter[opsz,wght].ttf"

# Kept equal to frontend/src/landing/components/mark.ts MARK (test_og_card checks).
CARD_COLOURS = {
    "plateTop": "#17696f", "plateBot": "#0a3a3e", "rim": "#8fc4c5",
    "q": "#66fff7", "mo": "#3d8bff", "fv": "#fae842", "rr": "#440ab8",
}
_SMALL = "#cfe6e4"
_LINE = "Quality · Moat · Fair Value · Reward/Risk, scored from fundamentals"
_QUESTIONS = [[("q", "Quality business?"), ("mo", "Durable moat?")], [("fv", "Fair price?")]]
_LEFT, _RIGHT = 78, W - 72

_cache: OrderedDict[str, bytes] = OrderedDict()
_MAX = 256


def _font(path: Path, size: int, weight: int) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(path), size)
    axes = f.get_variation_axes()
    f.set_variation_by_axes([weight if a["name"] in (b"Weight", "Weight") else
                             max(a["minimum"], min(a["maximum"], size)) for a in axes])
    return f


def _rgb(hex_: str) -> tuple[int, int, int]:
    return tuple(int(hex_[i:i + 2], 16) for i in (1, 3, 5))


def _ticker_font(ticker: str) -> ImageFont.FreeTypeFont:
    size = 156
    while size > 60:
        f = _font(_GROTESK, size, 700)
        if f.getlength(ticker) <= 0.6 * W:
            return f
        size -= 6
    return _font(_GROTESK, size, 700)


def ticker_width(ticker: str) -> float:
    return _ticker_font(ticker).getlength(ticker)


def _gradient() -> Image.Image:
    top, bot = _rgb(CARD_COLOURS["plateTop"]), _rgb(CARD_COLOURS["plateBot"])
    img = Image.new("RGB", (W, H))
    px = ImageDraw.Draw(img)
    for y in range(H):
        k = y / (H - 1)
        px.line([(0, y), (W, y)], fill=tuple(round(a + (b - a) * k) for a, b in zip(top, bot)))
    return img


def _mark(img: Image.Image, x: int, y: int, s: int) -> None:
    """The keyhole mark: rounded plate and four quadrants inside the keyhole, drawn
    with a mask (mark.ts KEYHOLE: head circle r=15 at (50,36), slot to y=80)."""
    k = s / 100
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([x + 4 * k, y + 4 * k, x + 96 * k, y + 96 * k], radius=22 * k,
                        fill=_rgb(CARD_COLOURS["plateTop"]), outline=_rgb(CARD_COLOURS["rim"]), width=2)
    mask = Image.new("L", (s, s), 0)
    m = ImageDraw.Draw(mask)
    m.ellipse([35 * k, 21 * k, 65 * k, 51 * k], fill=255)
    m.polygon([(43.1 * k, 51.3 * k), (56.9 * k, 51.3 * k), (62 * k, 80 * k), (38 * k, 80 * k)], fill=255)
    quad = Image.new("RGB", (s, s))
    q = ImageDraw.Draw(quad)
    q.rectangle([0, 0, s / 2, 53 * k], fill=_rgb(CARD_COLOURS["q"]))
    q.rectangle([s / 2, 0, s, 53 * k], fill=_rgb(CARD_COLOURS["mo"]))
    q.rectangle([0, 53 * k, s / 2, s], fill=_rgb(CARD_COLOURS["fv"]))
    q.rectangle([s / 2, 53 * k, s, s], fill=_rgb(CARD_COLOURS["rr"]))
    img.paste(quad, (x, y), mask)


def _draw(ticker: str) -> bytes:
    img = _gradient()
    d = ImageDraw.Draw(img)
    _mark(img, _LEFT, 60, 64)
    d.text((_LEFT + 82, 92), "Intrinsica", font=_font(_GROTESK, 38, 700), fill="white", anchor="lm")
    d.text((_LEFT - 6, 150), ticker, font=_ticker_font(ticker), fill="white")
    qf = _font(_GROTESK, 54, 600)
    y = 330
    for line in _QUESTIONS:
        x = _LEFT
        for key, text in line:
            d.ellipse([x, y + 22, x + 18, y + 40], fill=_rgb(CARD_COLOURS[key]))
            x += 30
            d.text((x, y), text, font=qf, fill="white")
            x += qf.getlength(text) + 34
        y += 68
    # 18% white over the gradient: blended by hand, since an RGB image ignores alpha.
    base = img.getpixel((_LEFT, 494))
    d.line([(_LEFT, 494), (_RIGHT, 494)], fill=tuple(round(c + (255 - c) * 0.18) for c in base), width=1)
    small = _font(_INTER, 25, 400)
    d.text((_LEFT, 536), _LINE, font=small, fill=_SMALL, anchor="lm")
    d.text((_RIGHT, 536), "intrinsica.io", font=_font(_INTER, 25, 700), fill="white", anchor="rm")
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


def render_card(ticker: str) -> bytes:
    if ticker in _cache:
        _cache.move_to_end(ticker)
        return _cache[ticker]
    png = _draw(ticker)
    _cache[ticker] = png
    if len(_cache) > _MAX:
        _cache.popitem(last=False)
    return png
```

- [ ] **Step 5: Implement the route** `backend/routers/og.py`

```python
from __future__ import annotations
import asyncio
from fastapi import APIRouter
from fastapi.responses import RedirectResponse, Response

from landing import og_card
from landing.tickers import normalize, lookup

router = APIRouter()
_GENERIC = "/og-image.png"


@router.api_route("/og/{name}", methods=["GET", "HEAD"], include_in_schema=False)
async def og_image(name: str):
    """Per-ticker share card. Only tickers on the SEC list are ever drawn: anything
    else, including the list being unavailable, redirects to the generic card, so
    nobody can mint a branded image carrying their own text (spec §5)."""
    if not name.endswith(".png"):
        return RedirectResponse(_GENERIC, status_code=302)
    t = normalize(name[:-4])
    if t is None or not (await lookup(t))[0]:
        return RedirectResponse(_GENERIC, status_code=302)
    png = await asyncio.to_thread(og_card.render_card, t)
    return Response(png, media_type="image/png",
                    headers={"Cache-Control": "public, max-age=86400"})
```

In `backend/main.py`, add `from routers.og import router as og_router` and, just before the `@app.get("/api/health")` line, `app.include_router(og_router)`.

- [ ] **Step 6: Run the tests and see them pass, then look at the card**

Run: `cd backend && python -m pytest tests/test_og_card.py -q`. Expected: PASS.

Then run `cd backend && python -c "from landing.og_card import render_card; open('../../og-NVDA.png','wb').write(render_card('NVDA'))"`, open `og-NVDA.png` (one level above the repo), and compare it with the approved mockup (`.superpowers/brainstorm/827-1790977003/archive/share-card-v3.html`, card B, with the small line from the spec). Adjust offsets in `_draw` until it matches. Delete the PNG afterwards.

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt "backend/assets/fonts/SpaceGrotesk[wght].ttf" "backend/assets/fonts/Inter[opsz,wght].ttf" backend/assets/fonts/OFL.txt backend/landing/og_card.py backend/routers/og.py backend/main.py backend/tests/test_og_card.py
git commit -m "feat(links): per-ticker share card drawn with Pillow at /og/{T}.png

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Per-ticker preview tags in `spa.py`

**Files:**
- Modify: `backend/spa.py`
- Test: `backend/tests/test_spa.py`

**Interfaces:**
- Consumes: `normalize` and `lookup` (Tasks 1–2). The tag set in `frontend/index.html` is unchanged.
- Produces: `/t/{raw}` responses whose `<title>`, `og:title`, `og:url`, `og:image` and `twitter:image` are per-ticker.

- [ ] **Step 1: Write the failing tests** (in `test_spa.py`)

Change the `static_dir` fixture's `index.html` to carry the real tags:
```python
_INDEX = """<!doctype html><html><head>
<title>Intrinsica</title>
<meta property="og:title" content="Intrinsica — Judge the business. Then judge the price." />
<meta property="og:image" content="https://intrinsica.io/og-image.png" />
<meta property="og:url" content="https://intrinsica.io/" />
<meta name="twitter:image" content="https://intrinsica.io/og-image.png" />
</head><body></body></html>"""
```
Write `_INDEX` instead of the one-line HTML. Keep every existing assertion that checks `<title>Intrinsica</title>` (still true for `/`).

Append:
```python
from unittest.mock import patch


async def _known(t):
    return (True, "X") if t in {"NVDA", "BRK.B"} else (False, None)


def test_a_known_ticker_link_gets_its_own_preview_tags(client):
    with patch("spa.lookup", new=_known):
        r = client.get("/t/nvda")
    assert r.headers["cache-control"] == "no-cache"
    assert "<title>NVDA: quality business? Durable moat? Fair price? · Intrinsica</title>" in r.text
    assert 'content="NVDA: quality business? Durable moat? Fair price? · Intrinsica"' in r.text
    assert 'content="https://intrinsica.io/og/NVDA.png"' in r.text
    assert 'content="https://intrinsica.io/t/NVDA"' in r.text
    assert "og-image.png" not in r.text


def test_a_class_share_link_uses_the_canonical_ticker(client):
    with patch("spa.lookup", new=_known):
        r = client.get("/t/BRK-B")
    assert 'content="https://intrinsica.io/og/BRK.B.png"' in r.text


@pytest.mark.parametrize("path", ["/t/XYZQ", "/t/a,b", '/t/%22%3E%3Cscript%3E', "/t/", "/t/NVDA/extra"])
def test_anything_else_gets_the_untouched_page(client, path):
    with patch("spa.lookup", new=_known):
        r = client.get(path)
    assert r.status_code == 200
    assert "<title>Intrinsica</title>" in r.text
    assert "https://intrinsica.io/og-image.png" in r.text
    assert "<script>" not in r.text


def test_head_works_on_a_ticker_link(client):
    with patch("spa.lookup", new=_known):
        assert client.head("/t/NVDA").status_code == 200
```

- [ ] **Step 2: Run them and see them fail**

Run: `cd backend && python -m pytest tests/test_spa.py -q`. Expected: the new tests FAIL.

- [ ] **Step 3: Implement** (in `backend/spa.py`)

```python
import html
import re
from fastapi.responses import HTMLResponse
from landing.tickers import normalize, lookup

_SITE = "https://intrinsica.io"


def _ticker_page(index_html: str, t: str) -> str:
    """index.html with the preview tags swapped for ticker t (spec 2026-10-03 §5).
    t is a canonical ticker already confirmed on the SEC list; escaped regardless."""
    title = html.escape(f"{t}: quality business? Durable moat? Fair price? · Intrinsica", quote=True)
    image = html.escape(f"{_SITE}/og/{t}.png", quote=True)
    url = html.escape(f"{_SITE}/t/{t}", quote=True)
    out = re.sub(r"<title>.*?</title>", f"<title>{title}</title>", index_html, count=1, flags=re.S)
    out = re.sub(r'(<meta property="og:title" content=")[^"]*(")', rf"\g<1>{title}\g<2>", out, count=1)
    out = re.sub(r'(<meta property="og:url" content=")[^"]*(")', rf"\g<1>{url}\g<2>", out, count=1)
    out = re.sub(r'(<meta property="og:image" content=")[^"]*(")', rf"\g<1>{image}\g<2>", out, count=1)
    out = re.sub(r'(<meta name="twitter:image" content=")[^"]*(")', rf"\g<1>{image}\g<2>", out, count=1)
    return out
```

Inside `mount_spa`:
- Read the index once, right after the `index.is_file()` check: `index_html = index.read_text(encoding="utf-8")`.
- In `spa(path)`, before the final `return FileResponse(index, ...)`:
```python
        m = re.fullmatch(r"t/([^/]+)", path)
        if m:
            t = normalize(m.group(1))
            if t is not None and (await lookup(t))[0]:
                return HTMLResponse(_ticker_page(index_html, t), headers={"Cache-Control": _NO_CACHE})
```
- Update the docstring: `/t/{TICKER}` links now get per-ticker preview tags.

- [ ] **Step 4: Run the tests and see them pass**

Run: `cd backend && python -m pytest tests/test_spa.py tests/test_canonical.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/spa.py backend/tests/test_spa.py
git commit -m "feat(links): per-ticker preview tags on /t/{TICKER}

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Analytics: two events, the `link` source, `t.co` → `x`

**Files:**
- Modify: `frontend/src/lib/analytics.ts`, `frontend/src/lib/analytics.test.ts`
- Modify: `backend/routers/events.py`
- Modify: `frontend/src/landing/types.ts`
- Modify: `frontend/src/lib/attribution.ts`, `frontend/src/lib/attribution.test.ts`
- Modify: `docs/superpowers/specs/2026-09-23-intrinsica-fake-door-design.md` (§9 addendum)
- Modify: `frontend/src/landing/LandingPage.test.tsx` (the mocked `EVENTS` gains the two keys)

**Interfaces:**
- Produces:
  - `EVENTS.tickerLinkOpened = 'ticker_link_opened'`;
  - `EVENTS.shareClicked = 'share_clicked'`;
  - `AnalyzeSource = 'sample' | 'typed' | 'link'`.

- [ ] **Step 1: Write the failing tests**

In `analytics.test.ts`, add `'ticker_link_opened'` and `'share_clicked'` to `SPEC_EVENTS`, with a comment line: `// added 2026-10-03 (ticker links spec §7)`.

In `attribution.test.ts`, inside `describe('readTouch')`:
```ts
  it('records an X click without tags as channel x, keeping the raw referrer', async () => {
    const { readTouch } = await fresh('/t/NVDA', 'https://t.co/abc123')
    expect(readTouch()).toMatchObject({ channel: 'x', referrer: 't.co' })
  })
```

- [ ] **Step 2: Run them and see them fail**

Run: `cd frontend && npx vitest run src/lib`. Expected: the EVENTS test and the `t.co` test FAIL.

Run: `cd backend && python -m pytest tests/test_events_router.py -q`. Expected: `test_the_backend_allowlist_is_exactly_the_frontend_event_list` still passes; it starts failing after Step 3's frontend edit until the backend is edited too.

- [ ] **Step 3: Implement**

`analytics.ts` `EVENTS`, after `watchlistClicked`:
```ts
  /** Arrived through a /t/{TICKER} link (ad, post or a visitor's share; the
   *  attribution says which). Carries { ticker, known }. Ticker links spec §7. */
  tickerLinkOpened: 'ticker_link_opened',
  /** Pressed Share on a result. Carries { ticker, method: 'native' | 'copy' }. */
  shareClicked: 'share_clicked',
```

`backend/routers/events.py` `FUNNEL_EVENTS`: add `"ticker_link_opened", "share_clicked",`.

`types.ts`: `export type AnalyzeSource = 'sample' | 'typed' | 'link'`. Extend its doc comment: `'link' is a /t/{TICKER} visit: it uses one free analysis while any remain, but is never blocked by the wall (ticker links spec D5).`

`attribution.ts`, in `readTouch`, replace the channel line:
```ts
  // X wraps every outbound link in t.co; an untagged X click belongs to the same
  // channel as a tagged X post (ticker links spec D7).
  const fromReferrer = touch.referrer === 't.co' ? 'x' : touch.referrer
  touch.channel = touch.utm_source ?? touch.ref ?? fromReferrer ?? 'direct'
```

`LandingPage.test.tsx`: add `tickerLinkOpened: 'ticker_link_opened', shareClicked: 'share_clicked',` to the mocked `EVENTS`.

Fake-door spec: after the B1 addendum paragraph added on 2026-10-02 (search for `*Added 2026-10-02 (launch checklist B1`), add:
```
*Added 2026-10-03 (ticker links spec §7, user decision):* the closed list grows by two
events, `ticker_link_opened` (arrived through a `/t/{TICKER}` link; props `ticker`,
`known`) and `share_clicked` (pressed Share; props `ticker`, `method`). The analysis
`source` prop gains `link`. The B3 rules count `analysis_completed` with `source` =
`typed` **or** `link` as an engaged visitor.
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `cd frontend && npx vitest run src/lib src/landing/LandingPage.test.tsx` and `cd backend && python -m pytest tests/test_events_router.py -q`. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/analytics.ts frontend/src/lib/analytics.test.ts backend/routers/events.py frontend/src/landing/types.ts frontend/src/lib/attribution.ts frontend/src/lib/attribution.test.ts frontend/src/landing/LandingPage.test.tsx docs/superpowers/specs/2026-09-23-intrinsica-fake-door-design.md
git commit -m "feat(analytics): ticker_link_opened, share_clicked, link source, t.co as x

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: The `/t/:ticker` route and the linked landing page

**Files:**
- Modify: `frontend/src/App.tsx`, `frontend/src/App.test.tsx`
- Modify: `frontend/src/landing/LandingPage.tsx`
- Modify: `frontend/src/landing/components/Hero.tsx`
- Modify: `frontend/src/landing/components/ResultCard.tsx` (the `Pill` only)
- Modify: `frontend/src/landing/theme.css`
- Test: `frontend/src/landing/linked.test.tsx` (new)

**Interfaces:**
- Consumes:
  - `normalizeTicker` and `noticeLabel` (Task 1);
  - `/api/landing/ticker/{t}` (Task 3);
  - `EVENTS.tickerLinkOpened` and `'link'` (Task 6);
  - `canAnalyze` and `recordRun` (existing `demoLimit.ts`).
- Produces:
  - `LandingPage` accepts `{ linkTicker?: string }`;
  - `Hero` accepts `linked?: string | null`.

- [ ] **Step 1: Write the failing tests**

`frontend/src/landing/linked.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import LandingPage from './LandingPage'
import { DEMO_RUN_LIMIT, runsUsed } from './demoLimit'
import type { TickerPayload } from './types'

vi.mock('../lib/analytics', () => ({
  track: vi.fn(),
  visitorId: () => 'v-test',
  EVENTS: {
    pageView: 'page_view', analysisStarted: 'analysis_started',
    analysisCompleted: 'analysis_completed', breakdownOpened: 'breakdown_opened',
    methodologyViewed: 'methodology_viewed', pricingViewed: 'pricing_viewed',
    planSelected: 'plan_selected', freePlanClicked: 'free_plan_clicked',
    watchlistClicked: 'watchlist_clicked', tickerLinkOpened: 'ticker_link_opened',
    shareClicked: 'share_clicked',
  },
}))

function payload(ticker: string, ok = true): TickerPayload {
  return {
    ticker, company_name: `${ticker} Inc.`, price: 100,
    quality: ok ? { score: 7, fundamentals_composite: 7, profile_label: 'Tech', categories: [] } as never : null,
    moat: null, fair_value: null, reward_risk: null, calibrations: [], errors: ok ? [] : ['failed'],
  }
}

/** Routes the two endpoints: the ticker check, and analyze (which echoes the asked
 *  tickers back as rows, failing any in `failing`). */
function server({ known = true, failing = [] as string[] } = {}) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.includes('/api/landing/ticker/')) {
      const t = decodeURIComponent(url.split('/').pop()!)
      return { json: async () => ({ ticker: t, known, name: null }) }
    }
    const { tickers } = JSON.parse(String(init?.body))
    return { json: async () => ({
      results: tickers.map((t: string) => payload(t, !failing.includes(t))),
      invalid: [], error: null }) }
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function tracked() {
  const { track } = await import('../lib/analytics')
  return vi.mocked(track)
}

function show(raw: string) {
  return render(<MemoryRouter initialEntries={[`/t/${raw}`]}><LandingPage linkTicker={raw} /></MemoryRouter>)
}

beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState(null, '', '/t/x')
})

describe('a /t/ link', () => {
  it('names the stock in the headline and shows its result, not AAPL', async () => {
    server()
    show('nvda')
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('NVDA: judge the business.'))
    await waitFor(() => expect(screen.getByText('NVDA Inc.')).toBeInTheDocument())
    expect(screen.queryByText('AAPL Inc.')).toBeNull()
    expect(screen.getByPlaceholderText('Try another ticker…')).toBeInTheDocument()
    expect(screen.getByText(/Live analysis · computed just now/)).toBeInTheDocument()
    expect(document.title).toBe('NVDA: Quality, Moat, Fair Value · Intrinsica')
  })

  it('fires ticker_link_opened once and runs as source link', async () => {
    server()
    show('NVDA')
    const track = await tracked()
    await waitFor(() => expect(screen.getByText('NVDA Inc.')).toBeInTheDocument())
    expect(track.mock.calls.filter(c => c[0] === 'ticker_link_opened'))
      .toEqual([['ticker_link_opened', { ticker: 'NVDA', known: true }]])
    expect(track).toHaveBeenCalledWith('analysis_started', expect.objectContaining({ source: 'link' }))
  })

  it('uses one free analysis while some remain, and another on a repeat visit', async () => {
    server()
    const first = show('NVDA')
    await waitFor(() => expect(runsUsed()).toBe(1))
    first.unmount()
    show('NVDA')
    await waitFor(() => expect(runsUsed()).toBe(2))
  })

  it('still shows the linked stock when the free analyses are used up, without counting', async () => {
    localStorage.setItem('intrinsica_demo_runs',
      JSON.stringify({ count: DEMO_RUN_LIMIT, windowStart: Date.now() }))
    server()
    show('NVDA')
    await waitFor(() => expect(screen.getByText('NVDA Inc.')).toBeInTheDocument())
    expect(runsUsed()).toBe(DEMO_RUN_LIMIT)
    expect(screen.getByText(/You've used all/)).toBeInTheDocument()
  })

  it.each([
    ['an unknown ticker', 'XYZQ', { known: false }, 'XYZQ'],
    ['a malformed link', 'a,b', {}, 'AB'],
    ['a failed analysis', 'NVDA', { failing: ['NVDA'] }, 'NVDA'],
  ])('falls back to the AAPL example for %s, in place', async (_label, raw, opts, shown) => {
    server(opts as never)
    show(raw)
    await waitFor(() => expect(screen.getByText('AAPL Inc.')).toBeInTheDocument())
    expect(screen.getByText(`We couldn't find ${shown}. Here's an example instead.`)).toBeInTheDocument()
    expect(window.location.pathname).toBe('/')
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/^Judge the business/)
    expect(runsUsed()).toBe(0)
  })

  it('puts the card right after the headline on phones (class hook for the CSS)', async () => {
    server()
    const { container } = show('NVDA')
    await waitFor(() => expect(screen.getByText('NVDA Inc.')).toBeInTheDocument())
    expect(container.querySelector('header.hero.linked')).not.toBeNull()
  })
})
```

In `App.test.tsx`:
- change the LandingPage mock to `vi.mock('./landing/LandingPage', () => ({ default: ({ linkTicker }: { linkTicker?: string }) => <div>{linkTicker ? `landing-page:${linkTicker}` : 'landing-page'}</div> }))`;
- replace the test `'shows the landing page for unknown paths such as future share links'` with:
```tsx
  it('passes a /t/ link ticker to the landing page', async () => {
    vi.stubEnv('VITE_PUBLIC_MODE', '1')
    await renderAt('/t/AMZN')
    expect(screen.getByText('landing-page:AMZN')).toBeInTheDocument()
  })

  it('still shows the plain landing page for other unknown paths', async () => {
    vi.stubEnv('VITE_PUBLIC_MODE', '1')
    await renderAt('/whatever')
    expect(screen.getByText('landing-page')).toBeInTheDocument()
  })
```
- and in the local-dev describe add:
```tsx
  it('serves /t/ links in dev too', async () => {
    vi.stubEnv('VITE_PUBLIC_MODE', '')
    await renderAt('/t/NVDA')
    expect(screen.getByText('landing-page:NVDA')).toBeInTheDocument()
  })
```

- [ ] **Step 2: Run them and see them fail**

Run: `cd frontend && npx vitest run src/landing/linked.test.tsx src/App.test.tsx`. Expected: FAIL.

- [ ] **Step 3: Implement the route** (`App.tsx`)

```tsx
import { BrowserRouter, Routes, Route, useParams } from 'react-router-dom'

/** /t/{TICKER}: the landing page with that stock featured (ticker links spec §4).
 *  Registered in both modes, before the public-mode catch-all. */
function TickerLanding() {
  const { ticker = '' } = useParams()
  return <LandingPage linkTicker={ticker} />
}
```
Add `<Route path="/t/:ticker" element={<TickerLanding />} />` right after the `/privacy` route. Update the comment block above `App` to mention it.

- [ ] **Step 4: Implement the page logic** (`LandingPage.tsx`)

1. Imports: `import { normalizeTicker, noticeLabel } from './ticker'`.
2. Signature: `export default function LandingPage({ linkTicker }: { linkTicker?: string } = {})`.
3. State: `const [linked, setLinked] = useState<string | null>(null)`. This is the canonical ticker while the page is featuring a link.
4. Change `analyze` to take a counting flag and return whether a usable row came back:
```ts
  const analyze = useCallback(async (
    tickers: string[], source: AnalyzeSource, countRun = source === 'typed',
  ): Promise<boolean> => {
```
   - Replace `if (source === 'typed' && !body.error && results.length > 0) {` with `if (countRun && !body.error && results.length > 0) {`.
   - At the end of the `try` block (after the count), add `return results.some(usable)`.
   - Make the `catch` branch `return false` after setting the notice.
   - Add the helper above the component:
```ts
/** A row worth featuring: at least one of the four assessments came back. A ticker
 *  that does not exist comes back as a row with every block null. */
function usable(r: TickerPayload): boolean {
  return Boolean(r.quality || r.moat || r.fair_value || r.reward_risk)
}
```
5. Replace the mount effect:
```ts
  useEffect(() => {
    track(EVENTS.pageView)
    if (linkTicker === undefined) {
      void analyze([SAMPLE], 'sample')
      return
    }
    let live = true
    const fallBack = () => {
      if (!live) return
      setLinked(null)
      // replaceState, not navigate(): navigating to "/" would unmount this page and
      // mount a fresh one, losing the notice. The router doesn't need to know — the
      // page already renders what "/" renders.
      window.history.replaceState(window.history.state, '', '/')
      void analyze([SAMPLE], 'sample')
      setNotice(`We couldn't find ${noticeLabel(linkTicker)}. Here's an example instead.`)
    }
    void (async () => {
      const t = normalizeTicker(linkTicker)
      let known = false
      if (t) {
        try {
          const r = await fetch(`${API_BASE}/api/landing/ticker/${encodeURIComponent(t)}`)
          known = Boolean((await r.json()).known)
        } catch {
          known = true // the check itself failed: try the analysis, fall back if it fails
        }
      }
      if (!live) return
      track(EVENTS.tickerLinkOpened, { ticker: t ?? noticeLabel(linkTicker), known })
      if (!t || !known) return fallBack()
      setLinked(t)
      // Spec D5: a link always shows its stock; it uses a free analysis only while
      // one remains. canAnalyze() is read BEFORE the run.
      const ok = await analyze([t], 'link', canAnalyze())
      if (!ok) fallBack()
    })()
    return () => { live = false }
  }, [analyze, linkTicker])
```
   **Note on `useState(true)` for `busy`:** this is unchanged. The link path starts with a fetch, so the card shows its loading state until the analysis settles.

   **StrictMode:** in dev the effect runs, cleans up, then runs again. The `live` flag stops the first pass from firing `ticker_link_opened` or the fallback, as long as its fetch resolves after the cleanup. Leave `page_view` as it is (existing behaviour).
6. Set the document title while a link is featured:
```ts
  useEffect(() => {
    if (!linked) return
    const previous = document.title
    document.title = `${linked}: Quality, Moat, Fair Value · Intrinsica`
    return () => { document.title = previous }
  }, [linked])
```
7. Pass `linked={linked}` to `<Hero>`.

- [ ] **Step 5: Implement Hero, the Pill and the CSS**

`Hero.tsx`:
- Add the prop `/** The ticker a /t/ link is featuring (ticker links spec §4), or null. */ linked?: string | null`, and destructure it with default `null`.
- `<header className={linked ? 'hero linked' : 'hero'}>`.
- Headline:
```tsx
          <h1 className="hero-h1">
            {linked && <><span className="hero-tk">{linked}:</span>{' '}</>}
            {linked ? 'judge the business.' : 'Judge the business.'}{' '}<br />Then judge the price.
          </h1>
```
- Placeholder: `placeholder={linked ? 'Try another ticker…' : 'Enter one or more tickers — e.g. NVDA, AMD, AVGO'}`.

`ResultCard.tsx` `Pill`:
```tsx
function Pill({ source }: { source: AnalyzeSource | null }) {
  if (source === 'typed') return <span className="rc-pill yours">Your analysis</span>
  const label = source === 'link' ? 'Live analysis · computed just now' : 'Live example · computed just now'
  return <span className="rc-pill live"><i aria-hidden="true" />{label}</span>
}
```

`theme.css`, appended:
```css
/* ticker links (spec 2026-10-03 §4): the featured ticker, and on phones the card
 * right after the headline. display: contents lets hero-l's children take part in
 * the single-column grid; DOM order (and so reading and tab order) is unchanged. */
.intrinsica .hero-tk { color: var(--accent); }
@media (max-width: 900px) {
  .intrinsica .hero.linked .hero-l { display: contents; }
  .intrinsica .hero.linked .hero-h1 { order: 1; }
  .intrinsica .hero.linked .hero-r { order: 2; }
  .intrinsica .hero.linked .hero-sub { order: 3; }
  .intrinsica .hero.linked .analyzer { order: 4; }
  .intrinsica .hero.linked .notice { order: 5; }
}
```

- [ ] **Step 6: Run the tests and see them pass**

Run: `cd frontend && npx vitest run`. Expected: everything passes, including the existing `LandingPage.test.tsx`, `funnel.test.tsx` and `Hero` tests.

Run: `npx tsc -b --force` (clean) and `npx eslint src/App.tsx src/landing/LandingPage.tsx src/landing/components/Hero.tsx src/landing/components/ResultCard.tsx src/landing/linked.test.tsx`. Expected: no errors beyond the three pre-existing ones in `LandingPage.tsx`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.test.tsx frontend/src/landing/LandingPage.tsx frontend/src/landing/components/Hero.tsx frontend/src/landing/components/ResultCard.tsx frontend/src/landing/theme.css frontend/src/landing/linked.test.tsx
git commit -m "feat(links): /t/{TICKER} features that stock, with fallback and the D5 allowance rule

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Share button

**Files:**
- Create: `frontend/src/landing/share.ts`
- Create: `frontend/src/landing/components/ShareButton.tsx`
- Modify: `frontend/src/landing/components/ResultCard.tsx`
- Modify: `frontend/src/landing/theme.css`
- Test: `frontend/src/landing/components/ShareButton.test.tsx`

**Interfaces:**
- Consumes: `track` and `EVENTS.shareClicked` (Task 6).
- Produces:
  - `shareUrl(ticker: string): string`;
  - `shareText(ticker: string): string`;
  - `<ShareButton ticker />`.

- [ ] **Step 1: Write the failing tests**

`frontend/src/landing/components/ShareButton.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ShareButton from './ShareButton'
import { shareUrl, shareText } from '../share'

vi.mock('../../lib/analytics', async importActual => ({
  ...(await importActual<typeof import('../../lib/analytics')>()),
  track: vi.fn(),
}))

async function tracked() {
  const { track } = await import('../../lib/analytics')
  return vi.mocked(track)
}

beforeEach(() => {
  vi.clearAllMocks()
  Reflect.deleteProperty(navigator, 'share')
})

describe('share link and text', () => {
  it('always points at the canonical site with ref=share', () => {
    expect(shareUrl('BRK.B')).toBe('https://intrinsica.io/t/BRK.B?ref=share')
    expect(shareText('NVDA')).toBe('NVDA on Intrinsica: quality business? Durable moat? Fair price?')
  })
})

describe('ShareButton', () => {
  it('opens the native share sheet when there is one', async () => {
    const share = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'share', { value: share, configurable: true })
    render(<ShareButton ticker="NVDA" />)
    await userEvent.click(screen.getByRole('button', { name: 'Share NVDA' }))
    expect(share).toHaveBeenCalledWith({
      title: 'NVDA on Intrinsica', text: shareText('NVDA'), url: shareUrl('NVDA') })
    expect(await tracked()).toHaveBeenCalledWith('share_clicked', { ticker: 'NVDA', method: 'native' })
  })

  it('stays quiet when the visitor cancels the share sheet', async () => {
    Object.defineProperty(navigator, 'share', {
      value: vi.fn().mockRejectedValue(new DOMException('cancel', 'AbortError')), configurable: true })
    render(<ShareButton ticker="NVDA" />)
    await userEvent.click(screen.getByRole('button', { name: 'Share NVDA' }))
    expect(screen.queryByText('Link copied')).toBeNull()
    expect(screen.queryByRole('textbox')).toBeNull()
  })

  it('copies the link on a desktop and says so', async () => {
    const user = userEvent.setup()
    const write = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue()
    render(<ShareButton ticker="NVDA" />)
    await user.click(screen.getByRole('button', { name: 'Share NVDA' }))
    expect(write).toHaveBeenCalledWith(shareUrl('NVDA'))
    expect(await screen.findByText('Link copied')).toBeInTheDocument()
    expect(await tracked()).toHaveBeenCalledWith('share_clicked', { ticker: 'NVDA', method: 'copy' })
  })

  it('shows the link to copy by hand when the clipboard refuses', async () => {
    const user = userEvent.setup()
    vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(new Error('denied'))
    render(<ShareButton ticker="NVDA" />)
    await user.click(screen.getByRole('button', { name: 'Share NVDA' }))
    expect(await screen.findByDisplayValue(shareUrl('NVDA'))).toBeInTheDocument()
  })
})
```

In `ResultCard.test.tsx`, add:
```tsx
  it('offers Share for a single result and for every compared row', () => {
    const { rerender } = render(<ResultCard {...props({ rows: [row()] })} />)
    expect(screen.getByRole('button', { name: 'Share AAPL' })).toBeInTheDocument()
    rerender(<ResultCard {...props({ rows: [row(), row({ ticker: 'MSFT' })] })} />)
    expect(screen.getByRole('button', { name: 'Share AAPL' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Share MSFT' })).toBeInTheDocument()
  })
```
If the file names its props builder differently, use that builder. It already builds `ResultCardProps` for the existing tests.

- [ ] **Step 2: Run them and see them fail**

Run: `cd frontend && npx vitest run src/landing/components/ShareButton.test.tsx src/landing/components/ResultCard.test.tsx`. Expected: FAIL.

- [ ] **Step 3: Implement**

`frontend/src/landing/share.ts`:
```ts
/** The Share button's link and text (ticker links spec §6). Always the canonical
 *  site, whatever host the page is on, and tagged so whoever opens it is recorded
 *  as channel `share` (B1). */
export const shareUrl = (t: string) => `https://intrinsica.io/t/${t}?ref=share`
export const shareText = (t: string) => `${t} on Intrinsica: quality business? Durable moat? Fair price?`
```

`frontend/src/landing/components/ShareButton.tsx`:
```tsx
import { useState } from 'react'
import { Share2 } from 'lucide-react'
import { track, EVENTS } from '../../lib/analytics'
import { shareText, shareUrl } from '../share'

/** Share one result (ticker links spec §6): the phone's own share sheet where there
 *  is one, otherwise copy the link. Fires share_clicked on the click itself. */
export default function ShareButton({ ticker }: { ticker: string }) {
  const [state, setState] = useState<'idle' | 'copied' | 'manual'>('idle')
  const url = shareUrl(ticker)

  async function onClick(e: React.MouseEvent) {
    e.stopPropagation() // inside a clickable comparison row
    const native = typeof navigator.share === 'function'
    track(EVENTS.shareClicked, { ticker, method: native ? 'native' : 'copy' })
    if (native) {
      try { await navigator.share({ title: `${ticker} on Intrinsica`, text: shareText(ticker), url }) }
      catch { /* cancelled or refused: nothing to say */ }
      return
    }
    try {
      await navigator.clipboard.writeText(url)
      setState('copied')
      setTimeout(() => setState('idle'), 2000)
    } catch {
      setState('manual')
    }
  }

  return (
    <span className="share-wrap">
      <button type="button" className="share" aria-label={`Share ${ticker}`} title="Share" onClick={onClick}>
        <Share2 size={14} strokeWidth={1.9} aria-hidden="true" /><span className="share-l">Share</span>
      </button>
      <span className="share-msg" aria-live="polite">{state === 'copied' ? 'Link copied' : ''}</span>
      {state === 'manual' && (
        <input className="share-url" readOnly value={url} aria-label="Link to copy"
               onFocus={e => e.currentTarget.select()} autoFocus
               onClick={e => e.stopPropagation()} />
      )}
    </span>
  )
}
```

`ResultCard.tsx`:
- import `ShareButton`;
- in the one-ticker header, after `<Star … />{' '}`, add `<ShareButton ticker={r.ticker} />{' '}`;
- in `CompareView`, after `<Star ticker={r.ticker} onWatch={onWatch} />`, add `<ShareButton ticker={r.ticker} />`.

`theme.css`, appended:
```css
/* Share button (ticker links spec §6) — sits beside the watchlist bookmark. */
.intrinsica .share-wrap { position: relative; display: inline-flex; align-items: center; gap: 6px; vertical-align: middle; }
.intrinsica .share { display: inline-flex; align-items: center; gap: 4px; border: 1px solid var(--border2);
  background: var(--bg); color: var(--accent); border-radius: 7px; padding: 2px 8px; font: 600 12px var(--fb); cursor: pointer; }
.intrinsica .share:hover { border-color: var(--accent); }
.intrinsica .share:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.intrinsica .share-msg { font-size: 12px; color: var(--pos); }
.intrinsica .share-url { font: 12px var(--fm); width: 260px; max-width: 70vw; padding: 3px 6px; border: 1px solid var(--border2); border-radius: 6px; }
@media (max-width: 560px) { .intrinsica .share-l { display: none; } }
```

- [ ] **Step 4: Run the tests and see them pass**

Run: `cd frontend && npx vitest run && npx tsc -b --force && npx eslint src/landing/share.ts src/landing/components/ShareButton.tsx src/landing/components/ShareButton.test.tsx src/landing/components/ResultCard.tsx`. Expected: PASS and clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/landing/share.ts frontend/src/landing/components/ShareButton.tsx frontend/src/landing/components/ShareButton.test.tsx frontend/src/landing/components/ResultCard.tsx frontend/src/landing/components/ResultCard.test.tsx frontend/src/landing/theme.css
git commit -m "feat(links): Share button on every result

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Self-hosted fonts, and the privacy notice in step

**Files:**
- Modify: `frontend/package.json` and `package-lock.json` (via npm)
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/landing/theme.css` (line 1) and `frontend/src/index.css` (line 1)
- Create: `frontend/src/fonts.test.ts`
- Modify: `frontend/src/landing/PrivacyPage.tsx` and `frontend/src/landing/PrivacyPage.test.tsx`

**Interfaces:** none new.

- [ ] **Step 1: Write the failing tests**

`frontend/src/fonts.test.ts`:
```ts
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect } from 'vitest'

/** Ticker links spec D11: fonts are self-hosted, so no visitor's IP goes to Google.
 *  The privacy notice stopped mentioning Google Fonts on the same day; this keeps
 *  the two true together. */
const src = dirname(fileURLToPath(import.meta.url))
function files(dir: string): string[] {
  return readdirSync(dir).flatMap(n => {
    const p = join(dir, n)
    return statSync(p).isDirectory() ? files(p) : /\.(css|ts|tsx)$/.test(n) && !n.endsWith('.test.ts') ? [p] : []
  })
}

describe('fonts', () => {
  it('are never loaded from Google', () => {
    const offenders = [...files(src), resolve(src, '../index.html')]
      .filter(f => /fonts\.(googleapis|gstatic)\.com/.test(readFileSync(f, 'utf8')))
    expect(offenders).toEqual([])
  })
})
```

In `PrivacyPage.test.tsx`:
- remove `/Google Fonts/i, // theme.css loads fonts from Google` from the disclosure list;
- add:
```tsx
  it('does not claim a Google Fonts transfer the site no longer makes', () => {
    const { container } = show()
    expect(container.textContent).not.toMatch(/Google Fonts/i)
  })
```

- [ ] **Step 2: Run them and see them fail**

Run: `cd frontend && npx vitest run src/fonts.test.ts src/landing/PrivacyPage.test.tsx`. Expected: both new checks FAIL.

- [ ] **Step 3: Implement**

```bash
cd frontend && npm install @fontsource/inter @fontsource/space-grotesk @fontsource/jetbrains-mono
```

`main.tsx`, at the top, before `import './index.css'`:
```ts
// Self-hosted fonts (ticker links spec D11): bundled by Vite, so no request goes to
// Google. Only the weights the site uses.
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'
import '@fontsource/inter/800.css'
import '@fontsource/space-grotesk/500.css'
import '@fontsource/space-grotesk/600.css'
import '@fontsource/space-grotesk/700.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@fontsource/jetbrains-mono/600.css'
```
Delete line 1 (`@import url('https://fonts.googleapis.com/…')`) from both `src/landing/theme.css` and `src/index.css`.

`PrivacyPage.tsx`: delete the `<li>` with **Google Fonts** under "Who processes it".

- [ ] **Step 4: Run the tests, then build**

Run: `cd frontend && npx vitest run && npx tsc -b --force && npm run build`. Expected: all pass, and the build output lists `.woff2` files under `dist/assets/`.

Run `npm run dev`, open `http://localhost:5173/`, and confirm in DevTools → Network that nothing is requested from `fonts.googleapis.com` and the headings are in Space Grotesk.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/main.tsx frontend/src/landing/theme.css frontend/src/index.css frontend/src/fonts.test.ts frontend/src/landing/PrivacyPage.tsx frontend/src/landing/PrivacyPage.test.tsx
git commit -m "feat(fonts): self-host Inter, Space Grotesk and JetBrains Mono; privacy notice drops Google Fonts

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Deploy config, checklist updates, end-to-end check

**Files:**
- Modify: `cloudbuild.yaml` (add `SEC_USER_AGENT` to `--set-env-vars`)
- Modify: `DEPLOY.md` (env table row)
- Modify, **never commit**: `MonetizationPlan/Intrinsica_Fake_Door_Launch_Checklist.html`

- [ ] **Step 1: Add the env var**

In `cloudbuild.yaml`, append `,SEC_USER_AGENT=Intrinsica contact@intrinsica.io` to the `--set-env-vars=` value. The value contains a space, so quote the whole flag the way the file already quotes values with special characters. If it doesn't, switch that one argument to the `^##^` delimiter syntax: `--set-env-vars=^##^INTRINSICA_PUBLIC_MODE=1##…##SEC_USER_AGENT=Intrinsica contact@intrinsica.io`.

In `DEPLOY.md`'s env table, add the row `| SEC_USER_AGENT | Intrinsica contact@intrinsica.io | SEC requires a contact in the User-Agent to download its ticker list (ticker links spec §3) |`.

- [ ] **Step 2: Commit**

```bash
git add cloudbuild.yaml DEPLOY.md
git commit -m "chore(deploy): SEC_USER_AGENT for the ticker list

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 3: Update the checklist HTML (do not stage it)**

- **B3 section:** the "Engaged visitor" row becomes: A visitor with `analysis_completed` where `source` = `typed` **or** `link`: they analysed a stock themselves, or arrived on a `/t/` link and got its result. Leave out `source = sample`.
- **New section after B3, "How to tag your links":**
  - one table row per channel (`x`, `reddit`, `hn`, `google`, `indiehackers`, `producthunt`) with a ready link in the form `https://intrinsica.io/t/NVDA?utm_source=<channel>&utm_campaign=<your label>`;
  - a sentence that X Ads and Google Ads take the tagged link in their website-URL field;
  - a sentence to open each ad's link once before it goes live.
- **B1, B2 and B4 rows:** mark them done with the date and commit hashes.

- [ ] **Step 4: End-to-end check, local**

Run the backend with the frontend built into it:
```bash
cd frontend && VITE_PUBLIC_MODE=1 npm run build && cd ../backend && SEC_USER_AGENT="Intrinsica contact@intrinsica.io" INTRINSICA_PUBLIC_MODE=1 INTRINSICA_STATIC_DIR=../frontend/dist uvicorn main:app --port 8080
```
Then:
- `curl -s localhost:8080/t/nvda | grep og:image` shows `https://intrinsica.io/og/NVDA.png`;
- `curl -sI localhost:8080/og/XYZQ.png` gives 302 to `/og-image.png`;
- `localhost:8080/og/NVDA.png` in a browser shows the card;
- `localhost:8080/t/NVDA` at 390px width shows the headline, then NVDA's card, then the input;
- `localhost:8080/t/XYZQ` shows the AAPL example, the notice, and `/` in the address bar.

- [ ] **Step 5: Hand off**

Run the full backend and frontend verification commands from Global constraints, then use superpowers:finishing-a-development-branch. After deploy, the founder posts one test link on X (or uses a card validator) to confirm the card renders.
