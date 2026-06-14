"""
RecoverAI — Security Utilities (Hardened)

Provides:
  - Password hashing (bcrypt)
  - Password strength validation
  - JWT access + refresh token creation (with jti claim for revocation)
  - Token revocation blacklist:
      * Redis-backed when REDIS_URL is configured (multi-worker safe)
      * In-memory fallback when Redis is unavailable (single-worker only)
  - Redis-backed rate limiter with in-memory fallback
"""
import uuid
import re
import time
import logging
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from threading import Lock

import jwt
from passlib.context import CryptContext

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── JWT issuer / audience ─────────────────────────────────────────────────────
# These MUST match the values validated in every jwt.decode() call (deps.py,
# auth.py). They are emitted as the `iss` / `aud` claims at token creation; if a
# decode site omits them, PyJWT raises InvalidAudienceError and rejects the token.
JWT_ISSUER = "recoverai"
JWT_AUDIENCE = "recoverai-api"

# ── Password Hashing ──────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plaintext password against a bcrypt hash (timing-safe)."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Return the bcrypt hash of a plaintext password."""
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Enforce a strong password policy.

    Requirements:
    - At least 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - At least 1 special character (@$!%*?&_#^-+=)

    Returns:
        (True, "") if valid
        (False, reason) if invalid
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit (0-9)."
    if not re.search(r"[@$!%*?&_#^+=\-]", password):
        return False, "Password must contain at least one special character (@$!%*?&_#^-+=)."
    return True, ""


# ── Redis Connection (optional, lazy) ────────────────────────────────────────
# If REDIS_URL is set in .env, all rate limiting and token blacklist operations
# use Redis (multi-worker safe). Otherwise falls back to in-memory (single-worker).

_redis_client = None
_redis_checked = False


def _get_redis():
    """Return a Redis client or None if not configured."""
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True

    if not settings.redis_url:
        logger.info(
            "REDIS_URL not set — using in-memory token blacklist and rate limiter "
            "(safe for single-worker deployments only)."
        )
        return None

    try:
        import redis.asyncio as aioredis  # type: ignore
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
        )
        logger.info("Redis connected — using Redis-backed security store.")
    except Exception as exc:
        logger.warning("Redis connection failed (%s) — falling back to in-memory store.", exc)
        _redis_client = None

    return _redis_client


# ── Token Revocation Blacklist ────────────────────────────────────────────────

_REVOKED_TOKENS: dict[str, float] = {}  # jti -> unix expiry timestamp (memory fallback)
_REVOKED_LOCK = Lock()


def _prune_revoked_tokens() -> None:
    """Remove expired entries from the in-memory blacklist."""
    now = time.time()
    with _REVOKED_LOCK:
        expired = [jti for jti, exp in _REVOKED_TOKENS.items() if exp < now]
        for jti in expired:
            del _REVOKED_TOKENS[jti]


def revoke_token(jti: str, expires_at: float | None = None) -> None:
    """Add a JWT ID to the revocation blacklist.

    Uses Redis SETEX if available, otherwise in-memory dict.

    Args:
        jti: The JWT ID to revoke.
        expires_at: Unix timestamp when this token naturally expires.
                    If None, defaults to 30 days from now (safe upper bound).
    """
    if expires_at is None:
        expires_at = time.time() + 30 * 24 * 3600

    redis = _get_redis()
    if redis is not None:
        import asyncio
        ttl = max(1, int(expires_at - time.time()))

        async def _do_revoke():
            try:
                await redis.setex(f"blacklist:{jti}", ttl, "1")
            except Exception as exc:
                logger.warning("Redis revoke_token failed (%s) — memory fallback.", exc)
                with _REVOKED_LOCK:
                    _REVOKED_TOKENS[jti] = expires_at

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(_do_revoke())
            else:
                loop.run_until_complete(_do_revoke())
        except RuntimeError:
            with _REVOKED_LOCK:
                _REVOKED_TOKENS[jti] = expires_at
    else:
        with _REVOKED_LOCK:
            _REVOKED_TOKENS[jti] = expires_at


def is_token_revoked(jti: str) -> bool:
    """Sync check — falls back to memory if Redis unavailable."""
    _prune_revoked_tokens()
    return jti in _REVOKED_TOKENS


async def is_token_revoked_async(jti: str) -> bool:
    """Async check — uses Redis if available, otherwise memory."""
    redis = _get_redis()
    if redis is not None:
        try:
            result = await redis.get(f"blacklist:{jti}")
            return result is not None
        except Exception as exc:
            logger.warning("Redis is_token_revoked_async failed (%s) — memory fallback.", exc)
    _prune_revoked_tokens()
    return jti in _REVOKED_TOKENS


# ── Redis Rate Limiter ────────────────────────────────────────────────────────

_RATE_LIMIT_WINDOW_SECONDS = 900  # 15 minutes
_MAX_ATTEMPTS = 5
_rate_limit_store: dict[str, dict] = defaultdict(lambda: {"count": 0, "window_start": 0.0})
_rate_limit_lock = Lock()


async def rate_limit_check(ip: str) -> tuple[bool, int]:
    """Check if IP exceeded failed-login limit. Returns (exceeded, retry_after_seconds)."""
    redis = _get_redis()
    now = time.time()

    if redis is not None:
        try:
            key = f"ratelimit:{ip}"
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, _RATE_LIMIT_WINDOW_SECONDS)
            if count > _MAX_ATTEMPTS:
                ttl = await redis.ttl(key)
                return True, max(0, ttl)
            return False, 0
        except Exception as exc:
            logger.warning("Redis rate_limit_check failed (%s) — memory fallback.", exc)

    with _rate_limit_lock:
        record = _rate_limit_store[ip]
        if now - record["window_start"] > _RATE_LIMIT_WINDOW_SECONDS:
            record["count"] = 0
            record["window_start"] = now
        record["count"] += 1
        if record["count"] > _MAX_ATTEMPTS:
            retry_after = int(_RATE_LIMIT_WINDOW_SECONDS - (now - record["window_start"]))
            return True, max(0, retry_after)
        return False, 0


async def rate_limit_clear(ip: str) -> None:
    """Reset rate limit counter for IP after successful login."""
    redis = _get_redis()
    if redis is not None:
        try:
            await redis.delete(f"ratelimit:{ip}")
            return
        except Exception as exc:
            logger.warning("Redis rate_limit_clear failed (%s) — memory fallback.", exc)
    with _rate_limit_lock:
        _rate_limit_store.pop(ip, None)


# ── JWT Token Creation ────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Create a signed short-lived access JWT.

    Includes a unique `jti` claim to support per-token revocation.
    Default expiry: settings.access_token_expire_minutes (15 min)
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),          # Unique token ID for revocation
        "type": "access",
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    })
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(data: dict) -> str:
    """
    Create a signed long-lived refresh JWT.

    Used to obtain new access tokens without re-authenticating.
    Default expiry: settings.refresh_token_expire_days (7 days)
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
        "type": "refresh",
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    })
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
