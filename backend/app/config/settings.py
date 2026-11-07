"""
Runtime settings for the API (not simulation constants - those live in
app/config/simulation_constants.py).

Values can be overridden through environment variables, e.g.
    SPACEAGRISIM_CORS_ORIGINS='["http://localhost:5173"]'
"""

import os
import secrets
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SPACEAGRISIM_", env_file=".env", extra="ignore")

    app_name: str = "SpaceAgriSim API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    database_url: str = "sqlite:////tmp/spaceagrisim/scenarios.db" if os.environ.get('VERCEL') else "sqlite:///.spaceagrisim/scenarios.db"
    history_writes_enabled: bool = not bool(os.environ.get('VERCEL'))
    max_history: int = Field(default=200, ge=1, le=10000)
    database_pool_size: int = Field(default=5, ge=1, le=30)
    database_max_overflow: int = Field(default=5, ge=0, le=30)

    # Set a durable high-entropy value through the host's secret manager. The
    # ephemeral fallback makes local development usable but invalidates tokens
    # at restart and is intentionally never suitable for multi-instance use.
    auth_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(48), min_length=32)
    auth_token_minutes: int = Field(default=60, ge=5, le=1440)
    auth_rate_limit_per_minute: int = Field(default=30, ge=1, le=60)

    # Origins allowed to call the API from a browser. The Vite dev server
    # proxies /api so this mostly matters when the frontend is served elsewhere.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("cors_origins")
    @classmethod
    def explicit_cors_origins(cls, origins: list[str]) -> list[str]:
        if not origins or any(origin == "*" or "*" in origin for origin in origins):
            raise ValueError("CORS origins must be explicit; wildcards are not permitted")
        if any(not origin.startswith(("https://", "http://localhost", "http://127.0.0.1")) for origin in origins):
            raise ValueError("CORS origins must use HTTPS outside local development")
        return origins


settings = Settings()
