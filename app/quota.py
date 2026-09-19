"""Ledger — free daily allowance per IP + Lucky Point wallet per user.

Stored OUTSIDE app/static (never downloadable), file mode 0600.

Rules:
  - Every IP gets FREE_DAILY free AI ops per day (guest & logged-in alike).
  - Past the free allowance, a logged-in user pays Lucky Points from wallet.
    ($1 = 100 pts via PayPal recharge.) Guests without points get blocked.
  - Op costs: dict COST below — poem 10 / vision 10 / art 15 / stylize 15.
Day boundary = Asia/Shanghai midnight.
"""
import json
import os
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
QUOTA_FILE = os.path.join(DATA_DIR, "quota.json")

FREE_DAILY = 3            # free AI ops per IP per day
USD_PER_100_PTS = 1.0     # $1 → 100 Lucky Points
MIN_RECHARGE_USD = 1      # integer dollars
POINTS_PER_USD = 100

# AI op → Lucky Points
COST = {
    "poem": 10,       # DeepSeek text
    "vision": 10,     # Doubao photo analysis (cache hit → 0)
    "art": 15,        # Seedream 2K image
    "stylize": 15,    # vision + redraw pipeline
}

_lock = threading.Lock()
_tz = ZoneInfo("Asia/Shanghai")


def _day() -> str:
    return datetime.now(_tz).strftime("%Y-%m-%d")


class QuotaCorruptError(RuntimeError):
    """quota.json 损坏 —— 宁可报错也不要用空数据覆盖写回(会把所有人余额清零)."""


def _load() -> dict:
    if not os.path.exists(QUOTA_FILE):
        return {}
    try:
        with open(QUOTA_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("quota.json 顶层不是对象")
        return data
    except Exception as e:
        # 损坏: 保留现场(.corrupt)并抛错, 阻止后续 _save 用空数据覆盖
        try:
            os.replace(QUOTA_FILE, QUOTA_FILE + ".corrupt")
        except Exception:
            pass
        raise QuotaCorruptError(f"quota.json 损坏, 已改名为 .corrupt: {e}") from e


def _save(data: dict) -> None:
    """原子写: 先写 .tmp 再 os.replace —— 断电/并发下不会残留半截文件."""
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = QUOTA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    try:
        os.chmod(tmp, 0o600)
    except Exception:
        pass
    os.replace(tmp, QUOTA_FILE)   # 原子替换


# ───────────────────────── free allowance (per IP) ─────────────────────────

def _ip_key(ip: str) -> str:
    return f"ip:{ip}"


def free_status(ip: str) -> dict:
    """How many free ops remain today for this IP."""
    d = _day()
    with _lock:
        data = _load()
        used = int((data.get(_ip_key(ip)) or {}).get(d, 0))
    return {"used": used, "limit": FREE_DAILY, "remaining": max(0, FREE_DAILY - used)}


def free_take(ip: str) -> bool:
    """Atomically consume one free op. True if free slot was available."""
    d = _day()
    with _lock:
        data = _load()
        key = _ip_key(ip)
        entry = data.get(key) or {}
        entry = {k: v for k, v in entry.items() if k >= d}
        used = int(entry.get(d, 0))
        if used >= FREE_DAILY:
            data[key] = entry
            _save(data)
            return False
        entry[d] = used + 1
        data[key] = entry
        _save(data)
        return True


def free_refund(ip: str) -> None:
    d = _day()
    with _lock:
        data = _load()
        key = _ip_key(ip)
        entry = data.get(key) or {}
        if int(entry.get(d, 0)) > 0:
            entry[d] = int(entry[d]) - 1
            if entry[d] <= 0:
                entry.pop(d, None)
            data[key] = entry
            _save(data)


# ───────────────────────── Lucky Point wallet (per user) ─────────────────────────

def _wallet(data: dict, user_id: str) -> dict:
    w = data.setdefault("wallets", {}).setdefault(user_id, {})
    w.setdefault("points", 0)
    w.setdefault("history", [])
    return w


def balance(user_id: str) -> int:
    with _lock:
        data = _load()
        w = data.get("wallets", {}).get(user_id, {})
        return int(w.get("points", 0))


def add_points(user_id: str, amount_usd: float, note: str = "", once_key: str = "") -> dict:
    """once_key: 非空时做幂等键 — 同一 key 只入账一次 (防 webhook/capture 重复加币)."""
    pts = int(round(amount_usd * POINTS_PER_USD))
    return add_pts_raw(user_id, pts, note, once_key=once_key)


def add_pts_raw(user_id: str, pts: int, note: str = "", once_key: str = "") -> dict:
    with _lock:
        data = _load()
        # 幂等: 已处理过的 once_key 直接返回当前余额, 不重复加
        used = data.setdefault("once_keys", {})
        if once_key:
            if once_key in used:
                w0 = data.get("wallets", {}).get(user_id, {})
                return {"added": 0, "balance": int(w0.get("points", 0)), "duplicate": True}
            used[once_key] = datetime.now(_tz).strftime("%Y-%m-%d %H:%M:%S")
            # 只留最近 2000 条, 防文件无限膨胀
            if len(used) > 2000:
                for k in sorted(used, key=lambda x: used[x])[:len(used) - 2000]:
                    used.pop(k, None)
        w = _wallet(data, user_id)
        w["points"] = int(w["points"]) + pts
        w["history"].append({
            "t": datetime.now(_tz).strftime("%Y-%m-%d %H:%M:%S"),
            "delta": f"{pts:+d}",
            "note": note,
        })
        w["history"] = w["history"][-50:]
        _save(data)
        return {"added": pts, "balance": int(w["points"])}


def spend_points(user_id: str, cost: int, note: str = "") -> bool:
    with _lock:
        data = _load()
        w = _wallet(data, user_id)
        if int(w["points"]) < cost:
            return False
        w["points"] = int(w["points"]) - cost
        w["history"].append({
            "t": datetime.now(_tz).strftime("%Y-%m-%d %H:%M:%S"),
            "delta": f"-{cost}",
            "note": note,
        })
        w["history"] = w["history"][-50:]
        _save(data)
        return True


def wallet_info(user_id: str) -> dict:
    with _lock:
        data = _load()
        w = data.get("wallets", {}).get(user_id, {})
        return {
            "points": int(w.get("points", 0)),
            "history": w.get("history", [])[-10:],
        }


def status(account_key: str, premium: bool = False) -> dict:
    """统一额度视图: 免费剩余 + 钱包余额 + 会员状态.

    account_key: "user:<id>" 或 "ip:<ip>" —— 与钱包同一身份.
    (auth.py 曾调用此函数但实现缺失, 走到即 AttributeError→500)
    """
    if account_key.startswith("ip:"):
        free = free_status(account_key[3:])
    else:
        free = {"used": 0, "limit": FREE_DAILY, "remaining": 0}

    with _lock:
        data = _load()
        w = data.get("wallets", {}).get(account_key, {})
        points = int(w.get("points", 0))

    return {
        "points": points,
        "free": free,
        "is_member": bool(premium),
        "costs": COST,
    }
