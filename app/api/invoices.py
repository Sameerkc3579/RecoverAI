"""
RecoveryAgent — Invoice CRUD endpoints (multi-tenant, JWT-protected).

Routes
──────
POST   /api/invoices            — insert a new invoice (scoped to current user)
GET    /api/invoices            — list invoices owned by current user
PATCH  /api/invoices/{id}       — update an invoice (owner-scoped)
DELETE /api/invoices/{id}       — delete an invoice (owner-scoped)
POST   /api/invoices/upload-proof — upload proof file
"""
import os
import uuid
from datetime import date, datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from bson import ObjectId
from bson.errors import InvalidId

from app.core.database import get_collection
from app.models.schemas import InvoiceCreate, InvoiceResponse
from app.services.recovery_logic import calculate_msme_interest
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/invoices", tags=["Invoices"])

COLLECTION = "invoices"


def _serialise(doc: dict) -> InvoiceResponse:
    """Convert a raw MongoDB document into an InvoiceResponse."""
    doc["id"] = str(doc.pop("_id"))
    doc.pop("owner_id", None)  # strip internal field from response
    return InvoiceResponse(**doc)


def _enrich_with_interest(doc: dict) -> dict:
    """
    Enrich a raw MongoDB invoice document with live MSME interest data.
    Also recalculates daysOverdue so dashboards always show the real value.
    """
    doc["id"] = str(doc.pop("_id"))
    doc.pop("owner_id", None)

    # Resolve the due date field (could be stored as dueDate or due_date)
    due_date_str = doc.get("dueDate") or doc.get("due_date") or ""

    # Recalculate days overdue dynamically from today
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

    # Calculate MSME interest
    principal = doc.get("amount", 0)
    interest_data = calculate_msme_interest(principal, due_date_str)
    doc["interest_data"] = interest_data

    return doc


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
    summary="Update invoice status",
)
async def update_invoice(
    invoice_id: str,
    payload: dict,
    current_user: dict = Depends(get_current_user),
) -> InvoiceResponse:
    col = get_collection(COLLECTION)
    try:
        oid = ObjectId(invoice_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ID")

    result = await col.update_one(
        {"_id": oid, "owner_id": current_user["_id"]},
        {"$set": payload},
    )
    doc = await col.find_one({"_id": oid, "owner_id": current_user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Invoice not found")
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
    col = get_collection(COLLECTION)
    try:
        oid = ObjectId(invoice_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ID")
    result = await col.delete_one({"_id": oid, "owner_id": current_user["_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Invoice not found")


@router.post(
    "/upload-proof",
    response_model=dict,
    status_code=201,
    summary="Upload Proof of Delivery",
)
async def upload_proof(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Upload a file to local storage and return the URL."""
    ext = file.filename.split('.')[-1] if file.filename and '.' in file.filename else 'pdf'
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join("uploads", filename)
    with open(filepath, "wb") as f:
        f.write(await file.read())
    return {"proof_url": f"/uploads/{filename}"}
