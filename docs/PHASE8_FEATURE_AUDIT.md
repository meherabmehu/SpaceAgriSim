# Phase 8 — Feature Audit

Every user-facing feature inspected against five questions: does it work, does it
say something the evidence does not support, is it reachable, is it tested, and
what should happen to it.

Status vocabulary: **keep**, **keep with disclosure**, **retire**, **blocked**.

---

## Prediction surfaces

| Feature | Surface | Reachable from UI | Tests | Finding | Action |
|---|---|---|---|---|---|
| Mizuna harvest regression | `POST /api/predict/mizuna-harvest-v1` | Yes (Evidence → Predictions) | 4 | 14 endpoints; target definition differs between arms (`DATA_HARMONIZATION.md` H1). Panel already says "not independent validation". | **Keep with disclosure.** Registry pins it at `baseline-only`; no promotion path. |
| Tomato flight-response classifier | `POST /api/predict/tomato-flight-response-v1` | Yes | 3 | Predicts recorded environment, not plant health or yield. UI states this. | **Keep with disclosure.** |
| Earth lettuce regression v1 | `POST /api/predict/lettuce-earth-growth-v1` | Yes | 5 | Sound, but a weaker model class than the one the platform's own benchmark had measured. | **Superseded by v2**; still served, marked deprecated in OpenAPI. |
| Earth lettuce regression v2 | `POST /api/predict/lettuce-earth-growth-v2` | Via generic registry card | 8 | Better on every held-out experiment. | **Added.** See `PHASE8_ML_IMPROVEMENTS.md`. |
| Mizuna absolute microbial load | `POST /api/predict/mizuna-microbial-load-v1` | **No** | 4 | Held-out R² −0.55 and −0.58. Worse than the mean on both campaigns. | **Retired** (410 Gone, evidence preserved). |
| Mizuna relative microbial load | `POST /api/predict/mizuna-microbial-relative-load-v2` | **No** | 5 | Held-out R² +0.444/+0.373, permutation p = 0.000. Intervals under-cover. | **Keep with disclosure.** |

### The reachability problem nobody had noticed

Both microbial models are API-only. `grep -rn microbial frontend/src` returns
**zero** hits. So the platform's most defensible new science — the re-scoped
relative-load model that actually transfers across campaigns — is invisible to
every user, while the weakest model in the registry (the retired absolute-load
endpoint) had been reachable by any client that guessed the path.

That is a real product gap, recorded rather than papered over. It is also why
retiring the absolute-load endpoint costs the UI nothing: no panel called it.

## Simulation surfaces

| Feature | Surface | Finding | Action |
|---|---|---|---|
| Single-crop simulation | `POST /api/simulate` | 6480-scenario sweep: 0 invariant violations. Every response carries `PHASE_1_DISCLAIMER`. | **Keep.** |
| Four-scenario comparison | `POST /api/compare` | Includes a "Custom habitat" scenario; carries its own `LIMITATIONS` list. | **Keep.** |
| Advisor | `POST /api/advisor` | Insight strings label themselves "model response, not a measured stress probability". | **Keep.** |
| Optimizer | `POST /api/optimize` | 81 candidates, 3-objective Pareto frontier. Optimises assumed response curves; says so. | **Keep.** |
| Config / crops / assumptions | `GET /api/config`, `/api/crops`, `/api/assumptions` | Static, consistent with the engine. | **Keep.** |

## Evidence and registry surfaces

| Feature | Finding | Action |
|---|---|---|
| `/api/datasets`, `/api/datasets/{id}` | Honest per-dataset limitations. | Keep |
| `/api/models` | Registry schema sound; five models, all artifacts checksum-verified. | Keep, now with correct cache sizing |
| `/api/science/measurements`, `/api/science/checksums`, `/api/science/evidence`, `/api/science/calibration` | Phase 7 evidence surfaces, internally consistent. | Keep |
| `/api/scientific-summary` | States `platformMaturity: research-and-education`, `nasaEndorsed: false`, `validatedModels: []`. | Keep |
| **`/api/science/classification`** | New. Publishes the evidence category of every prediction surface. | **Added** |

## Account surfaces

| Feature | Finding | Action |
|---|---|---|
| Register / login / logout / me | Argon2id, HS256 with `jti` + revocation, rate limited, no credential leakage. | Keep, see `PHASE8_SECURITY_REVIEW.md` |
| Scenario history | Gated behind `history_writes_enabled`, which is off on Vercel. | Keep |

## Features that do not exist and are not pretended to exist

Disease image classification, yield forecasting for tomato or radish, measured
water demand, measured gas exchange for an arbitrary crop, lunar or Martian
validated predictions. `unsupportedTargets` in `/api/models` lists these
explicitly, and no dead UI affordance suggests otherwise.

## Automation defect found during the audit

`scripts/verify_deployment_config.py`, `scripts/verify_model_registry.py` and
`scripts/compare_ui_screenshots.py` write their reports into **git-tracked**
paths under `docs/phase7/` and `docs/screenshots/`. Running any verification
therefore dirties the working tree with timestamp-only churn, and a careless
`git add -A` would commit it as if it were a real change.

Not fixed in this phase — the correct fix is a configurable output path, and
changing where the Phase 7 verifiers write belongs with the verifiers, not with
the science. Recorded here so the next person does not mistake the churn for a
regression, and so it is not silently "fixed" by committing regenerated images.
