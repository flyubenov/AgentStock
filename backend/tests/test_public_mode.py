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
