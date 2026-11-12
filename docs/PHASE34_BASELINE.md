# Phase 34 — baseline audit

Starting commit **`e7ee85582bfc4224e9f94a4f0d3e85672dcc95fa`** (`main`, the Phase 33 delivery),
verified with `git ls-remote` before the clone was used. This document is the traceable baseline
the rest of Phase 34 is measured against: what exists, where it is, what it claims, and which
claims this phase re-checked. It is an inventory and a set of pointers, not a re-description of
every earlier report.

## 1. Frontend

| surface | count | location |
|---|---|---|
| routes (hash-based nav entries) | 16 | `frontend/src/pages/MissionPlatform.jsx` (`NAV`) |
| lazily loaded page modules | 16 | `frontend/src/pages/PlatformModules.jsx` |
| shared prediction panels | 2 | `EarthLettucePrediction.jsx`, `RadiationTranscriptomicPrediction.jsx` |
| science panels / support | 2 | `sciencePanels.jsx`, `moduleSupport.jsx`, `WaterEvidencePanel.jsx` |
| charts | 1 shared component | `src/charts/GrowthPlot.jsx` (recharts), plus 3 modules that import recharts directly |

Nav (unchanged by this phase): Mission control, Simulation lab, AI prediction center, Scientific
workflow, Guided workflows, Research assistant, Growth chamber, World comparison, Crop intelligence,
NASA data explorer, Mission analytics, Mission advisor, Benchmark transparency, Model comparison,
Account & sharing, Methodology.

Status labels the UI must keep distinguishing: measured, model estimate, user setpoint, derived,
experimental comparison, unavailable. Loading/empty/error/retry states and the "API connected"
indicator are asserted by the Playwright suite.

## 2. Backend

| surface | count | location |
|---|---|---|
| routers | 11 | `backend/app/routes/*.py` |
| OpenAPI paths / operations | 83 / 90 | `app.openapi()` at this commit |
| served model ids | 7 | `app.research.MODEL_IDS` |
| withdrawn artifacts (retained, unreachable) | 2 | `app.research.RETIRED_MODEL_IDS` |
| registered artifacts | 9 | `ml/artifacts/*.py` + `registry` |

Served models at baseline: `lettuce-earth-growth-v1/-v2/-v3`, `tomato-flight-response-v1`,
`mizuna-microbial-relative-load-v2`, `radiation-quality-osd46-v1`, `radiation-exposure-osd46-v1`.
Withdrawn and unreachable: `mizuna-harvest-v1` (held-out R² −0.333), `mizuna-microbial-load-v1`
(superseded, replaced by v2), plus the `et0-emulator-v1` card (physics only is served).

## 3. Data

* `data/metadata/dataset_manifest` — **24 datasets** with id, title, source URL, metadata URL.
* `data/raw/` — 22 MB across OSD-46, OSD-59, OSD-120, OSD-314, OSD-386, OSD-655, OSD-670, OSD-723,
  OSD-745, OSD-780 and NTRS extracts.
* `data/processed/` — 5.5 MB, including `mizuna_microbial_load.csv` (356 rows; VEG04A 184,
  VEG04B 172, **both campaigns in one file**) and `lettuce_earth.csv` (1648 rows, DAT 2–29,
  air/root 20–32 °C, PPFD 200–750, FW 0.441–942.1 g).
* `data/literature/external_lettuce_peerj17085` — PeerJ 2024 treatment means with study
  conditions, committed in an earlier phase.
* Checksums, licences and provenance: `data/metadata/*checksums*.py`,
  `ml/training/phase32_provenance.py` (verified 9/9 at baseline and at delivery).

## 4. Tests and gates at baseline

| gate | baseline result | how |
|---|---|---|
| SQLite suite | 1213 passed, 23 skipped | `pytest backend/tests` |
| PostgreSQL 17.11 suite | 1236 passed, 0 skipped | `SPACEAGRISIM_TEST_POSTGRES_URL=…:55432/spaceagri_test` |
| model audit | 9/9 models, 161 checks, 0 failed, 5 gaps | `scripts/audit_models.py` |
| registry verification | 60/60 | `scripts/verify_model_registry.py` |
| provenance | 9/9 | `ml/training/phase32_provenance.py --check` |
| feature readiness / coverage | 12 features, up to date | `--check` on both builders |
| frontend lint / typecheck | clean | `npm run lint`, `npm run typecheck` |
| production build + budget | 2698 modules, initial 240 kB across 3 modules | `npm run build:check` |
| Playwright | 123 passed ×3 viewports | `npx playwright test` |

The 23 SQLite skips are the PostgreSQL persistence tests (no server configured in that run) plus
the multi-worker PostgreSQL assertions; with a server available they execute. Their reasons are
printed by `-rs` and are not hidden.

## 5. Known limitations carried into this phase

Five documented audit gaps, all of one family:

| model | field | what was missing |
|---|---|---|
| `tomato-flight-response-v1` | calibration | no out-of-fold probability measurement |
| `lettuce-earth-growth-v1` | calibration-scope | coverage measured within the fitted campaigns only (0.9393) |
| `lettuce-earth-growth-v2` | calibration-scope | same (0.9606) |
| `mizuna-microbial-load-v1` | calibration-scope | same (0.9919) |
| `mizuna-microbial-relative-load-v2` | calibration-scope | same (0.9919) |

Plus the limitations that are not audit gaps and stay open: v3's failed independent holdout
(Touliatos, 41.6 % MAPE vs a 30 % criterion), the water benchmark being shape-only
(Spearman 0.7909), the ET0 emulator's withdrawal, `mizuna-harvest-v1`'s negative held-out R², and
the absence of any measured reference ET, substrate-moisture or LED-spectrum dataset in the
repository.

## 6. What this phase then did, and did not do

* Re-measured the five gaps above against independent campaigns and out-of-fold probabilities
  (`PHASE34_SCIENTIFIC_VALIDATION.md`).
* Found and corrected two false statements in served text about a second mizuna campaign that has
  always been in the repository.
* Repaired the visual gate, which had been unable to pass since the dashboard grew
  (`PHASE34_VISUAL_REGRESSION.md`).
* Changed no frontend behaviour, no API contract, no database schema, no model, no threshold and
  no test expectation. No dataset was added (`PHASE34_DATA_ACQUISITION.md`).
* Touched no production service, and made no Render change of any kind.
