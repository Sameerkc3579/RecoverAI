"""
RecoveryAgent — Shared FastAPI dependencies.

Provides `get_current_user` — a dependency that decodes the JWT Bearer token,
looks up the user in MongoDB, and returns the user document.
If the token is missing, expired, or the user doesn't exist → 401.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.core.config import settings
from app.core.database import get_collection

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

USERS_COLLECTION = "users"


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Decode a JWT Bearer token and return the authenticated user document.

    Raises HTTP 401 if the token is invalid, expired, or the user is missing.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        email: str | None = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    col = get_collection(USERS_COLLECTION)
    user = await col.find_one({"email": email})
    if user is None:
        raise credentials_exception

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    return user


async def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Ensure the current user is an authorized admin.
    """
    if current_user.get("email") != "imexperiment4@gmail.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access God Mode resources.",
        )
    return current_user
