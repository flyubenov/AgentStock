from fastapi import APIRouter
from services.sheets import read_database
from services.screener_sheets import read_screener_one

router = APIRouter()


@router.get("/database")
async def get_database():
    try:
        results = await read_database()
        return {"results": [r.model_dump() for r in results]}
    except Exception as e:
        return {"error": str(e), "results": []}


@router.get("/screener/{ticker}")
async def get_screener(ticker: str):
    try:
        r = await read_screener_one(ticker)
        if r is None:
            return {"error": f"No screener record for {ticker.upper()}"}
        return r.model_dump()
    except Exception as e:
        return {"error": str(e)}
