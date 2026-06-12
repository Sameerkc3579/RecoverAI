import logging
import asyncio
from datetime import datetime, timezone
from app.core.database import get_collection
from app.services.email_service import send_reminder_email
from app.services.ai_service import generate_auto_reply
from bson import ObjectId

logger = logging.getLogger(__name__)

async def process_drip_for_user(user: dict):
    """Process drip campaigns for a single user."""
    owner_id = user["_id"]
    drip_settings = user.get("drip_settings", {})
    
    if not drip_settings:
        return
        
    invoices_col = get_collection("invoices")
    drip_log_col = get_collection("drip_log")
    
    # 1. Fetch all unresolved invoices with a due date
    cursor = invoices_col.find({
        "owner_id": owner_id,
        "recovered": False,
        "due_date": {"$exists": True, "$ne": None, "$ne": ""}
    })
    
    today = datetime.now(timezone.utc).date()
    
    sent_count = 0
    
    async for invoice in cursor:
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
                
            # Convert to string to match settings keys
            day_key = str(days_overdue)
            
            # Check if this exact day is configured as a drip step
            if day_key not in ["7", "21", "35", "45"]:
                continue
                
            step = drip_settings.get(day_key)
            if not step or not step.get("enabled"):
                continue
                
            invoice_id = invoice["_id"]
            
            # 2. Check idempotency (did we already send this specific day's drip?)
            already_sent = await drip_log_col.find_one({
                "invoice_id": invoice_id,
                "days_overdue": days_overdue,
                "status": "sent"
            })
            
            if already_sent:
                continue
                
            # We need to send a message.
            contact_email = invoice.get("email")
            if not contact_email:
                logger.warning(f"Skipping drip for invoice {invoice_id} (no email address)")
                continue
                
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
                "contact": invoice.get("contact", ""),
                "amount": invoice.get("amount"),
                "invoiceNo": invoice.get("invoice_no", ""),
                "dueDate": due_date_str,
                "daysOverdue": days_overdue
            }
            
            # Re-use the existing AI generator but spoof the incoming context
            message_body = await generate_auto_reply(
                incoming_text=f"Please generate a payment reminder for {inv_ctx['company']}. They are {days_overdue} days overdue.",
                invoice_data=inv_ctx,
                tone=tone
            )
            
            if not message_body:
                logger.error(f"Failed to generate AI message for invoice {invoice_id}")
                continue
                
            sender_business = user.get("settings", {}).get("businessName", "RecoverAI")
            
            # 5. Send Email
            success = await send_reminder_email(
                to_email=contact_email,
                debtor_company=invoice.get("company", "Valued Client"),
                invoice_no=invoice.get("invoice_no", "N/A"),
                amount=invoice.get("amount", 0.0),
                days_overdue=days_overdue,
                due_date=due_date_str,
                tone=tone,
                message_body=message_body,
                sender_business=sender_business
            )
            
            if success:
                # 6. Log success and increment reminder count
                await drip_log_col.insert_one({
                    "owner_id": owner_id,
                    "invoice_id": invoice_id,
                    "days_overdue": days_overdue,
                    "channel": "email",
                    "sent_at": datetime.now(timezone.utc),
                    "status": "sent"
                })
                
                await invoices_col.update_one(
                    {"_id": invoice_id},
                    {"$inc": {"reminders": 1}}
                )
                sent_count += 1
                logger.info(f"Successfully sent Day {days_overdue} drip for invoice {invoice_id}")
                
        except Exception as e:
            logger.error(f"Error processing invoice {invoice.get('_id')} for drip: {e}", exc_info=True)
            
    if sent_count > 0:
        logger.info(f"Finished drip processing for user {owner_id} - sent {sent_count} reminders")


async def run_daily_drips():
    """
    Main job that runs daily at midnight.
    Loops through all users and runs their drip campaigns.
    """
    logger.info("Starting midnight Drip Campaign Engine...")
    
    users_col = get_collection("users")
    cursor = users_col.find({"drip_settings": {"$exists": True}})
    
    tasks = []
    async for user in cursor:
        tasks.append(process_drip_for_user(user))
        
    if tasks:
        # Run 5 users concurrently to be safe
        chunk_size = 5
        for i in range(0, len(tasks), chunk_size):
            chunk = tasks[i:i + chunk_size]
            await asyncio.gather(*chunk, return_exceptions=True)
            
    logger.info("Completed midnight Drip Campaign Engine run.")
