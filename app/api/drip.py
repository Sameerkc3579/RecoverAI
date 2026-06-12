from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.database import get_collection
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/drip-settings", tags=["Drip Campaigns"])

class DripStep(BaseModel):
    enabled: bool
    channel: str = "email"

class DripSettingsUpdate(BaseModel):
    # Dictionary mapping day (string) to DripStep
    settings: Dict[str, DripStep]

@router.get("", response_model=Dict[str, Any], summary="Get current user's drip settings")
async def get_drip_settings(current_user: dict = Depends(get_current_user)):
    """Fetch the drip settings for the current user."""
    users_col = get_collection("users")
    user = await users_col.find_one({"_id": current_user["_id"]})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Default settings if none exist
    default_settings = {
        "7": {"enabled": True, "channel": "email"},
        "21": {"enabled": True, "channel": "email"},
        "35": {"enabled": True, "channel": "email"},
        "45": {"enabled": True, "channel": "email"}
    }
    
    return user.get("drip_settings", default_settings)

@router.put("", summary="Update current user's drip settings")
async def update_drip_settings(
    payload: DripSettingsUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update the drip settings for the current user."""
    users_col = get_collection("users")
    
    # Convert Pydantic models to dict
    settings_dict = {day: step.model_dump() for day, step in payload.settings.items()}
    
    result = await users_col.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"drip_settings": settings_dict}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
        
    return {"status": "success", "drip_settings": settings_dict}
