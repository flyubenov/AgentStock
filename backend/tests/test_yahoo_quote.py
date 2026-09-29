"""services/yahoo.py:fetch_quote / _fetch_quote_sync (lines ~61-101) had no test of
its own -- the landing-cache tests only ever patched fetch_quote at the point cache.py
imports it, which proves the cache *calls* it, never that it is actually unmemoized.
Adding an @lru_cache to _fetch_quote_sync tomorrow would leave every one of those
green while silently reintroducing the exact frozen-price bug this function exists to
avoid. These tests assert the real property, against the real function."""
from unittest.mock import patch

import pytest

import services.yahoo as yahoo


def test_fetch_quote_sync_carries_no_lru_cache():
    # A functools.lru_cache-wrapped callable always exposes cache_info/cache_clear.
    # _fetch_sync (the memoized sibling this function deliberately does not copy) has
    # them; _fetch_quote_sync must not.
    assert not hasattr(yahoo._fetch_quote_sync, "cache_info")
    assert not hasattr(yahoo._fetch_quote_sync, "cache_clear")
    assert hasattr(yahoo._fetch_sync, "cache_info")  # the contrast this guards against


async def test_fetch_quote_hits_yfinance_on_every_call_not_just_the_first():
    calls = []

    class _FakeTicker:
        def __init__(self, ticker):
            calls.append(ticker)

        @property
        def info(self):
            # A real, changing price on every fetch -- if _fetch_quote_sync were
            # memoized, the second call would never reach here at all and both
            # prices would come back identical.
            return {"currentPrice": 100.0 + len(calls)}

    with patch.object(yahoo.yf, "Ticker", _FakeTicker):
        first = await yahoo.fetch_quote("AAPL")
        second = await yahoo.fetch_quote("AAPL")

    assert len(calls) == 2
    assert first != second
    assert first == 101.0
    assert second == 102.0


async def test_fetch_quote_returns_none_rather_than_raising_when_price_missing():
    class _FakeTicker:
        def __init__(self, ticker):
            pass

        @property
        def info(self):
            return {}  # no currentPrice, no regularMarketPrice

    with patch.object(yahoo.yf, "Ticker", _FakeTicker):
        price = await yahoo.fetch_quote("ZZZZ")  # must not raise

    assert price is None


async def test_fetch_quote_returns_none_rather_than_raising_on_exception():
    class _FakeTicker:
        def __init__(self, ticker):
            raise RuntimeError("network exploded")

    with patch.object(yahoo.yf, "Ticker", _FakeTicker):
        price = await yahoo.fetch_quote("AAPL")  # must not raise

    assert price is None
