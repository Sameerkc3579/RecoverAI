"""
RecoveryAgent — Chat / AI generation endpoint.

Routes
──────
POST /api/generate-message — accepts PromptRequest, returns generated text
"""
import asyncio
from typing import List
from fastapi import APIRouter, HTTPException

from app.models.schemas import PromptRequest
from app.services.ai_service import generate_message as ai_generate_message

router = APIRouter(prefix="/api", tags=["AI Generation"])


@router.post(
    "/generate-message",
    response_model=dict,
    summary="Generate a recovery message via Gemini",
)
async def generate_message(payload: PromptRequest) -> dict[str, str]:
    """
    Generate a professional debt-recovery message using Google Gemini.
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
async def bulk_generate_messages(payloads: List[PromptRequest]) -> List[dict]:
    """Process multiple prompts concurrently using Gemini."""
    async def process_one(payload: PromptRequest) -> dict:
        try:
            return {"message": await ai_generate_message(payload.prompt, payload.invoice_data or {}, payload.tone)}
        except Exception as exc:
            return {"error": str(exc), "message": None}
            
    results = await asyncio.gather(*(process_one(p) for p in payloads))
    return list(results)
