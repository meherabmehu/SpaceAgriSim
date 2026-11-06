-- Initial PostgreSQL schema. Run once before starting a restricted production role.
-- Equivalent to app.storage.metadata. No raw NASA files or trained model binaries in this table.
BEGIN;
CREATE TABLE IF NOT EXISTS scenarios (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at VARCHAR(40) NOT NULL,
    configuration TEXT NOT NULL,
    model_version VARCHAR(60) NOT NULL
);
COMMIT;
