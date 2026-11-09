# Database Backup and Recovery — SpaceAgriSim

Date: 2026-11-09
Applies to: the Render-hosted deployment (`spaceagrisim-api.onrender.com`) and its PostgreSQL
database.

**Bottom line, stated plainly:** Render provides **no backup and no point-in-time recovery** for
this database, because the Free compute plan includes neither. Since Phase 22 (2026-11-09) there is
an **off-platform, encrypted, scheduled `pg_dump`** in this repository's GitHub Actions, and a
restore-validation workflow that restores a backup into a throwaway PostgreSQL 18 database and
checks it row by row. That is a real backup — but it is *not* vendor-side recovery: the recovery
point is "the last successful daily run" (up to 24 hours), not "ten minutes ago".

The automation's components were executed locally against PostgreSQL 18 with production-shaped data
(§5.1); the first run inside GitHub Actions has **not happened yet**, because the workflow and its
two secrets are not on GitHub at the time of writing. `docs/DATABASE_BACKUP_AUTOMATION.md` is the
setup and runbook, including the exact secret names.

Nothing below claims a vendor backup exists. Where a fact is not verifiable from this environment,
it says so.

---

## 1. What Render provides (vendor documentation)

Read from Render's documentation on 2026-11-09 — [doc]:

| Plan | Automated backups | Point-in-time recovery | Retention | Logical exports |
| --- | --- | --- | --- | --- |
| **Free compute plan** | **None** | **None** | n/a | Not available |
| Hobby (paid) | Continuous (WAL) | Yes, **3 days** back | 3 days | Yes, `.dir.tar.gz`, kept **7 days** |
| Pro and above (paid) | Continuous (WAL) | Yes, **7 days** back | 7 days | Yes, kept **7 days** |

Other facts from the same source that matter operationally:

* PITR restores to **a point at least 10 minutes in the past**; you cannot restore to "now".
* A restore creates a **new database instance**; the existing one is not rewound in place. Cutover
  means pointing the API's `SPACEAGRISIM_DATABASE_URL` at the new instance.
* **Deleting a database deletes its backups.** Deleting the workspace deletes them too. Backups are
  a lifecycle feature of the instance, not an independent archive.
* Backup/restore actions are dashboard (or API) operations on the instance, not something the
  application can trigger.

**What is verified about *this* instance, and what is not.** `render.yaml` contains no
`databases:` block — the database was created in the dashboard — so its plan is not
version-controlled and cannot be read from this repository [executed]. No Render API key is
available in this environment, so the instance's plan and its backup status were **not** queried
**[not verified]**. What *can* be said with certainty: if the instance is on the Free compute plan,
everything in the first row applies, i.e. nothing exists to restore from.

The consequence is worth stating without softening: **the database currently holds the only copy of
every account, scenario, saved analysis and share link.** Losing the instance loses the data, and
the recovery point objective is "whenever someone last ran a manual dump".

## 2. What the data is, and what a loss costs

| Table | Contents | Reconstructible? |
| --- | --- | --- |
| `users` | Accounts: email, scrypt password hash, timestamps | **No.** Users would have to register again |
| `sessions` | Session/refresh state | Yes, by logging in again |
| `scenarios` | Saved habitat configurations, owner-scoped | **No.** User-authored input |
| `analyses` | Saved model runs (e.g. `lettuce-earth-growth-v3` output) | Only by re-running the same inputs, which are themselves lost with the scenario |
| `share_links` | Public read-only tokens | No, and links already sent out would 404 |
| `activities`, benchmark rows | Audit/derived | Partly derived |

Simulation results are deterministic functions of stored inputs, so the *code and models* are
recoverable from Git. The **user-authored inputs are not**, which is precisely what a backup has to
protect.

## 3. Manual backup procedure (works today, on any plan)

Render's *External Database URL* is required from a machine outside Render; the Internal URL only
resolves inside Render's network.

```bash
# 1. Take the dump. Render's external URL needs TLS: append ?sslmode=require if it is not there.
export PGPASSWORD='<password from the External Database URL>'
pg_dump 'postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require' \
        --format=custom --no-owner --no-privileges \
        --file="spaceagrisim-$(date -u +%Y%m%dT%H%M%SZ).dump"
unset PGPASSWORD

# 2. Verify the dump is a readable archive (does not touch the database).
pg_restore --list "spaceagrisim-<stamp>.dump" | head -20

# 3. Record a checksum next to it, so a truncated file cannot pass as a backup later.
sha256sum "spaceagrisim-<stamp>.dump" > "spaceagrisim-<stamp>.dump.sha256"
```

Rules that make this a backup rather than a gesture:

1. **Store it off Render.** A file on the API's disk is deleted on every deploy (free web services
   have an ephemeral filesystem) and shares the fate of the thing it is protecting.
2. **Encrypt or place it in access-controlled storage.** A dump contains password hashes and email
   addresses; it is as sensitive as the database.
3. **Keep the password out of shell history and logs.** Use `PGPASSWORD` from a secret store, and
   never put a URL on a command line where `ps` can read it (the scripts here pass URLs via the
   environment for that reason).
4. **Retention:** at least 7 daily dumps plus one monthly; 30 days is a better default for a dataset
   this small (the drill below produced a ~12 KB archive for a database with real rows).

On a **paid** instance there is a second, cheaper path: the dashboard's *Logical Export* produces a
`.dir.tar.gz` kept for 7 days. Use it in addition to, not instead of, a copy outside Render, since
it is deleted with the instance.

## 4. Restore procedure

Never restore straight over the live database. Restore into a **new** instance or a separate
database, verify, then cut over.

```bash
# 1. Create an empty target database (a new Render Postgres instance, or a local/CI database).
export PGPASSWORD='<target password>'
pg_restore --no-owner --no-privileges --exit-on-error \
           --dbname='postgresql://USER:PASSWORD@TARGET_HOST:5432/spaceagrisim_restore?sslmode=require' \
           spaceagrisim-<stamp>.dump

# 2. Compare row counts per table with the source's last known counts.
psql 'postgresql://…/spaceagrisim_restore' -c \
  "select 'users', count(*) from users union all
   select 'scenarios', count(*) from scenarios union all
   select 'analyses', count(*) from analyses union all
   select 'share_links', count(*) from share_links;"

# 3. Start the API against the restored database and let the readiness probe inspect it.
SPACEAGRISIM_DATABASE_URL='postgresql://…/spaceagrisim_restore' \
  uvicorn app.main:app --app-dir backend --port 8012
curl -s http://127.0.0.1:8012/api/ready
```

Cutover, when step 3 is green:

1. Set `SPACEAGRISIM_DATABASE_URL` on the `spaceagrisim-api` service to the restored database's
   **Internal** URL (Render service → Environment).
2. Deploy/restart the service. Auto-deploy is on with a commit trigger (Phase 22), so a restart is
   now an explicit **Manual Deploy** in the dashboard rather than a side effect of a push.
3. Confirm `/api/ready` → `status: ready` with `databaseMigrations: {applied: 4, total: 4,
   pending: 0}`.
4. Run `scripts/production_smoke.py` against the API to prove accounts and scenarios actually work,
   then log in with a real account and open a saved scenario.
5. Only then retire the old instance — and remember that deleting it deletes its backups.

If the app answers `database_schema_incomplete` after a restore, the restore did not include the
schema; if it answers `database_migration_pending`, restart the service once so the additive
migration runs. Neither response drops or rewrites data.

## 5. Recovery drill (executed, with results)

A dump that has never been restored is a hope. `scripts/restore_drill.sh` turns it into evidence.
It dumps the source read-only, restores into a **separate** database, and compares row counts; it
refuses to run when both URLs are the same or the target already has a schema.

Executed on 2026-11-09 against a local PostgreSQL 17.11 server, with a scenario and a share-link
lifecycle exercised through the API first so the dump contained real rows [executed]:

```
1/4 dumping source (read-only)…
    dump size: 12234 bytes
2/4 counting rows in the source…
    users: 3
    scenarios: 1
    analyses: 0
    share_links: 0
3/4 restoring into the target database…
4/4 comparing row counts…
    [ok]   users: 3
    [ok]   scenarios: 1
    [ok]   analyses: 0
    [ok]   share_links: 0
restore drill passed: the dump restores into a separate database with identical row counts
```

Then the restored database was handed to the application itself, which is the only check that
matters — a restore that no application can read is still a loss [executed]:

```
GET http://127.0.0.1:8012/api/ready
{'status': 'ready', 'databaseDialect': 'postgresql', 'databaseSchema': 'present',
 'databaseMigrations': {'applied': 4, 'total': 4, 'pending': 0}}

POST /api/auth/login  (drill account)   -> access token issued
GET  /api/scenarios   (with token)      -> ['DRILL-scenario']
```

So the recovery path is proven end to end: **dump → restore into a separate database → the API
reads the restored rows**. A user account from before the dump could log in afterwards and see its
scenario.

Limits of this evidence, stated rather than glossed:

* It ran against **local PostgreSQL 17.11**, not the Render instance. Restoring Render's own dump
  into a Render instance is the production exercise, and it needs dashboard access.
* The dump was small (three accounts, one scenario). It proves the mechanism, not the timing of a
  large restore; RTO for this dataset is seconds, but that is a property of its size today.

### 5.1 Phase 22: restore validation against PostgreSQL 18, with ownership checks

The drill above compares row counts. `scripts/restore_validate.py` goes further, because a count can
match while the *relationships* are broken: it checks the six ownership edges, the migration-added
columns and the account rows themselves, and it refuses any target that looks like production.

Executed 2026-11-09 against a local **PostgreSQL 18.6** server — the same major version Render runs
— with a source database seeded through the application's own storage layer (2 accounts, 3
scenarios including one legacy unowned row, 1 analysis, 1 share link, 1 email token, 1 audit event),
dumped with the same `scripts/db_backup.py` path the workflow uses:

```
dump:     11,991 bytes, sha256 25dba99e…, pg_restore --list lists 30 entries / 7 table-data blocks
encrypted: 12,096 bytes (GPG symmetric, AES-256); decrypt round-trip sha256 matches;
           a wrong passphrase is rejected; the round-tripped dump still lists as a valid archive
restore:   pg_restore --exit-on-error into spaceagrisim_restore_check -> no errors
checks:    17/17 passed
           - all seven tables, required columns, required index present
           - row counts equal the dump manifest for all seven tables
           - no orphans on scenarios/analyses/share_links/email_tokens/audit_events -> users,
             share_links -> scenarios
           - no empty password hashes, no duplicate emails
           - 1 legacy scenario without an owner: reported, not modified
app:       the API's own storage layer pointed at the restored database reads it correctly:
           {'dialect': 'postgresql', 'status': 'available', 'schema': 'present'},
           migrations 4/4 applied / 0 pending, durable True, both accounts, owner's scenario listed
```

Refusals, also executed, each exiting 2 without touching anything: production URL as target,
production database name on another host, a non-local host without `--allow-remote`, a target that
already had the schema, and a truncated dump
(`pg_restore: error: could not read from input file: end of file`).

Limits: it ran locally, not against Render, and the dump is 12 KB — it proves the mechanism, not the
timing of a large restore.

## 6. Recovery objectives implied by the current configuration

| Objective | Current answer | Why |
| --- | --- | --- |
| RPO (most data you can lose) | **Up to 24 hours** once `db-backup.yml` runs with its secrets; currently **unbounded** because it has not run yet | No vendor backup or PITR on the Free compute plan; the off-platform daily dump is the only recovery point |
| RTO (time to serve again) | Minutes *if a dump exists* (drill: seconds for this dataset), **never** if none exists | Restore + cutover as in §4 |
| Backup integrity assurance | Every run (archive listing + decrypt round-trip), every week (full restore validation) | §5 and §5.1; `db-restore-verify.yml` automates the weekly part |
| Protection against instance deletion | **None** | Render deletes backups with the instance |

## 7. Recommended actions, in order of cost-effectiveness

1. ~~Start a manual dump schedule~~ — **done in Phase 22**: `.github/workflows/db-backup.yml` runs
   daily at 02:17 UTC, plus `workflow_dispatch`. It moves the RPO from "unbounded" to "one day" the
   moment its two repository secrets exist. See `docs/DATABASE_BACKUP_AUTOMATION.md`.
2. **Run `scripts/restore_drill.sh` against a throwaway database quarterly** (or after any schema
   change), and keep its output with the release record. A backup nobody has restored is unproven.
3. **Move the database to a paid instance type** if the data matters. Hobby gives 3-day PITR, Pro
   gives 7 days, and that is the only way to recover from "a bad deploy wrote wrong rows an hour
   ago" without losing the intervening day.
4. **Represent the database in `render.yaml`** (a `databases:` block with plan, region and version)
   so its configuration is reviewable, and so a rebuild from the blueprint does not silently lack a
   database.
5. ~~Automate the dump in CI~~ — **written in Phase 22** (`db-backup.yml` + `db-restore-verify.yml`),
   pending the two repository secrets. Until those exist, a manual run is still the honest answer.
6. **Alert on backup absence.** The scheduled run notifies the repository owner on failure, which is
   GitHub's default and the only free mechanism. A "last verified dump" field on `/api/ready` was
   considered and rejected: the API never sees the dump artifacts, so it could only report a value
   someone wrote by hand, which is worse than no field at all.
7. **Raise the database to a paid instance type before the expiry date** if the account data is to
   survive (§8) — this is the only action in this list that needs a spending decision.

## 8. The database expires on 9 December 2026

This is the most time-critical fact in this document, and it is a hard vendor limit rather than a
risk that may or may not materialise. Render's documentation states it without qualification
([free instances](https://render.com/docs/free#30-day-limit)):

> Free Render Postgres databases **expire 30 days after creation**. An expired Free database is
> inaccessible unless you upgrade it to a paid compute plan. After a Free database expires, you have
> a grace period of **14 days** to upgrade it… After the grace period, Render **deletes** the
> database (along with all of its data).

Applied to this instance (creation date reported by the dashboard as 2026-11-09, expiry
**2026-12-09**):

| Date | What happens | What is still possible |
| --- | --- | --- |
| up to 2026-12-09 | normal service | everything |
| 2026-12-09 → 2026-12-23 | database **inaccessible**; 14-day grace | upgrade to a paid plan, or restore the last dump into a **new** instance |
| after 2026-12-23 | Render **deletes** the instance and all data | only an off-platform dump can restore anything |

Note the second row carefully: during the grace period the data still exists but the running API
cannot read it, so `/api/ready` will answer `database_unavailable` (with a SQLSTATE if the server
answered) and every account, scenario, analysis and share link will be unreachable. If that happens
and there is no dump, **the data is not recoverable** — it is not merely offline.

### Consequences, in order of severity

1. **Total loss of user-authored data if no backup exists.** Accounts, scenarios, saved analyses and
   share links are not derivable from Git; only the code and models are.
2. **Public share links break permanently.** `share_links` rows live in the same database; there is
   no external copy of the token → scenario mapping.
3. **Registered accounts must re-register**, and because `emailDelivery` is `unconfigured` there is
   no verification or password-reset mail to soften that.
4. **The API and web client stay up but useless.** Static hosting is unaffected, so the site loads
   and every data-backed action fails — a worse failure mode than a clean outage.

### Options, with what each actually costs

| Option | Data survives? | Needs approval / spend | Notes |
| --- | --- | --- | --- |
| **A. Upgrade the database compute plan** (Hobby or higher) | Yes, in place | **Yes — paid plan.** Not done, not recommended unilaterally | Hobby also brings 3-day PITR and logical exports; Pro brings 7 days |
| **B. Keep Free, recreate a new Free database before expiry** | Only if a dump is restored into it | No spend, but it expires 30 days later (a rolling 30-day horizon) | The workspace allows **one** Free Postgres at a time, so the old instance must be deleted — which is exactly why the dump must exist first |
| **C. Move to another provider's free tier** (e.g. Neon/Supabase free) | Only if a dump is restored | No spend; changes `SPACEAGRISIM_DATABASE_URL` | Out of scope here: a new vendor, new secrets, new latency profile |
| **D. Do nothing, keep the dumps** | No — the service loses its data on 2026-12-23 | No spend | The honest "acceptable for a demo, not for users" position |

**Restoring into a new instance is proven, not assumed:** the §5.1 run restored a dump into a
separate PostgreSQL 18 database and the application read accounts and scenarios back from it. Doing
the same against a new Render Postgres instance differs only in the host in
`SPACEAGRISIM_DATABASE_URL`; the client-major-version rule (install PostgreSQL **18** client tools,
as the workflow does) is the one thing that changes if the new instance runs a different major
version.

### Checklist for the expiry window

- [ ] A dump newer than 2026-12-08 is downloaded and stored **outside GitHub** (artifacts expire).
- [ ] Its SHA-256 matches the manifest, and `pg_restore --list` reads it.
- [ ] `db-restore-verify.yml` has been green on that artifact.
- [ ] The decision (upgrade / recreate / migrate / retire) is recorded before 2026-12-09.
- [ ] If upgrading or recreating: `SPACEAGRISIM_DATABASE_URL` is updated and `/api/ready` reports
      `status: ready` with `databaseMigrations.pending: 0`, and `scripts/production_smoke.py`
      passes 23/23 against the new instance.

## 9. What this document does *not* claim

* It does not claim a backup job is **running**: the workflow is committed, but nothing has executed
  it yet (no repository secrets existed when it was written). Until the first green run, the backup
  status is still "manual only" — `docs/DATABASE_BACKUP_AUTOMATION.md` §6 says the same thing.
* It does not claim the Render instance's plan was verified; it says what each plan provides and
  what an unverified plan means.
* It does not present the local drill as a production restore; it is the mechanism being proven, in
  the environment available to this audit.
