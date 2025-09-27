from fastapi import APIRouter

from app.matching.consumers import engine

router = APIRouter()

@router.get("/snapshot")
async def get_snapshot():
    return engine.top5_snapshot()

