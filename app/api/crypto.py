"""Crypto Challenge wall — 密文挑战墙 (boonxiong2 自创算法 + 经典算法).

Challenge list lives in data/crypto_challenges.json (0600, outside static).
Answers are stored ONLY as SHA-256 (never plaintext). Submissions are rate
limited per IP per challenge (in-memory, cleared on restart).

前端 UI 全英文; 后端错误消息保持中文(调试惯例)。
"""

import hashlib
import json
import os
import threading
import time

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from .auth import client_ip, identity_from
from .. import board, quota

router = APIRouter()

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CHALL_FILE = os.path.join(DATA_DIR, "crypto_challenges.json")
SOLVED_FILE = os.path.join(DATA_DIR, "crypto_solved.json")

_lock = threading.Lock()
# in-memory attempt counter: (ip, qid) -> [timestamps]  (5 attempts / qid / ip)
_attempts = {}
MAX_ATTEMPTS = 5

# 每题可答次数窗口(防脚本爆破答案 hash — 虽然 hash 单向, 但答案本身可能被字典撞)
ATTEMPT_WINDOW = 300  # seconds; keep 5 attempts per 5 minutes per qid


def _load_challenges() -> list:
    if not os.path.exists(CHALL_FILE):
        return []
    try:
        with open(CHALL_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _challenge_by_qid(qid: str):
    for ch in _load_challenges():
        if ch.get("qid") == qid:
            return ch
    return None


def _load_solved() -> dict:
    if not os.path.exists(SOLVED_FILE):
        return {}
    try:
        with open(SOLVED_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_solved(data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    fd = os.open(SOLVED_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    try:
        os.chmod(SOLVED_FILE, 0o600)
    except Exception:
        pass


def _ip_key(request: Request) -> str:
    return identity_from(request)["key"]  # ip:<addr> 或 user:<id>


def _check_attempts(ipk: str, qid: str) -> int:
    """返回剩余可提交次数; 超限抛 429。"""
    now = time.time()
    with _lock:
        key = (ipk, qid)
        hist = [t for t in _attempts.get(key, []) if now - t < ATTEMPT_WINDOW]
        if len(hist) >= MAX_ATTEMPTS:
            wait = int(ATTEMPT_WINDOW - (now - hist[0]))
            raise HTTPException(status_code=429,
                                detail=f"尝试次数过多, 请 {wait} 秒后再试 (每题每 {MAX_ATTEMPTS} 次 / 5分钟)")
        _attempts[key] = hist
        return MAX_ATTEMPTS - len(hist)


def _record_attempt(ipk: str, qid: str) -> None:
    with _lock:
        key = (ipk, qid)
        _attempts.setdefault(key, []).append(time.time())


class SubmitIn(BaseModel):
    qid: str
    answer: str


@router.get("/crypto/list")
def crypto_list(request: Request):
    """挑战列表(含密文或下载链接)。列表信息本身公开 —— 密文就是要给人看的。"""
    ipk = _ip_key(request)
    solved = _load_solved()
    mine = set(solved.get(ipk, []))
    out = []
    for ch in _load_challenges():
        item = {
            "qid": ch["qid"],
            "diff": ch.get("diff", 1),
            "algo": ch.get("algo", ""),
            "hint": ch.get("hint", ""),
            "pts": ch.get("pts", 0),
            "solved": ch["qid"] in mine,
            "cipher": ch.get("cipher"),
            "file": ch.get("file"),
        }
        out.append(item)
    return {"challenges": out}


@router.post("/crypto/submit")
def crypto_submit(body: SubmitIn, request: Request):
    qid = (body.qid or "").strip().upper()
    answer = (body.answer or "").strip().lower()
    ch = _challenge_by_qid(qid)
    if ch is None:
        raise HTTPException(status_code=404, detail=f"挑战 {qid} 不存在")
    if not answer:
        raise HTTPException(status_code=400, detail="答案不能为空")

    ipk = _ip_key(request)
    solved = _load_solved()
    mine = set(solved.get(ipk, []))

    if qid in mine:
        return {"ok": True, "already": True, "qid": qid}

    remaining = _check_attempts(ipk, qid)
    digest = hashlib.sha256(answer.encode("utf-8")).hexdigest()
    _record_attempt(ipk, qid)

    if digest == ch.get("sha256", ""):
        mine.add(qid)
        solved[ipk] = sorted(mine)
        _save_solved(solved)
        pts = int(ch.get("pts", 0))
        ident = identity_from(request)
        uid = ident.get("user_id")
        name = board.display_name(ipk, ident, client_ip(request))
        rec = board.record_solve(ipk, name, qid, pts, ident["kind"])
        # 只有登录用户进钱包 (站长定: 游客可上榜但不发分, 推注册)
        credited = False
        if uid and pts > 0 and rec.get("new"):
            quota.add_pts_raw(uid, pts, note=f"密文挑战 {qid} 破解奖励")
            credited = True
        return {
            "ok": True, "already": False, "qid": qid, "pts": pts,
            "credited": credited,
            "balance": quota.balance(uid) if uid else 0,
            "board_points": rec.get("points", 0),
        }
    return {"ok": False, "qid": qid, "attempts_left": remaining - 1}


def _ip_key_of(request: Request) -> str:
    return identity_from(request)["key"]


@router.get("/crypto/leaderboard")
def crypto_leaderboard(limit: int = 20):
    """公开排行榜 — 昵称 + 破题数 + 总分 + 最后破解时间。"""
    limit = max(1, min(int(limit or 20), 100))
    data = board.leaderboard(limit)
    data["points_per_qid"] = {c["qid"]: int(c.get("pts", 0)) for c in _load_challenges()}
    data["total_challenges"] = len(_load_challenges())
    return data


@router.get("/crypto/cert")
def crypto_cert(request: Request):
    """当前身份的破题证书数据(前端渲染成可分享页面)。"""
    ipk = _ip_key_of(request)
    data = board.cert(ipk)
    if data is None:
        return {"ok": False, "reason": "no_solves"}
    data["ok"] = True
    data["total_challenges"] = len(_load_challenges())
    return data
