from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app
from auth import docs_kwargs

client = TestClient(app)

TOKEN = "s3cret-token"


def _rows():
    return patch("routers.database.read_database", new=AsyncMock(return_value=[]))


def test_rejects_missing_token(monkeypatch):
    monkeypatch.setenv("API_TOKEN", TOKEN)
    with _rows():
        resp = client.get("/api/database")
    assert resp.status_code == 401


def test_rejects_wrong_token(monkeypatch):
    monkeypatch.setenv("API_TOKEN", TOKEN)
    with _rows():
        resp = client.get("/api/database", headers={"X-Api-Key": "nope"})
    assert resp.status_code == 401


def test_accepts_header_token(monkeypatch):
    monkeypatch.setenv("API_TOKEN", TOKEN)
    with _rows():
        resp = client.get("/api/database", headers={"X-Api-Key": TOKEN})
    assert resp.status_code == 200


def test_accepts_query_token_for_eventsource(monkeypatch):
    # EventSource cannot send headers, so /api/stream passes ?token=.
    monkeypatch.setenv("API_TOKEN", TOKEN)
    with _rows():
        resp = client.get(f"/api/database?token={TOKEN}")
    assert resp.status_code == 200


def test_destructive_endpoint_blocked_without_token(monkeypatch):
    monkeypatch.setenv("API_TOKEN", TOKEN)
    with patch("routers.database.delete_database_row", new=AsyncMock()) as delete:
        resp = client.delete("/api/database/AAPL")
    assert resp.status_code == 401
    delete.assert_not_called()


def test_health_is_open(monkeypatch):
    monkeypatch.setenv("API_TOKEN", TOKEN)
    assert client.get("/api/health").status_code == 200


def test_cors_preflight_is_open(monkeypatch):
    monkeypatch.setenv("API_TOKEN", TOKEN)
    resp = client.options(
        "/api/database",
        headers={"Origin": "http://localhost:5173",
                 "Access-Control-Request-Method": "GET",
                 "Access-Control-Request-Headers": "x-api-key"},
    )
    assert resp.status_code == 200


def test_401_carries_cors_headers(monkeypatch):
    # Without CORS headers the browser hides the 401 and the frontend can't
    # tell "bad token" from "backend down".
    monkeypatch.setenv("API_TOKEN", TOKEN)
    resp = client.get("/api/database", headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 401
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_no_token_configured_locally_stays_open(monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    with _rows():
        assert client.get("/api/database").status_code == 200


def test_no_token_configured_on_cloud_run_fails_closed(monkeypatch):
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.setenv("K_SERVICE", "agent-stock-api")
    with _rows():
        resp = client.get("/api/database")
    assert resp.status_code == 503


def test_docs_disabled_on_cloud_run(monkeypatch):
    monkeypatch.setenv("K_SERVICE", "agent-stock-api")
    assert docs_kwargs() == {"docs_url": None, "redoc_url": None, "openapi_url": None}


def test_docs_enabled_locally(monkeypatch):
    monkeypatch.delenv("K_SERVICE", raising=False)
    assert docs_kwargs() == {}


def test_configured_token_ignores_surrounding_whitespace(monkeypatch):
    # A secret created through a PowerShell pipe ends in "\r\n"; the user types
    # the bare token, which must still match.
    monkeypatch.setenv("API_TOKEN", TOKEN + "\r\n")
    with _rows():
        resp = client.get("/api/database", headers={"X-Api-Key": TOKEN})
    assert resp.status_code == 200
