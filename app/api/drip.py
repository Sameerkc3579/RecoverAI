import hmac
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.database import get_collection
from app.api.deps import get_current_user
from app.workers.drip_scheduler import run_daily_drips

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/drip-settings", tags=["Drip Campaigns"])
cron_router = APIRouter(tags=["Cron"])

_IST = timezone(timedelta(hours=5, minutes=30))
# A run whose lock is older than this without finishing was killed (e.g. by the
# serverless timeout) and may be retried
_STALE_RUN_AFTER = timedelta(minutes=15)

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


@cron_router.get("/api/cron/drips", include_in_schema=False)
async def cron_run_drips(request: Request):
    """
    Daily drip run for serverless hosting (Vercel Cron — see vercel.json), where
    the in-process APScheduler never fires because no process stays alive.

    Requires CRON_SECRET: Vercel sends "Authorization: Bearer <CRON_SECRET>" on
    every cron call once the variable is set in the project. Without it the
    endpoint is disabled rather than left open.

    Runs at most once per IST day (a MongoDB lock). A run that raises releases the
    lock so it can be retried; a run killed mid-way (no finished_at after 15 min)
    is treated as crashed and may run again.
    """
    if not settings.cron_secret:
        logger.error("CRON_DRIPS_DISABLED | CRON_SECRET is not set — refusing /api/cron/drips")
        raise HTTPException(status_code=401, detail="Unauthorized")
    auth = request.headers.get("authorization", "")
    if not hmac.compare_digest(auth.encode(), f"Bearer {settings.cron_secret}".encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")

    runs_col = get_collection("cron_runs")
    run_id = f"drips:{datetime.now(_IST).date().isoformat()}"
    now = datetime.now(timezone.utc)
    # Clear a lock left by a run that was killed before finishing
    await runs_col.delete_one({"_id": run_id, "finished_at": {"$exists": False},
                               "started_at": {"$lt": now - _STALE_RUN_AFTER}})
    # Ownership token: if this run is ever reclaimed as stale, it must not
    # delete or complete the lock that now belongs to the newer run.
    owner = {"_id": run_id, "token": uuid.uuid4().hex}
    try:
        await runs_col.insert_one({**owner, "started_at": now})
    except DuplicateKeyError:
        return {"status": "skipped", "reason": "already ran today"}

    try:
        result = await run_daily_drips(time_budget_seconds=settings.cron_time_budget_seconds)
    except Exception:
        logger.exception("CRON_DRIPS_FAILED | %s — releasing the lock so it can be retried", run_id)
        await runs_col.delete_one(owner)
        raise HTTPException(status_code=500, detail="Drip run failed")

    if result.get("failed_users") or result.get("failed_invoices") or result.get("stopped_early"):
        # Work was left undone — per-step idempotency makes a retry safe, so keep
        # the day retryable instead of marking it finished
        logger.error("CRON_DRIPS_PARTIAL | %s | %s — releasing the lock so it can be retried", run_id, result)
        await runs_col.delete_one(owner)
        return {"status": "partial", **result}

    await runs_col.update_one(
        owner,
        {"$set": {"finished_at": datetime.now(timezone.utc), **result}},
    )
    logger.info("CRON_DRIPS | %s | %s", run_id, result)
    return {"status": "ok", **result}
