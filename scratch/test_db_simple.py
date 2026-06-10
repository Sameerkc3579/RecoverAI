
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

async def test_db():
    load_dotenv()
    uri = os.getenv("MONGO_URI")
    print(f"Connecting to: {uri}")
    client = AsyncIOMotorClient(uri)
    try:
        print("Pinging...")
        await client.admin.command("ping")
        print("Ping successful!")
    except Exception as e:
        print(f"Ping failed: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(test_db())
