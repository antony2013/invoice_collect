from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

logger = logging.getLogger(__name__)

Environment = Literal["development", "test", "production"]

_INSECURE_SECRET_PREFIXES = ("change-me", "secret", "changeme", "default", "password")


class Settings(BaseSettings):
    """Application settings, loaded from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Invoice Management API"
    environment: Environment = "development"
    debug: bool = True
    log_level: str = "info"

    api_v1_prefix: str = "/api/v1"
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    secret_key: str = "change-me"
    access_token_expire_minutes: int = 1440

    database_url: str = "sqlite:///./data/app.db"

    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "invoice-files"
    minio_secure: bool = False

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

    @model_validator(mode="after")
    def _validate_production_settings(self) -> Settings:
        if self.environment == "production":
            if self.debug:
                logger.warning(
                    "DEBUG is enabled in production — disabling for safety"
                )
                self.debug = False
            secret_lower = self.secret_key.lower().strip()
            if (
                len(self.secret_key) < 32
                or any(secret_lower.startswith(p) for p in _INSECURE_SECRET_PREFIXES)
            ):
                raise ValueError(
                    "SECRET_KEY must be at least 32 characters and not a "
                    "default/insecure value in production. Generate one with: "
                    "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
                )
        return self

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            if value.startswith("["):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
