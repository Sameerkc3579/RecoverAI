"""
RecoverAI — Custom Security Middleware Stack

Middleware (applied in order):
  1. SecurityHeadersMiddleware  — injects hardened HTTP security headers on every response
  2. RequestSizeLimitMiddleware — rejects payloads > MAX_UPLOAD_SIZE_MB (DoS protection)
  3. AuditLogMiddleware         — structured security audit log for every request
"""
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp

logger = logging.getLogger("security.audit")

# ── 1. Security Headers Middleware ────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects hardened security headers on every HTTP response.

    Headers applied:
    - Strict-Transport-Security : Force HTTPS for 1 year, include subdomains
    - X-Content-Type-Options    : Prevent MIME-type sniffing
    - X-Frame-Options           : Prevent clickjacking (deny all iframes)
    - Referrer-Policy           : Limit referrer header leakage
    - Permissions-Policy        : Disable dangerous browser features
    - Content-Security-Policy   : Restrict resource loading origins
    - Cache-Control             : Prevent caching of API responses
    - X-XSS-Protection          : Legacy XSS filter for older browsers
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # HTTPS enforcement (Vercel / production)
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        # Prevent MIME sniffing attacks
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Limit referrer info leakage
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Disable risky browser APIs
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), "
            "payment=(), usb=(), magnetometer=(), gyroscope=()"
        )

        # Content Security Policy — tight allowlist
        # Allows same-origin resources + Google accounts for OAuth
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://accounts.google.com https://apis.google.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self' https://accounts.google.com; "
            "frame-src https://accounts.google.com; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self';"
        )

        # Prevent API responses from being cached
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"

        # Legacy XSS filter
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Remove server fingerprinting headers
        response.headers.pop("Server", None)
        response.headers.pop("X-Powered-By", None)

        return response


# ── 2. Request Size Limit Middleware ──────────────────────────────────────────

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Rejects HTTP requests whose Content-Length exceeds the configured limit.
    Prevents Denial-of-Service attacks via oversized payloads.

    Limit: 10 MB (configurable via MAX_UPLOAD_SIZE_MB env var)
    """

    def __init__(self, app: ASGIApp, max_size_mb: int = 10) -> None:
        super().__init__(app)
        self.max_size_bytes = max_size_mb * 1024 * 1024

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_size_bytes:
                    logger.warning(
                        "BLOCKED_OVERSIZED_REQUEST | ip=%s | path=%s | size=%d bytes | limit=%d bytes",
                        request.client.host if request.client else "unknown",
                        request.url.path,
                        size,
                        self.max_size_bytes,
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": (
                                f"Request payload too large. "
                                f"Maximum allowed size is {self.max_size_bytes // (1024*1024)} MB."
                            )
                        },
                    )
            except ValueError:
                pass  # Malformed content-length — let FastAPI handle it

        return await call_next(request)


# ── 3. Audit Log Middleware ───────────────────────────────────────────────────

class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Structured security audit log for every HTTP request.

    Log format:
        AUDIT | method=POST | path=/api/auth/login | status=200 | ip=1.2.3.4 | duration=42ms | ua=...

    This log is the foundation for detecting:
    - Brute-force attacks (many 401s from same IP)
    - Path traversal attempts
    - Abnormal usage patterns
    - Post-breach forensics
    """

    # Paths that should not be logged (health checks create noise)
    _SUPPRESS = {"/health", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self._SUPPRESS:
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        client_ip = (
            request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )
        user_agent = request.headers.get("user-agent", "")[:120]  # truncate

        logger.info(
            "AUDIT | method=%s | path=%s | status=%d | ip=%s | duration=%sms | ua=%s",
            request.method,
            request.url.path,
            response.status_code,
            client_ip,
            duration_ms,
            user_agent,
        )

        return response
