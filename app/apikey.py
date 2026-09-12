"""API keys — lc-<32 hex>, HMAC-SHA256 (pepper) at rest.

Stored OUTSIDE app/static (never downloadable), file mode 0600.
Full key is returned ONLY at creation. Only the hash is persisted.

Format:  lc-<32 hex>            e.g. lc-4cb3924079656ad25224264911d6c5a8
At rest: {"<body>": {"hash": <hmac-sha256>, "uid", "label", "created",
                     "last_used", "uses"}}

Pepper lives in .env as HICARD_KEY_PEPPER. Lose it → every key is void.

Billing: API calls via a key NEVER use the per-IP free allowance — they
always spend Lucky Points from the owner's wallet. See charge_api_op().
"""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_FILE = os.path.join(DATA_DIR, "apikeys.json")

KEY_PREFIX = "lc-"
BODY_HEX_LEN = 32          # 16^32 ≈ 3.4e38 — brute force is hopeless
MAX_KEYS_PER_USER = 10

_lock = threading.Lock()
_pepper: bytes | None = None


def _get_pepper() -> bytes:
    """Read HICARD_KEY_PEPPER from settings (loaded from .env at startup)."""
    global _pepper
    if _pepper is None:
        val = os.environ.get("HICARD_KEY_PEPPER", "")
        if not val:
            try:
                from .config import settings
                val = settings.hicard_key_pepper or ""
            except Exception:
                val = ""
        if not val:
            raise RuntimeError(
                "HICARD_KEY_PEPPER is not set — add it to .env. "
                "Without it every existing API key becomes void."
            )
        _pepper = val.encode()
    return _pepper


def _hash_body(body: str) -> str:
    return hmac.new(_get_pepper(), body.encode(), hashlib.sha256).hexdigest()


def _load() -> dict:
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(db: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = DB_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, DB_FILE)          # atomic


def create_key(uid: str, label: str = "") -> tuple[str, dict]:
    """Mint a new key. Returns (full_key, record). Full key shown once only."""
    body = secrets.token_hex(BODY_HEX_LEN // 2)
    full_key = KEY_PREFIX + body
    with _lock:
        db = _load()
        rec = {
            "hash": _hash_body(body),
            "uid": uid,
            "label": label or "",
            "created": int(time.time()),
            "last_used": None,
            "uses": 0,
        }
        db[body] = rec
        _save(db)
    return full_key, rec


def verify_key(full_key: str | None, count_use: bool = True) -> dict | None:
    """O(1) lookup + single constant-time HMAC compare. None if invalid."""
    if not full_key or not isinstance(full_key, str):
        return None
    if not full_key.startswith(KEY_PREFIX):
        return None
    body = full_key[len(KEY_PREFIX):]
    if len(body) != BODY_HEX_LEN:
        return None

    with _lock:
        db = _load()
        rec = db.get(body)
        if not rec:
            return None
        if not hmac.compare_digest(rec["hash"], _hash_body(body)):
            return None
        if count_use:
            rec["last_used"] = int(time.time())
            rec["uses"] = rec.get("uses", 0) + 1
            db[body] = rec
            _save(db)
    return rec


def revoke_key(uid: str, key_id: str) -> bool:
    """Revoke by internal id (first 8 hex of body). Owner-scoped."""
    with _lock:
        db = _load()
        for body, rec in list(db.items()):
            if body.startswith(key_id) and rec.get("uid") == uid:
                del db[body]
                _save(db)
                return True
    return False


def list_keys(uid: str) -> list[dict]:
    """List a user's keys — masked, never the full key."""
    db = _load()
    return sorted(
        (
            {
                "id": body[:8],                                # internal, for revoke
                "key": KEY_PREFIX + "*" * BODY_HEX_LEN,        # lc-****... (half-width)
                "label": r.get("label", ""),
                "created": r.get("created"),
                "last_used": r.get("last_used"),
                "uses": r.get("uses", 0),
            }
            for body, r in db.items()
            if r.get("uid") == uid
        ),
        key=lambda x: x["created"] or 0,
        reverse=True,
    )


# ───────────────────────── billing (key-based) ─────────────────────────

class ApiKeyError(Exception):
    """Raised when a key is missing/invalid — mapped to HTTP 401."""


class ApiQuotaError(Exception):
    """Raised when the wallet cannot cover the op — mapped to HTTP 402."""

    def __init__(self, cost: int, balance: int):
        self.cost = cost
        self.balance = balance
        super().__init__(f"insufficient points: need {cost}, have {balance}")


def require_api_key(x_api_key: str | None) -> dict:
    """Validate a key from the X-API-Key header. Raises ApiKeyError if bad."""
    rec = verify_key(x_api_key)
    if not rec:
        raise ApiKeyError("Invalid API key")
    return rec


def charge_api_op(rec: dict, ops: list[str]) -> dict:
    """Spend Lucky Points for an API-key call.

    API traffic NEVER touches the per-IP free allowance — it always pays.
    Call refund_api_op() if the underlying AI call fails.
    """
    from . import quota

    uid = rec["uid"]
    cost = sum(quota.COST.get(o, 0) for o in ops)
    if cost <= 0:
        return {"method": "points", "cost": 0, "paid": 0,
                "balance": quota.balance(uid)}

    if not quota.spend_points(uid, cost, note=f"API:{'+'.join(ops)}"):
        raise ApiQuotaError(cost, quota.balance(uid))
    return {"method": "points", "cost": cost, "paid": cost,
            "balance": quota.balance(uid), "uid": uid}


def refund_api_op(rec: dict, ops: list[str], charge: dict | None) -> None:
    """Give points back when the AI call failed (never charge for errors)."""
    from . import quota

    if not charge or not charge.get("paid"):
        return
    quota.add_pts_raw(rec["uid"], charge["paid"],
                      note=f"退款(API:{'+'.join(ops)}失败)")
