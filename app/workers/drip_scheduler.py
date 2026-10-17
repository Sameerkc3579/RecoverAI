import logging
import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from app.core.database import get_collection
from app.services.ai_service import generate_message
from app.services.whatsapp_service import _normalize_phone, _validate_phone, _mask_phone
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)

# Drip step days (must match ALLOWED_DRIP_DAYS in app/api/drip.py).
DRIP_STEP_DAYS = (7, 21, 35, 45)

# If the midnight job is missed (server down/restarted), a step is still sent
# on any of the next GRACE_DAYS - 1 days instead of being skipped forever.
# Steps are >= 10 days apart, so at most one step can match on a given day.
DRIP_GRACE_DAYS = 3

# Due dates are Indian calendar dates and the cron fires at 00:00 IST (18:30 UTC
# the previous day) — days overdue must be counted on the IST date.
IST = timezone(timedelta(hours=5, minutes=30))

# A "processing" claim older than this belongs to a run that died mid-draft
# (e.g. a serverless timeout) and may be reclaimed.
STALE_CLAIM_AFTER = timedelta(minutes=30)


def _due_step(days_overdue: int) -> Optional[int]:
    """Return the drip step day due for this many days overdue, if any."""
    for step_day in DRIP_STEP_DAYS:
        if step_day <= days_overdue < step_day + DRIP_GRACE_DAYS:
            return step_day
    return None

async def process_drip_for_user(user: dict, deadline: Optional[float] = None) -> int:
    """
    Process drip campaigns for a single user. Returns the number of drafts created.
    Stops starting new invoices once `deadline` (time.monotonic()) has passed.
    """
    owner_id = user["_id"]
    drip_settings = user.get("drip_settings", {})
    
    if not drip_settings:
        return 0
        
    invoices_col = get_collection("invoices")
    drip_log_col = get_collection("drip_log")
    
    # 1. Fetch all unresolved invoices with a due date
    cursor = invoices_col.find({
        "owner_id": owner_id,
        "recovered": False,
        "due_date": {"$exists": True, "$nin": [None, ""]}
    })
    
    today = datetime.now(IST).date()
    
    sent_count = 0
    
    async for invoice in cursor:
        if deadline is not None and time.monotonic() > deadline:
            logger.warning(f"Drip time budget reached for user {owner_id} — remaining invoices run next time")
            break
        claimed = False
        log_filter = None
        try:
            # Parse due date (format: YYYY-MM-DD)
            due_date_str = invoice["due_date"]
            # Handle possible datetime objects
            if isinstance(due_date_str, datetime):
                due_date_str = due_date_str.strftime("%Y-%m-%d")
            
            # Simple string parsing since we enforce YYYY-MM-DD in UI
            if "T" in due_date_str:
                due_date_str = due_date_str.split("T")[0]
                
            due_dt = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            days_overdue = (today - due_dt).days
            
            if days_overdue <= 0:
                continue
                
            # Find the drip step due today (exact day, or within the grace window)
            step_day = _due_step(days_overdue)
            if step_day is None:
                continue

            # Convert to string to match settings keys
            day_key = str(step_day)
                
            step = drip_settings.get(day_key)
            if not step or not step.get("enabled"):
                continue
                
            invoice_id = invoice["_id"]

            # 2. Cheap idempotency pre-check (did we already handle this step?)
            # The log keys on the step day, which is what older entries stored too.
            already_sent = await drip_log_col.find_one({
                "invoice_id": invoice_id,
                "days_overdue": step_day,
            })

            if already_sent:
                claimed_at = already_sent.get("claimed_at")
                if claimed_at and claimed_at.tzinfo is None:
                    claimed_at = claimed_at.replace(tzinfo=timezone.utc)  # Mongo returns naive UTC
                stale = (
                    already_sent.get("status") == "processing"
                    and claimed_at is not None
                    and datetime.now(timezone.utc) - claimed_at > STALE_CLAIM_AFTER
                )
                if not stale:
                    continue
                # Left behind by a run that died mid-draft — release and retry
                await drip_log_col.delete_one({"_id": already_sent["_id"], "status": "processing"})

            # We need to send a message. Phones are often entered formatted
            # ("+91 98765 43210") — normalise to digits before validating.
            contact_phone = _normalize_phone(invoice.get("phone"))
            if not contact_phone:
                logger.warning(f"Skipping drip for invoice {invoice_id} (no phone number)")
                continue
            
            # Validate phone number format
            if not _validate_phone(contact_phone):
                logger.warning(f"Skipping drip for invoice {invoice_id} (invalid phone format: {_mask_phone(contact_phone)})")
                continue
                
            # Atomically claim this (invoice, step) so concurrent runs — multiple
            # workers each running the scheduler — can't draft it twice.
            log_filter = {"invoice_id": invoice_id, "days_overdue": step_day}
            try:
                claim = await drip_log_col.update_one(
                    log_filter,
                    {"$setOnInsert": {
                        "owner_id": owner_id,
                        "channel": "whatsapp",
                        "status": "processing",
                        "claimed_at": datetime.now(timezone.utc),
                    }},
                    upsert=True,
                )
            except DuplicateKeyError:
                continue  # another run inserted the claim first
            if claim.upserted_id is None:
                continue  # already claimed or drafted by another run
            claimed = True

            # 3. Determine Tone
            tone_map = {
                "7": "Friendly",
                "21": "Firm Warning",
                "35": "Final Notice",
                "45": "Legal Threat"
            }
            tone = tone_map[day_key]
            
            # 4. Generate AI Message
            # Build invoice context
            inv_ctx = {
                "company": invoice.get("company"),
                "phone": contact_phone,
                "amount": invoice.get("amount"),
                "invoice_no": invoice.get("invoice_no", ""),
                "due_date": due_date_str,
                "status": invoice.get("status", "pending")
            }
            
            prompt = f"""
            You are an AI recovery agent representing our company.
            The debtor ({inv_ctx['company']}) is {days_overdue} days overdue on Invoice {inv_ctx['invoice_no']} (Amount: {inv_ctx['amount']}, due on {due_date_str}).
            Draft a short, professional, and {tone.lower()} WhatsApp reminder message.
            Return ONLY the drafted WhatsApp message, no extra conversational text.
            """
            
            message_body = await generate_message(
                prompt=prompt,
                invoice_data=inv_ctx,
                tone=tone,
                channel="whatsapp",
            )
            
            if not message_body:
                logger.error(f"Failed to generate AI message for invoice {invoice_id}")
                await drip_log_col.delete_one({**log_filter, "status": "processing"})
                continue
                
            # 5. Draft Mode: Save to whatsapp_drafts collection
            drafts_col = get_collection("whatsapp_drafts")
            await drafts_col.insert_one({
                "owner_id": owner_id,
                "invoice_id": invoice_id,
                "contact_phone": contact_phone,
                "incoming_message": "SYSTEM_DRIP_CAMPAIGN",
                "draft_reply": message_body,
                "status": "pending_approval",
                "created_at": datetime.now(timezone.utc),
                "drip_day": step_day
            })
            claimed = False  # the draft exists — never release the claim now

            # 6. Log success and increment reminder count
            await drip_log_col.update_one(
                log_filter,
                {"$set": {
                    "status": "drafted",
                    "sent_at": datetime.now(timezone.utc),
                    "actual_days_overdue": days_overdue,
                }},
            )
            
            await invoices_col.update_one(
                {"_id": invoice_id},
                {"$inc": {"reminders": 1}}
            )
            sent_count += 1
            logger.info(f"Successfully drafted Day {days_overdue} WhatsApp message for invoice {invoice_id} (phone: {_mask_phone(contact_phone)})")
                
        except Exception as e:
            logger.error(f"Error processing invoice {invoice.get('_id')} for drip: {e}", exc_info=True)
            # Release our claim so the step can be retried on the next run
            if claimed and log_filter:
                try:
                    await drip_log_col.delete_one({**log_filter, "status": "processing"})
                except Exception:
                    logger.warning(f"Could not release drip claim for invoice {invoice.get('_id')}", exc_info=True)
            
    if sent_count > 0:
        logger.info(f"Finished drip processing for user {owner_id} - sent {sent_count} reminders")
    return sent_count


async def run_daily_drips(time_budget_seconds: Optional[float] = None) -> dict:
    """
    Main job that runs daily at midnight.
    Loops through all users and runs their drip campaigns.

    time_budget_seconds: stop starting new work after this long (serverless
    functions have a hard timeout). Unfinished steps are picked up on the next
    run thanks to the grace window and per-step idempotency.
    """
    deadline = time.monotonic() + time_budget_seconds if time_budget_seconds else None
    logger.info("Starting midnight Drip Campaign Engine...")
    
    # Unique (invoice, step) index makes the per-step claim race-safe.
    # Best effort: if legacy duplicate log rows exist the index can't be
    # built, and the claim falls back to the plain upsert check.
    try:
        await get_collection("drip_log").create_index(
            [("invoice_id", 1), ("days_overdue", 1)],
            unique=True,
            name="unique_drip_step",
        )
    except Exception as e:
        logger.warning(f"Could not ensure unique drip_log index: {e}")

    users_col = get_collection("users")
    cursor = users_col.find({"drip_settings": {"$exists": True}})
    
    users = [user async for user in cursor]

    drafted = 0
    stopped_early = False
    # Run 5 users concurrently to be safe
    chunk_size = 5
    for i in range(0, len(users), chunk_size):
        if deadline is not None and time.monotonic() > deadline:
            stopped_early = True
            break
        chunk = users[i:i + chunk_size]
        results = await asyncio.gather(
            *(process_drip_for_user(u, deadline) for u in chunk), return_exceptions=True
        )
        drafted += sum(r for r in results if isinstance(r, int))
    if deadline is not None and time.monotonic() > deadline:
        stopped_early = True

    logger.info("Completed midnight Drip Campaign Engine run.")
    return {"users": len(users), "drafted": drafted, "stopped_early": stopped_early}
