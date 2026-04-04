import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

async def check():
    load_dotenv()
    uri = os.getenv("MONGO_URI")
    db_name = os.getenv("DB_NAME", "recovery_agent")
    
    print(f"Connecting to: {uri[:15]}...")
    client = AsyncIOMotorClient(uri)
    
    try:
        # Check connection
        await client.admin.command('ping')
        print("✅ MongoDB connection successful.")
        
        db = client[db_name]
        
        # 1. Total users
        users = await db['users'].find().to_list(100)
        print(f"DEBUG: Found {len(users)} users in collection 'users'")
        for u in users:
            print(f"  - User: {u.get('email')} (is_admin: {u.get('email') == 'imexperiment4@gmail.com'})")
            
        admin = await db['users'].find_one({"email": "imexperiment4@gmail.com"})
        if not admin:
            print("❌ CRITICAL: Admin 'imexperiment4@gmail.com' not found in database!")
            return

        # 2. Assign invoices
        total_inv = await db['invoices'].count_documents({})
        admin_inv = await db['invoices'].count_documents({"owner_id": admin["_id"]})
        print(f"DEBUG: System Total Invoices: {total_inv}")
        print(f"DEBUG: Admin Account Invoices: {admin_inv}")
        
        if admin_inv == 0 and total_inv > 0:
            print("Action: Assigning all system-wide invoices to Admin...")
            result = await db['invoices'].update_many(
                {}, 
                {"$set": {"owner_id": admin["_id"]}}
            )
            print(f"✅ Successfully assigned {result.modified_count} invoices to Admin.")
        elif total_inv == 0:
            print("⚠️ No invoices found in 'invoices' collection to assign.")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(check())
