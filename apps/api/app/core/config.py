"""
Central config — all env vars live here, never os.environ elsewhere.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    SECRET_KEY: str  # used for JWT signing — required, no default

    # ── CORS ──────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # ── Database ──────────────────────────────────────────────────────────
    DATABASE_URL: str  # asyncpg DSN, e.g. postgresql+asyncpg://...

    # ── Supabase ──────────────────────────────────────────────────────────
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str  # never expose to frontend

    # ── Stripe (optional until billing is wired up) ───────────────────────
    STRIPE_SECRET_KEY: str | None = Field(default=None)
    STRIPE_WEBHOOK_SECRET: str | None = Field(default=None)
    STRIPE_BILLING_PRICE_ID: str | None = Field(default=None)

    # ── Redis / BullMQ ────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    # ── Email (optional until email is wired up) ──────────────────────────
    RESEND_API_KEY: str | None = Field(default=None)
    EMAIL_FROM: str = "noreply@invoicesaas.com"

    # ── Frontend ──────────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
