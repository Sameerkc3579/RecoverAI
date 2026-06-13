import logging
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

async def send_whatsapp_message(to_phone: str, message_text: str) -> bool:
    """
    Sends a WhatsApp message via the official Meta Cloud API.
    """
    if not settings.WHATSAPP_API_TOKEN or not settings.WHATSAPP_PHONE_NUMBER_ID:
        logger.error("WhatsApp credentials are not configured in environment variables.")
        return False

    url = f"https://graph.facebook.com/v20.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_API_TOKEN}",
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
                logger.info(f"Successfully sent WhatsApp message to {to_phone}")
                return True
            else:
                logger.error(f"Failed to send WhatsApp message. Status: {response.status_code}, Response: {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"Exception while sending WhatsApp message to {to_phone}: {e}")
        return False
