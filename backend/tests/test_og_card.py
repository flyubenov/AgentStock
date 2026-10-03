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


def test_the_cache_evicts_oldest_first_and_redraws_an_evicted_ticker(monkeypatch):
    og_card._cache.clear()
    monkeypatch.setattr(og_card, "_MAX", 3)
    calls = []
    monkeypatch.setattr(og_card, "_draw", lambda t: calls.append(t) or t.encode())
    for t in ("A", "B", "C"):
        og_card.render_card(t)
    og_card.render_card("A")  # A becomes most recent; B is now oldest
    og_card.render_card("D")  # evicts B
    assert list(og_card._cache) == ["C", "A", "D"]
    calls.clear()
    og_card.render_card("A")
    assert calls == []
    og_card.render_card("B")
    assert calls == ["B"]
    og_card._cache.clear()


def test_concurrent_renders_past_the_cache_limit_do_not_raise(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    og_card._cache.clear()
    monkeypatch.setattr(og_card, "_MAX", 3)
    monkeypatch.setattr(og_card, "_draw", lambda t: t.encode())
    tickers = [f"T{i}" for i in range(10)] * 200
    with ThreadPoolExecutor(16) as ex:
        out = list(ex.map(og_card.render_card, tickers))
    assert out == [t.encode() for t in tickers]
    assert len(og_card._cache) <= 3
    og_card._cache.clear()


def test_a_slow_lookup_redirects_to_the_generic_card(client):
    import asyncio

    async def slow(t):
        await asyncio.sleep(5)
        return (True, "X")

    with patch("routers.og.lookup", new=slow), patch("routers.og._LOOKUP_TIMEOUT", 0.05):
        r = client.get("/og/NVDA.png", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/og-image.png"


def test_a_client_over_the_limit_gets_the_generic_card_not_a_429(client, monkeypatch):
    from routers import og
    monkeypatch.setattr(og._limiter, "limit", 1)
    og._limiter.hits.clear()
    assert client.get("/og/NVDA.png").status_code == 200
    with patch.object(og_card, "render_card", side_effect=AssertionError("must not draw")):
        r = client.get("/og/NVDA.png", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/og-image.png"
    og._limiter.hits.clear()
