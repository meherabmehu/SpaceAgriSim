-- Initial PostgreSQL schema. Run once before starting a restricted production role.
-- Equivalent to app.storage.metadata. No raw NASA files or trained model binaries in this table.
BEGIN;
CREATE TABLE IF NOT EXISTS scenarios (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_at VARCHAR(40) NOT NULL,
    configuration TEXT NOT NULL,
    model_version VARCHAR(60) NOT NULL,
    owner_id VARCHAR(36)
);
ALTER TABLE scenarios ADD COLUMN IF NOT EXISTS owner_id VARCHAR(36);
CREATE INDEX IF NOT EXISTS scenarios_owner_created_idx ON scenarios (owner_id, created_at DESC);
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(254) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at VARCHAR(40) NOT NULL,
    disabled BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS revoked_tokens (
    jti VARCHAR(64) PRIMARY KEY,
    expires_at VARCHAR(40) NOT NULL
);
COMMIT;
