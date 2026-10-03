import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import landing.tickers as tickers
from landing.tickers import normalize, sec_key

_CASES = json.loads((Path(__file__).resolve().parents[2]
                     / "frontend/src/landing/ticker-cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("raw,want", _CASES)
def test_normalize_matches_the_shared_table(raw, want):
    assert normalize(raw) == want


def test_sec_key_uses_the_dash_form():
    assert sec_key("BRK.B") == "BRK-B"
    assert sec_key("NVDA") == "NVDA"


_SAMPLE = json.loads((Path(__file__).parent / "fixtures/sec_company_tickers_sample.json")
                     .read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _fresh_list(monkeypatch):
    tickers._reset()
    monkeypatch.setenv("SEC_USER_AGENT", "Intrinsica contact@intrinsica.io")
    yield
    tickers._reset()


def _fetch_ok():
    return patch("landing.tickers._fetch_json", new=AsyncMock(return_value=_SAMPLE))


def test_a_listed_ticker_is_known_with_its_title():
    with _fetch_ok():
        assert asyncio.run(tickers.lookup("NVDA")) == (True, "NVIDIA CORP")


def test_a_class_share_is_found_by_its_dash_key():
    with _fetch_ok():
        assert asyncio.run(tickers.lookup("BRK.B")) == (True, "BERKSHIRE HATHAWAY INC")


def test_an_unlisted_ticker_is_not_known():
    with _fetch_ok():
        assert asyncio.run(tickers.lookup("XYZQ")) == (False, None)


def test_the_list_is_fetched_once_and_cached():
    with _fetch_ok() as fetch:
        asyncio.run(tickers.lookup("NVDA"))
        asyncio.run(tickers.lookup("AAPL"))
        assert fetch.await_count == 1


def test_the_cache_expires_after_seven_days(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(tickers, "_now", lambda: clock[0])
    with _fetch_ok() as fetch:
        asyncio.run(tickers.lookup("NVDA"))
        clock[0] += 7 * 24 * 3600 + 1
        asyncio.run(tickers.lookup("NVDA"))
        assert fetch.await_count == 2


def test_a_failed_fetch_means_unavailable_not_a_crash():
    with patch("landing.tickers._fetch_json", new=AsyncMock(side_effect=RuntimeError("down"))) as fetch:
        assert asyncio.run(tickers.lookup("NVDA")) == (False, None)
        assert asyncio.run(tickers.list_available()) is False
        # Second immediate lookup should not fetch again (retry-after protection)
        assert asyncio.run(tickers.lookup("AAPL")) == (False, None)
        assert fetch.await_count == 1


def test_without_a_user_agent_the_sec_is_never_called(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    with _fetch_ok() as fetch:
        assert asyncio.run(tickers.list_available()) is False
        fetch.assert_not_awaited()


def test_concurrent_burst_during_outage_fetches_once():
    """During an SEC outage, N concurrent requests should fetch once, not N times."""
    with patch("landing.tickers._fetch_json", new=AsyncMock(side_effect=RuntimeError("down"))) as fetch:
        async def burst():
            return await asyncio.gather(*[tickers.lookup("NVDA") for _ in range(5)])
        results = asyncio.run(burst())
        # All 5 requests should get (False, None)
        assert all(r == (False, None) for r in results)
        # But only 1 fetch attempt (others queued on lock and found retry-after in effect)
        assert fetch.await_count == 1
