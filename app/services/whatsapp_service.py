import re
import logging
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)


def _mask_phone(phone: str) -> str:
    """Mask phone number for safe logging (GDPR/CCPA compliant). e.g. 919876543210 -> 91****3210"""
    if not phone or len(phone) < 6:
        return "***"
    return f"{phone[:2]}****{phone[-4:]}"


def _normalize_phone(phone: str) -> str:
    """
    Normalise to WhatsApp's international format (digits, with country code).
    Strips formatting, then adds India's 91 to bare 10-digit numbers and to
    0-prefixed trunk numbers — WhatsApp cannot deliver without a country code.
      "+91 98765-43210" -> "919876543210"   "9876543210" -> "919876543210"
      "09876543210"     -> "919876543210"   "+1 (415) 555-0100" -> "14155550100"
    """
    digits = re.sub(r"[\s\-().+]", "", phone or "")
    if digits.isdigit():
        if len(digits) == 10:
            return "91" + digits
        if len(digits) == 11 and digits.startswith("0"):
            return "91" + digits[1:]
    return digits


def _validate_phone(phone: str) -> bool:
    """Basic phone number validation: digits only, 7-15 chars (E.164 without +)."""
    return bool(re.match(r"^\d{7,15}$", phone.strip()))


async def send_whatsapp_message(to_phone: str, message_text: str) -> bool:
    """
    Sends a WhatsApp message via the official Meta Cloud API.
    """
    access_token = settings.whatsapp_access_token or settings.whatsapp_api_token
    if not access_token or not settings.whatsapp_phone_number_id:
        logger.error("WhatsApp credentials are not configured in environment variables.")
        return False

    to_phone = _normalize_phone(to_phone)
    if not _validate_phone(to_phone):
        logger.error(f"Invalid phone number format for recipient {_mask_phone(to_phone)}")
        return False

    url = f"https://graph.facebook.com/v20.0/{settings.whatsapp_phone_number_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {
            "body": message_text
        }
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=10.0)
            
            if response.status_code in (200, 201):
                logger.info(f"Successfully sent WhatsApp message to {_mask_phone(to_phone)}")
                return True
            else:
                logger.error(f"Failed to send WhatsApp message to {_mask_phone(to_phone)}. Status: {response.status_code}")
                return False
                
    except Exception as e:
        logger.error(f"Exception while sending WhatsApp message to {_mask_phone(to_phone)}: {e}")
        return False
