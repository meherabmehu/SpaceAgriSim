# Final live production verification

SpaceAgriSim — independent verification of the deployed application.

| | |
|---|---|
| Verification date | 2026-11-12, 05:38–06:00 UTC |
| Target | `https://spaceagrisim-web.onrender.com` (frontend), `https://spaceagrisim-api.onrender.com` (backend) |
| Claimed deployed commit | `f6f6da1fa3637c1d5b59bc57e00fb4085076eb43` |
| Verified GitHub `main` HEAD | `f6f6da1fa3637c1d5b59bc57e00fb4085076eb43` |
| Method | live HTTP probes, headless Chromium (Playwright) against the production URLs, byte comparison of deployed artifacts against a local rebuild of the same commit |
| Code changes made | **none** |
| Deployments triggered | **none** |
| Render settings touched | **none** |
| Production database writes | **none** (every request issued was a read or a pure computation; see §2.4) |

---

## 0. Verdict

**PRODUCTION LIVE — PARTIALLY VERIFIED.**

**Not "VERIFIED", and deliberately so.** Every check that could be performed passed — there were no
failures of any kind — but one *mandated* check could not be performed at all: §7 asks for the Render
logs and deployment status for both services, and this environment has no Render credential
(`api.render.com/v1/services` returns `401 {"message":"Unauthorized"}` with the only account available
here, and creating a Render token is forbidden by the rules). The report therefore cannot claim full
verification, because an essential check remains untested.

Two categories are NOT TESTED: Render's logs/dashboard (§7, no access) and the authenticated
logged-in experience (§4.5, no production account exists and creating one is forbidden — which the
task explicitly authorises marking NOT TESTED). Everything else passed.

| # | Category | Verdict |
|---|---|---|
| 1 | Deployed version identity | **PASS** |
| 2 | Backend live API | **PASS** |
| 3 | Frontend, 16 routes × 3 viewports | **PASS** |
| 4 | Authentication and access control (signed-out, forged tokens) | **PASS** |
| 4b | Authenticated, signed-in experience | **NOT TESTED** |
| 5 | Scientific modules and evidence | **PASS** |
| 6 | Security (non-destructive) | **PASS** |
| 7a | Render logs / dashboard / deployment status | **NOT TESTED** — blocks the overall verdict |
| 7b | Runtime health observed from outside | **PASS** (substitute, limited) |

No category failed. One mandated category (§7a) is untested, and one (§4b) is untested with the task's
explicit permission; that is what makes the overall state PARTIALLY VERIFIED rather than VERIFIED.

---

## 1. Deployed version identity

### 1.1 GitHub `main` HEAD

```
$ git ls-remote origin refs/heads/main
f6f6da1fa3637c1d5b59bc57e00fb4085076eb43    refs/heads/main
```

Local `HEAD` in the verified checkout: `f6f6da1fa3637c1d5b59bc57e00fb4085076eb43`, working tree
clean, 0 commits ahead or behind `origin/main`. This matches the SHA supplied for the deployment.

### 1.2 The running backend is this commit — proven by schema equality

The OpenAPI document is generated from the application's own route and model definitions, so two
different commits produce two different documents almost immediately. Generated from the committed
tree at `f6f6da1` and fetched from production:

| | |
|---|---|
| Locally generated from `f6f6da1` | 91,545 bytes |
| Fetched from `https://spaceagrisim-api.onrender.com/api/openapi.py` | 91,545 bytes |
| Canonicalised (sorted keys) comparison | **IDENTICAL** |

83 paths, 90 operations, `SpaceAgriSim API` v0.1.0 on both sides.

### 1.3 The running frontend is this commit — proven by byte equality

The production bundle was rebuilt locally from `f6f6da1` with the production API base URL, and every
shared artifact was compared by SHA-256:

| Artifact | Live vs local |
|---|---|
| `index-DM3jsIKX.js` (34,691 B) | **IDENTICAL** |
| `index-CEyO1MZR.css` (54,622 B) | **IDENTICAL** |
| `vendor-react-Bl4wyysX.js` (192,906 B) | **IDENTICAL** |
| `vendor-icons-BkiIBxMZ.js` (18,305 B) | **IDENTICAL** |
| `vendor-charts-B89hi3F6.js` (402,652 B) | **IDENTICAL** |
| `DigitalTwin3D-J2l9go_u.js` (25,637 B) | **IDENTICAL** |
| `GuidedWorkflows-CcfIJU3J.js` (29,913 B) | **IDENTICAL** |

A Vite build emits content-hashed filenames, so a byte-identical `index-DM3jsIKX.js` is not a
coincidence: the deployed bytes are the bytes this commit produces.

The deployed bundle also confirms the production API wiring: the string
`https://spaceagrisim-api.onrender.com/api` appears 4 times, and `localhost` / `127.0.0.1` appear
**0** times.

### 1.4 Service liveness

| Check | Result |
|---|---|
| `GET https://spaceagrisim-api.onrender.com/` | 200, `application/json`, 0.24 s |
| `GET https://spaceagrisim-web.onrender.com/` | 200, `text/html`, 0.07 s |
| All static assets referenced by `index.html` | 200, correct MIME types |
| `x-render-origin-server: uvicorn` | present on API responses (Render → uvicorn, as configured) |

**Verdict: PASS.** Both services are live and both provably correspond to `f6f6da1`. Whether a
deployment job is still *pending* cannot be read without Render access; it is inferred absent because
the served artifacts already equal the commit exactly (§7 for the limitation).

---

## 2. Backend live API

### 2.1 Entry points

| URL | Status | Time | Content-Type | Body |
|---|---|---|---|---|
| `/` | 200 | 0.24 s | application/json | `{"message":"SpaceAgriSim API is running","docs":"/api/docs"}` |
| `/api/health` | 200 | 0.27 s | application/json | `{"status":"ok","service":"SpaceAgriSim API","version":"0.1.0"}` |
| `/api/ready` | 200 | 1.59 s | application/json | 681 B; see §2.5 |
| `/openapi.py` | **404** | 0.24 s | application/json | `{"detail":"Not Found"}` |
| `/api/openapi.py` | 200 | 1.54 s | application/json | 85,916 B schema |

`/openapi.py` 404 is **correct**: the application mounts everything under `/api`, and the schema is
served at `/api/openapi.py`. This was confirmed from the running service rather than assumed, and
it is why the schema (§1.2) was read before any other endpoint was probed.

### 2.2 Read endpoints — all passed

33 read endpoints were called. **Every one returned 200, `application/json`, and a body that parsed
as JSON.** Median latency 0.24 s, slowest 0.88 s.

| Endpoint | Status | Bytes | Latency |
|---|---|---|---|
| `/api/config` | 200 | 10,074 | 0.24 s |
| `/api/crops` | 200 | 954 | 0.21 s |
| `/api/datasets` | 200 | 85,186 | 0.24 s |
| `/api/datasets/live-status` | 200 | 15,879 | 0.23 s |
| `/api/models` | 200 | 157,210 | 0.32 s |
| `/api/workflow/models` | 200 | 24,647 | 0.25 s |
| `/api/assumptions` | 200 | 7,761 | 0.22 s |
| `/api/scientific-summary` | 200 | 1,592 | 0.23 s |
| `/api/science/calibration` | 200 | 11,796 | 0.23 s |
| `/api/science/checksums` | 200 | 3,274 | 0.23 s |
| `/api/science/classification` | 200 | 30,891 | 0.26 s |
| `/api/science/evidence` | 200 | 3,416 | 0.59 s |
| `/api/science/measurements` | 200 | 25,435 | 0.24 s |
| `/api/provenance` | 200 | 21,218 | 0.25 s |
| `/api/benchmarks` | 200 | 6,543 | 0.26 s |
| `/api/closed-loop` | 200 | 6,234 | 0.24 s |
| `/api/external-validation` | 200 | 14,618 | 0.25 s |
| `/api/external-datasets` | 200 | 1,399 | 0.21 s |
| `/api/explorer/datasets` | 200 | 14,852 | 0.79 s |
| `/api/explorer/overlaps` | 200 | 33,766 | 0.64 s |
| `/api/water-use-evidence` | 200 | 3,651 | 0.24 s |
| `/api/workflows` | 200 | 2,054 | 0.23 s |
| `/api/workflows/units` | 200 | 7,387 | 0.22 s |
| `/api/workflows/water-demand/capability` | 200 | 5,529 | 0.57 s |
| `/api/workflows/light-stress/capability` | 200 | 8,185 | 0.23 s |
| `/api/workflows/light-stress/controlled-environment/capability` | 200 | 5,295 | 0.22 s |
| `/api/reference-et0/model` | 200 | 2,870 | 0.21 s |
| `/api/metrics` | 200 | 1,047 | 0.46 s |
| `/api/assistant/health` | 200 | 302 | 0.88 s |
| `/api/assistant/provider` | 200 | 641 | 0.23 s |
| `/api/assistant/corpus` | 200 | 247 | 0.23 s |
| `/api/assistant/suggestions` | 200 | 1,633 | 0.24 s |
| `/api/models/tomato-flight-response-v1/example` | 200 | 2,824 | 0.58 s |
| `/api/datasets/OSD-46/preview` | 200 | — | 0.24 s |

### 2.3 Computational endpoints — all passed

These POST endpoints compute a response and persist nothing. Each was called with inputs taken from
the live schema (bounds and enums read from `/api/openapi.py`, not invented).

| Endpoint | Status | Result summary |
|---|---|---|
| `/api/simulate` | 200 | `cropYield` 21,492.3 g, `waterUsed` 389.4 L, `estimatedOxygenProduced` 1,337.3 g, provenance `physics-based estimate` |
| `/api/compare` | 200 | matched vs baseline scenario pair |
| `/api/optimize` | 200 | baseline + optimised configuration |
| `/api/advisor` | 200 | 3+ sourced insights |
| `/api/water-use-evidence/compare` (scale 1.0) | 200 | verdict `shape-only`, mean ratio 0.623 |
| `/api/water-use-evidence/compare` (scale 2.0) | 200 | verdict `shape-only`, mean ratio 1.247 — *changes with the input, as it must* |
| `/api/predict/lettuce-earth-growth-v1` | 200 | 20.602 g fresh shoot mass/plant |
| `/api/predict/lettuce-earth-growth-v2` | 200 | 9.891 g |
| `/api/predict/lettuce-earth-growth-v3` | 200 | 18.022 g |
| `/api/predict/mizuna-microbial-relative-load-v2` (flight) | 200 | +1.227 SD, `validated-exploratory` |
| `/api/predict/mizuna-microbial-relative-load-v2` (ground) | 200 | −0.753 SD |
| `/api/predict/radiation-exposure-osd46-v1` | 200 | `irradiated`, p 0.999995 |
| `/api/predict/radiation-quality-osd46-v1` | 200 | `control`, p 0.993909 |
| `/api/predict/tomato-flight-response-v1` | 200 | `flight`, p 0.5138, `calibrated: false` |
| `/api/workflow/validate` | 200 | `valid: true`, 4 features |
| `/api/workflow/run` (`save: false`) | 200 | full interpreted workflow output |
| `/api/workflow/compatible` | 200 | exact match list |
| `/api/reference-et0/validate` | 200 | Hargreaves ET₀ 5.3 mm/day |
| `/api/assistant/ask` | 200 | `status: grounded`, answers with cited passages |
| `/api/reports/json` | 200 | provenance-carrying mission report |

One **422** was observed and is correct behaviour, not a defect: `/api/predict/mizuna-microbial-relative-load-v2`
rejected `freshWeightG: 100.0` because the schema bounds it to 0–50 and `harvestIndex` to 1–5. Re-run
inside the declared bounds, both directions returned 200. **The only 4xx/5xx seen in the whole
computational sweep was that one, and it was my input error, correctly reported.**

### 2.4 What was deliberately not called

Nothing in this verification wrote to production. Excluded on purpose:

`POST /api/scenarios` (creates a record) · `POST /api/workflow/run-and-save` · `POST /api/scenarios/{id}/share`
· `POST /api/auth/register` · `POST /api/auth/verify/*` · `POST /api/auth/password/*` ·
`POST /api/auth/login` · `POST /api/auth/logout` · `DELETE`/`PATCH /api/scenarios/{id}` ·
`DELETE /api/analyses/{id}` · all seven `/api/predict/*` beyond the single read-only runs above
(those are pure functions).

`/api/workflow/run` was called with `save: false` and its sibling `run-and-save` was not called at
all, so no analysis row could have been created.

### 2.5 Readiness detail

```json
{ "status": "ready",
  "simulation": "available",
  "database": "available",
  "databaseDialect": "postgresql",
  "databaseSchema": "present",
  "databaseMigrations": { "applied": 4, "total": 4, "pending": 0 },
  "databasePool": { "pooled": true, "size": 5, "checkedOut": 0, "capacity": 10, "exhausted": false },
  "storage": { "durable": true, "reason": "Rows live in a PostgreSQL database that outlives the application process." },
  "emailDelivery": "unconfigured",
  "shareLinks": true,
  "rateLimitIdentity": "socket",
  "operatorConsole": false,
  "scientificValidation": "uncalibrated mathematical estimates" }
```

PostgreSQL, schema present, 4 of 4 migrations applied, 0 pending, pool not exhausted, storage declared
durable. `emailDelivery: unconfigured` and `operatorConsole: false` are honest capability reports, and
both match the observed behaviour in §4 (verification email not configured; `/api/admin/*` returns 404).

**Verdict: PASS.** 52 API calls across read and computational endpoints; zero unexpected statuses.

---

## 3. Frontend, by route and viewport

### 3.1 Method

Headless Chromium navigated to each of the 16 hash routes on the **live** URL at three viewports —
desktop 1440×1100, tablet 820×1180, mobile 412×915 (Pixel 7 device profile). For each of the 48
combinations the run recorded: document status, rendered text length, page height, horizontal
overflow, broken images, `console` errors, `pageerror` exceptions, responses ≥ 400 and failed
requests. Each route was then **reloaded** and re-measured, so a route that only works via in-app
navigation would fail here.

Evidence: `browser_results.py` and 48 screenshots in `screenshots/`.

### 3.2 Results — 48 of 48 clean

| Route | Desktop | Tablet | Mobile |
|---|---|---|---|
| `#dashboard` | 200 · 2,416 chars · h1649 | 200 · 2,260 · h2468 | 200 · 2,231 · h2530 |
| `#laboratory` | 200 · 3,889 · h2287 | 200 · 3,872 · h3268 | 200 · 3,843 · h3894 |
| `#predictions` | 200 · 13,291 · h7060 | 200 · 13,274 · h10502 | 200 · 13,264 · h12447 |
| `#workflow` | 200 · 3,626 · h2404 | 200 · 3,609 · h3017 | 200 · 3,599 · h3752 |
| `#workflows` | 200 · 4,901 · h1849 | 200 · 4,884 · h2499 | 200 · 4,874 · h3504 |
| `#assistant` | 200 · 2,026 · h1100 | 200 · 2,009 · h1262 | 200 · 1,999 · h1406 |
| `#greenhouse` | 200 · 1,663 · h1100 | 200 · 1,646 · h1327 | 200 · 1,603 · h1368 |
| `#comparison` | 200 · 1,948 · h1577 | 200 · 1,899 · h2322 | 200 · 1,869 · h2315 |
| `#crops` | 200 · 2,977 · h1452 | 200 · 2,960 · h2532 | 200 · 2,950 · h2769 |
| `#datasets` | 200 · 7,051 · h4226 | 200 · 7,034 · h7266 | 200 · 7,024 · h7807 |
| `#analytics` | 200 · 2,238 · h2504 | 200 · 2,221 · h2864 | 200 · 2,191 · h2899 |
| `#advisor` | 200 · 2,455 · h1406 | 200 · 2,438 · h1603 | 200 · 2,428 · h1778 |
| `#benchmarks` | 200 · 8,684 · h3881 | 200 · 8,667 · h5486 | 200 · 8,657 · h7322 |
| `#models` | 200 · 8,344 · h4100 | 200 · 8,327 · h4672 | 200 · 8,317 · h4794 |
| `#account` | 200 · 1,248 · h1100 | 200 · 1,231 · h1180 | 200 · 1,221 · h915 |
| `#methodology` | 200 · 3,097 · h1290 | 200 · 3,080 · h1719 | 200 · 3,070 · h2128 |

Aggregated across all 48:

| Signal | Count |
|---|---|
| Document status not 200 | **0** |
| Console errors | **0** |
| Uncaught page errors | **0** |
| Responses ≥ 400 | **0** |
| Failed network requests | **0** |
| Broken images | **0** |
| Horizontal page overflow | **0 px** (maximum across all 48) |
| Blank screens | **0** (minimum 1,221 characters rendered) |
| Broken after reload | **0** |

The `#models` table is 995 px wide inside a `.table-scroll` container with `overflow-x: auto`
(client 342 px on mobile) while the **page** overflows by 0 px — a deliberate inner scroll region, not
a layout break. Verified explicitly rather than assumed.

### 3.3 Console and network

Every API call the pages make goes to the production backend and every one returned 200. Distinct
call outcomes observed from the browser: 17, all 200 —

`/api/config`, `/api/simulate`, `/api/compare`, `/api/datasets`, `/api/models`, `/api/ready`,
`/api/benchmarks`, `/api/closed-loop`, `/api/external-validation`, `/api/explorer/overlaps`,
`/api/water-use-evidence`, `/api/water-use-evidence/compare`, `/api/workflow/models`,
`/api/workflows/water-demand/capability`, `/api/advisor`, `/api/assistant/corpus`,
`/api/assistant/suggestions`.

No CORS errors, no mixed-content blocks, no requests to `localhost`.

### 3.4 Navigation and refresh

In-app navigation was exercised by clicking, not by typing URLs: *Simulation lab* → `#laboratory`,
*NASA data explorer* → `#datasets`, *Model comparison* → `#models`, *Research assistant* →
`#assistant`, *Methodology* → `#methodology`. All five changed the hash and rendered the expected
heading. Every one of the 16 routes additionally survived a hard reload at all three viewports.

### 3.5 Loading and error states

With `/api/**` blocked at the browser, `#benchmarks` still rendered 1,124 characters — navigation,
headings and an explanatory message — rather than a blank panel or a white screen. Screenshot:
`screenshots/error-state-api-blocked-desktop.png`.

**Verdict: PASS.** 48/48 combinations, zero console errors, zero failed requests, zero overflow.

---

## 4. Authentication and access control

### 4.1 Signed out (tested)

| Probe | Status | Body |
|---|---|---|
| `GET /api/auth/me` | 401 | `{"detail":"Authentication is required"}` |
| `GET /api/auth/activity` | 401 | `{"detail":"Authentication is required"}` |
| `GET /api/scenarios` | 401 | `{"detail":"Authentication is required"}` |
| `GET /api/analyses` | 401 | `{"detail":"Authentication is required"}` |

The `#account` route renders a sign-in affordance, shows **no** email address, **no** private list and
**no** red authentication banner. (A 401 banner on the signed-out account page was a defect fixed
earlier in this project; this confirms it stays fixed in production.)

### 4.2 Forged and malformed credentials (tested)

| Probe | Status | Body |
|---|---|---|
| `Bearer not-a-real-token` | 401 | `Invalid or expired authentication token` |
| `Bearer ` (empty) | 401 | `Authentication is required` |
| `Basic YWRtaW46YWRtaW4=` | 401 | `Authentication is required` |
| `alg:none` JWT with `sub: admin`, exp 2099 | 401 | `Invalid or expired authentication token` |
| Random 40-char operator token | 401 | `Invalid or expired authentication token` |

The `alg:none` attempt is the important one: an unsigned token asserting `sub: admin` is rejected. The
operator console is not merely protected but **absent** — `/api/admin/summary` and `/api/admin/audit`
return `404 {"detail":"Not found"}` with and without a token, exactly as designed when no operator
token is configured.

### 4.3 Cross-account and invalid identifiers (tested)

| Probe | Status | Body |
|---|---|---|
| `GET /api/scenarios/{random uuid}` | 401 | `Authentication is required` |
| `GET /api/analyses/{random uuid}` | 401 | `Authentication is required` |
| `GET /api/analyses/{random uuid}/export/json` | 401 | `Authentication is required` |
| `GET /api/shared/{random token}` | 404 | `Shared scenario not found or no longer available` |
| `GET /api/datasets/definitely-not-a-study` | 404 | `Study not registered` |
| `GET /api/explorer/datasets/definitely-not-a-study` | 404 | `Unknown dataset` |
| `GET /api/models/not-a-model/explanation` | 404 | `Unknown model` |
| `GET /api/models/not-a-model/reference-profiles` | 404 | `Unknown model` |

No private record was returned for any guessed identifier, and no error message revealed whether a
record exists.

### 4.4 Session expiry — NOT TESTED

Testing expiry end-to-end requires a real session, so it is **NOT TESTED** here. What *is* verified is
the rejection path every expired session would take: a token that is invalid or past its expiry returns
401 with `Invalid or expired authentication token` (§4.2), and the client treats 401 as signed-out
(§4.1, no banner). The lifetime bound (≤ 24 h) is enforced by the application's settings validation,
verified locally in the deployment-configuration checks — not observed in production.

### 4.5 The signed-in experience — NOT TESTED

**No production account exists and creating one is forbidden by the task rules, so the authenticated
pages (saved scenarios, analysis history, share links, account settings) were not exercised live.**
No credentials were guessed. The logic behind those pages is covered by 1,258 (SQLite) and 1,282
(PostgreSQL) automated backend tests in the delivered tree, plus Playwright tests that register and
sign in against a local instance — but **none of that is live-production evidence**, and it is not
presented as such.

**Verdict: PASS for signed-out and forged-token access control; NOT TESTED for the authenticated
experience.** Anonymous users are not shown protected information.

---

## 5. Scientific modules

A page can load cleanly and still show the wrong thing, so this section reads the rendered text and
compares it against the live API. 44 assertions, all passing.

### 5.1 Model registry (`#predictions`, `#models`)

All 7 served models are listed and all 7 live verdicts match the API exactly:

| Model | Evidence verdict | Decision grade |
|---|---|---|
| `lettuce-earth-growth-v1` | fails-independent-check | no |
| `lettuce-earth-growth-v2` | fails-independent-check | no |
| `lettuce-earth-growth-v3` | fails-independent-check | no |
| `mizuna-microbial-relative-load-v2` | passes-independent-check | **yes** |
| `radiation-exposure-osd46-v1` | no-independent-check | no |
| `radiation-quality-osd46-v1` | no-independent-check | no |
| `tomato-flight-response-v1` | no-independent-check | no |

The page states these numbers in its own words: *"1 of 7 is currently decision grade: 3 failed an
independent check, 3 have never been scored by one"*. The vocabulary is rendered verbatim per card
(`fails-independent-check`, `no-independent-check`), together with the **measurement behind each
verdict** — for example *"0 of 6 independent treatment means covered, prediction/measurement ratio
median 3.655 (1.905–5.493)"* — not a summary that could be mistaken for a pass.

The registry also states what the table must **not** be used for: *"not rank one against another,
which the metrics do not support"*, and every model is shown beside its own baseline (`MAE 38.94`
against `125.83`). Withdrawn models are declared absent rather than silently dropped: *"Models
withdrawn in Phase 31 are not listed here: their artifacts and evaluations are kept as documented
negative results."*

Verdict language observed and required:

- *"The prediction is shown for inspection, not as a validated forecast."* — present.
- *"NASA-trained exploratory models have narrower scope than the habitat simulator and do not
  validate its lettuce, tomato, or radish forecasts."* — present.

### 5.2 Measured / derived / predicted separation

| Claim the product must never make | Result |
|---|---|
| "validated for spacecraft operations" | only occurrence is the footer *"Not validated for spacecraft operations"* — a disclaimer |
| "flight-qualified" | absent |
| "certified for crew use" | absent |

The dashboard labels its own numbers: *"Mechanistic estimate"*, *"Scenario output · No calibrated
confidence interval"*, *"physics-based estimate"*. The prediction page labels model output with
`evidenceStatus` and a per-model scope (`decisionScope` for the mizuna model names the two VEG-04
campaigns and states that a third campaign's offset must come from its own baseline samples).

### 5.3 Figures match the API

The dashboard was read and compared with the live `/api/simulate` response for the same default
configuration:

| Displayed | API | Match |
|---|---|---|
| Predicted biomass `21.5 kg` | `cropYield` 21,492.3 g | ✔ |
| Water supplied `389.4 L` | `waterUsed` 389.4 | ✔ |
| Oxygen estimate `1,337.3 g` | `estimatedOxygenProduced` 1,337.3 | ✔ |
| Harvested yield `0 kg` (next harvest day 35) | `harvestedYield` 0.0 for a 30-day run of a 35-day cycle | ✔ |

### 5.4 Provenance, duplicates and gaps

- *"A registered study is not automatically a downloaded training table."*
- *"OSD-320 is a second deposit of OSD-46"* with the measurement: *"minimum correlation 1.000000 and
  maximum absolute difference 0.0"* — the duplicate-deposit safeguard is not a claim, it carries its number.
- *"45 shared sample identifiers"* between OSD-655 × OSD-780, flagged as shared material rather than
  two independent samples.
- Opening a study's `Details` panel renders *"Provenance & processed data · Files, eligibility,
  licensing and limitations"*.

### 5.5 Benchmarks and honesty about gaps

- *"Every number below is read from a pinned artifact. None of them was used to tune the model."*
- *"The simulator fixes and transpires roughly a seventh of what the chamber did per square metre.
  That is the honest headline: the per-area magnitude is the same order, and the crop models are not
  calibrated to this chamber."*
- Model ÷ measured ratios shown (`×0.13`, `×0.14`, `×0.96`, `×1.18`), not hidden.

### 5.6 Crop intelligence

- *"NASA study associations provide research context, not parameter calibration."*
- *"Radish and tomato crop parameters are not validated simply because a related NASA study exists."*

### 5.7 Research assistant

Corpus boundary and retrieval status vocabulary (`grounded` / `partial` / `insufficient`) are rendered,
and a live `POST /api/assistant/ask` returned `status: grounded` with cited passages.

### 5.8 Water / resource evidence

`/api/water-use-evidence` and `/api/water-use-evidence/compare` return a `shape-only` verdict that
describes itself: *"The seasonal shape agrees and the level does not"*, with mean ratio `0.623` at
light scale 1.0 and `1.247` at 2.0 — the comparison tracks its input rather than being a fixed string.

**Verdict: PASS.** 44 of 44 content assertions pass; no fabricated or unsupported claim was found; every
limitation the project documents is visible in the live UI.

---

## 6. Security (non-destructive)

| Check | Result |
|---|---|
| Anonymous access to private endpoints | 401 on all four; nothing leaked |
| Forged / malformed / `alg:none` tokens | 401 on all five |
| Operator console without configuration | 404, does not confirm its existence |
| Guessed UUIDs and study/model ids | 404 with a neutral message; no record returned |
| Path traversal attempt (`/api/models/../etc/passwd`) | 404 `{"detail":"Not Found"}` |
| Malformed JSON body | 422 with a structured `validation_error`, no traceback |
| Out-of-bounds numeric input | 422 naming the bound (`less than or equal to 50`) |
| Wrong HTTP method (`DELETE /api/health`) | 405 `{"detail":"Method Not Allowed"}` |
| Error bodies | JSON only; **no stack trace, no file path, no SQL, no credential** in any response observed |
| Security headers | `x-content-type-options: nosniff`, `x-frame-options: DENY` |
| Request correlation | `x-request-id` present on responses |

### CORS

Measured with an explicit `Origin` header and a preflight (`Access-Control-Request-Method: POST`,
`Access-Control-Request-Headers: content-type, authorization`):

| Origin | Simple GET → ACAO | Preflight |
|---|---|---|
| `https://spaceagrisim-web.onrender.com` | echoes the origin | **200**, `allow-origin` echoes it, methods `GET, POST, OPTIONS`, `max-age 600` |
| `http://localhost:5173` | echoes the origin | 200, echoes it (development origin, as configured) |
| `https://evil.example.com` | **no** ACAO header | **400**, no ACAO |
| `null` | **no** ACAO header | **400**, no ACAO |

The production frontend is allowed; unlisted origins are refused. `Vary` includes `Origin`, so a cache
cannot serve one origin's headers to another.

> Note on method: an early pass of my harness reported "no ACAO on any response". That was a bug in
> **my** harness — HTTP/2 delivers header names lower-cased and my first reader did a case-sensitive
> dict lookup. Re-measured through the header API and by `curl -D`, CORS is present and correct. The
> wrong reading is recorded here rather than deleted, because a verification report that hides its own
> false negative is worth less than the paper it is written on.

**Verdict: PASS.**

---

## 7. Render runtime verification

### 7.1 Logs and deployment status — NOT TESTED

Render's logs, build history and service dashboard are reachable only through Render itself. **No
Render API credential exists in this environment**, and the task forbids changing any Render setting —
including creating a token. The following could therefore not be observed and are reported honestly as
**NOT TESTED**:

- build completion and build logs for either service;
- deployment status / "still deploying" state;
- per-request 4xx/5xx lines in Render's log stream;
- database connection-failure lines;
- restart counts;
- the boundary between historical errors and errors after the latest deploy.

### 7.2 What was observed instead — PASS (substitute, with its limits)

| Substitute check | Result |
|---|---|
| Both services respond right now | 200 from both |
| Served artifacts equal the commit byte-for-byte | §1.3 — 7/7 identical |
| Served schema equals the commit byte-for-byte | §1.2 — identical |
| Readiness reports a healthy PostgreSQL with 4/4 migrations | §2.5 |
| Database pool not exhausted | `checkedOut: 0`, `exhausted: false` |
| No restart during a 2.5-minute observation window | in-process request counters went **738 → 739**, monotonic, no counter reset |
| Total requests served by the running process | 738+ across 83 distinct paths at first sample |
| Static assets served with correct MIME types | 5/5 |

What this proves: the process serving traffic has been alive and consistent for at least the
observation window, has served several hundred requests including all of mine, and is the build it
claims to be. What it does **not** prove: that no restart happened earlier, what the logs contain, or
that the deployment job reported success. Those remain NOT TESTED.

**Verdict: 7a NOT TESTED · 7b PASS (limited).**

---

## 8. Supporting evidence

The evidence files live in the verification workspace (`live_evidence/`, outside the repository) and
are **not committed**, per the instruction that this report is a report only. The screenshot paths below
are relative to that directory.

| Artifact | Contents |
|---|---|
| `live_evidence/browser_results.py` | 48 route × viewport records: status, text length, overflow, console/page errors, failed requests, screenshot paths |
| `live_evidence/get_sweep.py` | 33 read endpoints: status, latency, content type, byte counts, body heads |
| `live_evidence/post_sweep.py` | 19 computational calls with bodies |
| `live_evidence/auth_probe.py` | 22 authorization probes |
| `live_evidence/cors.py` | 8 CORS probes |
| `live_evidence/errors_cors.py` | 7 error-handling probes |
| `live_evidence/live_openapi.py` | the production schema as served (85,916 B) |
| `live_evidence/scientific_findings.py` | 44 scientific-content assertions |
| `live_evidence/ux_findings.py` | 21 interaction and accessibility assertions |
| `live_evidence/screenshots/` | 51 PNGs: 48 route/viewport captures plus OSD-46 detail, and the blocked-API error state |
| `live_evidence/deployed_index.js` | the production entry bundle as downloaded, used for the base-URL and SHA-256 comparison |

Screenshots reviewed by eye during the run: `dashboard-desktop.png` (real API figures, Earth imagery
credited, "Mechanistic estimate" label), `predictions-desktop.png` (per-card verdicts with measured
numbers), `models-mobile.png` (mobile layout, inner-scrolling table), `error-state-api-blocked-desktop.png`
(readable failure, navigation intact), `datasets-osd46-details-desktop.png` (provenance panel).

---

## 9. What this report does not claim

- It does not claim the **authenticated** application was exercised in production. It was not.
- It does not claim Render's **logs** were read, or that the deploy job reported success. They were not.
- It does not claim anything about **email delivery**: production reports `emailDelivery: unconfigured`,
  so registration verification mail cannot be sent; that is a configuration fact, not a defect.
- It does not claim the **operator console** works: it is disabled by configuration and returns 404.
- It does not claim performance beyond the latencies measured from this one vantage point over roughly
  600 seconds of testing; Render free-tier cold starts were not separately induced or measured.
- It does not claim the scientific claims are *true*. It claims the application **reports them
  accurately**, with their verdicts, their measured numbers and their limitations intact.

---

## 10. Final decision

**PRODUCTION LIVE — PARTIALLY VERIFIED.**

Why not "VERIFIED": the task requires the Render logs and deployment status to be inspected, and that
inspection could not be performed from here — there is no Render credential in this environment and
obtaining one is out of bounds. "Do not claim full verification if any essential checks remain
untested" is the instruction, and the instruction is followed: the inability to read the deploy log is
an untested essential check, regardless of how clean everything else is.

Why not "VERIFICATION FAILED": nothing failed. Not one assertion in this report is red. The
qualification is about *access*, not about the application.

What was measured, restricted to what can be evidenced:

- The deployed commit is proven, not inferred: the API schema served in production is byte-identical
  to the schema generated from `f6f6da1`, and seven production asset bundles are SHA-256 identical to
  a local rebuild of the same commit.
- 52 API calls: every read endpoint 200 with valid JSON; every computational endpoint 200; the single
  422 was a correct rejection of an out-of-bounds input I supplied.
- 48 of 48 route × viewport combinations: no console error, no page error, no 4xx/5xx, no failed
  request, no broken image, no horizontal overflow, no blank screen, no broken reload.
- 44 of 44 scientific-content assertions: verdicts, measured numbers, provenance and limitations all
  render as the evidence requires, and no unsupported claim appears.
- 21 of 21 interaction and accessibility assertions, including a live check that changing the crop
  refreshes every metric card together with no stale figure left behind.
- Authorization behaves correctly for anonymous, forged, `alg:none` and guessed-identifier requests;
  CORS admits the production origin and refuses unlisted ones.

Because §7a (Render logs and deployment status) and §4.5 (the signed-in experience) are untested, the
overall state is **PARTIALLY VERIFIED**. Both are enumerated above with what was used in their place
and what that substitute cannot prove. Neither reflects an observed defect: the application, as
reachable from the public internet, behaved correctly in every test performed.

To close the remaining gap, whoever holds the Render account needs to: open both services' *Logs* and
*Events* tabs, confirm the latest deploy shows `f6f6da1` and completed successfully, and scan the
post-deploy window for 5xx lines, database connection failures or restart events. That is a five-minute
check and it is the only thing standing between PARTIALLY VERIFIED and VERIFIED.
