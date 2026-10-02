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
