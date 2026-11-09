# Why the API runs one worker, and what would have to change first

Date: 2026-11-09
Applies to: `spaceagrisim-api` on Render (`--workers 1` in `render.yaml` and in the start command).

`--workers 1` is not a leftover or an oversight. It is the only safe setting for the request limiter
in `backend/app/middleware.py`, and raising it without replacing that limiter would silently
multiply every caller's budget. This note records the mechanism, the evidence, and the prerequisite
for scaling — so the next person does not discover it by being rate-limited in production.

## 1. What the limiter is

`RequestGuard` keeps a `defaultdict(deque)` keyed by `(client address, bucket)`, prunes entries
older than 60 seconds, and compares the deque length against a per-minute budget:

```python
self.requests = defaultdict(deque)          # process memory, nothing else
...
window = self.requests[key]
while window and window[0] < start - 60:
    window.popleft()
if len(window) >= limit:
    return 429
window.append(start)
```

The state is a Python object inside the worker process. There is no database row, no file, no
network call. Buckets are `auth` (stricter), `optimize` and `general`.

## 2. What happens at N workers

| Requests in a minute (per caller) | 1 worker | 2 workers | 4 workers |
| --- | --- | --- | --- |
| General budget, e.g. 60/min | 60 allowed | up to **120** allowed | up to **240** allowed |
| Auth budget, e.g. 10/min | 10 allowed | up to **20** allowed | up to **40** allowed |

Each worker only sees the requests it happened to serve, so the effective budget is
`limit × workers` — and which worker answers is up to the load balancer, so the effective budget is
not even a stable number: it varies with routing. That is the actual problem. A limit that changes
with the weather is not a limit, and it applies to login and password-reset attempts too, which are
the endpoints where it matters most.

Three more things multiply the same way:

* `/api/metrics` counters (`backend/app/observability.py`) are per process, so they would
  under-report by roughly a factor of N. The payload already says `"scope": "per-process"`.
* The connection pool is per worker: 5 + 5 overflow = **10 connections each**, so 4 workers would
  open up to 40 against an instance whose direct-connection budget is small (Free plan).
* Startup DDL is already safe across processes — `_initialise_schema()` takes a PostgreSQL advisory
  lock (`SCHEMA_LOCK_KEY`) with a bounded wait — so this is *not* the blocker. The limiter is.

## 3. The current budget is already shared by everyone (finding F1)

`/api/ready` reports `rateLimitIdentity`, and on the live deployment it reads:

```json
"rateLimitIdentity": "socket"
```

Behind Render's proxy every request arrives from the proxy's address, so with
`SPACEAGRISIM_TRUSTED_PROXY_HOPS=0` (the safe default) **all callers share one budget**. Setting it
to the real number of trusted hops makes the limiter key on the caller's address instead, but only
after the forwarding chain has been checked — believing a client-supplied `X-Forwarded-For` hands
every caller a fresh budget on demand, which is worse than a shared one.

The monitor treats `socket` as a warning, not a failure, for exactly this reason: it is a known,
documented degradation on a single-instance deployment, and fixing it needs a decision about the
proxy chain rather than a code change.

## 4. What would be needed to run more than one worker

Prerequisite, in order:

1. **A shared counter store.** Any of: Redis / Key Value (Render offers managed Key Value,
   including a Free tier), or a Postgres-backed counter table with an atomic
   `INSERT … ON CONFLICT DO UPDATE` and a TTL sweep. The limiter then becomes
   `INCR key; EXPIRE key 60`-style, and the budget is global because the store is global.
2. **A reachability guarantee.** Free *web* services cannot receive private network traffic — a
   Free Key Value instance would have to be reached over its **public** endpoint with TLS, or the
   web service has to move to a paid plan that can use the private network. This is a plan decision,
   not a code decision.
3. **A tested degrade path.** If the store is unreachable, the limiter must fail *closed* for auth
   and *open* for reads (a rate limiter that takes the site down is worse than one that briefly
   allows more), and the choice must be asserted in tests rather than left to the exception handler.
4. **A pool budget.** `pool_size + max_overflow` per worker × workers must stay under the
   database's direct-connection limit; the readiness payload reports capacity so this is measurable
   before and after.
5. **A load test.** None has been run. Without one, no claim about throughput at 2+ workers is
   supportable, and this document deliberately makes none.

None of these are introduced here: they need a managed Key Value instance and/or a paid plan, which
is a spending decision the project owner has not made. The worker count therefore stays at **1**,
and `render.yaml` carries a comment pointing at this file so a future change is not silent.

## 5. What to check if rate limiting looks wrong

| Symptom | Read this | Then |
| --- | --- | --- |
| Users report 429s in bursts | `/api/ready` → `rateLimitIdentity` | if `socket`, everyone shares one budget; decide on the proxy-hop setting |
| 429s only on login | `SPACEAGRISIM_AUTH_RATE_LIMIT_PER_MINUTE` | the auth bucket is intentionally tight; raising it weakens brute-force protection |
| 429s after a deploy | — | expected: counters reset with the process, so a caller who was throttled gets a clean budget |
| `/api/metrics` shows a `pool-timeout` failure class | `/api/ready` → `databasePool` | the bottleneck is the database pool, not the limiter; find the slow query first |
