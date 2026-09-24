from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration.

    Secrets are read from the environment.  The development defaults exist only to make
    the local demo runnable; production startup rejects the development JWT secret.
    """

    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "MATRIVA API"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = False

    # SQLite keeps the API runnable without Docker.  Production should use PostgreSQL.
    database_url: str = "sqlite:///./matriva.db"
    redis_url: str = "redis://localhost:6379/0"
    vector_database_url: str | None = None
    auto_create_tables: bool = True

    # Auth
    jwt_secret: str = Field(default="dev-only-change-me-please-use-32-plus-chars", min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "matriva-api"
    jwt_audience: str = "matriva-clients"
    jwt_expires_minutes: int = Field(default=30, ge=5, le=1440)

    # Browser clients.  Comma-separated in environment variables.
    cors_origins: str = "http://localhost:3000"

    # R0 demo routes are intentionally disabled by setting DEMO_MODE=false in production.
    demo_mode: bool = True

    # Limits
    max_message_chars: int = Field(default=4000, ge=100, le=20000)
    max_upload_bytes: int = Field(default=10_000_000, ge=100_000, le=50_000_000)
    rate_limit_auth_per_minute: int = Field(default=20, ge=1, le=1000)
    rate_limit_chat_per_minute: int = Field(default=30, ge=1, le=1000)
    rate_limit_general_per_minute: int = Field(default=120, ge=1, le=5000)

    # Optional external providers
    llm_provider: str = "groq"
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-oss-120b"
    embedding_provider: str = "gemini"
    embedding_api_key: str = ""
    embedding_model: str = "models/gemini-embedding-001"

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_flag(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return False

    @field_validator("jwt_algorithm")
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        # Do not allow an algorithm selected from untrusted configuration.
        if value not in {"HS256", "HS384", "HS512"}:
            raise ValueError("jwt_algorithm must be an HMAC SHA-2 algorithm")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
