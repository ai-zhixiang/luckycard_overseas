import hmac, hashlib, json, time, uuid
from datetime import datetime, timedelta
import httpx
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..config import settings
from ..models import User, PaymentTransaction
from .auth import identity_from

router = APIRouter()
LS_API_BASE = "https://api.lemonsqueezy.com/v1"

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/vnd.api+json",
    "Authorization": f"Bearer {settings.ls_api_key}",
}


def _ls_headers() -> dict:
    return {
        "Accept": "application/json",
        "Content-Type": "application/vnd.api+json",
        "Authorization": f"Bearer {settings.ls_api_key}",
    }


# ─────────────────────────────────────────────
# 1. Create Checkout — returns redirect URL
# ─────────────────────────────────────────────
@router.post("/payment/checkout")
async def create_checkout(data: dict, db: AsyncSession = Depends(get_db)):
    """
    Lemon Squeezy 结账 —— 【已停用】。
    本站仅使用 PayPal 收款（见 /api/payment/paypal/*）。LS 密钥从未配置，
    此端点保留仅为兼容旧调用，一律返回 410 提示改走 PayPal。
    """
    raise HTTPException(
        status_code=410,
        detail="Lemon Squeezy 通道已停用，请使用 PayPal 支付（/api/payment/paypal/*）",
    )



# ─────────────────────────────────────────────
# 2. Verify Webhook Signature
# ─────────────────────────────────────────────
def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify Lemon Squeezy webhook x-signature header"""
    if not settings.ls_webhook_secret:
        return False
    expected = hmac.new(
        settings.ls_webhook_secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


# ─────────────────────────────────────────────
# 3. Webhook — handles subscription events
# ─────────────────────────────────────────────
@router.post("/payment/webhook")
async def payment_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Lemon Squeezy webhook events"""
    # Verify signature
    body = await request.body()
    signature = request.headers.get("x-signature", "")
    if not verify_webhook_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event = json.loads(body)
    event_name = event.get("meta", {}).get("event_name", "")
    data = event.get("data", {})
    attributes = data.get("attributes", {})

    # Extract common fields
    ls_order_id = str(attributes.get("order_id", "")) or data.get("id", "")
    ls_subscription_id = str(attributes.get("subscription_id", "")) or (
        data.get("id", "") if "subscription" in event_name else ""
    )
    ls_customer_id = str(attributes.get("customer_id", ""))
    variant_id = attributes.get("variant_id", 0) or 0
    custom_data = attributes.get("custom_data", {}) or {}
    user_id = custom_data.get("user_id", "")
    status = attributes.get("status", "")

    if event_name == "order_created":
        amount_cents = attributes.get("total", 0)
        currency = attributes.get("currency", "USD")

        # Find user by custom user_id or email
        if not user_id:
            user_email = attributes.get("user_email", "") or custom_data.get("email", "")
            if user_email:
                result = await db.execute(select(User).where(User.email == user_email))
                user = result.scalar_one_or_none()
                if user:
                    user_id = user.id

        # Create transaction record
        tx = PaymentTransaction(
            user_id=user_id or None,
            ls_order_id=ls_order_id,
            ls_subscription_id=ls_subscription_id,
            ls_customer_id=ls_customer_id,
            variant_id=variant_id,
            product_name="Lucky Card Premium",
            status="paid",
            amount_cents=amount_cents,
            currency=currency,
        )
        db.add(tx)

        # Immediately activate premium for the user (first payment = activated)
        if user_id:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.is_premium = True
                # Set expiry to 30 days from now (will be updated by subscription_created)
                user.premium_until = datetime.utcnow() + timedelta(days=30)
                user.ls_customer_id = ls_customer_id
                user.ls_order_id = ls_order_id
                if ls_subscription_id:
                    user.ls_subscription_id = ls_subscription_id

        await db.commit()
        return {"ok": True, "event": event_name}

    elif event_name == "subscription_created":
        # Set premium expiry based on subscription billing
        renews_at = attributes.get("renews_at", "")
        trial_ends_at = attributes.get("trial_ends_at", "")

        # Find user
        if user_id:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
        elif ls_customer_id:
            result = await db.execute(select(User).where(User.ls_customer_id == ls_customer_id))
            user = result.scalar_one_or_none()
        else:
            user = None

        if user:
            user.is_premium = True
            user.ls_subscription_id = ls_subscription_id
            user.ls_customer_id = ls_customer_id
            # Calculate premium until date
            if renews_at:
                try:
                    renew_dt = datetime.fromisoformat(renews_at.replace("Z", "+00:00"))
                except:
                    renew_dt = datetime.utcnow() + timedelta(days=30)
            else:
                renew_dt = datetime.utcnow() + timedelta(days=30)
            if trial_ends_at:
                try:
                    trial_dt = datetime.fromisoformat(trial_ends_at.replace("Z", "+00:00"))
                    if trial_dt > renew_dt:
                        renew_dt = trial_dt + timedelta(days=30)
                except:
                    pass
            user.premium_until = renew_dt

        # Update transaction
        if ls_order_id:
            result = await db.execute(
                select(PaymentTransaction).where(PaymentTransaction.ls_order_id == ls_order_id)
            )
            tx = result.scalar_one_or_none()
            if tx:
                tx.ls_subscription_id = ls_subscription_id
                tx.status = "paid"

        await db.commit()
        return {"ok": True, "event": event_name}

    elif event_name == "subscription_updated":
        # Update premium status
        cancelled = attributes.get("cancelled", False)
        renews_at = attributes.get("renews_at", "")

        if ls_subscription_id:
            result = await db.execute(
                select(User).where(User.ls_subscription_id == ls_subscription_id)
            )
            user = result.scalar_one_or_none()
            if user:
                if cancelled or status == "cancelled":
                    user.is_premium = False
                elif renews_at:
                    try:
                        user.premium_until = datetime.fromisoformat(renews_at.replace("Z", "+00:00"))
                    except:
                        pass
                await db.commit()

        return {"ok": True, "event": event_name}

    elif event_name == "subscription_cancelled":
        if ls_subscription_id:
            result = await db.execute(
                select(User).where(User.ls_subscription_id == ls_subscription_id)
            )
            user = result.scalar_one_or_none()
            if user:
                user.is_premium = False
                await db.commit()

        return {"ok": True, "event": event_name}

    return {"ok": True, "event": event_name, "handled": False}


# ─────────────────────────────────────────────
# 4. Check premium status
# ─────────────────────────────────────────────
@router.get("/payment/premium-status/{user_id}")
async def premium_status(user_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """查询会员状态。仅允许查询自己；过期判定为只读，不再写库。

    (原先无鉴权可遍历任意 user_id 泄露会员信息, 且 GET 会改 is_premium 造成状态回退)
    """
    ident = identity_from(request)
    if ident.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="只能查询自己的会员状态")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 只读判定: 到期即视为非会员, 但不落库 (落库交给 webhook / 定时任务)
    is_active = bool(user.is_premium and user.premium_until and datetime.utcnow() < user.premium_until)

    return {
        "is_premium": is_active,
        "premium_until": user.premium_until.isoformat() if user.premium_until else None,
    }


@router.get("/payment/config")
async def payment_config():
    """Public payment config (no secrets)"""
    return {
        "premium_price": 9.9,
        "premium_currency": "USD",
        "premium_interval": "month",
        "premium_name": "Lucky Card Premium",
    }
