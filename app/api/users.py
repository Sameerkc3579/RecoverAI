from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from datetime import datetime, timezone

from app.core.database import get_collection
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/users", tags=["Users"])

class UserSettingsUpdate(BaseModel):
    businessName: Optional[str] = None
    ownerName: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    email: Optional[str] = None  # Contact email, not login email
    gstin: Optional[str] = None
    autoReminder: Optional[bool] = None
    whatsappEnabled: Optional[bool] = None
    emailEnabled: Optional[bool] = None
    legalAtDays: Optional[int] = None
    reminderDays: Optional[list[int]] = None
    commissionRate: Optional[float] = None
    # NOTE: `plan` is intentionally excluded — subscription plan changes are admin-only.
    # A user setting their own plan would be a privilege escalation vulnerability.

@router.get("/me", summary="Get current user profile & settings")
async def get_me(current_user: dict = Depends(get_current_user)):
    user = dict(current_user)
    user["_id"] = str(user["_id"])
    user.pop("hashed_password", None)
    return user

@router.put("/me/settings", summary="Update current user settings")
async def update_settings(
    payload: UserSettingsUpdate,
    current_user: dict = Depends(get_current_user)
):
    update_data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}

    # SECURITY: Explicitly block any privileged fields that must not be user-writable.
    # These should only be modified via admin endpoints.
    _BLOCKED_USER_FIELDS = {"plan", "is_active", "hashed_password", "_id", "owner_id", "auth_provider"}
    for blocked in _BLOCKED_USER_FIELDS:
        update_data.pop(blocked, None)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    # The payload uses camelCase, but the DB might use snake_case for some fields. 
    # For now, let's store settings in a nested "settings" object or just top level.
    # To keep it compatible with existing settings logic, we'll store it in a `settings` object
    # inside the user document, and we might map some fields to the root level (like business_name).
    
    set_fields = {"updated_at": datetime.now(timezone.utc).isoformat()}
    
    # Also update root level business_name, phone, city if they exist in payload
    if "businessName" in update_data:
        set_fields["business_name"] = update_data["businessName"]
    if "phone" in update_data:
        set_fields["phone"] = update_data["phone"]
    if "city" in update_data:
        set_fields["city"] = update_data["city"]

    # Merge into the existing `settings` sub-document using dotted keys instead of
    # replacing it wholesale. A wholesale replace ($set settings = update_data)
    # wiped every previously-saved setting whenever the user changed one field.
    for k, v in update_data.items():
        set_fields[f"settings.{k}"] = v

    col = get_collection("users")
    await col.update_one(
        {"_id": current_user["_id"]},
        {"$set": set_fields}
    )
    
    updated_user = await col.find_one({"_id": current_user["_id"]})
    updated_user["_id"] = str(updated_user["_id"])
    updated_user.pop("hashed_password", None)
    return updated_user


# ── Drip Campaign Settings ────────────────────────────────────────────────────

class DripStepConfig(BaseModel):
    enabled: bool = True

class DripSettingsPayload(BaseModel):
    """User-configurable drip campaign settings."""
    day_7: DripStepConfig = DripStepConfig(enabled=True)
    day_21: DripStepConfig = DripStepConfig(enabled=True)
    day_35: DripStepConfig = DripStepConfig(enabled=True)
    day_45: DripStepConfig = DripStepConfig(enabled=True)

# Default drip settings for new users who haven't configured anything yet
_DEFAULT_DRIP = {
    "day_7":  {"enabled": True},
    "day_21": {"enabled": True},
    "day_35": {"enabled": True},
    "day_45": {"enabled": True},
}


@router.get("/drip-settings", summary="Get drip campaign settings")
async def get_drip_settings(current_user: dict = Depends(get_current_user)):
    """Return the user's saved drip campaign preferences."""
    user_settings = current_user.get("drip_settings", _DEFAULT_DRIP)
    return {"drip_settings": user_settings}


@router.put("/drip-settings", summary="Save drip campaign settings")
async def update_drip_settings(
    payload: DripSettingsPayload,
    current_user: dict = Depends(get_current_user),
):
    """Persist the user's drip campaign preferences to MongoDB."""
    drip_data = payload.model_dump()

    col = get_collection("users")
    await col.update_one(
        {"_id": current_user["_id"]},
        {"$set": {
            "drip_settings": drip_data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"status": "ok", "drip_settings": drip_data}

