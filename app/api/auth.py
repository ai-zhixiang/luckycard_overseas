"""Session & identity — signed cookie, guest-by-IP, account register/login.

Cookie `lc_sess` = base64url(json).hexdigest (HMAC-SHA256 with SECRET_KEY).
Payload: {"k": "user:<id>" | "ip", "p": 0|1 (premium), "n": name, "exp": ts}
Guests are keyed by their client IP server-side; the cookie just records that
they went through the XP login window so the UI can show an identity.
"""
import asyncio
import base64
import hashlib
import hmac
import json
import re
import secrets
import threading
import time
from datetime import datetime

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

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

# 邮箱格式: 本地部分@域名.TLD(≥2 字母)。挡掉 "a@b" / "@@@" / "x@y.z" 这类。
# (挡的是"格式", 挡不了"格式对但不是你的邮箱" —— 那要靠邮箱验证。)
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")

# 常见一次性邮箱域名 —— 直接拒。想放行就从这里删。
DISPOSABLE_DOMAINS = {
    "mailinator.com", "10minutemail.com", "guerrillamail.com", "sharklasers.com",
    "tempmail.com", "temp-mail.org", "throwawaymail.com", "yopmail.com",
    "trashmail.com", "getnada.com", "maildrop.cc", "dispostable.com",
    "fakeinbox.com", "mailnesia.com", "mytemp.email", "emailondeck.com",
}


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


# ── 密码哈希: Argon2id (memory_cost=19MiB, time_cost=2, parallelism=1) ──
# 本机实测单次 ~23ms, 只在注册/登录时各算一次, 不影响页面速度。
# 存储格式 "argon2$<encoded>"; 老的 "sha256$salt$hash" 记录仍可登录,
# 验证通过后自动重存为 Argon2 (无需重置密码)。
_PH = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1,
                     hash_len=32, salt_len=16)


def _hash_password(password: str) -> str:
    """→ 入库字符串。Argon2 编码串自带算法标识: $argon2id$v=19$m=19456,t=2,p=1$..."""
    return _PH.hash(password)


def _verify_password(password: str, stored: str) -> tuple[bool, bool]:
    """(是否正确, 是否需要升级重存)。兼容老的 sha256 记录。"""
    if not stored:
        return False, False
    s = stored
    if s.startswith("argon2$"):        # 兼容早期写法 "argon2$$argon2id$…"
        s = s[len("argon2"):]
    if s.startswith("$argon2"):        # Argon2id 编码串
        try:
            _PH.verify(s, password)
        except VerifyMismatchError:
            return False, False
        except Exception:
            return False, False
        return True, _PH.check_needs_rehash(s)
    if stored.startswith("sha256$"):   # 老记录 sha256$salt$hash
        salt, _, h = stored[len("sha256$"):].partition("$")
        if not salt or not h:
            return False, False
        calc = hashlib.sha256((salt + password).encode()).hexdigest()
        if hmac.compare_digest(calc, h):
            return True, True          # 老方案 → 顺势升级
    return False, False


# ── 登录/注册限流 (内存计数, 重启清空) ──
# 登录只统计"失败"次数: 连续 5 次错密码 → 该 IP 锁 60 秒; 登录成功即清零。
# 所以正常用户永远不会被自己的成功登录挡住。
_fail_lock = threading.Lock()
_login_fails: dict = {}
_login_hits: dict = {}
LOGIN_MAX_FAILS = 5
LOGIN_WINDOW = 60
REGISTER_MAX = 3
REGISTER_WINDOW = 600


def _login_guard(key: str) -> None:
    now = time.time()
    with _fail_lock:
        hist = [t for t in _login_fails.get(key, []) if now - t < LOGIN_WINDOW]
        if len(hist) >= LOGIN_MAX_FAILS:
            wait = int(LOGIN_WINDOW - (now - hist[0]))
            raise HTTPException(429, f"密码错误次数过多, 请 {wait} 秒后再试")
        _login_fails[key] = hist


def _login_failed(key: str) -> None:
    with _fail_lock:
        _login_fails.setdefault(key, []).append(time.time())


def _login_ok(key: str) -> None:
    with _fail_lock:
        _login_fails.pop(key, None)


def _register_guard(key: str) -> None:
    now = time.time()
    with _fail_lock:
        hist = [t for t in _login_hits.get(key, []) if now - t < REGISTER_WINDOW]
        if len(hist) >= REGISTER_MAX:
            wait = int(REGISTER_WINDOW - (now - hist[0]))
            raise HTTPException(429, f"注册太频繁, 请 {wait} 秒后再试")
        hist.append(now)
        _login_hits[key] = hist


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
async def register(request: Request, data: dict, db: AsyncSession = Depends(get_db), response: JSONResponse = None):
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    nickname = (data.get("nickname") or "").strip() or email.split("@")[0] or "User"
    if len(email) > 254 or not EMAIL_RE.match(email):
        raise HTTPException(400, "邮箱格式不对(需要形如 name@example.com)")
    if len(password) < 8:
        raise HTTPException(400, "密码太短(至少8位)")
    domain = email.rsplit("@", 1)[1]
    if any(domain == d or domain.endswith("." + d) for d in DISPOSABLE_DOMAINS):
        raise HTTPException(400, "不支持临时邮箱, 请用常用邮箱注册")
    _register_guard(client_ip(request))
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(409, "该邮箱已注册")
    # Argon2id 是 CPU 密集的阻塞调用 → 丢线程, 别钉住事件循环
    pw_hash = await asyncio.to_thread(_hash_password, password)
    user = User(email=email, password_hash=pw_hash, nickname=nickname)
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
async def account_login(request: Request, data: dict, db: AsyncSession = Depends(get_db), response: JSONResponse = None):
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    ipk = client_ip(request)
    _login_guard(ipk)                     # 连续错 5 次 → 该 IP 锁 60s
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not user.password_hash:
        _login_failed(ipk)
        raise HTTPException(401, "邮箱或密码错误")
    ok, needs_upgrade = await asyncio.to_thread(_verify_password, password, user.password_hash)
    if not ok:
        _login_failed(ipk)
        raise HTTPException(401, "邮箱或密码错误")
    _login_ok(ipk)
    if needs_upgrade:
        # 老 sha256 记录: 登录成功后顺手升级成 Argon2id
        user.password_hash = await asyncio.to_thread(_hash_password, password)
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
