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
