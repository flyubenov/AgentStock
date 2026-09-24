from __future__ import annotations

import asyncio
import dataclasses
import os
import time
from collections import OrderedDict
from datetime import datetime, timezone

from orchestrator.batch import _run_one_guarded
from services.yahoo import fetch_ticker_info
from risk_reward.data import fetch_risk_reward_inputs
from risk_reward.scoring import build_metric_scores, aggregate
from risk_reward.models import RiskRewardInputs, RiskRewardResult
# Reused verbatim so the fast-refresh snapshot is built by the exact same code as a
# normal risk_reward.engine.run() -- no scoring/aggregation/snapshot logic is ever
# duplicated here, only the (unavoidable) glue that assembles a result from an
# already-fetched RiskRewardInputs instead of fetching one.
from risk_reward.engine import _snapshot as _rr_snapshot

# Two-speed freshness (spec S12.1). Fundamentals (Quality, Moat, Fair Value $/share)
# move on earnings, not on days, so the whole _run_one-shaped result is cached for
# days. Price and Reward/Risk are price-sensitive (R-R reads discount-to-52-week-high,
# trend vs 200-day, RSI, volatility and beta) so they refresh far more often. Both are
# env-tunable without a deploy.
SLOW_TTL = float(os.getenv("LANDING_SLOW_TTL", "259200"))   # 3 days
FAST_TTL = float(os.getenv("LANDING_FAST_TTL", "900"))      # 15 minutes

# A crawler hitting this public, unauthenticated endpoint with fresh tickers must not
# grow the cache without bound. Marquee tickers are seeded and re-touched on every
# page view, so normal traffic keeps them resident without a separate pinning
# mechanism -- LRU alone is enough.
MAX_ENTRIES = 64

# Clock indirection so tests can advance time without sleeping (monkeypatch this name).
_now = time.monotonic

# Cache key: ticker.strip().upper() -- the same normalization the router already does
# before calling us, applied again here so the module is safe to call standalone.
#
# Slow layer entry:  {"result": <_run_one-shaped dump>, "inputs": RiskRewardInputs | None, "ts": float}
#   "inputs" is the RiskRewardInputs snapshot fetched alongside the same
#   _run_one_guarded run, kept so a fast refresh can recompute Reward/Risk from a
#   fresh price without re-fetching price history / the income statement (the
#   expensive two-thirds of risk_reward.data.fetch_risk_reward_inputs). None when
#   that side-fetch itself failed -- the main slow-layer result still stands, but a
#   fast refresh degrades to "no cached inputs to refresh from" until the next slow
#   repopulation.
#
# Fast layer entry:  {"price": float | None, "rr": <RiskRewardResult dump> | None, "ts": float}
_slow: "OrderedDict[str, dict]" = OrderedDict()
_fast: "OrderedDict[str, dict]" = OrderedDict()
_locks: dict[str, asyncio.Lock] = {}

# Yahoo's own forwardPE / priceToSalesTrailing12Months / pegRatio are baked in
# against the price at the moment `info` was fetched. Each is exactly linear in
# price with its other term fixed over a 15-minute window (forwardPE = price /
# forwardEPS, priceToSales = price / salesPerShare, pegRatio = PE / growth), so a
# fast refresh rescales each by fresh_price / cached_price -- exact arithmetic, not
# an estimate. No other `info` key is touched: rsi, volatility, beta and every
# fundamental are real series statistics that don't meaningfully move on one fresh
# tick, and are correctly left stale until the next slow-layer repopulation.
_RESCALED_INFO_KEYS = ("forwardPE", "priceToSalesTrailing12Months", "pegRatio")


def _lock_for(key: str) -> asyncio.Lock:
    lock = _locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _locks[key] = lock
    return lock


def _maybe_drop_lock(key: str) -> None:
    """Once a ticker is gone from both layers its lock can go too, so a crawler
    hammering fresh tickers doesn't leak one asyncio.Lock per distinct ticker seen
    forever."""
    if key not in _slow and key not in _fast:
        _locks.pop(key, None)


def _evict(d: "OrderedDict[str, dict]") -> None:
    while len(d) > MAX_ENTRIES:
        oldest_key, _ = d.popitem(last=False)
        _maybe_drop_lock(oldest_key)


def _rescale_inputs(inp: RiskRewardInputs, fresh_price: float) -> RiskRewardInputs:
    """Copy of `inp` with a fresh price for a fast-layer refresh -- see
    _RESCALED_INFO_KEYS for exactly which derived info keys move with it."""
    cached_price = inp.price
    if not cached_price:
        # No baseline price to rescale against (the slow-layer snapshot never
        # resolved one) -- use the fresh price outright rather than divide by
        # zero/None, and leave info untouched.
        return dataclasses.replace(inp, price=fresh_price)
    ratio = fresh_price / cached_price
    info = dict(inp.info)
    for key in _RESCALED_INFO_KEYS:
        val = info.get(key)
        if val is not None:
            info[key] = val * ratio
    return dataclasses.replace(inp, price=fresh_price, info=info)


async def _populate_slow(key: str, ts: float) -> dict:
    """Run the full pipeline (fair_value + screener + risk_reward, with the Sheets
    upserts) and, alongside it, fetch a fresh RiskRewardInputs snapshot to seed
    future fast-layer refreshes from. The two run concurrently. A failure of the
    side-fetch degrades to inputs=None (the main result still stands); a failure of
    _run_one_guarded itself propagates -- there is no result to cache at all."""
    run_out, inputs_or_exc = await asyncio.gather(
        _run_one_guarded(key), fetch_risk_reward_inputs(key), return_exceptions=True)
    if isinstance(run_out, Exception):
        raise run_out
    inputs = None if isinstance(inputs_or_exc, Exception) else inputs_or_exc
    return {"result": run_out["result"], "inputs": inputs, "ts": ts}


async def _refresh_fast(slow_entry: dict) -> tuple[float | None, dict | None]:
    """One quote fetch (a single call) plus the existing, un-duplicated pure scoring
    (build_metric_scores + aggregate) re-run on a price-refreshed copy of the cached
    RiskRewardInputs -- one cheap call instead of risk_reward.engine.run's full
    three-call fetch."""
    inputs: RiskRewardInputs | None = slow_entry.get("inputs")
    if inputs is None:
        raise RuntimeError("no cached risk-reward inputs available to refresh from")
    quote = await fetch_ticker_info(inputs.ticker)
    fresh_price = quote.get("currentPrice") or quote.get("regularMarketPrice")
    if not fresh_price:
        raise RuntimeError("quote fetch returned no usable price")
    refreshed = _rescale_inputs(inputs, fresh_price)
    scores = build_metric_scores(refreshed)
    agg = aggregate(scores)
    rr_dump = RiskRewardResult(
        ticker=refreshed.ticker, company_name=refreshed.company_name,
        current_price=refreshed.price,
        last_evaluated=datetime.now(timezone.utc).isoformat(),
        ratio=agg.ratio, tier=agg.tier, reward_score=agg.reward, risk_score=agg.risk,
        actionable_insight=agg.insight, metric_scores=scores,
        raw_snapshot=_rr_snapshot(refreshed), status=agg.status, errors=[],
    ).model_dump()
    return fresh_price, rr_dump


async def get_analysis(ticker: str) -> dict:
    """The _run_one-shaped result dict for one ticker, served from cache when fresh.
    Never raises for a cache-layer failure -- a refresh failure serves the stale
    entry; only a cold miss whose engine run itself fails propagates (the router's
    existing per-ticker error handling turns that into an error payload, unchanged)."""
    key = ticker.strip().upper()
    lock = _lock_for(key)
    async with lock:
        now = _now()

        slow = _slow.get(key)
        just_refreshed_slow = False
        if slow is None or (now - slow["ts"]) >= SLOW_TTL:
            try:
                slow = await _populate_slow(key, now)
            except Exception:
                if slow is not None:
                    # Fundamentals refresh failed but stale ones exist -- degrade,
                    # same "stale beats broken" principle as the fast layer.
                    _slow.move_to_end(key)
                else:
                    raise
            else:
                _slow[key] = slow
                _slow.move_to_end(key)
                _evict(_slow)
                just_refreshed_slow = True
        else:
            _slow.move_to_end(key)

        fast = _fast.get(key)
        if just_refreshed_slow:
            # Fresh fundamentals just landed in the same call -- seed the fast layer
            # from that same snapshot's own price/risk_reward instead of an
            # immediately-redundant quote fetch. Its own 15-minute clock starts now.
            dump = slow["result"]
            fast = {"price": dump.get("current_price"), "rr": dump.get("risk_reward"), "ts": now}
            _fast[key] = fast
            _fast.move_to_end(key)
            _evict(_fast)
        elif fast is None or (now - fast["ts"]) >= FAST_TTL:
            try:
                price, rr_dump = await _refresh_fast(slow)
            except Exception:
                if fast is not None:
                    _fast.move_to_end(key)
                else:
                    dump = slow["result"]
                    fast = {"price": dump.get("current_price"), "rr": dump.get("risk_reward"), "ts": now}
                    _fast[key] = fast
                    _fast.move_to_end(key)
                    _evict(_fast)
            else:
                fast = {"price": price, "rr": rr_dump, "ts": now}
                _fast[key] = fast
                _fast.move_to_end(key)
                _evict(_fast)
        else:
            _fast.move_to_end(key)

    result = dict(slow["result"])
    price = fast.get("price") if fast else result.get("current_price")
    result["current_price"] = price
    result["risk_reward"] = fast.get("rr") if fast else result.get("risk_reward")
    fair_value = result.get("fair_value")
    if fair_value is not None and price:
        result["price_vs_fair_value_pct"] = round((fair_value - price) / price * 100, 2)
    else:
        result["price_vs_fair_value_pct"] = None
    return result


async def seed(tickers: list[str]) -> None:
    """Warm the slow layer for each ticker. Safe to call at startup: a failure for
    one ticker (or all of them, e.g. a Yahoo outage at boot) never raises -- it just
    leaves that ticker's cache entry cold for the first real visitor."""
    for t in tickers:
        try:
            await get_analysis(t)
        except Exception:
            pass


def cache_stats() -> dict:
    return {"slow": len(_slow), "fast": len(_fast)}
