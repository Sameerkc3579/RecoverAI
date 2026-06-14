from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime, timezone

from app.core.database import get_collection
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/users", tags=["Users"])

# Explicit allowlist of user-writable settings keys — prevents arbitrary key injection
_ALLOWED_SETTINGS_KEYS = {
    "businessName", "ownerName", "phone", "city", "email",
    "gstin", "autoReminder", "whatsappEnabled", "emailEnabled",
    "legalAtDays", "reminderDays", "commissionRate"
}

class UserSettingsUpdate(BaseModel):
    businessName: Optional[str] = Field(None, max_length=300)
    ownerName: Optional[str] = Field(None, max_length=200)
    phone: Optional[str] = Field(None, max_length=20)
    city: Optional[str] = Field(None, max_length=100)
    email: Optional[EmailStr] = None  # Contact email — validated format
    gstin: Optional[str] = Field(None, max_length=20)
    autoReminder: Optional[bool] = None
    whatsappEnabled: Optional[bool] = None
    emailEnabled: Optional[bool] = None
    legalAtDays: Optional[int] = Field(None, ge=1, le=365)  # 1–365 days
    reminderDays: Optional[list[int]] = None
    commissionRate: Optional[float] = Field(None, ge=0.0, le=100.0)  # 0–100%
    # NOTE: `plan` is intentionally excluded — subscription plan changes are admin-only.

    @field_validator("reminderDays")
    @classmethod
    def validate_reminder_days(cls, v):
        if v is not None:
            if len(v) > 10:
                raise ValueError("Maximum 10 reminder days allowed")
            for day in v:
                if not (1 <= day <= 365):
                    raise ValueError(f"Each reminder day must be between 1 and 365, got {day}")
        return v

# Safe user profile response — only expose fields that are safe to return
class UserProfileResponse(BaseModel):
    id: str
    business_name: Optional[str] = None
    email: str
    is_active: bool = True
    plan: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    auth_provider: Optional[str] = None
    created_at: Optional[str] = None
    settings: Optional[dict] = None
    drip_settings: Optional[dict] = None

    class Config:
        extra = "ignore"  # Silently drop any DB fields not in this model

@router.get("/me", summary="Get current user profile & settings")
async def get_me(current_user: dict = Depends(get_current_user)) -> dict:
    """Return a curated user profile — never exposes internal DB fields."""
    safe_fields = {
        "id": str(current_user["_id"]),
        "business_name": current_user.get("business_name"),
        "email": current_user.get("email"),
        "is_active": current_user.get("is_active", True),
        "plan": current_user.get("plan"),
        "phone": current_user.get("phone"),
        "city": current_user.get("city"),
        "auth_provider": current_user.get("auth_provider"),
        "created_at": current_user.get("created_at"),
        "settings": current_user.get("settings", {}),
        "drip_settings": current_user.get("drip_settings", {}),
    }
    return safe_fields

@router.put("/me/settings", summary="Update current user settings")
async def update_settings(
    payload: UserSettingsUpdate,
    current_user: dict = Depends(get_current_user)
):
    update_data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}

    # SECURITY: Explicitly block any privileged fields that must not be user-writable.
    _BLOCKED_USER_FIELDS = {"plan", "is_active", "hashed_password", "_id", "owner_id", "auth_provider"}
    for blocked in _BLOCKED_USER_FIELDS:
        update_data.pop(blocked, None)

    # SECURITY: Only write keys that are in the explicit allowlist — prevents arbitrary key injection
    update_data = {k: v for k, v in update_data.items() if k in _ALLOWED_SETTINGS_KEYS}

    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields provided to update")

    set_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    # Update root-level fields
    if "businessName" in update_data:
        set_fields["business_name"] = update_data["businessName"]
    if "phone" in update_data:
        set_fields["phone"] = update_data["phone"]
    if "city" in update_data:
        set_fields["city"] = update_data["city"]

    # Merge into the `settings` sub-document
    for k, v in update_data.items():
        set_fields[f"settings.{k}"] = v

    col = get_collection("users")
    await col.update_one(
        {"_id": current_user["_id"]},
        {"$set": set_fields}
    )
    
    # Return curated response — not raw DB document
    updated_user = await col.find_one({"_id": current_user["_id"]})
    return {
        "id": str(updated_user["_id"]),
        "business_name": updated_user.get("business_name"),
        "email": updated_user.get("email"),
        "is_active": updated_user.get("is_active", True),
        "plan": updated_user.get("plan"),
        "settings": updated_user.get("settings", {}),
        "drip_settings": updated_user.get("drip_settings", {}),
    }
