"""
RecoveryAgent — NLP pipeline for debtor reply processing.

Pipeline stages
───────────────
1. **Translation**: Converts raw Hindi / Hinglish / regional text → clean English
2. **Intent Classification**: Classifies the translated reply into one of:
   - promise_to_pay
   - dispute
   - stall
   - unknown
3. **Action Suggestion**: Returns a recommended next step for the recovery agent.

Both stages use the shared Gemini async client from ``ai_service``.

Resilience Strategy (Heuristic Fallback):
──────────────────────────────────────────
When the Gemini API returns a 429 / quota / billing error:
  - Stage 1 failure → skips translation, runs heuristic on raw text immediately.
  - Stage 2 failure → uses translated text + heuristic for classification.
  - Global failure  → heuristic runs as a last resort before returning "unknown".

The heuristic uses keyword matching for Hindi/Hinglish/English payment keywords
(kal, payment, bhej, deta, UPI, galat, etc.) to classify intent, keeping the
demo intelligent even without active API credits.
"""
import json
import logging
from typing import Literal

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Gemini client (shared config) ─────────────────────────────────────────────
_client = genai.Client(api_key=settings.gemini_api_key)
MODEL = "gemini-1.5-flash"

# ── Valid intents ─────────────────────────────────────────────────────────────
IntentType = Literal["promise_to_pay", "dispute", "stall", "unknown"]

# ── Stage 1 — Translation prompt ─────────────────────────────────────────────
_TRANSLATE_SYSTEM = """\
You are a professional translator specialising in Indian languages.

RULES:
1. Translate the user's message into clean, professional English.
2. The input may be in Hindi (Devanagari), Hinglish, Marathi, Tamil, Telugu,
   Gujarati, Bengali, Punjabi, or any mix thereof.
3. Preserve the original meaning and emotional tone accurately.
4. If the text is already in English, clean it up for grammar and clarity.
5. Return ONLY the translated text — no preamble, no explanations.
"""

# ── Stage 2 — Intent classification prompt ────────────────────────────────────
_CLASSIFY_SYSTEM = """\
You are an intent-classification engine for a debt-recovery system.

Classify the debtor's reply into EXACTLY ONE of these four intents:
  • promise_to_pay — Debtor agrees, promises, or commits to making payment.
  • dispute — Debtor challenges the debt, mentions product issues, wrong amount, etc.
  • stall — Debtor avoids commitment, defers, asks to call back, says owner is away, etc.
  • unknown — Cannot determine clear intent from the message.

Also assess your confidence:
  • high — Clear, unambiguous intent
  • medium — Likely intent but some ambiguity
  • low — Very unclear or mixed signals

And suggest ONE next action:
  • For promise_to_pay → "Schedule follow-up in 48 hours to confirm payment received"
  • For dispute → "Escalate to account manager for dispute resolution"
  • For stall → "Send a firmer follow-up message in 24 hours"
  • For unknown → "Request clarification from the debtor"

YOU MUST RESPOND ONLY WITH A VALID JSON OBJECT in this exact format:
{"intent": "<intent>", "confidence": "<high|medium|low>", "suggested_action": "<action>"}

No markdown, no code fences, no extra text. ONLY the raw JSON object.
"""


# ── Heuristic Fallback ────────────────────────────────────────────────────────
# Runs when Gemini quota is exhausted. Keyword lists cover common Hindi/Hinglish
# utterances a debtor might actually send over WhatsApp.

_PROMISE_KEYWORDS = [
    "kal", "kal tak", "aaj", "abhi", "payment", "bhej", "bhejta", "bhejti",
    "deta", "deti", "dunga", "dungi", "kar deta", "kar deti", "transfer",
    "upi", "neft", "imps", "paisa", "paise", "send", "pay", "paid",
    "de dunga", "de dungi", "karta hoon", "karti hoon", "zaroor", "pakka",
    "confirm", "done", "clearing", "clear kar", "bhej deta", "bhej raha",
    "wire", "rtgs", "cheque", "check",
]
_DISPUTE_KEYWORDS = [
    "galat", "wrong", "dispute", "nahi mila", "mila nahi", "issue",
    "problem", "defect", "return", "wapas", "quality", "damaged",
    "not received", "nahi aaya", "invoice galat", "amount galat",
    "received nahi", "deliver nahi", "short", "partial",
]
_STALL_KEYWORDS = [
    "baad mein", "bad mein", "thoda time", "wait", "ruko", "rukiye",
    "abhi nahi", "owner nahi", "sahab nahi", "boss nahi", "out of town",
    "bahar hain", "next week", "agli baar", "phone karo", "call karo",
    "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "thodi der", "busy", "meeting", "baat karo", "baad",
]


def _heuristic_classify(raw_text: str) -> dict:
    """
    Keyword-based intent classification — runs when Gemini API is unavailable.
    Scans for Hindi/Hinglish/English payment-related keywords and scores each category.
    Returns the highest-scoring intent (ties broken: promise > dispute > stall).
    """
    text_lower = raw_text.lower()

    promise_score = sum(1 for kw in _PROMISE_KEYWORDS if kw in text_lower)
    dispute_score = sum(1 for kw in _DISPUTE_KEYWORDS if kw in text_lower)
    stall_score   = sum(1 for kw in _STALL_KEYWORDS   if kw in text_lower)

    logger.info(
        "Heuristic scores — promise:%d dispute:%d stall:%d for text: '%s'",
        promise_score, dispute_score, stall_score, raw_text[:60],
    )

    max_score = max(promise_score, dispute_score, stall_score)
    if max_score == 0:
        return {
            "intent": "unknown",
            "confidence": "low",
            "suggested_action": "Request clarification from the debtor",
        }

    if promise_score >= dispute_score and promise_score >= stall_score:
        return {
            "intent": "promise_to_pay",
            "confidence": "medium" if promise_score >= 2 else "low",
            "suggested_action": "Schedule follow-up in 48 hours to confirm payment received",
        }
    elif dispute_score >= stall_score:
        return {
            "intent": "dispute",
            "confidence": "medium" if dispute_score >= 2 else "low",
            "suggested_action": "Escalate to account manager for dispute resolution",
        }
    else:
        return {
            "intent": "stall",
            "confidence": "medium" if stall_score >= 2 else "low",
            "suggested_action": "Send a firmer follow-up message in 24 hours",
        }


def _is_quota_error(exc: Exception) -> bool:
    """Detect Google API quota / billing exhaustion errors (429, ResourceExhausted, etc.)."""
    err_str = str(exc).lower()
    return any(kw in err_str for kw in [
        "429", "quota", "resource_exhausted", "resourceexhausted",
        "billing", "limit: 0", "limit:0", "rate limit", "too many requests",
    ])


async def _translate(raw_text: str) -> str:
    """Stage 1: Translate raw debtor reply to professional English."""
    logger.info("NLP Stage 1 — translating %d chars", len(raw_text))
    try:
        response = await _client.aio.models.generate_content(
            model=MODEL,
            contents=raw_text,
            config=types.GenerateContentConfig(
                system_instruction=_TRANSLATE_SYSTEM,
                temperature=0.2,
                max_output_tokens=512,
            ),
        )
        translated = response.text.strip()
        logger.info("Translation result: %s", translated[:120])
        return translated
    except Exception as exc:
        if _is_quota_error(exc):
            # Re-raise quota errors so process_debtor_reply can activate heuristic
            logger.warning("Quota/billing error detected in translation stage: %s", exc)
            raise
        logger.exception("Translation failed with non-quota error: %s", exc)
        return f"[MOCK TRANSLATION: User replied in regional language referring to '{raw_text[:20]}...']"


async def _classify_intent(english_text: str) -> dict:
    """Stage 2: Classify the translated text into an intent category."""
    logger.info("NLP Stage 2 — classifying intent")
    try:
        response = await _client.aio.models.generate_content(
            model=MODEL,
            contents=f"Debtor reply: \"{english_text}\"",
            config=types.GenerateContentConfig(
                system_instruction=_CLASSIFY_SYSTEM,
                temperature=0.1,
                max_output_tokens=256,
            ),
        )
        raw = response.text.strip()
        # Strip possible markdown fences the model might add
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        result = json.loads(raw)
        # Validate fields
        if result.get("intent") not in ("promise_to_pay", "dispute", "stall", "unknown"):
            result["intent"] = "unknown"
        if result.get("confidence") not in ("high", "medium", "low"):
            result["confidence"] = "medium"
        if "suggested_action" not in result:
            result["suggested_action"] = "Request clarification from the debtor"

        logger.info("Classification: %s (%s)", result["intent"], result["confidence"])
        return result
    except json.JSONDecodeError:
        logger.warning("Gemini returned non-JSON for classification, defaulting to unknown")
        return {
            "intent": "unknown",
            "confidence": "low",
            "suggested_action": "Request clarification from the debtor",
        }
    except Exception as exc:
        if _is_quota_error(exc):
            # Re-raise quota errors so process_debtor_reply can activate heuristic
            logger.warning("Quota/billing error detected in classification stage: %s", exc)
            raise
        logger.exception("Intent classification failed with non-quota error: %s", exc)
        return {
            "intent": "unknown",
            "confidence": "low",
            "suggested_action": "[MOCK ACTION] Manual review required due to API failure.",
        }


async def process_debtor_reply(raw_text: str) -> dict:
    """
    Full NLP pipeline: translate → classify → return structured result.

    Resilience Strategy:
    ─────────────────────
    1. Attempt the full Gemini pipeline (translate + classify).
    2. If a quota/billing error (429 / ResourceExhausted / limit:0) is detected
       at the Translation stage → immediately skip to heuristic on raw text.
    3. If quota error occurs at the Classification stage → run heuristic on
       the already-translated text (best of both worlds).
    4. All other unexpected errors → heuristic is attempted as last resort,
       ensuring the webhook endpoint ALWAYS returns 200 OK.
    """
    try:
        # ── Stage 1: Translation ──────────────────────────────────────────────
        try:
            translated_text = await _translate(raw_text)
        except Exception as exc:
            if _is_quota_error(exc):
                logger.warning(
                    "⚡ Quota error in TRANSLATION — activating heuristic fallback on raw text."
                )
                result = _heuristic_classify(raw_text)
                return {
                    "translated_text": f"[Heuristic fallback — API quota reached] {raw_text}",
                    "intent": result["intent"],
                    "confidence": result["confidence"],
                    "suggested_action": result["suggested_action"],
                    "fallback_mode": "heuristic_keyword",
                }
            raise  # Non-quota translation errors bubble up to outer handler

        # Safety check: if translation returned a mock placeholder, API is likely down
        if "[MOCK TRANSLATION" in translated_text:
            logger.warning("Mock translation detected — activating heuristic fallback.")
            result = _heuristic_classify(raw_text)
            return {
                "translated_text": f"[Heuristic fallback] {raw_text}",
                "intent": result["intent"],
                "confidence": result["confidence"],
                "suggested_action": result["suggested_action"],
                "fallback_mode": "heuristic_keyword",
            }

        # ── Stage 2: Classification ───────────────────────────────────────────
        try:
            classification = await _classify_intent(translated_text)
        except Exception as exc:
            if _is_quota_error(exc):
                logger.warning(
                    "⚡ Quota error in CLASSIFICATION — activating heuristic fallback on translated text."
                )
                result = _heuristic_classify(raw_text)
                return {
                    "translated_text": translated_text,
                    "intent": result["intent"],
                    "confidence": result["confidence"],
                    "suggested_action": result["suggested_action"],
                    "fallback_mode": "heuristic_keyword",
                }
            raise

        # ── Stage 3: Assemble final response ─────────────────────────────────
        return {
            "translated_text": translated_text,
            "intent": classification["intent"],
            "confidence": classification["confidence"],
            "suggested_action": classification["suggested_action"],
        }

    except Exception as e:
        logger.error("Global NLP Pipeline Failure: %s", e)
        # Final safety net — try heuristic before returning a generic fallback
        try:
            result = _heuristic_classify(raw_text)
            return {
                "translated_text": f"[Global fallback — pipeline error] {raw_text}",
                "intent": result["intent"],
                "confidence": result["confidence"],
                "suggested_action": result["suggested_action"],
                "fallback_mode": "heuristic_keyword",
            }
        except Exception:
            return {
                "translated_text": f"System Fallback: {raw_text}",
                "intent": "unknown",
                "confidence": "low",
                "suggested_action": "Review message manually in Debtor Inbox.",
                "fallback_mode": "error",
            }