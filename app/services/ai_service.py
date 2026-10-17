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
import re

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
You are RecoverAI's debt-recovery agent for Indian MSME businesses. Draft the message the user asks for. Tone: {tone}.
{channel_rules}
Always:
- Include the invoice number, amount and due date.
- If the invoice is 45+ days overdue, cite the MSMED Act 2006 interest penalty as leverage.
- Offer a payment arrangement path; never use abusive or threatening language beyond the requested tone.
- Output only the message itself — no labels such as "Channel:", "Tone:" or "Message:", and no commentary.
- Write the complete message through to the sign-off; never stop after an opening line.
"""

_CHANNEL_RULES = {
    "whatsapp": "Channel: WhatsApp. Write a short conversational chat message (3-6 lines), warm but firm; "
                "\"ji\" and \"sir/madam\" are fine. Do NOT include a subject line or email formatting.",
    "email": "Channel: Email. Start with a single \"Subject:\" line, then greeting, body and signature.",
    "legal": "Channel: Legal notice. Formal letter citing MSMED Act 2006 Sections 15-17 with a 15-day "
             "ultimatum. Start with a \"Subject:\" line.",
}
_DEFAULT_CHANNEL_RULES = ("Use the format of the channel named in the request: WhatsApp messages are short "
                          "and have no subject line; emails and legal notices start with a \"Subject:\" line.")

# Lines models sometimes prepend despite instructions — removed from WhatsApp drafts
_META_LINE = re.compile(r"^\s*(\*\*)?\s*(subject|channel|tone|message type)\s*:.*$", re.IGNORECASE)


_CHANNEL_KEYWORDS = {
    "whatsapp": ("whatsapp",),
    "email": ("email", "e-mail"),
    "legal": ("legal notice", "letter before action"),
}


def _infer_channel(prompt: str) -> str | None:
    """
    Infer the requested format from the request text. Requests name their format
    first ("WhatsApp message for…", "Professional email to…", "Draft a formal
    Legal Notice…"), so the earliest mention wins — "an email about the legal
    notice" is an email, not a legal notice.
    """
    text = (prompt or "").lower()
    positions = {
        channel: min((i for i in (text.find(k) for k in keywords) if i >= 0), default=-1)
        for channel, keywords in _CHANNEL_KEYWORDS.items()
    }
    found = {c: i for c, i in positions.items() if i >= 0}
    return min(found, key=found.get) if found else None


def _clean_for_channel(text: str, channel: str | None) -> str:
    """WhatsApp drafts must start with the message itself, not Subject/Channel lines."""
    if channel != "whatsapp":
        return text
    lines = text.strip().splitlines()
    while lines and (not lines[0].strip() or _META_LINE.match(lines[0])):
        lines.pop(0)
    return "\n".join(lines).strip()

# ── Transient error check ────────────────────────────────────────────────────
_TRANSIENT_SIGNALS = ("429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE", "overloaded", "empty response")

def _is_transient(err: str) -> bool:
    return any(sig in err for sig in _TRANSIENT_SIGNALS)


def _build_config(tone: str, channel: str | None = None) -> types.GenerateContentConfig:
    """Shared GenerateContentConfig to avoid repetition."""
    return types.GenerateContentConfig(
        system_instruction=_SYSTEM_INSTRUCTION.format(
            tone=tone, channel_rules=_CHANNEL_RULES.get(channel, _DEFAULT_CHANNEL_RULES)),
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


async def generate_message(prompt: str, invoice_data: dict, tone: str, channel: str | None = None) -> str:
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

    channel = channel or _infer_channel(prompt)
    logger.info("Calling Gemini %s | tone: %s | channel: %s", MODEL, tone, channel)

    context_prompt = (
        f"INVOICE CONTEXT:\n{json.dumps(invoice_data, indent=2)}\n\n"
        f"REQUESTED MESSAGE DRAFT:\n{prompt}\n\n"
        "Output the complete message from start to finish, including the sign-off."
    )

    async def _call(model: str) -> str:
        client = _get_client()
        response = await client.aio.models.generate_content(
            model=model,
            contents=context_prompt,
            config=_build_config(tone, channel),
        )
        text = response.text
        if not text:
            # response.text is None/empty when Gemini returns no candidates
            # (e.g. a safety block) — treat as a transient failure so the
            # caller retries/falls back instead of returning null to the client.
            raise RuntimeError(f"Gemini ({model}) returned an empty response (possible safety block).")
        return _clean_for_channel(text, channel)

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