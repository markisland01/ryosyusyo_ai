from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import app.models  # noqa: F401
from app.api import export, history, receipts, rules, videos
from app.config import OUTPUT_DIR
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="経理書類スキャンAI",
    description="領収書、クレジットカード明細、銀行通帳を動画から抽出し、OCR と AI で整理するシステム",
    version="0.1.0",
    lifespan=lifespan,
)

static_dir = Path(__file__).parent / "static"
templates_dir = Path(__file__).parent / "templates"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
templates = Jinja2Templates(directory=str(templates_dir))

app.include_router(videos.router)
app.include_router(receipts.router)
app.include_router(export.router)
app.include_router(history.router)
app.include_router(rules.router)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/upload")
async def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@app.get("/upload/long-receipt")
async def long_receipt_upload_page(request: Request):
    return templates.TemplateResponse("long_receipt_upload.html", {"request": request})


@app.get("/rules")
async def rules_page(request: Request):
    return templates.TemplateResponse("rules.html", {"request": request})


@app.get("/mock-suite")
async def mock_suite_page(request: Request):
    return templates.TemplateResponse("mock_suite.html", {"request": request})


@app.get("/ops-mock")
async def ops_mock_page(request: Request):
    return templates.TemplateResponse("ops_mock.html", {"request": request})


@app.get("/client-review-mock")
async def client_review_mock_page(request: Request):
    return templates.TemplateResponse("client_review_mock.html", {"request": request})


@app.get("/results/{video_id}")
async def results_page(request: Request, video_id: int):
    return templates.TemplateResponse("results.html", {"request": request, "video_id": video_id})
