# Phase 11 — baseline

Recorded against the real remote before any Phase 11 change. Every number below was read
back out of a committed artifact in this environment; none is copied from the Phase 10
prose.

## Repository state

| Item | Value |
| --- | --- |
| Remote `main` at Phase 11 start | **`02eac8a`** (`Merge the Phase 10 consolidated work report`) |
| Prompt stated | `0257473` — that was the remote tip before the consolidated report merge (`c491c20`), which followed it |
| Phase 11 branch | `feat/phase11-nasa-ai-validation` |
| Registered models | **8**, unchanged since Phase 9 |
| NASA datasets in catalogue | **19** |
| Backend tests | **291 passed** (including the live PostgreSQL round-trip) |
| Model integrity checks | **40 / 40** |
| Registry-vs-artifact audit | **8 models, 0 findings** |
| Python / PostgreSQL | 3.13, PostgreSQL 17 (UTF-8 cluster on port 55432) |

The prompt's `0257473` and the actual `02eac8a` differ by exactly one docs commit, so the
counts it quotes are unaffected. Recording the difference rather than restating the
prompt's figure, because a baseline that names a commit it was not measured at is not a
baseline.

## Phase 10 findings, verified from artifacts

Each value below was re-read from `ml/evaluation/*.py` in this environment.

| Claim in the Phase 11 brief | Artifact | Verified value |
| --- | --- | --- |
| OSD-314 microgravity vs 0.34 g, balanced accuracy 1.000 | `phase10_partial_gravity` | **1.000**, permutation p 0.0055 |
| OSD-346 replication did not reproduce the contrast | `phase10_partial_gravity_replication` | `replicated: false` |
| OSD-346 graded signal, Spearman ≈ 0.571, not monotonic | same | **ρ 0.571**, p 0.0015, `monotoneInLevelOrder: false` |
| OSD-782 dose, poor generalization to unseen cells | `phase10_dose_recovery` | cell-held-out **0.111**; timepoint-held-out 0.611 |
| Mizuna harvest, 14 rows, no useful model | `phase10_weak_model_audit` | `keep baseline-only status` |
| Mizuna microbial coverage ≈ 0.992 after group conformal | `phase10_uncertainty_decision` | **0.9919** both microbial models |
| Lettuce v2 R² ≈ 0.870 | `phase10_weak_model_audit` | v2 shipped **0.870 / 34.92 MAE** |
| Cross-study transfer failed | `phase10_cross_study` | `transfer-failed-under-every-harmonisation` |
| Registry clean | `phase10_registry_api_audit` | 8 models, **0** high-severity findings |

Nothing here was overwritten. Phase 11 adds new artifacts alongside these.

## Additional Phase 10 values Phase 11 inherits as fixed points

| Quantity | Value |
| --- | --- |
| OSD-782 within-study, cells held out | 0.438 (95 % CI 0.300–0.591) |
| OSD-782 within-study, timepoints held out | 0.812 (p 0.001) |
| Dose, ordinal Spearman across timepoints | 0.197 (p 0.0155), monotone |
| Radiation single-gene permutation drop (quality / exposure) | 0.0037 / 0.0000 |
| Genes chosen in all 22 folds (quality / exposure) | 75 / 95 of 150 |

## What Phase 11 must not do

- Do not redesign the UI, or change theme, layout, typography, navigation, or the 3D scene.
- Do not promote a model that has not beaten its held-out criteria, pre-declared.
- Do not use OSD-346 repeatedly for tuning and then call it independent validation.
- Do not turn a molecular gravity-response classifier into a Moon or Mars growth predictor.
- Do not manufacture dose values, campaigns, labels, or synthetic training rows.
- Do not claim a distance threshold is a validated out-of-domain detector.
- Do not deploy.

## Environment notes for reproducibility

The sandbox restored this workspace twice to a pre-Phase-9 checkout during Phase 10. The
reconciliation used each time was: verify the remote, back up untracked files to `/tmp`,
then `git checkout -f -B main origin/main`. Phase 11 assumes the same failure mode can
recur, so every artifact is committed as soon as it is verified rather than held in the
working tree.

The PostgreSQL cluster must be initialised **UTF-8**; an `SQL_ASCII` initdb makes psycopg
return `bytes` for `pg_catalog.version()` and the SQLAlchemy dialect raises
`TypeError: cannot use a string pattern on a bytes-like object`. This is an environment
fault, not a repository defect.
