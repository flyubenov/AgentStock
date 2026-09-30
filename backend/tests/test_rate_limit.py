from types import SimpleNamespace

from services.rate_limit import RateLimiter, client_key


def _req(headers: dict[str, str] | None = None, host: str | None = "127.0.0.1"):
    return SimpleNamespace(headers=headers or {},
                           client=SimpleNamespace(host=host) if host else None)


def test_allows_up_to_the_limit_then_refuses():
    lim = RateLimiter(limit=2, window_seconds=60, now=lambda: 100.0)
    assert not lim.limited("ip")
    assert not lim.limited("ip")
    assert lim.limited("ip")


def test_the_limit_frees_up_once_the_window_passes():
    t = [100.0]
    lim = RateLimiter(limit=2, window_seconds=60, now=lambda: t[0])
    assert not lim.limited("ip")
    assert not lim.limited("ip")
    assert lim.limited("ip")
    t[0] += 60
    assert not lim.limited("ip")


def test_clients_are_counted_separately():
    lim = RateLimiter(limit=1, window_seconds=60, now=lambda: 0.0)
    assert not lim.limited("a")
    assert lim.limited("a")
    assert not lim.limited("b")


def test_forgets_the_least_recent_client_past_its_bound():
    lim = RateLimiter(limit=5, window_seconds=60, max_clients=3, now=lambda: 0.0)
    for ip in ["a", "b", "c", "d"]:
        lim.limited(ip)
    assert list(lim.hits) == ["b", "c", "d"]


def test_clear_forgets_everyone():
    lim = RateLimiter(limit=1, window_seconds=60, now=lambda: 0.0)
    lim.limited("a")
    lim.clear()
    assert not lim.limited("a")


def test_client_key_uses_the_right_most_forwarded_for_entry():
    # Cloud Run's front end APPENDS the address it saw; anything left of it is client-supplied.
    assert client_key(_req({"x-forwarded-for": "10.0.0.1, 203.0.113.7"})) == "203.0.113.7"


def test_client_key_falls_back_to_the_socket_peer_then_unknown():
    assert client_key(_req()) == "127.0.0.1"
    assert client_key(_req(host=None)) == "unknown"
