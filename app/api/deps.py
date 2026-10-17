"""
RecoverAI — Shared FastAPI dependencies (Security-Hardened).

Provides:
  - get_current_user  : Validates JWT, checks revocation blacklist, returns user doc
  - get_admin_user    : Ensures current user is in ADMIN_EMAILS list (from env, not hardcoded)
"""
import logging

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
import jwt

from app.core.config import settings
from app.core.database import get_collection
from app.core.security import is_token_revoked_async, JWT_AUDIENCE, JWT_ISSUER

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

USERS_COLLECTION = "users"


async def get_current_user(request: Request, token: str = Depends(oauth2_scheme)) -> dict:
    """
    Decode a JWT Bearer token and return the authenticated user document.

    Security checks performed (in order):
    1. JWT cryptographic signature verification
    2. Token expiry check (handled by jose)
    3. Token type must be 'access' (rejects refresh tokens used as access tokens)
    4. jti checked against revocation blacklist
    5. User existence check in MongoDB
    6. Account active status check

    Raises HTTP 401 if any check fails.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    actual_token = request.cookies.get("access_token") or token
    if not actual_token:
        raise credentials_exception

    try:
        payload = jwt.decode(
            actual_token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )

        # Enforce token type — refresh tokens cannot be used as access tokens
        if payload.get("type") != "access":
            raise credentials_exception

        email: str | None = payload.get("sub")
        jti: str | None = payload.get("jti")

        if email is None or jti is None:
            raise credentials_exception

        # Check if this specific token has been revoked (logout support)
        if await is_token_revoked_async(jti):
            logger.warning("REVOKED_TOKEN_USED | email=%s | jti=%s", email, jti)
            raise credentials_exception

    except jwt.InvalidTokenError:
        raise credentials_exception

    col = get_collection(USERS_COLLECTION)
    user = await col.find_one({"email": email})
    if user is None:
        raise credentials_exception

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact support.",
        )

    return user


async def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Ensure the current user is an authorized administrator.

    Admin emails are loaded from ADMIN_EMAILS environment variable — NOT hardcoded.
    This prevents attackers from knowing the admin email by reading source code.
    """
    if current_user.get("email") not in settings.admin_emails_list:
        logger.warning(
            "UNAUTHORIZED_ADMIN_ACCESS | email=%s | ip=unknown",
            current_user.get("email"),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource.",
        )
    return current_user
