"""
RecoverAI — Automated Drip Campaign Scheduler

Runs a background CRON job at midnight IST every day.
For each user with drip settings enabled, it:
  1. Queries all unpaid invoices (recovered = False)
  2. Dynamically calculates daysOverdue
  3. Matches against configured drip triggers (Day 7, 21, 35, 45)
  4. Generates an AI-crafted WhatsApp message via Gemini
  5. Sends it via the WhatsApp Cloud API
  6. Logs the event to MongoDB

Architecture
────────────
Uses APScheduler's AsyncIOScheduler which runs inside the FastAPI event loop,
so no external process manager, Redis, or Celery is required.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from math import floor

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import settings
from app.core.database import get_collection
from app.services.ai_service import generate_message
from app.services.whatsapp_service import send_whatsapp_message

logger = logging.getLogger(__name__)

# ── Scheduler instance ────────────────────────────────────────────────────────
_scheduler: AsyncIOScheduler | None = None

# ── Drip step definitions ─────────────────────────────────────────────────────
DRIP_STEPS = {
    7:  {"key": "day_7",  "tone": "Friendly Reminder",   "label": "First Gentle Reminder"},
    21: {"key": "day_21", "tone": "Firm Warning",         "label": "Firm Follow-up"},
    35: {"key": "day_35", "tone": "Final Warning",        "label": "Final Warning"},
    45: {"key": "day_45", "tone": "Legal Notice",         "label": "Auto Legal Notice"},
}

# Default drip settings — all steps enabled
_DEFAULT_DRIP = {
    "day_7":  {"enabled": True},
    "day_21": {"enabled": True},
    "day_35": {"enabled": True},
    "day_45": {"enabled": True},
}


def _calculate_days_overdue(due_date_str: str) -> int:
    """Calculate days overdue from a due date string (YYYY-MM-DD or ISO format)."""
    try:
        # Handle both 'YYYY-MM-DD' and full ISO timestamps
        due = datetime.fromisoformat(due_date_str.replace("Z", "+00:00"))
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - due
        return max(0, floor(delta.total_seconds() / 86400))
    except (ValueError, AttributeError):
        return 0


def _build_prompt(invoice: dict, step_label: str, days_overdue: int) -> str:
    """Build the AI prompt for a drip message."""
    return (
        f"Draft a {step_label} WhatsApp message for the following overdue invoice.\n"
        f"The invoice is {days_overdue} days overdue.\n"
        f"Company: {invoice.get('company', 'Unknown')}\n"
        f"Invoice #: {invoice.get('invoiceNo', invoice.get('invoice_no', 'N/A'))}\n"
        f"Amount: ₹{invoice.get('amount', 0):,.0f}\n"
        f"Due Date: {invoice.get('dueDate', invoice.get('due_date', 'N/A'))}\n\n"
        "Keep it concise for WhatsApp (under 500 characters). "
        "If overdue 45+ days, cite MSMED Act 2006 penalties."
    )


async def _process_single_drip(
    user: dict,
    invoice: dict,
    days_overdue: int,
    step_config: dict,
) -> bool:
    """
    Process a single drip event: generate message → send → log.
    Returns True if the message was sent successfully.
    """
    step = DRIP_STEPS[days_overdue]
    phone = (invoice.get("phone") or "").strip()
    if not phone:
        logger.debug(
            "DRIP_SKIP_NO_PHONE | user=%s | invoice=%s",
            user.get("email", "?"),
            invoice.get("invoiceNo", "?"),
        )
        return False

    # Clean phone number — digits only, ensure country code
    clean_phone = "".join(c for c in phone if c.isdigit())
    if len(clean_phone) == 10:
        clean_phone = "91" + clean_phone  # Default to India

    # Build invoice context dict for the AI
    invoice_data = {
        "company": invoice.get("company", ""),
        "contact": invoice.get("contact", ""),
        "invoiceNo": invoice.get("invoiceNo", invoice.get("invoice_no", "")),
        "amount": invoice.get("amount", 0),
        "dueDate": invoice.get("dueDate", invoice.get("due_date", "")),
        "daysOverdue": days_overdue,
        "status": invoice.get("status", ""),
    }

    prompt = _build_prompt(invoice, step["label"], days_overdue)

    # Generate the AI message
    try:
        message_text = await generate_message(prompt, invoice_data, step["tone"])
    except Exception as exc:
        logger.error(
            "DRIP_AI_ERROR | user=%s | invoice=%s | error=%s",
            user.get("email", "?"),
            invoice.get("invoiceNo", "?"),
            exc,
        )
        return False

    if not message_text:
        logger.warning(
            "DRIP_AI_EMPTY | user=%s | invoice=%s",
            user.get("email", "?"),
            invoice.get("invoiceNo", "?"),
        )
        return False

    # Send via WhatsApp
    sent = await send_whatsapp_message(clean_phone, message_text)

    # Log the drip event to the drip_log collection
    drip_log_entry = {
        "user_id": str(user["_id"]),
        "user_email": user.get("email", ""),
        "invoice_id": str(invoice["_id"]),
        "invoice_no": invoice.get("invoiceNo", invoice.get("invoice_no", "")),
        "company": invoice.get("company", ""),
        "phone": clean_phone,
        "days_overdue": days_overdue,
        "drip_step": step["label"],
        "message": message_text[:500],
        "sent": sent,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        drip_col = get_collection("drip_log")
        await drip_col.insert_one(drip_log_entry)
    except Exception as exc:
        logger.error("DRIP_LOG_ERROR | %s", exc)

    # Append to the invoice's communication_log
    if sent:
        comm_entry = {
            "type": "drip_whatsapp",
            "direction": "outbound",
            "step": step["label"],
            "message": message_text[:300],
            "phone": clean_phone,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "auto": True,
        }
        try:
            inv_col = get_collection("invoices")
            await inv_col.update_one(
                {"_id": invoice["_id"]},
                {"$push": {"communication_log": comm_entry}},
            )
        except Exception as exc:
            logger.error("DRIP_COMM_LOG_ERROR | %s", exc)

    logger.info(
        "DRIP_%s | user=%s | invoice=%s | company=%s | day=%d | sent=%s",
        "SENT" if sent else "FAILED",
        user.get("email", "?"),
        invoice.get("invoiceNo", "?"),
        invoice.get("company", "?"),
        days_overdue,
        sent,
    )
    return sent


async def run_daily_drips() -> dict:
    """
    Main drip campaign runner — called by the scheduler at midnight IST.

    Returns a summary dict with counts for logging/debugging.
    """
    logger.info("═══ DRIP_SCHEDULER_START | Running daily drip campaign check ═══")
    start_time = datetime.now(timezone.utc)

    stats = {"users_checked": 0, "invoices_checked": 0, "drips_sent": 0, "drips_failed": 0, "drips_skipped": 0}

    try:
        users_col = get_collection("users")
        inv_col = get_collection("invoices")

        # Get all users (we check their drip settings individually)
        users_cursor = users_col.find({"is_active": {"$ne": False}})
        users = await users_cursor.to_list(length=10000)

        for user in users:
            stats["users_checked"] += 1
            user_id = user["_id"]
            drip_settings = user.get("drip_settings", _DEFAULT_DRIP)

            # Get all unpaid invoices for this user
            invoices_cursor = inv_col.find({
                "owner_id": str(user_id),
                "recovered": {"$ne": True},
            })
            invoices = await invoices_cursor.to_list(length=5000)

            for invoice in invoices:
                stats["invoices_checked"] += 1
                due_date = invoice.get("dueDate") or invoice.get("due_date") or ""
                if not due_date:
                    continue

                days_overdue = _calculate_days_overdue(due_date)

                # Check if this matches any drip trigger day
                if days_overdue not in DRIP_STEPS:
                    continue

                step = DRIP_STEPS[days_overdue]
                step_settings = drip_settings.get(step["key"], {"enabled": True})

                if not step_settings.get("enabled", True):
                    stats["drips_skipped"] += 1
                    continue

                # Check if we already sent a drip for this invoice at this step today
                drip_col = get_collection("drip_log")
                today_start = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ).isoformat()
                already_sent = await drip_col.find_one({
                    "invoice_id": str(invoice["_id"]),
                    "drip_step": step["label"],
                    "timestamp": {"$gte": today_start},
                })
                if already_sent:
                    stats["drips_skipped"] += 1
                    continue

                # Fire the drip
                sent = await _process_single_drip(user, invoice, days_overdue, step_settings)
                if sent:
                    stats["drips_sent"] += 1
                else:
                    stats["drips_failed"] += 1

                # Small delay between sends to avoid WhatsApp rate limits
                await asyncio.sleep(1.5)

    except Exception as exc:
        logger.exception("DRIP_SCHEDULER_CRITICAL_ERROR | %s", exc)

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
    logger.info(
        "═══ DRIP_SCHEDULER_DONE | elapsed=%.1fs | users=%d | invoices=%d | sent=%d | failed=%d | skipped=%d ═══",
        elapsed,
        stats["users_checked"],
        stats["invoices_checked"],
        stats["drips_sent"],
        stats["drips_failed"],
        stats["drips_skipped"],
    )
    return stats


# ── Scheduler Lifecycle ───────────────────────────────────────────────────────

def start_scheduler() -> None:
    """
    Initialise and start the APScheduler AsyncIOScheduler.

    Schedules `run_daily_drips` to fire at midnight IST (00:00 Asia/Kolkata).
    Uses a misfire grace time of 1 hour — if the server was down at midnight,
    the job will still run when it comes back online within the hour.
    """
    global _scheduler

    if _scheduler is not None:
        logger.warning("DRIP_SCHEDULER | Scheduler already running — skipping start")
        return

    _scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
    _scheduler.add_job(
        run_daily_drips,
        trigger=CronTrigger(hour=0, minute=0, timezone="Asia/Kolkata"),
        id="daily_drip_campaign",
        name="Daily Drip Campaign Runner",
        replace_existing=True,
        misfire_grace_time=3600,  # 1 hour grace period
    )
    _scheduler.start()
    logger.info("✅  DRIP_SCHEDULER | Started — next run at midnight IST")


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("🛑  DRIP_SCHEDULER | Stopped")
