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
