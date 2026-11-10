"""PostgreSQL persistence tests: real server, isolated schema, restart-equivalent reads.

These are the tests the persistence claim rests on. They run against an actual PostgreSQL server
when `SPACEAGRISIM_TEST_POSTGRES_URL` is set and skip cleanly when it is not, so the ordinary suite
stays runnable without a database server - but a skip is not a pass, and the CI job that matters
provisions PostgreSQL so these execute rather than skip.

Isolation is by schema, not by database name:

* one schema per test, named `persistence_test_<random>`, created before the engine opens;
* every connection from this module carries `search_path` for that schema, so `create_all` builds
  tables there and the server's `public` schema - which is what a real deployment uses - is never
  read, written or dropped;
* teardown drops only that schema, with CASCADE, and only if its name carries the test prefix.

Nothing here can reach production: the URL is explicitly a test database, the schema is generated,
and the teardown refuses to drop anything it did not create.
"""

from __future__ import annotations

import json
import os
import threading
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from app import storage
from app.config.settings import settings

POSTGRES_TEST_URL = os.getenv("SPACEAGRISIM_TEST_POSTGRES_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason=("Set SPACEAGRISIM_TEST_POSTGRES_URL=postgresql+psycopg://user:pass@host:5432/db to run "
            "the PostgreSQL persistence tests against an isolated schema"),
)

PASSWORD = "CorrectHorseBattery9!"


def _admin_engine():
    """An engine on the test database itself, with no search_path redirection."""
    return create_engine(POSTGRES_TEST_URL, pool_pre_ping=True)


@pytest.fixture
def pg_schema():
    """A throwaway schema in the supplied test database, and a URL that points the app at it.

    Function-scoped rather than module-scoped: rows written by one test must not be counted by the
    next. A shared schema made the retention test fail on rows an earlier test had left behind,
    which is a test-isolation bug that reads exactly like a persistence bug.
    """
    schema = f"persistence_test_{uuid.uuid4().hex[:10]}"
    admin = _admin_engine()
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = make_url(POSTGRES_TEST_URL)
    scoped = url.set(query={**dict(url.query), "options": f"-csearch_path={schema}"})
    scoped_url = scoped.render_as_string(hide_password=False)
    try:
        yield {"schema": schema, "url": scoped_url}
    finally:
        # Only ever drops a schema this fixture created, and only if it carries the prefix.
        if schema.startswith("persistence_test_"):
            with admin.begin() as connection:
                connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def pg(pg_schema, monkeypatch):
    """Point the application at the isolated schema and hand back a fresh engine each test."""
    storage.dispose_database()
    monkeypatch.setattr(settings, "database_url", pg_schema["url"], raising=False)
    monkeypatch.setattr(settings, "history_writes_enabled", True, raising=False)
    yield pg_schema
    storage.dispose_database()


# ---------------------------------------------------------------------------
# The configuration actually reaches PostgreSQL
# ---------------------------------------------------------------------------
def test_the_application_connects_to_postgresql_not_sqlite(pg):
    """The whole report depends on this: with a configured URL, nothing falls back to SQLite."""
    engine = storage.database()
    assert engine.dialect.name == "postgresql"
    health = storage.database_health()
    assert health["dialect"] == "postgresql"
    assert health["status"] == "available"
    assert health["schema"] == "present"
    # The tables live in the isolated schema, not in the server's public schema.
    with engine.connect() as connection:
        current = connection.execute(text("SHOW search_path")).scalar()
    assert pg["schema"] in current


def test_sqlite_is_not_in_the_url_the_server_sees(pg):
    assert storage.settings.database_url_resolved.startswith("postgresql+psycopg://")


# ---------------------------------------------------------------------------
# Scenario lifecycle
# ---------------------------------------------------------------------------
def _configuration(**overrides) -> str:
    body = {"crop": "lettuce", "simulationDays": 35, "radiation": 0.01,
            "waterAvailability": 100.0, "lightHours": 16.0, "co2Level": 420.0,
            "growingArea": 10.0, "earthComparisonMode": "matched", "lightIntensity": 400.0,
            "temperature": 22.0, "humidity": 65.0, "waterRecyclingEfficiency": 90.0,
            "lightSpectrum": "balanced"}
    body.update(overrides)
    return json.dumps(body)


def test_create_read_update_delete_round_trip(pg):
    owner = str(uuid.uuid4())
    created = storage.save_scenario("audit scenario", _configuration(), owner)
    assert created["owner_id"] == owner

    fetched = storage.get_scenario(owner, created["id"])
    assert fetched is not None
    assert fetched["name"] == "audit scenario"
    assert json.loads(fetched["configuration"])["simulationDays"] == 35

    updated = storage.update_scenario(owner, created["id"], name="audit scenario (edited)")
    assert updated["name"] == "audit scenario (edited)"
    assert storage.get_scenario(owner, created["id"])["name"] == "audit scenario (edited)"

    replaced = storage.update_scenario(owner, created["id"],
                                       configuration=_configuration(simulationDays=60))
    assert json.loads(storage.get_scenario(owner, created["id"])["configuration"])["simulationDays"] == 60
    assert replaced["name"] == "audit scenario (edited)"  # a partial update keeps the other field

    assert storage.delete_scenario(owner, created["id"]) is True
    assert storage.get_scenario(owner, created["id"]) is None
    assert storage.delete_scenario(owner, created["id"]) is False


def test_ownership_is_enforced_on_read_update_and_delete(pg):
    alice, bob = str(uuid.uuid4()), str(uuid.uuid4())
    row = storage.save_scenario("alice private", _configuration(), alice)

    assert storage.get_scenario(bob, row["id"]) is None
    assert storage.update_scenario(bob, row["id"], name="stolen") is None
    assert storage.delete_scenario(bob, row["id"]) is False

    # Alice's row is untouched by any of the three attempts.
    still_there = storage.get_scenario(alice, row["id"])
    assert still_there["name"] == "alice private"


def test_listing_returns_only_the_callers_rows(pg):
    alice, bob = str(uuid.uuid4()), str(uuid.uuid4())
    storage.save_scenario("alice 1", _configuration(), alice)
    storage.save_scenario("bob 1", _configuration(), bob)
    alice_rows = storage.list_scenarios(alice)
    assert [row["name"] for row in alice_rows] == ["alice 1"]
    assert all(row["owner_id"] == alice for row in alice_rows)


def test_deleting_a_scenario_removes_its_share_links(pg):
    owner = str(uuid.uuid4())
    row = storage.save_scenario("shared", _configuration(), owner)
    token = storage.create_share_link(row["id"], owner, ttl_days=7)
    assert storage.resolve_share_link(token) is not None

    assert storage.delete_scenario(owner, row["id"]) is True
    # A link that outlived its scenario would resolve to nothing and could not be revoked.
    assert storage.resolve_share_link(token) is None
    with storage.database().connect() as connection:
        remaining = connection.execute(
            text("SELECT count(*) FROM share_links WHERE scenario_id = :sid"), {"sid": row["id"]}
        ).scalar()
    assert remaining == 0


def test_retention_trims_only_the_owners_history(pg, monkeypatch):
    """One active account must not be able to evict another account's rows."""
    monkeypatch.setattr(settings, "max_history", 2, raising=False)
    alice, bob = str(uuid.uuid4()), str(uuid.uuid4())
    storage.save_scenario("bob keeps this", _configuration(), bob)
    for index in range(4):
        storage.save_scenario(f"alice {index}", _configuration(), alice)

    assert [row["name"] for row in storage.list_scenarios(alice)] == ["alice 3", "alice 2"]
    assert [row["name"] for row in storage.list_scenarios(bob)] == ["bob keeps this"]
    with storage.database().connect() as connection:
        total = connection.execute(text("SELECT count(*) FROM scenarios")).scalar()
    assert total == 3


# ---------------------------------------------------------------------------
# Saved analyses (simulation results)
# ---------------------------------------------------------------------------
def _payload(model_id: str = "lettuce-earth-growth-v3") -> str:
    return json.dumps({"modelId": model_id, "inputs": {"daysAfterTransplant": 28},
                       "output": {"kind": "regression", "prediction": 123.4,
                                  "unit": "g fresh shoot mass per plant", "calibrated": False}})


def test_saved_analysis_round_trip(pg):
    owner = str(uuid.uuid4())
    storage.create_user(f"pg-{uuid.uuid4().hex[:8]}@example.com", "hash")
    row = storage.save_analysis(owner, "lettuce-earth-growth-v3", "analysis", _payload())
    fetched = storage.get_analysis(owner, row["id"])
    assert fetched is not None
    assert json.loads(fetched["payload"])["output"]["prediction"] == 123.4
    usage = storage.analysis_usage(owner)
    assert usage["count"] == 1

    assert storage.delete_analysis(owner, row["id"]) is True
    assert storage.get_analysis(owner, row["id"]) is None


def test_another_account_cannot_read_or_delete_an_analysis(pg):
    owner, other = str(uuid.uuid4()), str(uuid.uuid4())
    storage.create_user(f"pg-{uuid.uuid4().hex[:8]}@example.com", "hash")
    row = storage.save_analysis(owner, "lettuce-earth-growth-v3", "analysis", _payload())
    assert storage.get_analysis(other, row["id"]) is None
    assert storage.delete_analysis(other, row["id"]) is False
    assert storage.get_analysis(owner, row["id"]) is not None


# ---------------------------------------------------------------------------
# The restart-equivalent test
# ---------------------------------------------------------------------------
def test_records_survive_engine_disposal_and_reconnection(pg):
    """The persistence claim, tested the only way that proves anything.

    Data is written through one engine; that engine is disposed and the memoised handle is
    dropped, exactly as a process restart would; a fresh engine is built and the record is read
    back over a new connection. If the row had been in a connection-local buffer, a temp table or
    a process dictionary, this is where it would disappear.
    """
    owner = str(uuid.uuid4())
    scenario = storage.save_scenario("survives restart", _configuration(growingArea=12.5), owner)
    analysis = storage.save_analysis(owner, "lettuce-earth-growth-v3", "restart analysis",
                                     _payload())

    first_engine = storage.database()
    connection_id_before = _connection_identity()

    storage.dispose_database()          # dispose pool + forget the engine
    assert first_engine.pool.checkedout() == 0

    reopened = storage.database()       # a genuinely new engine
    assert reopened is not first_engine
    connection_id_after = _connection_identity()
    assert connection_id_after != connection_id_before, "a new server backend was expected"

    restored = storage.get_scenario(owner, scenario["id"])
    assert restored is not None
    assert restored["name"] == "survives restart"
    assert json.loads(restored["configuration"])["growingArea"] == 12.5

    restored_analysis = storage.get_analysis(owner, analysis["id"])
    assert restored_analysis is not None
    assert json.loads(restored_analysis["payload"])["output"]["prediction"] == 123.4

    # And the row really is a row, not a cached response.
    with reopened.connect() as connection:
        name = connection.execute(
            text("SELECT name FROM scenarios WHERE id = :id"), {"id": scenario["id"]}
        ).scalar_one()
    assert name == "survives restart"


def _connection_identity() -> str:
    """Identify the server backend a connection lands on.

    PostgreSQL assigns a unique pid per backend connection. Caching the pid from an earlier
    connection would let a test pass after nothing was actually reopened.
    """
    with storage.database().connect() as connection:
        return str(connection.execute(text("SELECT pg_backend_pid()")).scalar_one())


def test_scenario_history_endpoint_reads_after_restart(pg):
    """The same guarantee through the HTTP surface, not only the storage functions."""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    email = f"restart-{uuid.uuid4().hex[:8]}@example.com"
    registered = client.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    assert registered.status_code == 201, registered.text
    token = registered.json()["accessToken"]
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post("/api/scenarios", headers=headers,
                          json={"name": "http restart", "configuration": json.loads(_configuration())})
    assert created.status_code == 201, created.text
    scenario_id = created.json()["id"]

    storage.dispose_database()  # restart-equivalent, then serve the next request

    fetched = client.get(f"/api/scenarios/{scenario_id}", headers=headers)
    assert fetched.status_code == 200, fetched.text
    assert fetched.json()["name"] == "http restart"
    listed = client.get("/api/scenarios", headers=headers)
    assert any(row["id"] == scenario_id for row in listed.json()["scenarios"])
    # The account itself, its hash and its token survived the same restart.
    assert client.get("/api/auth/me", headers=headers).status_code == 200


# ---------------------------------------------------------------------------
# Failure, rollback, cleanup, concurrency
# ---------------------------------------------------------------------------
def test_missing_schema_is_not_reported_as_available(pg):
    """A reachable server with no tables must not read as ready."""
    with storage.database().begin() as connection:
        connection.execute(text("ALTER TABLE scenarios RENAME TO scenarios_hidden"))
    try:
        health = storage.database_health()
        assert health["status"] == "unavailable"
        assert health["schema"] == "incomplete"
        assert "scenarios" in health["missingTables"]

        from fastapi.testclient import TestClient

        from app.main import app

        ready = TestClient(app).get("/api/ready")
        assert ready.status_code == 503
        assert ready.json()["detail"]["reason"] == "schema-incomplete"
    finally:
        with storage.database().begin() as connection:
            connection.execute(text("ALTER TABLE scenarios_hidden RENAME TO scenarios"))
    assert storage.database_health()["status"] == "available"


def test_transaction_rolls_back_when_a_write_fails(pg):
    """A failed transaction must leave neither its first write nor a partial row behind.

    The transaction inserts a valid scenario and then violates a NOT NULL constraint in the same
    block. If the block rolled back, the scenario is gone; if it committed the first statement and
    failed on the second - the actual failure mode of a hand-managed session - the scenario
    survives and the database is left holding half a unit of work.
    """
    from sqlalchemy.exc import IntegrityError

    owner = str(uuid.uuid4())
    before = len(storage.list_scenarios(owner))
    doomed_id = str(uuid.uuid4())
    with pytest.raises(IntegrityError):
        with storage.database().begin() as connection:
            connection.execute(storage.scenarios.insert().values(
                id=doomed_id, name="rolled back", configuration=_configuration(),
                created_at="2026-01-01T00:00:00+00:00", model_version="assumptions-2.0",
                owner_id=owner))
            # analyses.owner_id is NOT NULL; supplying None fails inside the same transaction.
            connection.execute(storage.analyses.insert().values(
                id=str(uuid.uuid4()), owner_id=None, model_id="x", title="x",
                created_at="2026-01-01T00:00:00+00:00", payload="{}"))

    assert storage.get_scenario(owner, doomed_id) is None
    assert len(storage.list_scenarios(owner)) == before


def test_quota_rejection_persists_nothing(pg, monkeypatch):
    monkeypatch.setattr(settings, "max_analyses_per_user", 1, raising=False)
    owner = str(uuid.uuid4())
    storage.create_user(f"pg-{uuid.uuid4().hex[:8]}@example.com", "hash")
    storage.save_analysis(owner, "lettuce-earth-growth-v3", "first", _payload())
    with pytest.raises(storage.AnalysisQuotaExceeded):
        storage.save_analysis(owner, "lettuce-earth-growth-v3", "second", _payload())
    assert storage.analysis_usage(owner)["count"] == 1


def test_sessions_are_returned_to_the_pool(pg):
    """Every accessor closes what it opens; a leak here exhausts the pool in production."""
    owner = str(uuid.uuid4())
    for _ in range(20):
        storage.save_scenario("pool check", _configuration(), owner)
        storage.list_scenarios(owner)
        storage.get_scenario(owner, "does-not-exist")
        storage.database_health()
    assert storage.database().pool.checkedout() == 0


def test_concurrent_creates_are_all_persisted(pg):
    """Ten threads writing at once must produce ten rows, not a lost update or a deadlock."""
    owner = str(uuid.uuid4())
    errors: list[BaseException] = []
    ids: list[str] = []
    lock = threading.Lock()

    def create(index: int) -> None:
        try:
            row = storage.save_scenario(f"concurrent {index}", _configuration(), owner)
            with lock:
                ids.append(row["id"])
        except BaseException as exc:  # noqa: BLE001 - the assertion below reports it
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=create, args=(index,)) for index in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert not errors, errors
    assert len(set(ids)) == 10
    stored = {row["id"] for row in storage.list_scenarios(owner)}
    assert set(ids) <= stored
    assert len(storage.list_scenarios(owner)) == 10


def test_connection_failure_is_reported_without_leaking_credentials(pg, monkeypatch):
    """A wrong password must fail as a typed, secret-free error, not as a traceback."""
    from sqlalchemy.engine import make_url

    broken = make_url(POSTGRES_TEST_URL).set(password="definitely-wrong-password")
    monkeypatch.setattr(settings, "database_url", broken.render_as_string(hide_password=False),
                        raising=False)
    storage.dispose_database()
    with pytest.raises(Exception) as excinfo:
        storage.database_health()
    message = str(excinfo.value)
    assert "definitely-wrong-password" not in message
    storage.dispose_database()


def test_migrations_are_repeatable_and_non_destructive(pg):
    """Re-running the schema step on populated tables must not drop or rewrite anything."""
    owner = str(uuid.uuid4())
    row = storage.save_scenario("pre-migration", _configuration(), owner)
    engine = storage.database()
    before = sorted(inspect(engine).get_table_names())
    columns_before = {column["name"] for column in inspect(engine).get_columns("scenarios")}

    storage._migrate_scenarios_owner(engine)
    storage._migrate_users_columns(engine)
    storage.metadata.create_all(engine)

    assert sorted(inspect(engine).get_table_names()) == before
    assert {column["name"] for column in inspect(engine).get_columns("scenarios")} == columns_before
    assert storage.get_scenario(owner, row["id"])["name"] == "pre-migration"


def test_owner_index_exists_for_scoped_queries(pg):
    engine = storage.database()
    indexes = {index["name"] for index in inspect(engine).get_indexes("scenarios")}
    assert "ix_scenarios_owner_id" in indexes
