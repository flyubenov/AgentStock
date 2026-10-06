import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")


@pytest.fixture(autouse=True)
def _api_auth_disabled(monkeypatch):
    # A developer's backend/.env may set API_TOKEN (load_dotenv runs at import);
    # keep it from 401-ing the router tests. test_api_auth.py re-sets it per test.
    monkeypatch.delenv("API_TOKEN", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
