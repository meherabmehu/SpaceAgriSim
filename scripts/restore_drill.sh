#!/usr/bin/env bash
# Restore drill: prove a dump of the live database can be restored into a SEPARATE database and
# that the application would read the same rows from it.
#
# Why a drill: Render's backup policy on the Free compute plan provides no automated backups and no
# point-in-time recovery (see docs/DATABASE_BACKUP_AND_RECOVERY.md). A dump that has never been
# restored is a hope, not a backup. This script is the cheapest way to turn it into evidence.
#
# Safety:
#   * SOURCE is only ever read (pg_dump, never DDL/DML).
#   * TARGET must be a different database and must not already contain the schema unless
#     ALLOW_NONEMPTY_TARGET=1, because pg_restore would collide with existing rows.
#   * Both URLs are passed to pg_dump/pg_restore by environment variable, never on the command line
#     (a command line is visible in `ps`), and never printed.
#
# Usage:
#   SOURCE_DATABASE_URL='postgresql://…/db' TARGET_DATABASE_URL='postgresql://…/db_restore' \
#     scripts/restore_drill.sh
#
# Exit codes: 0 = drill passed, 1 = drill failed, 2 = refused to run (unsafe or missing input).
set -euo pipefail

: "${SOURCE_DATABASE_URL:?set SOURCE_DATABASE_URL (read-only source)}"
: "${TARGET_DATABASE_URL:?set TARGET_DATABASE_URL (an empty, separate database)}"

# The app accepts postgres:// and postgresql:// aliases; the client tools want the plain form.
normalise() { printf '%s' "${1/postgresql+psycopg:\/\//postgresql://}"; }
SOURCE_DATABASE_URL="$(normalise "$SOURCE_DATABASE_URL")"
TARGET_DATABASE_URL="$(normalise "$TARGET_DATABASE_URL")"

if [ "$SOURCE_DATABASE_URL" = "$TARGET_DATABASE_URL" ]; then
  echo "refusing to run: SOURCE and TARGET are the same database" >&2
  exit 2
fi

command -v pg_dump >/dev/null || { echo "pg_dump not found on PATH (install postgresql-client)" >&2; exit 2; }
command -v pg_restore >/dev/null || { echo "pg_restore not found on PATH" >&2; exit 2; }
command -v psql >/dev/null || { echo "psql not found on PATH" >&2; exit 2; }

TABLES=(users scenarios analyses share_links)

count_rows() { # $1 = URL
  psql "$1" -tAc "select coalesce(sum(n_live_tup),0) from pg_stat_user_tables" 2>/dev/null || echo 0
}

for table in "${TABLES[@]}"; do
  present="$(psql "$TARGET_DATABASE_URL" -tAc \
    "select count(*) from information_schema.tables where table_schema='public' and table_name='$table'")"
  if [ "$present" != "0" ] && [ "${ALLOW_NONEMPTY_TARGET:-0}" != "1" ]; then
    echo "refusing to run: target already has table '$table'; use a fresh database" >&2
    exit 2
  fi
done

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT
DUMP="$WORKDIR/dump.tar.gz"

echo "1/4 dumping source (read-only)…"
pg_dump "$SOURCE_DATABASE_URL" --format=custom --no-owner --no-privileges --file="$DUMP"
echo "    dump size: $(wc -c <"$DUMP") bytes"

# Non-secret counts, taken from the source with a plain SELECT.
declare -A SOURCE_COUNTS
echo "2/4 counting rows in the source…"
for table in "${TABLES[@]}"; do
  SOURCE_COUNTS[$table]="$(psql "$SOURCE_DATABASE_URL" -tAc "select count(*) from $table" 2>/dev/null || echo 0)"
  echo "    $table: ${SOURCE_COUNTS[$table]}"
done

echo "3/4 restoring into the target database…"
pg_restore --no-owner --no-privileges --exit-on-error --dbname="$TARGET_DATABASE_URL" "$DUMP"

echo "4/4 comparing row counts…"
FAILED=0
for table in "${TABLES[@]}"; do
  restored="$(psql "$TARGET_DATABASE_URL" -tAc "select count(*) from $table")"
  if [ "$restored" = "${SOURCE_COUNTS[$table]}" ]; then
    echo "    [ok]   $table: $restored"
  else
    echo "    [FAIL] $table: source ${SOURCE_COUNTS[$table]} != restored $restored"
    FAILED=1
  fi
done

if [ "$FAILED" -ne 0 ]; then
  echo "restore drill FAILED" >&2
  exit 1
fi
echo "restore drill passed: the dump restores into a separate database with identical row counts"
