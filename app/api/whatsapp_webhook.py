"""
RecoverAI — WhatsApp Business API Webhook Handler

Routes
──────
GET  /api/webhooks/whatsapp   — Meta webhook verification (hub challenge)
POST /api/webhooks/whatsapp   — Inbound message receiver (HMAC-verified)
GET  /api/whatsapp/messages   — List all received WA messages (authenticated)
GET  /api/whatsapp/status     — Webhook connectivity status (authenticated)
POST /api/whatsapp/send       — Send an outbound WA message (authenticated)

How it works
────────────
1. Meta sends a GET to verify ownership → we echo hub.challenge.
2. Meta sends a POST for every inbound message → we verify the
   X-Hub-Signature-256 HMAC, parse the message payload, match the
   sender's phone number to an invoice in MongoDB, run the NLP pipeline
   (translate + classify), persist to `whatsapp_messages` collection,
   append to the invoice's communication_log, and optionally auto-reply.
3. We ALWAYS return HTTP 200 to Meta within 20 s — otherwise Meta retries.

Environment variables required
───────────────────────────────
WHATSAPP_VERIFY_TOKEN      — arbitrary secret you set when registering the webhook
WHATSAPP_WEBHOOK_SECRET    — HMAC secret Meta uses to sign POST bodies
WHATSAPP_PHONE_NUMBER_ID   — Meta phone number ID (from Developer Console)
WHATSAPP_ACCESS_TOKEN      — Meta System User permanent access token
"""

import hashlib
import hmac
import logging
import re
import time
from datetime import datetime, timezone

import httpx
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import get_collection
from app.services.nlp_service import process_debtor_reply
from app.services.whatsapp_service import _normalize_phone

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WhatsApp Webhook"])

# ── Collections ───────────────────────────────────────────────────────────────
WA_MESSAGES_COLLECTION = "whatsapp_messages"
INVOICES_COLLECTION = "invoices"


def _wa_access_token() -> str:
    """Meta access token — WHATSAPP_ACCESS_TOKEN, or the legacy WHATSAPP_API_TOKEN."""
    return settings.whatsapp_access_token or settings.whatsapp_api_token


# ── HMAC Verification ─────────────────────────────────────────────────────────

def _verify_whatsapp_signature(raw_body: bytes, signature_header: str) -> bool:
    """
    Verify the X-Hub-Signature-256 header from Meta.
    Returns True if the signature matches. Always returns False if
    WHATSAPP_WEBHOOK_SECRET is not configured (fail-closed).
    """
    secret = settings.whatsapp_webhook_secret
    if not secret:
        logger.error("SECURITY: WHATSAPP_WEBHOOK_SECRET not configured — rejecting webhook. Set this in .env.")
        return False

    expected_prefix = "sha256="
    if not signature_header.startswith(expected_prefix):
        return False

    received_sig = signature_header[len(expected_prefix):]
    computed = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, received_sig)


# ── Phone number normalisation ─────────────────────────────────────────────────

def _normalise_phone(raw: str) -> list[str]:
    """
    Generate candidate phone strings for matching against invoice.phone.
    WhatsApp sends numbers without spaces/dashes, prefixed with country code.
    e.g. "919876543210" → tries ["919876543210", "9876543210", "+919876543210", "+9876543210"]
    """
    digits = "".join(c for c in raw if c.isdigit())
    candidates = [digits]

    # Strip leading 91 (India country code)
    if digits.startswith("91") and len(digits) == 12:
        candidates.append(digits[2:])

    # Add + prefix variants
    candidates.extend([f"+{d}" for d in candidates[:]])
    return candidates


def _phone_regex(number: str) -> str:
    """
    Anchored regex matching exactly this phone number however the stored value is
    formatted ("98765 43210", "+91-98765-43210", "09876543210"). For Indian
    numbers the 91 country code / 0 trunk prefix is optional, mirroring
    _normalize_phone; every other number must match in full — a matching
    10-digit suffix from another country is not the same recipient.
    Built only from digits, so it is safe to use as a $regex.
    """
    digits = _normalize_phone(number)
    if not digits.isdigit():
        return r"(?!)"  # matches nothing
    sep = r"\D*"
    if len(digits) == 12 and digits.startswith("91"):
        return rf"^\D*(?:9{sep}1|0)?{sep}" + sep.join(digits[2:]) + r"\D*$"
    return r"^\D*" + sep.join(digits) + r"\D*$"


async def _find_invoice_by_phone(phone_candidates: list[str]) -> dict | None:
    """
    Find the most-recent non-recovered invoice whose phone matches any candidate.
    Uses a regex match to tolerate formatting differences.
    """
    col = get_collection(INVOICES_COLLECTION)
    for candidate in phone_candidates:
        # Build a regex that strips non-digits for comparison
        digits_only = "".join(c for c in candidate if c.isdigit())
        if len(digits_only) < 7:
            continue
        # Match the complete number, ignoring the stored phone's formatting
        pattern = _phone_regex(digits_only)
        doc = await col.find_one(
            {
                "phone": {"$regex": pattern},
                "recovered": {"$ne": True},
            },
            sort=[("_id", -1)],
        )
        if doc:
            return doc
    return None


# ── WhatsApp Cloud API — Send Message ──────────────────────────────────────────

async def _send_whatsapp_reply(to_number: str, text: str) -> bool:
    """
    Send a text message via WhatsApp Cloud API.
    Returns True on success, False on failure.
    Silently skips if WHATSAPP_PHONE_NUMBER_ID / WHATSAPP_ACCESS_TOKEN missing.
    """
    phone_number_id = settings.whatsapp_phone_number_id
    access_token = _wa_access_token()

    if not phone_number_id or not access_token:
        logger.info("WA send skipped — WHATSAPP_PHONE_NUMBER_ID / WHATSAPP_ACCESS_TOKEN not configured")
        return False

    url = f"https://graph.facebook.com/v20.0/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text},
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if resp.status_code == 200:
            logger.info("WA_SEND_OK | to=%s", to_number)
            return True
        logger.warning("WA_SEND_FAILED | to=%s | status=%d | body=%s", to_number, resp.status_code, resp.text[:200])
        return False
    except Exception as exc:
        logger.error("WA_SEND_ERROR | to=%s | error=%s", to_number, exc)
        return False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/api/webhooks/whatsapp",
    summary="Meta webhook ownership verification",
    response_class=PlainTextResponse,
    include_in_schema=False,
)
async def whatsapp_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """
    Meta calls this endpoint to confirm we own the webhook URL.
    We must respond with the raw hub.challenge string if the verify_token matches.
    """
    expected_token = settings.whatsapp_verify_token
    if not expected_token:
        logger.error("WHATSAPP_VERIFY_TOKEN not set — cannot complete Meta webhook verification")
        raise HTTPException(status_code=500, detail="Webhook verify token not configured.")

    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info("WA_WEBHOOK_VERIFIED | challenge=%s", hub_challenge)
        return PlainTextResponse(content=hub_challenge, status_code=200)

    logger.warning("WA_WEBHOOK_VERIFY_FAILED | mode=%s | token_match=%s", hub_mode, hub_verify_token == expected_token)
    raise HTTPException(status_code=403, detail="Webhook verification failed.")


@router.post(
    "/api/webhooks/whatsapp",
    summary="Receive inbound WhatsApp messages from Meta",
    include_in_schema=False,
)
async def whatsapp_receive(request: Request):
    """
    Processes all inbound WhatsApp messages from Meta Business Platform.

    Pipeline per message:
    1. Verify HMAC signature
    2. Parse Meta payload — extract phone + text
    3. Match phone to an active invoice in MongoDB
    4. Run NLP pipeline (translate → classify)
    5. Persist to whatsapp_messages collection
    6. Append to matched invoice's communication_log
    7. Optionally auto-reply via WhatsApp Cloud API
    8. Always return 200 — never let Meta retry
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not _verify_whatsapp_signature(raw_body, signature):
        logger.warning("WA_INVALID_SIGNATURE | sig=%s", signature[:40])
        # Return 200 anyway — Meta will stop sending if we return 403 repeatedly
        return {"status": "ignored", "reason": "invalid_signature"}

    try:
        payload = await request.json()
    except Exception:
        return {"status": "ignored", "reason": "invalid_json"}

    # Meta wraps everything in entry → changes → value → messages
    entries = payload.get("entry", [])
    wa_col = get_collection(WA_MESSAGES_COLLECTION)
    inv_col = get_collection(INVOICES_COLLECTION)

    processed = 0
    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            contacts = {c["wa_id"]: c.get("profile", {}).get("name", "") for c in value.get("contacts", [])}

            for msg in messages:
                if msg.get("type") != "text":
                    continue  # Skip non-text messages (images, audio, etc.) for now

                from_number = msg.get("from", "")
                wa_msg_id = msg.get("id", "")
                text_body = msg.get("text", {}).get("body", "").strip()
                sender_name = contacts.get(from_number, "")
                timestamp_unix = int(msg.get("timestamp", time.time()))
                timestamp_iso = datetime.fromtimestamp(timestamp_unix, tz=timezone.utc).isoformat()

                if not text_body:
                    continue

                logger.info("WA_INBOUND | from=%s | msg_id=%s | text=%s", from_number, wa_msg_id, text_body[:60])

                # ── Match phone → invoice ──────────────────────────────────
                phone_candidates = _normalise_phone(from_number)
                matched_invoice = await _find_invoice_by_phone(phone_candidates)
                invoice_id = str(matched_invoice["_id"]) if matched_invoice else None
                owner_id = matched_invoice.get("owner_id") if matched_invoice else None

                # ── Run NLP pipeline ──────────────────────────────────────
                try:
                    analysis = await process_debtor_reply(text_body)
                except Exception as exc:
                    logger.error("NLP_FAILED | wa_msg_id=%s | error=%s", wa_msg_id, exc)
                    analysis = {
                        "translated_text": text_body,
                        "intent": "unknown",
                        "confidence": "low",
                        "suggested_action": "Review message manually in Debtor Inbox.",
                        "fallback_mode": "error",
                    }

                # ── Persist to whatsapp_messages ──────────────────────────
                wa_doc = {
                    "wa_msg_id": wa_msg_id,
                    "from_number": from_number,
                    "sender_name": sender_name,
                    "raw_message": text_body,
                    "translated_text": analysis.get("translated_text", text_body),
                    "intent": analysis.get("intent", "unknown"),
                    "confidence": analysis.get("confidence", "low"),
                    "suggested_action": analysis.get("suggested_action", ""),
                    "fallback_mode": analysis.get("fallback_mode"),
                    "invoice_id": invoice_id,
                    "owner_id": owner_id,
                    "matched": bool(matched_invoice),
                    "timestamp": timestamp_iso,
                    "received_at": datetime.now(timezone.utc).isoformat(),
                    "replied": False,
                }
                await wa_col.insert_one(wa_doc)

                # ── Append to invoice communication_log ───────────────────
                if matched_invoice:
                    log_entry = {
                        "timestamp": timestamp_iso,
                        "direction": "inbound",
                        "source": "whatsapp_webhook",
                        "raw_message": text_body,
                        "translated_text": analysis.get("translated_text", text_body),
                        "intent": analysis.get("intent", "unknown"),
                        "confidence": analysis.get("confidence", "low"),
                        "suggested_action": analysis.get("suggested_action", ""),
                        "logged_by": f"whatsapp:{from_number}",
                        "wa_msg_id": wa_msg_id,
                    }
                    await inv_col.update_one(
                        {"_id": matched_invoice["_id"]},
                        {"$push": {"communication_log": log_entry}},
                    )
                    logger.info(
                        "WA_MATCHED | from=%s → invoice=%s | intent=%s",
                        from_number, invoice_id, analysis.get("intent"),
                    )
                else:
                    logger.warning("WA_UNMATCHED | from=%s — no active invoice found", from_number)

                # ── Optional Auto-Reply ────────────────────────────────────
                if matched_invoice and settings.whatsapp_auto_reply:
                    intent = analysis.get("intent", "unknown")
                    auto_replies = {
                        "promise_to_pay": (
                            f"Thank you for confirming! We have noted your commitment to pay "
                            f"₹{int(matched_invoice.get('amount') or 0):,} for invoice "
                            f"{matched_invoice.get('invoiceNo', '')}. "
                            f"We will follow up in 48 hours. — RecoverAI Collections"
                        ),
                        "dispute": (
                            f"We acknowledge your concern regarding invoice "
                            f"{matched_invoice.get('invoiceNo', '')}. "
                            f"Our team will review the details and get back to you shortly. "
                            f"— RecoverAI Collections"
                        ),
                        "stall": (
                            f"We understand you may need more time. However, this invoice is "
                            f"{matched_invoice.get('daysOverdue', 0)} days overdue. "
                            f"Please share a specific payment date at your earliest convenience. "
                            f"— RecoverAI Collections"
                        ),
                    }
                    reply_text = auto_replies.get(intent)
                    if reply_text:
                        sent = await _send_whatsapp_reply(from_number, reply_text)
                        if sent:
                            await wa_col.update_one(
                                {"wa_msg_id": wa_msg_id},
                                {"$set": {"replied": True, "auto_reply_text": reply_text}},
                            )

                processed += 1

    logger.info("WA_WEBHOOK_DONE | messages_processed=%d", processed)
    return {"status": "ok", "processed": processed}


# ── Authenticated Management Endpoints ────────────────────────────────────────

@router.get(
    "/api/whatsapp/messages",
    summary="List all received WhatsApp messages",
)
async def list_whatsapp_messages(
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    """
    Returns the latest WhatsApp messages scoped to the current user's invoices.
    Admin users see all messages platform-wide.
    """
    from app.core.config import settings as cfg
    wa_col = get_collection(WA_MESSAGES_COLLECTION)

    query = {}
    # Non-admins only see messages linked to their invoices
    if current_user.get("email") not in cfg.admin_emails_list:
        query["owner_id"] = current_user["_id"]

    cursor = wa_col.find(query).sort("received_at", -1).limit(limit)
    docs = await cursor.to_list(limit)
    for d in docs:
        d["id"] = str(d.pop("_id"))
        if "owner_id" in d:
            d["owner_id"] = str(d["owner_id"])
        if "invoice_id" in d and d["invoice_id"]:
            d["invoice_id"] = str(d["invoice_id"])
    return docs


@router.get(
    "/api/whatsapp/status",
    summary="WhatsApp webhook configuration status",
)
async def whatsapp_status(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Returns which WhatsApp settings are configured without exposing secrets."""
    return {
        "verify_token_set": bool(settings.whatsapp_verify_token),
        "webhook_secret_set": bool(settings.whatsapp_webhook_secret),
        "phone_number_id_set": bool(settings.whatsapp_phone_number_id),
        "access_token_set": bool(_wa_access_token()),
        "auto_reply_enabled": settings.whatsapp_auto_reply,
        "webhook_url_path": "/api/webhooks/whatsapp",
        "fully_configured": all([
            settings.whatsapp_verify_token,
            settings.whatsapp_phone_number_id,
            _wa_access_token(),
        ]),
    }


class SendMessageRequest(BaseModel):
    to_number: str
    message: str


@router.post(
    "/api/whatsapp/send",
    summary="Send an outbound WhatsApp message manually",
)
async def send_whatsapp_message(
    payload: SendMessageRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Manually send a WhatsApp text message to a phone number."""
    if not payload.to_number.strip() or not payload.message.strip():
        raise HTTPException(status_code=400, detail="to_number and message are required.")

    # International format with country code (WhatsApp can't deliver without one)
    clean_number = _normalize_phone(payload.to_number)

    # Verify the exact number belongs to one of the user's invoices
    inv_col = get_collection(INVOICES_COLLECTION)
    owner_query = {"phone": {"$regex": _phone_regex(clean_number)}}
    if current_user.get("email") not in settings.admin_emails_list:
        owner_query["owner_id"] = current_user.get("_id")
    matching_inv = await inv_col.find_one(owner_query)
    if not matching_inv:
        raise HTTPException(status_code=403, detail="Phone number not associated with any of your invoices.")

    success = await _send_whatsapp_reply(clean_number, payload.message)
    if not success:
        raise HTTPException(
            status_code=503,
            detail=(
                "WhatsApp send failed. Ensure WHATSAPP_PHONE_NUMBER_ID and "
                "WHATSAPP_ACCESS_TOKEN are configured correctly."
            ),
        )

    logger.info("WA_MANUAL_SEND | user=%s | to=%s", current_user.get("email"), clean_number)
    return {"status": "sent", "to": clean_number}
