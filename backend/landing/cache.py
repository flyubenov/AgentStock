from __future__ import annotations

import asyncio
import dataclasses
import os
import time
from collections import OrderedDict
from datetime import datetime, timezone

from orchestrator.batch import _run_one_guarded
from services.yahoo import fetch_quote
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
# set via env vars, read once at import -- changing either still means a new Cloud Run
# revision (a redeploy), not a live-tunable dial; "no code change" is the accurate
# claim, not "no deploy".
SLOW_TTL = float(os.getenv("LANDING_SLOW_TTL", "259200"))   # 3 days
# 1 hour, not 15 minutes: the core assessments move on earnings, not intraday, and
# Yahoo is not licensed for commercial use -- every avoided call reduces exposure.
FAST_TTL = float(os.getenv("LANDING_FAST_TTL", "3600"))
# A failed fast refresh (Yahoo hiccup, rate limit) keeps serving the stale price/R-R
# per the degradation rule below, but must not sit at the *old* timestamp -- that
# would leave it permanently "expired", so every subsequent view would re-attempt the
# quote fetch's own ~9s blocking rate-limit retry loop while holding this ticker's
# lock (a Yahoo wobble becoming a per-view retry storm). Stamping a fresh ts with this
# short backoff instead means at most one retry per LANDING_FAST_NEGATIVE_TTL, not one
# per view.
FAST_NEGATIVE_TTL = float(os.getenv("LANDING_FAST_NEGATIVE_TTL", "60"))
# The timeout on a fast-layer refresh's network leg specifically. yf.Ticker().info
# (via fetch_quote) accepts no timeout of its own -- see _HISTORY_TIMEOUT in
# services/yahoo.py for why that matters -- and the per-ticker lock is held across
# this await, so an unbounded call would queue every concurrent viewer of that ticker
# behind one stuck socket. A few seconds is plenty for a quote.
FAST_REFRESH_TIMEOUT = float(os.getenv("LANDING_FAST_REFRESH_TIMEOUT", "5"))

# A crawler hitting this public, unauthenticated endpoint with fresh tickers must not
# grow the cache without bound. Marquee tickers are seeded and re-touched on every
# page view, so normal traffic keeps them resident without a separate pinning
# mechanism -- LRU alone is enough.
MAX_ENTRIES = 64

# Clock indirection so tests can advance time without sleeping (monkeypatch this name).
_now = time.monotonic

# This module's state is a single process's in-memory dict. Each backend instance
# (Cloud Run can and will run more than one, and scale-to-zero throws it away entirely
# between idle periods) holds its own independent cache and re-seeds cold on its own
# startup -- the Sheets-write and Yahoo-call reduction this cache exists to provide is
# per-instance, not a global guarantee across the fleet.
#
# Cache key: ticker.strip().upper() -- the same normalization the router already does
# before calling us, applied again here so the module is safe to call standalone.
#
# Slow layer entry:  {"result": <_run_one-shaped dump>, "inputs": RiskRewardInputs | None,
#                      "ts": float, "failed": bool}
#   "inputs" is the RiskRewardInputs snapshot fetched alongside the same
#   _run_one_guarded run, kept so a fast refresh can recompute Reward/Risk from a
#   fresh price without re-fetching price history / the income statement (the
#   expensive two-thirds of risk_reward.data.fetch_risk_reward_inputs). None when
#   that side-fetch itself failed -- the main slow-layer result still stands, but a
#   fast refresh degrades to "no cached inputs to refresh from" until the next slow
#   repopulation.
#   "failed" is True when _run_one_guarded itself completed but declined the ticker
#   (fv_failed) -- a dead ticker or a Yahoo outage does not raise, it returns a
#   status="failed" dump, and that must not be pinned as truth for a full 3 days (see
#   get_analysis: a failed slow entry is retried after FAST_TTL, not SLOW_TTL).
#
# Fast layer entry:  {"price": float | None, "rr": <RiskRewardResult dump> | None,
#                      "ts": float, "failed": bool}
#   "failed" is True when the fast refresh itself raised (quote fetch failed/timed
#   out) and the entry is holding stale data -- get_analysis then retries after the
#   shorter FAST_NEGATIVE_TTL, not the full FAST_TTL.
_slow: "OrderedDict[str, dict]" = OrderedDict()
_fast: "OrderedDict[str, dict]" = OrderedDict()

# Per-ticker single-flight locks, refcounted (see _acquire_lock/_release_lock): a lock
# is only ever dropped once nobody is waiting on or holding it, never merely because
# its cache entry was LRU-evicted. Evicting a lock out from under an in-flight holder
# would let the next caller for that ticker create a fresh, unlocked Lock and start a
# second concurrent engine run (and a second Sheets upsert) for the same ticker --
# precisely under the crawler pressure MAX_ENTRIES exists to contain.
_locks: dict[str, asyncio.Lock] = {}
_lock_refs: dict[str, int] = {}

# Yahoo's own forwardPE / priceToSalesTrailing12Months / pegRatio / trailingPegRatio
# are baked in against the price at the moment `info` was fetched. Each is exactly
# linear in price with its other term fixed over the fast-layer's refresh window
# (forwardPE = price / forwardEPS, priceToSales = price / salesPerShare,
# peg(Ratio) = PE / growth), so a fast refresh rescales each by
# fresh_price / cached_price -- exact arithmetic, not an estimate. Nothing else in
# `info` is touched -- `beta` is a real info key but not price-derived, so it's left
# alone. `rsi` and `volatility` are not `info` keys at all: they're RiskRewardInputs'
# own dataclass fields (inp.rsi / inp.volatility, populated once from the price
# history at slow-layer fill time) and are correctly left stale until the next slow
# repopulation, same as every fundamental.
_RESCALED_INFO_KEYS = ("forwardPE", "priceToSalesTrailing12Months",
                       "pegRatio", "trailingPegRatio")


def _acquire_lock(key: str) -> asyncio.Lock:
    """Claim this ticker's lock for the duration of one get_analysis call, creating it
    on first use. Must be paired with _release_lock in a finally."""
    lock = _locks.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _locks[key] = lock
    _lock_refs[key] = _lock_refs.get(key, 0) + 1
    return lock


def _release_lock(key: str) -> None:
    """Release this call's claim. Only once nobody else holds a claim (refcount back
    to 0) -- and the lock genuinely isn't locked, belt-and-suspenders -- is it dropped
    from _locks, so a crawler hammering fresh tickers doesn't leak one asyncio.Lock
    per distinct ticker seen forever."""
    remaining = _lock_refs.get(key, 0) - 1
    if remaining <= 0:
        _lock_refs.pop(key, None)
        lock = _locks.get(key)
        if lock is not None and not lock.locked():
            _locks.pop(key, None)
    else:
        _lock_refs[key] = remaining


def _touch(d: "OrderedDict[str, dict]", key: str) -> None:
    """move_to_end for LRU recency, guarded: `key` may already be gone by the time
    this runs -- a concurrent get_analysis call for a *different* ticker can evict it
    via _evict while this call is mid-await (the two hold different per-ticker locks,
    so nothing prevents that race). That must degrade quietly, not raise -- especially
    on the failure-handling paths, where a KeyError here would turn "serve stale" into
    an unhandled exception, exactly backwards."""
    if key in d:
        d.move_to_end(key)


def _evict(d: "OrderedDict[str, dict]") -> None:
    while len(d) > MAX_ENTRIES:
        d.popitem(last=False)


def _rescale_inputs(inp: RiskRewardInputs, fresh_price: float) -> RiskRewardInputs:
    """Copy of `inp` with a fresh price for a fast-layer refresh -- see
    _RESCALED_INFO_KEYS for exactly which derived info keys move with it. `inp` itself
    is never mutated."""
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
    _run_one_guarded itself propagates -- there is no result to cache at all.

    fv_failed is carried through as "failed" so get_analysis can give a declined
    ticker (dead symbol, Yahoo outage) a short negative-cache life instead of pinning
    a blank, error-shaped payload for the full 3-day slow TTL -- before this cache
    existed, every page view simply retried."""
    run_out, inputs_or_exc = await asyncio.gather(
        _run_one_guarded(key), fetch_risk_reward_inputs(key), return_exceptions=True)
    if isinstance(run_out, Exception):
        raise run_out
    inputs = None if isinstance(inputs_or_exc, Exception) else inputs_or_exc
    return {"result": run_out["result"], "inputs": inputs, "ts": ts,
            "failed": bool(run_out.get("fv_failed"))}


async def _refresh_fast(slow_entry: dict) -> tuple[float | None, dict | None]:
    """One quote fetch (a single call) plus the existing, un-duplicated pure scoring
    (build_metric_scores + aggregate) re-run on a price-refreshed copy of the cached
    RiskRewardInputs -- one cheap call instead of risk_reward.engine.run's full
    three-call fetch.

    Uses services.yahoo.fetch_quote, not fetch_ticker_info: fetch_ticker_info's
    underlying fetch is @lru_cache'd forever per process (see its docstring), so a
    15-minute-or-however-long refresh built on it would silently keep re-deriving from
    the exact same frozen price for the life of a warm instance -- a real bug this
    cache shipped with once already. fetch_quote is the same single yfinance call,
    deliberately left unmemoized for exactly this caller. The caller wraps this whole
    call in asyncio.wait_for -- fetch_quote's own yf.Ticker().info accepts no timeout,
    and the per-ticker lock is held across this await."""
    inputs: RiskRewardInputs | None = slow_entry.get("inputs")
    if inputs is None:
        raise RuntimeError("no cached risk-reward inputs available to refresh from")
    fresh_price = await fetch_quote(inputs.ticker)
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
    lock = _acquire_lock(key)
    try:
        async with lock:
            now = _now()

            slow = _slow.get(key)
            just_refreshed_slow = False
            slow_ttl = FAST_TTL if (slow is not None and slow.get("failed")) else SLOW_TTL
            if slow is None or (now - slow["ts"]) >= slow_ttl:
                try:
                    slow = await _populate_slow(key, now)
                except Exception:
                    if slow is not None:
                        # Fundamentals refresh failed but stale ones exist -- degrade,
                        # same "stale beats broken" principle as the fast layer.
                        _touch(_slow, key)
                    else:
                        raise
                else:
                    _slow[key] = slow
                    _touch(_slow, key)
                    _evict(_slow)
                    just_refreshed_slow = True
            else:
                _touch(_slow, key)

            fast = _fast.get(key)
            if just_refreshed_slow:
                # Fresh fundamentals just landed in the same call -- seed the fast
                # layer from that same snapshot's own price/risk_reward instead of an
                # immediately-redundant quote fetch. Its own clock starts now.
                dump = slow["result"]
                fast = {"price": dump.get("current_price"), "rr": dump.get("risk_reward"),
                        "ts": now, "failed": False}
                _fast[key] = fast
                _touch(_fast, key)
                _evict(_fast)
            else:
                fast_ttl = FAST_NEGATIVE_TTL if (fast is not None and fast.get("failed")) else FAST_TTL
                if fast is None or (now - fast["ts"]) >= fast_ttl:
                    try:
                        price, rr_dump = await asyncio.wait_for(
                            _refresh_fast(slow), FAST_REFRESH_TIMEOUT)
                    except Exception:
                        if fast is not None:
                            # Stale beats broken: keep the old price/R-R, but stamp a
                            # fresh ts (short negative-cache backoff) so the next view
                            # doesn't immediately re-attempt the same failing fetch.
                            fast = {"price": fast["price"], "rr": fast["rr"],
                                    "ts": now, "failed": True}
                            _fast[key] = fast
                            _touch(_fast, key)
                        else:
                            dump = slow["result"]
                            fast = {"price": dump.get("current_price"),
                                    "rr": dump.get("risk_reward"), "ts": now, "failed": True}
                            _fast[key] = fast
                            _touch(_fast, key)
                            _evict(_fast)
                    else:
                        fast = {"price": price, "rr": rr_dump, "ts": now, "failed": False}
                        _fast[key] = fast
                        _touch(_fast, key)
                        _evict(_fast)
                else:
                    _touch(_fast, key)
    finally:
        _release_lock(key)

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
