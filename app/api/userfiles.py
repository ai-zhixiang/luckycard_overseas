"""My Documents (桌面版文件资源管理器) — 每账号私有空间, 超限自动清理, 突发创建熔断.

规则:
  * 空间:  data/userfiles/<账号身份sha1前24位>/   (账号 = user:<id> 或 ip:<ip>, 与钱包同一身份)
  * 免费上限: >30 个文件 或 >50MB → 记 wipe_at=now+1h, 前端弹警告条 "1小时后清空, 尽快下载";
    到期(或已到期)后任意请求触发整目录清空; 用户主动删到线以下则取消警告。
  * 超限后禁止继续新建(防一小时窗口内无限膨胀); 删除/下载不受限。
  * 熔断: 同 IP 10 秒内新建 >=20 次(疑似恶意批量创建) → 直接封 30 天(内存版, 重启清空, 与 static-manager 一致)。
"""
import hashlib
import json
import shutil
import tempfile
import time
import zipfile
from collections import deque
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from .auth import client_ip, identity_from

router = APIRouter()

ROOT_DIR = Path(__file__).resolve().parents[2] / "data" / "userfiles"

LIMIT_FILES = 30
LIMIT_BYTES = 50 * 1024 * 1024   # 50 MB
WIPE_SECONDS = 3600              # 超限后 1 小时清空

BURST_MAX = 20
BURST_WINDOW = 10                # 秒
BAN_SECONDS = 30 * 24 * 3600     # 30 天

META_NAME = ".meta.json"
TEXT_EXTS = {".txt", ".md", ".log"}
MAX_TEXT = 512 * 1024             # 读写文本上限 512KB
MAX_NAME = 80
BAD_NAME_CHARS = set('/\\:*?"<>|')

_BANS: dict[str, float] = {}     # ip -> 解封时间戳
_BURST: dict[str, deque] = {}    # ip -> 创建时间戳队列


# ───────────────────────── helpers ─────────────────────────

def _assert_not_banned(request: Request) -> None:
    ip = client_ip(request)
    until = _BANS.get(ip)
    if until and until > time.time():
        left = int((until - time.time()) // 3600)
        raise HTTPException(403, f"Banned: too many file creations in a short time (auto-unban in ~{left}h)")


def _note_create(request: Request) -> None:
    """每次 touch/mkdir 记一笔; 窗口内超阈值 → 直接封 IP."""
    ip = client_ip(request)
    now = time.time()
    dq = _BURST.setdefault(ip, deque())
    dq.append(now)
    while dq and dq[0] < now - BURST_WINDOW:
        dq.popleft()
    if len(dq) >= BURST_MAX:
        _BANS[ip] = now + BAN_SECONDS
        dq.clear()
        raise HTTPException(403, "Too many file creations in a short time — this IP has been banned for 30 days.")


def _account_dir(request: Request) -> Path:
    ident = identity_from(request)
    folder = hashlib.sha1(ident["key"].encode()).hexdigest()[:24]
    d = (ROOT_DIR / folder).resolve()   # 一律绝对路径, 避免 CWD 不同导致 rel/abs 混用
    d.mkdir(parents=True, exist_ok=True)
    return d


def _meta(root: Path) -> dict:
    try:
        return json.loads((root / META_NAME).read_text(encoding="utf-8"))
    except Exception:
        return {"wipe_at": None}


def _save_meta(root: Path, meta: dict) -> None:
    (root / META_NAME).write_text(json.dumps(meta), encoding="utf-8")


def _wipe_if_due(root: Path) -> None:
    """到期自动清空整个账号目录(含 meta)."""
    meta = _meta(root)
    if meta.get("wipe_at") and time.time() >= meta["wipe_at"]:
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True, exist_ok=True)


def _scan(root: Path) -> tuple[int, int]:
    """递归统计: 文件数, 总字节(不含 .meta.json)."""
    n_files = n_bytes = 0
    for p in root.rglob("*"):
        if p.name == META_NAME or not p.is_file():
            continue
        n_files += 1
        try:
            n_bytes += p.stat().st_size
        except OSError:
            pass
    return n_files, n_bytes


def _over_meta(root: Path) -> dict:
    n, b = _scan(root)
    over = n > LIMIT_FILES or b > LIMIT_BYTES
    meta = _meta(root)
    wipe_at = meta.get("wipe_at")
    if over and not wipe_at:
        wipe_at = int(time.time()) + WIPE_SECONDS
        _save_meta(root, {"wipe_at": wipe_at})
    elif not over and wipe_at:
        _save_meta(root, {"wipe_at": None})
        wipe_at = None
    return {"count": n, "bytes": b, "over": over, "wipe_at": wipe_at}


def _rel(p: Path, root: Path) -> str:
    return p.relative_to(root).as_posix()


def _resolve(root: Path, path: str, must_exist: bool = True) -> Path:
    """把客户端相对路径安全解析到账号目录内."""
    if path in ("", "/", "."):
        p = root
    else:
        try:
            parts = [s for s in path.replace("\\", "/").split("/") if s and s != "."]
            if any(s == ".." for s in parts):
                raise ValueError
            p = root.joinpath(*parts)
        except ValueError:
            raise HTTPException(400, "Invalid path")
    p = p.resolve()
    if not str(p).startswith(str(root.resolve())):
        raise HTTPException(400, "Invalid path")
    if must_exist and not p.exists():
        raise HTTPException(404, "Not found")
    return p


def _validate_name(name: str) -> str:
    name = (name or "").strip().strip(" .")
    if not name or len(name) > MAX_NAME:
        raise HTTPException(400, "Invalid name")
    if any(ch in BAD_NAME_CHARS for ch in name) or name.startswith("."):
        raise HTTPException(400, "Invalid name")
    return name


def _unique_name(parent: Path, base: str) -> str:
    """XP 式自动编号: New Folder, New Folder (2), ..."""
    if not (parent / base).exists():
        return base
    stem = Path(base).stem
    suffix = Path(base).suffix
    i = 2
    while (parent / f"{stem} ({i}){suffix}").exists():
        i += 1
    return f"{stem} ({i}){suffix}"


def fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}TB"


def _entry_list(root: Path, target: Path) -> list[dict]:
    items = []
    for e in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if e.name == META_NAME:
            continue
        is_dir = e.is_dir()
        try:
            st = e.stat()
        except OSError:
            continue
        items.append({
            "name": e.name,
            "path": _rel(e, root),
            "is_dir": is_dir,
            "size": 0 if is_dir else st.st_size,
            "size_display": "" if is_dir else fmt_size(st.st_size),
            "mtime": int(st.st_mtime),
            "kind": "folder" if is_dir else ("txt" if e.suffix.lower() in TEXT_EXTS else "file"),
        })
    return items


# ───────────────────────── endpoints ─────────────────────────

@router.get("/userfiles/status")
def userfiles_status(request: Request):
    _assert_not_banned(request)
    root = _account_dir(request)
    _wipe_if_due(root)
    st = _over_meta(root)
    ident = identity_from(request)
    wipe_at = st["wipe_at"]
    return {
        "kind": ident["kind"],
        "name": ident["name"],
        "count": st["count"],
        "bytes": st["bytes"],
        "size_display": fmt_size(st["bytes"]),
        "limit_files": LIMIT_FILES,
        "limit_bytes": LIMIT_BYTES,
        "limit_display": fmt_size(LIMIT_BYTES),
        "over": st["over"],
        "wipe_at": wipe_at,
        "seconds_left": max(0, wipe_at - int(time.time())) if wipe_at else None,
    }


@router.get("/userfiles/list")
def userfiles_list(request: Request, path: str = ""):
    _assert_not_banned(request)
    root = _account_dir(request)
    _wipe_if_due(root)
    target = _resolve(root, path)
    if not target.is_dir():
        raise HTTPException(400, "Not a directory")
    return {"path": _rel(target, root) if target != root else "", "items": _entry_list(root, target)}


@router.post("/userfiles/touch")
def userfiles_touch(request: Request, name: str = Form(""), parent: str = Form("")):
    _assert_not_banned(request)
    root = _account_dir(request)
    _wipe_if_due(root)
    st = _over_meta(root)
    if st["over"]:
        raise HTTPException(403, "Storage limit reached — files will be auto-deleted soon; delete some files or download them first.")
    _note_create(request)
    parent_dir = _resolve(root, parent, must_exist=False)
    if not parent_dir.is_dir():
        raise HTTPException(400, "Not a directory")
    base = _validate_name(name or "New Text Document.txt")
    if Path(base).suffix.lower() not in TEXT_EXTS and "." not in Path(base).name[1:]:
        base += ".txt"          # 没带扩展名 → 默认 txt
    name = _unique_name(parent_dir, base)
    (parent_dir / name).write_text("", encoding="utf-8")
    _over_meta(root)
    return {"status": "ok", "name": name, "path": _rel(parent_dir / name, root)}


@router.post("/userfiles/mkdir")
def userfiles_mkdir(request: Request, name: str = Form(""), parent: str = Form("")):
    _assert_not_banned(request)
    root = _account_dir(request)
    _wipe_if_due(root)
    st = _over_meta(root)
    if st["over"]:
        raise HTTPException(403, "Storage limit reached — files will be auto-deleted soon; delete some files or download them first.")
    _note_create(request)
    parent_dir = _resolve(root, parent, must_exist=False)
    if not parent_dir.is_dir():
        raise HTTPException(400, "Not a directory")
    base = _validate_name(name or "New Folder")
    name = _unique_name(parent_dir, base)
    (parent_dir / name).mkdir()
    return {"status": "ok", "name": name, "path": _rel(parent_dir / name, root)}


@router.get("/userfiles/read")
def userfiles_read(request: Request, path: str = ""):
    _assert_not_banned(request)
    root = _account_dir(request)
    _wipe_if_due(root)
    p = _resolve(root, path)
    if not p.is_file():
        raise HTTPException(400, "Not a file")
    if p.suffix.lower() not in TEXT_EXTS:
        raise HTTPException(400, "Only text files (.txt/.md/.log) can be opened here")
    if p.stat().st_size > MAX_TEXT:
        raise HTTPException(413, "File too large to open (max 512KB)")
    return {"name": p.name, "path": _rel(p, root), "content": p.read_text(encoding="utf-8", errors="replace")}


@router.post("/userfiles/save")
def userfiles_save(request: Request, path: str = Form(...), content: str = Form("")):
    _assert_not_banned(request)
    root = _account_dir(request)
    _wipe_if_due(root)
    p = _resolve(root, path)
    if not p.is_file():
        raise HTTPException(400, "Not a file")
    if p.suffix.lower() not in TEXT_EXTS:
        raise HTTPException(400, "Only text files (.txt/.md/.log) can be edited here")
    if len(content.encode("utf-8")) > MAX_TEXT:
        raise HTTPException(413, "File too large to save (max 512KB)")
    p.write_text(content, encoding="utf-8")
    _over_meta(root)
    return {"status": "ok"}


@router.post("/userfiles/delete")
def userfiles_delete(request: Request, path: str = Form(...)):
    _assert_not_banned(request)
    root = _account_dir(request)
    _wipe_if_due(root)
    p = _resolve(root, path)
    if p == root:
        raise HTTPException(400, "Cannot delete your My Documents")
    if p.is_dir():
        shutil.rmtree(p)        # 私有空间, 允许递归删文件夹
    else:
        p.unlink()
    _over_meta(root)
    return {"status": "ok", "deleted": _rel(p, root)}


@router.get("/userfiles/download")
def userfiles_download(request: Request, path: str = ""):
    _assert_not_banned(request)
    root = _account_dir(request)
    _wipe_if_due(root)
    p = _resolve(root, path)
    if not p.is_file():
        raise HTTPException(400, "Not a file")
    return FileResponse(p, filename=p.name, media_type="application/octet-stream")


@router.get("/userfiles/zip")
def userfiles_zip(request: Request):
    _assert_not_banned(request)
    root = _account_dir(request)
    _wipe_if_due(root)
    if not any(e.name != META_NAME for e in root.iterdir()):
        raise HTTPException(404, "My Documents is empty")
    tmp = Path(tempfile.gettempdir()) / f"mydocs_{hashlib.sha1(str(time.time()).encode()).hexdigest()[:8]}.zip"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(root.rglob("*")):
            if p.name == META_NAME or not p.is_file():
                continue
            zf.write(p, _rel(p, root))
    return FileResponse(tmp, filename="MyDocuments.zip", media_type="application/zip")
