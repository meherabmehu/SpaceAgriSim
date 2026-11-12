# Automated encrypted database backup — setup and runbook

Date: 2026-11-09
Applies to: the Render-hosted PostgreSQL 18 instance behind `spaceagrisim-api.onrender.com`.

**Status, stated plainly.** The automation is committed and its components were executed locally
against a PostgreSQL **18** server with production-shaped data (dump → verify → encrypt → decrypt →
restore into a separate database → 17/17 restore checks). It has **not yet run in GitHub Actions**,
because this environment has no GitHub credential to push the workflow or create the repository
secrets. The first real run is the manual `workflow_dispatch` in §5 — until that run is green, the
honest status is "implemented and proven offline, awaiting secrets".

Why it exists: Render's Free compute plan provides **no backups, no logical exports and no
point-in-time recovery**, and a Free database **expires 30 days after creation**
([Render docs, free instances](https://render.com/docs/free#30-day-limit);
[backups](https://render.com/docs/postgresql-backups)). A `pg_dump` from outside Render is the
vendor's own documented workaround. Scheduling it in CI is what turns the recovery point objective
from "whenever someone remembered" into a number.

---

## 1. How it fits together

```
                ┌──────────────────────────── GitHub Actions ────────────────────────────┐
 02:17 UTC      │ db-backup.yml                                                         │
 daily      ──► │  1 refuse to run without secrets                                       │
 (or manual)    │  2 install PostgreSQL 18 client  (pg_dump >= server major)              │
                │  3 .pgpass 0600  → no password in any argv                             │
                │  4 pg_dump -Fc → verify with `pg_restore --list` + row counts           │
                │  5 gpg AES-256 → decrypt round-trip must match SHA-256                  │
                │  6 upload ONLY the .gpg files as an artifact (retention 14 days)        │
                └───────────────────────────────────────────────────────────────────────┘
 weekly         ┌───────────────────────────────────────────────────────────────────────┐
 Sun 03:41 UTC  │ db-restore-verify.yml                                                 │
                │  download artifact → decrypt → throwaway postgres:18 container         │
                │  → scripts/restore_validate.py (schema, counts, ownership) → report    │
                └───────────────────────────────────────────────────────────────────────┘
 every 30 min   production-monitor.yml → scripts/monitor_production.py → /health /ready /metrics
```

Three workflows, one shared property: **none of them can write to production.** The backup
workflow opens read-only sessions (`pg_dump` issues SELECTs only). The restore workflow never
receives a production URL at all, and `scripts/restore_validate.py` refuses any target that is not
local or that matches production (§4).

Files:

| Path | Purpose |
| --- | --- |
| `.github/workflows/db-backup.yml` | scheduled + manual dump, verification, encryption, artifact |
| `.github/workflows/db-restore-verify.yml` | weekly + manual restore into a throwaway database |
| `.github/workflows/production-monitor.yml` | health/readiness/metrics verdict every 30 minutes |
| `scripts/db_backup.py` | dump + verify + counts + manifest (SQLite and PostgreSQL) |
| `scripts/restore_validate.py` | safety gates, restore, schema/count/ownership verification |
| `scripts/monitor_production.py` | endpoint checks with a remedy for each failure |

## 2. Repository secrets — exact names and setup

GitHub → repository → **Settings → Secrets and variables → Actions → New repository secret**.

| Secret | Value | Where it comes from |
| --- | --- | --- |
| `PRODUCTION_DATABASE_URL` | the full URL, including `?sslmode=require` | Render dashboard → the PostgreSQL instance → **Connect** → **External Database URL** |
| `BACKUP_ENCRYPTION_PASSPHRASE` | a long random passphrase (≥ 32 characters) | generate it yourself, e.g. `openssl rand -base64 48`; store it in a password manager |

Rules that matter:

* Use the **External** Database URL. The Internal one only resolves inside Render's network, so a
  GitHub runner cannot reach it.
* The URL may carry `postgresql://` or `postgres://`; both are accepted. The workflow normalises
  the SQLAlchemy form too, so pasting `postgresql+psycopg://…` also works.
* **Keep a copy of the passphrase outside GitHub.** If it is lost, every artifact becomes
  unreadable — the backup is only as recoverable as that one string. That is the deliberate
  trade-off: the alternative (storing the key next to the ciphertext) protects nothing.
* Secrets are never echoed. GitHub masks them in logs; the workflow additionally never puts the
  password on a command line, never writes the URL to a file, and prints only sizes, table names
  and row counts.
* If **external access is restricted by an IP allowlist** on the database, GitHub-hosted runners
  will be blocked — their addresses change per run. Either leave external access open on the Free
  instance, or run the workflow on a self-hosted runner with a fixed address.

Nothing else needs configuring: `GITHUB_TOKEN` (automatic) is enough for the cross-run artifact
download in the restore workflow.

## 3. What a run produces, and where it lives

* One artifact per run: `spaceagrisim-db-backup-<run_id>`, containing
  `spaceagrisim-<stamp>.dump.gpg` and `spaceagrisim-<stamp>.dump.manifest.py.gpg`.
* Encryption: GPG symmetric, **AES-256**, passphrase-derived key, no compression (a custom-format
  dump is already compressed). The plaintext dump exists only inside the runner's temp directory
  and is deleted before upload.
* The manifest (encrypted alongside) records: creation time, dialect and database **name** (never
  host, user or password), byte count, SHA-256, archive entry count, the tables found **in the
  archive**, and per-table row counts read from the source with `SELECT COUNT(*)`.

**Retention.** The artifact retention is the retention policy:

| What | Retention | Where |
| --- | --- | --- |
| Daily artifact | **14 days** (`retention_days` input, 1–90) | GitHub Actions artifacts |
| Restore-validation report | 30 days | GitHub Actions artifacts |
| Long-term / monthly | indefinite | **you** download and archive it (§6) |

14 days of dumps at ~12 KB each is well inside any storage quota, and it satisfies the "7 dailies
plus a monthly" rule in `docs/DATABASE_BACKUP_AND_RECOVERY.md` once a monthly copy is downloaded.
GitHub deletes artifacts after the retention window; there is no "keep forever" switch, which is
why the monthly download is a checklist item rather than a nicety.

**The repository is public.** That matters: workflow artifacts on a public repository can be
downloaded by any GitHub user, not only by collaborators. Encryption is therefore not
belt-and-braces, it is the control that keeps the artifact from being a public copy of the
database. Two hardening options, neither of which this phase changed on its own authority:

1. make the repository private (GitHub Free includes private repositories and Actions minutes), or
2. keep the repository public and keep the retention short (14 days) while storing the durable copy
   in your own encrypted storage.

## 4. Restore validation — what is actually checked

`scripts/restore_validate.py` refuses to run before it checks anything:

| Gate | Refusal |
| --- | --- |
| target identical to `--production-url` / `$PRODUCTION_DATABASE_URL` | "target is the production database" |
| target has the production database **name** | "target has the production database name" |
| target host is not `127.0.0.1`, `localhost`, `::1`, `postgres`, `db` | "not a local address" (unless `--allow-remote`) |
| target already holds the seven application tables | "must start from an empty database" |
| dump is not a readable custom-format archive | "re-take the backup" |

Then, after `pg_restore --exit-on-error`:

| Check | Why it is there |
| --- | --- |
| all seven tables present | a "successful" restore that lost a table is not a restore |
| `scenarios.owner_id`, `users.email_verified`, `users.password_changed_at`, `ix_scenarios_owner_id` | the additive migrations actually landed |
| every table's row count equals the dump's manifest | catches a truncated archive and a partial restore |
| no orphan rows on six ownership edges (`scenarios/analyses/share_links/email_tokens/audit_events` → `users`, `share_links` → `scenarios`) | a restore that loses the account but keeps its data is a silent data-loss bug |
| no empty password hashes, no duplicate emails | the restored accounts are still usable |
| legacy unowned scenarios are **counted and reported**, never "fixed" | production data is not rewritten to satisfy a checker |

Exit codes: `0` all checks passed · `1` a check failed · `2` refused to run · `3` the restore itself
failed.

### Evidence from the offline run

Executed on 2026-11-09 against **PostgreSQL 18.6** (the same major version Render runs), with a
source database seeded through the application's own storage layer — two accounts, three scenarios
(one legacy unowned row), one saved analysis, one share link, one email token, one audit event:

```
$ python3 scripts/db_backup.py --from-libpq-env --out <dir>
{"backupPath": "spaceagrisim-20261109T180015Z.dump", "sha256": "25dba99e…", "bytes": 11991,
 "backend": "postgresql"}
manifest: … (tocEntries 30, tablesInDump 7, rowCounts {users 2, scenarios 3, analyses 1,
            share_links 1, email_tokens 1, audit_events 1, revoked_tokens 0})

$ gpg --symmetric --cipher-algo AES256 …          # 11991 B plaintext → 12096 B ciphertext
roundtrip sha256 matches, archive still lists with pg_restore, wrong passphrase rejected

$ python3 scripts/restore_validate.py --dump … --expected … --target-url …/spaceagrisim_restore_check
  [ok] dump:readable-toc: 7 table-data entries listed by pg_restore
  [ok] dump:contains-required-tables: all seven tables are in the archive
  [ok] restore:pg_restore-exit-on-error: pg_restore completed without errors
  [ok] schema:application-tables / …:columns / …:indexes
  [ok] rows:match-dump-manifest: all table counts match the dump's manifest
  [ok] ownership:scenarios.owner_id->users … ownership:audit_events.user_id->users: no orphans
  [ok] accounts:usable-rows / accounts:unique-email
  [ok] ownership:legacy-unowned-scenarios: 1 scenario row has no owner (reported, not modified)
  17/17 checks passed
```

Then the **application itself** was pointed at the restored database, which is the check that
matters — a restore no application can read is still a loss:

```
database_health : {'dialect': 'postgresql', 'status': 'available', 'schema': 'present'}
migrations      : {'appliedCount': 4, 'pendingCount': 0, 'total': 4}
storage durable : {'dialect': 'postgresql', 'durable': True}
accounts        : ['drill.owner@example.invalid', 'drill.second@example.invalid']
scenarios owned : ['DRILL-scenario']
```

Negative gates, also executed, all exited 2 with the reason quoted in §4's table: production URL
target, production database name, remote host, non-empty target, truncated dump
(`pg_restore: error: could not read from input file: end of file`).

**What this does not prove.** It ran locally, not against Render, and the dataset is tiny (a 12 KB
dump). It proves the mechanism end to end and the timing only for a database this size. The
production exercise is `db-restore-verify.yml` after the first real backup.

## 5. Running it (manual steps)

**First run, in order:**

1. Create the two secrets (§2).
2. Actions → **Encrypted production database backup** → *Run workflow*.
3. Open the run: the summary shows the artifact name, retention, and that the archive verified.
   Any failure names the missing secret or the failing tool in plain language.
4. Actions → **Restore validation (throwaway database)** → *Run workflow* (leave `backup_run_id`
   blank to use the newest successful backup). It prints a per-check table in its summary.
5. Download the artifact once and archive it somewhere durable (§6). This is the monthly habit.

**Restoring for real** (disaster recovery) — full procedure in
`docs/DATABASE_BACKUP_AND_RECOVERY.md` §4; the short form:

```bash
# 1. Download the artifact from the workflow run, then decrypt.
gpg --decrypt spaceagrisim-<stamp>.dump.gpg > spaceagrisim-<stamp>.dump

# 2. Confirm it is intact before touching anything.
sha256sum spaceagrisim-<stamp>.dump          # must equal .manifest.py's "sha256"
pg_restore --list spaceagrisim-<stamp>.dump | head

# 3. Restore into a NEW database (a fresh Render Postgres, or a local one for rehearsal).
pg_restore --no-owner --no-privileges --exit-on-error \
  --dbname 'postgresql://USER:PASSWORD@HOST:5432/NEW_DB?sslmode=require' \
  spaceagrisim-<stamp>.dump

# 4. Verify with the same script CI uses.
python3 scripts/restore_validate.py --dump spaceagrisim-<stamp>.dump \
  --target-url 'postgresql://USER:PASSWORD@HOST:5432/NEW_DB'   # add --allow-remote for a
                                                              # dedicated throwaway instance
# 5. Cut over by pointing SPACEAGRISIM_DATABASE_URL at the new database, then run
#    scripts/production_smoke.py.
```

## 6. Limits and known gaps

* **The automation has not run on GitHub yet.** No credential was available to push the workflow or
  create the secrets. The first green `workflow_dispatch` run is what changes this line.
* **Render's own backups still do not exist.** This is an off-platform copy, taken daily. It cannot
  recover the last few hours, because it is not PITR: the RPO is "up to 24 hours". Only a paid
  instance type provides a recovery window measured in minutes.
* **The Free database expires.** 30 days after creation, then a 14-day grace period, then Render
  deletes it. See `docs/DATABASE_BACKUP_AND_RECOVERY.md` §9 — the backup is what makes that
  survivable rather than fatal.
* **Artifact download is not a backup strategy on its own.** GitHub can disable scheduled workflows
  in a repository with no pushes for 60 days, and artifacts expire. The monthly download and the
  monitor's "last backup" awareness are both human steps.
* **No backup-absence alerting.** A failed scheduled run sends GitHub's default notification to the
  repository owner only. Wiring it to email or chat needs a paid notification service or a
  third-party action; not introduced here.
