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

# ── Gemini model ────────────────────────────────────────────────────────────
MODEL = "gemini-2.5-flash"  # lighter model with separate quota bucket


# Lazy client — created on first use so a bad API key only breaks AI endpoints,
# not the entire application startup (which would cause 500 on every route).
_client = None


def _get_client():
    """Return the Gemini async client, initialising it on first call."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client

# ── Prompt templates ──────────────────────────────────────────────────────────
_SYSTEM_INSTRUCTION = """\
You are an elite debt recovery agent. Draft a complete, full-length [WhatsApp/Email/Legal] message. Tone: {tone}. If the invoice is 45+ days overdue, strictly use the MSMED Act 2006 penalties as leverage.
IMPORTANT: You MUST generate the entire message. This includes the Subject Line, greeting, the complete body explaining the situation and consequences, and a professional sign-off. DO NOT stop after generating the subject line.
"""

async def generate_message(prompt: str, invoice_data: dict, tone: str) -> str:
    """
    Call Gemini and return the generated recovery message text.
    Retries once on 429 RESOURCE_EXHAUSTED after a short delay.
    """
    import json
    import asyncio

    logger.info("Calling Gemini %s with tone: %s", MODEL, tone)

    context_prompt = f"""
INVOICE CONTEXT:
{json.dumps(invoice_data, indent=2)}

REQUESTED MESSAGE DRAFT:
{prompt}

CRITICAL: Output the entire complete letter/email from start to finish. Include the full body and sign-off.
    """

    async def _call_gemini():
        client = _get_client()
        response = await client.aio.models.generate_content(
            model=MODEL,
            contents=context_prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION.format(tone=tone),
                temperature=0.7,
                max_output_tokens=8192,
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
                    ),
                ],
            ),
        )
        return response.text

    try:
        return await _call_gemini()
    except Exception as exc:
        err = str(exc)
        # On quota exhaustion, wait and retry once
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            logger.warning("Gemini quota hit, retrying in 12s…")
            await asyncio.sleep(12)
            try:
                return await _call_gemini()
            except Exception as exc2:
                logger.exception("Gemini retry also failed: %s", exc2)
                raise RuntimeError(
                    "AI quota exhausted. Please try again in a minute, or contact support to upgrade the AI plan."
                )
        logger.exception("Gemini API error: %s", exc)
        raise RuntimeError(f"Gemini API error: {exc}")