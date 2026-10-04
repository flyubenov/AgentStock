import pytest
from unittest.mock import AsyncMock

def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")


@pytest.fixture(autouse=True)
def _no_currency_lookup(monkeypatch):
    """orchestrator.batch._run_one checks the reporting currency before running the
    engines. Tests that stub the engines must not reach Yahoo for that check, so it
    reads "no currency info" (decline nothing) unless a test patches it itself."""
    from orchestrator import batch
    monkeypatch.setattr(batch, "fetch_ticker_info", AsyncMock(return_value={}))
