import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

async def check():
    load_dotenv()
    uri = os.getenv("MONGO_URI")
    if not uri:
        print("❌ MONGO_URI not set in environment/.env")
        return
        
    db_name = os.getenv("DB_NAME", "recovery_agent")
    
    print(f"Connecting to: {uri[:15]}...")
    client = AsyncIOMotorClient(uri)
    
    try:
        # Check connection
        await client.admin.command('ping')
        print("✅ MongoDB connection successful.")
        
        db = client[db_name]
        
        # 1. Total users
        admin_email = os.getenv("ADMIN_EMAILS", "admin@example.com").split(",")[0].strip()
        users = await db['users'].find().to_list(100)
        print(f"DEBUG: Found {len(users)} users in collection 'users'")
        for u in users:
            print(f"  - User: {u.get('email')} (is_admin: {u.get('email') == admin_email})")
            
        admin = await db['users'].find_one({"email": admin_email})
        if not admin:
            print(f"❌ CRITICAL: Admin '{admin_email}' not found in database!")
            return

        # 2. Assign invoices safely
        total_inv = await db['invoices'].count_documents({})
        admin_inv = await db['invoices'].count_documents({"owner_id": admin["_id"]})
        unassigned_inv = await db['invoices'].count_documents({"owner_id": {"$exists": False}})
        
        print(f"DEBUG: System Total Invoices: {total_inv}")
        print(f"DEBUG: Admin Account Invoices: {admin_inv}")
        print(f"DEBUG: Unassigned Invoices: {unassigned_inv}")
        
        if unassigned_inv > 0:
            print("Action: Assigning only UNASSIGNED invoices to Admin...")
            result = await db['invoices'].update_many(
                {"owner_id": {"$exists": False}}, 
                {"$set": {"owner_id": admin["_id"]}}
            )
            print(f"✅ Successfully assigned {result.modified_count} previously unassigned invoices to Admin.")
        elif total_inv == 0:
            print("⚠️ No invoices found in 'invoices' collection to assign.")
        else:
            print("✅ All invoices are already assigned to owners.")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(check())
