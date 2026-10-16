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
# Model cascade: fastest/newest → stable mid-tier → legacy stable
MODEL           = "gemini-2.5-flash"    # primary — fast & cheap
FALLBACK_MODEL  = "gemini-3.5-flash-lite"  # second tier — separate quota from MODEL
                                         # (gemini-2.0-flash was retired by Google)
LEGACY_MODEL    = "gemini-flash-latest"   # last resort: alias that tracks the current Flash

# Retry backoff (kept short — serverless functions have tight wall-clock limits)
_RETRY_DELAY_1 = 1   # seconds, before first retry of MODEL
_RETRY_DELAY_2 = 2   # seconds, before switching to FALLBACK_MODEL


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

# ── Transient error check ────────────────────────────────────────────────────
_TRANSIENT_SIGNALS = ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "overloaded", "empty response")

def _is_transient(err: str) -> bool:
    return any(sig in err for sig in _TRANSIENT_SIGNALS)


def _build_config(tone: str) -> types.GenerateContentConfig:
    """Shared GenerateContentConfig to avoid repetition."""
    return types.GenerateContentConfig(
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
    )


async def generate_message(prompt: str, invoice_data: dict, tone: str) -> str:
    """
    Call Gemini and return the generated recovery message text.

    Strategy
    ────────
    1. Try MODEL (gemini-2.5-flash) immediately.
    2. On transient error: short wait, retry MODEL.
    3. On second transient error: short wait, try FALLBACK_MODEL (gemini-3.5-flash-lite).
    4. On third transient error: try LEGACY_MODEL (gemini-flash-latest) immediately.
    5. Raise a user-friendly error if all attempts fail.
    """
    import json
    import asyncio

    logger.info("Calling Gemini %s | tone: %s", MODEL, tone)

    context_prompt = (
        f"INVOICE CONTEXT:\n{json.dumps(invoice_data, indent=2)}\n\n"
        f"REQUESTED MESSAGE DRAFT:\n{prompt}\n\n"
        "CRITICAL: Output the entire complete letter/email from start to finish. "
        "Include the full body and sign-off."
    )

    async def _call(model: str) -> str:
        client = _get_client()
        response = await client.aio.models.generate_content(
            model=model,
            contents=context_prompt,
            config=_build_config(tone),
        )
        text = response.text
        if not text:
            # response.text is None/empty when Gemini returns no candidates
            # (e.g. a safety block) — treat as a transient failure so the
            # caller retries/falls back instead of returning null to the client.
            raise RuntimeError(f"Gemini ({model}) returned an empty response (possible safety block).")
        return text

    # ── Attempt 1: primary model ──────────────────────────────────────────────
    try:
        return await _call(MODEL)
    except Exception as exc:
        if not _is_transient(str(exc)):
            logger.exception("Gemini API error (non-transient): %s", exc)
            raise RuntimeError(f"Gemini API error: {exc}") from exc
        logger.warning("[1/4] %s transient error — waiting %ds… (%s)", MODEL, _RETRY_DELAY_1, str(exc)[:80])

    # ── Attempt 2: retry primary after a short delay ─────────────────────────
    await asyncio.sleep(_RETRY_DELAY_1)
    try:
        return await _call(MODEL)
    except Exception as exc:
        if not _is_transient(str(exc)):
            logger.exception("Gemini retry error (non-transient): %s", exc)
            raise RuntimeError(f"Gemini API error: {exc}") from exc
        logger.warning("[2/4] %s still overloaded — waiting %ds, switching to %s…", MODEL, _RETRY_DELAY_2, FALLBACK_MODEL)

    # ── Attempt 3: fallback model after a short delay ────────────────────────
    await asyncio.sleep(_RETRY_DELAY_2)
    try:
        return await _call(FALLBACK_MODEL)
    except Exception as exc:
        if not _is_transient(str(exc)):
            logger.exception("Gemini fallback error (non-transient): %s", exc)
            raise RuntimeError(f"Gemini API error: {exc}") from exc
        logger.warning("[3/4] %s also overloaded — trying legacy %s…", FALLBACK_MODEL, LEGACY_MODEL)

    # ── Attempt 4: legacy stable model ───────────────────────────────────────
    try:
        return await _call(LEGACY_MODEL)
    except Exception as exc:
        logger.exception("[4/4] All Gemini models failed. Last error: %s", exc)
        raise RuntimeError(
            "AI service is temporarily unavailable across all model tiers. "
            "Please try again in a few minutes."
        ) from exc