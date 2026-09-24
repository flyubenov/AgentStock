import asyncio
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers.analysis import router as analysis_router
from routers.database import router as database_router
from routers.watchlists import router as watchlists_router
from routers.events import router as events_router
from routers.landing import router as landing_router
from landing.cache import seed

load_dotenv()

app = FastAPI(title="Intrinsica")

# The landing page's compare grid (spec S12.4's marquee ticker, plus the trio Task 9
# offers). One constant so changing it is a one-line edit.
LANDING_MARQUEE_TICKERS = ["AAPL", "MSFT", "NVDA"]

# Comma-separated list of allowed frontend origins. Defaults to the local Vite
# dev server; set CORS_ORIGINS to the deployed frontend URL(s) in the cloud
# (e.g. "https://agentstock.vercel.app").
_cors_origins = [o.strip() for o in
                 os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
                 if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router, prefix="/api")
app.include_router(database_router, prefix="/api")
app.include_router(watchlists_router, prefix="/api")
app.include_router(events_router, prefix="/api")
app.include_router(landing_router, prefix="/api")


@app.on_event("startup")
async def _seed_landing_cache() -> None:
    # Cloud Run scales to zero, so the cache is cold for the first visitor after an
    # idle period -- exactly the visitor this page exists for. Fire-and-forget: seed()
    # itself never raises (a Yahoo outage at boot just leaves the cache cold), and this
    # must not block startup on live network calls either way.
    asyncio.create_task(seed(LANDING_MARQUEE_TICKERS))


@app.get("/api/health")
def health():
    return {"status": "ok"}
