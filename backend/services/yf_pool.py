from __future__ import annotations
import asyncio
import os
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
