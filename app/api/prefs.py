"""User preferences (server-side) — Clippy assistant on/off, etc.

为什么存服务器而不是 cookie: 清浏览器 cookie 后偏好不丢。
访客按 IP 记 (ip:1.2.3.4), 登录用户按账号记 (user:<id>), 与 quota.py 同一套身份。

文件: data/prefs.json, static 之外不可下载, 0600。
"""
import json
import os
import threading

from fastapi import APIRouter, Request
from pydantic import BaseModel

from .auth import identity_from

router = APIRouter()

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PREFS_FILE = os.path.join(DATA_DIR, "prefs.json")

_lock = threading.Lock()

DEFAULTS = {
    "clippy": True,  # Clippy pops up with per-app tips on window open
}


def _load() -> dict:
    if not os.path.exists(PREFS_FILE):
        return {}
    try:
        with open(PREFS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    fd = os.open(PREFS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    try:
        os.chmod(PREFS_FILE, 0o600)
    except Exception:
        pass


def get_pref(request: Request, name: str) -> bool:
    key = identity_from(request)["key"]
    with _lock:
        data = _load()
        entry = data.get(key) or {}
        return bool(entry.get(name, DEFAULTS.get(name, True)))


def set_pref(request: Request, name: str, value: bool) -> None:
    key = identity_from(request)["key"]
    with _lock:
        data = _load()
        entry = dict(data.get(key) or {})
        entry[name] = bool(value)
        data[key] = entry
        _save(data)


class PrefsBody(BaseModel):
    clippy: bool | None = None


@router.get("/prefs")
async def prefs_get(request: Request):
    return {"clippy": get_pref(request, "clippy")}


@router.put("/prefs")
async def prefs_put(request: Request, body: PrefsBody):
    if body.clippy is not None:
        set_pref(request, "clippy", body.clippy)
    return {"clippy": get_pref(request, "clippy")}
