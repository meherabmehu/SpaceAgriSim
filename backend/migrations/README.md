# Scenario schema migrations

Local SQLite creates the table on first history or readiness access. Production supports PostgreSQL through SQLAlchemy and psycopg:

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/migrations/001_scenarios.sql
```

Use a normal `postgresql://` URL for psql. Set `SPACEAGRISIM_DATABASE_URL=postgresql+psycopg://...` for the API. The initial migration is idempotent; deployment tooling must record application of future numbered migrations. Back up the database before changes. No destructive down migration is supplied; rollback app code while retaining the compatible table.

History is bounded to the newest 200 shared configurations (configurable). This is a shared demonstration workspace, without tenant accounts. Production deployments requiring private per-user history must add authentication and ownership enforcement before exposing it.
