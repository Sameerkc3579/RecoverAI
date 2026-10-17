"""
RecoverAI — Security Utilities (Hardened)

Provides:
  - Password hashing (bcrypt)
  - Password strength validation
  - JWT access + refresh token creation (with jti claim for revocation)
  - Token revocation blacklist and login/register attempt limiter, shared
    across workers/instances (Redis if reachable, else MongoDB, else memory)
"""
import os
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


# ── Shared security store ─────────────────────────────────────────────────────
# Logout revocations and login/register attempt counters must be shared by every
# worker / serverless instance, or they silently stop working (a token revoked on
# one instance stays valid on the others). Backends, in order:
#   1. Redis    — if REDIS_URL is set AND reachable (disabled after first failure)
#   2. MongoDB  — always available in this app; entries auto-expire via TTL indexes
#   3. Memory   — last-resort fallback if the database is unreachable
# The in-memory blacklist is also kept as a fast local cache.

_REVOKED_COLLECTION = "revoked_tokens"
_RATE_LIMIT_COLLECTION = "auth_rate_limits"

_redis_client = None
_redis_checked = False
_mongo_indexes_ready = False


def _get_redis():
    """Return a Redis client, or None if not configured / previously failed."""
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True

    if not settings.redis_url:
        return None

    # A serverless instance never has a local Redis — skip the doomed connect
    # (and its timeout on every cold start) if REDIS_URL points at loopback.
    from urllib.parse import urlparse
    if os.environ.get("VERCEL") and urlparse(settings.redis_url).hostname in ("localhost", "127.0.0.1", "::1"):
        logger.warning("REDIS_URL points to localhost on Vercel — ignoring it; using MongoDB security store.")
        return None

    try:
        import redis.asyncio as aioredis  # type: ignore
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2,
        )
    except Exception as exc:
        logger.warning("Redis unavailable (%s) — using MongoDB security store.", exc)
        _redis_client = None

    return _redis_client


def _disable_redis(exc: Exception) -> None:
    """Stop using an unreachable Redis so requests don't keep paying the timeout."""
    global _redis_client
    if _redis_client is not None:
        logger.warning("Redis error (%s) — switching to MongoDB security store.", exc)
    _redis_client = None


async def _get_mongo_collection(name: str):
    """Return a MongoDB collection for the security store, or None if the DB is down."""
    global _mongo_indexes_ready
    try:
        from app.core.database import get_collection
        col = get_collection(name)
        if not _mongo_indexes_ready:
            # TTL indexes: MongoDB deletes entries once `expires_at` has passed
            await get_collection(_REVOKED_COLLECTION).create_index("expires_at", expireAfterSeconds=0)
            await get_collection(_RATE_LIMIT_COLLECTION).create_index("expires_at", expireAfterSeconds=0)
            _mongo_indexes_ready = True
        return col
    except Exception as exc:
        logger.warning("MongoDB security store unavailable (%s) — memory fallback.", exc)
        return None


def _as_utc(dt: datetime) -> datetime:
    """MongoDB returns naive UTC datetimes — make them timezone-aware."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# ── Token Revocation Blacklist ────────────────────────────────────────────────

_REVOKED_TOKENS: dict[str, float] = {}  # jti -> unix expiry timestamp (local cache / fallback)
_REVOKED_LOCK = Lock()


def _prune_revoked_tokens() -> None:
    """Remove expired entries from the in-memory blacklist."""
    now = time.time()
    with _REVOKED_LOCK:
        expired = [jti for jti, exp in _REVOKED_TOKENS.items() if exp < now]
        for jti in expired:
            del _REVOKED_TOKENS[jti]


async def revoke_token(jti: str, expires_at: float | None = None) -> None:
    """Add a JWT ID to the shared revocation blacklist.

    Args:
        jti: The JWT ID to revoke.
        expires_at: Unix timestamp when this token naturally expires.
                    If None, defaults to 30 days from now (safe upper bound).
    """
    if expires_at is None:
        expires_at = time.time() + 30 * 24 * 3600
    with _REVOKED_LOCK:
        _REVOKED_TOKENS[jti] = expires_at

    redis = _get_redis()
    if redis is not None:
        try:
            await redis.setex(f"blacklist:{jti}", max(1, int(expires_at - time.time())), "1")
            return
        except Exception as exc:
            _disable_redis(exc)

    col = await _get_mongo_collection(_REVOKED_COLLECTION)
    if col is not None:
        try:
            await col.update_one(
                {"_id": jti},
                {"$set": {"expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc)}},
                upsert=True,
            )
        except Exception as exc:
            logger.warning("revoke_token: MongoDB write failed (%s) — revoked locally only.", exc)


async def is_token_revoked_async(jti: str) -> bool:
    """True if the token was revoked on ANY instance (local cache, then shared store)."""
    _prune_revoked_tokens()
    if jti in _REVOKED_TOKENS:
        return True

    redis = _get_redis()
    if redis is not None:
        try:
            return await redis.get(f"blacklist:{jti}") is not None
        except Exception as exc:
            _disable_redis(exc)

    col = await _get_mongo_collection(_REVOKED_COLLECTION)
    if col is not None:
        try:
            doc = await col.find_one({"_id": jti})
            # TTL cleanup runs periodically, so also check expiry explicitly
            return bool(doc) and _as_utc(doc["expires_at"]) > datetime.now(timezone.utc)
        except Exception as exc:
            logger.warning("is_token_revoked_async: MongoDB read failed (%s).", exc)
    return False


# ── Login / Register Attempt Limiter ──────────────────────────────────────────

_RATE_LIMIT_WINDOW_SECONDS = 900  # 15 minutes
_MAX_ATTEMPTS = 5
_rate_limit_store: dict[str, dict] = defaultdict(lambda: {"count": 0, "window_start": 0.0})
_rate_limit_lock = Lock()


def _limit_reached(count: int, record: bool) -> bool:
    # After recording, the attempt that pushes past the limit is blocked; a
    # read-only pre-check blocks once the limit has been used up.
    return count > _MAX_ATTEMPTS if record else count >= _MAX_ATTEMPTS


async def rate_limit_check(ip: str, *, scope: str = "login", record: bool = True) -> tuple[bool, int]:
    """
    Check if IP exceeded the attempt limit. Returns (exceeded, retry_after_seconds).

    record=True counts this call as an attempt; record=False only checks the
    current count (used for the pre-check before a login, so one failed login
    is counted once, not twice). Each scope (e.g. "login", "register") has its
    own counter so registrations don't use up the login budget.
    """
    now = time.time()
    store_key = ip if scope == "login" else f"{scope}:{ip}"

    redis = _get_redis()
    if redis is not None:
        try:
            key = f"ratelimit:{store_key}"
            if record:
                count = await redis.incr(key)
                if count == 1:
                    await redis.expire(key, _RATE_LIMIT_WINDOW_SECONDS)
            else:
                count = int(await redis.get(key) or 0)
            if _limit_reached(count, record):
                return True, max(0, await redis.ttl(key))
            return False, 0
        except Exception as exc:
            _disable_redis(exc)

    col = await _get_mongo_collection(_RATE_LIMIT_COLLECTION)
    if col is not None:
        try:
            from pymongo import ReturnDocument
            now_dt = datetime.now(timezone.utc)
            doc_id = f"{scope}:{ip}"
            if record:
                # One atomic update: increment inside the current window, or
                # start a new window if there is none / it has expired.
                active = {"$gt": ["$expires_at", now_dt]}
                doc = await col.find_one_and_update(
                    {"_id": doc_id},
                    [{"$set": {
                        "count": {"$cond": [active, {"$add": ["$count", 1]}, 1]},
                        "expires_at": {"$cond": [active, "$expires_at",
                                                 now_dt + timedelta(seconds=_RATE_LIMIT_WINDOW_SECONDS)]},
                    }}],
                    upsert=True,
                    return_document=ReturnDocument.AFTER,
                )
            else:
                doc = await col.find_one({"_id": doc_id, "expires_at": {"$gt": now_dt}})
            count = doc["count"] if doc else 0
            if _limit_reached(count, record):
                return True, max(0, int((_as_utc(doc["expires_at"]) - now_dt).total_seconds()))
            return False, 0
        except Exception as exc:
            logger.warning("rate_limit_check: MongoDB failed (%s) — memory fallback.", exc)

    with _rate_limit_lock:
        record_ = _rate_limit_store[store_key]
        if now - record_["window_start"] > _RATE_LIMIT_WINDOW_SECONDS:
            record_["count"] = 0
            record_["window_start"] = now
        if record:
            record_["count"] += 1
        if _limit_reached(record_["count"], record):
            retry_after = int(_RATE_LIMIT_WINDOW_SECONDS - (now - record_["window_start"]))
            return True, max(0, retry_after)
        return False, 0


async def rate_limit_clear(ip: str) -> None:
    """Reset the login attempt counter for IP after a successful login."""
    with _rate_limit_lock:
        _rate_limit_store.pop(ip, None)

    redis = _get_redis()
    if redis is not None:
        try:
            await redis.delete(f"ratelimit:{ip}")
            return
        except Exception as exc:
            _disable_redis(exc)

    col = await _get_mongo_collection(_RATE_LIMIT_COLLECTION)
    if col is not None:
        try:
            await col.delete_one({"_id": f"login:{ip}"})
        except Exception as exc:
            logger.warning("rate_limit_clear: MongoDB failed (%s).", exc)


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
