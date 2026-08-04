import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers.analysis import router as analysis_router
from routers.database import router as database_router
from routers.watchlists import router as watchlists_router

load_dotenv()

app = FastAPI(title="Fair Value Batch Calculator")

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


@app.get("/api/health")
def health():
    return {"status": "ok"}
