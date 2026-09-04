import os, time, fnmatch, hashlib, hmac, secrets
from pathlib import Path
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse, FileResponse
from typing import Optional

router = APIRouter()

STATIC_DIR = Path("app/static").resolve()
# SHA-256 hash of "Administrator_Windows11" — plaintext never stored
SECRET_HASH = "c2af5ef7b4a6e4aa511aa80030b5ddbe07a49535e6ab5895ddbb5a25f022a14d"
# Random key for signing cookies (regenerates on restart — sessions don't survive restart)
COOKIE_SECRET = secrets.token_hex(32)

# ─── IP fail2ban: 15 次登录失败封 30 天(内存版,重启清空) ───
BAN_LIMIT = 15
BAN_SECONDS = 30 * 24 * 3600
_FAILS: dict = {}  # ip -> [fail_count, first_fail_ts]

def _client_ip(request: Request) -> str:
    # nginx 已设 X-Real-IP($remote_addr),不可伪造;直连时退回 client.host
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")

def _check_banned(request: Request) -> None:
    ip = _client_ip(request)
    rec = _FAILS.get(ip)
    if not rec:
        return
    count, t0 = rec
    if time.time() - t0 > BAN_SECONDS:
        _FAILS.pop(ip, None)  # 到期自动解封
        return
    if count >= BAN_LIMIT:
        raise HTTPException(403, "The operation interrupted, because IP was banned")

def make_cookie_sig(value: str) -> str:
    """Sign a cookie value with HMAC-SHA256."""
    return hmac.new(COOKIE_SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()

def get_admin(request: Request) -> bool:
    """Check if request has a valid admin cookie. Returns True/False."""
    cookie = request.cookies.get("static_admin")
    if not cookie:
        return False
    # Cookie format: "1:<signature>"
    parts = cookie.split(":", 1)
    if len(parts) != 2:
        return False
    expected_sig = make_cookie_sig(parts[0])
    if parts[1] != expected_sig:
        return False
    return parts[0] == "1"

def require_admin(request: Request):
    """Dependency: raise 403 if no valid admin cookie."""
    if not get_admin(request):
        raise HTTPException(403, "Admin authentication required")

HUMAN_TYPES = {
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image", ".svg": "image", ".webp": "image", ".ico": "image",
    ".mp3": "audio", ".wav": "audio", ".ogg": "audio", ".flac": "audio",
    ".mp4": "video", ".webm": "video",
    ".zip": "archive", ".tar": "archive", ".gz": "archive", ".7z": "archive", ".rar": "archive",
    ".exe": "executable", ".AppImage": "executable", ".dmg": "executable",
    ".html": "code", ".js": "code", ".css": "code", ".json": "code",
    ".pdf": "document", ".txt": "document",
}

def fmt_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}TB"

def fmt_time(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))

# ─── Auth endpoints (饼干) ───

@router.post("/static/login")
async def login(request: Request, token: str = Form(...)):
    """Verify token, set admin cookie."""
    _check_banned(request)
    if hashlib.sha256(token.encode()).hexdigest() != SECRET_HASH:
        ip = _client_ip(request)
        rec = _FAILS.get(ip)
        if rec:
            rec[0] += 1
        else:
            rec = [1, time.time()]
        _FAILS[ip] = rec
        raise HTTPException(403, "Invalid token")
    _FAILS.pop(_client_ip(request), None)  # 成功登录清除失败记录
    sig = make_cookie_sig("1")
    resp = JSONResponse({"status": "ok", "admin": True})
    resp.set_cookie(
        key="static_admin",
        value=f"1:{sig}",
        max_age=86400 * 7,  # 7 days
        httponly=True,
        samesite="lax",
        path="/",
    )
    return resp

@router.get("/static/check")
async def check_admin(request: Request):
    """Check if the current request has a valid admin cookie."""
    return {"admin": get_admin(request)}

@router.post("/static/logout")
async def logout():
    """Clear the admin cookie."""
    resp = JSONResponse({"status": "ok"})
    resp.delete_cookie(key="static_admin", path="/")
    return resp

# ─── File operations (admin ops read cookie automatically) ───

STYLIZED_DIR = STATIC_DIR / "stylized"
HIDDEN_DIRS = {"stylized"}

@router.get("/static/list")
async def list_files(request: Request, path: str = "", search: str = ""):
    """List files in a directory. Pass subpath like 'images' or '' for root."""
    base = STATIC_DIR
    if path:
        target = base / path
        try:
            target = target.resolve()
            if not str(target).startswith(str(base)):
                raise HTTPException(400, "Invalid path")
        except:
            raise HTTPException(400, "Invalid path")
        if not target.exists() or not target.is_dir():
            raise HTTPException(404, "Directory not found")

        # Block non-admin from accessing stylized directory
        if str(target).startswith(str(STYLIZED_DIR)) and not get_admin(request):
            raise HTTPException(403, "Admin access required")
    else:
        target = base

    items = []
    try:
        entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        raise HTTPException(403, "Permission denied")

    is_admin = get_admin(request)
    for entry in entries:
        name = entry.name
        if name.startswith("."):
            continue
        # Hide protected directories from non-admin
        if not is_admin and name in HIDDEN_DIRS:
            continue
        is_dir = entry.is_dir()
        stat = entry.stat()
        size = stat.st_mtime if is_dir else stat.st_size
        mtime = stat.st_mtime

        ext = Path(name).suffix.lower()
        file_type = HUMAN_TYPES.get(ext, "folder" if is_dir else "file")

        if search and search.lower() not in name.lower():
            continue

        items.append({
            "name": name,
            "path": str(entry.relative_to(base)),
            "is_dir": is_dir,
            "size": size,
            "size_display": fmt_size(stat.st_size) if not is_dir else "",
            "mtime": mtime,
            "mtime_display": fmt_time(mtime),
            "type": file_type,
        })

    return {"items": items, "current_path": path, "total": len(items)}


@router.post("/static/delete")
async def delete_file(request: Request, file_path: str = Form(...)):
    """Delete a file or empty directory. Requires admin cookie."""
    require_admin(request)

    target = (STATIC_DIR / file_path).resolve()
    base = STATIC_DIR.resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(400, "Invalid path")

    if not target.exists():
        raise HTTPException(404, "File not found")

    if target.is_dir():
        if any(target.iterdir()):
            raise HTTPException(400, "Directory not empty")
        target.rmdir()
    else:
        target.unlink()

    return {"status": "ok", "deleted": file_path}


@router.post("/static/upload")
async def upload_file(request: Request, file: UploadFile = File(...), target_path: str = Form("")):
    """Upload a file. Requires admin cookie."""
    require_admin(request)

    dest_dir = (STATIC_DIR / target_path).resolve()
    base = STATIC_DIR.resolve()
    if not str(dest_dir).startswith(str(base)):
        raise HTTPException(400, "Invalid path")

    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / file.filename

    content = await file.read()
    if len(content) > 500 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 500MB)")

    with open(dest_file, "wb") as f:
        f.write(content)

    return {"status": "ok", "file": str(dest_file.relative_to(base)), "size": len(content)}


@router.post("/static/mkdir")
async def create_dir(request: Request, dir_name: str = Form(...), parent_path: str = Form("")):
    """Create a new directory. Requires admin cookie."""
    require_admin(request)

    new_dir = (STATIC_DIR / parent_path / dir_name).resolve()
    base = STATIC_DIR.resolve()
    if not str(new_dir).startswith(str(base)):
        raise HTTPException(400, "Invalid path")

    new_dir.mkdir(parents=False, exist_ok=False)
    return {"status": "ok", "dir": str(new_dir.relative_to(base))}
