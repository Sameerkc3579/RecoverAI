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
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Request, Response
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
import jwt

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
    is_token_revoked_async,
    rate_limit_check,
    rate_limit_clear,
    JWT_AUDIENCE,
    JWT_ISSUER,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Auth"])

USERS_COLLECTION = "users"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
# Non-raising variant for endpoints that also accept the HttpOnly cookie
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def _get_client_ip(request: Request) -> str:
    """
    Extract the real client IP, hardened against X-Forwarded-For spoofing.

    Attack scenario: An attacker can inject arbitrary IPs at the *front* of the
    X-Forwarded-For header (e.g., "1.1.1.1, real-attacker-ip").
    Taking the leftmost IP (as the original code did) would let any attacker
    bypass the rate limiter by simply rotating the spoofed first entry.

    Fix: Walk the X-Forwarded-For list from right-to-left and return the
    rightmost *public* IP — the last untrusted hop that the upstream proxy
    actually observed. If all IPs are private/loopback (internal network),
    fall back to the direct socket peer address.
    """
    import ipaddress

    # Only honour X-Forwarded-For behind a trusted proxy. Without one, the header
    # is attacker-controlled: spoofing it would let an attacker bypass the login
    # brute-force limiter or frame a victim's IP. Fall back to the socket peer.
    if not settings.proxy_headers_trusted:
        return request.client.host if request.client else "unknown"

    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        candidates = [ip.strip() for ip in reversed(forwarded.split(","))]
        for ip in candidates:
            try:
                addr = ipaddress.ip_address(ip)
                if not (addr.is_private or addr.is_loopback or addr.is_link_local):
                    return ip
            except ValueError:
                continue
        # All were private/invalid — use the rightmost valid entry
        try:
            last_xff = forwarded.split(",")[-1].strip()
            ipaddress.ip_address(last_xff)
            return last_xff
        except ValueError:
            pass

    return request.client.host if request.client else "unknown"


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """Request body for POST /api/auth/register."""
    business_name: str = Field(..., min_length=1, max_length=300)
    email: EmailStr
    # Removed min_length here — strength is validated by validate_password_strength()
    password: str = Field(..., min_length=8, max_length=128)


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
async def register(payload: RegisterRequest, request: Request) -> RegisterResponse:
    """Create a new user account with enforced strong password policy."""
    client_ip = _get_client_ip(request)
    exceeded, retry_after = await rate_limit_check(client_ip, scope="register")
    if exceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many attempts. Please try again in {retry_after // 60} minute(s).",
            headers={"Retry-After": str(retry_after)},
        )

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
            detail="Registration could not be completed. Please try again or use a different email.",
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

    # Enforce rate limit BEFORE DB lookup (prevents timing-based enumeration too).
    # Read-only check — only failed attempts below are counted.
    exceeded, retry_after = await rate_limit_check(client_ip, record=False)
    if exceeded:
        logger.warning(
            "RATE_LIMIT_TRIGGERED | ip=%s | retry_after=%ds", client_ip, retry_after
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please try again in {retry_after // 60} minute(s).",
            headers={"Retry-After": str(retry_after)},
        )

    col = get_collection(USERS_COLLECTION)
    user = await col.find_one({"email": form_data.username.lower()})

    # Uniform error — attacker cannot distinguish "no such user" from "wrong password"
    AUTH_ERROR = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not user:
        await rate_limit_check(client_ip)  # count the failure
        # SECURITY: Run dummy bcrypt even when user doesn't exist to prevent timing attack.
        verify_password(form_data.password, "$2b$12$notarealhashjustpaddingtomatch..")
        raise AUTH_ERROR

    if not verify_password(form_data.password, user["hashed_password"]):
        logger.warning("FAILED_LOGIN | email=%s | ip=%s", form_data.username.lower(), client_ip)
        await rate_limit_check(client_ip)  # count the failure
        raise AUTH_ERROR

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact support.",
        )

    # Successful login — clear rate limit counter
    await rate_limit_clear(client_ip)

    token_data = {"sub": user["email"]}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    is_admin = user["email"] in settings.admin_emails_list

    logger.info("LOGIN_SUCCESS | email=%s | ip=%s | is_admin=%s", user["email"], client_ip, is_admin)

    # Build JSON response with non-sensitive fields only
    response = JSONResponse(content={
        "token_type": "bearer",
        "is_admin": is_admin,
        "business_name": user.get("business_name"),
        "email": user["email"],
        # access_token also included for backward-compat; will be removed once
        # all clients switch to cookie-only mode
        "access_token": access_token,
    })

    # Set HttpOnly, Secure cookies — inaccessible to JavaScript (XSS-safe)
    _set_auth_cookies(response, access_token, refresh_token)
    return response


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
            "hashed_password": None,  # nosec B105
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

    response = JSONResponse(content={
        "token_type": "bearer",
        "is_admin": is_admin,
        "business_name": user.get("business_name"),
        "email": user["email"],
        "access_token": access_token,
    })
    _set_auth_cookies(response, access_token, refresh_token)
    return response


class LogoutBody(BaseModel):
    """Optional body for POST /api/auth/logout to also revoke refresh token."""
    refresh_token: Optional[str] = None


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Revoke current access token (logout)",
)
async def logout(
    request: Request,
    header_token: Optional[str] = Depends(optional_oauth2_scheme),
    body: Optional[LogoutBody] = None,
) -> LogoutResponse:
    """
    Revokes the current JWT by adding its jti to the blacklist.

    After calling this endpoint, the token is immediately invalid —
    no attacker can reuse a stolen token after the user logs out.

    The browser app authenticates with HttpOnly cookies (no Authorization
    header), so tokens are read from the header OR the cookies.
    """
    token = header_token or request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )
        jti = payload.get("jti")
        email = payload.get("sub", "unknown")
        if jti:
            revoke_token(jti)
            logger.info("LOGOUT | email=%s | jti=%s", email, jti)
    except jwt.InvalidTokenError:
        pass  # Expired/invalid token — logout is a no-op, that's fine

    # Also revoke the refresh token if provided
    body_refresh = getattr(body, 'refresh_token', None) or request.cookies.get("refresh_token")
    if body_refresh:
        try:
            refresh_payload = jwt.decode(
                body_refresh,
                settings.secret_key,
                algorithms=[settings.algorithm],
                audience=JWT_AUDIENCE,
                issuer=JWT_ISSUER,
            )
            refresh_jti = refresh_payload.get("jti")
            refresh_exp = refresh_payload.get("exp")
            if refresh_jti:
                revoke_token(refresh_jti, float(refresh_exp) if refresh_exp else None)
        except jwt.InvalidTokenError:
            pass  # Already expired — that's fine

    response = JSONResponse(content={"message": "Logged out successfully"})
    # Clear both auth cookies from the browser
    response.delete_cookie("access_token", httponly=True, samesite="lax")
    response.delete_cookie("refresh_token", httponly=True, samesite="lax")
    return response


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set HttpOnly, Secure, SameSite=Lax cookies for access and refresh tokens."""
    access_max_age = settings.access_token_expire_minutes * 60
    refresh_max_age = settings.refresh_token_expire_days * 24 * 3600
    cookie_kwargs = dict(
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain or None,
    )
    response.set_cookie("access_token", access_token, max_age=access_max_age, **cookie_kwargs)
    response.set_cookie("refresh_token", refresh_token, max_age=refresh_max_age, **cookie_kwargs)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange refresh token for new access token",
)
async def refresh_access_token(request: Request, payload: Optional[RefreshRequest] = None) -> TokenResponse:
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

    # Body token (API clients) or the HttpOnly cookie (browser app)
    refresh_token = payload.refresh_token if payload else request.cookies.get("refresh_token")
    if not refresh_token:
        raise credentials_exception

    try:
        decoded = jwt.decode(
            refresh_token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
        )

        if decoded.get("type") != "refresh":
            raise credentials_exception

        jti = decoded.get("jti")
        email = decoded.get("sub")

        if not jti or not email:
            raise credentials_exception

        if await is_token_revoked_async(jti):
            raise credentials_exception

    except jwt.InvalidTokenError:
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

    response = JSONResponse(content={
        "token_type": "bearer",
        "is_admin": user["email"] in settings.admin_emails_list,
        "business_name": user.get("business_name"),
        "email": user["email"],
        "access_token": new_access,
    })
    _set_auth_cookies(response, new_access, new_refresh)
    return response


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
