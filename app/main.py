"""
RecoverAI — FastAPI Application Entry-Point (Security-Hardened)

Security Changes Applied:
  1. CORS: wildcard `allow_origins=["*"]` replaced with explicit allowlist from settings
  2. API Docs (/docs, /redoc, /openapi.json) disabled in production (debug=False)
  3. Security Headers middleware: HSTS, CSP, X-Frame-Options, etc.
  4. Request size limit middleware: 10MB max (DoS protection)
  5. Audit log middleware: structured access log for security forensics
  6. Global error handler: strips internal details from 500 responses
  7. Server fingerprinting: generic server header

Startup order
─────────────
1. Load settings from .env (crashes if SECRET_KEY not set — fail-secure)
2. Connect to MongoDB
3. Mount security middleware stack
4. Mount API routers
5. Apply CORS middleware (restricted origins only)
"""
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import connect_db, close_db
from app.core.middleware import (
    SecurityHeadersMiddleware,
    RequestSizeLimitMiddleware,
    AuditLogMiddleware,
)
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

# ── Upload Directory ──────────────────────────────────────────────────────────
_IS_VERCEL = bool(os.environ.get("VERCEL"))
_UPLOAD_DIR = "/tmp/uploads" if _IS_VERCEL else "uploads"
os.makedirs(_UPLOAD_DIR, exist_ok=True)


# ── Application ───────────────────────────────────────────────────────────────
# IMPORTANT: app must be created BEFORE @app.on_event decorators reference it.
# API docs are gated behind debug mode:
# - debug=True  → /docs, /redoc, /openapi.json accessible (local dev only)
# - debug=False → all docs endpoints return 404 (production)
app = FastAPI(
    title="RecoveryAgent API",
    description=(
        "AI-powered debt-recovery assistant backend. "
        "Integrates Google Gemini, MongoDB, and WhatsApp messaging."
    ),
    version="0.1.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)


# ── Startup / Shutdown ────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """Application startup hooks."""
    logger.info("🚀  RecoveryAgent starting up…")
    logger.info("🔒  Security mode: %s", "PRODUCTION" if settings.is_production else "DEBUG")
    logger.info("🔒  CORS origins: %s", settings.origins_list)
    logger.info("🔒  Admin accounts configured: %d", len(settings.admin_emails_list))
    try:
        await connect_db()
        logger.info("✅  MongoDB connected  →  db: %s", settings.db_name)
    except Exception as exc:
        logger.warning("⚠️   MongoDB unavailable (%s) — continuing without DB", exc)


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown hooks."""
    logger.info("🛑  RecoveryAgent shutting down…")
    try:
        await close_db()
        logger.info("✅  MongoDB connection closed")
    except Exception as exc:
        logger.warning("⚠️   Error closing MongoDB: %s", exc)


# ── Global Error Handler ──────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all exception handler that prevents internal stack traces
    from leaking to API consumers in production.
    """
    logger.error(
        "UNHANDLED_EXCEPTION | path=%s | method=%s | error=%s: %s",
        request.url.path, request.method, type(exc).__name__, str(exc),
        exc_info=True,
    )
    if settings.debug:
        # In debug mode, surface the real error for development
        return JSONResponse(
            status_code=500,
            content={"detail": f"{type(exc).__name__}: {str(exc)}"},
        )
    # In production, generic error (no internal info leakage)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


# ── Security Middleware Stack ─────────────────────────────────────────────────
# Order matters — outermost middleware runs first on request, last on response.

# 1. Audit logging (outermost — logs every request including blocked ones)
app.add_middleware(AuditLogMiddleware)

# 2. Request size limit (blocks oversized payloads early)
app.add_middleware(RequestSizeLimitMiddleware, max_size_mb=settings.max_upload_size_mb)

# 3. Security response headers (innermost — applied to all responses)
app.add_middleware(SecurityHeadersMiddleware)


# ── CORS Middleware ───────────────────────────────────────────────────────────
# SECURITY FIX: Changed from allow_origins=["*"] to explicit allowlist.
# Only origins listed in ALLOWED_ORIGINS environment variable are permitted.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,        # ← NO WILDCARD
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(invoices_router)
app.include_router(chat_router)
app.include_router(webhook_router)
app.include_router(enrich_router)
app.include_router(admin_router)


# ── Static Files ──────────────────────────────────────────────────────────────
if not _IS_VERCEL:
    app.mount("/uploads", StaticFiles(directory=_UPLOAD_DIR), name="uploads")


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get(
    "/health",
    tags=["System"],
    summary="Health check",
    response_description="Service liveness confirmation",
)
async def health_check() -> dict[str, str]:
    """Returns ok when the server is reachable."""
    return {"status": "ok", "service": "RecoveryAgent API"}


# ── Root — Serve the React Frontend ──────────────────────────────────────────
FRONTEND_HTML = Path(__file__).resolve().parent.parent / "RecoverAI_MVP.html"


@app.get("/", tags=["System"], summary="Frontend", include_in_schema=False)
async def root():
    """Serve the RecoverAI single-page frontend."""
    if FRONTEND_HTML.exists():
        return FileResponse(FRONTEND_HTML, media_type="text/html")
    return {"status": "ok", "message": "RecoveryAgent API is running. Frontend UI deployed separately."}
