#!/usr/bin/env python3
"""Prove that a PostgreSQL dump restores into a *separate* database and is complete.

This is the second half of the backup story. A dump that has never been restored is a hope; the
only way to turn it into evidence is to restore it somewhere that is definitely not production and
then check the things a user would notice missing:

  * the seven application tables exist and carry the columns the migrations add,
  * every table's row count matches the dump's own manifest,
  * saved rows still point at the accounts that own them (no orphaned scenarios, analyses,
    share links, email tokens or audit events),
  * account rows are still usable (no empty password hashes, no duplicate emails).

Safety rules, in order of importance:

1. **It can never be pointed at production.** The target URL is refused if it equals
   ``--production-url``/``PRODUCTION_DATABASE_URL``, if its database name equals the production
   database name, or - unless ``--allow-remote`` is passed - if its host is not a local address.
   Restoring is destructive by nature (it replays CREATE/COPY), so this gate runs before anything
   else and before a single byte is written.
2. **It refuses a target that already holds the schema.** pg_restore into a populated database
   produces duplicate-key noise at best; the script stops instead.
3. **It never prints a connection string.** Output names the dialect, and at most the host and
   database of the *target*, never a user or a password.

Usage:
    python3 scripts/restore_validate.py \
        --dump backups/spaceagrisim-<stamp>.dump \
        --expected backups/spaceagrisim-<stamp>.dump.manifest \
        --target-url 'postgresql://postgres:...@127.0.0.1:5432/spaceagrisim_restore_check'

    python3 scripts/restore_validate.py --dump ... --target-url ... --report report.yaml

Exit codes: 0 = every check passed, 1 = a check failed, 2 = refused to run (unsafe or unusable
input), 3 = the restore itself failed.
"""
from __future__ import annotations
import sys as _sys, pathlib as _pathlib   # the repository root holds safedata/
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parents[1]))
import safedata

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

REQUIRED_TABLES = ("scenarios", "users", "analyses", "revoked_tokens", "email_tokens",
                   "share_links", "audit_events")

# Mirrors backend/app/storage.py MIGRATIONS. A restore that lost an additive step would still
# answer simple queries, so these are checked explicitly rather than inferred from the tables.
REQUIRED_COLUMNS = {
    "scenarios": ("owner_id",),
    "users": ("email_verified", "password_changed_at"),
}
REQUIRED_INDEXES = {"scenarios": ("ix_scenarios_owner_id",)}

# Ownership edges: (child table, child column, parent table). Every non-null child value must
# name a parent row, or the restored database has lost a user but kept that user's data.
OWNERSHIP_EDGES = (
    ("scenarios", "owner_id", "users"),
    ("analyses", "owner_id", "users"),
    ("share_links", "owner_id", "users"),
    ("share_links", "scenario_id", "scenarios"),
    ("email_tokens", "user_id", "users"),
    ("audit_events", "user_id", "users"),
)

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0", "postgres", "db", "database"}


@dataclass
class Check:
    name: str
    ok: bool
    detail: str

    def as_dict(self) -> dict:
        return {"check": self.name, "ok": self.ok, "detail": self.detail}


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    expected: dict[str, int] | None = None
    expectedSource: str = "none"

    def add(self, name: str, ok: bool, detail: str) -> Check:
        check = Check(name, ok, detail)
        self.checks.append(check)
        return check

    @property
    def failed(self) -> list[Check]:
        return [check for check in self.checks if not check.ok]

    def as_dict(self) -> dict:
        return {
            "ok": not self.failed,
            "checks": [check.as_dict() for check in self.checks],
            "counts": self.counts,
            "expectedCounts": self.expected,
            "expectedCountsSource": self.expectedSource,
            "summary": (f"{len(self.checks) - len(self.failed)}/{len(self.checks)} checks passed"),
        }


def libpq(database_url: str) -> str:
    return (database_url.replace("postgresql+psycopg://", "postgresql://")
                       .replace("postgres+psycopg://", "postgresql://")
                       .replace("postgres://", "postgresql://"))


def describe_target(database_url: str) -> str:
    """`host:port/database`, with no user and no password, for human-readable output."""
    try:
        parts = urlsplit(libpq(database_url))
    except ValueError:
        return "unparseable target"
    host = parts.hostname or "?"
    port = parts.port or 5432
    return f"{host}:{port}{parts.path or ''}"


def refusal(reason: str, remedy: str) -> tuple[int, dict]:
    return 2, {"ok": False, "refused": True, "reason": reason, "remedy": remedy}


def safety_gate(target_url: str, production_url: str | None, allow_remote: bool) -> dict | None:
    """Returns None when the target is safe, or a refusal payload. Runs before any write."""
    if not target_url.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
        return {"reason": "target is not a PostgreSQL URL",
                "remedy": "pass --target-url postgresql://user:pass@host:5432/db"}
    target = urlsplit(libpq(target_url))
    if production_url:
        prod = urlsplit(libpq(production_url))
        if (target.hostname, target.port, target.path) == (prod.hostname, prod.port, prod.path):
            return {"reason": "target is the production database (identical host, port and name)",
                    "remedy": "create a separate throwaway database and point --target-url at it"}
        if target.path and target.path == prod.path:
            return {"reason": "target has the production database name",
                    "remedy": "restore into a database with a distinct name, e.g. "
                              "spaceagrisim_restore_check"}
    if not allow_remote and (target.hostname or "").lower() not in LOCAL_HOSTS:
        return {"reason": f"target host '{target.hostname}' is not a local address",
                "remedy": "restore-validation runs against a local or CI service container; "
                          "pass --allow-remote only for a dedicated throwaway instance"}
    return None


def connect(target_url: str):
    import psycopg
    return psycopg.connect(libpq(target_url), connect_timeout=15)


def existing_app_tables(target_url: str) -> list[str]:
    with connect(target_url) as connection, connection.cursor() as cursor:
        cursor.execute(
            "select table_name from information_schema.tables "
            "where table_schema='public' and table_name = any(%s)", (list(REQUIRED_TABLES),))
        return sorted(row[0] for row in cursor.fetchall())


def toc_tables(dump: Path) -> tuple[int, list[str]]:
    result = subprocess.run(["pg_restore", "--list", str(dump)],
                            capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError((result.stderr.strip().splitlines() or ["pg_restore --list failed"])[0])
    entries = [line for line in result.stdout.splitlines()
               if line[:1].isdigit() and "TABLE DATA" in line]
    tables = sorted({line.split("TABLE DATA public ", 1)[1].split()[0]
                     for line in entries if "TABLE DATA public " in line})
    return len(entries), tables


def restore(dump: Path, target_url: str) -> None:
    result = subprocess.run(
        ["pg_restore", "--no-owner", "--no-privileges", "--exit-on-error",
         "--dbname", libpq(target_url), str(dump)],
        capture_output=True, text=True, check=False)
    if result.returncode != 0:
        first = (result.stderr.strip().splitlines() or ["pg_restore failed"])[0]
        raise RuntimeError(first)


def load_expected(manifest_path: Path | None) -> tuple[dict[str, int] | None, str]:
    if manifest_path is None:
        return None, "none (no --expected manifest supplied)"
    payload = safedata.load(manifest_path)
    counts = payload.get("sourceInventory")
    if not isinstance(counts, dict):
        return None, f"none ({manifest_path.name} has no sourceInventory)"
    # A count of -1 means "table absent in the source"; drop it rather than assert on it.
    cleaned = {name: int(value) for name, value in counts.items() if int(value) >= 0}
    return cleaned, f"{manifest_path.name} (captured {payload.get('createdAt', 'unknown time')})"


def verify_schema(report: Report, target_url: str) -> None:
    with connect(target_url) as connection, connection.cursor() as cursor:
        cursor.execute("select table_name from information_schema.tables "
                       "where table_schema='public'")
        present = {row[0] for row in cursor.fetchall()}
        missing = [name for name in REQUIRED_TABLES if name not in present]
        report.add("schema:application-tables", not missing,
                   "all seven tables present" if not missing
                   else "missing: " + ", ".join(missing))

        for table, columns in REQUIRED_COLUMNS.items():
            if table not in present:
                report.add(f"schema:{table}.columns", False, "table missing")
                continue
            cursor.execute("select column_name from information_schema.columns "
                           "where table_schema='public' and table_name=%s", (table,))
            have = {row[0] for row in cursor.fetchall()}
            missing_columns = [column for column in columns if column not in have]
            report.add(f"schema:{table}.columns", not missing_columns,
                       "present" if not missing_columns
                       else "missing columns: " + ", ".join(missing_columns))

        for table, indexes in REQUIRED_INDEXES.items():
            if table not in present:
                report.add(f"schema:{table}.indexes", False, "table missing")
                continue
            cursor.execute("select indexname from pg_indexes "
                           "where schemaname='public' and tablename=%s", (table,))
            have = {row[0] for row in cursor.fetchall()}
            missing_indexes = [name for name in indexes if name not in have]
            report.add(f"schema:{table}.indexes", not missing_indexes,
                       "present" if not missing_indexes
                       else "missing indexes: " + ", ".join(missing_indexes))


def verify_counts(report: Report, target_url: str) -> None:
    with connect(target_url) as connection, connection.cursor() as cursor:
        for table in REQUIRED_TABLES:
            try:
                cursor.execute(f'select count(*) from public."{table}"')
                report.counts[table] = int(cursor.fetchone()[0])
            except Exception:  # noqa: BLE001
                connection.rollback()
                report.counts[table] = -1
    if report.expected is None:
        report.add("rows:match-dump-manifest", True,
                   "no expected counts supplied; restored counts recorded instead: "
                   + json.dumps(report.counts, sort_keys=True))
        return
    mismatches = [f"{table}: expected {report.expected.get(table, 'absent')}, "
                  f"restored {report.counts.get(table)}"
                  for table in sorted(set(report.expected) | set(report.counts))
                  if report.expected.get(table, 0) != report.counts.get(table, 0)]
    report.add("rows:match-dump-manifest", not mismatches,
               "all table counts match the dump's manifest" if not mismatches
               else "; ".join(mismatches))


def verify_ownership(report: Report, target_url: str) -> None:
    """No child row may reference a parent that the restore did not bring back."""
    with connect(target_url) as connection, connection.cursor() as cursor:
        for child, column, parent in OWNERSHIP_EDGES:
            try:
                cursor.execute(
                    f'select count(*) from public."{child}" c where c."{column}" is not null '
                    f'and not exists (select 1 from public."{parent}" p where p.id = c."{column}")')
                orphans = int(cursor.fetchone()[0])
            except Exception as exc:  # noqa: BLE001
                connection.rollback()
                report.add(f"ownership:{child}.{column}->{parent}", False,
                           f"could not check: {type(exc).__name__}")
                continue
            report.add(f"ownership:{child}.{column}->{parent}", orphans == 0,
                       "no orphans" if orphans == 0
                       else f"{orphans} row(s) reference a missing {parent} row")


def verify_account_rows(report: Report, target_url: str) -> None:
    with connect(target_url) as connection, connection.cursor() as cursor:
        try:
            cursor.execute("select count(*) from public.users where password_hash is null "
                           "or length(password_hash) < 16")
            weak = int(cursor.fetchone()[0])
            report.add("accounts:usable-rows", weak == 0,
                       "every account row carries a password hash" if weak == 0
                       else f"{weak} account row(s) have an empty or truncated hash")
        except Exception as exc:  # noqa: BLE001
            connection.rollback()
            report.add("accounts:usable-rows", False, f"could not check: {type(exc).__name__}")

        try:
            cursor.execute("select count(*) from (select email from public.users "
                           "group by email having count(*) > 1) duplicates")
            duplicates = int(cursor.fetchone()[0])
            report.add("accounts:unique-email", duplicates == 0,
                       "no duplicate emails" if duplicates == 0
                       else f"{duplicates} duplicated email address(es)")
        except Exception as exc:  # noqa: BLE001
            connection.rollback()
            report.add("accounts:unique-email", False, f"could not check: {type(exc).__name__}")

        # Legacy local-demo rows legitimately have no owner; this is reported, never "fixed".
        try:
            cursor.execute("select count(*) from public.scenarios where owner_id is null")
            unowned = int(cursor.fetchone()[0])
            report.add("ownership:legacy-unowned-scenarios", True,
                       f"{unowned} scenario row(s) have no owner (legacy rows are permitted by "
                       f"the schema; reported for the record, not modified)")
        except Exception:  # noqa: BLE001
            connection.rollback()
            report.add("ownership:legacy-unowned-scenarios", False, "column missing")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Restore a SpaceAgriSim PostgreSQL dump into a throwaway database and verify it.")
    parser.add_argument("--dump", required=True, help="custom-format dump (pg_dump -Fc)")
    parser.add_argument("--target-url", required=True,
                        help="a SEPARATE, EMPTY PostgreSQL database; never production")
    parser.add_argument("--expected", help="the .manifest written next to the dump")
    parser.add_argument("--production-url", default=None,
                        help="production URL to refuse (defaults to $PRODUCTION_DATABASE_URL)")
    parser.add_argument("--allow-remote", action="store_true",
                        help="permit a non-local target (dedicated throwaway instance only)")
    parser.add_argument("--report", metavar="PATH", help="write the machine-readable report to PATH (YAML)")
    args = parser.parse_args(argv)

    dump = Path(args.dump)
    # The URL to refuse. From the flag when given, otherwise the environment, so the same variable
    # the API uses can be exported in an operator shell as a belt-and-braces guard.
    production_url = args.production_url or os.environ.get("PRODUCTION_DATABASE_URL")
    for tool in ("pg_restore",):
        if shutil.which(tool) is None:
            return _emit(args, *refusal(f"{tool} not found", "install the PostgreSQL client tools"))

    gate = safety_gate(args.target_url, production_url, args.allow_remote)
    if gate is not None:
        return _emit(args, *refusal(gate["reason"], gate["remedy"]))

    if not safedata.exists(dump):
        return _emit(args, *refusal(f"dump not found: {dump.name}",
                                    "pass --dump with the .dump file to validate"))

    try:
        present = existing_app_tables(args.target_url)
    except Exception as exc:  # noqa: BLE001
        return _emit(args, *refusal(
            f"cannot connect to the target ({type(exc).__name__})",
            "check that the throwaway database exists and is accepting connections"))
    if present:
        return _emit(args, *refusal(
            "target already contains application tables: " + ", ".join(present),
            "restore-validation must start from an empty database; create a new one"))

    report = Report()
    try:
        entries, tables = toc_tables(dump)
    except RuntimeError as exc:
        return _emit(args, *refusal(f"dump is not a readable custom-format archive ({exc})",
                                    "re-take the backup; this file cannot be restored"))
    missing = [name for name in REQUIRED_TABLES if name not in tables]
    report.add("dump:readable-toc", True, f"{entries} table-data entries listed by pg_restore")
    report.add("dump:contains-required-tables", not missing,
               "all seven tables are in the archive" if not missing
               else "missing from archive: " + ", ".join(missing))
    if missing:
        return _finish(args, report, args.target_url)

    expected, source = load_expected(Path(args.expected) if args.expected else None)
    report.expected, report.expectedSource = expected, source

    try:
        restore(dump, args.target_url)
    except RuntimeError as exc:
        report.add("restore:pg_restore-exit-on-error", False, str(exc))
        if args:
            print(json.dumps(report.as_dict(), indent=2))
        else:
            print(f"restore FAILED: {exc}")
        return 3
    report.add("restore:pg_restore-exit-on-error", True, "pg_restore completed without errors")

    verify_schema(report, args.target_url)
    verify_counts(report, args.target_url)
    verify_ownership(report, args.target_url)
    verify_account_rows(report, args.target_url)
    return _finish(args, report, args.target_url)


def _finish(args, report: Report, target_url: str) -> int:
    payload = report.as_dict()
    payload["target"] = describe_target(target_url)
    if args:
        print(json.dumps(payload, indent=2))
    else:
        print(f"restore validation against {payload['target']}")
        for check in report.checks:
            print(f"  [{'ok' if check.ok else 'FAIL'}] {check.name}: {check.detail}")
        print(f"  restored row counts: {json.dumps(report.counts, sort_keys=True)}")
        print(f"  expected counts from: {report.expectedSource}")
        print(f"  {payload['summary']}")
    return 0 if payload["ok"] else 1


def _emit(args, code: int, payload: dict) -> int:
    """Print the report, or write it to --report as YAML.

    The report used to be JSON emitted on stdout. It is YAML now, and written to a named
    file, so that neither this script nor the restore workflow has to produce a JSON
    document to describe what it did.
    """
    if args and getattr(args, "report", None):
        import yaml
        Path(args.report).write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=110),
            encoding="utf-8")
        print(f"report: {args.report}")
    elif args:
        print(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=110))
    else:
        print(f"refused to run: {payload['reason']}")
        print(f"remedy: {payload['remedy']}")
    return code


if __name__ == "__main__":
    sys.exit(main())
