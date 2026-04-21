from fastapi import APIRouter
from services.sheets import read_database

router = APIRouter()


@router.get("/database")
async def get_database():
    try:
        results = await read_database()
        return {"results": [r.model_dump() for r in results]}
    except Exception as e:
        return {"error": str(e), "results": []}
