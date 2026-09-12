"""API keys — 用户自助生成/查看/吊销 lc- key + 受 key 保护的付费 API。

身份: 生成/管理用登录 cookie (uid); 调用 API 用 X-API-Key。
计费: 走 key 的调用不吃免费额度, 一律扣钱包 Lucky Points (A1 方案)。
"""
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from .auth import identity_from
from .. import apikey

router = APIRouter()


def _require_user(request: Request) -> str:
    ident = identity_from(request) or {}
    uid = ident.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="Please sign in first")
    return uid


# ───────────────────────── key 管理 ─────────────────────────

class CreateBody(BaseModel):
    label: str = ""


@router.post("/apikey/create")
async def apikey_create(body: CreateBody, request: Request):
    """生成新 key。返回完整 key —— 只此一次, 让用户立刻复制。"""
    uid = _require_user(request)
    if len(apikey.list_keys(uid)) >= apikey.MAX_KEYS_PER_USER:
        raise HTTPException(
            status_code=400,
            detail=f"Key limit reached (max {apikey.MAX_KEYS_PER_USER}). Revoke one first.",
        )

    full_key, rec = apikey.create_key(uid, label=body.label.strip()[:40])
    return {
        "key": full_key,          # ← 唯一一次出现
        "label": rec["label"],
        "created": rec["created"],
    }


@router.get("/apikey/list")
async def apikey_list(request: Request):
    uid = _require_user(request)
    return {"keys": apikey.list_keys(uid)}


@router.post("/apikey/revoke")
async def apikey_revoke(data: dict, request: Request):
    """{id: '<8位内部id>'} → 吊销"""
    uid = _require_user(request)
    key_id = (data or {}).get("id", "")
    if not key_id:
        raise HTTPException(status_code=400, detail="Missing id")
    if not apikey.revoke_key(uid, key_id):
        raise HTTPException(status_code=404, detail="Key not found")


@router.get("/apikey/verify")
async def apikey_verify(request: Request):
    """自查一把 key 是否有效 (不更新使用统计)"""
    raw = request.headers.get("X-API-Key", "")
    rec = apikey.verify_key(raw, count_use=False)
    if not rec:
        raise HTTPException(status_code=401, detail="Invalid API key")
    from .. import quota
    return {
        "valid": True,
        "uid": rec["uid"],
        "label": rec.get("label", ""),
        "balance": quota.balance(rec["uid"]),
    }


# ───────────────────────── 受 key 保护的 API ─────────────────────────

def _auth_and_charge(x_api_key: str | None, ops: list[str]) -> dict:
    """验证 key + 扣点。返回 charge 信息; key/余额问题直接抛 HTTP。"""
    try:
        rec = apikey.require_api_key(x_api_key)
    except apikey.ApiKeyError:
        raise HTTPException(status_code=401, detail="Invalid API key")

    try:
        charge = apikey.charge_api_op(rec, ops)
    except apikey.ApiQuotaError as e:
        raise HTTPException(status_code=402, detail={
            "code": "insufficient_points",
            "message": "Insufficient Lucky Points. Please recharge.",
            "cost": e.cost,
            "balance": e.balance,
        })
    return {"rec": rec, "charge": charge}


@router.get("/v1/balance")
async def api_balance(x_api_key: str | None = Header(default=None)):
    """查询这把 key 所属账户的余额 (免费接口, 不扣点)"""
    try:
        rec = apikey.require_api_key(x_api_key)
    except apikey.ApiKeyError:
        raise HTTPException(status_code=401, detail="Invalid API key")

    from .. import quota
    return {
        "uid": rec["uid"],
        "label": rec.get("label", ""),
        "balance": quota.balance(rec["uid"]),
        "prices": quota.COST,
    }


@router.post("/v1/poem")
async def api_poem(data: dict, x_api_key: str | None = Header(default=None)):
    """写诗 API。POST {recipient, occasion, message} → 扣 10 点。"""
    ctx = _auth_and_charge(x_api_key, ["poem"])

    from .cards import generate_poem
    try:
        poem = await generate_poem(
            recipient=(data.get("recipient") or "").strip(),
            occasion=(data.get("occasion") or "").strip(),
            message=(data.get("message") or "").strip(),
        )
    except Exception:
        apikey.refund_api_op(ctx["rec"], ["poem"], ctx["charge"])
        raise
    if not poem or not str(poem).strip():
        apikey.refund_api_op(ctx["rec"], ["poem"], ctx["charge"])
        raise HTTPException(status_code=502, detail="Poem generation failed")

    from .. import quota
    return {
        "poem": poem,
        "charged": ctx["charge"],
        "balance": quota.balance(ctx["rec"]["uid"]),
    }
