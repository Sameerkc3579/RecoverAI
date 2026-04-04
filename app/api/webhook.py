"""
RecoveryAgent — Webhook router for incoming debtor replies.

Provides POST /api/debtor-reply which:
1. Accepts the raw message + invoice_id
2. Runs the NLP pipeline (translate → classify)
3. Pushes a communication_log entry onto the invoice document in MongoDB
4. Returns the NLP analysis to the caller
"""
import logging
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.database import get_collection
from app.services.nlp_service import process_debtor_reply

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Webhook"])


# ── Request / Response schemas ────────────────────────────────────────────────

class DebtorReplyRequest(BaseModel):
    """Incoming debtor reply payload."""
    invoice_id: str = Field(..., description="MongoDB ObjectId of the related invoice")
    message: str = Field(..., min_length=1, max_length=2000, description="Raw debtor reply text")


class DebtorReplyResponse(BaseModel):
    """NLP analysis result + DB confirmation."""
    invoice_id: str
    original_message: str
    translated_text: str
    intent: str
    confidence: str
    suggested_action: str
    db_updated: bool


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post(
    "/debtor-reply",
    response_model=DebtorReplyResponse,
    summary="Process an incoming debtor reply",
    description=(
        "Accepts a raw message from a debtor, translates it to English, "
        "classifies the intent, and appends the result to the invoice's "
        "communication_log in MongoDB."
    ),
)
async def handle_debtor_reply(payload: DebtorReplyRequest):
    """Run the NLP pipeline and update the invoice communication log."""
    invoice_id = payload.invoice_id
    raw_message = payload.message

    # Validate that the invoice exists
    coll = get_collection("invoices")
    try:
        oid = ObjectId(invoice_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid invoice_id format")

    existing = await coll.find_one({"_id": oid})
    if not existing:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")

    # Run the NLP pipeline
    try:
        analysis = await process_debtor_reply(raw_message)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    # Build the communication log entry
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "direction": "inbound",
        "raw_message": raw_message,
        "translated_text": analysis["translated_text"],
        "intent": analysis["intent"],
        "confidence": analysis["confidence"],
        "suggested_action": analysis["suggested_action"],
    }

    # Push to the invoice's communication_log array
    result = await coll.update_one(
        {"_id": oid},
        {"$push": {"communication_log": log_entry}},
    )
    db_updated = result.modified_count == 1

    if db_updated:
        logger.info("Updated invoice %s — intent=%s", invoice_id, analysis["intent"])
    else:
        logger.warning("Invoice %s found but communication_log update failed", invoice_id)

    return DebtorReplyResponse(
        invoice_id=invoice_id,
        original_message=raw_message,
        translated_text=analysis["translated_text"],
        intent=analysis["intent"],
        confidence=analysis["confidence"],
        suggested_action=analysis["suggested_action"],
        db_updated=db_updated,
    )
