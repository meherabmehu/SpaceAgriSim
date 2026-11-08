# Phase 19 — accounts, sharing, deployment truth, and the request budget behind a gateway

Phase 19 closes the gaps that were real product holes rather than missing science: an account you
could not verify or recover, saved work you could not share, a security history nobody could read,
and a per-address request budget that quietly becomes a global one behind a managed gateway.

Nothing here changes a scientific claim. The simulator, the evidence panels and the NASA data
explorer behave exactly as they did in Phase 18, and every new surface says so.

## What shipped

### 1. Email verification and password reset

| Endpoint | Purpose | Answer |
| --- | --- | --- |
| `POST /auth/verify/request` | send a verification link | `202` whether or not the address exists |
| `POST /auth/verify/confirm` | consume the link | `200`, or `400` if used/expired/unknown |
| `POST /auth/password/forgot` | send a reset link | `202` whether or not the address exists |
| `POST /auth/password/reset` | set a new password | `200`, or `400` if the link is spent |

Design decisions, each one a failure mode that is silent if done otherwise:

* **Single use.** `email_tokens.used_at` is checked and set inside one transaction, so two
  concurrent submissions of the same link cannot both succeed.
* **Hashed at rest.** Only a SHA-256 digest is stored. A database read cannot be replayed into a
  working reset link.
* **One live token per purpose.** Requesting again retires the previous link instead of leaving
  several valid ones behind.
* **No enumeration.** The request endpoints answer `202` for unknown addresses and write nothing.
* **Reset retires sessions.** `set_password` stamps `password_changed_at`; tokens carry the stamp
  they were issued under as a `pwd` claim and are rejected once it moves. No session table needed.
* **Verification is recorded, not enforced.** `emailVerified` is on the user object and the UI
  prompts, but an unverified account keeps working. Locking existing accounts out of their own
  saved scenarios to add a checkbox would be a regression, not a feature.

### 2. Email delivery, honestly

`app/mailer.py` has exactly three modes:

1. **SMTP configured** — send for real.
2. **Development outbox** (no SMTP, non-production) — a bounded in-memory outbox, and the request
   endpoint returns the token so the flow is testable without inventing a mail provider.
3. **Production without SMTP** — `503` naming the variables to set. It never answers "sent" when
   nothing was sent.

`/api/ready` reports the active mode as `emailDelivery`.

### 3. Account security history

`audit_events` records account creation, sign-in, failed sign-in, sign-out, verification, password
change, reset request, and share-link create/revoke. Each account sees only its own events
(`GET /auth/activity`), the history is trimmed to `SPACEAGRISIM_MAX_ACTIVITY_EVENTS`, and no row
stores an address, an IP, or anything a person typed.

### 4. Read-only share links

`POST /scenarios/{id}/share`, `DELETE /scenarios/{id}/share`, and public `GET /shared/{token}`.

* Read-only, and it exposes **no owner id, no email, no other scenario**. A test asserts the
  shared payload does not contain the owner's address.
* Capped per scenario (`SPACEAGRISIM_MAX_SHARE_LINKS_PER_SCENARIO`, default 3), expiring
  (`SPACEAGRISIM_SHARE_LINK_DAYS`, default 30), and revocable wholesale.
* The public payload **re-runs the stored configuration** instead of storing its output, so a
  shared page can never drift from what the current model produces for that input.
* Sharing a scenario you do not own answers `404`, the same as one that does not exist.
* The UI route is `/#shared/<token>`, which works on a static host without a rewrite rule.

Account email links are fragments for the same reason: `/#reset?token=…` and `/#verify?token=…`
always load the app, while `/reset?token=…` depends on a host rewrite a static deployment does
not have.

### 5. Deployment truth in the product

`/api/ready` and the **Account & sharing** panel report:

* `storage.durable` — SQLite under `/tmp` is called **not durable**, with the
  `SPACEAGRISIM_DATABASE_URL` remedy spelled out. A serverless demo that keeps SQLite in `/tmp`
  keeps accounts and scenarios for as long as the container lives; saying so is cheaper than
  discovering it after a cold start.
* `emailDelivery` — `smtp`, `outbox`, or `unconfigured`.
* `shareLinks` — whether sharing is available.
* `rateLimitIdentity` — `socket` or `forwarded` (see below).

### 6. The request budget follows the client

The guard always had per-address budgets. Behind a gateway, "address" was the gateway, so the
30/minute auth budget and the 180/minute general budget were shared by every visitor, and one
caller could spend them.

`SPACEAGRISIM_TRUSTED_PROXY_HOPS` now decides whether `X-Forwarded-For` is believed, and which
entry is used — the Nth from the **right**. It defaults to `0` on purpose: trusting a
client-supplied header while directly exposed lets a caller mint a fresh budget per request.

Verify the chain on the platform before enabling it; `/api/ready` shows which mode is active.

## Frontend

Preserved: no redesign, no framework change. Added:

* **Account & sharing** module (`src/pages/modules/Account.jsx`) — verification status, deployment
  guarantees, saved scenarios with share/revoke, and the account's own security history.
* **Shared scenario** public view (`src/pages/modules/SharedScenario.jsx`) — configuration,
  recomputed estimates, expiry, and the limitations that apply.
* **Auth dialog** gains *Forgot your password?*, plus reset and verify modes that consume
  `/#reset?token=…` and `/#verify?token=…` deep links.
* `src/services/accountApi.ts` — the account and sharing client.

Styles were appended to `platform.css`; no existing rule was modified.

## Verification

```
backend:  648 passed, 1 skipped   (the skip is the PostgreSQL-only integration test)
frontend: npm run lint / typecheck / build  — clean
```

Phase 18 baseline was 620 passed, 1 skipped; Phase 19 adds 28 cases across
`test_phase19_accounts_sharing.py` (22) and `test_phase19_gateway_limits.py` (6).

A live-server smoke run exercised the whole chain against real uvicorn: register → verify request
(dev outbox) → confirm → forgot → reset → old session `401` → sign in with the new password →
activity list → save scenario → share → public read with no owner data → revoke → `404`.

These are local checks. They are not production verification, and no claim is made here about any
deployment.

## Still open (disclosed, not filled)

* **Live OSDR re-sync** and a **model-comparison view** are not in this phase.
* Benchmark numbers from Phase 16/18 are still reachable from Methodology and Evidence but are
  not, yet, surfaced as a single panel.
* Science gaps unchanged and out of scope: ethylene/air-quality modelling, lunar and Martian
  regolith crop trials, a stress→yield-loss curve, spacecraft water-loop measurements, and any
  Moon/Mars yield claim from the molecular classifiers.

## Configuration added

See `backend/.env.example`: `SPACEAGRISIM_SMTP_*`, `SPACEAGRISIM_PUBLIC_APP_URL`,
`SPACEAGRISIM_EMAIL_VERIFICATION_HOURS`, `SPACEAGRISIM_PASSWORD_RESET_MINUTES`,
`SPACEAGRISIM_DATABASE_URL`, `SPACEAGRISIM_MAX_SHARE_LINKS_PER_SCENARIO`,
`SPACEAGRISIM_SHARE_LINK_DAYS`, `SPACEAGRISIM_MAX_ACTIVITY_EVENTS`,
`SPACEAGRISIM_TRUSTED_PROXY_HOPS`.
