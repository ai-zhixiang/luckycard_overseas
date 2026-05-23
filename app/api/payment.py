from fastapi import APIRouter

router = APIRouter()

@router.post("/payment/checkout")
async def create_checkout():
    return {"url": "https://checkout.stripe.com/placeholder"}
