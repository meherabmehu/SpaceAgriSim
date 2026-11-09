"""Multi-worker readiness: schema initialisation, migration registry, pooling, slow queries.

These tests cover the failure modes that only appear once more than one worker or instance opens
the same database at the same moment:

* two workers running the schema bootstrap concurrently (advisory lock),
* a deployment that reaches a database whose schema is behind (readiness must say so, not "ready"),
* a pool that is exhausted or misreported,
* slow statements, which must be counted without logging the statement or its parameters.

The PostgreSQL-only tests skip when ``SPACEAGRISIM_TEST_POSTGRES_URL`` is unset; the harness that
runs them is described in ``docs/PRODUCTION_READINESS_AUDIT.md``.
"""
from __future__ import annotations

import json
import os
import threading

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app import observability, storage


# --------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------
def _postgres_url() -> str | None:
    """The test DSN, normalised the same way the app normalises a platform URL."""
    raw = os.environ.get("SPACEAGRISIM_TEST_POSTGRES_URL", "").strip()
    if not raw:
        return None
    from app.config.settings import resolve_database_url

    return resolve_database_url(raw, raw)


requires_postgres = pytest.mark.skipif(
    _postgres_url() is None,
    reason="SPACEAGRISIM_TEST_POSTGRES_URL is not set; PostgreSQL-only assertion",
)


@pytest.fixture()
def scratch_engine(tmp_path, monkeypatch):
    """A private SQLite database, exposed as ``storage.database()`` for the duration of a test."""
    engine = create_engine(f"sqlite:///{tmp_path}/scratch.db", future=True)
    monkeypatch.setattr(storage, "database", lambda: engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def postgres_engine():
    url = _postgres_url()
    if url is None:
        pytest.skip("SPACEAGRISIM_TEST_POSTGRES_URL is not set")
    engine = create_engine(url, future=True)
    yield engine
    engine.dispose()


# --------------------------------------------------------------------------------------------
# Migration registry
# --------------------------------------------------------------------------------------------
def test_migration_registry_is_ordered_unique_and_described():
    ids = [migration["id"] for migration in storage.MIGRATIONS]
    assert len(ids) == len(set(ids)), f"duplicate migration id: {ids}"
    # Zero-padded prefixes make the deploy order readable and keep sorting honest once there are
    # more than nine steps.
    prefixes = [int(migration_id.split("-", 1)[0]) for migration_id in ids]
    assert prefixes == sorted(prefixes) == list(range(1, len(ids) + 1))
    for migration in storage.MIGRATIONS:
        assert migration["description"].strip()
        assert migration["requires"], migration["id"]


def test_registry_covers_every_required_table_and_ownership_column():
    """The first migration creates the tables; later ones are the additive steps this repo made."""
    first = storage.MIGRATIONS[0]
    assert set(first["requires"]["tables"]) == set(storage.REQUIRED_TABLES)
    column_requirements = {
        (table, column)
        for migration in storage.MIGRATIONS
        for table, columns in migration["requires"].get("columns", {}).items()
        for column in columns
    }
    # Ownership scoping is the one column a deployment can be missing and still answer /health.
    assert ("scenarios", "owner_id") in column_requirements


def test_fresh_schema_reports_every_migration_applied(scratch_engine):
    storage._apply_schema(scratch_engine)
    state = storage.migration_state()
    assert state["pendingCount"] == 0, state["pending"]
    assert state["appliedCount"] == state["total"] == len(storage.MIGRATIONS)


def test_empty_database_reports_the_initial_migration_as_pending(scratch_engine):
    state = storage.migration_state()
    assert state["appliedCount"] == 0
    assert [item["id"] for item in state["pending"]] == [
        migration["id"] for migration in storage.MIGRATIONS]
    missing = {entry for item in state["pending"] for entry in item["missing"]}
    assert "table scenarios" in missing
    # Read-only: inspecting an empty database must not create anything.
    with scratch_engine.connect() as connection:
        tables = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")).scalars().all()
    assert tables == []


def test_missing_owner_index_is_reported_as_its_own_pending_migration(scratch_engine):
    storage._apply_schema(scratch_engine)
    with scratch_engine.begin() as connection:
        connection.execute(text("DROP INDEX ix_scenarios_owner_id"))
    state = storage.migration_state()
    assert [item["id"] for item in state["pending"]] == ["0004-scenarios-owner-index"]
    assert state["pending"][0]["missing"] == ["index scenarios.ix_scenarios_owner_id"]
    assert state["appliedCount"] == state["total"] - 1


def test_apply_schema_is_repeatable_and_non_destructive(scratch_engine):
    storage._apply_schema(scratch_engine)
    with scratch_engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO scenarios (id, name, configuration, model_version, created_at, owner_id) "
            "VALUES ('scn-keep', 'keep me', '{}', 'v3', '2026-01-01T00:00:00Z', 'user-1')"))
    storage._apply_schema(scratch_engine)
    storage._apply_schema(scratch_engine)
    with scratch_engine.connect() as connection:
        rows = connection.execute(text("SELECT id FROM scenarios")).scalars().all()
    assert rows == ["scn-keep"]
    assert storage.migration_state()["pendingCount"] == 0


# --------------------------------------------------------------------------------------------
# Pool reporting
# --------------------------------------------------------------------------------------------
def test_pool_status_describes_sqlite_without_inventing_capacity(scratch_engine):
    status = storage.pool_status()
    assert status["dialect"] == "sqlite"
    assert status["pooled"] is False
    assert "note" in status
    # A fake "size 5, overflow -4" reading would invite treating a single-file store as a pool.
    assert "size" not in status


@requires_postgres
def test_pool_status_reports_postgres_capacity(postgres_engine, monkeypatch):
    monkeypatch.setattr(storage, "database", lambda: postgres_engine)
    status = storage.pool_status()
    assert status["dialect"] == "postgresql"
    assert status["pooled"] is True
    assert status["capacity"] >= status["size"] >= 1
    assert status["checkedOut"] >= 0
    assert status["exhausted"] is False
    # The URL carries the password; nothing derived from it may reach an operator surface.
    assert "password" not in json.dumps(status).lower()


# --------------------------------------------------------------------------------------------
# Advisory lock: the multi-worker case
# --------------------------------------------------------------------------------------------
@requires_postgres
def test_schema_bootstrap_waits_for_a_lock_held_elsewhere_then_fails_clearly(postgres_engine,
                                                                          monkeypatch):
    """A second worker must not run DDL underneath the first one.

    It either waits for the lock or refuses to start. Silently continuing produces the duplicate
    ``pg_type`` failures this project already hit once during engine construction.
    """
    holder = create_engine(_postgres_url(), future=True)
    monkeypatch.setattr(storage, "MIGRATION_LOCK_TIMEOUT_S", 0.6)
    with holder.connect() as connection:
        assert connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": storage.SCHEMA_LOCK_KEY}).scalar() is True
        try:
            with pytest.raises(storage.DatabaseConfigurationError) as caught:
                storage._initialise_schema(postgres_engine)
            assert caught.value.reason == "migration-lock-timeout"
            assert "held the schema lock" in caught.value.detail
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"),
                               {"key": storage.SCHEMA_LOCK_KEY})
    holder.dispose()
    # With the lock released the same call succeeds, so the failure was the lock and not the DDL.
    storage._initialise_schema(postgres_engine)
    assert storage.migration_state()["pendingCount"] == 0


@requires_postgres
def test_concurrent_workers_bootstrap_the_schema_once(monkeypatch):
    """Eight workers starting together against one empty database: no error, one schema."""
    url = _postgres_url()
    admin = create_engine(url, future=True, isolation_level="AUTOCOMMIT")
    schema = f"worker_race_{os.getpid()}_{threading.get_ident() % 1000:03d}"
    with admin.connect() as connection:
        connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))

    engines = [create_engine(url, future=True,
                             connect_args={"options": f"-csearch_path={schema}"}) for _ in range(8)]
    errors: list[BaseException] = []
    started = threading.Barrier(8)

    def bootstrap(engine):
        try:
            started.wait(timeout=30)
            storage._initialise_schema(engine)
        except BaseException as exc:  # noqa: BLE001 - reported through the assertion below
            errors.append(exc)

    threads = [threading.Thread(target=bootstrap, args=(engine,)) for engine in engines]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)

    try:
        assert errors == [], [f"{type(e).__name__}: {e}" for e in errors]
        with engines[0].connect() as connection:
            tables = connection.execute(text(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema = :schema"),
                {"schema": schema}).scalar()
        assert tables >= len(storage.REQUIRED_TABLES)
    finally:
        for engine in engines:
            engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


# --------------------------------------------------------------------------------------------
# Slow-query diagnostics
# --------------------------------------------------------------------------------------------
def test_slow_statement_is_counted_without_logging_sql_or_parameters(scratch_engine, monkeypatch,
                                                                     caplog):
    observability.reset_database_counters()
    monkeypatch.setattr(storage, "SLOW_QUERY_MS", 0.0)
    storage._install_slow_query_logging(scratch_engine)
    with scratch_engine.begin() as connection:
        connection.execute(text("SELECT :secret AS value"), {"secret": "user@example.com"})

    snapshot = observability.database_snapshot()
    assert snapshot["slowQueryCount"] >= 1
    assert snapshot["slowQueries"].get("SELECT", 0) >= 1

    logged = "\n".join(record.getMessage() for record in caplog.records
                       if "slow database statement" in record.getMessage())
    assert logged, "a slow statement must be logged when it crosses the threshold"
    assert "SELECT" in logged
    # The point of the reduced log line: the statement text and its parameters stay out of logs.
    assert "user@example.com" not in logged
    assert "SELECT :secret" not in logged
    observability.reset_database_counters()


def test_fast_statement_is_not_counted_as_slow(scratch_engine, monkeypatch, caplog):
    observability.reset_database_counters()
    monkeypatch.setattr(storage, "SLOW_QUERY_MS", 60_000.0)
    storage._install_slow_query_logging(scratch_engine)
    with scratch_engine.begin() as connection:
        connection.execute(text("SELECT 1"))
    assert observability.database_snapshot()["slowQueryCount"] == 0
    assert "slow database statement" not in caplog.text


def test_database_failures_are_counted_by_class(scratch_engine):
    observability.reset_database_counters()
    observability.record_db_failure("connect")
    observability.record_db_failure("connect")
    observability.record_db_failure("pool-timeout")
    failures = observability.database_snapshot()["failures"]
    assert failures == {"connect": 2, "pool-timeout": 1}
    observability.reset_database_counters()


# --------------------------------------------------------------------------------------------
# Readiness surface
# --------------------------------------------------------------------------------------------
def test_readiness_reports_migration_and_pool_detail(client):
    response = client.get("/api/ready")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ready"
    migrations = body["databaseMigrations"]
    assert migrations["total"] == len(storage.MIGRATIONS)
    assert migrations["pending"] == 0
    assert migrations["applied"] == migrations["total"]
    assert "pooled" in body["databasePool"]


def test_readiness_refuses_to_serve_a_deployment_with_a_pending_migration(client, monkeypatch):
    """The probe turned green is exactly how a half-migrated deploy serves 500s unnoticed."""
    monkeypatch.setattr(storage, "migration_state", lambda: {
        "applied": [], "pending": [{"id": "0002-scenarios-owner-id",
                                    "description": "Add scenarios.owner_id",
                                    "missing": ["column scenarios.owner_id"]}],
        "appliedCount": 0, "pendingCount": 1, "total": 4})
    observability.reset_database_counters()
    response = client.get("/api/ready")
    assert response.status_code == 503, response.text
    body = response.json()["detail"]
    assert body["error"] == "database_migration_pending"
    assert body["pendingMigrations"] == ["0002-scenarios-owner-id"]
    assert body["missing"] == ["column scenarios.owner_id"]
    assert "remedy" in body


def test_readiness_reports_schema_incomplete_separately_from_migration_state(client, monkeypatch):
    monkeypatch.setattr(storage, "database_health", lambda: {
        "dialect": "sqlite", "status": "degraded", "schema": "incomplete",
        "missingTables": "scenarios,users"})
    response = client.get("/api/ready")
    assert response.status_code == 503, response.text
    detail = response.json()["detail"]
    assert detail["error"] == "database_schema_incomplete"
    assert detail["missingTables"] == ["scenarios", "users"]
    # The headline is "the schema was never created", but the pending steps still ride along so a
    # single response tells the operator both what is wrong and what has to run.
    assert isinstance(detail["pendingMigrations"], list)


def test_readiness_counts_a_connection_failure_without_leaking_the_url(client, monkeypatch):
    observability.reset_database_counters()

    def explode():
        raise OperationalError("SELECT 1", {}, Exception("connection to 10.0.0.5:5432 failed"))

    monkeypatch.setattr(storage, "database_health", explode)
    response = client.get("/api/ready")
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["error"] == "database_unavailable"
    assert "10.0.0.5" not in json.dumps(detail)
    assert observability.database_snapshot()["failures"].get("connect") == 1
    observability.reset_database_counters()


def test_metrics_expose_database_counters(client):
    observability.reset_database_counters()
    observability.record_db_slow_query("UPDATE", 900.0)
    body = client.get("/api/metrics").json()
    database = body["metrics"]["database"]
    assert database["slowQueries"] == {"UPDATE": 1}
    assert "failures" in database
    observability.reset_database_counters()


# --------------------------------------------------------------------------------------------
# Failure classification (used by the request middleware for unhandled database errors)
# --------------------------------------------------------------------------------------------
def test_db_failure_classes_map_to_an_operator_action():
    from sqlalchemy import exc as sa_exc

    assert storage.classify_db_failure(sa_exc.TimeoutError("pool exhausted")) == "pool-timeout"
    assert storage.classify_db_failure(
        sa_exc.IntegrityError("INSERT", {}, Exception("duplicate key"))) == "integrity"
    assert storage.classify_db_failure(
        sa_exc.OperationalError("SELECT 1", {}, Exception("could not connect"))) == "connect"
    assert storage.classify_db_failure(sa_exc.ProgrammingError("SELECT", {}, Exception("x"))) \
        == "other"
    # A non-database exception is not counted as a database failure.
    assert storage.classify_db_failure(ValueError("nope")) is None


def test_unhandled_database_error_is_counted_and_still_raised():
    """The middleware classifies and re-raises; callers still see the original failure."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import exc as sa_exc

    from app.middleware import RequestGuard

    inner = FastAPI()

    @inner.get("/boom")
    def boom():
        raise sa_exc.OperationalError("SELECT 1", {}, Exception("connection to 10.0.0.5 failed"))

    observability.reset_database_counters()
    guarded = RequestGuard(inner, max_per_minute=1000, optimize_per_minute=1000)
    with pytest.raises(sa_exc.OperationalError):
        TestClient(guarded).get("/boom")
    assert observability.database_snapshot()["failures"] == {"connect": 1}
    observability.reset_database_counters()
