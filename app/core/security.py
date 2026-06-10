"""
RecoverAI — Security Utilities (Hardened)

Provides:
  - Password hashing (bcrypt)
  - Password strength validation
  - JWT access + refresh token creation (with jti claim for revocation)
  - Token revocation blacklist (in-memory, Redis-ready)
"""
import uuid
import re
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings

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


# ── Token Revocation Blacklist ────────────────────────────────────────────────
# In-memory dict mapping revoked JWT IDs (jti) -> expiry timestamp.
# Expired entries are pruned on each lookup to prevent unbounded memory growth.
# In production with multiple workers, replace this with a Redis SET + EXPIREAT.
# The interface (revoke_token / is_token_revoked) is identical to a Redis backend.

_REVOKED_TOKENS: dict[str, float] = {}  # jti -> unix expiry timestamp


def _prune_revoked_tokens() -> None:
    """Remove expired entries from the blacklist (called on each check)."""
    import time
    now = time.time()
    expired = [jti for jti, exp in _REVOKED_TOKENS.items() if exp < now]
    for jti in expired:
        del _REVOKED_TOKENS[jti]


def revoke_token(jti: str, expires_at: float | None = None) -> None:
    """Add a JWT ID to the revocation blacklist with an optional expiry time.

    Args:
        jti: The JWT ID to revoke.
        expires_at: Unix timestamp when this token naturally expires.
                    If None, defaults to 30 days from now (safe upper bound).
    """
    import time
    if expires_at is None:
        expires_at = time.time() + 30 * 24 * 3600  # 30-day fallback
    _REVOKED_TOKENS[jti] = expires_at


def is_token_revoked(jti: str) -> bool:
    """Return True if the given JWT ID has been revoked and not yet expired."""
    _prune_revoked_tokens()
    return jti in _REVOKED_TOKENS


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
        "iss": "recoverai",
        "aud": "recoverai-api",
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
        "iss": "recoverai",
        "aud": "recoverai-api",
    })
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
