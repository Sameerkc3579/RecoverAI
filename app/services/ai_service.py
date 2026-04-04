"""
RecoveryAgent — Gemini AI service for recovery message generation.

Capabilities
────────────
• WhatsApp messages  — concise, friendly, persuasive
• Formal emails      — structured, professional
• Legal notices      — MSMED Act 2006 compliant (Sections 15-17)

Language policy
───────────────
The model is explicitly instructed to support mixed English + structured Hindi
so MSME debtors who communicate in regional dialects receive culturally
appropriate responses.
"""
import logging

from google import genai
from google.genai import types

from app.core.config import settings
from app.models.schemas import PromptRequest

logger = logging.getLogger(__name__)

# ── Gemini async client ───────────────────────────────────────────────────────
_client = genai.Client(api_key=settings.gemini_api_key)
MODEL = "gemini-2.5-flash"

# ── Prompt templates ──────────────────────────────────────────────────────────
_SYSTEM_INSTRUCTION = """\
You are an elite debt recovery agent. Draft a complete, full-length [WhatsApp/Email/Legal] message. Tone: {tone}. If the invoice is 45+ days overdue, strictly use the MSMED Act 2006 penalties as leverage.
IMPORTANT: You MUST generate the entire message. This includes the Subject Line, greeting, the complete body explaining the situation and consequences, and a professional sign-off. DO NOT stop after generating the subject line.
"""

async def generate_message(prompt: str, invoice_data: dict, tone: str) -> str:
    """
    Call Gemini and return the generated recovery message text.
    """
    import json
    
    logger.info("Calling Gemini %s with dynamic UI prompt and tone: %s", MODEL, tone)
    
    # Inject MSMED Act penalty and invoice context
    context_prompt = f"""
INVOICE CONTEXT:
{json.dumps(invoice_data, indent=2)}

REQUESTED MESSAGE DRAFT:
{prompt}

CRITICAL: Output the entire complete letter/email from start to finish. Include the full body and sign-off.
    """
    
    try:
        response = await _client.aio.models.generate_content(
            model=MODEL,
            contents=context_prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION.format(tone=tone),
                temperature=0.7,
                max_output_tokens=8192,  # Large enough for full legal emails
                thinking_config=types.ThinkingConfig(thinking_budget=0),  # Disable thinking to prevent token budget waste
                # ⚡ NUCLEAR OPTION: TURN ALL HR SHIELDS OFF
                safety_settings=[
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    )
                ]
            ),
        )
        
        return response.text
    except Exception as exc:
        logger.exception("Gemini API error: %s", exc)
        raise RuntimeError(f"Gemini API error: {exc}")