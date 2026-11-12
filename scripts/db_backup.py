"""Create a consistent, verifiable backup of the scenario database.

Supports both storage backends the application uses:

  * SQLite  -- uses the sqlite3 online backup API, which is safe to run against
               a live database (it copies a consistent snapshot even if writers
               are active).
  * PostgreSQL -- shells out to `pg_dump -Fc` (custom format), proves the result
               is a readable archive with `pg_restore --list`, and never touches
               the data itself.

Design rules:
  * Never write the backup inside the web container's ephemeral filesystem; the
    caller supplies an explicit destination.
  * Always emit a sidecar manifest with SHA-256, byte count, schema/table
    inventory and row counts, so a restore can be *verified* rather than assumed.
  * Refuse to overwrite an existing backup unless --force is given.
  * Never write a connection string into the manifest. The manifest travels with
    the dump (and, in CI, gets uploaded), so it records the dialect and database
    name but never the host, the user or the password.

Two ways to hand PostgreSQL the connection, both deliberate:

  * ``--database-url``        the URL appears in this process's argv, which `ps`
                              can read. Fine on a laptop, not in CI.
  * ``--from-libpq-env``      pg_dump gets no URL at all: it reads PGHOST,
                              PGPORT, PGDATABASE, PGUSER and PGPASSFILE from the
                              environment, so the password never appears in any
                              command line. This is what the GitHub Actions
                              workflow uses.

Usage:
    python scripts/db_backup.py --database-url sqlite:///path/to.db --out backups/
    python scripts/db_backup.py --database-url postgresql+psycopg://... --out backups/
    python scripts/db_backup.py --from-libpq-env --out backups/
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root

# The tables a restore is expected to bring back. Kept in step with
# backend/app/storage.py REQUIRED_TABLES; duplicated rather than imported so the
# script runs without the application's dependencies installed.
REQUIRED_TABLES = ("scenarios", "users", "analyses", "revoked_tokens", "email_tokens",
                   "share_links", "audit_events")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sqlite_path(database_url: str) -> Path:
    if not database_url.startswith("sqlite:"):
        raise ValueError("not a sqlite URL")
    raw = database_url.split("sqlite:", 1)[1]
    if raw.startswith("////"):
        return Path("/" + raw.lstrip("/"))
    if raw.startswith("///"):
        return Path(raw[3:])
    if raw.startswith("//"):
        return Path(raw[2:])
    return Path(raw)


def inventory(connection: sqlite3.Connection) -> dict:
    tables = [r[0] for r in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    counts = {}
    for table in tables:
        counts[table] = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    return {"tables": tables, "rowCounts": counts}


def backup_sqlite(source: Path, target: Path) -> dict:
    if not safedata.exists(source):
        raise FileNotFoundError(f"SQLite database not found: {source}")
    source_connection = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        before = inventory(source_connection)
        destination = sqlite3.connect(target)
        try:
            source_connection.backup(destination)
            destination.commit()
        finally:
            destination.close()
    finally:
        source_connection.close()

    check = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
    try:
        integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
        after = inventory(check)
    finally:
        check.close()
    return {
        "backend": "sqlite",
        "dumpFormat": "sqlite-file",
        "integrityCheck": integrity,
        "sourceInventory": before,
        "backupInventory": after,
        "inventoryMatches": before == after,
    }


# ---------------------------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------------------------
_TOC_TABLE_DATA = re.compile(r"TABLE DATA public (\S+)")
_TOC_ENTRY = re.compile(r"^\d+; \d+ \d+ ")


def sqlalchemy_to_libpq(database_url: str) -> str:
    """pg_dump wants a libpq URL, not the SQLAlchemy dialect prefix."""
    return (database_url.replace("postgresql+psycopg://", "postgresql://")
                       .replace("postgres+psycopg://", "postgresql://")
                       .replace("postgres://", "postgresql://"))


def require_client(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(
            f"{name} not found. Backups must run from an operator machine or CI runner with the "
            f"PostgreSQL client tools of the server's MAJOR version installed (pg_dump refuses to "
            f"dump a server newer than itself), never from the web container.")


def toc_list(dump: Path) -> list[str]:
    """`pg_restore --list` output: the proof that the archive is readable."""
    result = subprocess.run(["pg_restore", "--list", str(dump)],
                            capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"pg_restore --list rejected the dump: {result.stderr.strip()}")
    return result.stdout.splitlines()


def describe_dump(dump: Path) -> dict:
    lines = toc_list(dump)
    entries = [line for line in lines if _TOC_ENTRY.match(line)]
    if not entries:
        raise RuntimeError("pg_restore --list returned no archive entries; the dump is empty")
    tables = sorted({match.group(1) for line in entries
                     for match in [_TOC_TABLE_DATA.search(line)] if match})
    missing = [name for name in REQUIRED_TABLES if name not in tables]
    return {
        "tocEntries": len(entries),
        # The archive itself names these, so this list is evidence, not a claim.
        "tablesInDump": tables,
        "missingRequiredTables": missing,
    }


def pg_row_counts() -> dict:
    """Per-table row counts, read with SELECT only. Never raises for a missing table."""
    try:
        import psycopg
    except ImportError:  # pragma: no cover - CI installs the runtime requirements
        return {"available": False,
                "reason": "psycopg not installed; counts skipped (dump verification unaffected)"}
    try:
        with psycopg.connect("") as connection:  # empty DSN: libpq reads the PG* environment
            counts: dict[str, int] = {}
            with connection.cursor() as cursor:
                for table in REQUIRED_TABLES:
                    try:
                        cursor.execute(f'SELECT COUNT(*) FROM public."{table}"')
                        counts[table] = int(cursor.fetchone()[0])
                    except Exception:  # noqa: BLE001 - an absent table is data, not an error
                        connection.rollback()
                        counts[table] = -1
            return {"available": True, "rowCounts": counts,
                    "totalRows": sum(value for value in counts.values() if value >= 0)}
    except Exception as exc:  # noqa: BLE001 - a count failure must not invalidate a good dump
        return {"available": False, "reason": f"{type(exc).__name__}: counts skipped"}


def backup_postgres(target: Path, database_url: str | None) -> dict:
    require_client("pg_dump")
    require_client("pg_restore")
    command = ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", "--file", str(target)]
    if database_url:
        # libpq reads PGHOST/PGUSER/PGPASSWORD from the environment, so the URL is the only
        # place the password appears - and only in this process's argv, which is why CI uses
        # --from-libpq-env instead.
        command.append(sqlalchemy_to_libpq(database_url))
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        # stderr from pg_dump names the host but never the password; keep only the first line
        # so a transient failure does not dump a wall of text into a CI summary.
        first = (result.stderr.strip().splitlines() or ["no stderr"])[0]
        raise RuntimeError(f"pg_dump failed: {first}")
    if not safedata.exists(target) or target.stat().st_size == 0:
        raise RuntimeError("pg_dump reported success but wrote an empty file")

    archive = describe_dump(target)
    if archive["missingRequiredTables"]:
        raise RuntimeError(
            "the dump is readable but is missing application tables: "
            + ", ".join(archive["missingRequiredTables"]))
    counts = pg_row_counts()
    return {
        "backend": "postgresql",
        "dumpFormat": "custom (pg_dump -Fc)",
        # Stated as a fact about this run: the archive was listed by pg_restore.
        "tocVerified": True,
        "tocEntries": archive["tocEntries"],
        "tablesInDump": archive["tablesInDump"],
        "sourceInventory": counts.get("rowCounts") if counts.get("available") else None,
        "rowCountsAvailable": counts.get("available", False),
        "rowCountsNote": counts.get("reason"),
    }


def _database_name(database_url: str | None) -> str | None:
    """The database name only. The host and the credentials stay in the environment."""
    if not database_url:
        return os.environ.get("PGDATABASE")
    if database_url.startswith("sqlite:"):
        # A local file path carries a home directory that has no business travelling with the dump;
        # the file name alone identifies the source well enough.
        return Path(sqlite_path(database_url)).name
    from urllib.parse import urlsplit
    try:
        path = urlsplit(sqlalchemy_to_libpq(database_url)).path
    except ValueError:
        return None
    return path.lstrip("/") or None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Back up the SpaceAgriSim scenario database.")
    parser.add_argument("--database-url",
                        help="SQLAlchemy URL, e.g. sqlite:///path.db or postgresql+psycopg://...")
    parser.add_argument("--from-libpq-env", action="store_true",
                        help="PostgreSQL only: read PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSFILE "
                             "from the environment so no URL appears in any command line.")
    parser.add_argument("--out", default="backups", help="destination directory")
    parser.add_argument("--force", action="store_true", help="overwrite an existing backup")
    args = parser.parse_args(argv)

    if bool(args.database_url) == bool(args.from_libpq_env):
        print("give exactly one of --database-url or --from-libpq-env", file=sys.stderr)
        return 1
    database_url = args.database_url
    if args.from_libpq_env:
        if not os.environ.get("PGDATABASE"):
            print("--from-libpq-env needs PGDATABASE (and normally PGHOST, PGUSER, PGPASSFILE)",
                  file=sys.stderr)
            return 1
        database_url = None

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()

    if database_url and database_url.startswith("sqlite:"):
        target = out_dir / f"spaceagrisim-{stamp}.sqlite3"
        if safedata.exists(target) and not args.force:
            print(f"refusing to overwrite {target} (use --force)", file=sys.stderr)
            return 1
        details = backup_sqlite(sqlite_path(database_url), target)
    elif args.from_libpq_env or (database_url and database_url.startswith(("postgresql", "postgres:"))):
        target = out_dir / f"spaceagrisim-{stamp}.dump"
        if safedata.exists(target) and not args.force:
            print(f"refusing to overwrite {target} (use --force)", file=sys.stderr)
            return 1
        details = backup_postgres(target, database_url)
    else:
        print("unsupported database URL; expected sqlite:, postgresql or --from-libpq-env",
              file=sys.stderr)
        return 1

    body = safedata.bytes(target)
    manifest = {
        "createdAt": datetime.now(timezone.utc).isoformat(),
        # Identification only: dialect and database name. No host, no user, no password, no URL.
        "database": {
            "dialect": "sqlite" if target.suffix == ".sqlite3" else "postgresql",
            "name": _database_name(database_url),
        },
        "backupPath": target.name,
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        **details,
    }
    # The sidecar manifest is YAML rather than JSON so that neither the repository nor a
    # backup directory ever depends on a JSON document.
    manifest_path = target.with_suffix(target.suffix + ".manifest.yaml")
    safedata.dump(manifest, manifest_path)

    print(json.dumps({k: manifest[k] for k in
                      ("backupPath", "sha256", "bytes", "backend")}, indent=2))
    if manifest.get("integrityCheck") not in (None, "ok"):
        print(f"INTEGRITY FAILURE: {manifest['integrityCheck']}", file=sys.stderr)
        return 1
    if manifest.get("inventoryMatches") is False:
        print("INVENTORY MISMATCH between source and backup", file=sys.stderr)
        return 1
    print(f"manifest: {manifest_path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
