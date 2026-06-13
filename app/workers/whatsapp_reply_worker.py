import logging
from datetime import datetime, timezone
from app.core.database import get_collection
from app.services.ai_service import generate_message

logger = logging.getLogger(__name__)

async def process_incoming_whatsapp(from_phone: str, message_body: str, debtor_invoice: dict):
    """
    Background worker to process incoming WhatsApp messages from debtors.
    Extracts intent using Gemini and saves a DRAFT reply in the database.
    """
    logger.info(f"Processing incoming WhatsApp message from {from_phone}: {message_body}")
    
    # Context for the AI
    invoice_context = {
        "company": debtor_invoice.get("company", "Unknown"),
        "amount": debtor_invoice.get("amount", "Unknown"),
        "contact": debtor_invoice.get("contact", from_phone),
        "status": debtor_invoice.get("status", "pending"),
        "invoice_no": debtor_invoice.get("invoice_no", "Unknown")
    }

    prompt = f"""
    You are an AI recovery agent representing our company.
    We just received this WhatsApp message from the debtor ({invoice_context['contact']}) regarding Invoice {invoice_context['invoice_no']} (Amount: {invoice_context['amount']}).
    
    Debtor's Message: "{message_body}"
    
    Instructions:
    1. Read the debtor's message and understand their intent (e.g., they paid, they are asking for time, they are making an excuse).
    2. Draft a polite, concise, and professional WhatsApp reply. 
    3. If they are asking for a few days extension, politely agree but mention this is the final extension.
    4. If they claim they paid, ask for the UTR or transaction ID so we can verify.
    
    Return ONLY the drafted WhatsApp message, no extra conversational text.
    """
    
    try:
        # Generate the reply using Gemini
        draft_reply = await generate_message(prompt=prompt, invoice_data=invoice_context, tone="friendly")
        
        # Draft Mode: Save to a new collection instead of sending
        drafts_col = await get_collection("whatsapp_drafts")
        await drafts_col.insert_one({
            "invoice_id": debtor_invoice["_id"],
            "contact_phone": from_phone,
            "incoming_message": message_body,
            "draft_reply": draft_reply,
            "status": "pending_approval",
            "created_at": datetime.now(timezone.utc)
        })
        
        logger.info(f"Successfully drafted AI reply for {from_phone} and saved for manual approval.")
        
    except Exception as e:
        logger.error(f"Failed to generate or save WhatsApp draft reply for {from_phone}: {e}")
