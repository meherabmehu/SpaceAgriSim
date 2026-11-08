"""Bounded shared scenario history. PostgreSQL in production, SQLite for local demos."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (Boolean, Column, MetaData, String, Table, Text, create_engine, delete,
                        func, inspect, select, text)
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
# Phase 12: saved AI analyses. Kept separate from `scenarios` because an analysis is a
# model inference with its citations, not a habitat configuration, and the two have
# different retention and export semantics.
analyses = Table("analyses", metadata,
    Column("id", String(36), primary_key=True),
    # Never nullable: an analysis always belongs to an authenticated account. There is
    # no legacy row to migrate, so there is no reason to permit an orphan.
    Column("owner_id", String(36), nullable=False, index=True),
    Column("model_id", String(64), nullable=False),
    Column("title", String(120), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("payload", Text, nullable=False),
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


class AnalysisQuotaExceeded(Exception):
    """Raised when saving would exceed a per-account limit. Carries the numbers for the caller."""

    def __init__(self, code: str, message: str, **detail):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail


def _lock_owner(connection, owner_id: str) -> None:
    """Serialise quota accounting for one account, without depending on the dialect.

    Two concurrent saves could otherwise both read "199 of 200 used" and both insert. A no-op
    UPDATE on the owner row takes a row lock in PostgreSQL and the database write lock in SQLite,
    so the second transaction waits and then re-reads a count that includes the first.
    """
    connection.execute(users.update().where(users.c.id == owner_id)
                       .values(created_at=users.c.created_at))


def analysis_usage(owner_id: str) -> dict:
    """Current count and byte usage for one account."""
    if not owner_id:
        raise ValueError("owner_id is required")
    statement = (select(func.count(analyses.c.id),
                        func.coalesce(func.sum(func.length(analyses.c.payload)), 0))
                 .where(analyses.c.owner_id == owner_id))
    with database().connect() as connection:
        count, used = connection.execute(statement).one()
    return {"count": int(count), "bytes": int(used),
            "maxCount": settings.max_analyses_per_user,
            "maxBytes": settings.max_analysis_bytes_per_user}


def list_analyses(owner_id: str, limit: int | None = None, offset: int = 0):
    """One page of an account's analyses, newest first, with the account-wide total.

    The owner filter is never optional and never derived from the request body.
    """
    if not owner_id:
        raise ValueError("owner_id is required to list analyses")
    page_size = max(1, min(int(limit or settings.max_analyses_page_size),
                           settings.max_analyses_page_size))
    page_offset = max(0, int(offset or 0))
    statement = (select(analyses).where(analyses.c.owner_id == owner_id)
                 .order_by(analyses.c.created_at.desc(), analyses.c.id.desc())
                 .limit(page_size).offset(page_offset))
    total_statement = select(func.count(analyses.c.id)).where(analyses.c.owner_id == owner_id)
    with database().connect() as connection:
        rows = [dict(row._mapping) for row in connection.execute(statement)]
        total = int(connection.execute(total_statement).scalar_one())
    return rows, total, {"limit": page_size, "offset": page_offset, "total": total,
                         "hasMore": page_offset + len(rows) < total}


def save_analysis(owner_id: str, model_id: str, title: str, payload: str):
    """Insert one analysis, enforcing size and per-account quotas inside the transaction."""
    if not owner_id:
        raise ValueError("owner_id is required to save an analysis")
    payload_bytes = len(payload.encode("utf-8"))
    if payload_bytes > settings.max_analysis_bytes:
        raise AnalysisQuotaExceeded(
            "payload-too-large", "Analysis payload is too large to save",
            bytes=payload_bytes, limit=settings.max_analysis_bytes)
    row = {"id": str(uuid4()), "owner_id": owner_id, "model_id": model_id,
           "title": title, "created_at": datetime.now(timezone.utc).isoformat(),
           "payload": payload}
    with database().begin() as connection:
        _lock_owner(connection, owner_id)
        count, used = connection.execute(
            select(func.count(analyses.c.id),
                   func.coalesce(func.sum(func.length(analyses.c.payload)), 0))
            .where(analyses.c.owner_id == owner_id)).one()
        if int(count) >= settings.max_analyses_per_user:
            raise AnalysisQuotaExceeded(
                "quota-count", "Saved-analysis limit reached for this account",
                count=int(count), limit=settings.max_analyses_per_user)
        if int(used) + payload_bytes > settings.max_analysis_bytes_per_user:
            raise AnalysisQuotaExceeded(
                "quota-bytes", "Saved-analysis storage limit reached for this account",
                bytes=int(used) + payload_bytes, limit=settings.max_analysis_bytes_per_user)
        connection.execute(analyses.insert().values(**row))
    return row


def purge_expired_analyses(now: datetime | None = None) -> int:
    """Delete analyses past the retention window. Returns the number removed.

    Retention is off unless `analysis_retention_days` is positive, so the default behaviour for
    an existing deployment is unchanged: nothing is deleted.
    """
    if settings.analysis_retention_days <= 0:
        return 0
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=settings.analysis_retention_days)
    with database().begin() as connection:
        result = connection.execute(delete(analyses).where(analyses.c.created_at < cutoff.isoformat()))
    return int(result.rowcount or 0)


def delete_all_analyses(owner_id: str) -> int:
    """Delete every analysis for one account. Scoped by owner, like every other accessor."""
    if not owner_id:
        raise ValueError("owner_id is required")
    with database().begin() as connection:
        result = connection.execute(delete(analyses).where(analyses.c.owner_id == owner_id))
    return int(result.rowcount or 0)


def get_analysis(owner_id: str, analysis_id: str):
    """Fetch one analysis, scoped to its owner.

    Returning None for another user's id is deliberate: a 403 would confirm that the
    id exists, which is an enumeration oracle.
    """
    with database().connect() as connection:
        row = connection.execute(select(analyses).where(
            (analyses.c.id == analysis_id) & (analyses.c.owner_id == owner_id))).first()
    return dict(row._mapping) if row else None


def delete_analysis(owner_id: str, analysis_id: str) -> bool:
    with database().begin() as connection:
        result = connection.execute(delete(analyses).where(
            (analyses.c.id == analysis_id) & (analyses.c.owner_id == owner_id)))
    return bool(result.rowcount)


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
