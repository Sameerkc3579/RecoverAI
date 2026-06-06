"""
RecoverAI — Application Configuration (Security-Hardened)

All settings are loaded from environment variables / .env file.
SECURITY RULES:
  - secret_key has NO default fallback — startup fails if not set (fail-secure)
  - admin_emails loaded from env, not hardcoded in source
  - debug mode defaults to False (safe default)
"""
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Gemini ────────────────────────────────────────────────────────────────
    gemini_api_key: str

    # ── MongoDB ───────────────────────────────────────────────────────────────
    mongo_uri: str
    db_name: str = "recovery_agent"

    # ── WhatsApp Cloud API ──────────────────────────────────────────────────────
    whatsapp_api_token: str = ""           # Legacy field kept for compatibility
    whatsapp_verify_token: str = ""        # Your chosen secret for Meta webhook verification
    whatsapp_webhook_secret: str = ""      # HMAC secret Meta uses to sign POST bodies
    whatsapp_phone_number_id: str = ""     # Meta Phone Number ID (from Developer Console)
    whatsapp_access_token: str = ""        # Meta System User permanent access token
    whatsapp_auto_reply: bool = False      # Set True to enable automatic intent-based replies

    # ── JWT Auth ──────────────────────────────────────────────────────────────
    # NO default fallback — startup CRASHES if SECRET_KEY is not in .env
    # This is intentional fail-secure design. If you see this error:
    #   ValidationError: secret_key — Field required
    # → You must set SECRET_KEY in your .env file.
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15      # Short-lived access tokens (15 min)
    refresh_token_expire_days: int = 7         # Refresh tokens valid for 7 days

    # ── Application ───────────────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:3000,http://localhost:5173,http://localhost:8000"
    debug: bool = False                        # Defaults to False — safe production default

    # ── Google OAuth ──────────────────────────────────────────────────────────
    google_client_id: str = ""

    # ── Admin Access ──────────────────────────────────────────────────────────
    # Comma-separated list of admin email addresses.
    # Example: ADMIN_EMAILS=admin@yourcompany.com,backup-admin@yourcompany.com
    admin_emails: str = ""

    # ── File Upload ───────────────────────────────────────────────────────────
    max_upload_size_mb: int = 10

    # ── Webhook Security ──────────────────────────────────────────────────────
    webhook_secret: str = ""   # HMAC secret for verifying external webhook calls

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters long. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(64))\""
            )
        return v

    @property
    def origins_list(self) -> list[str]:
        """Return ALLOWED_ORIGINS as a parsed list."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def admin_emails_list(self) -> list[str]:
        """Return ADMIN_EMAILS as a parsed lowercase list."""
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]

    @property
    def is_production(self) -> bool:
        """True when debug mode is off — used to gate sensitive features."""
        return not self.debug


# Singleton — import this everywhere
settings = Settings()
