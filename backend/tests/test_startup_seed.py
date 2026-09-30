import asyncio

from fastapi.testclient import TestClient

import main


def _app():
    return main.create_app(public_mode=True, static_dir="", canonical_host="")


def test_startup_waits_for_the_seed_when_a_wait_is_configured(monkeypatch):
    # Cloud Run bills CPU per request, so a background seed would be starved right after
    # a deploy. With LANDING_SEED_WAIT_SECONDS set, startup (which has boosted CPU and a
    # long probe window) finishes the pre-warm before the revision takes traffic.
    done = []

    async def fake_seed(tickers):
        await asyncio.sleep(0.05)
        done.append(list(tickers))

    monkeypatch.setattr(main, "seed", fake_seed)
    monkeypatch.setenv("LANDING_SEED_WAIT_SECONDS", "5")
    with TestClient(_app()):
        assert done == [main.LANDING_MARQUEE_TICKERS]


def test_a_slow_seed_never_blocks_startup_past_the_bound(monkeypatch):
    finished = []

    async def stuck_seed(tickers):
        try:
            await asyncio.sleep(60)
        finally:
            finished.append(True)

    monkeypatch.setattr(main, "seed", stuck_seed)
    monkeypatch.setenv("LANDING_SEED_WAIT_SECONDS", "0.1")
    with TestClient(_app()) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
        assert finished == []           # the timeout must not cancel the seed itself
    assert finished == [True]           # shutdown cancels and awaits it


def test_default_is_fire_and_forget(monkeypatch):
    # Local dev and every other test: no waiting, exactly as before.
    started = []

    async def slow_seed(tickers):
        started.append(True)
        await asyncio.sleep(60)

    monkeypatch.setattr(main, "seed", slow_seed)
    monkeypatch.delenv("LANDING_SEED_WAIT_SECONDS", raising=False)
    with TestClient(_app()) as client:
        assert client.get("/api/health").status_code == 200
