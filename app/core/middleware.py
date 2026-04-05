"""
RecoverAI — Custom Security Middleware Stack

IMPORTANT: Uses raw ASGI middleware (NOT BaseHTTPMiddleware).
BaseHTTPMiddleware wraps exceptions into ExceptionGroup on Python 3.11+,
which causes "Exception in ASGI application" crashes on every request.
Raw ASGI middleware does not have this problem.

Middleware (applied in order):
  1. SecurityHeadersMiddleware  — injects hardened HTTP security headers
  2. RequestSizeLimitMiddleware — rejects payloads > MAX_UPLOAD_SIZE_MB
  3. AuditLogMiddleware         — structured access log for every request
"""
import logging
import time

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger("security.audit")


# ── 1. Security Headers Middleware ────────────────────────────────────────────

class SecurityHeadersMiddleware:
    """Raw ASGI middleware — injects hardened security headers on every response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Permissions-Policy"] = (
                    "geolocation=(), microphone=(), camera=(), "
                    "payment=(), usb=(), magnetometer=(), gyroscope=()"
                )
                headers["Content-Security-Policy"] = (
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
                headers["X-XSS-Protection"] = "1; mode=block"
                # Remove server fingerprinting (MutableHeaders uses del, not pop)
                try:
                    del headers["server"]
                except KeyError:
                    pass
                try:
                    del headers["x-powered-by"]
                except KeyError:
                    pass
            await send(message)

        await self.app(scope, receive, send_with_security_headers)


# ── 2. Request Size Limit Middleware ──────────────────────────────────────────

class RequestSizeLimitMiddleware:
    """Raw ASGI middleware — rejects requests whose Content-Length exceeds the limit."""

    def __init__(self, app: ASGIApp, max_size_mb: int = 10) -> None:
        self.app = app
        self.max_size_bytes = max_size_mb * 1024 * 1024

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_size_bytes:
                    client = scope.get("client")
                    ip = client[0] if client else "unknown"
                    logger.warning(
                        "BLOCKED_OVERSIZED_REQUEST | ip=%s | path=%s | size=%d bytes",
                        ip, scope.get("path", ""), size,
                    )
                    response = JSONResponse(
                        status_code=413,
                        content={"detail": f"Payload too large. Max {self.max_size_bytes // (1024*1024)} MB."},
                    )
                    await response(scope, receive, send)
                    return
            except (ValueError, TypeError):
                pass

        await self.app(scope, receive, send)


# ── 3. Audit Log Middleware ───────────────────────────────────────────────────

class AuditLogMiddleware:
    """Raw ASGI middleware — structured audit log for every HTTP request."""

    _SUPPRESS = {"/health", "/favicon.ico"}

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in self._SUPPRESS:
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 0

        async def send_and_capture(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
            await send(message)

        await self.app(scope, receive, send_and_capture)

        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        headers = dict(scope.get("headers", []))
        client = scope.get("client")
        forwarded = headers.get(b"x-forwarded-for", b"").decode()
        ip = forwarded.split(",")[0].strip() if forwarded else (client[0] if client else "unknown")
        ua = headers.get(b"user-agent", b"").decode()[:120]
        method = scope.get("method", "")

        logger.info(
            "AUDIT | method=%s | path=%s | status=%d | ip=%s | duration=%sms | ua=%s",
            method, path, status_code, ip, duration_ms, ua,
        )
