"""Crypto challenge leaderboard + certificate data (server-side).

Records every solver keyed by the same identity as quota/prefs
(ip:<addr> guest | user:<id> account). Guests are welcome on the board but
only LOGGED-IN users get Lucky Points paid into their wallet (user decision
2026-09: keeps the board open while making registration worth it).

File: app/data/crypto_board.json (0600, outside static — never downloadable).
"""
import json
import os
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
BOARD_FILE = os.path.join(DATA_DIR, "crypto_board.json")

_tz = ZoneInfo("Asia/Shanghai")
_lock = threading.Lock()


def _load() -> dict:
    if not os.path.exists(BOARD_FILE):
        return {}
    try:
        with open(BOARD_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    fd = os.open(BOARD_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    try:
        os.chmod(BOARD_FILE, 0o600)
    except Exception:
        pass


def display_name(key: str, ident: dict, ip: str) -> str:
    """user:<id> → nickname; ip:<addr> → Guest-<last 4 of addr>."""
    if key.startswith("user:"):
        return ident.get("name") or "User"
    tail = ip.replace(".", "").replace(":", "")[-4:] or "0000"
    return f"Guest-{tail}"


def record_solve(key: str, name: str, qid: str, pts: int, kind: str) -> dict:
    """Add qid to this identity's solved list. Idempotent per qid."""
    now = datetime.now(_tz).strftime("%Y-%m-%d %H:%M:%S")
    with _lock:
        data = _load()
        entry = data.get(key) or {}
        solved = entry.get("solved") or []
        if qid in solved:
            return {"solved": solved, "points": int(entry.get("points", 0)), "new": False}
        solved.append(qid)
        entry["solved"] = solved
        entry["points"] = int(entry.get("points", 0)) + int(pts)
        entry["name"] = name
        entry["kind"] = kind
        entry["first"] = entry.get("first") or now
        entry["last"] = now
        data[key] = entry
        _save(data)
        return {"solved": solved, "points": int(entry["points"]), "new": True}


def _rank_rows() -> list:
    """Sorted board rows: most points, then most solved, then earliest last solve."""
    data = _load()
    rows = []
    for key, e in data.items():
        rows.append({
            "key": key,
            "name": e.get("name") or ("User" if key.startswith("user:") else "Guest"),
            "kind": e.get("kind") or ("user" if key.startswith("user:") else "ip"),
            "solved": list(e.get("solved") or []),
            "points": int(e.get("points", 0)),
            "first": e.get("first"),
            "last": e.get("last"),
        })
    rows.sort(key=lambda r: (-r["points"], -len(r["solved"]), r["last"] or ""))
    return rows


def leaderboard(limit: int = 20) -> dict:
    rows = _rank_rows()
    out = []
    for i, r in enumerate(rows[:limit], start=1):
        out.append({
            "rank": i,
            "name": r["name"],
            "kind": r["kind"],
            "solved_count": len(r["solved"]),
            "points": r["points"],
            "last": r["last"],
        })
    return {"rows": out, "total_players": len(rows)}


def cert(key: str) -> dict | None:
    """Per-solver certificate data; None when this identity has nothing solved."""
    data = _load()
    e = data.get(key)
    if not e or not e.get("solved"):
        return None
    return {
        "name": e.get("name") or "Guest",
        "kind": e.get("kind") or ("user" if key.startswith("user:") else "ip"),
        "solved": list(e.get("solved") or []),
        "points": int(e.get("points", 0)),
        "first": e.get("first"),
        "last": e.get("last"),
    }
