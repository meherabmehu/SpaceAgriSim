# Database Backup and Recovery — SpaceAgriSim

Date: 2026-11-09
Applies to: the Render-hosted deployment (`spaceagrisim-api.onrender.com`) and its PostgreSQL
database.

**Bottom line, stated plainly:** as configured today this deployment has **no verified automated
backup and no point-in-time recovery**. The database lives on Render, the blueprint in this
repository does not describe it, and on a Free compute plan Render provides no backups at all. Until
that changes, the recovery plan is a manual `pg_dump` that someone has to remember to run, plus the
restore drill in this document that proves such a dump can actually be restored.

Nothing below claims a backup exists. Where a fact is not verifiable from this environment, it says
so.

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
2. Deploy/restart the service. `autoDeployTrigger` is `off`, so a restart is a deliberate action.
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

## 6. Recovery objectives implied by the current configuration

| Objective | Current answer | Why |
| --- | --- | --- |
| RPO (most data you can lose) | **Everything since the last manual dump**, i.e. unbounded if none was taken | No automated backup, no PITR on the Free compute plan |
| RTO (time to serve again) | Minutes *if a dump exists* (drill: seconds for this dataset), **never** if none exists | Restore + cutover as in §4 |
| Backup integrity assurance | Only from a drill that has actually restored the file | The drill in §5 is the mechanism |
| Protection against instance deletion | **None** | Render deletes backups with the instance |

## 7. Recommended actions, in order of cost-effectiveness

1. **Start a manual dump schedule now.** One `pg_dump` per day to encrypted storage outside Render,
   plus one before any risky operation. Cost: minutes; it moves RPO from "unbounded" to "one day".
2. **Run `scripts/restore_drill.sh` against a throwaway database quarterly** (or after any schema
   change), and keep its output with the release record. A backup nobody has restored is unproven.
3. **Move the database to a paid instance type** if the data matters. Hobby gives 3-day PITR, Pro
   gives 7 days, and that is the only way to recover from "a bad deploy wrote wrong rows an hour
   ago" without losing the intervening day.
4. **Represent the database in `render.yaml`** (a `databases:` block with plan, region and version)
   so its configuration is reviewable, and so a rebuild from the blueprint does not silently lack a
   database.
5. **Automate the dump in CI** (a scheduled workflow running `pg_dump` with a repository secret and
   uploading the archive) once the push token used here has the `workflow` scope — the token
   available during this audit does not, so no workflow change was made. Until then a local cron or
   a manual monthly run is the honest answer.
6. **Alert on backup absence.** A note in the release checklist is weaker than a monitor, but for a
   single-instance deployment it is what exists today; the `/api/ready` payload is the place to
   surface "last verified dump" if this is ever automated.

## 8. What this document does *not* claim

* It does not claim a backup job is configured, because none is.
* It does not claim the Render instance's plan was verified; it says what each plan provides and
  what an unverified plan means.
* It does not present the local drill as a production restore; it is the mechanism being proven, in
  the environment available to this audit.
