import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from main import create_app


_INDEX = """<!doctype html><html><head>
<title>Intrinsica</title>
<meta property="og:title" content="Intrinsica — Judge the business. Then judge the price." />
<meta property="og:image" content="https://intrinsica.io/og-image.png" />
<meta property="og:url" content="https://intrinsica.io/" />
<meta name="twitter:image" content="https://intrinsica.io/og-image.png" />
</head><body></body></html>"""


async def _none(t):
    return (False, None)


@pytest.fixture(autouse=True)
def _no_network_lookup():
    # The real lookup may hit the SEC list; no test here may reach the network.
    with patch("spa.lookup", new=_none):
        yield


@pytest.fixture
def static_dir(tmp_path):
    site = tmp_path / "site"
    (site / "assets").mkdir(parents=True)
    (site / "index.html").write_text(_INDEX, encoding="utf-8")
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


@pytest.mark.parametrize("path", ["/checkout", "/privacy", "/t/AMZN", "/app", "/database"])
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


@pytest.mark.parametrize("path", ["../secret.txt", "assets/../../secret.txt", "..\secret.txt"])
def test_the_guard_itself_refuses_traversal(static_dir, path):
    # The HTTP client normalises ../ before the request leaves, so the cases above may
    # never reach the guard; call the route function directly to pin it.
    import asyncio
    from fastapi import FastAPI
    from spa import mount_spa
    app = FastAPI()
    mount_spa(app, str(static_dir))
    endpoint = [r for r in app.routes if getattr(r, "path", "") == "/{path:path}"][0].endpoint
    resp = asyncio.run(endpoint(path))
    assert pathlib_name(resp) == "index.html"


def pathlib_name(resp) -> str:
    import pathlib
    return pathlib.Path(resp.path).name


@pytest.mark.parametrize("path", ["/", "/t/AMZN", "/og-image.png"])
def test_head_requests_are_answered_like_get(client, path):
    # Uptime monitors and link-preview crawlers probe with HEAD; a 405 reads as "down".
    r = client.head(path)
    assert r.status_code == 200


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


def test_a_slow_ticker_lookup_serves_the_untouched_page(client):
    # A cold instance may still be downloading the SEC list; X's crawler gives up
    # after a few seconds, so the page is served generic rather than late.
    import asyncio

    async def slow(t):
        await asyncio.sleep(5)
        return (True, "X")

    with patch("spa.lookup", new=slow), patch("spa._LOOKUP_TIMEOUT", 0.05):
        r = client.get("/t/NVDA")
    assert r.status_code == 200
    assert "og/NVDA.png" not in r.text
    assert "<title>Intrinsica</title>" in r.text


def test_startup_warms_the_sec_list_and_a_failure_cannot_stop_startup():
    import main
    calls = []

    async def boom():
        calls.append(1)
        raise RuntimeError("SEC down")

    with patch("main.list_available", new=boom), patch("main.seed", new=lambda tickers: _noop()):
        with TestClient(create_app(public_mode=True, static_dir="", canonical_host="")) as c:
            assert c.get("/api/health").status_code in (200, 404)
    assert calls == [1]


async def _noop():
    return None
