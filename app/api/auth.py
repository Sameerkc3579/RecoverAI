"""
RecoveryAgent — Auth router.

Routes
──────
POST /api/auth/register — create a new user account
POST /api/auth/login    — authenticate and return a JWT
"""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends
from pydantic import BaseModel, EmailStr, Field

from google.oauth2 import id_token
from google.auth.transport import requests

from app.core.database import get_collection
from app.core.config import settings
from app.core.security import get_password_hash, verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["Auth"])

USERS_COLLECTION = "users"


# ── Schemas ───────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """Request body for POST /api/auth/register."""
    business_name: str = Field(..., min_length=1, max_length=300)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)

class GoogleAuthRequest(BaseModel):
    """Request body when logging in via Google Identity Services."""
    credential: str


class RegisterResponse(BaseModel):
    """Confirmation after successful registration."""
    id: str
    business_name: str
    email: str
    message: str = "Registration successful"


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    is_admin: bool = False

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
    """Create a new user account with hashed password."""
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

    return RegisterResponse(
        id=str(result.inserted_id),
        business_name=payload.business_name,
        email=payload.email.lower(),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and get a JWT",
)
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """
    Standard OAuth2 password flow.
    `username` field is the user's email.
    """
    col = get_collection(USERS_COLLECTION)
    user = await col.find_one({"email": form_data.username.lower()})

    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    access_token = create_access_token(
        data={"sub": user["email"]}
    )
    
    # Check if user is admin
    is_admin = user["email"] == "imexperiment4@gmail.com"

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        is_admin=is_admin
    )


@router.post(
    "/google",
    response_model=TokenResponse,
    summary="Authenticate via Google Sign-In"
)
async def google_login(payload: GoogleAuthRequest) -> TokenResponse:
    """
    Verifies the Google JWT credential. If the user doesn't exist, an account is automatically created.
    """
    if not settings.google_client_id or settings.google_client_id == "your-google-client-id-here":
        # Bypass for local dev / MVP if client ID isn't set yet (WARNING: Unsafe for prod without an ID)
        # We'll just extract the email from the unsigned token if no Client ID is provided.
        # But assuming the user WILL provide it, we still enforce verification.
        pass

    try:
        # Verify the token Google sent us
        idinfo = id_token.verify_oauth2_token(
            payload.credential, 
            requests.Request(), 
            settings.google_client_id if settings.google_client_id != "your-google-client-id-here" else None
        )
        
        email = idinfo.get("email", "").lower()
        if not email:
            raise ValueError("No email provided in Google token.")
        
        business_name = idinfo.get("name", email.split("@")[0])

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Google credential: {str(e)}"
        )

    col = get_collection(USERS_COLLECTION)
    user = await col.find_one({"email": email})

    # Auto-register if user doesn't exist
    if not user:
        user_doc = {
            "business_name": business_name,
            "email": email,
            "hashed_password": None, # Google users don't have a local password
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True,
        }
        await col.insert_one(user_doc)
        user = user_doc

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated.",
        )

    access_token = create_access_token(data={"sub": user["email"]})
    is_admin = user["email"] == "imexperiment4@gmail.com"

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        is_admin=is_admin
    )


@router.get(
    "/config",
    response_model=AuthConfigResponse,
    summary="Get public authentication settings"
)
async def get_auth_config() -> AuthConfigResponse:
    """Returns public settings like Google Client ID for the frontend."""
    cid = settings.google_client_id
    if cid == "your-google-client-id-here":
        cid = None
    return AuthConfigResponse(google_client_id=cid)
