from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db

router = APIRouter()

@router.get("/cards/list")
async def list_cards(skip: int = 0, limit: int = 20, db: AsyncSession = Depends(get_db)):
    return {"cards": [], "total": 0}

@router.post("/cards/create")
async def create_card(data: dict, db: AsyncSession = Depends(get_db)):
    return {"status": "ok", "card_id": "temp"}
