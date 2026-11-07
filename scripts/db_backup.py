"""Create a consistent, verifiable backup of the scenario database.

Supports both storage backends the application uses:

  * SQLite  -- uses the sqlite3 online backup API, which is safe to run against
               a live database (it copies a consistent snapshot even if writers
               are active).
  * PostgreSQL -- shells out to `pg_dump -Fc` (custom format) and never touches
               the data itself.

Design rules:
  * Never write the backup inside the web container's ephemeral filesystem; the
    caller supplies an explicit destination.
  * Always emit a sidecar manifest with SHA-256, byte count, schema/table
    inventory and row counts, so a restore can be *verified* rather than assumed.
  * Refuse to overwrite an existing backup unless --force is given.

Usage:
    python scripts/db_backup.py --database-url sqlite:///path/to.db --out backups/
    python scripts/db_backup.py --database-url postgresql+psycopg://... --out backups/
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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
    if not source.is_file():
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
        "integrityCheck": integrity,
        "sourceInventory": before,
        "backupInventory": after,
        "inventoryMatches": before == after,
    }


def backup_postgres(database_url: str, target: Path) -> dict:
    if shutil.which("pg_dump") is None:
        raise RuntimeError(
            "pg_dump not found. Backups must run from an operator machine with "
            "PostgreSQL client tools installed, never from the web container.")
    # pg_dump wants a libpq URL, not the SQLAlchemy dialect prefix.
    libpq_url = database_url.replace("postgresql+psycopg://", "postgresql://")
    result = subprocess.run(
        ["pg_dump", "--format=custom", "--no-owner", "--no-privileges",
         "--file", str(target), libpq_url],
        capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {result.stderr.strip()}")
    return {
        "backend": "postgresql",
        "note": ("Custom-format dump. Verify with scripts/db_restore_verify.py into an "
                 "ISOLATED database before touching production."),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Back up the SpaceAgriSim scenario database.")
    parser.add_argument("--database-url", required=True,
                        help="SQLAlchemy URL, e.g. sqlite:///path.db or postgresql+psycopg://...")
    parser.add_argument("--out", default="backups", help="destination directory")
    parser.add_argument("--force", action="store_true", help="overwrite an existing backup")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_stamp()

    if args.database_url.startswith("sqlite:"):
        target = out_dir / f"spaceagrisim-{stamp}.sqlite3"
        if target.exists() and not args.force:
            print(f"refusing to overwrite {target} (use --force)", file=sys.stderr)
            return 1
        details = backup_sqlite(sqlite_path(args.database_url), target)
    elif args.database_url.startswith("postgresql"):
        target = out_dir / f"spaceagrisim-{stamp}.dump"
        if target.exists() and not args.force:
            print(f"refusing to overwrite {target} (use --force)", file=sys.stderr)
            return 1
        details = backup_postgres(args.database_url, target)
    else:
        print("unsupported database URL; expected sqlite: or postgresql", file=sys.stderr)
        return 1

    body = target.read_bytes()
    manifest = {
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "databaseUrl": args.database_url.split("@")[-1] if "@" in args.database_url
                       else args.database_url,
        "backupPath": str(target),
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
        **details,
    }
    manifest_path = target.with_suffix(target.suffix + ".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({k: manifest[k] for k in
                      ("backupPath", "sha256", "bytes", "backend")}, indent=2))
    if manifest.get("integrityCheck") not in (None, "ok"):
        print(f"INTEGRITY FAILURE: {manifest['integrityCheck']}", file=sys.stderr)
        return 1
    if manifest.get("inventoryMatches") is False:
        print("INVENTORY MISMATCH between source and backup", file=sys.stderr)
        return 1
    print(f"manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
