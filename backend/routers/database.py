from fastapi import APIRouter
from services.sheets import read_database, delete_database_row, delete_watchlist_row
from services.screener_sheets import read_screener_one, delete_screener_row

router = APIRouter()


@router.get("/database")
async def get_database():
    try:
        results = await read_database()
        return {"results": [r.model_dump() for r in results]}
    except Exception as e:
        return {"error": str(e), "results": []}


@router.delete("/database/{ticker}")
async def delete_ticker(ticker: str):
    """Drop a company everywhere it is persisted: the Database row the grid reads,
    its Screener row, and the Tickers input list — so it stops costing time on the
    next recalculate."""
    t = ticker.strip().upper()
    try:
        removed = {
            "database": await delete_database_row(t),
            "screener": await delete_screener_row(t),
            "tickers": await delete_watchlist_row(t),
        }
        if not any(removed.values()):
            return {"deleted": False, "error": f"No records found for {t}"}
        return {"deleted": True, "ticker": t, "removed": removed}
    except Exception as e:
        return {"deleted": False, "error": str(e)}


@router.get("/screener/{ticker}")
async def get_screener(ticker: str):
    try:
        r = await read_screener_one(ticker)
        if r is None:
            return {"error": f"No screener record for {ticker.upper()}"}
        return r.model_dump()
    except Exception as e:
        return {"error": str(e)}
