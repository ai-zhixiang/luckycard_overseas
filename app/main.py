import os
import shutil, uuid, json, base64, subprocess
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from .database import engine, Base
from .api import cards, music, auth, payment, paypal, static_manager, wallet, culture, prefs
from .config import settings
from pydantic import BaseModel
import httpx

app = FastAPI(title="Lucky Card", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """404 → XP 风格错误页; /api 路径仍返回 JSON 错误。"""
    if exc.status_code == 404 and not request.url.path.startswith("/api"):
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

app.include_router(cards.router, prefix="/api", tags=["cards"])
app.include_router(music.router, prefix="/api", tags=["music"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(payment.router, prefix="/api", tags=["payment"])
app.include_router(paypal.router, prefix="/api", tags=["paypal"])
app.include_router(wallet.router, prefix="/api", tags=["wallet"])
app.include_router(static_manager.router, prefix="/api", tags=["static"])
app.include_router(culture.router, prefix="/api", tags=["culture"])
app.include_router(prefs.router, prefix="/api", tags=["prefs"])

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/card/{card_id}")
async def card_short(card_id: str):
    """短链 /card/{id} → 卡片分享页（OG 友好）"""
    return RedirectResponse(url=f"/api/card-share/{card_id}")

@app.get("/download/source")
async def download_source():
    zip_path = "app/static/luckycard-source.zip"
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename="luckycard-source.zip",
        headers={"Content-Disposition": 'attachment; filename="luckycard-source.zip"'}
    )

@app.get("/stylize")
async def stylize_page(request: Request):
    return templates.TemplateResponse("stylize.html", {"request": request})

@app.get("/api/check-country")
async def check_country(request: Request):
    """Server-side IP country check to avoid CORS/403 issues."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://ip-api.com/json/?fields=countryCode",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            data = resp.json()
            return {"country": data.get("countryCode", "")}
    except Exception:
        return {"country": ""}

@app.get("/win11lpc")
async def win11lpc_page(request: Request):
    return templates.TemplateResponse("win11lpc.html", {"request": request})

@app.get("/static-manager")
async def static_manager_page(request: Request):
    return templates.TemplateResponse("static-manager.html", {"request": request})

class Win11Code(BaseModel):
    code: str

@app.post("/api/win11lpc/compile")
async def win11lpc_compile(body: Win11Code):
    import time
    t0 = time.time()
    try:
        w11_dir = Path("/home/ubuntu/luckycardeng/win11lpc")
        tmp_path = w11_dir / f"tmp_{uuid.uuid4().hex[:8]}.w11"
        tmp_path.write_text(body.code, encoding="utf-8")

        proc = subprocess.run(
            [str(w11_dir / "_Win11LPC"), str(tmp_path)],
            capture_output=True, text=True, timeout=30,
            cwd=str(w11_dir),
        )

        cpp_path = tmp_path.with_suffix(".cpp")
        if cpp_path.exists():
            cpp = cpp_path.read_text(encoding="utf-8")
            cpp_path.unlink(missing_ok=True)
        else:
            cpp = proc.stdout or proc.stderr or "(no output)"

        tmp_path.unlink(missing_ok=True)

        duration_ms = int((time.time() - t0) * 1000)

        if proc.returncode != 0 and not cpp.strip():
            return {"status": "error", "message": cpp.strip() or "Transpile failed"}

        return {"status": "ok", "cpp": cpp, "duration_ms": duration_ms}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Transpile timed out (30s)"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/stylize")
async def stylize_image(request: Request, file: UploadFile = File(...),
    style: str = Form("watercolor"),
    style_prompt: str = Form(""),
):
    from .api.auth import charge_op, refund_op
    charge = charge_op(request, ["stylize"])
    try:
        result = await _stylize_impl(file, style, style_prompt)
    except Exception as e:
        refund_op(request, ["stylize"], charge)
        raise
    if result.get("status") != "ok":
        refund_op(request, ["stylize"], charge)
    return result


async def _stylize_impl(file: UploadFile, style: str, style_prompt: str):
    try:
        # Save uploaded file temporarily
        tmp_dir = Path("/tmp/stylize_uploads")
        tmp_dir.mkdir(exist_ok=True)
        tmp_path = tmp_dir / f"{uuid.uuid4().hex}{Path(file.filename or 'img.jpg').suffix}"
        content = await file.read()
        tmp_path.write_bytes(content)

        # Encode to base64
        img_b64 = base64.b64encode(tmp_path.read_bytes()).decode()

        # Run stylize pipeline
        env = os.environ.copy()
        env["ARK_API_KEY"] = settings.ark_api_key or ""
        proc = subprocess.run(
            ["/home/ubuntu/luckycardeng/.venv/bin/python3", "stylize_pipeline.py"],
            input=f"STYLE:{style}\nSTYLE_PROMPT:{style_prompt}\n{img_b64}\n",
            capture_output=True, text=True, timeout=300,
            cwd="/home/ubuntu/luckycardeng",
            env=env,
        )
        if proc.returncode != 0:
            return {"status": "error", "message": proc.stderr.strip() or "Pipeline failed"}

        result = json.loads(proc.stdout)
        if result.get("status") != "ok":
            return result

        # Copy to static folder for web access
        out_path = Path(result["file"])
        static_dir = Path("app/static/stylized")
        static_dir.mkdir(exist_ok=True)
        static_name = f"{uuid.uuid4().hex[:12]}.jpg"
        static_path = static_dir / static_name
        static_path.write_bytes(out_path.read_bytes())

        return {
            "status": "ok",
            "result_url": f"/static/stylized/{static_name}",
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Pipeline timed out (300s)"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/card-art")
async def card_art(request: Request, text: str = Form(...), style: str = Form("watercolor"), card_id: str = Form("")):
    """Generate AI artwork for a card from poem text."""
    from .api.auth import charge_op, refund_op
    charge = charge_op(request, ["art"])
    try:
        result = await _card_art_impl(text, style, card_id)
    except Exception as e:
        refund_op(request, ["art"], charge)
        raise
    if result.get("status") != "ok":
        refund_op(request, ["art"], charge)
    return result


async def _card_art_impl(text: str, style: str, card_id: str):
    from sqlalchemy import select
    from .models import GreetingCard
    try:
        STYLE_MAP = {
            "watercolor": "watercolor painting, soft, artistic",
            "oil": "oil painting, rich textures, classic",
            "sketch": "pencil sketch, monochrome, artistic",
            "anime": "anime style, vibrant colors, Japanese illustration",
            "cyberpunk": "cyberpunk, neon, futuristic, dark",
        }
        style_desc = STYLE_MAP.get(style, style)

        seed_data = {
            "model": "ep-20260525152143-fzpqw",
            "prompt": f"{style_desc}. Scene inspired by: {text}. High quality, detailed, greeting card artwork.",
            "size": "1920x1920",
            "n": 1,
        }
        import urllib.request

        api_key = settings.ark_api_key
        if not api_key:
            return {"status": "error", "message": "API key not configured"}

        req = urllib.request.Request(
            "https://ark.cn-beijing.volces.com/api/v3/images/generations",
            json.dumps(seed_data).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        )
        seed_resp = json.loads(urllib.request.urlopen(req, timeout=180).read())
        img_url = seed_resp["data"][0]["url"]

        # Download to static
        static_dir = Path("app/static/stylized")
        static_dir.mkdir(exist_ok=True)
        static_name = f"art_{uuid.uuid4().hex[:12]}.jpg"
        static_path = static_dir / static_name
        urllib.request.urlretrieve(img_url, str(static_path))

        # Save art_url to card record if card_id provided
        if card_id:
            try:
                from .database import AsyncSessionLocal
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(GreetingCard).where(GreetingCard.id == card_id)
                    )
                    card = result.scalar_one_or_none()
                    if card:
                        card.art_url = f"/static/stylized/{static_name}"
                        await db.commit()
            except Exception:
                pass  # Non-fatal if DB save fails

        return {
            "status": "ok",
            "result_url": f"/static/stylized/{static_name}",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Simple file upload endpoint."""
    import aiofiles
    save_dir = Path("/home/ubuntu/uploads")
    save_dir.mkdir(exist_ok=True)
    save_path = save_dir / (file.filename or "upload.zip")
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)
    return {"status": "ok", "path": str(save_path), "size": len(content)}

@app.get("/about.txt")
async def about_txt():
    """Plain-text site description — for crawlers / AI agents."""
    return FileResponse("app/static/about.txt", media_type="text/plain; charset=utf-8")

@app.get("/robots.txt")
async def robots_txt():
    return FileResponse("app/static/robots.txt", media_type="text/plain; charset=utf-8")

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})
