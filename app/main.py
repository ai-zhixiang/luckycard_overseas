from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from .database import engine, Base
from .api import cards, music, auth, payment, paypal

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

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})
