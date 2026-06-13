import hmac
import hashlib
import logging
from fastapi import APIRouter, Request, HTTPException, Query, BackgroundTasks
from app.core.config import settings
from app.core.database import get_collection
from app.workers.whatsapp_reply_worker import process_incoming_whatsapp
from app.services.whatsapp_service import _validate_phone, _mask_phone

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])


def _verify_signature(payload_bytes: bytes, signature_header: str | None) -> bool:
    """
    Verify the X-Hub-Signature-256 HMAC sent by Meta.
    Returns True if signature is valid, or if no webhook secret is configured
    (fail-closed in production, logged warning in dev).
    """
    secret = getattr(settings, "WHATSAPP_WEBHOOK_SECRET", "") or getattr(settings, "webhook_secret", "")
    
    if not secret:
        if settings.debug:
            logger.warning("SECURITY: No WHATSAPP_WEBHOOK_SECRET configured — accepting unverified webhook (dev mode only)")
            return True
        else:
            logger.error("SECURITY: No WHATSAPP_WEBHOOK_SECRET configured — rejecting webhook in production")
            return False

    if not signature_header or not signature_header.startswith("sha256="):
        logger.warning("SECURITY: Missing or malformed X-Hub-Signature-256 header")
        return False

    expected_sig = signature_header[7:]  # Strip "sha256=" prefix
    computed_sig = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed_sig, expected_sig)


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
    Verifies HMAC signature before processing.
    """
    # 0. HMAC Signature Verification — reject forged payloads
    payload_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    
    if not _verify_signature(payload_bytes, signature):
        logger.warning("SECURITY: Rejected webhook with invalid HMAC signature")
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    import json
    payload = json.loads(payload_bytes)
    
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
        
        # Validate phone number format
        if not from_phone or not _validate_phone(from_phone):
            logger.warning("Invalid or missing phone number in webhook payload")
            return {"status": "dropped", "reason": "Invalid phone format"}
        
        logger.info(f"Received WhatsApp message from {_mask_phone(from_phone)}")
        
    except (IndexError, AttributeError) as e:
        logger.error(f"Failed to parse WhatsApp webhook payload: {e}")
        return {"status": "error", "detail": "Invalid payload format"}

    # 2. PRIVACY FILTER: Only process messages from known debtors in the database
    invoices_col = get_collection("invoices")
    
    # Use exact match instead of regex to prevent ReDoS attacks
    debtor_invoice = await invoices_col.find_one({"contact": from_phone})
    
    if not debtor_invoice:
        logger.info(f"Privacy Filter: Dropped message from non-debtor {_mask_phone(from_phone)}")
        return {"status": "dropped", "reason": "Sender is not a known debtor"}

    # 3. Pass to background worker for processing (Draft generation)
    logger.info(f"Known debtor recognized (Invoice ID: {debtor_invoice['_id']}). Offloading to AI worker.")
    background_tasks.add_task(process_incoming_whatsapp, from_phone, message_body, debtor_invoice)
    
    # Always return 200 OK immediately so Meta knows we received it
    return {"status": "received"}
