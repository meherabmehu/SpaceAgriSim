"""Database backup and restore-verification drills (Phase 6).

These exercise the operator scripts against a real SQLite database so the
backup/restore path is tested rather than merely documented.
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def seeded_db(tmp_path):
    """A real SQLite database with the application schema and a few rows."""
    from app import storage
    from app.config.settings import settings

    path = tmp_path / "scenarios.db"
    original = settings.database_url
    settings.database_url = f"sqlite:///{path}"
    storage.database.cache_clear()
    try:
        storage.initialize_storage() if hasattr(storage, "initialize_storage") else None
        for index in range(3):
            storage.save_scenario(f"phase6-backup-{index}", '{"crop":"lettuce"}')
        yield path
    finally:
        settings.database_url = original
        storage.database.cache_clear()


def test_backup_creates_verified_snapshot(seeded_db, tmp_path):
    backup_mod = load("db_backup")
    out = tmp_path / "backups"
    assert backup_mod.main(["--database-url", f"sqlite:///{seeded_db}", "--out", str(out)]) == 0

    created = list(out.glob("*.sqlite3"))
    assert len(created) == 1
    manifest = json.loads(Path(str(created[0]) + ".manifest.json").read_text())

    assert manifest["backend"] == "sqlite"
    assert manifest["integrityCheck"] == "ok"
    assert manifest["inventoryMatches"] is True
    assert manifest["bytes"] == created[0].stat().st_size
    assert len(manifest["sha256"]) == 64
    # The scenario rows must actually be in the backup.
    assert manifest["backupInventory"]["rowCounts"].get("scenarios", 0) >= 3


def test_restore_verification_passes_on_good_backup(seeded_db, tmp_path):
    backup_mod = load("db_backup")
    verify_mod = load("db_restore_verify")
    out = tmp_path / "backups"
    assert backup_mod.main(["--database-url", f"sqlite:///{seeded_db}", "--out", str(out)]) == 0
    backup = next(out.glob("*.sqlite3"))
    assert verify_mod.main([str(backup)]) == 0


def test_restore_verification_detects_tampering(seeded_db, tmp_path):
    backup_mod = load("db_backup")
    verify_mod = load("db_restore_verify")
    out = tmp_path / "backups"
    assert backup_mod.main(["--database-url", f"sqlite:///{seeded_db}", "--out", str(out)]) == 0
    backup = next(out.glob("*.sqlite3"))

    # Corrupt the snapshot; the checksum check must catch it.
    with backup.open("ab") as handle:
        handle.write(b"tampered")
    assert verify_mod.main([str(backup)]) == 1


def test_restore_verification_detects_row_loss(seeded_db, tmp_path):
    backup_mod = load("db_backup")
    verify_mod = load("db_restore_verify")
    out = tmp_path / "backups"
    assert backup_mod.main(["--database-url", f"sqlite:///{seeded_db}", "--out", str(out)]) == 0
    backup = next(out.glob("*.sqlite3"))
    manifest_path = Path(str(backup) + ".manifest.json")
    manifest = json.loads(manifest_path.read_text())

    # Delete every scenario row from the snapshot, then re-stamp the manifest so
    # the checksum matches again - isolation must still catch the loss.
    connection = sqlite3.connect(backup)
    connection.execute("DELETE FROM scenarios")
    connection.commit()
    connection.close()
    import hashlib
    body = backup.read_bytes()
    manifest["sha256"] = hashlib.sha256(body).hexdigest()
    manifest["bytes"] = len(body)
    manifest_path.write_text(json.dumps(manifest))

    assert verify_mod.main([str(backup)]) == 1


def test_backup_refuses_to_overwrite(seeded_db, tmp_path, monkeypatch):
    backup_mod = load("db_backup")
    out = tmp_path / "backups"
    monkeypatch.setattr(backup_mod, "utc_stamp", lambda: "fixed")
    assert backup_mod.main(["--database-url", f"sqlite:///{seeded_db}", "--out", str(out)]) == 0
    # Second identical run must refuse without --force.
    assert backup_mod.main(["--database-url", f"sqlite:///{seeded_db}", "--out", str(out)]) == 1


def test_backup_rejects_missing_database(tmp_path):
    backup_mod = load("db_backup")
    with pytest.raises(FileNotFoundError):
        backup_mod.main(["--database-url", f"sqlite:///{tmp_path/'nope.db'}",
                        "--out", str(tmp_path / "b")])


def test_postgres_backup_without_pg_dump_fails_loudly(monkeypatch):
    backup_mod = load("db_backup")
    monkeypatch.setattr(backup_mod.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="pg_dump not found"):
        backup_mod.backup_postgres("postgresql+psycopg://u:p@h/db", Path("/tmp/x.dump"))
