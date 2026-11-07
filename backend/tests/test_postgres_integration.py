"""Optional real-PostgreSQL test. It runs only with an explicitly supplied test DSN."""
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
        assert storage.database_health() == {"dialect": "postgresql", "status": "available"}
    finally:
        with storage.database().begin() as connection:
            connection.execute(delete(storage.scenarios).where(storage.scenarios.c.name == marker))
        storage.database().dispose()
        storage.database.cache_clear()
