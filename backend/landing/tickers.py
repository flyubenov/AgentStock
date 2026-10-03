"""Ticker-link support (spec 2026-10-03 §3): normalisation, and (Task 2) the SEC list
of known US tickers. Mirrors frontend/src/landing/ticker.ts; ticker-cases.json pins
both. Canonical form uses a dot (BRK.B) because /api/landing/analyze validates that
shape; the SEC list is keyed by the dash form."""
from __future__ import annotations
import asyncio
import logging
import os
import re
import time

import httpx

log = logging.getLogger(__name__)

_SHAPE = re.compile(r"^[A-Z]{1,5}([.-][A-Z]{1,2})?$")


def normalize(raw: str) -> str | None:
    t = (raw or "").strip().upper()
    return t.replace("-", ".") if _SHAPE.match(t) else None


def sec_key(ticker: str) -> str:
    return ticker.replace(".", "-")


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
    # Note for later: branch `05-yfinance-replacement` has `services/sec/edgar_client.py`
    # with the same CIK map. When both branches are on `main`, switch to that client.
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
        if _failed_at is not None and _now() - _failed_at < _RETRY_AFTER:
            return _titles      # possibly stale, possibly None
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
