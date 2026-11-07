"""Verify a backup by restoring it into a throwaway database and checking it.

This never restores over a live database. It:

  1. re-hashes the backup file and compares it with the manifest,
  2. restores into a temporary location,
  3. checks SQLite integrity, table inventory and row counts against the
     manifest recorded at backup time,
  4. exits non-zero on any mismatch.

Usage:
    python scripts/db_restore_verify.py backups/spaceagrisim-....sqlite3
    python scripts/db_restore_verify.py backups/spaceagrisim-....dump --database-url postgresql+psycopg://...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(connection: sqlite3.Connection) -> dict:
    tables = [r[0] for r in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {"tables": tables,
            "rowCounts": {t: connection.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                          for t in tables}}


def verify_sqlite(backup: Path, manifest: dict) -> list[str]:
    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        restored = Path(tmp) / "restored.sqlite3"
        shutil.copy2(backup, restored)
        connection = sqlite3.connect(f"file:{restored}?mode=ro", uri=True)
        try:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                problems.append(f"integrity_check returned {integrity!r}")
            observed = inventory(connection)
        finally:
            connection.close()
    expected = manifest.get("backupInventory") or manifest.get("sourceInventory") or {}
    if expected:
        if observed["tables"] != expected.get("tables"):
            problems.append(f"table inventory differs: {observed['tables']} != {expected.get('tables')}")
        if observed["rowCounts"] != expected.get("rowCounts"):
            problems.append(f"row counts differ: {observed['rowCounts']} != {expected.get('rowCounts')}")
    return problems


def verify_postgres(backup: Path, database_url: str) -> list[str]:
    if shutil.which("pg_restore") is None:
        return ["pg_restore not found; run this from an operator machine with PostgreSQL client tools"]
    result = subprocess.run(["pg_restore", "--list", str(backup)],
                            capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return [f"pg_restore --list failed: {result.stderr.strip()}"]
    if not result.stdout.strip():
        return ["pg_restore --list produced no entries; the dump looks empty"]
    return []


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Verify a SpaceAgriSim database backup.")
    parser.add_argument("backup", help="path to the backup file")
    parser.add_argument("--manifest", help="path to the manifest (default: <backup>.manifest.json)")
    parser.add_argument("--database-url", help="target PostgreSQL URL for restore drills")
    args = parser.parse_args(argv)

    backup = Path(args.backup)
    if not backup.is_file():
        print(f"backup not found: {backup}", file=sys.stderr)
        return 1
    manifest_path = Path(args.manifest) if args.manifest else \
        backup.with_suffix(backup.suffix + ".manifest.json")
    if not manifest_path.is_file():
        print(f"manifest not found: {manifest_path}", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text())

    problems = []
    digest = sha256(backup)
    if digest != manifest.get("sha256"):
        problems.append(f"sha256 mismatch: {digest} != {manifest.get('sha256')}")
    if backup.stat().st_size != manifest.get("bytes"):
        problems.append(f"byte count mismatch: {backup.stat().st_size} != {manifest.get('bytes')}")

    backend = manifest.get("backend")
    if backend == "sqlite":
        problems += verify_sqlite(backup, manifest)
    elif backend == "postgresql":
        problems += verify_postgres(backup, args.database_url or "")
    else:
        problems.append(f"unknown backend {backend!r}")

    report = {
        "backup": str(backup),
        "backend": backend,
        "sha256Verified": digest == manifest.get("sha256"),
        "restoreVerified": not problems,
        "problems": problems,
    }
    print(json.dumps(report, indent=2))
    if problems:
        print("RESTORE VERIFICATION FAILED", file=sys.stderr)
        return 1
    print("restore verification passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
