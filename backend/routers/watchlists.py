from fastapi import APIRouter
from pydantic import BaseModel
from services.watchlist_sheets import (
    read_watchlists, save_watchlist, delete_watchlist,
)

router = APIRouter()


class WatchlistBody(BaseModel):
    filter: dict = {}


@router.get("/watchlists")
async def get_watchlists():
    try:
        results = await read_watchlists()
        return {"results": [w.model_dump() for w in results]}
    except Exception as e:
        return {"error": str(e), "results": []}


@router.put("/watchlists/{name}")
async def put_watchlist(name: str, body: WatchlistBody):
    n = name.strip()
    if not n:
        return {"saved": False, "error": "Watchlist name is required"}
    try:
        w = await save_watchlist(n, body.filter)
        return {"saved": True, **w.model_dump()}
    except Exception as e:
        return {"saved": False, "error": str(e)}


@router.delete("/watchlists/{name}")
async def remove_watchlist(name: str):
    n = name.strip()
    try:
        removed = await delete_watchlist(n)
        if not removed:
            return {"deleted": False, "error": f"No watchlist named {n!r}"}
        return {"deleted": True, "name": n}
    except Exception as e:
        return {"deleted": False, "error": str(e)}
