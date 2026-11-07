"""Bounded shared scenario history. PostgreSQL in production, SQLite for local demos."""
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Boolean, Column, MetaData, String, Table, Text, create_engine, delete, inspect, select, text
from app.config.settings import settings

metadata = MetaData()
scenarios = Table("scenarios", metadata,
    Column("id", String(36), primary_key=True),
    Column("name", String(100), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("configuration", Text, nullable=False),
    Column("model_version", String(60), nullable=False),
    # Nullable only to retain access to legacy local demonstration rows. New
    # API-created rows always receive an authenticated owner's id.
    Column("owner_id", String(36), nullable=True, index=True),
)
users = Table("users", metadata,
    Column("id", String(36), primary_key=True),
    Column("email", String(254), nullable=False, unique=True, index=True),
    Column("password_hash", Text, nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("disabled", Boolean, nullable=False, default=False),
)
revoked_tokens = Table("revoked_tokens", metadata,
    Column("jti", String(64), primary_key=True),
    Column("expires_at", String(40), nullable=False),
)

@lru_cache(maxsize=1)
def database():
    url = settings.database_url
    if url.startswith("sqlite:///"):
        name = url.removeprefix("sqlite:///")
        if name != ":memory:":
            Path(name).parent.mkdir(parents=True, exist_ok=True)
    if not (url.startswith("sqlite:///") or url.startswith("postgresql+psycopg://")):
        raise ValueError("Database URL must use sqlite:/// or postgresql+psycopg://")
    # pre-ping prevents a stale pooled PostgreSQL connection from surfacing as
    # an opaque scenario-save failure after an idle hosted deployment.
    engine = create_engine(
        url,
        pool_pre_ping=True,
        # SQLite cannot safely use a pooled connection across arbitrary
        # threads; PostgreSQL benefits from bounded reusable connections.
        **({"pool_size": settings.database_pool_size, "max_overflow": settings.database_max_overflow}
           if url.startswith("postgresql+") else {}),
    )
    metadata.create_all(engine)
    _migrate_scenarios_owner(engine)
    return engine


def _migrate_scenarios_owner(engine) -> None:
    """Idempotent migration for databases created before account ownership.

    The project uses a deliberately small schema. Recording the version avoids
    an undeclared manual SQL step while keeping existing SQLite demos usable.
    A production service should run this at deploy time with a migration-role
    credential, before serving application traffic.
    """
    columns = {column["name"] for column in inspect(engine).get_columns("scenarios")}
    if "owner_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE scenarios ADD COLUMN owner_id VARCHAR(36)"))


def database_health() -> dict[str, str]:
    """Perform a no-write health check without exposing connection details."""
    engine = database()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"dialect": engine.dialect.name, "status": "available"}

def list_scenarios(owner_id: str | None = None):
    statement = select(scenarios).order_by(scenarios.c.created_at.desc()).limit(settings.max_history)
    if owner_id is not None:
        statement = statement.where(scenarios.c.owner_id == owner_id)
    with database().connect() as connection:
        return [dict(row._mapping) for row in connection.execute(statement)]

def save_scenario(name: str, configuration: str, owner_id: str | None = None):
    row = {"id": str(uuid4()), "name": name,
           "created_at": datetime.now(timezone.utc).isoformat(),
           "configuration": configuration, "model_version": "assumptions-2.0", "owner_id": owner_id}
    with database().begin() as connection:
        connection.execute(scenarios.insert().values(**row))
        expired = connection.execute(select(scenarios.c.id).order_by(
            scenarios.c.created_at.desc()).offset(settings.max_history)).scalars().all()
        if expired:
            connection.execute(delete(scenarios).where(scenarios.c.id.in_(expired)))
    return row


def find_user_by_email(email: str):
    with database().connect() as connection:
        row = connection.execute(select(users).where(users.c.email == email)).first()
    return dict(row._mapping) if row else None


def create_user(email: str, password_hash: str):
    row = {"id": str(uuid4()), "email": email, "password_hash": password_hash,
           "created_at": datetime.now(timezone.utc).isoformat(), "disabled": False}
    with database().begin() as connection:
        connection.execute(users.insert().values(**row))
    return row


def revoke_token(jti: str, expires_at: str) -> None:
    with database().begin() as connection:
        connection.execute(revoked_tokens.insert().values(jti=jti, expires_at=expires_at))


def token_is_revoked(jti: str) -> bool:
    with database().connect() as connection:
        return connection.execute(select(revoked_tokens.c.jti).where(revoked_tokens.c.jti == jti)).first() is not None
