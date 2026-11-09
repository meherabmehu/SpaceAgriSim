"""
Runtime settings for the API (not simulation constants - those live in
app/config/simulation_constants.py).

Values can be overridden through environment variables, e.g.
    SPACEAGRISIM_CORS_ORIGINS='["http://localhost:5173"]'
"""

import logging
import os
import secrets
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# One ephemeral secret per process. Before Phase 13 the fallback was generated per Settings
# instance, which meant two workers of the same deployment could disagree about what a valid
# token was. A process-local value is still wrong for a multi-process deployment - it is just
# consistently wrong instead of randomly wrong - which is why production now refuses to start
# without a real secret (see Settings.require_persistent_auth_secret).
_EPHEMERAL_AUTH_SECRET = secrets.token_urlsafe(48)

# Values that look deliberate but are not secret. Rejecting them is cheap; discovering that a
# deployment signed tokens with "changeme" is not.
AUTH_SECRET_REJECTED = {
    "changeme", "change-me", "changemeplease", "secret", "secretkey", "password", "passw0rd",
    "development", "dev", "dev-secret", "development-secret", "test", "testing", "example",
    "placeholder", "insecure", "spaceagrisim", "spaceagrisim-secret", "your-secret",
    "your-secret-here", "replace-me", "todo", "none", "null", "default",
}


def _validate_auth_secret(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    if len(candidate) < 32:
        raise ValueError(f"{field} must be at least 32 characters; use a random value, not a password")
    if len(set(candidate)) < 12:
        raise ValueError(f"{field} has too little entropy; generate it with secrets.token_urlsafe(48)")
    if candidate.lower() in AUTH_SECRET_REJECTED:
        raise ValueError(f"{field} is a known placeholder value")
    return candidate


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SPACEAGRISIM_", env_file=".env", extra="ignore")

    app_name: str = "SpaceAgriSim API"
    app_version: str = "0.1.0"
    api_prefix: str = "/api"
    database_url: str = "sqlite:////tmp/spaceagrisim/scenarios.db" if os.environ.get('VERCEL') else "sqlite:///.spaceagrisim/scenarios.db"
    history_writes_enabled: bool = not bool(os.environ.get('VERCEL'))
    max_history: int = Field(default=200, ge=1, le=10000)

    # ---------------------------------------------------------------- Phase 19: accounts
    # Transactional email for verification and password reset. With no host configured the
    # service either uses a development outbox (non-production) or refuses the request with an
    # explicit 503 (production). See app/mailer.py.
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    email_verification_hours: int = Field(default=24, ge=1, le=168)
    password_reset_minutes: int = Field(default=30, ge=5, le=1440)
    # Public origin used to build the links people receive. The app routes on the fragment, so the
    # link is `<public_app_url>/#reset?token=…`, which loads on a static host without a rewrite.
    public_app_url: str = "http://localhost:5173"

    # Sharing a saved scenario is a per-account capability; this bounds how many live links one
    # scenario may have so a client cannot mint an unbounded number of tokens.
    max_share_links_per_scenario: int = Field(default=3, ge=1, le=20)
    share_link_days: int = Field(default=30, ge=1, le=365)
    max_activity_events: int = Field(default=200, ge=10, le=5000)
    # Operator surface (/admin/*). Unset means the endpoints are not offered at all (404), so a
    # public deployment does not advertise a panel nobody configured. This is a separate
    # credential from any account: an operator should not need - or get - a login.
    admin_token: str = ""
    database_pool_size: int = Field(default=5, ge=1, le=30)
    database_max_overflow: int = Field(default=5, ge=0, le=30)

    # development | test | staging | production. A hosting platform that sets VERCEL is treated
    # as production unless the operator says otherwise, because that is where the ephemeral
    # fallback would silently invalidate every token on each restart.
    environment: Literal["development", "test", "staging", "production"] = Field(
        default_factory=lambda: "production" if os.environ.get("VERCEL") else "development")

    # Set a durable high-entropy value through the host's secret manager, e.g.
    # SPACEAGRISIM_AUTH_SECRET=$(python -c "import secrets;print(secrets.token_urlsafe(48))").
    # Unset in development means one ephemeral value per process: usable, and documented as
    # invalid across restarts. Unset in production is a startup failure, not a warning.
    auth_secret: str | None = None
    # Rotation window: tokens signed with the previous secret still verify, so a deployment can
    # roll the secret without logging every user out at once. Remove it once the longest token
    # lifetime (auth_token_minutes) has passed. See docs/PHASE13_PRODUCTION_READINESS.md.
    auth_secret_previous: str | None = None

    # Saved-analysis quotas. Enforced inside the write transaction, not by a client-side count.
    max_analyses_per_user: int = Field(default=200, ge=1, le=100_000)
    max_analysis_bytes: int = Field(default=1_000_000, ge=1024, le=50_000_000)
    max_analysis_bytes_per_user: int = Field(default=20_000_000, ge=1024, le=2_000_000_000)
    max_analyses_page_size: int = Field(default=50, ge=1, le=500)
    # 0 keeps analyses forever. A positive value enables the retention sweep.
    analysis_retention_days: int = Field(default=0, ge=0, le=3650)
    auth_token_minutes: int = Field(default=60, ge=5, le=1440)
    auth_rate_limit_per_minute: int = Field(default=30, ge=1, le=60)
    # General per-IP request budget. The default is the production value; the
    # browser suite raises it through the environment because a single page load
    # legitimately issues several API calls and a full E2E run would otherwise
    # trip its own guard and fail on unrelated assertions.
    general_rate_limit_per_minute: int = Field(default=180, ge=1, le=100000)
    # Phase 19: how many reverse proxies sit in front of this service. The per-address request
    # guard is worthless behind a managed gateway unless it reads the client address from the
    # forwarding chain - every visitor otherwise shares the proxy's address, so one caller can
    # spend the whole budget. Set to 1 for a single gateway (Vercel/Render/nginx). Zero means
    # forwarded headers are ignored, which is correct when the service is exposed directly: a
    # client can forge X-Forwarded-For and reset its own budget per request.
    trusted_proxy_hops: int = Field(default=0, ge=0, le=5)

    # Origins allowed to call the API from a browser. The Vite dev server
    # proxies /api so this mostly matters when the frontend is served elsewhere.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @field_validator("auth_secret", "auth_secret_previous")
    @classmethod
    def strong_auth_secret(cls, value: str | None, info) -> str | None:
        return _validate_auth_secret(value, info.field_name)

    @model_validator(mode="after")
    def require_persistent_auth_secret(self):
        """Fail fast rather than sign tokens with a secret the next worker will not share."""
        if self.environment != "production":
            if self.auth_secret is None:
                logger.warning(
                    "SPACEAGRISIM_AUTH_SECRET is not set; using a process-local ephemeral secret. "
                    "Issued tokens become invalid on restart and are not shared between workers.")
            return self
        if self.auth_secret is None:
            raise ValueError(
                "SPACEAGRISIM_AUTH_SECRET must be set when SPACEAGRISIM_ENVIRONMENT=production. "
                "Generate one with: python -c 'import secrets;print(secrets.token_urlsafe(48))' "
                "and store it in the host's secret manager.")
        if self.auth_secret_previous is not None and self.auth_secret_previous == self.auth_secret:
            raise ValueError("auth_secret_previous must differ from auth_secret")
        return self

    @property
    def resolved_auth_secret(self) -> str:
        """The secret to sign with: the configured one, or the documented ephemeral fallback."""
        return self.auth_secret or _EPHEMERAL_AUTH_SECRET

    @property
    def auth_secrets_for_verification(self) -> list[str]:
        """Newest first. Rotation keeps the old secret verifying until it is removed."""
        secrets_in_order = [self.resolved_auth_secret]
        if self.auth_secret and self.auth_secret_previous:
            secrets_in_order.append(self.auth_secret_previous)
        return secrets_in_order

    @property
    def auth_secret_is_persistent(self) -> bool:
        return self.auth_secret is not None

    @field_validator("cors_origins")
    @classmethod
    def explicit_cors_origins(cls, origins: list[str]) -> list[str]:
        if not origins or any(origin == "*" or "*" in origin for origin in origins):
            raise ValueError("CORS origins must be explicit; wildcards are not permitted")
        if any(not origin.startswith(("https://", "http://localhost", "http://127.0.0.1")) for origin in origins):
            raise ValueError("CORS origins must use HTTPS outside local development")
        return origins


settings = Settings()
