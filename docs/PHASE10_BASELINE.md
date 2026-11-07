# Phase 10 baseline

Recorded before any Phase 10 change, against the repository as it stands on
`main` after Phase 9. Every number below was read back out of the committed
artifacts and re-measured in this environment, not copied from a previous report.

## Repository state

| Item | Value |
| --- | --- |
| Branch point | `b1946b9` (`main`, Phase 9 audit merged) |
| Phase 10 branch | `feat/phase10-advanced-nasa-ai` |
| Registered models | 8 |
| Backend tests | **262 passed** |
| PostgreSQL | 17.11, disposable cluster on port 55432, database `spaceagrisim_test` |
| Python | 3.13.16, scikit-learn 1.6.1 |
| Excluded model artifacts | 2 (`radiation-dose-osd782-v1`, `gravity-reorientation-osd411-v1`) |

The Phase 9 prompt recorded the merge as `8a90d48`. That was the Phase 9 feature
merge; two audit merges followed it (`a5cdb48`, then the follow-up fixes). The
actual `main` tip at Phase 10 start is `b1946b9`, and the numbers in this document
are measured at that commit. Recording the difference rather than restating the
prompt's figure, because a baseline that names a commit it was not measured at is
not a baseline.

## Registered models, measured

| Model | Samples | Groups | Features | Held-out metrics |
| --- | --- | --- | --- | --- |
| `lettuce-earth-growth-v1` | 1,648 | 4 experiments | 4 | MAE 38.94, R² 0.812 |
| `lettuce-earth-growth-v2` | 1,648 | 4 experiments | 4 | MAE 34.92, R² 0.870 |
| `mizuna-harvest-v1` | 14 | 10 pillows | 4 | MAE 15.50, **R² −0.333** |
| `mizuna-microbial-load-v1` | 123 | 35 pillows | 6 | MAE 1.087, R² 0.549 |
| `mizuna-microbial-relative-load-v2` | 123 | 35 pillows | 5 | MAE 0.539, R² 0.509 |
| `tomato-flight-response-v1` | 36 | 21 plants | 64 genes | acc 0.917, macro F1 0.916 |
| `radiation-quality-osd46-v1` | 44 | 22 groups | 150 genes | acc 0.932, **balanced 0.898** |
| `radiation-exposure-osd46-v1` | 44 | 22 groups | 150 genes | acc 0.932, **balanced 0.910** |

Excluded, artifact retained, unreachable from the API:

| Candidate | Best balanced accuracy | Permutation p | Why excluded |
| --- | --- | --- | --- |
| `radiation-dose-osd782-v1` | 0.361 (chance 0.333) | 0.2475 | dose confounded with processing order |
| `gravity-reorientation-osd411-v1` | 0.500 | 0.6931 | 90° ground reorientation is not gravity level |

## Uncertainty status, measured

This is the weakest part of the platform as Phase 9 left it, and it is the part
Phase 10 has the most room to improve honestly.

| Model | Interval radius | Nominal | Empirical coverage | Calibrated? |
| --- | --- | --- | --- | --- |
| `lettuce-earth-growth-v2` | 90.95 g | none claimed | 0.900 (descriptive only) | **no** |
| `mizuna-microbial-load-v1` | 2.346 log₁₀ CFU/g | 0.90 | **0.811** | **no** |
| `mizuna-microbial-relative-load-v2` | 1.108 SD | 0.90 | **0.849** | **no** |
| `mizuna-harvest-v1` | 28.24 g | none | untested | **no** |
| radiation classifiers | — | — | — | **no**, `calibrated: false` |

Two of the three models that claim a 90 % interval deliver roughly 81–85 %
coverage. The artifacts are honest about it, which is to their credit, but a
stated 90 % interval that covers 85 % of held-out points is a defect worth fixing
rather than a caveat worth repeating.

## What Phase 10 must not do

- Do not report a coverage figure the artifacts do not produce.
- Do not promote a model because it beats a *wrong* baseline (for example a
  majority classifier that scores 0.0 on a 3-class problem, which is not a
  competitive baseline).
- Do not claim cross-study generalisation that Phase 9 measured as a failure.
- Do not present a re-tuned model as a new scientific result when all that changed
  is a hyperparameter.
