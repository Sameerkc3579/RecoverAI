"""
RecoverAI — 3-Layer Firewall Middleware

Layer 1: Global IP Rate Limiter
    Tracks requests per IP with separate limits for auth, webhook, and general endpoints.
    Auto-bans IPs after sustained abuse.

Layer 2: Suspicious Request Blocker
    Detects SQL injection, path traversal, XSS probing, and scanner User-Agents.
    Returns 403 Forbidden for all blocked requests.

Layer 3: Honeypot Trap Endpoints
    Fake paths that real users never access but automated scanners always try.
    Any IP hitting a trap gets banned for 1 hour.
"""

import logging
import re
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# ── Layer 1: Rate Limit Configuration ─────────────────────────────────────────
GENERAL_RATE_LIMIT = 100       # requests per window
AUTH_RATE_LIMIT = 15           # auth endpoint requests per window
WEBHOOK_RATE_LIMIT = 30        # webhook endpoint requests per window
RATE_WINDOW_SECONDS = 60       # sliding window size
BAN_DURATION_SECONDS = 900     # 15 minutes
BAN_THRESHOLD = 3              # consecutive violations before ban
CLEANUP_INTERVAL = 300         # clean expired entries every 5 min

# ── Layer 2: Attack Signatures ────────────────────────────────────────────────
SQL_INJECTION_PATTERNS = [
    r"('\s*(OR|AND)\s+['\d])", r"UNION\s+SELECT", r";\s*DROP\s+",
    r"1\s*=\s*1", r"'\s*--", r"/\*\*/", r"EXEC\s*\(", r"xp_cmdshell",
    r"INFORMATION_SCHEMA", r"LOAD_FILE\s*\(", r"INTO\s+OUTFILE",
]
PATH_TRAVERSAL_PATTERNS = [
    r"\.\./", r"\.\.\\", r"%2e%2e", r"%252e", r"%c0%ae",
]
XSS_PATTERNS = [
    r"<script", r"javascript:", r"onerror\s*=", r"onload\s*=",
    r"eval\s*\(", r"document\.cookie", r"alert\s*\(",
]
SCANNER_PATHS = [
    ".git/", ".svn/", "wp-content/", "cgi-bin/", ".aws/", ".docker/",
]
SCANNER_USER_AGENTS = [
    "sqlmap", "nikto", "dirbuster", "gobuster", "nmap", "masscan",
    "acunetix", "nessus", "burpsuite", "hydra", "wfuzz", "ffuf",
    "nuclei", "zgrab", "whatweb",
]

_COMPILED_SQL = [re.compile(p, re.IGNORECASE) for p in SQL_INJECTION_PATTERNS]
_COMPILED_PATH = [re.compile(p, re.IGNORECASE) for p in PATH_TRAVERSAL_PATTERNS]
_COMPILED_XSS = [re.compile(p, re.IGNORECASE) for p in XSS_PATTERNS]

# ── Layer 3: Honeypot Paths ───────────────────────────────────────────────────
HONEYPOT_PATHS = {
    "/admin.php", "/wp-admin", "/wp-login.php", "/.env", "/phpmyadmin",
    "/config.json", "/.git/config", "/xmlrpc.php", "/wp-config.php",
    "/administrator", "/actuator", "/.git/HEAD", "/server-status",
    "/phpinfo.php", "/wp-includes", "/solr/", "/manager/html",
    "/.DS_Store", "/backup.sql", "/dump.sql", "/db.sql",
}
HONEYPOT_BAN_SECONDS = 3600  # 1 hour


class FirewallMiddleware(BaseHTTPMiddleware):
    """Three-layer firewall: rate limiter -> attack blocker -> honeypot traps."""

    def __init__(self, app):
        super().__init__(app)
        # {ip: {"count": int, "window_start": float, "violations": int, "banned_until": float}}
        self._rate_store: dict[str, dict] = {}
        self._last_cleanup = time.time()

    # ── IP Extraction ─────────────────────────────────────────────────────────

    @staticmethod
    def _get_client_ip(request) -> str:
        """Extract real client IP — rightmost non-private entry in X-Forwarded-For."""
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            ips = [ip.strip() for ip in forwarded.split(",")]
            for ip in reversed(ips):
                if ip and not ip.startswith(("10.", "172.", "192.168.", "127.")):
                    return ip
            return ips[-1]
        return request.client.host if request.client else "127.0.0.1"

    # ── Layer 1: Rate Limiter ─────────────────────────────────────────────────

    def _cleanup_expired(self):
        """Remove expired rate limit entries to prevent memory leaks."""
        now = time.time()
        if now - self._last_cleanup < CLEANUP_INTERVAL:
            return
        self._last_cleanup = now
        expired = [
            ip for ip, data in self._rate_store.items()
            if now - data.get("window_start", 0) > RATE_WINDOW_SECONDS * 2
            and now > data.get("banned_until", 0)
        ]
        for ip in expired:
            del self._rate_store[ip]

    def _check_rate_limit(self, ip: str, path: str) -> bool:
        """Returns True if request should be BLOCKED due to rate limiting."""
        self._cleanup_expired()
        now = time.time()

        if ip not in self._rate_store:
            self._rate_store[ip] = {
                "count": 0, "window_start": now,
                "violations": 0, "banned_until": 0,
            }

        entry = self._rate_store[ip]

        # Check if IP is currently banned
        if now < entry.get("banned_until", 0):
            return True

        # Reset window if expired
        if now - entry["window_start"] > RATE_WINDOW_SECONDS:
            entry["count"] = 0
            entry["window_start"] = now

        entry["count"] += 1

        # Determine limit based on path
        if path.startswith("/api/auth/"):
            limit = AUTH_RATE_LIMIT
        elif path.startswith("/api/webhooks/"):
            limit = WEBHOOK_RATE_LIMIT
        else:
            limit = GENERAL_RATE_LIMIT

        if entry["count"] > limit:
            entry["violations"] = entry.get("violations", 0) + 1
            if entry["violations"] >= BAN_THRESHOLD:
                entry["banned_until"] = now + BAN_DURATION_SECONDS
                logger.warning(
                    "FIREWALL_BAN | ip=%s | reason=rate_limit | violations=%d | banned_for=%ds",
                    ip, entry["violations"], BAN_DURATION_SECONDS,
                )
            return True

        return False

    # ── Layer 2: Attack Pattern Detection ─────────────────────────────────────

    @staticmethod
    def _is_suspicious_request(path: str, query: str, user_agent: str) -> str | None:
        """Returns the attack type if suspicious, None otherwise."""
        check_str = f"{path}?{query}".lower()

        # SQL Injection
        for pattern in _COMPILED_SQL:
            if pattern.search(check_str):
                return "sql_injection"

        # Path Traversal
        for pattern in _COMPILED_PATH:
            if pattern.search(check_str):
                return "path_traversal"

        # XSS Probing
        for pattern in _COMPILED_XSS:
            if pattern.search(check_str):
                return "xss_probe"

        # Scanner paths
        path_lower = path.lower()
        for scanner_path in SCANNER_PATHS:
            if scanner_path in path_lower:
                return "scanner_path"

        # Scanner User-Agents
        ua_lower = user_agent.lower()
        for scanner in SCANNER_USER_AGENTS:
            if scanner in ua_lower:
                return "scanner_ua"

        return None

    # ── Layer 3: Honeypot Check ───────────────────────────────────────────────

    def _check_honeypot(self, ip: str, path: str) -> bool:
        """Returns True if path is a honeypot trap. Bans the IP for 1 hour."""
        path_lower = path.lower().rstrip("/")
        for trap in HONEYPOT_PATHS:
            if path_lower == trap.rstrip("/") or path_lower.startswith(trap):
                now = time.time()
                if ip not in self._rate_store:
                    self._rate_store[ip] = {
                        "count": 0, "window_start": now,
                        "violations": 0, "banned_until": 0,
                    }
                self._rate_store[ip]["banned_until"] = now + HONEYPOT_BAN_SECONDS
                self._rate_store[ip]["violations"] = BAN_THRESHOLD + 1
                logger.warning(
                    "HONEYPOT_TRAP | ip=%s | path=%s | banned_for=%ds",
                    ip, path, HONEYPOT_BAN_SECONDS,
                )
                return True
        return False

    # ── Dispatch ──────────────────────────────────────────────────────────────

    async def dispatch(self, request, call_next):
        path = request.url.path
        query = str(request.url.query or "")
        user_agent = request.headers.get("user-agent", "")

        # Skip firewall for static assets
        if path.startswith(("/static/", "/uploads/")):
            return await call_next(request)

        ip = self._get_client_ip(request)

        # ── Layer 3: Honeypot traps (check first — instant ban) ───────────
        if self._check_honeypot(ip, path):
            return JSONResponse(
                status_code=404,
                content={"detail": "Not Found"},
            )

        # ── Layer 2: Attack pattern detection ─────────────────────────────
        attack_type = self._is_suspicious_request(path, query, user_agent)
        if attack_type:
            logger.warning(
                "FIREWALL_BLOCK | ip=%s | type=%s | path=%s | query=%s | ua=%s",
                ip, attack_type, path, query[:100], user_agent[:80],
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Forbidden"},
            )

        # ── Layer 1: Rate limiting ────────────────────────────────────────
        if self._check_rate_limit(ip, path):
            logger.warning("FIREWALL_RATE_LIMIT | ip=%s | path=%s", ip, path)
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(RATE_WINDOW_SECONDS)},
            )

        return await call_next(request)
