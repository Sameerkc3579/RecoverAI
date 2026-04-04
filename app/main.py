"""
RecoveryAgent — FastAPI application entry-point.

Startup order
─────────────
1. Load settings from .env
2. Connect to MongoDB
3. Mount API routers
4. Apply CORS middleware

Run with:
    uvicorn app.main:app --reload --port 8000
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import connect_db, close_db
from app.api.invoices import router as invoices_router
from app.api.chat import router as chat_router
from app.api.webhook import router as webhook_router
from app.api.auth import router as auth_router
from app.api.enrich import router as enrich_router
from app.api.admin import router as admin_router

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup / shutdown hooks."""
    logger.info("🚀  RecoveryAgent starting up…")
    try:
        os.makedirs("uploads", exist_ok=True)
        await connect_db()
        logger.info("✅  MongoDB connected  →  db: %s", settings.db_name)
    except Exception as exc:
        logger.warning("⚠️   MongoDB unavailable (%s) — continuing without DB", exc)

    yield  # ← server is live

    logger.info("🛑  RecoveryAgent shutting down…")
    await close_db()
    logger.info("✅  MongoDB connection closed")


# ── Application ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="RecoveryAgent API",
    description=(
        "AI-powered debt-recovery assistant backend. "
        "Integrates Google Gemini, MongoDB, and WhatsApp messaging."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ── CORS Middleware ───────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(invoices_router)
app.include_router(chat_router)
app.include_router(webhook_router)
app.include_router(enrich_router)
app.include_router(admin_router)

# ── Static Files ──────────────────────────────────────────────────────────────
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get(
    "/health",
    tags=["System"],
    summary="Health check",
    response_description="Service liveness confirmation",
)
async def health_check() -> dict[str, str]:
    """Returns *ok* when the server is reachable."""
    return {"status": "ok", "service": "RecoveryAgent API"}


# ── Root — serve the React frontend ──────────────────────────────────────────────────
FRONTEND_HTML = Path(__file__).resolve().parent.parent / "RecoverAI_MVP.html"


@app.get("/", tags=["System"], summary="Frontend", include_in_schema=False)
async def root():
    """Serve the RecoverAI single-page frontend."""
    return FileResponse(FRONTEND_HTML, media_type="text/html")
