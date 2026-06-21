from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from routers.analysis import router as analysis_router
from routers.database import router as database_router

load_dotenv()

app = FastAPI(title="Fair Value Batch Calculator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router, prefix="/api")
app.include_router(database_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
