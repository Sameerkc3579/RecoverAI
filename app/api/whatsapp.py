import logging
from fastapi import APIRouter, Request, HTTPException, Query, BackgroundTasks
from app.core.config import settings
from app.core.database import get_collection
from app.workers.whatsapp_reply_worker import process_incoming_whatsapp

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])

@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """
    Meta Webhook Verification Endpoint.
    Meta will send a GET request here to verify ownership of the webhook URL.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp Webhook verified successfully!")
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Invalid verification token")

@router.post("/webhook")
async def handle_incoming_message(request: Request, background_tasks: BackgroundTasks):
    """
    Meta incoming message webhook.
    Receives all incoming WhatsApp messages sent to the Business Number.
    """
    payload = await request.json()
    
    # 1. Parse the standard WhatsApp Cloud API payload structure
    try:
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            return {"status": "ignored", "reason": "No messages in payload"}
            
        message = messages[0]
        from_phone = message.get("from")
        message_body = message.get("text", {}).get("body", "")
        
        logger.info(f"Received WhatsApp message from {from_phone}")
        
    except (IndexError, AttributeError) as e:
        logger.error(f"Failed to parse WhatsApp webhook payload: {e}")
        return {"status": "error", "detail": "Invalid payload format"}

    # 2. PRIVACY FILTER: Only process messages from known debtors in the database
    invoices_col = await get_collection("invoices")
    
    # Standardize phone number for lookup (strip +, spaces, etc if needed, but WhatsApp sends just digits e.g. 15551234567)
    # Search the database for any invoice matching this contact's phone number
    debtor_invoice = await invoices_col.find_one({"contact": {"$regex": from_phone, "$options": "i"}})
    
    if not debtor_invoice:
        logger.warning(f"Privacy Filter Triggered: Dropped message from unknown number {from_phone}")
        return {"status": "dropped", "reason": "Sender is not a known debtor"}

    # 3. Pass to background worker for processing (Draft generation)
    logger.info(f"Known debtor recognized (Invoice ID: {debtor_invoice['_id']}). Offloading to AI worker.")
    background_tasks.add_task(process_incoming_whatsapp, from_phone, message_body, debtor_invoice)
    
    # Always return 200 OK immediately so Meta knows we received it
    return {"status": "received"}
