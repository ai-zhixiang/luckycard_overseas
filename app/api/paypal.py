"""
PayPal REST API — Checkout & Webhook
"""
import json, hashlib, hmac, uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..config import settings
from ..models import User, PaymentTransaction

router = APIRouter()
PAYPAL_API = "https://api-m.paypal.com"

PREMIUM_PRICE = 9.9  # USD
PREMIUM_CURRENCY = "USD"
PREMIUM_DURATION_DAYS = 30


async def _paypal_token() -> str:
    """Get PayPal OAuth2 access token"""
    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{PAYPAL_API}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(settings.paypal_client_id, settings.paypal_client_secret),
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            raise HTTPException(502, f"PayPal auth failed: {resp.text[:200]}")
        return resp.json()["access_token"]


# ─────────────────────────────────────────────
# 1. Create Order
# ─────────────────────────────────────────────
@router.post("/payment/paypal/create-order")
async def create_paypal_order(data: dict, db: AsyncSession = Depends(get_db)):
    """Create a PayPal order for Premium ($9.9/month)
    Expects: {"user_id": "xxx"}
    """
    user_id = data.get("user_id")
    if not user_id:
        raise HTTPException(400, "user_id required")

    # Verify user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    token = await _paypal_token()
    import httpx
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{PAYPAL_API}/v2/checkout/orders",
            json={
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {
                        "currency_code": PREMIUM_CURRENCY,
                        "value": str(PREMIUM_PRICE),
                    },
                    "description": "Lucky Card Premium · 30 days",
                    "custom_id": user_id,
                }],
                "application_context": {
                    "brand_name": "Lucky Card",
                    "landing_page": "NO_PREFERENCE",
                    "user_action": "PAY_NOW",
                    "return_url": f"https://{settings.domain}/payment/success",
                    "cancel_url": f"https://{settings.domain}/payment/cancel",
                },
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        data = resp.json()
        if resp.status_code not in (200, 201):
            raise HTTPException(502, f"PayPal create order failed: {data.get('message','')[:200]}")

    # Save order to DB for tracking
    paypal_order_id = data["id"]
    tx = PaymentTransaction(
        user_id=user_id,
        product_name="Lucky Card Premium",
        status="pending",
        amount_cents=int(PREMIUM_PRICE * 100),
        currency=PREMIUM_CURRENCY,
        gateway="paypal",
        gateway_order_id=paypal_order_id,
    )
    db.add(tx)
    await db.commit()

    return {
        "order_id": paypal_order_id,
        "amount": PREMIUM_PRICE,
        "currency": PREMIUM_CURRENCY,
    }


# ─────────────────────────────────────────────
# 2. Capture Order (after buyer approves)
# ─────────────────────────────────────────────
@router.post("/payment/paypal/capture-order/{paypal_order_id}")
async def capture_paypal_order(paypal_order_id: str, db: AsyncSession = Depends(get_db)):
    """Capture an approved PayPal order"""
    token = await _paypal_token()
    import httpx
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{PAYPAL_API}/v2/checkout/orders/{paypal_order_id}/capture",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
        data = resp.json()
        if resp.status_code not in (200, 201):
            raise HTTPException(502, f"PayPal capture failed: {data.get('message','')[:200]}")

    # Check capture status
    status = data.get("status", "")
    if status != "COMPLETED":
        return {"success": False, "status": status, "message": "Payment not completed"}

    # Extract user_id from custom_id
    purchase_units = data.get("purchase_units", [])
    user_id = ""
    for pu in purchase_units:
        user_id = pu.get("custom_id", "")
        break

    capture_id = ""
    for pu in purchase_units:
        captures = pu.get("payments", {}).get("captures", [])
        for cap in captures:
            capture_id = cap.get("id", "")
            break

    # Update transaction
    result = await db.execute(
        select(PaymentTransaction).where(PaymentTransaction.gateway_order_id == paypal_order_id)
    )
    tx = result.scalar_one_or_none()
    if tx:
        tx.status = "paid"
        tx.gateway_capture_id = capture_id
        tx.updated_at = datetime.utcnow()

    # Activate premium
    if user_id:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            now = datetime.utcnow()
            if user.is_premium and user.premium_until and user.premium_until > now:
                # Extend existing premium
                user.premium_until = user.premium_until + timedelta(days=PREMIUM_DURATION_DAYS)
            else:
                user.is_premium = True
                user.premium_until = now + timedelta(days=PREMIUM_DURATION_DAYS)
            user.paypal_subscription_id = paypal_order_id

    await db.commit()
    return {"success": True, "status": status, "capture_id": capture_id}


# ─────────────────────────────────────────────
# 3. Verify Webhook Signature
# ─────────────────────────────────────────────
def verify_paypal_webhook(
    headers: dict, body: bytes, webhook_id: str
) -> bool:
    """Verify PayPal webhook using their POST verification API"""
    import httpx
    token = httpx.post(
        f"{PAYPAL_API}/v1/oauth2/token",
        data={"grant_type": "client_credentials"},
        auth=(settings.paypal_client_id, settings.paypal_client_secret),
    ).json()["access_token"]

    verification = {
        "auth_algo": headers.get("paypal-auth-algo", ""),
        "cert_url": headers.get("paypal-cert-url", ""),
        "transmission_id": headers.get("paypal-transmission-id", ""),
        "transmission_sig": headers.get("paypal-transmission-sig", ""),
        "transmission_time": headers.get("paypal-transmission-time", ""),
        "webhook_id": webhook_id,
        "webhook_event": json.loads(body.decode()),
    }

    resp = httpx.post(
        f"{PAYPAL_API}/v1/notifications/verify-webhook-signature",
        json=verification,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    return resp.json().get("verification_status") == "SUCCESS"


# ─────────────────────────────────────────────
# 4. Webhook — handles payment events
# ─────────────────────────────────────────────
@router.post("/payment/paypal/webhook")
async def paypal_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle PayPal webhook events"""
    body = await request.body()
    headers_dict = dict(request.headers)

    webhook_id = settings.paypal_webhook_id
    if webhook_id:
        if not verify_paypal_webhook(headers_dict, body, webhook_id):
            raise HTTPException(401, "Invalid webhook signature")

    event = json.loads(body)
    event_type = event.get("event_type", "")

    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        resource = event.get("resource", {})
        paypal_order_id = resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id", "")
        capture_id = resource.get("id", "")
        custom_id = resource.get("custom_id", "")
        amount_value = resource.get("amount", {}).get("value", "0")

        # Update transaction
        result = await db.execute(
            select(PaymentTransaction).where(PaymentTransaction.gateway_order_id == paypal_order_id)
        )
        tx = result.scalar_one_or_none()
        if tx:
            tx.status = "paid"
            tx.gateway_capture_id = capture_id
            tx.updated_at = datetime.utcnow()

        # Activate premium
        if custom_id:
            result = await db.execute(select(User).where(User.id == custom_id))
            user = result.scalar_one_or_none()
            if user:
                now = datetime.utcnow()
                if user.is_premium and user.premium_until and user.premium_until > now:
                    user.premium_until = user.premium_until + timedelta(days=PREMIUM_DURATION_DAYS)
                else:
                    user.is_premium = True
                    user.premium_until = now + timedelta(days=PREMIUM_DURATION_DAYS)
                user.paypal_subscription_id = paypal_order_id
                await db.commit()

    return {"ok": True}


# ─────────────────────────────────────────────
# 5. Payment config (public, no secrets)
# ─────────────────────────────────────────────
@router.get("/payment/paypal/config")
async def paypal_config():
    return {
        "client_id": settings.paypal_client_id,
        "premium_price": PREMIUM_PRICE,
        "premium_currency": PREMIUM_CURRENCY,
        "premium_interval": "month",
        "premium_name": "Lucky Card Premium",
    }
