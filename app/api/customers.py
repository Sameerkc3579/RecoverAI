from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId

from app.core.database import get_collection
from app.api.deps import get_current_user
from app.models.schemas import CustomerCreate, CustomerUpdate, CustomerResponse
from app.services.customer_service import recalculate_customer_stats

router = APIRouter(prefix="/api/customers", tags=["Customers"])

@router.get("", response_model=list[CustomerResponse], summary="Get all customers for the current user")
async def get_customers(current_user: dict = Depends(get_current_user)):
    col = get_collection("customers")
    cursor = col.find({"owner_id": current_user["_id"]}).sort("_id", -1)
    results = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        doc.pop("owner_id", None)
        results.append(doc)
    return results

@router.get("/{customer_id}", response_model=CustomerResponse, summary="Get a single customer by ID")
async def get_customer(customer_id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("customers")
    try:
        oid = ObjectId(customer_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ID")
        
    doc = await col.find_one({"_id": oid, "owner_id": current_user["_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    doc["id"] = str(doc.pop("_id"))
    doc.pop("owner_id", None)
    return doc

@router.post("", response_model=CustomerResponse, summary="Create a new customer")
async def create_customer(payload: CustomerCreate, current_user: dict = Depends(get_current_user)):
    col = get_collection("customers")
    data = payload.model_dump(by_alias=True)
    data["owner_id"] = current_user["_id"]
    data["created_at"] = datetime.now(timezone.utc).isoformat()
    data["total_outstanding"] = 0.0
    data["total_recovered"] = 0.0
    data["total_amount"] = 0.0
    data["invoice_count"] = 0
    data["last_activity"] = None
    result = await col.insert_one(data)
    
    doc = await col.find_one({"_id": result.inserted_id})
    doc["id"] = str(doc.pop("_id"))
    doc.pop("owner_id", None)
    return doc

@router.put("/{customer_id}", response_model=CustomerResponse, summary="Update a customer")
async def update_customer(customer_id: str, payload: CustomerUpdate, current_user: dict = Depends(get_current_user)):
    col = get_collection("customers")
    update_data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    try:
        oid = ObjectId(customer_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ID")

    result = await col.update_one(
        {"_id": oid, "owner_id": current_user["_id"]},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
        
    doc = await col.find_one({"_id": oid})
    doc["id"] = str(doc.pop("_id"))
    doc.pop("owner_id", None)
    return doc

@router.delete("/{customer_id}", summary="Delete a customer")
async def delete_customer(customer_id: str, current_user: dict = Depends(get_current_user)):
    col = get_collection("customers")
    try:
        oid = ObjectId(customer_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ID")

    result = await col.delete_one({"_id": oid, "owner_id": current_user["_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"status": "success"}

@router.post("/{customer_id}/recalculate", summary="Force recalculate customer stats")
async def recalculate_customer(customer_id: str, current_user: dict = Depends(get_current_user)):
    try:
        oid = ObjectId(customer_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ID")
        
    await recalculate_customer_stats(current_user["_id"], customer_id)
    return await get_customer(customer_id, current_user)
