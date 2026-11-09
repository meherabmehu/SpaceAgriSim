"""Backup automation, restore validation and production monitoring (Phase 22).

These tests exercise the operator tooling that lives outside the app: the safety gates that stop a
restore from touching production, the monitor's verdict logic against a real HTTP server, and the
backup manifest's promise to never carry a connection string.

No PostgreSQL server is required: the SQL-level checks are covered by the restore drill in
`docs/DATABASE_BACKUP_AND_RECOVERY.md` and by the `Restore validation` workflow, both of which run
against the real thing.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve their annotations through sys.modules, so the module must be registered
    # before it is executed.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


PRODUCTION = "postgresql://appuser:s3cret@pg.internal:5432/spaceagrisim"


# ------------------------------------------------------------------------------------------------
# restore_validate: the gates that keep a restore away from production
# ------------------------------------------------------------------------------------------------
def test_restore_refuses_the_production_database_itself():
    module = load("restore_validate")
    gate = module.safety_gate(PRODUCTION, PRODUCTION, allow_remote=True)
    assert gate is not None
    assert "production database" in gate["reason"]
    assert gate["remedy"]


def test_restore_refuses_a_target_with_the_production_database_name():
    module = load("restore_validate")
    gate = module.safety_gate("postgresql://u:p@other.example.com:5432/spaceagrisim",
                              PRODUCTION, allow_remote=True)
    assert gate is not None
    assert "production database name" in gate["reason"]


def test_restore_refuses_a_remote_host_by_default():
    module = load("restore_validate")
    gate = module.safety_gate("postgresql://u:p@db.example.com:5432/restore_check", PRODUCTION, False)
    assert gate is not None
    assert "not a local address" in gate["reason"]
    # ... and permits it only when the operator says so.
    assert module.safety_gate("postgresql://u:p@db.example.com:5432/restore_check",
                              PRODUCTION, True) is None


@pytest.mark.parametrize("target", [
    "postgresql://postgres:pw@127.0.0.1:5432/spaceagrisim_restore_check",
    "postgresql://postgres:pw@localhost:5432/spaceagrisim_restore_check",
    "postgresql+psycopg://postgres:pw@127.0.0.1:5432/spaceagrisim_restore_check",
])
def test_restore_accepts_a_local_throwaway_database(target):
    module = load("restore_validate")
    assert module.safety_gate(target, PRODUCTION, allow_remote=False) is None


def test_restore_refuses_a_non_postgresql_target():
    module = load("restore_validate")
    gate = module.safety_gate("sqlite:////tmp/x.db", PRODUCTION, allow_remote=True)
    assert gate is not None
    assert "not a PostgreSQL URL" in gate["reason"]


def test_restore_target_description_never_includes_credentials():
    module = load("restore_validate")
    described = module.describe_target("postgresql://appuser:s3cret@127.0.0.1:5432/restore_check")
    assert described == "127.0.0.1:5432/restore_check"
    assert "s3cret" not in described and "appuser" not in described


def test_refusal_payload_is_machine_readable():
    module = load("restore_validate")
    code, payload = module.refusal("nope", "do this instead")
    assert code == 2
    assert payload == {"ok": False, "refused": True, "reason": "nope", "remedy": "do this instead"}


def test_expected_counts_come_from_the_manifest(tmp_path):
    module = load("restore_validate")
    manifest = tmp_path / "x.dump.manifest.json"
    manifest.write_text(json.dumps({"createdAt": "2026-11-09T00:00:00Z",
                                    "sourceInventory": {"users": 2, "scenarios": -1}}))
    counts, source = module.load_expected(manifest)
    assert counts == {"users": 2}          # -1 means "table absent", so it is dropped
    assert "x.dump.manifest.json" in source
    assert module.load_expected(None) == (None, "none (no --expected manifest supplied)")


def test_report_summary_counts_failures():
    module = load("restore_validate")
    report = module.Report()
    report.add("a", True, "fine")
    report.add("b", False, "broken")
    payload = report.as_dict()
    assert payload["ok"] is False
    assert payload["summary"] == "1/2 checks passed"
    assert [check["check"] for check in payload["checks"]] == ["a", "b"]


def test_required_tables_match_the_application_schema():
    """The script keeps its own copy of the table list; this is what stops it drifting."""
    from app import storage

    module = load("restore_validate")
    assert set(module.REQUIRED_TABLES) == set(storage.REQUIRED_TABLES)

    backup_module = load("db_backup")
    assert set(backup_module.REQUIRED_TABLES) == set(storage.REQUIRED_TABLES)


# ------------------------------------------------------------------------------------------------
# db_backup: the manifest must be safe to upload
# ------------------------------------------------------------------------------------------------
def _seeded_sqlite(tmp_path):
    from app import storage
    from app.config.settings import settings

    path = tmp_path / "backup-source.db"
    original = settings.database_url
    settings.database_url = f"sqlite:///{path}"
    storage.database.cache_clear()
    try:
        for index in range(2):
            storage.save_scenario(f"phase22-{index}", '{"crop":"lettuce"}')
        yield path
    finally:
        settings.database_url = original
        storage.database.cache_clear()


def test_manifest_never_records_the_connection_string(tmp_path):
    module = load("db_backup")
    out = tmp_path / "backups"
    source = next(_seeded_sqlite(tmp_path))
    assert module.main(["--database-url", f"sqlite:///{source}", "--out", str(out)]) == 0

    manifest_path = next(out.glob("*.manifest.json"))
    text = manifest_path.read_text()
    manifest = json.loads(text)
    # The old manifest stored everything after '@' - host and database - in a file that CI uploads.
    assert "databaseUrl" not in manifest
    # The database file name only: no host, no absolute path, no user.
    assert manifest["database"] == {"dialect": "sqlite", "name": "backup-source.db"}
    assert "password" not in text.lower()


def test_backup_requires_exactly_one_connection_mode(tmp_path):
    module = load("db_backup")
    assert module.main(["--out", str(tmp_path / "a")]) == 1
    assert module.main(["--from-libpq-env", "--database-url", "sqlite:////tmp/x.db",
                        "--out", str(tmp_path / "b")]) == 1


def test_libpq_env_mode_requires_a_database_name(monkeypatch, tmp_path):
    module = load("db_backup")
    monkeypatch.delenv("PGDATABASE", raising=False)
    assert module.main(["--from-libpq-env", "--out", str(tmp_path / "c")]) == 1


def test_postgres_dump_verification_rejects_an_unreadable_archive(tmp_path):
    module = load("db_backup")
    bad = tmp_path / "not-a-dump.dump"
    bad.write_bytes(b"this is not a pg_dump archive")
    if module.shutil.which("pg_restore") is None:
        pytest.skip("pg_restore is not installed in this environment")
    with pytest.raises(RuntimeError):
        module.describe_dump(bad)


def test_sqlalchemy_urls_are_translated_for_libpq():
    module = load("db_backup")
    assert module.sqlalchemy_to_libpq("postgresql+psycopg://u:p@h:5432/d") == "postgresql://u:p@h:5432/d"
    assert module.sqlalchemy_to_libpq("postgres://u:p@h:5432/d") == "postgresql://u:p@h:5432/d"
    assert module.sqlalchemy_to_libpq("postgresql://u:p@h:5432/d") == "postgresql://u:p@h:5432/d"


def test_database_name_is_extracted_without_the_host():
    module = load("db_backup")
    assert module._database_name("postgresql+psycopg://u:p@h:5432/mydb") == "mydb"
    assert module._database_name(None) is None or isinstance(module._database_name(None), str)


# ------------------------------------------------------------------------------------------------
# monitor_production: verdict logic against a real HTTP server
# ------------------------------------------------------------------------------------------------
READY = {
    "status": "ready", "database": "available", "databaseDialect": "postgresql",
    "databaseSchema": "present", "databaseMigrations": {"applied": 4, "total": 4, "pending": 0},
    "databasePool": {"size": 5, "checkedOut": 0, "capacity": 10, "exhausted": False},
    "storage": {"dialect": "postgresql", "durable": True, "reason": "", "remedy": ""},
    "emailDelivery": "configured", "rateLimitIdentity": "forwarded",
}


class FakeAPI:
    """A local stand-in for the deployed API: same paths, bodies chosen per test."""

    def __init__(self, ready: dict, metrics: dict | None = None, ready_status: int = 200):
        self.payloads = {
            "/api/health": (200, {"status": "ok", "service": "SpaceAgriSim API", "version": "0.1.0"}),
            "/api/ready": (ready_status, ready),
            "/api/metrics": (200, metrics if metrics is not None else
                             {"metrics": {"requests": {"/api/health": 1}, "serverErrors": {},
                                          "database": {"slowQueries": {}, "slowQueryCount": 0,
                                                       "failures": {}},
                                          "startedAt": "2026-11-09T00:00:00Z",
                                          "uptimeSeconds": 3600}}),
        }
        handler = self._handler()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def _handler(self):
        payloads = self.payloads

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - http.server naming
                status, body = payloads.get(self.path, (404, {"error": "not found"}))
                encoded = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, *args):  # silence the test output
                return

        return Handler

    def __enter__(self):
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def test_monitor_passes_on_a_healthy_service():
    module = load("monitor_production")
    with FakeAPI(READY) as api:
        assert module.main(["--base-url", api.url, "--json"]) == 0


def test_monitor_reports_a_remedy_when_readiness_fails():
    module = load("monitor_production")
    broken = {"status": "error", "error": "database_unavailable",
              "reason": "connection-failed",
              "remedy": "Check the host and port in SPACEAGRISIM_DATABASE_URL."}
    with FakeAPI(broken, ready_status=503) as api:
        assert module.main(["--base-url", api.url]) == 1
        result = module.Result(base_url=api.url)
        module.check_ready(result, api.url, 5.0, allow_degraded=False)
        failure = result.failures[0]
        assert failure.name == "ready:status"
        assert "SPACEAGRISIM_DATABASE_URL" in failure.remedy


def test_monitor_flags_pending_migrations_and_pool_exhaustion():
    module = load("monitor_production")
    unhealthy = dict(READY, databaseMigrations={"applied": 3, "total": 4, "pending": 1},
                     databasePool={"size": 5, "checkedOut": 10, "capacity": 10, "exhausted": True},
                     storage={"dialect": "sqlite", "durable": False, "remedy": "Set a Postgres URL."})
    with FakeAPI(unhealthy) as api:
        result = module.Result(base_url=api.url)
        module.check_ready(result, api.url, 5.0, allow_degraded=False)
    failed = {check.name for check in result.failures}
    assert {"ready:migrations", "ready:pool", "ready:storage-durable"} <= failed
    remedies = {check.name: check.remedy for check in result.failures}
    assert "restart the service once" in remedies["ready:migrations"]
    assert "slow query" in remedies["ready:pool"]


def test_monitor_treats_warnings_as_non_fatal():
    module = load("monitor_production")
    warn = dict(READY, emailDelivery="unconfigured", rateLimitIdentity="socket")
    with FakeAPI(warn) as api:
        assert module.main(["--base-url", api.url, "--json"]) == 3


def test_monitor_reports_server_errors_as_a_warning_with_a_class_hint():
    module = load("monitor_production")
    metrics = {"metrics": {"requests": {"/api/scenarios": 4},
                           "serverErrors": {"/api/scenarios": 2},
                           "database": {"slowQueries": {}, "slowQueryCount": 0,
                                        "failures": {"pool-timeout": 3}},
                           "uptimeSeconds": 30}}
    with FakeAPI(READY, metrics=metrics) as api:
        assert module.main(["--base-url", api.url, "--json"]) == 3
        result = module.Result(base_url=api.url)
        module.check_metrics(result, api.url, 5.0)
        hints = {check.name: check.remedy for check in result.checks if check.remedy}
        assert "connection pool is exhausted" in hints["metrics:database-failures"]
        module.check_uptime(result)
        uptime = next(check for check in result.checks if check.name == "metrics:uptime")
        assert "restarted recently" in uptime.remedy


def test_monitor_fails_when_nothing_answers():
    module = load("monitor_production")
    # Port 9 (discard) on loopback is closed; the monitor must report, not raise.
    assert module.main(["--base-url", "http://127.0.0.1:9", "--timeout", "1"]) == 1


def test_metrics_endpoint_exposes_uptime_without_identifiers():
    """The new fields must be aggregate only: no client, no path parameter, no address."""
    from app import observability

    snapshot = observability.snapshot()
    assert "startedAt" in snapshot and "uptimeSeconds" in snapshot
    assert set(snapshot) == {"requests", "serverErrors", "database", "startedAt", "uptimeSeconds"}
    observability.record("/api/ready", 200)
    assert snapshot["startedAt"].endswith("Z")
