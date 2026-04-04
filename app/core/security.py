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

from jose import jwt
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
# In-memory set of revoked JWT IDs (jti).
# In production with multiple workers, replace this with a Redis SET.
# Interface is the same — just swap the storage backend.

_REVOKED_TOKENS: set[str] = set()


def revoke_token(jti: str) -> None:
    """Add a JWT ID to the revocation blacklist."""
    _REVOKED_TOKENS.add(jti)


def is_token_revoked(jti: str) -> bool:
    """Return True if the given JWT ID has been revoked."""
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
    })
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
