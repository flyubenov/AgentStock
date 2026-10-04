"""Foreign-currency reporters are declined before any engine runs.

Yahoo reports a US-listed foreign company's price, market cap and trailing EPS in
dollars but its statements, forward EPS and book value in the company's own
currency (KSPI: KZT; TSM: TWD; TM: JPY). Nothing converts between them, so every
engine mixes the two: TM showed a fair value of $8,924 (+4,817%), KSPI an earnings
yield of 7234%. Until a real conversion exists the ticker is declined outright,
with the same reader-facing message the SEC data path uses."""
import pytest
from unittest.mock import AsyncMock, patch

from orchestrator import batch
from landing.contract import build_ticker_payload
from models import TickerResult
from screener.models import ScreenerResult
from risk_reward.models import RiskRewardResult

KSPI_INFO = {"symbol": "KSPI", "shortName": "Kaspi.kz", "currency": "USD",
             "financialCurrency": "KZT", "currentPrice": 94.05}


def _engines():
    fv = TickerResult(ticker="AAPL", status="completed", fair_value=180.0, current_price=190.0)
    sc = ScreenerResult(ticker="AAPL", status="completed", quality_score=8.4)
    rr = RiskRewardResult(ticker="AAPL", status="completed", ratio=1.85,
                          tier="Reward-Favored", reward_score=4.1, risk_score=2.2)
    return (AsyncMock(return_value=fv), AsyncMock(return_value=sc), AsyncMock(return_value=rr))


def _patched(info, engines, upsert=None):
    fv, sc, rr = engines
    fetch = AsyncMock(side_effect=info) if isinstance(info, Exception) else AsyncMock(return_value=info)
    return [
        patch("orchestrator.batch.fetch_ticker_info", new=fetch),
        patch("orchestrator.batch.engine_run", new=fv),
        patch("orchestrator.batch.screener_run", new=sc),
        patch("orchestrator.batch.risk_reward_run", new=rr),
        patch("orchestrator.batch.upsert_result", new=upsert or AsyncMock()),
        patch("orchestrator.batch.upsert_screener_result", new=AsyncMock()),
        patch("orchestrator.batch.upsert_risk_reward_result", new=AsyncMock()),
    ]


async def _run(info, engines, upsert=None, persist=True):
    ps = _patched(info, engines, upsert)
    for p in ps:
        p.start()
    try:
        return await batch._run_one("KSPI", persist=persist)
    finally:
        for p in ps:
            p.stop()


@pytest.mark.asyncio
async def test_foreign_currency_reporter_is_declined_before_any_engine():
    engines = _engines()
    out = await _run(KSPI_INFO, engines)
    for e in engines:
        e.assert_not_awaited()
    r = out["result"]
    assert out["fv_failed"] is True
    assert r["status"] == "failed"
    assert r["errors"] == [batch.UNSUPPORTED_CURRENCY_MESSAGE]
    assert r["screener"] is None and r["risk_reward"] is None
    assert r["fair_value"] is None
    # Identity still shows on the card.
    assert r["ticker"] == "KSPI" and r["company_name"] == "Kaspi.kz"
    assert r["current_price"] == 94.05


@pytest.mark.asyncio
async def test_declined_reporter_blanks_its_database_row():
    # A stale fair value in the analyst Database is worse than a blank one (see the
    # persist comment in _run_one): the decline is written like any other decline.
    upsert = AsyncMock()
    await _run(KSPI_INFO, _engines(), upsert=upsert)
    upsert.assert_awaited_once()
    assert upsert.await_args.args[0].fair_value is None


@pytest.mark.asyncio
async def test_landing_run_of_a_declined_reporter_writes_nothing():
    upsert = AsyncMock()
    await _run(KSPI_INFO, _engines(), upsert=upsert, persist=False)
    upsert.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("info", [
    {"symbol": "AAPL", "currency": "USD", "financialCurrency": "USD"},
    {"symbol": "AAPL", "currency": "USD", "financialCurrency": "usd"},
    {"symbol": "AAPL", "currency": "USD"},            # no financialCurrency reported
    {"symbol": "AAPL", "financialCurrency": "EUR"},   # no trading currency reported
    {},
])
async def test_same_or_unknown_currency_runs_the_engines(info):
    engines = _engines()
    out = await _run(info, engines)
    for e in engines:
        e.assert_awaited_once()
    assert out["result"]["status"] == "completed"


@pytest.mark.asyncio
async def test_a_failed_info_fetch_leaves_the_decision_to_the_engines():
    engines = _engines()
    out = await _run(ValueError("yahoo down"), engines)
    for e in engines:
        e.assert_awaited_once()
    assert out["result"]["status"] == "completed"


def test_the_decline_message_reaches_the_public_payload_unchanged():
    payload = build_ticker_payload({
        "ticker": "KSPI", "company_name": "Kaspi.kz", "current_price": 94.05,
        "status": "failed", "errors": [batch.UNSUPPORTED_CURRENCY_MESSAGE],
        "screener": None, "risk_reward": None,
    })
    assert payload["errors"] == [batch.UNSUPPORTED_CURRENCY_MESSAGE]
    assert payload["quality"] is None and payload["fair_value"] is None


def test_the_frontend_matches_this_exact_message():
    # The page recognises the decline by its exact text (frontend/src/landing/format.ts
    # UNSUPPORTED_CURRENCY) to say why instead of "couldn't find"; a reworded message
    # here would silently bring the false "couldn't find" back.
    from pathlib import Path
    src = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "landing" / "format.ts").read_text(encoding="utf-8")
    assert f'UNSUPPORTED_CURRENCY = "{batch.UNSUPPORTED_CURRENCY_MESSAGE}"' in src
