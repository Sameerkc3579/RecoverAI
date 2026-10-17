"""One-off backfill: create customer records for existing invoices.  python scripts/migrate_customers.py"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # project root, for `app`

from bson import ObjectId
from app.core.database import connect_db, close_db, get_collection
from app.services.customer_service import upsert_customer, recalculate_customer_stats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate():
    await connect_db()
    logger.info("Connected to database. Starting customer migration...")
    
    invoices_col = get_collection("invoices")
    
    # Process all invoices that don't have a customer_id yet
    cursor = invoices_col.find({"customer_id": {"$exists": False}})
    
    count = 0
    async for invoice in cursor:
        owner_id = str(invoice.get("owner_id"))
        
        # Build invoice_data dictionary mimicking what upsert_customer expects
        invoice_data = {
            "company": invoice.get("company", ""),
            "contact": invoice.get("contact", ""),
            "email": invoice.get("email", ""),
            "phone": invoice.get("phone", ""),
            "gstin": invoice.get("gstin", ""),
            "city": invoice.get("city", "")
        }
        
        try:
            # 1. Upsert customer
            customer_id = await upsert_customer(owner_id, invoice_data)
            
            # 2. Link invoice to customer
            await invoices_col.update_one(
                {"_id": invoice["_id"]},
                {"$set": {"customer_id": customer_id}}
            )
            
            # 3. Recalculate stats for this customer
            await recalculate_customer_stats(owner_id, customer_id)
            
            count += 1
            if count % 10 == 0:
                logger.info(f"Processed {count} invoices...")
        except Exception as e:
            logger.error(f"Failed to migrate invoice {invoice['_id']}: {e}")

    logger.info(f"Migration completed. Processed {count} invoices.")
    await close_db()

if __name__ == "__main__":
    asyncio.run(migrate())
