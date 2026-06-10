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
import tempfile
from pathlib import Path

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.database import connect_db, close_db
from app.core.middleware import (
    SecurityHeadersMiddleware,
    RequestSizeLimitMiddleware,
    AuditLogMiddleware,
)
from app.core.firewall import FirewallMiddleware
from app.api.invoices import router as invoices_router
from app.api.chat import router as chat_router
from app.api.webhook import router as webhook_router
from app.api.auth import router as auth_router
from app.api.enrich import router as enrich_router
from app.api.admin import router as admin_router
from app.api.users import router as users_router
from app.api.customers import router as customers_router
from app.api.whatsapp_webhook import router as whatsapp_router
from app.api.deps import get_admin_user

# ── Logger ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
_IS_VERCEL = bool(os.environ.get("VERCEL"))
BASE_DIR = Path(__file__).resolve().parent.parent
_UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "uploads") if _IS_VERCEL else "uploads"
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

# 4. Firewall (outermost after CORS — runs first on every request)
#    Layer 1: IP rate limiter  |  Layer 2: Attack pattern blocker  |  Layer 3: Honeypot traps
app.add_middleware(FirewallMiddleware)


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
app.include_router(users_router)
app.include_router(customers_router)
app.include_router(whatsapp_router)


# ── Static Files ──────────────────────────────────────────────────────────────
# Serve the new modular frontend static directory (/static/css, /static/js)
_static_dir_candidates = [
    BASE_DIR / "static",
    Path("static"),
    Path("/var/task/static"),
]
for _static_cand in _static_dir_candidates:
    if _static_cand.exists():
        app.mount("/static", StaticFiles(directory=str(_static_cand)), name="static")
        logger.info("📦  Static dir mounted from: %s", _static_cand)
        break
else:
    logger.warning("⚠️  No static/ directory found — JS/CSS will not be served")

# Legacy dist/assets (Vite build artefacts)
_dist_asset_candidates = [
    BASE_DIR / "dist" / "assets",
    Path("/var/task/dist/assets"),
    Path("dist/assets"),
]
for _candidate in _dist_asset_candidates:
    if _candidate.exists():
        app.mount("/assets", StaticFiles(directory=str(_candidate)), name="assets")
        logger.info("📦  Static assets mounted from: %s", _candidate)
        break

if not _IS_VERCEL:
    _uploads_dir = BASE_DIR / "uploads"
    if _uploads_dir.exists():
        app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")
else:
    os.makedirs(os.path.join(tempfile.gettempdir(), "uploads"), exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=os.path.join(tempfile.gettempdir(), "uploads")), name="uploads")


# ── Landing page path candidates ─────────────────────────────────────────────
_LANDING_PATHS = [
    BASE_DIR / "landing-preview.html",
    Path("landing-preview.html"),
    Path("/var/task/landing-preview.html"),
]
LANDING_HTML: Path | None = next((p for p in _LANDING_PATHS if p.exists()), None)
logger.info("🌐  Landing HTML resolved to: %s", LANDING_HTML)

# ── App shell (SPA) HTML path candidates ──────────────────────────────────────
# Prefer new modular dashboard.html, fallback to legacy RecoverAI_MVP.html
_CANDIDATE_PATHS = [
    BASE_DIR / "dashboard.html",
    Path("dashboard.html"),
    Path("/var/task/dashboard.html"),
    BASE_DIR / "RecoverAI_MVP.html",
    Path("RecoverAI_MVP.html"),
    Path("/var/task/RecoverAI_MVP.html"),
]
FRONTEND_HTML: Path | None = next((p for p in _CANDIDATE_PATHS if p.exists()), None)
logger.info("📄  Frontend HTML resolved to: %s", FRONTEND_HTML)


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


@app.get("/api/startup-check", tags=["System"], include_in_schema=False)
async def startup_check(_admin=Depends(get_admin_user)):
    """
    Diagnostic endpoint — reports env var presence and import health.
    SECURITY: Requires admin JWT. Returns 404 in production mode.
    """
    if not settings.debug:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    import os
    checks = {
        "python_version": __import__("sys").version,
        "vercel": bool(os.environ.get("VERCEL")),
        "env_vars": {
            "GEMINI_API_KEY": "set" if os.environ.get("GEMINI_API_KEY") else "MISSING",
            "MONGO_URI": "set" if os.environ.get("MONGO_URI") else "MISSING",
            "SECRET_KEY": "set" if os.environ.get("SECRET_KEY") else "MISSING",
            "DEBUG": os.environ.get("DEBUG", "not set"),
        },
        "imports": {},
        "html_file": {},
    }
    for mod in ["fastapi", "motor", "jose", "passlib", "google.genai", "pymongo"]:
        try:
            __import__(mod)
            checks["imports"][mod] = "ok"
        except Exception as e:
            checks["imports"][mod] = f"FAILED: {e}"
    for p in _CANDIDATE_PATHS:
        checks["html_file"][str(p)] = "exists" if p.exists() else "missing"
    return checks


@app.get("/api/fs-debug", tags=["System"], include_in_schema=False)
async def fs_debug(_admin=Depends(get_admin_user)):
    """
    Filesystem diagnostic — lists files in key directories.
    SECURITY: Requires admin JWT. Returns 404 in production mode to prevent
    server directory structure from leaking to unauthenticated users.
    """
    if not settings.debug:
        return JSONResponse(status_code=404, content={"detail": "Not found"})
    import os
    data = {"cwd": os.getcwd(), "files_in_cwd": [], "files_in_var_task": [], "files_in_app": []}
    try:
        data["files_in_cwd"] = os.listdir(os.getcwd())
    except Exception as e:
        data["files_in_cwd"] = str(e)
    try:
        data["files_in_var_task"] = os.listdir("/var/task")
    except Exception as e:
        data["files_in_var_task"] = str(e)
    try:
        data["files_in_app"] = os.listdir(os.path.join(os.getcwd(), "app"))
    except Exception as e:
        data["files_in_app"] = str(e)
    return data



# ── Root — Serve the React Frontend ───────────────────────────────────────────────


@app.get("/dashboard", tags=["System"], summary="Frontend App", include_in_schema=False)
@app.get("/dashboard.html", tags=["System"], include_in_schema=False)
@app.get("/RecoverAI_MVP.html", tags=["System"], include_in_schema=False)
@app.get("/index.html", tags=["System"], include_in_schema=False)
@app.get("/inbox", tags=["Frontend"], include_in_schema=False)
@app.get("/invoices", tags=["Frontend"], include_in_schema=False)
@app.get("/recovery", tags=["Frontend"], include_in_schema=False)
@app.get("/legal", tags=["Frontend"], include_in_schema=False)
@app.get("/campaigns", tags=["Frontend"], include_in_schema=False)
@app.get("/customers", tags=["Frontend"], include_in_schema=False)
@app.get("/reports", tags=["Frontend"], include_in_schema=False)
@app.get("/reminders", tags=["Frontend"], include_in_schema=False)
@app.get("/admin", tags=["Frontend"], include_in_schema=False)
@app.get("/settings", tags=["Frontend"], include_in_schema=False)
@app.get("/accounting", tags=["Frontend"], include_in_schema=False)
@app.get("/whatsapp", tags=["Frontend"], include_in_schema=False)
@app.get("/whitelabel", tags=["Frontend"], include_in_schema=False)
async def dashboard():
    """Serve the RecoverAI single-page frontend (dashboard)."""
    try:
        # Try each path at request time (Vercel may differ from import time)
        for path in _CANDIDATE_PATHS:
            if path.exists():
                html_content = path.read_bytes()
                return HTMLResponse(
                    content=html_content, 
                    status_code=200,
                    headers={
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache",
                        "Expires": "0"
                    }
                )
    except Exception as exc:
        logger.error("❌  Failed to serve frontend: %s", exc)
    # Fallback: API is running but frontend file not found
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "message": "RecoveryAgent API is running."},
    )


@app.get("/", tags=["Frontend"], summary="Landing Page", include_in_schema=False)
async def serve_landing():
    """Serve the RecoverAI marketing landing page."""
    no_cache_headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    # Serve landing page if it exists
    for path in _LANDING_PATHS:
        if path.exists():
            return HTMLResponse(
                content=path.read_bytes(),
                status_code=200,
                headers=no_cache_headers,
            )
    # Fallback: serve the app shell if no landing page found
    for path in _CANDIDATE_PATHS:
        if path.exists():
            return HTMLResponse(
                content=path.read_bytes(),
                status_code=200,
                headers=no_cache_headers,
            )
    return JSONResponse(
        status_code=503,
        content={"error": "Frontend not found. Run the backend from the project root directory."}
    )


@app.get("/login", tags=["Frontend"], include_in_schema=False)
@app.get("/register", tags=["Frontend"], include_in_schema=False)
@app.get("/index.html", tags=["Frontend"], include_in_schema=False)
async def serve_app_shell():
    """Serve the RecoverAI SPA shell (login handled client-side)."""
    no_cache_headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    # Serve landing page for auth routes (Vite app)
    for path in _LANDING_PATHS:
        if path.exists():
            return HTMLResponse(
                content=path.read_bytes(),
                status_code=200,
                headers=no_cache_headers,
            )
    # Fallback to candidate paths
    for path in _CANDIDATE_PATHS:
        if path.exists():
            return HTMLResponse(
                content=path.read_bytes(),
                status_code=200,
                headers=no_cache_headers,
            )
    return JSONResponse(
        status_code=503,
        content={"error": "Frontend not found. Run the backend from the project root directory."}
    )

