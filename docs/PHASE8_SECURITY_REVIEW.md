# Phase 8 — Security Review

Verified by attack, not by reading the code and agreeing with it. Every probe below
was executed against the running application; the observed status code is recorded
next to the expectation.

---

## Authentication boundary

| # | Probe | Expected | Observed |
|---|---|---|---|
| 1 | Valid bearer token → `/api/auth/me` | 200 | **200** |
| 2 | `alg: none` forged token | 401 | **401** |
| 3 | HS256 token signed with a wrong key | 401 | **401** |
| 4 | Correctly signed but expired (`exp` in past) | 401 | **401** |
| 5 | Correctly signed, missing required `jti` claim | 401 | **401** |
| 6 | Correctly signed, `sub` repointed at another user | 401 | **401** |
| 7a | No `Authorization` header | 401 | **401** |
| 7b | Malformed token (`not.a.token`) | 401 | **401** |
| 7c | Wrong scheme (`Basic`) | 401 | **401** |
| 8 | Logout, then reuse the same token | 401 | **204 → 401** |
| 9 | SQL injection attempt in the login email | 422 | **422** |

Probe 6 is the interesting one: the signature is valid because the attacker knows
nothing about the key — the point is that the handler does not trust `sub`. It
re-reads the user by email, compares the id, and checks `disabled`. A signature
proves the token was issued; it does not prove the identity still exists.

Probe 8 confirms revocation is genuinely wired to storage: `jti` is looked up, not
merely trusted for its presence.

## Password handling

- Argon2id via `argon2-cffi`, parameters measured at runtime: **time_cost 3,
  memory_cost 65536 KiB, parallelism 4** — above the OWASP minimum.
- Verification catches `VerifyMismatchError` and `InvalidHashError` and returns
  `False` in both cases, so a corrupt hash cannot raise into a 500 that
  distinguishes it from a wrong password.
- Minimum password length 12, enforced by the request model (probe: 422).
- `/api/auth/me` returns only `{"user": {...}}`; probed for `hash` / `password`
  keys — **none leaked**.
- Duplicate registration with a different-case email returns **409**, so
  registration cannot be used to enumerate which addresses exist beyond the
  existence fact itself.

## Abuse limits

| Bucket | Limit | Probe | Observed |
|---|---|---|---|
| `auth` paths | 30 / min per address | 40 rapid login attempts | 30 × 401, **10 × 429** |
| `auth` paths | 30 / min per address | 35 rapid registrations | 28 × 201, **7 × 429** |
| `/optimize` | 12 / min | configured | — |
| general | 180 / min | configured | — |

Body size is capped at 64 KiB in the middleware and at 64 k in `nginx.conf`, so
the API and the proxy agree. The limiter's tracking dict is pruned once it exceeds
10 000 keys, so it cannot grow without bound.

All responses carry `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: no-referrer`, `Permissions-Policy` restricting geolocation,
microphone and camera, plus a per-request `x-request-id`. Auth and scenario paths
additionally get `Cache-Control: no-store`.

## CORS

Configuration is validated at load time rather than at request time:

| Configured origin | Result |
|---|---|
| `["*"]` | **rejected** |
| `["https://*.example.com"]` | **rejected** |
| `["http://evil.example"]` | **rejected** (no HTTPS outside localhost) |
| `["http://localhost:5173"]` | accepted |

A preflight from `https://evil.example` returned **400** with no
`Access-Control-Allow-Origin`. A preflight from the configured dev origin returned
200 with that exact origin echoed — not `*`.

## Findings

### F1 — Per-address rate limiting degrades behind a reverse proxy (medium, deployment-dependent, not fixed)

`RequestGuard` keys its buckets on `scope["client"][0]`. Behind the bundled
`nginx.conf`, every request to the API arrives from the proxy's address, so all
users share one bucket: the per-address limit silently becomes a global limit, and
one busy client can exhaust it for everyone.

Deliberately **not** fixed by trusting `X-Forwarded-For`: an application that
trusts that header unconditionally can be bypassed by any client that sets it,
which would be a worse bug than the one it fixes. The safe fix depends on
deployment topology — either terminate rate limiting at the edge, or accept
forwarded headers only from a configured, trusted proxy address. Both need
knowledge of the production ingress, which is unavailable here.

Until then: document it, and do not deploy the app directly behind a proxy that
forwards without stripping client-supplied `X-Forwarded-For`.

### F2 — No HSTS or CSP at the edge (low, cannot verify)

`frontend/nginx.conf` listens on port 80, sets `server_tokens off` and three
security headers, and leaves TLS to an upstream terminator. There is no
`Strict-Transport-Security` and no `Content-Security-Policy`.

HSTS belongs on the TLS terminator, which is not in this repository and cannot be
inspected without deployment access. `X-Frame-Options` also differs between layers
(`SAMEORIGIN` at nginx, `DENY` at the API); the browser applies the most
restrictive, so this is cosmetic, but the inconsistency is worth noting.

A CSP was **not** added, deliberately. The SPA includes a three.js greenhouse and
inline styles; a policy tight enough to be worth having would have to be developed
against the real bundle, and Phase 8 is forbidden from changing UI behaviour. An
untested CSP added at the end of a phase is how dashboards break in production.

### F3 — Previous phases' controls re-verified, no regression

Phase 4's invariants still hold: explicit CORS, no wildcard, bounded bodies, no
credential in any response, revocation enforced, and history writes gated behind
`history_writes_enabled` (`false` on Vercel, so a serverless deployment cannot
silently accumulate unbounded writes on ephemeral storage).

## What cannot be verified here

Production verification requires a deployed instance with real credentials. These
are **blocked, not passed**:

1. Multi-instance operation. The JWT signing key and the revocation store must be
   shared across replicas; with the ephemeral fallback secret, a restart
   invalidates every token and a second replica cannot validate the first's.
2. TLS configuration and HSTS behaviour at the real terminator.
3. Edge rate limiting under real traffic.
4. Secret-manager integration for `SPACEAGRISIM_AUTH_SECRET`.

No claim of production security verification is made anywhere in this phase. What
is claimed is narrower and checkable: the authentication boundary, the CORS policy,
the abuse limits and the password handling behave as intended when attacked, on a
local instance, with the evidence above.
