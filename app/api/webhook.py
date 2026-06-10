"""
RecoverAI — Webhook Router (Security-Hardened)

POST /api/debtor-reply — Process an incoming debtor reply

Security Fix:
  - Now requires JWT authentication (was previously completely open/unauthenticated)
  - Owner-scoped: users can only post replies to their own invoices
  - No anonymous actor can write to any invoice's communication log
"""
import logging
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.core.database import get_collection
from app.services.nlp_service import process_debtor_reply
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Webhook"])


# ── Request / Response Schemas ────────────────────────────────────────────────

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
    summary="Process an incoming debtor reply (authenticated)",
    description=(
        "Accepts a raw message from a debtor, translates it to English, "
        "classifies the intent, and appends the result to the invoice's "
        "communication_log in MongoDB. Requires authentication — only the "
        "invoice owner can post replies to their own invoices."
    ),
)
async def handle_debtor_reply(
    payload: DebtorReplyRequest,
    current_user: dict = Depends(get_current_user),  # SECURITY: authentication required
):
    """Run the NLP pipeline and update the invoice communication log."""
    invoice_id = payload.invoice_id
    raw_message = payload.message

    coll = get_collection("invoices")
    try:
        oid = ObjectId(invoice_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid invoice_id format.")

    # Owner-scoped lookup — user can only interact with their own invoices
    existing = await coll.find_one({"_id": oid, "owner_id": current_user["_id"]})
    if not existing:
        # Return 404 in both "not found" and "not yours" cases — no ownership leakage
        raise HTTPException(status_code=404, detail="Invoice not found.")

    # Run the NLP pipeline.
    # Note: process_debtor_reply never raises — on internal failure it returns
    # a dict with fallback_mode: "error" instead, so no try/except is needed here.
    analysis = await process_debtor_reply(raw_message)

    # Build the communication log entry
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "direction": "inbound",
        "raw_message": raw_message,
        "translated_text": analysis["translated_text"],
        "intent": analysis["intent"],
        "confidence": analysis["confidence"],
        "suggested_action": analysis["suggested_action"],
        "logged_by": current_user.get("email"),
    }

    # Push to the invoice's communication_log array (owner-scoped)
    result = await coll.update_one(
        {"_id": oid, "owner_id": current_user["_id"]},
        {"$push": {"communication_log": log_entry}},
    )
    db_updated = result.modified_count == 1

    logger.info(
        "DEBTOR_REPLY_LOGGED | invoice=%s | intent=%s | user=%s",
        invoice_id, analysis["intent"], current_user.get("email"),
    )

    return DebtorReplyResponse(
        invoice_id=invoice_id,
        original_message=raw_message,
        translated_text=analysis["translated_text"],
        intent=analysis["intent"],
        confidence=analysis["confidence"],
        suggested_action=analysis["suggested_action"],
        db_updated=db_updated,
    )
