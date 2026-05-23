from fastapi import APIRouter

router = APIRouter()

@router.get("/auth/status")
async def auth_status():
    return {"logged_in": False}
