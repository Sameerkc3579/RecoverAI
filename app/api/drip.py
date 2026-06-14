from typing import Dict, Any, Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.database import get_collection
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/drip-settings", tags=["Drip Campaigns"])

# Only these day keys are valid — prevents NoSQL injection via arbitrary string keys
ALLOWED_DRIP_DAYS = {"7", "21", "35", "45"}

class DripStep(BaseModel):
    enabled: bool
    channel: Literal["email", "whatsapp"] = "whatsapp"  # Strict enum — no arbitrary strings

class DripSettingsUpdate(BaseModel):
    # Dictionary mapping day (string) to DripStep — keys validated below
    settings: Dict[str, DripStep] = Field(..., max_length=10)  # Max 10 entries

    @field_validator("settings")
    @classmethod
    def validate_day_keys(cls, v: Dict[str, DripStep]) -> Dict[str, DripStep]:
        """Prevent NoSQL injection — only allow known safe day keys."""
        invalid_keys = set(v.keys()) - ALLOWED_DRIP_DAYS
        if invalid_keys:
            raise ValueError(f"Invalid drip day keys: {invalid_keys}. Allowed: {ALLOWED_DRIP_DAYS}")
        return v

@router.get("", response_model=Dict[str, Any], summary="Get current user's drip settings")
async def get_drip_settings(current_user: dict = Depends(get_current_user)):
    """Fetch the drip settings for the current user."""
    users_col = get_collection("users")
    user = await users_col.find_one({"_id": current_user["_id"]})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Default settings if none exist
    default_settings = {
        "7": {"enabled": True, "channel": "whatsapp"},
        "21": {"enabled": True, "channel": "whatsapp"},
        "35": {"enabled": True, "channel": "whatsapp"},
        "45": {"enabled": True, "channel": "whatsapp"}
    }
    
    return user.get("drip_settings", default_settings)

@router.put("", summary="Update current user's drip settings")
async def update_drip_settings(
    payload: DripSettingsUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update the drip settings for the current user."""
    users_col = get_collection("users")
    
    # Keys are already validated by the Pydantic validator above — safe to write
    settings_dict = {day: step.model_dump() for day, step in payload.settings.items()}
    
    result = await users_col.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"drip_settings": settings_dict}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {"status": "success", "drip_settings": settings_dict}
