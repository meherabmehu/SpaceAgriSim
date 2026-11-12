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

### 7. Live OSDR provenance re-sync

`scripts/resync_osdr.py` asks the public OSDR bucket about every study the platform pins:

* HEADs each sampled file URL, following the `geode` 302 to its presigned target and using a
  one-byte ranged GET there, because a presigned URL is signed for `GET` and answers `403` to a
  plain `HEAD`;
* compares the served byte count with the pinned count;
* lists the `version-N` directories the study publishes today.

Per-study verdicts: `unchanged`, `newer-version-available`, `bytes-changed`, `missing-files`,
`version-only`, `not-checkable`. The script records `filesChecked` vs `filesTotal` (hashed files
are sampled first) and **never edits a pin** — a study whose bytes changed is reported so a human
can decide.

Result against the live repository on 2026-11-08:

| verdict | studies |
| --- | --- |
| unchanged | 14 |
| newer version published | 4 — OSD-120 (pinned v14, publishes v20), OSD-346, OSD-411, OSD-782 |
| version-only (no pinned URL to HEAD) | 6 |

`GET /datasets/live-status` serves that recorded snapshot with its age, a `stale` flag past 30
days, and an explicit note that it is not a live query per request. A deployment with no snapshot
says so and names the script.

### 8. Benchmark panel

`GET /benchmarks` assembles three things that used to live only in documents:

* the pinned Biomass Production Chamber artifact (NASA TM 102788) — measured CO₂, water, dry
  biomass and O₂ per m² per day, with the simulator's values under the chamber's own operating
  point and the model ÷ measured ratio;
* the leafy-green planning anchor (NTRS 20250001897): **59.5 g m⁻² day⁻¹**, with the simulator's
  57.1 (0.96×), radish 42.9 (0.72×) and tomato 43.8 (0.74×);
* the CO₂ response factor, **evaluated by calling the engine** at 420 / 1000 / 3000 ppm
  (×1.00 / ×1.18 / ×1.29), next to the measured optimum of 1000 ppm and the disclosure that the
  factor keeps rising above it.

The panel has no ranking and no composite score. Measured and modelled sit in adjacent columns
with the ratio, because the sizes of the gaps are the finding.

### 9. Model comparison

The **Model comparison** view lists every artifact-backed model with its own metric against its
own baseline, its validation scheme, its sample count and its declared input domain. There is
deliberately no ordering and no cross-model score: an R² on a transcriptomic classifier and an MAE
on a harvest regression are not commensurable, and a league table would invent a comparison the
metrics do not support.

## Verification

```
backend:  657 passed, 1 skipped   (the skip is the PostgreSQL-only integration test)
frontend: npm run lint / typecheck / build  — clean
```

Phase 18 baseline was 620 passed, 1 skipped; Phase 19 adds 37 cases across
`test_phase19_accounts_sharing.py` (22), `test_phase19_gateway_limits.py` (6) and
`test_phase19_benchmarks_and_resync.py` (9).

A live-server smoke run exercised the whole chain against real uvicorn: register → verify request
(dev outbox) → confirm → forgot → reset → old session `401` → sign in with the new password →
activity list → save scenario → share → public read with no owner data → revoke → `404`.

These are local checks. They are not production verification, and no claim is made here about any
deployment.

## Still open (disclosed, not filled)

Science gaps, unchanged and out of scope: ethylene/air-quality modelling, lunar and Martian
regolith crop trials, a stress→yield-loss curve, spacecraft water-loop measurements, and any
Moon/Mars yield claim from the molecular classifiers. None of them has a public dataset that
could fill it, and inventing one would be worse than the gap.

Operational notes for whoever deploys this:

* `/api/ready` reports `emailDelivery` and `storage.durable`. On a serverless host with SQLite
  under `/tmp`, accounts and scenarios do not survive a cold start — the payload says so.
* `SPACEAGRISIM_TRUSTED_PROXY_HOPS` must be set to the real hop count behind a gateway;
  `/api/ready` shows which identity mode is live.
* `scripts/resync_osdr.py` is a scheduled job, not a request path. Four pinned studies have newer
  versions published; re-pinning them is a deliberate, reviewed step.

## Configuration added

See `backend/.env.example`: `SPACEAGRISIM_SMTP_*`, `SPACEAGRISIM_PUBLIC_APP_URL`,
`SPACEAGRISIM_EMAIL_VERIFICATION_HOURS`, `SPACEAGRISIM_PASSWORD_RESET_MINUTES`,
`SPACEAGRISIM_DATABASE_URL`, `SPACEAGRISIM_MAX_SHARE_LINKS_PER_SCENARIO`,
`SPACEAGRISIM_SHARE_LINK_DAYS`, `SPACEAGRISIM_MAX_ACTIVITY_EVENTS`,
`SPACEAGRISIM_TRUSTED_PROXY_HOPS`.

## External validation — status: attempted against an independent study, failed

`GET /api/external-validation` serves `data/literature/external_validation_screen`. It reports
`externalValidationAvailable: false` and says so on the benchmarks page rather than presenting the
leave-one-experiment-out figures as if they were independent: four experiments from one research
group are still one source.

Each candidate is recorded with the four inputs the model needs and a verdict. A candidate is only
usable when all four are reported per observation. Substituting a study average across three light
levels for a single-PPFD prediction would produce a number that looks like validation and is not,
so PeerJ 17085 is held at `usable-after-transcription` with no measurement entered until its
supplemental table is copied verbatim.

`domainCheck` is evaluated against the served model artifact, not against a copy of the bounds kept
in the route, so the panel cannot claim a flag the prediction route does not raise. The check runs
through `/api/predict/lettuce-earth-growth-v2`, which answers 200 with `outOfDistribution: true` and
the violated bounds attached — flagging, not refusal, and not evidence about accuracy.

## Hosted database configuration — found broken, now diagnosable

While checking the live deployment on 2026-11-09, `GET /api/health` answered 200 but every
database-backed route failed: `/api/auth/login` returned an opaque **500** and `/api/shared/<token>`
returned **503 "Share links unavailable"**. Accounts, history and share links were all down on the
hosted instance while the same paths passed locally, which is precisely the case that
"no claiming production verification from local tests" exists for.

Two gaps caused the confusing read:

1. The storage layer accepted only `sqlite:///` and `postgresql+psycopg://`. Render's blueprint
   prints `postgresql://` and older add-ons print `postgres://`, so a correct connection string was
   rejected outright. Those aliases are now normalised, and a blank dashboard variable falls back to
   the default file instead of disabling every route.
2. A rejected URL surfaced as a bare 500 on login and a bare "Database unavailable" on readiness.
   Both now return `503 database_misconfigured` with a `reason` (`scheme-unsupported`,
   `path-unwritable`) and a remedy naming the variable. The URL, host and password are never echoed;
   a test asserts the password does not appear in the response.

`/api/ready` carries the diagnosis: `reason`, exception type, and the SQLSTATE when the server
answered at all. Observed on the live instance after the fix (2026-11-09): `reason:
connection-failed` with **no SQLSTATE**, which means the connection never reached a database server
— the URL form was accepted, and the failure is a suspended, deleted or wrongly addressed instance.
That is a dashboard setting, not a code path; the remaining action is to check the Postgres
instance behind `SPACEAGRISIM_DATABASE_URL` on Render.

The frontend and browser deployments cannot be verified from here either: the Vercel preview host
answers `302` (deployment protection), and no Vercel credentials are available in this environment.

### The transcription and the result

The PeerJ 17085 per-level table was obtained from the publisher's open-access full text (EuropePMC
JATS XML, SHA-256 `69f08243…d27bb`, CC BY 4.0) and copied by hand into
`data/literature/external_lettuce_peerj17085`: fresh weight per plant at 28 DAT for 'Baby Cos'
and 'Green Oak' at three canopy levels (PPFD 697 / 391 / 322 µmol m⁻² s⁻¹), with the publication's
own standard deviations and significance groups. No value was read off a figure, and the reported
study averages (100.4 g and 163.9 g) were deliberately not used in place of the per-level rows.

The model was then scored against all six observations, with predictions computed from the served
artifact on each request rather than stored:

| Observation | Measured (g) | Modelled (g) | Ratio |
|---|---|---|---|
| Baby Cos, upper (697 µmol) | 84.5 | 454.2 | ×5.38 |
| Baby Cos, middle (391 µmol) | 123.8 | 341.0 | ×2.75 |
| Baby Cos, lower (322 µmol) | 92.9 | 341.0 | ×3.67 |
| Green Oak, upper (697 µmol) | 97.3 | 454.2 | ×4.67 |
| Green Oak, middle (391 µmol) | 190.7 | 341.0 | ×1.79 |
| Green Oak, lower (322 µmol) | 203.7 | 341.0 | ×1.67 |

Median ×3.21, mean absolute percentage error 232 %, every observation overpredicted.

**Root temperature was not measured by the study.** It is assumed equal to the reported air
temperature (27.5 °C) and the assumption is recorded in the artifact rather than buried. Probing it
from 20 to 32 °C moves the median ratio only between ×2.28 and ×3.21, so this is not what produced
the gap.

### What the check found about the model, not just its numbers

- **It has no cultivar input.** The two cultivars differ by 63 % on average in the study — more
  than the light-level effect within either cultivar. Identical inputs therefore produce identical
  outputs, so this variation cannot be represented at all.
- **Its light response is monotonic and stepwise.** The observed response is not monotonic: 'Baby
  Cos' peaks at the middle level, 'Green Oak' at the lower level. A tree ensemble returns flat
  plateaus between split points (341.0 g for both 322 and 391 µmol) and cannot express either the
  peak or the cultivar crossover.

Recalibration alone cannot close this gap, because the missing structure is in the feature set. The
model stays exploratory and must not be used to forecast harvest weight or size a farm.
