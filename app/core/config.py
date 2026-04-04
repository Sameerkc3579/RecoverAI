"""
RecoveryAgent — application configuration.
All settings are loaded from environment variables / .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Gemini
    gemini_api_key: str

    # MongoDB
    mongo_uri: str
    db_name: str = "recovery_agent"

    # WhatsApp
    whatsapp_api_token: str = ""

    # JWT Auth
    secret_key: str = "f7a3b8e1d94c42a6bc5ef0d1238976ab5c4d3e2f1a0b9c8d7e6f5a4b3c2d1e0f"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    # Application
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"
    debug: bool = False
    
    # Google OAuth
    google_client_id: str = ""

    @property
    def origins_list(self) -> list[str]:
        """Return ALLOWED_ORIGINS as a parsed list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


# Singleton — import this everywhere
settings = Settings()
