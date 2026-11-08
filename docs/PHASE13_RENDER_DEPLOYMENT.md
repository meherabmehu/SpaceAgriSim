# Deploying SpaceAgriSim to Render — step by step

Written 2026-11-07 against Render's documented limits and verified against a production-mode run of
this repository. Two services: `spaceagrisim-api` (Python web service) and `spaceagrisim-web`
(static site). `render.yaml` at the repository root describes both.

> **Read §1 first.** Render's free tier has two properties that decide how you should deploy this,
> and neither announces itself at build time.

---

## 1. What the free tier actually does to this app

| Render free-tier behaviour | What it does to SpaceAgriSim |
|---|---|
| **Ephemeral filesystem** — no persistent disks on free | The default SQLite database is wiped on every redeploy, restart and spin-down. Registered accounts and saved analyses disappear. |
| **Free Postgres expires 30 days after creation**, then a ~14-day upgrade grace period, then deletion | Any database you create for the demo has a calendar date attached. |
| **Spins down after 15 minutes idle**, ~1 minute to wake | The first visitor after a quiet period waits ~1 minute, and anything holding in-memory state is reset. |
| 512 MB RAM / 0.1 CPU | Fine for this app: inference is pure Python arithmetic, no sklearn, no numpy at request time. Measured in-process request cost is 4–24 ms. |
| 750 instance-hours/month | One always-on service is ~730 h. One API service fits; two free web services would not. There is only one web service here, so it fits. |

**Consequences you must decide on:**

1. **Use Postgres** (recommended) or accept that accounts and analyses reset. With Postgres the app
   is genuinely usable; without it, treat every deploy as a fresh demo.
2. Either way, the **static site is free and never sleeps** — the site loads immediately, the API
   may take a minute on the first request.

---

## 2. What the blueprint already sets, and why

`render.yaml` was updated in this phase because three settings in the previous version would have
broken a live deploy:

| Setting | Before | Now | Why it matters |
|---|---|---|---|
| `SPACEAGRISIM_AUTH_SECRET` | absent | `generateValue: true` | Phase 13 makes production refuse to start without it. Without a durable secret, every spin-down invalidates all tokens — on the free tier that is every 15 minutes of inactivity. |
| `SPACEAGRISIM_ENVIRONMENT` | absent | `production` | Selects the strict settings above. |
| Web client | not in the blueprint | `spaceagrisim-web` static site | The blueprint previously deployed only the API, so there was no frontend to open. |
| `SPACEAGRISIM_HISTORY_WRITES_ENABLED` | `false` | `true` | It was disabling scenario saving. Safe now because the database is durable; set it back to `false` if you skip Postgres. |

Also fixed: `VITE_API_BASE_URL` cannot be derived automatically (Render's `fromService` yields a bare
host and the client needs `https://…/api`), so it is a `sync: false` value you paste once.

**Verified before writing this:** with the blueprint's settings the API boots in production mode,
`/api/ready` returns 200, and register → run → save → list → export → ask all succeed, with
`partial / unsupported-premise` returned for the Moon-yield question. The production guard was also
verified to **fail loudly** when the secret is missing.

---

## 3. Deploy, in order

### Step 1 — Push the updated blueprint

```bash
cd /home/user/SpaceAgriSim_repo
git push origin main
```

The blueprint must be on `main` before you create services, because `autoDeployTrigger: 'off'`
means Render will not redeploy on later pushes — you trigger each deploy yourself.

### Step 2 — Create the database first (recommended)

Render dashboard → **New → Postgres** → free plan → same region as the API (**Singapore**).

Then copy the **Internal Database URL**. Rewrite its scheme:

```
postgres://…      →   postgresql+psycopg://…
```

The app validates the scheme and refuses anything else. Use the **internal** URL, not the external
one: internal traffic is free and lower-latency.

> If you skip this, everything still runs, but accounts and saved analyses reset on every restart.

### Step 3 — Create both services from the Blueprint

Dashboard → **New → Blueprint** → connect `meherabmehu/SpaceAgriSim` → branch `main`.
Render reads `render.yaml` and shows two services.

When prompted for the `sync: false` values:

| Service | Variable | Value |
|---|---|---|
| `spaceagrisim-api` | `SPACEAGRISIM_DATABASE_URL` | the `postgresql+psycopg://…` internal URL from step 2 |
| `spaceagrisim-api` | `SPACEAGRISIM_CORS_ORIGINS` | `["https://spaceagrisim-web.onrender.com"]` — exact, JSON list, no wildcard |
| `spaceagrisim-web` | `VITE_API_BASE_URL` | `https://spaceagrisim-api.onrender.com/api` — scheme **and** `/api` required |

Names must match the blueprint; if you pick different service names, update
`SPACEAGRISIM_CORS_ORIGINS` and the static site's URL accordingly.

### Step 4 — Deploy the API, then the web client

Render deploys in order but the two are independent. Watch the API log for:

```
Application startup complete.
Uvicorn running on http://0.0.0.0:<PORT>
```

If it exits immediately with a message about `SPACEAGRISIM_AUTH_SECRET`, the blueprint environment
was not applied — check the service's Environment tab.

### Step 5 — Verify the API is really up

```bash
curl -s https://spaceagrisim-api.onrender.com/api/health
curl -s https://spaceagrisim-api.onrender.com/api/ready
```

`/api/ready` reports `"database": "available"` and the dialect. If it says the database is
unavailable, the connection string is wrong — the health check will fail the deploy for the same
reason.

### Step 6 — Verify the frontend is talking to the API

Open `https://spaceagrisim-web.onrender.com`. You should see **"API connected"** in the mission
shell. If it says disconnected:

- Browser console shows a CORS error → `SPACEAGRISIM_CORS_ORIGINS` does not exactly match the
  static site origin.
- Requests go to the static host instead → `VITE_API_BASE_URL` is wrong; **rebuild** the static
  site after changing it, a restart is not enough.

### Step 7 — Run the acceptance path in the live app

1. **Dashboard** loads, "API connected".
2. **Research assistant** → ask *"What crop yield will the OSD-46 classifier predict on the Moon?"*
   → expect **partial** with an unsupported-premise refusal, not an answer.
3. Ask *"Compare the findings of OSD-314 and OSD-346"* → expect both accessions cited.
4. **Scientific workflow** → the mizuna absolute-load model appears **disabled**.
5. Run a lettuce prediction, **Run and save** (needs an account), export CSV → the header says the
   numbers are model output, not measurements.
6. **NASA data explorer** loads 26 accessions.

---

## 4. Failure modes, by symptom

| Symptom | Cause | Fix |
|---|---|---|
| Deploy fails: `SPACEAGRISIM_AUTH_SECRET must be set` | Blueprint env not applied | Add the variable manually; keep `generateValue` |
| `503 Database unavailable` on `/api/ready` | Wrong URL, or `postgres://` scheme | Use `postgresql+psycopg://` and the **internal** URL |
| Blank page on the static site | Publish directory wrong | Must be `./frontend/dist` |
| 404 on refresh / shared link | SPA rewrite missing | `/*` → `/index.html`, type `rewrite` |
| CORS error in console | Origin mismatch | Exact origin, JSON array, `https://`, no trailing slash |
| API calls hit the static host | `VITE_API_BASE_URL` missing or relative | Set full URL, then **redeploy** the static site |
| Everyone logged out after idling | Ephemeral auth secret | `generateValue: true` must be set; check it is not blank |
| Saved analyses vanish after redeploy | SQLite on ephemeral disk | Attach the Postgres URL |
| First request takes ~1 minute | Free-tier spin-down | Expected; upgrade the instance to keep it warm |

---

## 5. Limits to state out loud (not a production deployment)

- Free tier: **512 MB / 0.1 CPU, sleeps after 15 idle minutes**, 750 instance-hours/month.
- **Free Postgres expires 30 days after creation** and is deleted about two weeks later. Migrate or
  upgrade before then — this is a demo timeline, not a hosting plan.
- Single worker. Rate limiting is per process; a shared limiter needs the edge.
- No TLS configuration of your own (Render terminates it), no MFA, no email verification, no
  password reset — see `docs/PHASE13_PRODUCTION_READINESS.md` §5 for the full list of what is not
  verified.
- Nothing here changes the scientific position: the simulator is uncalibrated, every model is
  `trained-exploratory`, and no output is a NASA measurement.

---

## 6. After you deploy

- Set `autoDeployTrigger` to `auto` if you want pushes to deploy themselves; it is `off` now so a
  push cannot restart a demo mid-presentation.
- Before the Field Shift event, do **not** rely on this deployment as the submission — competition
  rules require the project to be built during the event. This is for the existing platform.
