from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app
from models import Watchlist

client = TestClient(app)


def test_get_watchlists_returns_results():
    wls = [Watchlist(name="Cheap quality", filter={"quality": {"min": 8}}, created="t")]
    with patch("routers.watchlists.read_watchlists", new=AsyncMock(return_value=wls)):
        resp = client.get("/api/watchlists")
    body = resp.json()
    assert body["results"][0]["name"] == "Cheap quality"
    assert body["results"][0]["filter"] == {"quality": {"min": 8}}


def test_get_watchlists_surfaces_error():
    with patch("routers.watchlists.read_watchlists",
               new=AsyncMock(side_effect=Exception("quota exceeded"))):
        resp = client.get("/api/watchlists")
    body = resp.json()
    assert "quota exceeded" in body["error"] and body["results"] == []


def test_put_watchlist_saves():
    saved = Watchlist(name="Momentum", filter={"gap": {"max": -20}}, created="t")
    with patch("routers.watchlists.save_watchlist",
               new=AsyncMock(return_value=saved)) as m:
        resp = client.put("/api/watchlists/Momentum",
                          json={"filter": {"gap": {"max": -20}}})
    body = resp.json()
    assert body["saved"] is True and body["name"] == "Momentum"
    m.assert_awaited_once_with("Momentum", {"gap": {"max": -20}})


def test_put_watchlist_rejects_blank_name():
    with patch("routers.watchlists.save_watchlist", new=AsyncMock()) as m:
        resp = client.put("/api/watchlists/%20", json={"filter": {}})
    body = resp.json()
    assert body["saved"] is False and "name" in body["error"].lower()
    m.assert_not_awaited()


def test_delete_watchlist_removes():
    with patch("routers.watchlists.delete_watchlist",
               new=AsyncMock(return_value=True)):
        resp = client.delete("/api/watchlists/Momentum")
    assert resp.json() == {"deleted": True, "name": "Momentum"}


def test_delete_watchlist_not_found():
    with patch("routers.watchlists.delete_watchlist",
               new=AsyncMock(return_value=False)):
        resp = client.delete("/api/watchlists/Nope")
    body = resp.json()
    assert body["deleted"] is False and "Nope" in body["error"]
