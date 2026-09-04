"""Session & identity — signed cookie, guest-by-IP, account register/login.

Cookie `lc_sess` = base64url(json).hexdigest (HMAC-SHA256 with SECRET_KEY).
Payload: {"k": "user:<id>" | "ip", "p": 0|1 (premium), "n": name, "exp": ts}
Guests are keyed by their client IP server-side; the cookie just records that
they went through the XP login window so the UI can show an identity.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..database import get_db
from ..models import User
from .. import quota

router = APIRouter()
COOKIE_NAME = "lc_sess"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days


# ───────────────────────── charging gate (shared by AI endpoints) ─────────────────────────

def charge_op(request: Request, ops: list[str], user_id_hint: str | None = None) -> dict:
    """Pay for AI ops: 1) per-IP free allowance first, 2) wallet points.

    ops: e.g. ["poem"] or ["poem","vision"] — cost looked up in quota.COST.
    Raises HTTPException(402) when neither free slot nor enough points.
    """
    ident = identity_from(request)
    ip = client_ip(request)
    cost = sum(quota.COST.get(o, 0) for o in ops)
    free = quota.free_status(ip)

    # 1) free slot?
    if free["remaining"] > 0 and quota.free_take(ip):
        return {"method": "free", "cost": 0, "free_remaining": free["remaining"] - 1}

    # 2) wallet points (logged-in user only)
    uid = (user_id_hint or ident.get("user_id"))
    if uid and cost > 0 and quota.spend_points(uid, cost, note=f"AI:{'+'.join(ops)}"):
        return {"method": "points", "cost": cost, "paid": cost,
                "balance": quota.balance(uid), "free_remaining": 0}

    raise HTTPException(402, detail={
        "code": "quota_blocked",
        "message": "今日免费额度已用完，需要 Lucky Points",
        "free": free,
        "cost": cost,
        "balance": quota.balance(uid) if uid else 0,
    })


def refund_op(request: Request, ops: list[str], charge: dict | None) -> None:
    """Give the charge back when the AI call failed (never charge for errors)."""
    if not charge:
        return
    if charge.get("method") == "free":
        quota.free_refund(client_ip(request))
    elif charge.get("method") == "points":
        uid = identity_from(request).get("user_id")
        if uid and charge.get("paid"):
            quota.add_pts_raw(uid, charge["paid"], note="退款(AI失败)")


# ───────────────────────────── helpers ─────────────────────────────

def _sign(payload: dict) -> str:
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(settings.secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def parse_token(token: str) -> dict | None:
    try:
        raw, sig = token.rsplit(".", 1)
        expect = hmac.new(settings.secret_key.encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expect):
            return None
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


def client_ip(request: Request) -> str:
    """nginx sets X-Real-IP; fall back to socket peer."""
    x = request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for")
    if x:
        return x.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def identity_from(request: Request) -> dict:
    """Resolve quota identity from cookie (premium account) or IP (guest)."""
    payload = None
    token = request.cookies.get(COOKIE_NAME)
    if token:
        payload = parse_token(token)
    if payload and payload.get("k", "").startswith("user:"):
        return {
            "kind": "user",
            "key": f"user:{payload['k'].split(':', 1)[1]}",
            "user_id": payload["k"].split(":", 1)[1],
            "premium": bool(payload.get("p")),
            "name": payload.get("n", "User"),
        }
    ip = client_ip(request)
    return {
        "kind": "ip",
        "key": f"ip:{ip}",
        "user_id": None,
        "premium": False,
        "name": "Guest",
    }


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(8)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return salt, h


def _set_session_cookie(response: JSONResponse, payload: dict) -> None:
    response.set_cookie(
        COOKIE_NAME,
        _sign(payload),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=True,
        path="/",
    )


async def _user_profile(user: User) -> dict:
    now = datetime.utcnow()
    premium = bool(user.is_premium) and (not user.premium_until or user.premium_until > now)
    ident = {
        "kind": "user",
        "key": f"user:{user.id}",
        "user_id": user.id,
        "premium": premium,
        "name": user.nickname or user.email or user.id,
    }
    return ident, quota.status(ident["key"], premium)


# ───────────────────────────── endpoints ─────────────────────────────

@router.get("/session/status")
async def session_status(request: Request):
    ident = identity_from(request)
    ip = client_ip(request)
    free = quota.free_status(ip)
    uid = ident.get("user_id")
    token = request.cookies.get(COOKIE_NAME)
    has_session = bool(token and parse_token(token))
    return {
        "logged_in": True,  # always logged in as at least guest
        "has_session": has_session,
        "kind": ident["kind"],
        "name": ident["name"],
        "user_id": uid,
        "premium": ident["premium"],
        "free": free,
        "balance": quota.balance(uid) if uid else 0,
        "costs": quota.COST,
    }


@router.post("/session/guest")
async def guest_login(response: JSONResponse):
    """XP login window: 'Guest' with empty password → identity is the IP."""
    _set_session_cookie(response, {"k": "ip", "p": 0, "n": "Guest", "exp": int(time.time()) + COOKIE_MAX_AGE})
    return {"status": "ok", "mode": "guest"}


@router.post("/session/register")
async def register(data: dict, db: AsyncSession = Depends(get_db), response: JSONResponse = None):
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    nickname = (data.get("nickname") or "").strip() or email.split("@")[0]
    if not email or "@" not in email or len(password) < 4:
        raise HTTPException(400, "邮箱格式不对或密码太短(至少4位)")
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(409, "该邮箱已注册")
    salt, h = _hash_password(password)
    user = User(email=email, password_hash=f"sha256${salt}${h}", nickname=nickname)
    db.add(user)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(409, "该邮箱已注册")
    await db.refresh(user)
    ident = {"k": f"user:{user.id}", "p": 0, "n": user.nickname or email, "exp": int(time.time()) + COOKIE_MAX_AGE}
    _set_session_cookie(response, ident)
    return {"status": "ok", "user_id": user.id, "name": ident["n"], "premium": False}


@router.post("/session/login")
async def account_login(data: dict, db: AsyncSession = Depends(get_db), response: JSONResponse = None):
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash:
        raise HTTPException(401, "邮箱或密码错误")
    try:
        scheme, salt, h = user.password_hash.split("$")
    except Exception:
        raise HTTPException(401, "邮箱或密码错误")
    if scheme != "sha256" or _hash_password(password, salt)[1] != h:
        raise HTTPException(401, "邮箱或密码错误")
    user.last_login = datetime.utcnow()
    await db.commit()
    now = datetime.utcnow()
    premium = bool(user.is_premium) and (not user.premium_until or user.premium_until > now)
    ident = {"k": f"user:{user.id}", "p": 1 if premium else 0,
             "n": user.nickname or email, "exp": int(time.time()) + COOKIE_MAX_AGE}
    _set_session_cookie(response, ident)
    return {"status": "ok", "user_id": user.id, "name": ident["n"], "premium": premium}


@router.post("/session/refresh")
async def session_refresh(request: Request, db: AsyncSession = Depends(get_db), response: JSONResponse = None):
    """Re-issue cookie from DB (call after Premium purchase to pick up new tier)."""
    token = request.cookies.get(COOKIE_NAME)
    payload = parse_token(token) if token else None
    if payload and payload.get("k", "").startswith("user:"):
        uid = payload["k"].split(":", 1)[1]
        result = await db.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()
        if user:
            now = datetime.utcnow()
            premium = bool(user.is_premium) and (not user.premium_until or user.premium_until > now)
            ident = {"k": f"user:{user.id}", "p": 1 if premium else 0,
                     "n": user.nickname or user.email or "User",
                     "exp": int(time.time()) + COOKIE_MAX_AGE}
            _set_session_cookie(response, ident)
            st = quota.status(f"user:{user.id}", premium)
            return {"status": "ok", "user_id": user.id, "name": ident["n"], "premium": premium, "quota": st}
    # guest: refresh cookie so it never silently dies mid-session
    _set_session_cookie(response, {"k": "ip", "p": 0, "n": "Guest", "exp": int(time.time()) + COOKIE_MAX_AGE})
    return {"status": "ok", "mode": "guest"}


@router.post("/session/logout")
async def logout(response: JSONResponse):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "ok"}
