import re
import logging
from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId

from app.core.database import get_collection

logger = logging.getLogger(__name__)

async def upsert_customer(owner_id: str, invoice_data: dict) -> str:
    """
    Upsert a customer record based on the invoice data.
    Matches by owner_id and company name (case-insensitive).
    Returns the customer _id as a string.
    """
    col = get_collection("customers")
    company = invoice_data.get("company", "").strip()
    if not company:
        company = "Unknown Company"

    # Try to find existing customer (case-insensitive match)
    existing = await col.find_one({
        "owner_id": ObjectId(owner_id) if isinstance(owner_id, str) else owner_id,
        "company": {"$regex": f"^{re.escape(company)}$", "$options": "i"}
    })

    if existing:
        # Update missing contact fields if the new invoice provides them
        update_fields = {}
        for field in ["contact", "email", "phone", "gstin", "city"]:
            val = invoice_data.get(field)
            if val and not existing.get(field):
                update_fields[field] = val

        if update_fields:
            update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
            await col.update_one({"_id": existing["_id"]}, {"$set": update_fields})
            logger.info("Updated existing customer %s with new fields: %s", existing["_id"], update_fields)
            
        return str(existing["_id"])
    else:
        # Create new customer
        new_customer = {
            "owner_id": ObjectId(owner_id) if isinstance(owner_id, str) else owner_id,
            "company": company,
            "contact": invoice_data.get("contact", ""),
            "email": invoice_data.get("email", ""),
            "phone": invoice_data.get("phone", ""),
            "gstin": invoice_data.get("gstin", ""),
            "city": invoice_data.get("city", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "total_outstanding": 0.0,
            "total_recovered": 0.0,
            "total_amount": 0.0,
            "invoice_count": 0,
            "last_activity": None
        }
        result = await col.insert_one(new_customer)
        logger.info("Created new customer %s: %s", result.inserted_id, company)
        return str(result.inserted_id)

async def recalculate_customer_stats(owner_id: str, customer_id: str) -> None:
    """
    Recalculate total_outstanding, total_recovered, total_amount, invoice_count,
    and last_activity for a specific customer by aggregating their invoices.
    """
    invoices_col = get_collection("invoices")
    customers_col = get_collection("customers")
    
    pipeline = [
        {"$match": {
            "owner_id": ObjectId(owner_id) if isinstance(owner_id, str) else owner_id,
            "customer_id": customer_id
        }},
        {"$group": {
            "_id": "$customer_id",
            "invoice_count": {"$sum": 1},
            "total_amount": {"$sum": "$amount"},
            "total_recovered": {
                "$sum": {
                    "$cond": [{"$eq": ["$recovered", True]}, "$amount", 0]
                }
            },
            "total_outstanding": {
                "$sum": {
                    "$cond": [{"$eq": ["$recovered", False]}, "$amount", 0]
                }
            },
            "last_activity_str": {"$max": {"$ifNull": ["$dueDate", "$issueDate"]}}
        }}
    ]
    
    cursor = invoices_col.aggregate(pipeline)
    result = await cursor.to_list(length=1)
    
    if result:
        stats = result[0]
        update_data = {
            "invoice_count": stats["invoice_count"],
            "total_amount": stats["total_amount"],
            "total_recovered": stats["total_recovered"],
            "total_outstanding": stats["total_outstanding"],
            "last_activity": stats.get("last_activity_str"),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
    else:
        # No invoices left
        update_data = {
            "invoice_count": 0,
            "total_amount": 0.0,
            "total_recovered": 0.0,
            "total_outstanding": 0.0,
            "last_activity": None,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
    await customers_col.update_one(
        {
            "_id": ObjectId(customer_id),
            "owner_id": ObjectId(owner_id) if isinstance(owner_id, str) else owner_id
        },
        {"$set": update_data}
    )
    logger.info("Recalculated stats for customer %s", customer_id)
