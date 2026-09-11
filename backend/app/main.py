from pathlib import Path
import logging

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes.documents import router as documents_router
from app.core.logging import setup_logging


# --------------------------------------------------
# Logging
# --------------------------------------------------

setup_logging()

logger = logging.getLogger(__name__)


# --------------------------------------------------
# FastAPI Application
# --------------------------------------------------

app = FastAPI(
    title="AI Document Intelligence API",
    version="1.0.0",
    description="AI-powered document extraction, validation and API platform",
)


# --------------------------------------------------
# API Routes
# --------------------------------------------------

app.include_router(documents_router)


# --------------------------------------------------
# Health Check
# --------------------------------------------------

@app.get("/api/v1/health")
def health_check():
    return {
        "status": "healthy",
        "service": "AI Document Intelligence API",
    }


# --------------------------------------------------
# Frontend Paths
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]

FRONTEND_DIR = BASE_DIR / "frontend"

TEMPLATES_DIR = FRONTEND_DIR / "templates"

STATIC_DIR = FRONTEND_DIR / "static"


# --------------------------------------------------
# Static Files
# --------------------------------------------------

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


# --------------------------------------------------
# Templates
# --------------------------------------------------

templates = Jinja2Templates(
    directory=TEMPLATES_DIR
)


# --------------------------------------------------
# Dashboard
# --------------------------------------------------

@app.get("/")
def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={},
    )


# --------------------------------------------------
# Document Result Page
# --------------------------------------------------

@app.get("/document_result.html")
def document_result(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="document_result.html",
        context={},
    )