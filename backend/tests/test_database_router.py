import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from main import app
from models import DatabaseRow
from screener.models import ScreenerResult

client = TestClient(app)


def test_database_includes_quality_score():
    with patch("routers.database.read_database",
               new=AsyncMock(return_value=[DatabaseRow(ticker="AAPL", quality_score=8.4)])):
        resp = client.get("/api/database")
    assert resp.json()["results"][0]["quality_score"] == 8.4


def test_screener_detail_endpoint():
    r = ScreenerResult(ticker="AAPL", quality_score=8.4, sector_profile="TECH_GROWTH")
    with patch("routers.database.read_screener_one", new=AsyncMock(return_value=r)):
        resp = client.get("/api/screener/AAPL")
    assert resp.json()["sector_profile"] == "TECH_GROWTH"


def test_screener_detail_not_found():
    with patch("routers.database.read_screener_one", new=AsyncMock(return_value=None)):
        resp = client.get("/api/screener/ZZZZ")
    assert resp.json().get("error")


def _patch_deletes(db=True, screener=True, tickers=True):
    return (
        patch("routers.database.delete_database_row", new=AsyncMock(return_value=db)),
        patch("routers.database.delete_screener_row", new=AsyncMock(return_value=screener)),
        patch("routers.database.delete_watchlist_row", new=AsyncMock(return_value=tickers)),
    )


def test_delete_removes_from_every_tab():
    a, b, c = _patch_deletes()
    with a as db, b as scr, c as tick:
        resp = client.delete("/api/database/aapl")
    body = resp.json()
    assert body["deleted"] is True and body["ticker"] == "AAPL"
    assert body["removed"] == {"database": True, "screener": True, "tickers": True}
    # the ticker is normalised once, before it reaches the Sheets layer
    for mock in (db, scr, tick):
        mock.assert_awaited_once_with("AAPL")


def test_delete_succeeds_when_only_the_database_row_exists():
    """A ticker evaluated before the Screener tab existed still deletes cleanly."""
    a, b, c = _patch_deletes(db=True, screener=False, tickers=False)
    with a, b, c:
        resp = client.delete("/api/database/AAPL")
    body = resp.json()
    assert body["deleted"] is True
    assert body["removed"] == {"database": True, "screener": False, "tickers": False}


def test_delete_unknown_ticker_reports_not_found():
    a, b, c = _patch_deletes(db=False, screener=False, tickers=False)
    with a, b, c:
        resp = client.delete("/api/database/ZZZZ")
    body = resp.json()
    assert body["deleted"] is False and "ZZZZ" in body["error"]


def test_delete_surfaces_sheets_failure():
    with patch("routers.database.delete_database_row",
               new=AsyncMock(side_effect=Exception("quota exceeded"))):
        resp = client.delete("/api/database/AAPL")
    body = resp.json()
    assert body["deleted"] is False and "quota exceeded" in body["error"]
