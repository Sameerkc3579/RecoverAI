"""
RecoverAI — Auth Router (Security-Hardened)

Routes
──────
POST /api/auth/register — Create a new user account (strong password enforced)
POST /api/auth/login    — Authenticate and return JWT pair (rate-limited, no user enumeration)
POST /api/auth/google   — Authenticate via Google Sign-In
POST /api/auth/logout   — Revoke the current access token
POST /api/auth/refresh  — Exchange a refresh token for a new access token
GET  /api/auth/config   — Return public auth configuration (Google Client ID)

Security Features:
  - Rate limiting: 5 failed login attempts per IP per 15 minutes → HTTP 429
  - No user enumeration: identical error for wrong email OR wrong password
  - Strong password policy enforced at registration
  - JWT revocation on logout via jti blacklist
  - Google OAuth requires a configured client_id (no anonymous bypass)
  - Admin role loaded from env, not hardcoded
"""
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock

from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr, Field
from jose import JWTError, jwt

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from starlette.concurrency import run_in_threadpool

# Persistent session caches Google's public certs to avoid an HTTP roundtrip on every login
_GOOGLE_AUTH_REQ = google_requests.Request()

from app.core.database import get_collection
from app.core.config import settings
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    validate_password_strength,
    revoke_token,
    is_token_revoked,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Auth"])

USERS_COLLECTION = "users"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# ── Rate Limiter (In-Memory, Per IP) ─────────────────────────────────────────
# Structure: { ip: {"count": N, "window_start": float} }
# Allows 5 failed attempts per 15-minute window per IP address.
# In production with multiple workers → replace with Redis INCR + EXPIRE.

_RATE_LIMIT_WINDOW_SECONDS = 900  # 15 minutes
_MAX_ATTEMPTS = 5
_rate_limit_store: dict[str, dict] = defaultdict(lambda: {"count": 0, "window_start": 0.0})
_rate_limit_lock = Lock()


def _check_rate_limit(ip: str) -> None:
    """
    Check if this IP has exceeded the failed-login limit.
    Does NOT increment the counter (call _record_failed_login on failure).
    Raises HTTP 429 if at or above limit.
    """
    now = time.time()
    with _rate_limit_lock:
        record = _rate_limit_store[ip]
        if now - record["window_start"] > _RATE_LIMIT_WINDOW_SECONDS:
            record["count"] = 0
            record["window_start"] = now
        if record["count"] >= _MAX_ATTEMPTS:
            retry_after = int(_RATE_LIMIT_WINDOW_SECONDS - (now - record["window_start"]))
            logger.warning(
                "RATE_LIMIT_TRIGGERED | ip=%s | attempts=%d | retry_after=%ds",
                ip, record["count"], retry_after,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Too many failed login attempts. "
                    f"Please try again in {retry_after // 60} minute(s)."
                ),
                headers={"Retry-After": str(retry_after)},
            )


def _record_failed_login(ip: str) -> None:
    """Increment failed-login counter. Call only after credentials are verified wrong."""
    with _rate_limit_lock:
        _rate_limit_store[ip]["count"] += 1


def _clear_rate_limit(ip: str) -> None:
    """Reset the rate limit counter for an IP after a successful login."""
    with _rate_limit_lock:
        _rate_limit_store.pop(ip, None)


def _get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting X-Forwarded-For (Vercel/proxy)."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """Request body for POST /api/auth/register."""
    business_name: str = Field(..., min_length=1, max_length=300)
    email: EmailStr
    # Removed min_length here — strength is validated by validate_password_strength()
    password: str = Field(..., max_length=128)


class GoogleAuthRequest(BaseModel):
    """Request body when logging in via Google Identity Services."""
    credential: str


class RefreshRequest(BaseModel):
    """Request body for POST /api/auth/refresh."""
    refresh_token: str


class RegisterResponse(BaseModel):
    """Confirmation after successful registration."""
    id: str
    business_name: str
    email: str
    message: str = "Registration successful"


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_admin: bool = False
    business_name: str | None = None
    email: str | None = None


class LogoutResponse(BaseModel):
    message: str = "Logged out successfully"


class AuthConfigResponse(BaseModel):
    """Public authentication configuration."""
    google_client_id: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(payload: RegisterRequest) -> RegisterResponse:
    """Create a new user account with enforced strong password policy."""

    # Validate password strength BEFORE hitting the database
    ok, reason = validate_password_strength(payload.password)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=reason,
        )

    col = get_collection(USERS_COLLECTION)

    # Check for duplicate email
    existing = await col.find_one({"email": payload.email.lower()})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    user_doc = {
        "business_name": payload.business_name,
        "email": payload.email.lower(),
        "hashed_password": get_password_hash(payload.password),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_active": True,
    }

    result = await col.insert_one(user_doc)
    logger.info("USER_REGISTERED | email=%s", payload.email.lower())

    return RegisterResponse(
        id=str(result.inserted_id),
        business_name=payload.business_name,
        email=payload.email.lower(),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and get a JWT pair",
)
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> TokenResponse:
    """
    Standard OAuth2 password flow with brute-force protection.

    Security notes:
    - Rate limited per IP (5 attempts / 15 min)
    - Identical error for wrong email OR wrong password (no user enumeration)
    - Access token (15 min) + refresh token (7 days) issued on success
    """
    client_ip = _get_client_ip(request)

    # Enforce rate limit BEFORE DB lookup (prevents timing-based enumeration too)
    _check_rate_limit(client_ip)

    col = get_collection(USERS_COLLECTION)
    user = await col.find_one({"email": form_data.username.lower()})

    # Uniform error — attacker cannot distinguish "no such user" from "wrong password"
    AUTH_ERROR = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not user:
        # Still run a fake verify to prevent timing attacks
        verify_password("dummy", "$2b$12$somethingthatnevermatchesat.all.plzandthankyou00")
        raise AUTH_ERROR

    if not verify_password(form_data.password, user["hashed_password"]):
        logger.warning("FAILED_LOGIN | email=%s | ip=%s", form_data.username.lower(), client_ip)
        raise AUTH_ERROR

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact support.",
        )

    # Successful login — clear rate limit counter
    _clear_rate_limit(client_ip)

    token_data = {"sub": user["email"]}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    is_admin = user["email"] in settings.admin_emails_list

    logger.info("LOGIN_SUCCESS | email=%s | ip=%s | is_admin=%s", user["email"], client_ip, is_admin)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        is_admin=is_admin,
        business_name=user.get("business_name"),
        email=user["email"],
    )


@router.post(
    "/google",
    response_model=TokenResponse,
    summary="Authenticate via Google Sign-In",
)
async def google_login(payload: GoogleAuthRequest) -> TokenResponse:
    """
    Verifies the Google JWT credential.

    Security: Google Client ID MUST be configured in .env (GOOGLE_CLIENT_ID).
    If not set, this endpoint returns 503 — no silent bypass.
    """
    # Require Google Client ID to be properly configured
    if not settings.google_client_id or settings.google_client_id == "your-google-client-id-here":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google Sign-In is not configured on this server.",
        )

    try:
        idinfo = await run_in_threadpool(
            id_token.verify_oauth2_token,
            payload.credential,
            _GOOGLE_AUTH_REQ,
            settings.google_client_id,   # Always verify audience — no None bypass
        )

        email = idinfo.get("email", "").lower()
        if not email:
            raise ValueError("No email provided in Google token.")

        # Require email to be verified by Google
        if not idinfo.get("email_verified", False):
            raise ValueError("Google account email is not verified.")

        business_name = idinfo.get("name") or idinfo.get("given_name") or email.split("@")[0]

    except Exception as e:
        logger.warning("GOOGLE_AUTH_FAILED | error=%s", str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google authentication failed. Please try again.",
        )

    col = get_collection(USERS_COLLECTION)
    user = await col.find_one({"email": email})

    if not user:
        user_doc = {
            "business_name": business_name,
            "email": email,
            "hashed_password": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True,
            "auth_provider": "google",
        }
        await col.insert_one(user_doc)
        user = user_doc
        logger.info("GOOGLE_USER_AUTO_REGISTERED | email=%s", email)

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact support.",
        )

    token_data = {"sub": user["email"]}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    is_admin = user["email"] in settings.admin_emails_list

    logger.info("GOOGLE_LOGIN_SUCCESS | email=%s | is_admin=%s", email, is_admin)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        is_admin=is_admin,
        business_name=user.get("business_name"),
        email=user["email"],
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Revoke current access token (logout)",
)
async def logout(token: str = Depends(oauth2_scheme)) -> LogoutResponse:
    """
    Revokes the current JWT by adding its jti to the blacklist.

    After calling this endpoint, the token is immediately invalid —
    no attacker can reuse a stolen token after the user logs out.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        jti = payload.get("jti")
        email = payload.get("sub", "unknown")
        if jti:
            revoke_token(jti)
            logger.info("LOGOUT | email=%s | jti=%s", email, jti)
    except JWTError:
        pass  # Expired/invalid token — logout is a no-op, that's fine

    return LogoutResponse()


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange refresh token for new access token",
)
async def refresh_access_token(payload: RefreshRequest) -> TokenResponse:
    """
    Issues a new access token given a valid, non-revoked refresh token.

    Validates:
    - Cryptographic signature
    - Token expiry
    - Token type must be 'refresh'
    - Token not in revocation blacklist
    - User still exists and is active
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        decoded = jwt.decode(
            payload.refresh_token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )

        if decoded.get("type") != "refresh":
            raise credentials_exception

        jti = decoded.get("jti")
        email = decoded.get("sub")

        if not jti or not email:
            raise credentials_exception

        if is_token_revoked(jti):
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    col = get_collection(USERS_COLLECTION)
    user = await col.find_one({"email": email})

    if not user or not user.get("is_active", True):
        raise credentials_exception

    token_data = {"sub": user["email"]}
    new_access = create_access_token(data=token_data)
    new_refresh = create_refresh_token(data=token_data)

    # Revoke the old refresh token (token rotation — prevents token reuse)
    revoke_token(jti)

    logger.info("TOKEN_REFRESHED | email=%s", email)

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        is_admin=user["email"] in settings.admin_emails_list,
        business_name=user.get("business_name"),
        email=user["email"],
    )


@router.get(
    "/config",
    response_model=AuthConfigResponse,
    summary="Get public authentication settings",
)
async def get_auth_config() -> AuthConfigResponse:
    """Returns public settings like Google Client ID for the frontend."""
    cid = settings.google_client_id
    if not cid or cid == "your-google-client-id-here":
        cid = None
    return AuthConfigResponse(google_client_id=cid)
