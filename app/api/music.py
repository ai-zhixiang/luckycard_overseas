from fastapi import APIRouter

router = APIRouter()

@router.get("/music/list")
async def list_music():
    return {"tracks": [], "total": 0}
