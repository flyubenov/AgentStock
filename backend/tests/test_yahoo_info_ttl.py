"""fetch_ticker_info / _fetch_sync (services/yahoo.py) memoizes with @lru_cache and no
TTL, so a long-lived server would hand back the exact same frozen `info` dict for the
rest of the process's life -- Task 8b's slow landing-cache layer expires after three
days and re-runs the engines expecting a genuine refresh, but they'd get the same
stale info back. _info_bucket() adds a time bucket to the cache key so old entries age
out via ordinary LRU eviction once _INFO_TTL seconds pass, while two calls inside one
bucket still dedupe to a single network fetch (the three engines that want the same
ticker's info start concurrently, seconds apart)."""
from unittest.mock import patch

import services.yahoo as yahoo

_INFO_A = {"symbol": "AAPL", "shortName": "Apple Inc.", "currentPrice": 100.0}
_INFO_B = {"symbol": "AAPL", "shortName": "Apple Inc.", "currentPrice": 200.0}


class _FakeTicker:
    """Records every construction and hands back the next queued info dict."""

    def __init__(self, calls: list, infos: list):
        self._calls = calls
        self._infos = infos

    def __call__(self, ticker):
        self._calls.append(ticker)
        idx = min(len(self._calls) - 1, len(self._infos) - 1)
        return _StubTicker(self._infos[idx])


class _StubTicker:
    def __init__(self, info):
        self.info = info


async def test_two_calls_inside_ttl_hit_network_once():
    yahoo._fetch_sync.cache_clear()
    calls: list = []
    fake = _FakeTicker(calls, [_INFO_A])

    with patch.object(yahoo.yf, "Ticker", fake):
        first = await yahoo.fetch_ticker_info("AAPL")
        second = await yahoo.fetch_ticker_info("AAPL")

    assert len(calls) == 1
    assert first == second == _INFO_A
    yahoo._fetch_sync.cache_clear()


async def test_call_after_ttl_elapses_hits_network_again():
    """Advances the clock (never sleeps) by far more than any reasonable TTL, via
    time.time -- deliberately not referencing the TTL bucket helper by name, so this
    stays a black-box check of the observable behaviour rather than the mechanism."""
    yahoo._fetch_sync.cache_clear()
    calls: list = []
    fake = _FakeTicker(calls, [_INFO_A, _INFO_B])
    real_time = yahoo.time.time()

    with patch.object(yahoo.yf, "Ticker", fake):
        with patch.object(yahoo.time, "time", lambda: real_time):
            first = await yahoo.fetch_ticker_info("AAPL")
        with patch.object(yahoo.time, "time", lambda: real_time + 100_000):
            second = await yahoo.fetch_ticker_info("AAPL")

    assert len(calls) == 2
    assert first == _INFO_A
    assert second == _INFO_B
    yahoo._fetch_sync.cache_clear()


async def test_different_tickers_inside_one_ttl_window_cached_independently():
    yahoo._fetch_sync.cache_clear()
    calls: list = []

    def fake_ticker(ticker):
        calls.append(ticker)
        return _StubTicker({"symbol": ticker, "shortName": ticker})

    with patch.object(yahoo.yf, "Ticker", fake_ticker):
        aapl_first = await yahoo.fetch_ticker_info("AAPL")
        msft_first = await yahoo.fetch_ticker_info("MSFT")
        aapl_second = await yahoo.fetch_ticker_info("AAPL")
        msft_second = await yahoo.fetch_ticker_info("MSFT")

    assert calls == ["AAPL", "MSFT"]  # one fetch per ticker, no cross-contamination
    assert aapl_first == aapl_second == {"symbol": "AAPL", "shortName": "AAPL"}
    assert msft_first == msft_second == {"symbol": "MSFT", "shortName": "MSFT"}
    yahoo._fetch_sync.cache_clear()
