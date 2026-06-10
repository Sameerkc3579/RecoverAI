from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId

from app.core.database import get_collection
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/customers", tags=["Customers"])

class CustomerCreate(BaseModel):
    company: str
    contact: Optional[str] = ""
    email: Optional[str] = ""
    phone: Optional[str] = ""
    city: Optional[str] = ""
    gstin: Optional[str] = ""

class CustomerUpdate(BaseModel):
    company: Optional[str] = None
    contact: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    gstin: Optional[str] = None

@router.get("", summary="Get all customers for the current user")
async def get_customers(current_user: dict = Depends(get_current_user)):
    col = get_collection("customers")
    cursor = col.find({"owner_id": current_user["_id"]}).sort("_id", -1)
    results = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        doc.pop("owner_id", None)
        results.append(doc)
    return results

@router.post("", summary="Create a new customer")
async def create_customer(payload: CustomerCreate, current_user: dict = Depends(get_current_user)):
    col = get_collection("customers")
    data = payload.model_dump()
    data["owner_id"] = current_user["_id"]
    data["created_at"] = datetime.now(timezone.utc).isoformat()
    result = await col.insert_one(data)
    
    doc = await col.find_one({"_id": result.inserted_id})
    doc["id"] = str(doc.pop("_id"))
    doc.pop("owner_id", None)
    return doc

@router.put("/{customer_id}", summary="Update a customer")
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
