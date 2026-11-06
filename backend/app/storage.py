"""Bounded shared scenario history. PostgreSQL in production, SQLite for local demos."""
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Column, MetaData, String, Table, Text, create_engine, delete, select
from app.config.settings import settings

metadata = MetaData()
scenarios = Table("scenarios", metadata,
    Column("id", String(36), primary_key=True),
    Column("name", String(100), nullable=False),
    Column("created_at", String(40), nullable=False),
    Column("configuration", Text, nullable=False),
    Column("model_version", String(60), nullable=False),
)

@lru_cache(maxsize=1)
def database():
    url = settings.database_url
    if url.startswith("sqlite:///"):
        name = url.removeprefix("sqlite:///")
        if name != ":memory:":
            Path(name).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, pool_pre_ping=True)
    metadata.create_all(engine)
    return engine

def list_scenarios():
    with database().connect() as connection:
        return [dict(row._mapping) for row in connection.execute(
            select(scenarios).order_by(scenarios.c.created_at.desc()).limit(settings.max_history))]

def save_scenario(name: str, configuration: str):
    row = {"id": str(uuid4()), "name": name,
           "created_at": datetime.now(timezone.utc).isoformat(),
           "configuration": configuration, "model_version": "assumptions-2.0"}
    with database().begin() as connection:
        connection.execute(scenarios.insert().values(**row))
        expired = connection.execute(select(scenarios.c.id).order_by(
            scenarios.c.created_at.desc()).offset(settings.max_history)).scalars().all()
        if expired:
            connection.execute(delete(scenarios).where(scenarios.c.id.in_(expired)))
    return row
