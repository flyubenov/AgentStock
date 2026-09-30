import asyncio
import os
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers.analysis import router as analysis_router
from routers.database import router as database_router
from routers.watchlists import router as watchlists_router
from routers.events import router as events_router
from routers.landing import router as landing_router
from landing.cache import seed
from services.events_sheets import flush_events, flush_loop

load_dotenv()

# The landing page's compare grid (spec S12.4's marquee ticker, plus the trio Task 9
# offers). One constant so changing it is a one-line edit.
LANDING_MARQUEE_TICKERS = ["AAPL", "MSFT", "NVDA"]

# Held so the task isn't garbage-collected mid-flight: asyncio.create_task only keeps
# a weak reference in the running loop, so a discarded handle can let the seed vanish
# silently before it finishes. Fire-and-forget still means "don't await it here", not
# "don't keep a reference to it".
_seed_task: asyncio.Task | None = None
_flush_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _seed_task, _flush_task
    # Cloud Run scales to zero, so the cache is cold for the first visitor after an
    # idle period -- exactly the visitor this page exists for. Fire-and-forget: seed()
    # itself never raises (a Yahoo outage at boot just leaves the cache cold), and this
    # must not block startup on live network calls either way.
    _seed_task = asyncio.create_task(seed(LANDING_MARQUEE_TICKERS))
    # Queued funnel events are written on a timer, not only once a batch fills —
    # see services/events_sheets.py for every trigger.
    _flush_task = asyncio.create_task(flush_loop())
    yield
    if _flush_task is not None:
        _flush_task.cancel()
        with suppress(asyncio.CancelledError):
            await _flush_task
    # Last chance for whatever is still queued: Cloud Run sends SIGTERM and allows a
    # grace period before an idle instance is removed, and this runs inside it.
    # flush_events() swallows a sink failure, so shutdown cannot hang on Sheets.
    await flush_events()
    if _seed_task is not None and not _seed_task.done():
        _seed_task.cancel()
        # Await it: a cancelled-but-never-awaited task can log "Task was destroyed
        # but it is pending" once the loop tears down. The CancelledError this raises
        # is the expected, successful outcome of the cancel() above, not a failure.
        with suppress(asyncio.CancelledError):
            await _seed_task


def _cors_origins() -> list[str]:
    # Comma-separated allowed frontend origins. Defaults to the local Vite dev server;
    # production sets CORS_ORIGINS=https://intrinsica.io (the page is same-origin, so
    # this only stops other sites' pages from calling the API).
    return [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
            if o.strip()]


def create_app(*, public_mode: bool | None = None, static_dir: str | None = None,
               canonical_host: str | None = None) -> FastAPI:
    """Build the app. Each argument left as None is read from the environment:
    INTRINSICA_PUBLIC_MODE ("1" = production: only the fake-door APIs exist -- the
    Agent Stock analyst routers are never mounted), INTRINSICA_STATIC_DIR (the built
    frontend to serve) and CANONICAL_HOST (www -> apex redirect). Unset, all three
    leave local dev exactly as it was."""
    if public_mode is None:
        public_mode = os.getenv("INTRINSICA_PUBLIC_MODE", "") == "1"
    if static_dir is None:
        static_dir = os.getenv("INTRINSICA_STATIC_DIR", "")
    if canonical_host is None:
        canonical_host = os.getenv("CANONICAL_HOST", "")

    app = FastAPI(title="Intrinsica", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if not public_mode:
        app.include_router(analysis_router, prefix="/api")
        app.include_router(database_router, prefix="/api")
        app.include_router(watchlists_router, prefix="/api")
    app.include_router(events_router, prefix="/api")
    app.include_router(landing_router, prefix="/api")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
