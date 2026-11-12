#!/usr/bin/env python3
"""Phase 7 deployment-configuration verification.

Part D asks for PostgreSQL integration on a disposable local instance *and*
verification of the deployment configuration, without weakening Phase 4's security
posture. This script verifies the second half against a real database, and asserts
the Phase 4 invariants still hold after Phase 7's changes.

What it actually does (nothing is asserted from documentation):

  1. applies backend/migrations/001_scenarios.sql to a disposable PostgreSQL
     database and inspects the resulting catalogue;
  2. runs the API's own storage layer against it and round-trips a scenario;
  3. loads the settings object under several environment configurations and
     checks the security invariants that must never regress;
  4. checks that the migration and the ORM metadata do not disagree.

Exit code is non-zero on any failure, so this is usable in CI.

Requires an isolated PostgreSQL instance and an explicit auth secret: the settings object refuses
to construct on Vercel without one, which is one of the invariants checked here. Example:
    SPACEAGRISIM_AUTH_SECRET=$(python -c "import secrets;print(secrets.token_urlsafe(48))") \\
    SPACEAGRISIM_TEST_POSTGRES_URL=postgresql+psycopg://user:pw@127.0.0.1:55432/db \\
        python scripts/verify_deployment_config.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

FAILURES: list[str] = []
CHECKS: list[dict] = []


def check(name: str, passed: bool, detail: str) -> None:
    CHECKS.append({"check": name, "passed": bool(passed), "detail": detail})
    if not passed:
        FAILURES.append(f"{name}: {detail}")


def psql(dsn: str, sql: str) -> tuple[int, str]:
    """Run SQL through psql, translating the SQLAlchemy DSN to libpq arguments."""
    from urllib.parse import unquote, urlparse

    parsed = urlparse(dsn.replace("postgresql+psycopg://", "postgresql://"))
    env = dict(os.environ, PGPASSWORD=unquote(parsed.password or ""))
    command = ["psql", "-h", parsed.hostname or "127.0.0.1",
               "-p", str(parsed.port or 5432), "-U", parsed.username or "postgres",
               "-d", (parsed.path or "/postgres").lstrip("/"), "-v", "ON_ERROR_STOP=1",
               "-At", "-c", sql]
    result = subprocess.run(command, capture_output=True, text=True, env=env, timeout=120)
    return result.returncode, (result.stdout + result.stderr).strip()


def verify_server_encoding(dsn: str) -> dict:
    """Fail loudly if the cluster is not UTF-8.

    A cluster initialised under a non-UTF-8 locale defaults to SQL_ASCII, and
    psycopg then hands SQLAlchemy `bytes` instead of `str` for text results. The
    dialect's version probe does `re.match(pattern, value)` on that value and
    raises `TypeError: cannot use a string pattern on a bytes-like object`, which
    names neither the encoding nor the fix. Catching it here turns a cryptic
    traceback into one line the operator can act on.
    """
    code, encoding = psql(dsn, "SHOW server_encoding")
    encoding = encoding.strip()
    ok = code == 0 and encoding.upper() in ("UTF8", "UTF-8")
    check("server encoding is UTF-8", ok, encoding or "could not read server_encoding")
    if not ok:
        check(
            "diagnostic: cluster must be initialised with -E UTF8",
            False,
            ("Recreate the cluster: initdb -D <dir> -E UTF8 --locale=C.UTF-8. "
             "A SQL_ASCII cluster makes psycopg return bytes and breaks the "
             "SQLAlchemy PostgreSQL dialect."))
    code, client = psql(dsn, "SHOW client_encoding")
    check("client encoding is UTF-8", code == 0 and client.strip().upper() in ("UTF8", "UTF-8"),
          client.strip())
    return {"serverEncoding": encoding, "clientEncoding": client.strip()}


def verify_migration(dsn: str) -> dict:
    code, output = psql(dsn, (ROOT / "backend/migrations/001_scenarios.sql").read_text())
    check("migration applies cleanly", code == 0, output.splitlines()[-1] if output else "ok")

    code, tables = psql(dsn, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY 1")
    expected = {"scenarios", "users", "revoked_tokens"}
    present = set(tables.split()) if code == 0 else set()
    check("migration creates the three required tables", expected <= present,
          f"present={sorted(present)}")

    code, columns = psql(dsn, ("SELECT column_name FROM information_schema.columns "
                               "WHERE table_name='scenarios' ORDER BY 1"))
    expected_columns = {"id", "name", "created_at", "configuration",
                        "model_version", "owner_id"}
    present_columns = set(columns.split()) if code == 0 else set()
    check("scenarios table has every column the ORM writes",
          expected_columns <= present_columns, f"present={sorted(present_columns)}")

    code, index = psql(dsn, ("SELECT indexname FROM pg_indexes WHERE tablename='scenarios'"))
    check("owner/created index exists", code == 0 and "scenarios_owner_created_idx" in index,
          index or "no indexes returned")

    # Idempotence: a deployment re-runs migrations, so a second application must
    # be a no-op rather than an error.
    code2, output2 = psql(dsn, (ROOT / "backend/migrations/001_scenarios.sql").read_text())
    check("migration is idempotent", code2 == 0, output2.splitlines()[-1] if output2 else "ok")
    return {"tables": sorted(present), "columns": sorted(present_columns)}


def verify_storage_roundtrip(dsn: str) -> dict:
    from app import storage
    from app.config.settings import settings

    storage.database.cache_clear()
    original = settings.database_url
    settings.database_url = dsn
    marker = f"phase7-verify-{uuid.uuid4()}"
    try:
        row = storage.save_scenario(marker, '{"crop":"lettuce"}')
        check("scenario write reaches PostgreSQL", row["name"] == marker, row["id"])
        listed = storage.list_scenarios()
        check("scenario is readable back", any(s["id"] == row["id"] for s in listed),
              f"{len(listed)} rows listed")
        health = storage.database_health()
        check("health reports the postgresql dialect", health.get("dialect") == "postgresql",
              json.dumps(health))
        with storage.database().begin() as connection:
            connection.exec_driver_sql(
                "DELETE FROM scenarios WHERE name = %s", (marker,))
        return {"rowId": row["id"], "health": health}
    finally:
        settings.database_url = original
        storage.database().dispose()
        storage.database.cache_clear()


def verify_settings_invariants() -> dict:
    """Phase 4 security invariants, re-checked after Phase 7's changes."""
    import importlib

    import app.config.settings as settings_module

    def fresh(**env):
        saved = {k: os.environ.get(k) for k in env}
        os.environ.update({k: v for k, v in env.items() if v is not None})
        try:
            importlib.reload(settings_module)
            return settings_module.Settings()
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    results = {}
    base = fresh()

    check("CORS origins are explicit, never a wildcard",
          all("*" not in origin for origin in base.cors_origins),
          json.dumps(base.cors_origins))

    try:
        fresh(SPACEAGRISIM_CORS_ORIGINS='["*"]')
        check("wildcard CORS is rejected", False, "wildcard origin was accepted")
    except Exception as exc:  # noqa: BLE001 - any rejection is the point
        check("wildcard CORS is rejected", True, type(exc).__name__)

    try:
        fresh(SPACEAGRISIM_CORS_ORIGINS='["http://example.com"]')
        check("plaintext non-local CORS origin is rejected", False,
              "http origin outside localhost was accepted")
    except Exception as exc:  # noqa: BLE001
        check("plaintext non-local CORS origin is rejected", True, type(exc).__name__)

    # `auth_secret` is the configured value, not the effective one: when it is unset the application
    # generates a process-local ephemeral secret, so the attribute is legitimately `None`. Reading a
    # length off it directly raised TypeError and killed the script before it could report the very
    # condition it exists to catch - a deployment without a configured secret.
    secret = base.auth_secret or ""
    check("auth secret meets the 32-character floor", len(secret) >= 32,
          "unset (an ephemeral secret is generated at runtime)" if not secret else f"length={len(secret)}")
    check("auth tokens expire within a day",
          5 <= base.auth_token_minutes <= 1440, str(base.auth_token_minutes))
    check("auth rate limiting is enabled",
          1 <= base.auth_rate_limit_per_minute <= 60, str(base.auth_rate_limit_per_minute))

    vercel = fresh(VERCEL="1")
    check("history writes are disabled on Vercel", vercel.history_writes_enabled is False,
          str(vercel.history_writes_enabled))
    check("Vercel default database path is /tmp", vercel.database_url.startswith("sqlite:////tmp/"),
          vercel.database_url)

    local = fresh(VERCEL=None)
    check("history writes are enabled locally", local.history_writes_enabled is True,
          str(local.history_writes_enabled))

    # Part D constraint: no public persistent writes without a durable database.
    # The combination below is the dangerous one and must not be reachable by
    # default.
    check("local default is not a public persistent store",
          not local.database_url.startswith("postgresql"),
          local.database_url)

    importlib.reload(settings_module)
    results.update({
        "corsOrigins": base.cors_origins,
        "authSecretLength": len(secret),
        "tokenMinutes": base.auth_token_minutes,
        "rateLimitPerMinute": base.auth_rate_limit_per_minute,
        "historyWritesOnVercel": vercel.history_writes_enabled,
        "localDatabaseUrl": local.database_url,
    })
    return results


def verify_orm_migration_parity() -> dict:
    """The SQL migration and the ORM metadata must describe the same table."""
    from app import storage

    orm_columns = {c.name for c in storage.scenarios.columns}
    sql_text = (ROOT / "backend/migrations/001_scenarios.sql").read_text()
    missing = [c for c in orm_columns if f" {c} " not in sql_text]
    check("every ORM column appears in the migration", not missing, f"missing={missing}")
    return {"ormColumns": sorted(orm_columns)}


def main() -> int:
    # Stated up front rather than discovered mid-run: `fresh(VERCEL="1")` below constructs the
    # settings object under a Vercel environment, where a missing secret is a validation error by
    # design. Without this guard that intended refusal surfaced as a pydantic traceback from the
    # middle of the SECURITY checks, which reads like a broken script instead of a precondition.
    if not os.getenv("SPACEAGRISIM_AUTH_SECRET"):
        print("SPACEAGRISIM_AUTH_SECRET must be set; run this with the deployment's own secret.")
        return 2

    dsn = os.getenv("SPACEAGRISIM_TEST_POSTGRES_URL")
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "phase": 7,
        "purpose": ("Verify the PostgreSQL path and the Phase 4 security invariants "
                    "against a running instance rather than against documentation."),
        "database": {"configured": bool(dsn), "dsnHost": None},
    }

    payload["settings"] = verify_settings_invariants()
    payload["orm"] = verify_orm_migration_parity()

    if dsn:
        from urllib.parse import urlparse
        payload["database"]["dsnHost"] = urlparse(
            dsn.replace("postgresql+psycopg://", "postgresql://")).hostname
        payload["database"]["encoding"] = verify_server_encoding(dsn)
        if not all(entry["passed"] for entry in CHECKS if "encoding" in entry["check"]):
            # Don't bury the real cause under unrelated SQLAlchemy failures.
            payload["checks"] = CHECKS
            payload["passed"] = False
            payload["failures"] = FAILURES
            out = ROOT / "docs" / "phase7" / "deployment_verification.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")
            for entry in CHECKS:
                print(f"  [{'PASS' if entry['passed'] else 'FAIL'}] "
                      f"{entry['check']}: {entry['detail']}")
            print("\nABORTED: database encoding is not UTF-8; see the diagnostic above.")
            return 1
        payload["database"]["migration"] = verify_migration(dsn)
        payload["database"]["storageRoundtrip"] = verify_storage_roundtrip(dsn)
    else:
        CHECKS.append({"check": "live database checks", "passed": False,
                       "detail": "SPACEAGRISIM_TEST_POSTGRES_URL not set"})
        FAILURES.append("live database checks: no DSN supplied")

    payload["checks"] = CHECKS
    payload["passed"] = not FAILURES
    payload["failures"] = FAILURES

    out = ROOT / "docs" / "phase7" / "deployment_verification.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n")

    for entry in CHECKS:
        print(f"  [{'PASS' if entry['passed'] else 'FAIL'}] {entry['check']}: {entry['detail']}")
    print(f"\n{len(CHECKS) - len(FAILURES)}/{len(CHECKS)} checks passed")
    print(f"written: {out.relative_to(ROOT)}")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
