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
import tempfile
import uuid
from datetime import date, datetime, timedelta, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Request

from app.core.database import get_collection
from app.core.config import settings
from app.models.schemas import InvoiceCreate, InvoiceResponse, InvoiceUpdate
from app.services.recovery_logic import calculate_msme_interest
from app.services.customer_service import upsert_customer, recalculate_customer_stats
from app.api.deps import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/invoices", tags=["Invoices"])

COLLECTION = "invoices"
PORTAL_TOKENS_COLLECTION = "portal_tokens"
PORTAL_TOKEN_TTL_DAYS = 7

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
    return os.path.join(tempfile.gettempdir(), "uploads") if is_vercel else "uploads"


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
            logger.debug("Silenced exception parsing due date", exc_info=True)

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
    
    # Customer Upsert Logic
    customer_id = await upsert_customer(current_user["_id"], data)
    await col.update_one({"_id": result.inserted_id}, {"$set": {"customer_id": customer_id}})
    
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
    payload: InvoiceUpdate,
    current_user: dict = Depends(get_current_user),
) -> InvoiceResponse:
    """
    Update an invoice owned by the current user.

    Security: The payload is a typed model (only known, well-typed fields are
    accepted), and is additionally run through the Mongo-operator sanitizer
    as defense-in-depth before being applied to the database.
    """
    update_data = payload.model_dump(by_alias=True, exclude_unset=True)

    # Reject empty payloads
    if not update_data:
        raise HTTPException(status_code=400, detail="Update payload cannot be empty.")

    # Sanitize payload — strip MongoDB operators and protected fields (defense-in-depth)
    safe_payload = _sanitize_update_payload(update_data)

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
        
    # Recalculate customer stats if monetary values or status changed
    if any(k in safe_payload for k in ("recovered", "amount", "status")) and "customer_id" in doc:
        await recalculate_customer_stats(current_user["_id"], doc["customer_id"])
        
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

    doc = await col.find_one({"_id": oid, "owner_id": current_user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    result = await col.delete_one({"_id": oid, "owner_id": current_user["_id"]})
    
    if "customer_id" in doc:
        await recalculate_customer_stats(current_user["_id"], doc["customer_id"])


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

    # Validate file magic bytes
    file_header = await file.read(8)
    await file.seek(0)
    MAGIC_BYTES = {
        b'%PDF': 'application/pdf',
        b'\xff\xd8\xff': 'image/jpeg',
        b'\x89PNG': 'image/png',
    }
    detected_type = None
    for magic, mime in MAGIC_BYTES.items():
        if file_header.startswith(magic):
            detected_type = mime
            break
    # Normalize image/jpg <-> image/jpeg before comparing — magic bytes always
    # map JPEGs to "image/jpeg", but browsers/clients may declare "image/jpg".
    _JPEG_ALIASES = {"image/jpeg", "image/jpg"}
    declared_type = file.content_type
    if detected_type in _JPEG_ALIASES and declared_type in _JPEG_ALIASES:
        pass  # both are JPEG — treat as a match
    elif detected_type and detected_type != declared_type:
        raise HTTPException(status_code=400, detail="File content does not match declared type.")

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


@router.post(
    "/{invoice_id}/portal-link",
    response_model=dict,
    status_code=200,
    summary="Generate Magic Link for Debtor Portal",
)
async def generate_portal_link(
    invoice_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Generate a magic link for a specific invoice."""
    col = get_collection(COLLECTION)
    try:
        oid = ObjectId(invoice_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid invoice ID format.")

    doc = await col.find_one({"_id": oid, "owner_id": current_user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Invoice not found.")

    token = "tok_" + str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=PORTAL_TOKEN_TTL_DAYS)

    tokens_col = get_collection(PORTAL_TOKENS_COLLECTION)
    await tokens_col.insert_one({
        "token": token,
        "invoice_id": oid,
        "owner_id": current_user["_id"],
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
    })

    base_url = str(request.base_url).rstrip("/")
    # Frontend debtor portal page is served at GET /portal (see app/main.py).
    portal_url = f"{base_url}/portal?token={token}"
    return {"token": token, "portal_url": portal_url}


@router.get(
    "/portal/{token}",
    response_model=dict,
    summary="Public debtor portal — view invoice via magic link (no auth)",
)
async def get_portal_invoice(token: str) -> dict:
    """
    Resolve a magic-link token to a minimal, owner-data-safe view of the
    associated invoice. No authentication required — the token itself is
    the credential. Returns 404 if the token is unknown or expired.
    """
    tokens_col = get_collection(PORTAL_TOKENS_COLLECTION)
    token_doc = await tokens_col.find_one({"token": token})
    if not token_doc:
        raise HTTPException(status_code=404, detail="Invalid or expired link.")

    expires_at = token_doc.get("expires_at")
    if expires_at:
        try:
            expiry_dt = datetime.fromisoformat(expires_at)
            if expiry_dt.tzinfo is None:
                expiry_dt = expiry_dt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expiry_dt:
                raise HTTPException(status_code=404, detail="Invalid or expired link.")
        except ValueError:
            raise HTTPException(status_code=404, detail="Invalid or expired link.")

    col = get_collection(COLLECTION)
    doc = await col.find_one({"_id": token_doc["invoice_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Invalid or expired link.")

    # Minimal, owner-data-safe public view — never leak owner_id or internal fields
    enriched = _enrich_with_interest(dict(doc))
    interest_data = enriched.get("interest_data") or {}
    return {
        "company": enriched.get("company"),
        "amount": enriched.get("amount"),
        # Invoices are stored with camelCase aliases (by_alias=True), so prefer
        # those keys and fall back to snake_case for any legacy documents.
        "invoiceNo": enriched.get("invoiceNo") or enriched.get("invoice_no"),
        "dueDate": enriched.get("dueDate") or enriched.get("due_date"),
        "daysOverdue": enriched.get("daysOverdue"),
        "status": enriched.get("status"),
        "interestAccrued": interest_data.get("interest_accrued"),
        "totalPayable": interest_data.get("total_claim"),
    }
