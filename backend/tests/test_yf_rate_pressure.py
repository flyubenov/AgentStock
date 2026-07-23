"""The rate-limit pressure signal the batch orchestrator reads to slow itself down.

yfinance fetches swallow a 429 into bounded retries and then a None/raise, so the
batch layer had no way to know Yahoo was throttling and kept hammering just as hard.
note_rate_limit() lets a fetch flag the throttle; rate_limit_pressure() reports it
for a short window afterwards.
"""
import pytest
import services.yf_pool as pool


def test_rate_limit_pressure_starts_false():
    pool._last_rate_limit_at = 0.0
    assert pool.rate_limit_pressure() is False


def test_note_rate_limit_raises_pressure():
    pool._last_rate_limit_at = 0.0
    pool.note_rate_limit()
    assert pool.rate_limit_pressure() is True


def test_pressure_decays_after_window(monkeypatch):
    pool.note_rate_limit()
    assert pool.rate_limit_pressure() is True
    monkeypatch.setattr(pool, "_RATE_LIMIT_PRESSURE_WINDOW", 0.0)
    assert pool.rate_limit_pressure() is False


def test_fetch_sync_flags_rate_limit_pressure(monkeypatch):
    """Driving the real retry loop under a simulated 429 must record pressure so the
    batch orchestrator widens its pacing on the next ticker."""
    import services.yahoo as yahoo

    yahoo._fetch_sync.cache_clear()
    pool._last_rate_limit_at = 0.0
    monkeypatch.setattr(yahoo.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        yahoo.yf, "Ticker",
        lambda t: (_ for _ in ()).throw(Exception("Too Many Requests: rate limited")),
    )
    with pytest.raises(Exception):
        yahoo._fetch_sync("ZZZZ")
    yahoo._fetch_sync.cache_clear()
    assert pool.rate_limit_pressure() is True
