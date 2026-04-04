"""
RecoveryAgent — database lifecycle helper.
Initialises and tears down the Motor async client.
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    if _client is None:
        raise RuntimeError("Database client has not been initialised yet.")
    return _client


def get_database() -> AsyncIOMotorDatabase:
    return get_client()[settings.db_name]


def get_collection(name: str):
    """Return a Motor collection by name from the active database."""
    return get_database()[name]



async def connect_db() -> None:
    """Create the Motor client and verify connectivity."""
    global _client
    _client = AsyncIOMotorClient(settings.mongo_uri)
    await _client.admin.command("ping")


async def close_db() -> None:
    """Close the Motor client gracefully."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
