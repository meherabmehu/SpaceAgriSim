# Database persistence audit

Scope: every resource the backend writes, where it is written, and whether it survives a process
restart. Written against `main` at `255110e`, verified against a real PostgreSQL 17 server locally
and in CI against `postgres:16-alpine`.

## 1. Connection and configuration

| Item | Where | Finding |
| --- | --- | --- |
| Configuration | `backend/app/config/settings.py` | `SPACEAGRISIM_DATABASE_URL`; platform aliases `postgres://` and `postgresql://` are rewritten to `postgresql+psycopg://`. Blank is treated as unset. |
| Unset default | `Settings.database_url_default` | SQLite file — `/tmp/spaceagrisim/scenarios.db` on Vercel, `.spaceagrisim/scenarios.db` elsewhere. |
| Driver | `backend/requirements.txt` | `psycopg[binary]` 3.x (not psycopg2). |
| Engine | `backend/app/storage.py::database()` | One engine per process, `pool_pre_ping=True`; PostgreSQL gets `pool_size` 5 / `max_overflow` 5. Construction is serialised by a lock (see §4.4). |
| Schema creation | `storage.metadata.create_all` | `checkfirst`, additive: creates missing tables, never alters or drops an existing one. |
| Migrations | `_migrate_scenarios_owner`, `_migrate_users_columns` | Additive `ALTER TABLE ... ADD COLUMN`, guarded by an `inspect` check, so they are repeatable. Plus `CREATE INDEX IF NOT EXISTS` for `owner_id`. |

`/api/ready` reported `database: available`, `databaseDialect: postgresql`, `storage.durable: true`
in production before this audit. Those indicators were **true but incomplete**, which is why this
audit exists: they answered "did a socket answer", not "can every feature store its data".

## 2. Resources and where they live

Schema has seven tables (`storage.metadata`). Every one is written by a live route.

| Resource | Table | Written by | Read by |
| --- | --- | --- | --- |
| Saved scenario (habitat configuration + name) | `scenarios` | `POST /api/scenarios`, `PATCH /api/scenarios/{id}` | `GET /api/scenarios`, `GET /api/scenarios/{id}`, share links |
| Account | `users` | `POST /api/auth/register`, password reset, email verification | login, `/api/auth/me`, admin summary |
| Saved model result ("analysis") | `analyses` | `POST /api/workflow/run` with `save`, `POST /api/workflow/run-and-save` | `GET /api/analyses`, `GET /api/analyses/{id}`, exports |
| Logged-out tokens | `revoked_tokens` | `POST /api/auth/logout` | every authenticated request |
| Verification / reset tokens (SHA-256 only) | `email_tokens` | `POST /api/account/verify/request`, `/password/forgot` | `/verify/confirm`, `/password/reset` |
| Public share links (SHA-256 only) | `share_links` | `POST /api/scenarios/{id}/share` | `GET /api/shared/{token}` |
| Account security history | `audit_events` | login, logout, share create/revoke, scenario update/delete | `GET /api/auth/activity`, admin audit |

Derived, not stored, by design: a simulation result. `POST /api/simulate` is a pure function of its
request, and the app stores a result only when a user explicitly saves it — as a scenario
(configuration) or an analysis (model output plus citations). Reproducing a shared scenario
re-runs the current model rather than replaying a frozen number, so a saved page cannot show a
result the shipped model no longer produces.

## 3. In-memory state found in production paths

| Item | Where | Verdict |
| --- | --- | --- |
| Rate-limiter request windows | `app/middleware.py` (`defaultdict(deque)`) | Intentionally ephemeral. Losing it on restart widens a budget briefly; it stores no user data. |
| Request/error counters | `app/observability.py` | Intentionally ephemeral, documented in the payload (`"per-process; resets on deployment"`). |
| Development email outbox | `app/mailer.py` (`deque(maxlen=50)`) | Non-production only. In production with no SMTP the mailer refuses with 503 rather than pretending to deliver. |
| Model artifact cache | `app/research.py` (`lru_cache`) | Derived from checksum-verified files on disk; a miss re-reads them. |
| Evidence corpus / BM25 index | `app/evidence.py` | Built from packaged JSON at startup. |
| Engine handle | `app/storage.py` (`lru_cache(maxsize=1)` + lock) | A handle, not data. |

No route stores user data in a dictionary and returns it later. There is no in-process cache of
scenario or account rows.

## 4. Defects found and fixed

1. **Scenario read, update and delete did not exist.** Only create and list were routed, so no
   client could confirm a specific saved configuration had been stored intact, and an account could
   not rename or erase its own scenario. Added `GET`, `PATCH` and `DELETE /api/scenarios/{id}`,
   owner-scoped, with share links removed in the same transaction as the scenario.
2. **Retention could delete another account's data.** `save_scenario` trimmed history by row count
   across the whole table, so a busy account evicted the oldest rows of every other account. Now
   scoped to the owner (and to `owner_id IS NULL` for legacy rows).
3. **`owner_id` had no index on migrated databases.** `index=True` only applies when the table is
   created; a pre-existing database got the column without the index and every scoped query scanned
   the table. Added `CREATE INDEX IF NOT EXISTS`.
4. **Engine construction raced.** `lru_cache` is not atomic around a slow function, and building an
   engine runs `create_all`. Two concurrent first requests both missed the cache and both ran schema
   creation; PostgreSQL rejected the loser with a duplicate-key error on a catalog index. This was
   reproduced by the concurrency test, not hypothesised. Construction is now serialised by a lock
   with a fast path for the cache hit.
5. **Readiness could not tell "connected" from "migrated".** `database_health()` ran `SELECT 1`
   only, so a reachable database with missing tables reported `available` and then every account,
   history and share route failed. It now also inspects the seven required tables; `/api/ready`
   returns 503 `schema-incomplete` with the missing table names, and the payload gained
   `databaseSchema`.

## 5. Guarantees, stated plainly

* With `SPACEAGRISIM_DATABASE_URL` set to a PostgreSQL URL, every accessor in `storage.py` uses
  that engine. There is no code path that falls back to SQLite once a PostgreSQL URL resolves.
* SQLite is used only when no URL is configured (local demo / isolated tests). When the SQLite file
  lives under `/tmp`, `/api/ready` reports `storage.durable: false` and names the remedy.
* Every write is a single SQLAlchemy transaction. Multi-statement work (quota accounting, scenario
  delete plus share-link delete, token consumption) happens inside one `begin()` block, so a
  failure leaves no partial unit of work.
* Accessors are owner-scoped in the `WHERE` clause, not by a read-then-write sequence.
* `pool_pre_ping` means a connection the server dropped while idle fails visibly rather than
  surfacing as an opaque save error.

## 6. Known limitations

1. **Schema creation runs at first use, not as a deploy step.** `create_all` plus additive
   `ALTER TABLE` is idempotent and safe, but it runs with application credentials and the first
   request after a deploy pays for it. A dedicated migration tool (Alembic) with a migration role is
   the production-grade answer; the current approach was chosen to avoid a deploy-time secret the
   platform does not provide.
2. **Two processes can still race on first-ever schema creation.** The in-process lock fixes
   threads. The deployment runs `--workers 1` for exactly this class of reason; `create_all` is
   `checkfirst` and PostgreSQL takes an advisory lock internally, but this is not a proven
   multi-process guarantee.
3. **`scenarios.owner_id` is nullable** for legacy local demonstration rows. Rows created through
   the API always carry an owner; a legacy `NULL` row is not visible to any account.
4. **Retention is enforced on write, not by a scheduled job.** An account that stops writing keeps
   its rows past `max_history` until it writes again.
5. **`audit_events` is capped per account on write**, so a very old event can be trimmed. It is an
   operational history, not an append-only audit log.
6. **Revoked tokens are not garbage-collected.** Rows expire by timestamp but nothing deletes them.
7. **No backup or PITR is configured.** Durability here means "survives a restart", not "survives
   the loss of the database". That is a platform setting, not application code.

## 7. Production state

`GET /api/ready` on `https://spaceagrisim-api.onrender.com` returned HTTP 200 with
`database: available`, `databaseDialect: postgresql`, `storage.durable: true` before this change.
The persisted state itself is verified by the tests in `docs/DATABASE_PERSISTENCE_TEST_REPORT.md`,
which run against a real server on every CI run — not by reading that payload. `databaseSchema`
appears in the payload once this change is deployed.
