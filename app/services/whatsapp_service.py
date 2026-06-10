"""
RecoverAI — Shared WhatsApp Cloud API Service.

Extracted from whatsapp_webhook.py so that both the webhook handler
AND the drip campaign scheduler can send WhatsApp messages without
circular imports.
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_whatsapp_message(to_number: str, text: str) -> bool:
    """
    Send a text message via WhatsApp Cloud API.

    Returns True on success, False on failure.
    Silently skips if WHATSAPP_PHONE_NUMBER_ID / WHATSAPP_ACCESS_TOKEN not configured.
    """
    phone_number_id = settings.whatsapp_phone_number_id
    access_token = settings.whatsapp_access_token

    if not phone_number_id or not access_token:
        logger.info(
            "WA send skipped — WHATSAPP_PHONE_NUMBER_ID / WHATSAPP_ACCESS_TOKEN not configured"
        )
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
        logger.warning(
            "WA_SEND_FAILED | to=%s | status=%d | body=%s",
            to_number,
            resp.status_code,
            resp.text[:200],
        )
        return False
    except Exception as exc:
        logger.error("WA_SEND_ERROR | to=%s | error=%s", to_number, exc)
        return False
