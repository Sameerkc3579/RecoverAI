"""
RecoverAI — Invoice CRUD endpoints (Security-Hardened, multi-tenant, JWT-protected).

Routes
──────
POST   /api/invoices            — Insert a new invoice (scoped to current user)
GET    /api/invoices            — List invoices owned by current user
PATCH  /api/invoices/{id}       — Update an invoice (owner-scoped, MongoDB injection protected)
DELETE /api/invoices/{id}       — Delete an invoice (owner-scoped)
POST   /api/invoices/upload-proof — Upload proof file (MIME + size + extension validated)

Security Fixes Applied:
  - MongoDB operator injection protection on PATCH (strips $ operators from payload)
  - File upload: extension allowlist, MIME type check, 10MB size limit, filename sanitization
"""
import logging
import os
import uuid
from datetime import date, datetime

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Request

from app.core.database import get_collection
from app.core.config import settings
from app.models.schemas import InvoiceCreate, InvoiceResponse
from app.services.recovery_logic import calculate_msme_interest
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/invoices", tags=["Invoices"])

COLLECTION = "invoices"

# ── File Upload Security Constants ────────────────────────────────────────────
# Strict allowlist of permitted file extensions for proof-of-delivery documents
ALLOWED_EXTENSIONS: set[str] = {"pdf", "png", "jpg", "jpeg"}

# Map allowed extensions to their valid MIME types (Content-Type header check)
ALLOWED_MIME_TYPES: set[str] = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
}

# MongoDB operators that must never appear in user-supplied update payloads
# These could be used for injection attacks or privilege escalation
_DANGEROUS_MONGO_OPERATORS = {
    "$where", "$expr", "$function", "$accumulator",
    "$lookup", "$merge", "$out", "$graphLookup",
    "$addFields", "$replaceRoot", "$replaceWith",
}

# Fields that users must never be allowed to modify directly
_PROTECTED_FIELDS = {"_id", "owner_id", "created_at", "hashed_password"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sanitize_update_payload(payload: dict) -> dict:
    """
    Strip MongoDB operator injection from user-supplied PATCH payloads.

    Rules:
    1. Remove any key starting with '$' (MongoDB operator)
    2. Remove protected internal fields (owner_id, _id, etc.)
    3. Recursively sanitize nested dicts

    This prevents:
    - NoSQL injection ($where, $expr)
    - Privilege escalation (overwriting owner_id)
    - Structural manipulation ($addFields, $lookup)
    """
    sanitized = {}
    for key, value in payload.items():
        # Block MongoDB operators
        if key.startswith("$"):
            logger.warning("BLOCKED_MONGO_OPERATOR | key=%s", key)
            continue
        # Block protected fields
        if key in _PROTECTED_FIELDS:
            logger.warning("BLOCKED_PROTECTED_FIELD | key=%s", key)
            continue
        # Recursively sanitize nested objects
        if isinstance(value, dict):
            value = _sanitize_update_payload(value)
        sanitized[key] = value
    return sanitized


def _get_upload_dir() -> str:
    """Return the upload directory path (Vercel-compatible)."""
    is_vercel = bool(os.environ.get("VERCEL"))
    return "/tmp/uploads" if is_vercel else "uploads"


def _serialise(doc: dict) -> InvoiceResponse:
    """Convert a raw MongoDB document into an InvoiceResponse."""
    doc["id"] = str(doc.pop("_id"))
    doc.pop("owner_id", None)
    return InvoiceResponse(**doc)


def _enrich_with_interest(doc: dict) -> dict:
    """Enrich a raw MongoDB invoice document with live MSME interest data."""
    doc["id"] = str(doc.pop("_id"))
    doc.pop("owner_id", None)

    due_date_str = doc.get("dueDate") or doc.get("due_date") or ""

    if due_date_str:
        try:
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
                try:
                    due_dt = datetime.strptime(due_date_str.strip(), fmt).date()
                    break
                except ValueError:
                    continue
            else:
                due_dt = None
            if due_dt:
                doc["daysOverdue"] = max(0, (date.today() - due_dt).days)
        except Exception:
            pass

    principal = doc.get("amount", 0)
    interest_data = calculate_msme_interest(principal, due_date_str)
    doc["interest_data"] = interest_data

    return doc


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=InvoiceResponse,
    status_code=201,
    summary="Create a new invoice",
)
async def create_invoice(
    payload: InvoiceCreate,
    current_user: dict = Depends(get_current_user),
) -> InvoiceResponse:
    """Insert a new invoice document scoped to the authenticated user."""
    col = get_collection(COLLECTION)
    data = payload.model_dump(by_alias=True)
    data["owner_id"] = current_user["_id"]
    result = await col.insert_one(data)
    doc = await col.find_one({"_id": result.inserted_id})
    if doc is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve created invoice.")
    return _serialise(doc)


@router.get(
    "",
    summary="List all invoices (enriched with MSME interest)",
)
async def list_invoices(current_user: dict = Depends(get_current_user)):
    """Return all invoice documents owned by the current user, newest first."""
    col = get_collection(COLLECTION)
    cursor = col.find({"owner_id": current_user["_id"]}).sort("_id", -1)
    results = []
    async for doc in cursor:
        enriched = _enrich_with_interest(doc)
        results.append(enriched)
    return results


@router.patch(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    summary="Update invoice status (MongoDB injection protected)",
)
async def update_invoice(
    invoice_id: str,
    payload: dict,
    current_user: dict = Depends(get_current_user),
) -> InvoiceResponse:
    """
    Update an invoice owned by the current user.

    Security: The payload is sanitized to strip MongoDB operators and
    protected fields before being applied to the database.
    """
    # Reject empty payloads
    if not payload:
        raise HTTPException(status_code=400, detail="Update payload cannot be empty.")

    # Sanitize payload — strip MongoDB operators and protected fields
    safe_payload = _sanitize_update_payload(payload)

    if not safe_payload:
        raise HTTPException(
            status_code=422,
            detail="Update payload contained only disallowed fields or operators.",
        )

    col = get_collection(COLLECTION)
    try:
        oid = ObjectId(invoice_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid invoice ID format.")

    # Owner-scoped update — cannot modify another user's invoice
    await col.update_one(
        {"_id": oid, "owner_id": current_user["_id"]},
        {"$set": safe_payload},
    )
    doc = await col.find_one({"_id": oid, "owner_id": current_user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return _serialise(doc)


@router.delete(
    "/{invoice_id}",
    status_code=204,
    summary="Delete an invoice",
)
async def delete_invoice(
    invoice_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete an invoice owned by the current user."""
    col = get_collection(COLLECTION)
    try:
        oid = ObjectId(invoice_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid invoice ID format.")

    result = await col.delete_one({"_id": oid, "owner_id": current_user["_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found.")


@router.post(
    "/upload-proof",
    response_model=dict,
    status_code=201,
    summary="Upload Proof of Delivery (validated)",
)
async def upload_proof(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Upload a proof-of-delivery file with full security validation.

    Security checks:
    1. Extension allowlist: only pdf, png, jpg, jpeg
    2. MIME type validation via Content-Type header
    3. File size limit: settings.max_upload_size_mb (default 10 MB)
    4. Filename sanitized and replaced with a UUID (no path traversal)
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    # 1. Extension check (case-insensitive)
    raw_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if raw_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '.{raw_ext}' is not allowed. Accepted types: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # 2. MIME type check (Content-Type header sent by the browser)
    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"MIME type '{content_type}' is not allowed.",
        )

    # 3. Read file in chunks, enforcing size limit
    max_size = settings.max_upload_size_mb * 1024 * 1024
    chunks = []
    total_bytes = 0
    while True:
        chunk = await file.read(65536)  # 64 KB chunks
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum allowed size is {settings.max_upload_size_mb} MB.",
            )
        chunks.append(chunk)
    file_bytes = b"".join(chunks)

    # 4. Generate a UUID-based filename (no path traversal, no original filename)
    safe_filename = f"{uuid.uuid4().hex}.{raw_ext}"
    upload_dir = _get_upload_dir()
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, safe_filename)

    with open(filepath, "wb") as f:
        f.write(file_bytes)

    logger.info(
        "FILE_UPLOADED | user=%s | filename=%s | size=%d bytes | type=%s",
        current_user.get("email"), safe_filename, total_bytes, content_type,
    )

    return {"proof_url": f"/uploads/{safe_filename}"}
