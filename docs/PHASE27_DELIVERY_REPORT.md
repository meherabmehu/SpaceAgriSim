# Phase 27 — Delivery Report

**Branch:** `main`, built directly on `5800b9a` and fast-forwarded.
**Scope executed:** integration verification, PostgreSQL CI and local execution, feature readiness
and implementation-coverage audits, one complete research-ready feature, engine integrity audit,
frontend integration, full verification sweep.
**Not executed, on purpose:** any Render operation or configuration change, any production database
access, any migration, any model retraining, any promotion of an experimental feature, any
threshold relaxation.

---

## 1. Commits

| SHA | Subject |
| --- | --- |
| `f6ffd08` | phase27: run PostgreSQL tests in CI instead of skipping them |
| `ce3fff0` | phase27: correct the phase 26 water-use figures against the data |
| `5335d28` | phase27: serve the measured water-use benchmark and compare against it |
| `1875c07` | phase27: put the measured water benchmark in the simulation lab |
| `80c6166` | phase27: audit feature implementation coverage across ten workflow layers |
| `da03f0f` | phase27: audit simulation engine integrity with executable checks |
| `df91594` | docs: phase 27 integration and feature audit reports |
| `4ddc9d9` | docs: phase 27 delivery report |
| `184fbd9` | phase27: remove a race from the water-evidence browser test |

Every SHA is verified against the remote ref; the exact `git ls-remote` output is in §7.

## 2. Deliverables

| # | Deliverable | Where |
| --- | --- | --- |
| 1 | Integration report | `docs/PHASE27_INTEGRATION_REPORT.md` |
| 2 | Feature audit | `docs/PHASE27_FEATURE_AUDIT.md` |
| 3 | Delivery report | `docs/PHASE27_DELIVERY_REPORT.md` |
| 4 | Feature implementation coverage matrix | `docs/PHASE27_FEATURE_COVERAGE_MATRIX.md` + `data/research/phase27/feature_implementation_coverage.json` |
| 5 | PostgreSQL CI configuration | `.github/workflows/ci.yml` (`postgres` job) |
| 6 | PostgreSQL test results | §4 of this report, and `docs/PHASE27_POSTGRESQL_RELIABILITY.md` |
| 7 | Complete research-ready feature | measured water use — service, route, UI, tests, docs |
| 8 | Updated tests | 24 feature tests, 46 engine-integrity tests, 10 coverage tests, 4 E2E specs |
| 9 | Updated documentation | this report plus the four above, and `docs/DELIVERY_REPORT.md` §L |

## 3. Headline results

| Measure | Before | After |
| --- | --- | --- |
| PostgreSQL tests executed | 0 of 24 (skipped) | **24 of 24** |
| Backend tests | 988 passed / 24 skipped | **1069 passed / 24 skipped** (SQLite) · **1093 passed / 0 skipped** (PostgreSQL) |
| Complete end-to-end features | 0 of 12 | **1 of 12** |
| Frontend E2E | 89 passed | **93 passed** (desktop, tablet, mobile) |
| Phase 26 water-use dates | 10 used, prose said 13 | **11**, and the prose matches |
| Duplicated calculations | 1 found | 0 |
| Flaky browser tests | 1 (mine, introduced this phase) | 0 — fixed with a direct API assertion |

## 4. Verification, reported by outcome

### Passed

| Check | Result |
| --- | --- |
| Backend suite on PostgreSQL 17.11 | **1093 passed, 0 skipped, 0 failed** (41 s) |
| Backend suite on SQLite | **1069 passed, 24 skipped, 0 failed** (35 s) |
| PostgreSQL-specific files | **87 passed** |
| `scripts/audit_models.py` | **141 checks, 0 failed** |
| `scripts/verify_model_registry.py` | **60 of 60 checks passed** |
| Catalogue drift (`build_catalog.py --check`) | up to date, 28 datasets |
| Gap matrix (`build_gap_matrix.py --check`) | up to date, 12 gaps |
| Feature readiness (`build_feature_readiness.py --check`) | up to date, 12 features |
| Coverage matrix (`build_feature_coverage.py --check`) | up to date, 12 features |
| Frontend lint | clean |
| Frontend typecheck | clean |
| Frontend production build | succeeded (8.4 s) |
| Browser E2E, all three viewports | **93 passed** (3.4 min) |

### Skipped

| Check | Count | Why |
| --- | --- | --- |
| PostgreSQL tests under SQLite | 24 | by design; **all 24 execute in the PostgreSQL job and locally** |

### Failed and fixed

| Failure | Cause | Resolution |
| --- | --- | --- |
| `test_connection_failure_is_reported_without_leaking_credentials` | **my test server**, not the product: `initdb --auth=trust` accepts any password, so a wrong-credential test could not fail | server reconfigured to `scram-sha-256`, matching the CI container; test passed unmodified |
| `test_gap_matrix_markdown_is_not_stale` | latent bug: the renderer stamped the wall-clock date into committed markdown | date now comes from `generatedOn` in the artefact |
| `test_catalogue_covers_twenty_three_datasets…` | hard-coded 23 after Phase 26 added five | updated to 28 **with exact per-class counts retained**, so the anti-inflation guard stays |
| Two engine-integrity tests | one was my own argument-order mistake; one found a genuine duplicated harvest formula | both fixed (§5) |

### Not executed

| Check | Why |
| --- | --- |
| `scripts/validate_datasets.py` | **pre-existing environment limitation, not a regression.** It integrity-checks `data/raw/OSD-767/…`, and `data/raw/OSD-*/` is gitignored, so the file is absent in any fresh clone and the check fails on the missing file rather than on bad content. The committed artifact says `valid: true` from a machine that had the download. Not "fixed" by editing the artifact — that would be exactly the fabrication this project forbids. |
| `pip_audit` | not part of the requested sweep; the CI job runs it. |
| Render deployment | out of scope by instruction; the owner handles it separately. |

## 5. What was actually built

### 5.1 PostgreSQL reliability

A `postgres` CI job with a real `postgres:17` service container, health checks, `postgresql-client`
for the backup/restore test, and — the part that matters — **a gate that fails the build if any test
skips**. The prior situation was structural: the SQLite job skipped every PostgreSQL test, so
persistence, transaction, constraint and connection-failure coverage was green by absence on every
run.

Locally reproduced against PostgreSQL 17.11 rather than inferred from a YAML file. Full details in
`docs/PHASE27_POSTGRESQL_RELIABILITY.md`.

### 5.2 The completed feature: measured crop water use

**Endpoints.** `GET /api/water-use-evidence`, `POST /api/water-use-evidence/compare`.

**Service.** `backend/app/water_evidence.py` — assembles the benchmark, runs the comparison against
the *shipped, unmodified* demand path, and carries uncertainty and limitations with every number.

**UI.** A panel inside the existing simulation lab (`frontend/src/pages/modules/WaterEvidencePanel.jsx`).
Visual identity and navigation unchanged; the panel uses the existing card, pill, stat-pair and
field classes plus one new CSS block.

**Three refusals, each tested:**

1. The result is never called a validation. `isValidation` is false; the verdict is one of
   `shape-only`, `level-mismatch`, `not-applicable`.
2. A crop with no measurement gets `not-applicable` and **no curve**. Nothing is extrapolated from
   the lettuce trial to tomato or radish.
3. The between-pot spread is labelled as what the experiment measured, not as a confidence interval,
   and the uncertainty block names the two inputs that are not measured at all.

**What it shows.** Shape supported (ρ = 0.791 across 11 dates); level not identifiable — on a
pot-surface denominator the platform is 0.247× the measurement, on a canopy-area denominator 2.871×,
and the sign of the discrepancy depends on geometry the study does not publish. The simulator's crop
profile is unchanged.

**Uncertainty.** Between-pot spread: ±27.3 % at the treatment level. Level inside that spread: no.

**Provenance.** DOI, licence, processed-table path, and per-file SHA-256 from the acquisition
manifest, with `hashVerified` computed from the hashes rather than asserted.

### 5.3 Engine integrity

46 executable tests covering every question the brief asks. The most valuable is
`test_every_input_changes_at_least_one_output`: all 15 simulation inputs must move at least one
output field. `lightSpectrum` is the documented exception (warnings only) and a test keeps it that
way, because the alternative is an unbacked spectrum response appearing silently.

**Two real findings:**

1. **Duplicated calculation.** `simulate_growth()` repeated `potential_harvest_g()`'s formula inline.
   Identical today, and nothing would have caught them diverging. `simulate_growth()` now calls the
   one definition; a test asserts they agree exactly and another greps for a single occurrence.
2. **A mistake in my own audit.** My first unit test passed `et0_reference_demand_l`'s arguments in
   the wrong order and compared quantities that were not what the test name claimed. Fixed, with the
   signature written into the test so the error is harder to repeat.

## 6. The Phase 26 correction

Integration review found that the Phase 26 water-use artefact reported 10 measurement dates while
its prose claimed 13, and the trial has 11. The recomputed whole-day rate cannot exist for a pot's
first weighing; using that column alone dropped 55 of 604 rows and a whole date.

Fixed by falling back to the workbook's own per-day column for each pot's first interval and
recording which source produced each row (549 recomputed, 55 from the workbook). Everything was
regenerated by script, not retyped: 380 pot-days, 11 dates, Spearman 0.7909, Pearson 0.5631, pooled
ratio 0.1401, fitted scale 6.38, per-gram 0.1416. Two tests pin the coverage.

The scientific conclusion did not change. The numbers now match the data.

## 7. Remote verification

`main` moved from `5800b9a` to `184fbd9dc2ff1b299f41a9cf8ae90748c5b6cb2e`.

```
$ git ls-remote origin main
184fbd9dc2ff1b299f41a9cf8ae90748c5b6cb2e   refs/heads/main
```

**Fresh-clone verification of `main`** (a new `--depth 1` clone, not the working copy):

| Check | Result |
| --- | --- |
| `python3 -m pytest -q backend/tests` (SQLite) | **1069 passed, 24 skipped** |
| same suite against a new PostgreSQL database | **1093 passed, 0 skipped** |
| `build_catalog.py --check` | up to date, 28 datasets |
| `build_gap_matrix.py --check` | up to date, 12 gaps |
| `build_feature_readiness.py --check` | up to date, 12 features |
| `build_feature_coverage.py --check` | up to date, 12 features |
| `npm run lint` / `typecheck` / `build` | clean / clean / built in 8.2 s |
| `npx playwright test e2e/water-evidence.spec.js` | 12 passed |
| Deliverable files present | all four Phase 27 documents, the coverage JSON, the service module, the panel and the spec |

One extra finding from that verification: the first fresh-clone run failed 3 tests and errored 19
because my own `CREATE DATABASE` for the test database had silently failed behind password
authentication — an operator mistake in my verification, not a repository defect. Rerun against a
database that existed: 1093 passed, 0 skipped.

## 8. Remaining work, ranked

From the feature audit, in the order they should be attempted:

1. **Per-prediction interval** on the harvest models (major) — the platform's central claim is a
   prediction with no stated range.
2. **Out-of-distribution warning** (major) — the training envelope is already recorded in the split
   artefacts; this is mostly wiring.
3. **Expose the reference-ET0 water path** in the UI (major) — implemented, tested, unreachable.
4. **Arbitrate the two water paths** (major) — needs per-day trial weather; the evidence half exists.
5. Comparison that can include the measured benchmark, and units as machine-readable fields (minor).

## 9. What must not be claimed about this phase

- No feature became `production-ready`. Nine of twelve still have an incomplete applicable layer.
- Experimental features (LED spectra, nutrient management, cultivar parameters, mission energy) were
  **not** validated and not promoted.
- The water feature does **not** validate the simulator's water use. It makes the disagreement
  visible and quantified, which is a different and smaller thing.
- PostgreSQL passing in CI says the persistence layer behaves; it says nothing about a production
  deployment, which was not touched.
