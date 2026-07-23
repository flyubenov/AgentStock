from __future__ import annotations
import asyncio
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor

# All blocking yfinance calls run on this dedicated, size-bounded pool — never the
# default asyncio executor. yfinance's rate-limit retry sleeps for several seconds
# while holding a worker thread; a batch fans those blocking fetches out across many
# tickers at once. Routing them through the shared default executor let those sleeps
# saturate it and starve FastAPI/Starlette (and every other endpoint), freezing the
# whole server. A separate bounded pool contains the blast radius: a rate-limited
# batch merely slows down while the rest of the app stays responsive.
YF_MAX_WORKERS = int(os.getenv("YF_MAX_WORKERS", "8"))
_EXECUTOR = ThreadPoolExecutor(max_workers=YF_MAX_WORKERS, thread_name_prefix="yf")


async def run_yf(fn, *args):
    """Run a blocking yfinance callable on the dedicated pool and await the result."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_EXECUTOR, fn, *args)


# --- rate-limit pressure signal ------------------------------------------------
# A yfinance fetch swallows a 429 into its bounded retry/backoff and then returns
# None (or raises), so the batch orchestrator upstream never sees the throttle and
# used to keep hammering Yahoo just as hard — the run got slower and slower until it
# froze. note_rate_limit() lets a fetch flag that Yahoo is throttling;
# rate_limit_pressure() reports it for a short window so run_batch can widen its
# inter-ticker pacing (adaptive slowdown) instead of pushing into the same wall.
_RATE_LIMIT_PRESSURE_WINDOW = float(os.getenv("YF_RATE_LIMIT_WINDOW", "20"))
_last_rate_limit_at: float = 0.0
_rl_lock = threading.Lock()


def note_rate_limit() -> None:
    """Record that a yfinance fetch just hit a rate limit. Safe to call from the
    pool worker threads."""
    global _last_rate_limit_at
    with _rl_lock:
        _last_rate_limit_at = time.monotonic()


def rate_limit_pressure() -> bool:
    """True when a rate limit was observed within the recent window."""
    with _rl_lock:
        last = _last_rate_limit_at
    return last > 0 and (time.monotonic() - last) < _RATE_LIMIT_PRESSURE_WINDOW
