from functools import lru_cache
from typing import Literal

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigPresence(BaseModel):
    name: str
    present: bool


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    ENVIRONMENT: Literal["development", "production"] = "development"
    DEBUG: bool = False
    ENABLE_SMOKE_TESTS: bool = False
    SECRET_KEY: str
    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_SERVICE_ROLE_KEY: str
    REDIS_URL: str = "redis://localhost:6379"
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    FREE_TIER_ORG_LIMIT: int = 1
    RECEIPT_BUCKET: str = "receipts"
    RECEIPT_MAX_SIZE_MB: int = 10
    RESEND_API_KEY: str | None = None
    RESEND_FROM_EMAIL: str | None = None
    SMOKE_TEST_EMAIL: str = "jacobmuck2004@gmail.com"
    STRIPE_SECRET_KEY: str | None = None
    RECEIPT_ALLOWED_TYPES: list[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
    ]

    def config_presence(self, names: list[str]) -> list[ConfigPresence]:
        return [
            ConfigPresence(
                name=name,
                present=bool(value) and bool(str(value).strip()),
            )
            for name in names
            for value in [getattr(self, name, None)]
        ]

    def required_config_presence(self) -> list[ConfigPresence]:
        required_names = [
            name for name, field in type(self).model_fields.items() if field.is_required()
        ]
        return self.config_presence(required_names)

    def required_config_ready(self) -> bool:
        return all(check.present for check in self.required_config_presence())

    def smoke_config_presence(self) -> list[ConfigPresence]:
        return self.config_presence(
            [
                "REDIS_URL",
                "RESEND_API_KEY",
                "RESEND_FROM_EMAIL",
                "SMOKE_TEST_EMAIL",
                "STRIPE_SECRET_KEY",
            ]
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
