"""Optional real-PostgreSQL round trip. Runs only with an explicitly supplied test DSN.

Superseded in coverage by `test_postgresql_persistence.py`, which isolates itself in a throwaway
schema and covers the restart-equivalent path. This one is kept because it is the oldest statement
of the guarantee - a row written to PostgreSQL is readable back - and because it runs in the full
suite whenever a DSN is present.
"""
import os
import uuid

import pytest
from sqlalchemy import delete

from app import storage
from app.config.settings import settings


POSTGRES_TEST_URL = os.getenv("SPACEAGRISIM_TEST_POSTGRES_URL")


@pytest.mark.skipif(not POSTGRES_TEST_URL, reason="Set SPACEAGRISIM_TEST_POSTGRES_URL to run against an isolated PostgreSQL test database")
def test_postgres_scenario_roundtrip(monkeypatch):
    assert POSTGRES_TEST_URL.startswith("postgresql+psycopg://")
    storage.database.cache_clear()
    monkeypatch.setattr(settings, "database_url", POSTGRES_TEST_URL)
    marker = f"phase3-test-{uuid.uuid4()}"
    try:
        row = storage.save_scenario(marker, '{"crop":"lettuce"}')
        assert row["name"] == marker
        assert any(saved["id"] == row["id"] for saved in storage.list_scenarios())
        health = storage.database_health()
        assert health["dialect"] == "postgresql"
        assert health["status"] == "available"
        # Connectivity alone is not the claim: the schema the API queries must be there too.
        assert health["schema"] == "present"
        assert health["missingTables"] == ""
    finally:
        with storage.database().begin() as connection:
            connection.execute(delete(storage.scenarios).where(storage.scenarios.c.name == marker))
        storage.database.cache_clear()
