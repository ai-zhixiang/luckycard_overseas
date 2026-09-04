"""Lucky Point wallet — balance & PayPal recharge (custom integer USD)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from ..database import get_db
from ..models import PaymentTransaction
from .. import quota
from ..config import settings
from .auth import identity_from, parse_token, COOKIE_NAME

router = APIRouter()


def _require_user(request: Request) -> str:
    token = request.cookies.get(COOKIE_NAME)
    payload = parse_token(token) if token else None
    uid = None
    if payload and payload.get("k", "").startswith("user:"):
        uid = payload["k"].split(":", 1)[1]
    if not uid:
        raise HTTPException(401, "需要先登录账号才能充值")
    return uid


@router.get("/wallet")
async def wallet_status(request: Request):
    ident = identity_from(request)
    ip = ident.get("_ip") or ""
    uid = ident.get("user_id")
    free = quota.free_status(_ip_of(request))
    return {
        "kind": ident["kind"],
        "name": ident["name"],
        "free": free,
        "balance": quota.balance(uid) if uid else 0,
        "history": quota.wallet_info(uid)["history"] if uid else [],
        "costs": quota.COST,
        "points_per_usd": quota.POINTS_PER_USD,
        "min_usd": quota.MIN_RECHARGE_USD,
        "dev_grant": bool(settings.dev_grant),
    }


def _ip_of(request: Request) -> str:
    x = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for")
    if x:
        return x.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/wallet/grant")
async def wallet_grant(data: dict, request: Request):
    """DEV ONLY — grant test points without PayPal. Guarded by DEV_GRANT env."""
    if not settings.dev_grant:
        raise HTTPException(403, "测试加币未开启")
    uid = _require_user(request)
    try:
        pts = int(data.get("points", 0))
    except (TypeError, ValueError):
        raise HTTPException(400, "点数必须是整数")
    if pts <= 0 or pts > 10000:
        raise HTTPException(400, "点数范围 1-10000")
    return quota.add_pts_raw(uid, pts, note="测试加币(DEV)")


@router.post("/wallet/recharge/create")
async def recharge_create(data: dict, request: Request, db: AsyncSession = Depends(get_db)):
    """{amount_usd: int} → PayPal order. custom_id = 'recharge:<uid>'"""
    uid = _require_user(request)
    raw = data.get("amount_usd")
    try:
        if isinstance(raw, bool):
            raise ValueError
        num = float(raw)
        if num != int(num):
            raise ValueError
        amount = int(num)
    except (TypeError, ValueError):
        raise HTTPException(400, "金额必须是整数(美元)")
    if amount < quota.MIN_RECHARGE_USD:
        raise HTTPException(400, f"最少充值 ${quota.MIN_RECHARGE_USD}")
    if amount > 500:
        raise HTTPException(400, "单次最多 $500")

    pts = amount * quota.POINTS_PER_USD
    from .paypal import _paypal_token, PAYPAL_API
    import httpx
    token = await _paypal_token()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{PAYPAL_API}/v2/checkout/orders",
            json={
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {"currency_code": "USD", "value": f"{amount}.00"},
                    "description": f"Lucky Points ×{pts}",
                    "custom_id": f"recharge:{uid}",
                }],
                "application_context": {
                    "brand_name": "Lucky Card",
                    "landing_page": "NO_PREFERENCE",
                    "user_action": "PAY_NOW",
                    "return_url": "https://hicard.world/payment/success",
                    "cancel_url": "https://hicard.world/payment/cancel",
                },
            },
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        )
        body = resp.json()
        if resp.status_code not in (200, 201):
            raise HTTPException(502, f"PayPal create order failed: {body.get('message', '')[:200]}")

    tx = PaymentTransaction(
        user_id=uid,
        product_name=f"Lucky Points ×{pts}",
        status="pending",
        amount_cents=amount * 100,
        currency="USD",
        gateway="paypal",
        gateway_order_id=body["id"],
    )
    db.add(tx)
    await db.commit()

    return {"order_id": body["id"], "amount_usd": amount, "points": pts}


@router.post("/wallet/recharge/capture/{paypal_order_id}")
async def recharge_capture(paypal_order_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    """Capture an approved recharge order → credit Lucky Points."""
    from .paypal import _paypal_token, PAYPAL_API
    import httpx
    token = await _paypal_token()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{PAYPAL_API}/v2/checkout/orders/{paypal_order_id}/capture",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        if resp.status_code not in (200, 201):
            raise HTTPException(502, f"PayPal capture failed: {data.get('message', '')[:200]}")

    if data.get("status") != "COMPLETED":
        return {"success": False, "status": data.get("status")}

    # find custom_id & amount from capture
    uid = None
    amount_usd = 0.0
    for pu in data.get("purchase_units", []):
        cid = pu.get("custom_id", "")
        if cid.startswith("recharge:"):
            uid = cid.split(":", 1)[1]
        for cap in pu.get("payments", {}).get("captures", []):
            try:
                amount_usd = float(cap.get("amount", {}).get("value", "0"))
            except ValueError:
                amount_usd = 0.0

    if not uid:
        raise HTTPException(400, "订单缺少充值标识")

    res = quota.add_points(uid, amount_usd, note=f"PayPal 充值 ${amount_usd:.2f}")

    result = await db.execute(select(PaymentTransaction).where(
        PaymentTransaction.gateway_order_id == paypal_order_id
    ))
    tx = result.scalar_one_or_none()
    if tx:
        tx.status = "paid"
        tx.gateway_capture_id = data.get("id", "")
        tx.updated_at = datetime.utcnow()
        await db.commit()

    return {"success": True, "status": "COMPLETED", **res}
