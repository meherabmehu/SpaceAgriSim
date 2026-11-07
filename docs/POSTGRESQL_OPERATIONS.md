# PostgreSQL operations

## Configuration

The API accepts only `sqlite:///...` for local development or `postgresql+psycopg://...` for PostgreSQL. Set production configuration outside Git:

```text
SPACEAGRISIM_DATABASE_URL=postgresql+psycopg://ROLE:PASSWORD@HOST:5432/spaceagrisim
SPACEAGRISIM_HISTORY_WRITES_ENABLED=true
SPACEAGRISIM_CORS_ORIGINS=["https://your-frontend.example"]
```

Use an isolated migration-capable role for schema setup and a restricted runtime role for the API. The initial schema is in `backend/migrations/001_scenarios.sql`; it is idempotent and preserves existing rows.

## Health and integration test

`GET /api/ready` performs `SELECT 1` and returns only the database dialect/status, never a DSN or credentials.

Run the optional real-PostgreSQL integration check only against a disposable database:

```powershell
$env:SPACEAGRISIM_TEST_POSTGRES_URL='postgresql+psycopg://USER:PASSWORD@HOST:5432/spaceagrisim_test'
backend/.venv/Scripts/python -m pytest -q backend/tests/test_postgres_integration.py
Remove-Item Env:SPACEAGRISIM_TEST_POSTGRES_URL
```

It creates one uniquely named scenario, verifies read/write/health, then removes only that row. The test is skipped by default so no hosted resource is created accidentally.

## Backup and recovery

Use provider-managed point-in-time recovery plus encrypted logical backups. Example commands must run from an operator machine with `pg_dump`/`pg_restore`, never from the web container:

```sh
pg_dump --format=custom --no-owner "$SPACEAGRISIM_DATABASE_URL" > spaceagrisim-$(date +%F).dump
pg_restore --clean --if-exists --no-owner --dbname "$RESTORE_DATABASE_URL" spaceagrisim-YYYY-MM-DD.dump
```

Before a restore, stop writes, restore into an isolated database first, verify `scenarios` row count and `/api/ready`, then switch the application DSN deliberately. Do not restore over production as a first validation step. Retain backups according to the chosen provider policy and test restoration periodically.
