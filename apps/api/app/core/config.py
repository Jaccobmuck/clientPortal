"""
Central config — all env vars live here, never os.environ elsewhere.
"""

from functools import lru_cache
from typing import Literal

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

    # ── Stripe ────────────────────────────────────────────────────────────
    STRIPE_SECRET_KEY: str           # sk_test_... or sk_live_...
    STRIPE_WEBHOOK_SECRET: str       # whsec_...
    STRIPE_BILLING_PRICE_ID: str     # price_... for the SaaS subscription

    # ── Redis / BullMQ ────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"

    # ── Email ─────────────────────────────────────────────────────────────
    RESEND_API_KEY: str
    EMAIL_FROM: str = "noreply@invoicesaas.com"

    # ── Frontend ──────────────────────────────────────────────────────────
    FRONTEND_URL: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
