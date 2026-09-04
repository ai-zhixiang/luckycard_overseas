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


def _load() -> dict:
    if not os.path.exists(QUOTA_FILE):
        return {}
    try:
        with open(QUOTA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    fd = os.open(QUOTA_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    try:
        os.chmod(QUOTA_FILE, 0o600)
    except Exception:
        pass


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


def add_points(user_id: str, amount_usd: float, note: str = "") -> dict:
    pts = int(round(amount_usd * POINTS_PER_USD))
    return add_pts_raw(user_id, pts, note)


def add_pts_raw(user_id: str, pts: int, note: str = "") -> dict:
    with _lock:
        data = _load()
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
