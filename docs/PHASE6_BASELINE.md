# Phase 6 — Baseline Audit

**Audited:** 2026-11-07
**Auditor:** autonomous Phase 6 engineering pass
**Repository:** `https://github.com/meherabmehu/SpaceAgriSim.git`
**Branch under development:** `feat/phase6-nasa-ai-completion`

---

## 1. Correction to the Phase 6 brief

The Phase 6 execution brief states:

> Phase 4 has yet been merged into main.

**This is no longer true and the brief is out of date.** Verified independently:

```
$ git merge-base --is-ancestor origin/feat/phase4-production-security main
YES - merged
```

| Reference | Commit | Commit date | Subject |
|---|---|---|---|
| `main` (verified baseline) | `cf1d6c3` | 2026-11-07 20:12:48 +0600 | `merge: phase four production security` |
| `origin/feat/phase4-production-security` | `7193c56` | — | `docs: complete phase four handoff` |

The merge commit `cf1d6c3` has parents `4ceba2a` (the brief's stated Phase 4
baseline) and `7193c56` (the Phase 4 branch tip). **Phase 4 is therefore already
integrated into `main`.**

Consequences for Phase 6:

* No Phase 4 merge step is required or was performed.
* The Phase 6 branch is based directly on `main` @ `cf1d6c3`, which transitively
  contains every Phase 4 commit.
* `git log --oneline -15` on `main` shows the expected Phase 4 sequence
  (`b5512c6 feat: implement authentication` → `e39d7b5` → `69604b9` →
  `c3fafff` → `d0feee3` → `b93f026` → `7193c56` → merge `cf1d6c3`).

## 2. Branch inventory at audit time

```
* main                                   cf1d6c3
  remotes/origin/HEAD -> origin/main
  remotes/origin/feat/phase2-scientific-validation
  remotes/origin/feat/phase3-production-ml
  remotes/origin/feat/phase4-production-security
  remotes/origin/feat/scientific-mission-platform
  remotes/origin/main
```

## 3. Repository shape

| Measure | Value |
|---|---|
| Tracked files | 249 |
| Working-tree size (excl. `.git`) | 7.3 MB |
| Backend Python modules | 24 (`backend/app`) |
| Backend test modules | 14 (`backend/tests`) |
| Frontend source files | ~70 (`frontend/src`) |
| ML training scripts | 2 (`ml/training`) |
| Data pipeline scripts | 9 (`scripts`) |
| Existing docs | 35 (`docs/`) |
| Existing baseline screenshots | 9 (`docs/screenshots`) |

## 4. Backend test baseline — independently reproduced

The brief reports "100 backend tests passed, one optional PostgreSQL test
skipped". Reproduced from a clean install:

```
$ cd backend && python -m pytest -q
.......................................................................s [ 71%]
.............................                                            [100%]
100 passed, 1 skipped, 1 warning in 2.03s
```

**Confirmed.** The skip is `test_postgres_integration.py` gated on a live
PostgreSQL DSN, as documented in Phase 4.

> Caveat: this run used the sandbox's Python 3.13 / FastAPI 0.162. The
> repository pins `python 3.12.10` in `ml/artifacts/registry` and
> `.python-version`. Version drift is noted in `docs/PHASE6_PROGRESS.md` but did
> not affect the assertions.

## 5. Verified NASA studies in the pre-existing inventory

The existing manifest covers **13** OSD records, not the 14 claimed in the
brief. `scripts/nasa_pipeline.py` declares:

```python
IDS = [267, 268, 269, 745, 766, 767, 773, 7, 120, 436, 625, 375, 655]
```

That is 13 identifiers. `OSD-895` (EDEN ISS) is handled separately through
`scripts/acquire_osd895.py` and stored under `data/raw/OSD-895/`, so the
*effectively covered* count is **14** — but the brief's claim that the "existing
inventory contains 14 NASA OSDR study/context records" is only true if OSD-895
is counted, and OSD-895 is not part of the versioned `IDS` acquisition path.
This is documented as a finding, not silently papered over.

Every one of the 14 identifiers was re-queried against the live official OSDR
API during this audit (see `docs/NASA_DATASET_EXPANSION.md`).

## 6. Existing model baseline (as recorded in artifacts)

| Model ID | Source | Samples | Groups | Reported metric | Existing status |
|---|---|---|---|---|---|
| `mizuna-harvest-v1` | OSD-655 | 14 | 10 | MAE 14.76 g, R² −0.153 | `baseline-only` |
| `tomato-flight-response-v1` | OSD-767 | 36 | 21 | macro-F1 0.805, ROC-AUC 0.941 | `experimental` |
| `lettuce-earth-growth-v1` | WUR/4TU (not NASA) | 1,648 | 4 | R² 0.812, MAE 38.95 g | `experimental` |

Artifacts are portable JSON with SHA-256 entries in `ml/artifacts/registry`;
the backend verifies checksums at load time (`backend/app/research.py::load_model`).
No pickle is used. This is a sound design and was preserved.

## 7. Simulation engine baseline

`backend/app/simulation/` implements a transparent mechanistic model:

* `growth.py` — normalised logistic curve, `biomass = harvestBiomass ×
  growthFactor × area × logistic(t)`, with continuous multi-cycle harvest.
* `water.py` — canopy-scaled daily demand, availability-limited supply, deficit
  and recovery.
* `factors.py` — multiplicative environmental response factors.
* `gas_exchange.py` — carbon mass-balance CO₂/O₂ estimate.
* `impact.py`, `serializers.py`, `model_description.py` — reporting and
  self-description.

The separation of *demand / supplied / deficit / recovered* and of *standing /
harvested / cumulative* biomass is scientifically careful and was preserved.
Phase 6 adds calibration and evidence labelling; it does not restructure these
modules.

## 8. Production/security baseline (Phase 4, verified present)

Present in `backend/app/`:

* `auth.py` — Argon2id hashing, signed expiring bearer tokens, revocation.
* `middleware.py` — request-size limits, security headers, auth rate limiting.
* `routes/auth.py` — register / login / logout / `me`.
* `routes/workspace.py` — account-scoped scenario history.
* `storage.py` — SQLite/PostgreSQL-compatible schema.
* `observability.py` — `/api/metrics`, privacy-safe audit logging.
* `config/settings.py` — strict non-wildcard CORS validation.

## 9. Deliverable-relevant defects found during the audit

These are recorded here because they drive Phase 6 work:

1. **OSD-655 target-definition inconsistency (high impact).** The mizuna model
   target `Total (g)` is assembled by *different formulas* in the flight and
   ground-control arms. Verified arithmetically: 8/8 flight rows satisfy
   `Total = mean(4 MMD replicate weighings) + crew consumption`, while 6/6
   ground rows satisfy `Total = harvested leaf mass + broken-leaf mass`. Only
   the ground arm records leaf counts. Full detail in
   `ml/analysis/audit_osd655_mass.py` and `docs/phase6/osd655_mass_audit`.
2. **OSD-655 CSV header under-labels the MMD block.** The header declares two
   blank sub-headers for three extra populated replicate columns, so
   `Consumption Avg. (g)` lands on a replicate value and `Return Samples (g)`
   lands on consumption. `Total (g)` is unaffected. Any key-based re-derivation
   is unsafe.
3. **Inventory count discrepancy** (13 in `IDS` vs 14 in docs) — see §5.
4. **OD-895 is out-of-band** from the versioned acquisition path.

## 10. Baseline preserved-state commitment

Per the non-negotiable UI/UX requirement, the following were recorded before any
change:

* `frontend/src/**` — reads as the visual source of truth; no redesign.
* `frontend/src/styles/platform.css`, `index.css` — untouched by Phase 6.
* `frontend/src/three/GrowthChamberScene.jsx` — untouched.
* `docs/screenshots/*.png` — 9 pre-existing captures retained as the visual
  regression reference.

Phase 6 frontend work is restricted to data wiring inside existing components.
Screenshot comparison results are recorded in `docs/PHASE6_PROGRESS.md`.
