"""Security review 2026-10-06: production sends the standard browser security headers
and does not publish its API description."""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from main import create_app


async def _none(t):
    return (False, None)


@pytest.fixture(autouse=True)
def _no_network_lookup():
    with patch("spa.lookup", new=_none):
        yield


@pytest.fixture
def site(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>Intrinsica</title>", encoding="utf-8")
    return tmp_path


@pytest.fixture
def public(site):
    return TestClient(create_app(public_mode=True, static_dir=str(site), canonical_host=""))


@pytest.mark.parametrize("path", ["/", "/api/health", "/login", "/t/NVDA"])
def test_every_public_response_carries_the_security_headers(public, path):
    h = public.get(path).headers
    assert h["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in h["permissions-policy"]
    csp = h["content-security-policy"]
    for part in ["default-src 'self'", "script-src 'self'", "frame-ancestors 'none'",
                 "object-src 'none'", "base-uri 'self'"]:
        assert part in csp


def test_the_csp_allows_no_inline_or_foreign_scripts(public):
    csp = public.get("/").headers["content-security-policy"]
    script = [d for d in csp.split(";") if d.strip().startswith("script-src")][0]
    assert "unsafe" not in script and "http" not in script


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_the_api_description_is_not_published(public, path):
    r = public.get(path)
    assert r.status_code == 404
    assert "swagger" not in r.text.lower() and '"openapi"' not in r.text


def test_local_dev_keeps_its_docs_and_has_no_csp(site):
    dev = TestClient(create_app(public_mode=False, static_dir="", canonical_host=""))
    assert dev.get("/docs").status_code == 200
    assert "content-security-policy" not in dev.get("/api/health").headers
