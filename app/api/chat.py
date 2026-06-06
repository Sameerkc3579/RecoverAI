"""
RecoveryAgent — Chat / AI generation endpoint.

Routes
──────
POST /api/generate-message — accepts PromptRequest, returns generated text

Security Fix:
  - Added JWT authentication to all AI endpoints.
  - Previously, /api/generate-message and /api/bulk-generate were completely
    unauthenticated, allowing any anonymous user to exhaust the Gemini API key.
"""
import asyncio
from typing import List
from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import PromptRequest
from app.services.ai_service import generate_message as ai_generate_message
from app.api.deps import get_current_user

router = APIRouter(prefix="/api", tags=["AI Generation"])


@router.post(
    "/generate-message",
    response_model=dict,
    summary="Generate a recovery message via Gemini",
)
async def generate_message(
    payload: PromptRequest,
    current_user: dict = Depends(get_current_user),  # SECURITY: auth required
) -> dict[str, str]:
    """
    Generate a professional debt-recovery message using Google Gemini.
    Requires a valid JWT — unauthenticated callers receive HTTP 401.
    """
    try:
        text = await ai_generate_message(payload.prompt, payload.invoice_data or {}, payload.tone)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return {"message": text}


@router.post(
    "/bulk-generate",
    response_model=List[dict],
    summary="Bulk generate recovery messages",
)
async def bulk_generate_messages(
    payloads: List[PromptRequest],
    current_user: dict = Depends(get_current_user),  # SECURITY: auth required
) -> List[dict]:
    """Process multiple prompts concurrently using Gemini.
    Requires a valid JWT — unauthenticated callers receive HTTP 401.
    """
    # Cap bulk requests to prevent a single authenticated user from flooding the API
    if len(payloads) > 20:
        raise HTTPException(status_code=400, detail="Bulk limit is 20 messages per request.")

    async def process_one(payload: PromptRequest) -> dict:
        try:
            return {"message": await ai_generate_message(payload.prompt, payload.invoice_data or {}, payload.tone)}
        except Exception as exc:
            return {"error": str(exc), "message": None}

    results = await asyncio.gather(*(process_one(p) for p in payloads))
    return list(results)
