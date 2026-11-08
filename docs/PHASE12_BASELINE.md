# Phase 12 — baseline

Recorded from the repository itself on branch `feat/phase12-ai-platform-completion`.
Every statement below was produced by a command, not by reading a previous report.

---

## 1. Verification of the Phase 11 merge (done before any Phase 12 work)

The prompt explicitly says not to assume Phase 11 was merged because its report says so.
It was checked independently:

```
git fetch origin
git ls-remote origin refs/heads/main   -> 7957a05d0a33a022558940f9bb3cd63744701aa1
git merge-base --is-ancestor 02eac8a HEAD   -> phase 10 merge is an ancestor
git merge-base --is-ancestor c79f292 HEAD   -> phase 11 final report is an ancestor
git log --oneline --merges -3
  7957a05 Merge Phase 11: NASA AI validation, dataset discovery, and the negatives
  02eac8a Merge the Phase 10 consolidated work report
  0257473 Merge OSD-346: the partial-gravity result does not replicate
```

**Phase 11 is genuinely merged into remote `main`.** No integration work was needed and no
work was stranded on a feature branch. `docs/PHASE11_*.md` is present on `main` (11 files).

---

## 2. Local checkout state, and why it needed care

The sandbox checkout had drifted back to the **Phase 8 merge** (`9669553`, an ancestor of
`origin/main`) with about 130,000 lines of uncommitted Phase 9 work in the tree. That work
was later committed on `main`, so the files were stale duplicates of history rather than
unique work. They were archived to `/tmp/bk12/stale_tree.tgz` (8.8 MB) before the tree was
moved to verified `origin/main`. Nothing was discarded without a copy.

Environment rebuilt from scratch, because none of it is committed:

| Component | State at start | Action |
| --- | --- | --- |
| Python dependencies | absent | installed from `backend/requirements*.txt`, `SQLAlchemy>=2.0,<2.1` pinned |
| `frontend/node_modules` | absent | `npm ci` |
| PostgreSQL 17 | not installed | `apt-get install postgresql-17`, `initdb` UTF-8, port 55432, socket `/tmp/pgsock` |
| `backend/scientific_data` | present but **stale** | regenerated with `scripts/package_runtime_data.py` |

The stale runtime bundle is worth recording because it produced the only baseline failures:

```
pytest -q  ->  2 failed, 289 passed
  test_phase10_dose_gravity.py::test_the_registry_says_only_what_the_artifacts_support
  test_phase8_scientific_integrity.py::test_lettuce_v2_is_registered_beside_v1_not_over_it

after python3 scripts/package_runtime_data.py
pytest -q  ->  291 passed
```

Root cause: the bundle's `registry.json` predated Phase 9/10, so `supersedes` was missing on
`lettuce-earth-growth-v2`. Not a code defect, and not silently "fixed" by editing the test —
the packager regenerates the bundle from the committed artifacts, which is the intended path.

---

## 3. Verified baseline numbers

| Gate | Command | Result |
| --- | --- | --- |
| Backend suite | `SPACEAGRISIM_TEST_POSTGRES_URL=… pytest -q` | **291 passed** |
| Registered models | `ml/artifacts/registry.json` | **8** |
| Dataset catalogue | `data/metadata/dataset_manifest.json` | **19** |
| Scientific classification entries | `app.science_classification.FEATURES` | **16** (8 model surfaces + 2 excluded + 6 simulator/estimator surfaces) |
| Pinned dataset versions | `dataset_manifest.json` | 19 studies, each with `metadataSha256` + `verifiedAt` |

Model inventory, exactly as the registry serves it:

| Model | Status | Source type |
| --- | --- | --- |
| `lettuce-earth-growth-v1` | trained-exploratory | external scientific data (not NASA) |
| `lettuce-earth-growth-v2` (supersedes v1) | trained-exploratory | external scientific data (not NASA) |
| `mizuna-harvest-v1` | trained-exploratory | NASA OSDR OSD-655 |
| `mizuna-microbial-load-v1` | trained-exploratory | NASA OSDR plate counts |
| `mizuna-microbial-relative-load-v2` (supersedes v1) | trained-exploratory | NASA OSDR plate counts |
| `radiation-quality-osd46-v1` | trained-exploratory | NASA OSDR microarray GLDS-46 |
| `radiation-exposure-osd46-v1` | trained-exploratory | NASA OSDR microarray GLDS-46 |
| `tomato-flight-response-v1` | trained-exploratory | NASA OSDR OSD-767 |

Two further models are excluded from the registry and are **not** served:
`radiation-dose-osd782-v1` and `gravity-reorientation-osd411-v1`, both classified category 6.

---

## 4. Architecture as it actually exists

**Backend** — FastAPI, 4,370 lines across `backend/app`:

| Area | Module | State |
| --- | --- | --- |
| App wiring, middleware, rate limit | `main.py`, `middleware.py`, `observability.py` | working |
| Auth (argon2 + JWT, revocation) | `auth.py`, `routes/auth.py` | working |
| Storage (SQLAlchemy Core, 3 tables) | `storage.py` | working |
| Model inference (dependency-free JSON evaluators) | `research.py` (589 lines) | working |
| Research/model/dataset API | `routes/research.py` (607 lines) | working |
| Simulation engine | `simulation/*` (7 modules) | working |
| Workspace, advisor, optimizer, reports | `routes/workspace.py` | working |
| Scientific classification taxonomy | `science_classification.py` (400 lines) | working |

**Database**: `scenarios`, `users`, `revoked_tokens`. Scenarios are owner-scoped with an
idempotent migration from the pre-ownership schema.

**Frontend** — React 18 + Vite, 4,991 lines across 10 modules, one nav array of 10 entries in
`MissionPlatform.jsx`, lazy-loaded modules through `PlatformModules.jsx`, and a shared design
system in `missionUI.jsx` (`Card`, `number`) plus `moduleSupport.jsx` (`useResource`,
`RequestState`, `Limitations`, `JsonDetails`).

Existing modules: dashboard, laboratory, predictions, greenhouse (3D), comparison, crops,
datasets, analytics, advisor, methodology.

---

## 5. What the audit found missing

Stated precisely, because "missing" is a claim that needs a search:

1. **No research assistant of any kind.** `grep -rn "assistant"` over `backend/app` and
   `frontend/src` returns nothing. There is no retrieval layer, no citation machinery, and
   no question-answering surface. This is the largest genuine gap.
2. **`/api/models` does not carry the scientific classification.** `science_classification`
   knows each model's category, status and service permission, but the model rows served to
   the UI do not include it. Consequently the UI cannot distinguish a NASA-trained molecular
   classifier from an Earth-only regression without hardcoding.
3. **No calibration or explanation availability on model rows.** Those facts exist in
   `phase10_uncertainty_patch.json` and the `*-explanation.json` artifacts but are not
   merged into the registry payload.
4. **No saved analyses.** Only `scenarios` are persisted. A model inference with its
   explanation and citations cannot be saved, re-listed, or exported as a research record.
5. **No duplicate safeguards in the dataset API.** Phase 11 proved OSD-320 duplicates the 44
   arrays in OSD-46 and wrote `phase11_duplicate_audit.json`, but `/api/datasets` does not
   surface it, so the risk it documents is currently only in a document.
6. **No AI analysis export.** `/api/reports/{format}` covers simulation output only.

---

## 6. What the audit found working and must be preserved

- Exact linear attributions for both radiation classifiers, with `404` for models that have
  no valid explanation method (no surrogate stubs).
- Reference profiles labelled `synthetic: True` with an explicit warning that a centroid is
  not a measured specimen.
- Partial-gene-vector rejection (`422`, `expression-feature-mismatch`).
- Six-category scientific classification with category 6 explicitly unservable.
- Owner-scoped scenarios; argon2 passwords; JWT with revocation.
- Rate limiting middleware and bounded request sizes.
- 291 backend tests, 40 registry checks, 27 browser tests (Phase 11 baseline).

---

## 7. Baseline gates reproduced before Phase 12 changes

| Gate | Result |
| --- | --- |
| `pytest -q` with PostgreSQL | **291 passed** |
| Registry verification | to be re-run after bundle regeneration in §8 |

Everything in Phase 12 is measured against these numbers. Regressing below them is a failure,
not a trade-off.
