"""Bounded shared scenario history. PostgreSQL in production, SQLite for local demos."""
import hashlib
import logging
import os
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (Boolean, Column, MetaData, String, Table, Text, create_engine, delete,
                        event, func, inspect, select, text)
from app.config.settings import settings
from app.observability import record_db_slow_query

logger = logging.getLogger(__name__)

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
    # Phase 19: recorded but not enforced - an unverified account keeps working, the UI can prompt.
    Column("email_verified", Boolean, nullable=False, default=False),
    # Set on every password change. Tokens carry the value they were issued under, so a reset
    # retires every session that predates it without a server-side session table.
    Column("password_changed_at", String(40), nullable=True),
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

# Phase 19: single-use account tokens. Only a SHA-256 digest is stored, so a database read cannot
# be replayed into a working verification or reset link.
email_tokens = Table("email_tokens", metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(36), nullable=False, index=True),
    Column("purpose", String(16), nullable=False),
    Column("token_hash", String(64), nullable=False, unique=True, index=True),
    Column("created_at", String(40), nullable=False),
    Column("expires_at", String(40), nullable=False),
    Column("used_at", String(40), nullable=True),
)
# Phase 19: read-only public links to one saved scenario. The token is hashed for the same reason.
share_links = Table("share_links", metadata,
    Column("id", String(36), primary_key=True),
    Column("scenario_id", String(36), nullable=False, index=True),
    Column("owner_id", String(36), nullable=False, index=True),
    Column("token_hash", String(64), nullable=False, unique=True, index=True),
    Column("created_at", String(40), nullable=False),
    Column("expires_at", String(40), nullable=False),
    Column("revoked_at", String(40), nullable=True),
)
# Phase 19: per-account security history. Event kinds only - no address, no IP, no free text.
audit_events = Table("audit_events", metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(36), nullable=False, index=True),
    Column("kind", String(40), nullable=False),
    Column("detail", String(200), nullable=False, default=""),
    Column("created_at", String(40), nullable=False),
)


class DatabaseConfigurationError(RuntimeError):
    """The configured database cannot be opened, and the reason is safe to show an operator.

    `reason` is a short code the readiness endpoint and the error handler can pass on: "blank" is
    resolved before this point, so what remains is a scheme the driver cannot use, a filesystem
    that refuses the SQLite file, or a server that will not answer. None of them includes the URL
    itself, which may carry a password.
    """

    def __init__(self, reason: str, detail: str):
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


def _url_scheme(url: str) -> str:
    return url.split("://", 1)[0] if "://" in url else "unset"


# Advisory lock that serialises the startup DDL across processes. A `threading.Lock` only covers
# threads inside one worker; two workers on the same database each ran create_all, and PostgreSQL
# rejected the loser with `duplicate key value violates unique constraint "pg_type_typname_nsp_index"`.
SCHEMA_LOCK_KEY = 0x5A5A_2026

# Bounded wait for that lock. A deploy that cannot take it within the window refuses to start
# half-migrated, which is a clear log line, rather than racing another worker.
MIGRATION_LOCK_TIMEOUT_S = float(os.environ.get("SPACEAGRISIM_MIGRATION_LOCK_TIMEOUT_S", "30") or 30)

# Statements slower than this are counted and logged by verb and duration only. Parameters are
# where addresses, hashes and free text live, so neither the text nor the parameters are logged.
SLOW_QUERY_MS = float(os.environ.get("SPACEAGRISIM_SLOW_QUERY_MS", "250") or 250)


# One lock for engine construction. `lru_cache` is not atomic around a slow function, and
# building an engine runs `CREATE TABLE IF NOT EXISTS` for every table: two threads arriving on a
# cold start - or at the first request after a restart - both miss the cache, both run create_all,
# and PostgreSQL rejects the loser with a duplicate-key error on a catalog index. That surfaced as
# a real failure in the concurrency test, not as a theoretical one.
_ENGINE_LOCK = threading.Lock()


def database():
    """The process-wide engine, built at most once even under concurrent first use."""
    if _build_database.cache_info().currsize:
        return _build_database()
    with _ENGINE_LOCK:
        return _build_database()


@lru_cache(maxsize=1)
def _build_database():
    url = settings.database_url_resolved
    if url.startswith("sqlite:///"):
        name = url.removeprefix("sqlite:///")
        if name != ":memory:":
            try:
                Path(name).parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise DatabaseConfigurationError(
                    "path-unwritable",
                    f"the SQLite directory could not be created ({type(exc).__name__})",
                ) from exc
    if not (url.startswith("sqlite:///") or url.startswith("postgresql+psycopg://")):
        raise DatabaseConfigurationError(
            "scheme-unsupported",
            f"database URL scheme {_url_scheme(url)!r} is not supported; "
            "use sqlite:/// or a PostgreSQL URL",
        )
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
    _install_slow_query_logging(engine)
    _initialise_schema(engine)
    return engine


def _install_slow_query_logging(engine) -> None:
    """Log slow statements by operation and duration, never by text or parameters.

    Parameters are where addresses, hashes and free text live, so they are not logged. The
    operation verb is enough to tell a slow read from a slow write, and the duration is the
    signal that matters. Errors are counted separately by `observability`.
    """
    if getattr(engine, "_spaceagrisim_timed", False):
        return

    @event.listens_for(engine, "before_cursor_execute")
    def _before(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        context._spaceagrisim_started = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        started = getattr(context, "_spaceagrisim_started", None)
        if started is None:
            return
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if elapsed_ms >= SLOW_QUERY_MS:
            operation = (statement or "").split(" ", 1)[0].upper()[:12]
            record_db_slow_query(operation, elapsed_ms)
            logger.warning("slow database statement: %s took %.0f ms", operation, elapsed_ms)

    engine._spaceagrisim_timed = True  # type: ignore[attr-defined]


def _initialise_schema(engine) -> None:
    """Create the schema and apply the additive migrations, once, across every worker.

    Serialised with a PostgreSQL advisory lock so a multi-instance rollout cannot have two
    workers running `create_all` at the same moment. On SQLite there is only one process by
    definition for this deployment, so the in-process lock is sufficient.
    """
    if engine.dialect.name != "postgresql":
        _apply_schema(engine)
        return
    with engine.connect() as connection:
        # A dedicated connection holds the lock; DDL runs on it so the lock covers the DDL.
        acquired = connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": SCHEMA_LOCK_KEY}).scalar()
        waited = 0.0
        while not acquired and waited < MIGRATION_LOCK_TIMEOUT_S:
            time.sleep(0.25)
            waited += 0.25
            acquired = connection.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": SCHEMA_LOCK_KEY}).scalar()
        if not acquired:
            raise DatabaseConfigurationError(
                "migration-lock-timeout",
                f"another process held the schema lock for more than "
                f"{MIGRATION_LOCK_TIMEOUT_S:.0f}s; refusing to start half-migrated")
        try:
            _apply_schema(engine)
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"),
                               {"key": SCHEMA_LOCK_KEY})


def _apply_schema(engine) -> None:
    metadata.create_all(engine)
    _migrate_scenarios_owner(engine)
    _migrate_users_columns(engine)


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
    # `index=True` in the Table definition only creates the index with the table. On a database
    # that predates the column, the ALTER adds it without one, and every owner-scoped query then
    # scans the table. IF NOT EXISTS makes this repeatable on both dialects.
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_scenarios_owner_id ON scenarios (owner_id)"))


def _migrate_users_columns(engine) -> None:
    """Add the Phase 19 account columns to a database created before them.

    Idempotent and additive only: existing rows keep working, unverified accounts stay usable
    (verification is recorded, not enforced), and no data is rewritten.
    """
    columns = {column["name"] for column in inspect(engine).get_columns("users")}
    for name, ddl in (("email_verified", "BOOLEAN"),
                      ("password_changed_at", "VARCHAR(40)")):
        if name in columns:
            continue
        with engine.begin() as connection:
            connection.execute(text(f"ALTER TABLE users ADD COLUMN {name} {ddl}"))


def dispose_database() -> None:
    """Close the pooled engine and forget it, so the next call builds a new one.

    This is what an application restart does to the storage layer. It exists as a named function
    rather than a `cache_clear()` in each test so the restart-equivalent persistence test exercises
    the same path production takes: pool disposed, engine rebuilt, schema re-verified, rows read
    back from the server rather than from a connection that was never closed.
    """
    with _ENGINE_LOCK:
        if _build_database.cache_info().currsize:
            _build_database().dispose()
        _build_database.cache_clear()


def _driver_diagnosis(exc: BaseException) -> dict[str, str]:
    """Non-secret fragments of a connection failure that actually narrow it down.

    A psycopg SQLSTATE separates "wrong password" (28P01) from "no such database" (3D000) from
    "host unreachable" (08006 ...), and none of those codes carries a host or a credential. The
    message itself is deliberately not included: psycopg puts the address in it.
    """
    diagnosis = {"exceptionType": type(exc).__name__}
    for source in (exc, getattr(exc, "orig", None)):
        code = getattr(source, "sqlstate", None) or getattr(source, "pgcode", None)
        if code:
            diagnosis["sqlstate"] = str(code)
            break
    return diagnosis


# The tables every persistence path needs. A readiness check that only runs SELECT 1 reports a
# reachable but uninitialised database as available, and then every account, history and share
# route fails while the health probe stays green - which is exactly the incident Phase 19 fixed
# for connectivity and this closes for schema.
REQUIRED_TABLES = ("scenarios", "users", "analyses", "revoked_tokens", "email_tokens",
                   "share_links", "audit_events")


# ---------------------------------------------------------------------------------------------
# Migration registry
#
# Every schema step this project has ever needed is listed here with the condition that proves it
# applied. Nothing rewrites or drops data, so the list is a record of additive steps and the
# inspection below is read-only: it never runs DDL, which is what makes it safe to expose on a
# production readiness endpoint.
# ---------------------------------------------------------------------------------------------
MIGRATIONS = (
    {
        "id": "0001-initial-schema",
        "description": "Create the seven tables the API reads and writes.",
        "requires": {"tables": REQUIRED_TABLES},
    },
    {
        "id": "0002-scenarios-owner-id",
        "description": "Add scenarios.owner_id for per-account history.",
        "requires": {"columns": {"scenarios": ("owner_id",)}},
    },
    {
        "id": "0003-users-phase19-columns",
        "description": "Add users.email_verified and users.password_changed_at.",
        "requires": {"columns": {"users": ("email_verified", "password_changed_at")}},
    },
    {
        "id": "0004-scenarios-owner-index",
        "description": "Index scenarios.owner_id so owner-scoped queries do not scan the table.",
        "requires": {"indexes": {"scenarios": ("ix_scenarios_owner_id",)}},
    },
)


def migration_state() -> dict:
    """Read-only: which registered migrations have applied, and which have not.

    A deployment that skipped a step reports it here instead of failing later on a query the
    schema cannot answer. This runs no DDL and writes nothing.
    """
    engine = database()
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    columns: dict[str, set[str]] = {}
    indexes: dict[str, set[str]] = {}
    for table in REQUIRED_TABLES:
        if table not in tables:
            continue
        columns[table] = {column["name"] for column in inspector.get_columns(table)}
        indexes[table] = {index["name"] for index in inspector.get_indexes(table)}

    applied, pending = [], []
    for migration in MIGRATIONS:
        requires = migration["requires"]
        missing: list[str] = []
        for table in requires.get("tables", ()):  # pragma: no branch - one entry today
            if table not in tables:
                missing.append(f"table {table}")
        for table, names in requires.get("columns", {}).items():
            if table not in tables:
                missing.append(f"table {table}")
                continue
            missing.extend(f"column {table}.{name}" for name in names
                           if name not in columns.get(table, set()))
        for table, names in requires.get("indexes", {}).items():
            if table not in tables:
                missing.append(f"table {table}")
                continue
            missing.extend(f"index {table}.{name}" for name in names
                           if name not in indexes.get(table, set()))
        entry = {"id": migration["id"], "description": migration["description"]}
        if missing:
            pending.append({**entry, "missing": missing})
        else:
            applied.append(entry)
    return {"applied": applied, "pending": pending, "appliedCount": len(applied),
            "pendingCount": len(pending), "total": len(MIGRATIONS)}


def pool_status() -> dict:
    """Connection-pool state, without the URL. Safe to report to an operator.

    `exhausted` is the condition that turns into a burst of 500s under load: every pooled
    connection is checked out and the overflow allowance is spent, so the next request waits and
    then fails with a pool timeout.
    """
    engine = database()
    if engine.dialect.name != "postgresql":
        # SQLite is this project's single-process store; its pool has no meaningful capacity
        # story, and reporting one invites a reader to treat it as a production pool.
        return {"dialect": engine.dialect.name, "pooled": False,
                "note": "single-process store; pool capacity is not a production concern"}
    pool = engine.pool
    try:
        size = pool.size()
        checked_out = pool.checkedout()
        overflow = pool.overflow()
    except (AttributeError, NotImplementedError):
        return {"dialect": engine.dialect.name, "pooled": False}
    max_overflow = getattr(pool, "_max_overflow", None)
    capacity = size + max(0, max_overflow) if isinstance(max_overflow, int) else None
    return {
        "dialect": engine.dialect.name,
        "pooled": True,
        "size": size,
        "checkedOut": checked_out,
        "overflow": overflow,
        "capacity": capacity,
        "exhausted": bool(capacity is not None and checked_out >= capacity),
        "note": "per worker process; capacity is pool_size + max_overflow",
    }


def classify_db_failure(exc: BaseException) -> str | None:
    """Name the failure class of a database exception, or None if it is not a database exception.

    Four classes cover what an operator actually acts on, and each maps to a different fix:
    `pool-timeout` (capacity), `connect` (the server or its credentials), `integrity` (a request
    or code path), `other` (everything else). The exception message is never returned: psycopg
    puts the host and, on a bad password, the user in it.
    """
    from sqlalchemy import exc as sa_exc

    if isinstance(exc, sa_exc.TimeoutError):
        return "pool-timeout"
    if isinstance(exc, sa_exc.IntegrityError):
        return "integrity"
    if isinstance(exc, (sa_exc.OperationalError, sa_exc.InterfaceError, sa_exc.DisconnectionError)):
        return "connect"
    if isinstance(exc, sa_exc.SQLAlchemyError):
        return "other"
    return None


def database_health() -> dict[str, str]:
    """No-write health check: connectivity *and* the schema the API actually queries.

    `SELECT 1` proves a socket answered. It does not prove the tables exist, so a fresh or
    half-migrated database would be reported ready and then fail on first use. This inspects the
    tables as well, which is read-only and costs one catalog query per call.
    """
    engine = database()
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
        present = set(inspect(connection).get_table_names())
    missing = [name for name in REQUIRED_TABLES if name not in present]
    return {
        "dialect": engine.dialect.name,
        "status": "unavailable" if missing else "available",
        "schema": "incomplete" if missing else "present",
        "missingTables": ",".join(missing),
    }

def storage_durability() -> dict:
    """Whether saved data survives a restart, in the operator's terms.

    A serverless deployment that keeps SQLite under /tmp is durable for exactly as long as the
    container lives. That is worth stating in the readiness payload instead of documenting it
    only in a README: it is the difference between "your account exists" and "your account
    existed until the last cold start".
    """
    url = settings.database_url_resolved
    dialect = "postgresql" if url.startswith("postgresql+") else "sqlite"
    if dialect == "postgresql":
        return {"dialect": dialect, "durable": True,
                "reason": "Rows live in a PostgreSQL database that outlives the application process.",
                "remedy": ""}
    path = url.removeprefix("sqlite:///")
    # Not a temp-file creation: this is a string comparison against the configured database URL,
    # used to tell the operator whether their data will survive a redeploy.
    volatile = path == ":memory:" or path.startswith("/tmp") or path.startswith("/var/tmp")  # nosec B108
    if volatile:
        return {"dialect": dialect, "durable": False,
                "reason": "SQLite file lives under /tmp, which a serverless platform discards",
                "remedy": "Set SPACEAGRISIM_DATABASE_URL to a postgresql+psycopg:// URL; "
                          "see docs/POSTGRESQL_OPERATIONS.md"}
    return {"dialect": dialect, "durable": True,
            "reason": "SQLite file is on a persistent path, but a managed PostgreSQL database is "
                      "still the recommended production store.",
            "remedy": ""}


def list_scenarios(owner_id: str | None = None):
    statement = select(scenarios).order_by(scenarios.c.created_at.desc()).limit(settings.max_history)
    if owner_id is not None:
        statement = statement.where(scenarios.c.owner_id == owner_id)
    with database().connect() as connection:
        return [dict(row._mapping) for row in connection.execute(statement)]

def get_scenario(owner_id: str, scenario_id: str):
    """One scenario, scoped to its owner.

    Returns None for another account's id rather than 403, for the same reason the analysis
    accessor does: a distinguishable answer is an existence oracle.
    """
    if not owner_id:
        raise ValueError("owner_id is required")
    with database().connect() as connection:
        row = connection.execute(select(scenarios).where(
            (scenarios.c.id == scenario_id) & (scenarios.c.owner_id == owner_id))).first()
    return dict(row._mapping) if row else None


def update_scenario(owner_id: str, scenario_id: str, *,
                    name: str | None = None, configuration: str | None = None):
    """Rename and/or replace one owned scenario. Returns the stored row, or None if not owned.

    The WHERE clause carries the owner, so the update can never touch another account's row: a
    scoped read followed by an unscoped write would be a race that hands one account another's
    scenario. Nothing is written when neither field is supplied.
    """
    if not owner_id:
        raise ValueError("owner_id is required")
    changes: dict[str, str] = {}
    if name is not None:
        changes["name"] = name
    if configuration is not None:
        changes["configuration"] = configuration
    if not changes:
        return get_scenario(owner_id, scenario_id)
    with database().begin() as connection:
        result = connection.execute(
            scenarios.update()
            .where((scenarios.c.id == scenario_id) & (scenarios.c.owner_id == owner_id))
            .values(**changes))
        if not result.rowcount:
            return None
        row = connection.execute(select(scenarios).where(scenarios.c.id == scenario_id)).first()
    return dict(row._mapping) if row else None


def delete_scenario(owner_id: str, scenario_id: str) -> bool:
    """Delete one owned scenario and every share link that pointed at it.

    The share links are removed in the same transaction, because a link that survives its
    scenario is a dangling reference that resolves to nothing and cannot be revoked from a
    page that no longer exists.
    """
    if not owner_id:
        raise ValueError("owner_id is required")
    with database().begin() as connection:
        owned = connection.execute(select(scenarios.c.id).where(
            (scenarios.c.id == scenario_id) & (scenarios.c.owner_id == owner_id))).first()
        if owned is None:
            return False
        connection.execute(delete(share_links).where(
            (share_links.c.scenario_id == scenario_id)
            & (share_links.c.owner_id == owner_id)))
        connection.execute(delete(scenarios).where(
            (scenarios.c.id == scenario_id) & (scenarios.c.owner_id == owner_id)))
    return True


def save_scenario(name: str, configuration: str, owner_id: str | None = None):
    row = {"id": str(uuid4()), "name": name,
           "created_at": datetime.now(timezone.utc).isoformat(),
           "configuration": configuration, "model_version": "assumptions-2.0", "owner_id": owner_id}
    with database().begin() as connection:
        connection.execute(scenarios.insert().values(**row))
        # Retention trims the owner's own history. Trimming globally would delete the oldest rows
        # in the table regardless of who owns them, so one active account could evict another
        # account's data - a persistence bug that only shows up once there are two accounts.
        expired_statement = select(scenarios.c.id)
        if owner_id is not None:
            expired_statement = expired_statement.where(scenarios.c.owner_id == owner_id)
        else:
            expired_statement = expired_statement.where(scenarios.c.owner_id.is_(None))
        expired = connection.execute(
            expired_statement.order_by(scenarios.c.created_at.desc())
            .offset(settings.max_history)).scalars().all()
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
    # Bandit's B105 matches the *column name* `password_hash`; the value stored is whatever hash the
    # caller produced, never a literal. Marked on the reported line so the marker and the finding
    # are in the same place.
    row = {"id": str(uuid4()), "email": email, "password_hash": password_hash,  # nosec B105
           "created_at": datetime.now(timezone.utc).isoformat(), "disabled": False,
           "email_verified": False, "password_changed_at": None}
    with database().begin() as connection:
        connection.execute(users.insert().values(**row))
    return row


def revoke_token(jti: str, expires_at: str) -> None:
    with database().begin() as connection:
        connection.execute(revoked_tokens.insert().values(jti=jti, expires_at=expires_at))


def token_is_revoked(jti: str) -> bool:
    with database().connect() as connection:
        return connection.execute(select(revoked_tokens.c.jti).where(revoked_tokens.c.jti == jti)).first() is not None


# ---------------------------------------------------------------------------------------------
# Phase 19 accessors: account tokens, password change, share links, activity
# ---------------------------------------------------------------------------------------------

class ShareLimitReached(Exception):
    def __init__(self, limit: int):
        super().__init__("Share link limit reached for this scenario")
        self.limit = limit


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_account_token(user_id: str, purpose: str, ttl_minutes: int) -> str:
    """Create a single-use token and return it. Only its hash is stored.

    Any earlier unused token for the same purpose is invalidated first, so a second request
    cannot leave two live reset links behind.
    """
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    with database().begin() as connection:
        connection.execute(email_tokens.update()
                           .where((email_tokens.c.user_id == user_id)
                                  & (email_tokens.c.purpose == purpose)
                                  & (email_tokens.c.used_at.is_(None)))
                           .values(used_at=now.isoformat()))
        connection.execute(email_tokens.insert().values(
            id=str(uuid4()), user_id=user_id, purpose=purpose, token_hash=_hash_token(token),
            created_at=now.isoformat(),
            expires_at=(now + timedelta(minutes=ttl_minutes)).isoformat(), used_at=None))
    return token


def consume_account_token(token: str, purpose: str):
    """Mark a token used and return its user id, or None when it is unknown/expired/used.

    Consumption happens inside one transaction that checks `used_at IS NULL`, so two concurrent
    submissions of the same link cannot both succeed.
    """
    digest = _hash_token(token)
    now = datetime.now(timezone.utc).isoformat()
    with database().begin() as connection:
        row = connection.execute(select(email_tokens.c.id, email_tokens.c.user_id)
                                 .where((email_tokens.c.token_hash == digest)
                                        & (email_tokens.c.purpose == purpose)
                                        & (email_tokens.c.used_at.is_(None))
                                        & (email_tokens.c.expires_at > now))).first()
        if row is None:
            return None
        updated = connection.execute(email_tokens.update()
                                     .where((email_tokens.c.id == row.id)
                                            & (email_tokens.c.used_at.is_(None)))
                                     .values(used_at=now))
        if not updated.rowcount:
            return None
    return row.user_id


def mark_email_verified(user_id: str) -> None:
    with database().begin() as connection:
        connection.execute(users.update().where(users.c.id == user_id).values(email_verified=True))


def set_password(user_id: str, password_hash: str) -> str:
    """Replace the password hash and stamp the change time. Returns the stamp.

    The stamp goes into the new token as `pwd` and is compared on every request, which is how a
    password reset invalidates sessions that were issued before it.
    """
    stamp = datetime.now(timezone.utc).isoformat()
    with database().begin() as connection:
        connection.execute(users.update().where(users.c.id == user_id)
                           .values(password_hash=password_hash, password_changed_at=stamp))
    return stamp


def create_share_link(scenario_id: str, owner_id: str, ttl_days: int) -> str:
    """Mint one read-only share token for a scenario the caller owns.

    Returns None when the scenario does not belong to the caller, and raises ShareLimitReached
    when the per-scenario cap is already used, so neither case can be reported as success.
    """
    with database().begin() as connection:
        owned = connection.execute(select(scenarios.c.id).where(
            (scenarios.c.id == scenario_id) & (scenarios.c.owner_id == owner_id))).first()
        if owned is None:
            return None
        live = connection.execute(select(func.count(share_links.c.id)).where(
            (share_links.c.scenario_id == scenario_id)
            & (share_links.c.revoked_at.is_(None))
            & (share_links.c.expires_at > datetime.now(timezone.utc).isoformat()))).scalar_one()
        if int(live) >= settings.max_share_links_per_scenario:
            raise ShareLimitReached(settings.max_share_links_per_scenario)
        token = secrets.token_urlsafe(24)
        now = datetime.now(timezone.utc)
        connection.execute(share_links.insert().values(
            id=str(uuid4()), scenario_id=scenario_id, owner_id=owner_id,
            token_hash=_hash_token(token), created_at=now.isoformat(),
            expires_at=(now + timedelta(days=ttl_days)).isoformat(), revoked_at=None))
    return token


def resolve_share_link(token: str):
    """The shared scenario for a token, or None if unknown, revoked or expired.

    Returns only what the public view needs: no owner id and no account data.
    """
    digest = _hash_token(token)
    now = datetime.now(timezone.utc).isoformat()
    with database().connect() as connection:
        row = connection.execute(
            select(scenarios.c.name, scenarios.c.configuration, scenarios.c.created_at,
                   scenarios.c.model_version, share_links.c.expires_at)
            .select_from(share_links.join(scenarios, share_links.c.scenario_id == scenarios.c.id))
            .where((share_links.c.token_hash == digest)
                   & (share_links.c.revoked_at.is_(None))
                   & (share_links.c.expires_at > now))).first()
    return dict(row._mapping) if row else None


def revoke_share_links(scenario_id: str, owner_id: str) -> int:
    """Revoke every live link for one owned scenario. Returns how many were revoked."""
    with database().begin() as connection:
        result = connection.execute(
            share_links.update()
            .where((share_links.c.scenario_id == scenario_id)
                   & (share_links.c.owner_id == owner_id)
                   & (share_links.c.revoked_at.is_(None)))
            .values(revoked_at=datetime.now(timezone.utc).isoformat()))
    return int(result.rowcount or 0)


def record_activity(user_id: str, kind: str, detail: str = "") -> None:
    """Append one security-relevant event and trim the account's history to the cap."""
    if not user_id:
        return
    now = datetime.now(timezone.utc)
    with database().begin() as connection:
        connection.execute(audit_events.insert().values(
            id=str(uuid4()), user_id=user_id, kind=kind, detail=detail[:200],
            created_at=now.isoformat()))
        stale = connection.execute(
            select(audit_events.c.id).where(audit_events.c.user_id == user_id)
            .order_by(audit_events.c.created_at.desc())
            .offset(settings.max_activity_events)).scalars().all()
        if stale:
            connection.execute(delete(audit_events).where(audit_events.c.id.in_(stale)))


def list_activity(user_id: str, limit: int = 50):
    with database().connect() as connection:
        rows = connection.execute(
            select(audit_events.c.kind, audit_events.c.detail, audit_events.c.created_at)
            .where(audit_events.c.user_id == user_id)
            .order_by(audit_events.c.created_at.desc()).limit(max(1, min(limit, 200)))).all()
    return [dict(row._mapping) for row in rows]


def list_recent_activity(limit: int = 100):
    """Newest events across every account, for the operator audit view.

    Returns user_id because the caller pseudonymises it before anything leaves the process; this
    function is never wired to a public route.
    """
    with database().connect() as connection:
        rows = connection.execute(
            select(audit_events.c.user_id, audit_events.c.kind, audit_events.c.detail,
                   audit_events.c.created_at)
            .order_by(audit_events.c.created_at.desc()).limit(max(1, min(limit, 500)))).all()
    return [dict(row._mapping) for row in rows]


def activity_summary() -> dict:
    """Aggregate counts an operator can read without seeing a single account."""
    now = datetime.now(timezone.utc).isoformat()
    with database().connect() as connection:
        accounts = connection.execute(select(func.count(users.c.id))).scalar_one()
        by_kind = dict(connection.execute(
            select(audit_events.c.kind, func.count(audit_events.c.id))
            .group_by(audit_events.c.kind)).all())
        live_links = connection.execute(select(func.count(share_links.c.id)).where(
            (share_links.c.revoked_at.is_(None)) & (share_links.c.expires_at > now))).scalar_one()
    return {"accounts": int(accounts), "liveShareLinks": int(live_links),
            "byKind": {key: int(value) for key, value in sorted(by_kind.items())}}


def read_json_artifact(name: str):
    """Read one metadata artifact out of the active data directory, or None when absent."""
    from app.research import DATA
    path = DATA / "metadata" / name
    if not path.is_file():
        return None
    import json
    return json.loads(path.read_text())


# Older call sites (tests, backup tooling) drop the memoised engine with `database.cache_clear()`.
# `database()` is no longer an lru_cache wrapper itself, so the attributes are carried over: the
# same call now disposes the pool as well, which is what those callers always meant by "forget the
# engine".
database.cache_clear = dispose_database  # type: ignore[attr-defined]
database.cache_info = _build_database.cache_info  # type: ignore[attr-defined]
