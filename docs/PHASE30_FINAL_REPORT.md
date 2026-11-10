# Phase 30 — Final report

**Complete scientific evidence acquisition, dataset integration and platform finalisation.**

| | |
|---|---|
| Phase start commit | `6b93fc1` (Phase 29, verified as remote `main` HEAD before any work) |
| Final commit | recorded at the end of this document and verified against the remote |
| Branch | `main` |
| Production changes | **none** — no Render deploy, no environment variables, no service settings, no production database, no paid resources |

This phase searched for data, acquired what it found, evaluated models against it, and removed two
capabilities the evidence could not support. Nothing was fabricated, no acceptance criterion was
moved, and no result is reported that the committed artifacts do not contain.

---

## 1. Start and final state

- Remote `main` at the start: `6b93fc1` — *Phase 29: the seven required reports, and the readiness
  records they cite*. Verified by `git ls-remote` before any work began.
- All work is on `main` in this repository, committed in meaningful units, pushed, and the remote
  HEAD re-read after the push (Section 16).

## 2. Every dataset searched

Sources searched, by name, with what each yielded:

| Source | Queries | Yield |
|---|---|---|
| NASA Open Data / POWER | controlled-environment crop growth, yield | no CEA yield dataset |
| NASA GeneLab / OSDR | graded gravity, fractional gravity, microgravity, clinostat, RPM | molecular and morphological endpoints only |
| NASA LSDA, NTRS | partial-gravity crop growth, chamber yields | ground-chamber reports already in the corpus |
| ESA, JAXA, DLR | graviperception, crop yield under reduced gravity | analog studies, not partial gravity |
| Zenodo | lettuce light-use efficiency, controlled-environment wheat, lettuce biomass | **2 acquired**, 10 rejected |
| Dryad | crop water stress, UAV imagery | 2 rejected |
| Figshare, Harvard Dataverse, PANGAEA, Mendeley Data, OpenAIRE, Research Data Australia | CEA yield, water deficit yield | nothing committable |
| USDA Ag Data Commons / NAL / ARS | lettuce yield, water response | DNS did not resolve from this environment (recorded) |
| Europe PMC, Crossref, Semantic Scholar, OpenAlex, Google Scholar, journal supplements | Ky values, multi-study lettuce harvest | publications without data, or data behind a paywall |

## 3. Acquired

| Dataset | DOI | Licence | Samples / experiments | File | SHA-256 |
|---|---|---|---|---|---|
| Indoor wheat (Apogee), fully controlled environment | `10.5281/zenodo.17764612` | CC BY 4.0 | 39 experiment rows, 719 sub-plot rows, 34 with yield + environment | `data/raw/phase30/wheat_yields.xlsx` (138 723 B) | `385d4680…c33c5` |
| Kilowatts to kilograms: lettuce LUE compilation | `10.5281/zenodo.14640245` | CC BY 4.0 | 53 published treatment means from 40 studies | `data/raw/phase30/lue_dataset.xlsx` (34 049 B) | `feb96c6c…ecedd` |

Full detail: `docs/PHASE30_DATASET_ACQUISITION.md`, `data/metadata/phase30_acquisition_manifest.json`,
`data/processed/phase30/quality.json`.

## 4. Rejected, with reasons

Twelve, each with its DOI and reason in the manifest (§2 of the acquisition report). The classes of
rejection: null licence (1), unusable size (2), no crop response variable (3), duplicate experiment
(1), simulation output rather than measurement (1), wrong species (2), confounded design (1), and no
water-application gradient so no crop-specific Ky (2).

## 5. Models

| Model | Protocol | Independent result | Criterion | Served |
|---|---|---|---|---|
| Lettuce harvest, cross-study | leave-one-study-out + 8 sealed studies | **310.17 % MAPE**, R² −0.4831, median APE 84.49 % | 30 % | **no** |
| Wheat controlled-environment surface | leave-one-experiment-out + 6 sealed runs | **297.46 % MAPE**, R² −0.3673, median APE 256.54 % | 30 % | **no** |

In both cases no fitted candidate beat the mean baseline out of fold. The 2 % simplicity rule
selected the baseline for harvest, and selection did not touch the holdout in either evaluation.

## 6. Independent results, stated plainly

- Harvest: 8 holdout studies, one scoring pass, 310.17 % MAPE. The interval spans a factor of 29.1.
- Wheat: 6 sealed experiments, one scoring pass, 297.46 % MAPE. Conformal interval width 3.58×,
  descriptive out-of-fold coverage 0.867.
- Development figures (42.65 % for v3, 57.42 % for the wheat surface) are labelled development and
  are never presented as validation.
- Prior holdout inspection is disclosed in both artifacts: the Phase 28 Touliatos point and the
  Phase 27 v3 development folds had been seen in earlier phases, and both artifacts record it.

## 7. W1 / W2 / W3 status

| Workflow | Before Phase 30 | After |
|---|---|---|
| W1 water demand | complete | **complete, unchanged** — no yield-loss claim added, because no crop-specific Ky exists |
| W3 light quality & stress | complete (measured spectral comparison) | **complete** + new measured controlled-environment wheat panel |
| W2 harvest prediction | "complete" with a model that had already failed at 41.59 % | **removed** — 410 tombstone, catalogue `unavailable`, evidence-only UI |

All three keep `arbitrated: false`; no validated arbitration between models exists.

## 8. Features completed

1. Two datasets acquired, hashed, processed, documented, and entered in the catalogue as class A.
2. `GET/POST /api/workflows/light-stress/controlled-environment` — measured band summaries over the
   wheat series, with between-experiment intervals, experiment identifiers, provenance and hash
   verification, and an explicit no-significance-test statement.
3. A fourth guided-workflow tab that renders that panel from the API, with the failed surface shown
   above the measured results.
4. `ml/research/build_phase30_datasets.py` with a `--check` mode, so the committed tables are
   provably reproducible from the raw workbook.
5. Two evaluation scripts and two artifacts with pre-registered protocols, sealed holdouts,
   holdout-spent flags and served=false.

## 9. Features removed

1. **Fractional-gravity growth response** — constant, factor, engine input, impact step, API field,
   presets, frontend control, comparison naming, documentation claims and tests. `/api/simulate`
   returns 422 naming the decision; `POST /api/compare` cases are `Earth background` / `Lunar
   surface` / `Mars surface` / `Custom habitat` and differ in dose rate only.
2. **Operational harvest forecasting** — run endpoint (410), request schema, catalogue status,
   frontend run tab, and the claim that the workflow was complete.

Both removals are documented in `docs/PHASE30_REMOVED_CAPABILITIES.md` and asserted by
`backend/tests/test_phase30_removed_capabilities.py`.

## 10. Residual limitations

- No environmental response surface is served: the fit failed at 297.46 %.
- No crop-specific water-deficit yield loss exists, and Ky was never transferred between crops.
- Prediction intervals are descriptive; 6–8 independent points cannot establish coverage.
- The wheat panel is one cultivar at one facility family; its bands mix correlations between
  factors, which is why no significance test is reported.
- The lettuce compilation is published treatment means, so within-study variance is unavailable and
  the unit of independence is the study.
- The removal of gravity leaves the simulator with radiation as its only environment-driven yield
  penalty, and that curve remains an assumption.

## 11. Test results — SQLite

```
python3 -m pytest backend/tests -q --no-header -p no:randomly
1180 passed, 24 skipped, 1 warning in 38.14s
```

New Phase 30 tests: `test_phase30_datasets.py` (17) and `test_phase30_removed_capabilities.py` (19).
Replaced, not deleted: the Phase 28 harvest tests and the Phase 27 engine-integrity gravity test now
assert the removals.

## 12. Test results — PostgreSQL 17

```
SPACEAGRISIM_TEST_POSTGRES_URL=postgresql+psycopg://…@127.0.0.1:55432/spaceagrisim_test \
  python3 -m pytest backend/tests -q --no-header -p no:randomly
1204 passed, 1 warning in 43.15s
```

Auth, authz, workflow, scientific-unit, provenance/checksum, leakage, model-audit and registry tests
all ran against PostgreSQL, not SQLite.

## 13. Frontend results

```
npm run lint        → clean
npm run typecheck   → clean
npm run build       → ✓ built in 7.48s
```

Playwright, per viewport, with the API and dev server started by the config:

| Viewport | Result |
|---|---|
| desktop (1440×1100) | **40 passed** |
| tablet (820×1180) | **41 passed** (1 skipped by design) |
| mobile (Pixel 7) | **40 passed** |

New/changed end-to-end coverage: the harvest tab is proven to have **no run control and no numeric
inputs**, to state the removal, to print every failed evaluation, and to render the parity table the
API returns; the controlled-environment panel is proven to match the API's group means and counts and
to offer no prediction control.

## 14. Audit and registry

```
python3 scripts/audit_models.py --write
models audited 9/9 · checks 157 run, 0 failed · documented gaps 19
```

Section 11 of the audit is new in Phase 30: it fails if a gravity field, factor or constant
reappears, if the harvest catalogue entry becomes `complete` again, if it advertises a run endpoint,
if a removed workflow exposes a served model, or if any advertised endpoint is not mounted in the
application's own OpenAPI document.

Registry verification, feature coverage (`PHASE27`), feature readiness (`PHASE26`), workflow
readiness (`PHASE29`), the gap matrix and the dataset catalogue were all regenerated from their
builders and their `--check` modes pass.

## 15. Reproducibility

- Raw files immutable, hashed, committed; the builder never writes to `data/raw`.
- `ml/research/build_phase30_datasets.py --check` rebuilds from the raw workbook and compares against
  the committed CSVs; it runs inside the test suite.
- Every model run is seeded (`seed: 20261110`) and every split is derived from a SHA-256 of the group
  key, so the partitions are reconstructible without storing them.
- Unit maps are written per field (`unitMap[field] = {unit, modelled}`); no conversion happens
  silently, and there is no imputation.
- The Phase 7 output fingerprint changed because the gravity factor was removed. It was regenerated
  with `scripts/calibrate_phase7.py` and the change is justified in a `deliberateChanges` entry
  carrying the before/after hashes — not hand-edited.

## 16. Deployment-relevant changes

**No deployment was performed and no Render configuration was touched.**

Changes that a future deploy would carry:

- `POST /api/workflows/harvest-prediction/run` now returns **410** — a breaking change for any client
  that called it. The replacement is documented in the tombstone body.
- `gravity` is no longer accepted by `POST /api/simulate` (422) and is absent from `/api/config`;
  `POST /api/compare` scenario names changed to `Earth background` / `Lunar surface` /
  `Mars surface` / `Custom habitat`.
- `/api/compare` and `/api/simulate` outputs no longer contain a `gravity` field; stored scenarios
  that still hold one are stripped on the share-link path so old links keep rendering.
- Two new read-only endpoints under `/api/workflows/light-stress/controlled-environment`.
- No new environment variables, no new dependencies, no migration required.

## 17. Decision register — every gap, one of two outcomes

| Gap | Decision |
|---|---|
| Fractional gravity | **B — removed completely** (no dataset measures crop yield across gravity; every recovered record is molecular or morphological) |
| Harvest forecasting | **B — removed completely** (310.17 % MAPE on 8 sealed studies; mean baseline selected out of fold) |
| Environmental response surface (PPFD/CO₂/temperature) | **A for the measured comparison** (wheat series acquired and served as bands); **B for the prediction** (surface failed at 297.46 %) |
| Crop water-deficit yield loss | **B** — no crop-specific Ky found; no yield-loss claim retained |
| Prediction intervals / coverage | documented — descriptive only, no coverage guarantee advertised |
| LED spectrum response | unchanged from Phase 29: measured comparison served, surface not claimed |
| Remaining nine gaps in `dataset_gap_matrix.json` | unchanged, each with its stated consequence |

There is no "future phase" list: each gap above ends in either an integrated and tested capability or
a documented multi-source failure with the capability removed.

---

**Final commit:** see the head of this repository's `main`; the SHA is recorded in the delivery
message and verified against `git ls-remote origin main` after the push.
