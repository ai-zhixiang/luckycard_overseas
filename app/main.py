import os, uuid, json, base64, subprocess
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from .database import engine, Base
from .api import cards, music, auth, payment, paypal
from .config import settings

app = FastAPI(title="Lucky Card", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

app.include_router(cards.router, prefix="/api", tags=["cards"])
app.include_router(music.router, prefix="/api", tags=["music"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(payment.router, prefix="/api", tags=["payment"])
app.include_router(paypal.router, prefix="/api", tags=["paypal"])

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

@app.post("/api/stylize")
async def stylize_image(
    file: UploadFile = File(...),
    style: str = Form("watercolor"),
    style_prompt: str = Form(""),
):
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
            ["python3", "stylize_pipeline.py"],
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
async def card_art(text: str = Form(...), style: str = Form("watercolor")):
    """Generate AI artwork for a card from poem text."""
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

        return {
            "status": "ok",
            "result_url": f"/static/stylized/{static_name}",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})
