# Phase 9 final report

## Outcome

Phase 9 added **two** scientifically defensible molecular classifiers and **excluded
two** candidates that failed their pre-specified evaluation. It also corrected a
factual error from the previous eligibility pass, and fixed four real defects — two
in the ML pipeline, one in the registry, one in the test infrastructure.

No deployment was performed. Nothing in this report claims production verification.

## Models

### Registered (8 total, 6 unchanged from Phase 8)

| Model | Status | Headline |
| --- | --- | --- |
| `radiation-quality-osd46-v1` | **new**, experimental | acc 0.932, balanced 0.898, p = 0.0099 |
| `radiation-exposure-osd46-v1` | **new**, experimental | acc 0.932, balanced 0.910; batch-controlled 0.969 |
| six Phase 6–8 models | unchanged | — |

### Excluded with retained evidence

| Candidate | Why | Evidence |
| --- | --- | --- |
| `radiation-dose-osd782-v1` | balanced 0.361 vs 0.333 chance, p = 0.353; dose confounded with processing order | `ml/evaluation/excluded/` |
| `gravity-reorientation-osd411-v1` | balanced 0.500, p = 0.517; failed every transfer direction | `ml/evaluation/excluded/` |

`ml/artifacts/registry.json` holds 8 entries and every SHA-256 is re-verified by the
test suite. A test asserts the two excluded models are absent from the registry and
return 404 from the API.

## Discovery correction

The Phase 8-era conclusion *"no crop-microbiome data is usable"* was **wrong**. A
systematic sweep of 587 OSDR studies found 231 with processed matrices; screening
those found six with processed taxonomic tables, including **OSD-267 (VEG-01A)** and
**OSD-269 (VEG-03A)** — ISS-grown red romaine lettuce microbiome studies.

The corrected claim is narrower and evidence-backed: the data exists, but **cannot
support a classifier** (VEG-01A has 2 flight leaf plants; leaf and root are repeated
measures per plant; pooling missions confounds mission with condition). A descriptive
CLR analysis with a 5000-permutation test finds **no detectable flight effect**
(p = 0.904 and 0.794). No model was registered for it.

## Verified results

### Positive

| Result | Number |
| --- | --- |
| A1 radiation quality, LOGO over 22 groups | acc **0.932**, balanced **0.898**, macro F1 0.906 |
| A1 permutation test | **p = 0.0099** (floor at B = 100), null mean 0.318 |
| A1 bootstrap 95 % CI for accuracy | 0.864 – 1.000 |
| A1 genes shared by all 22 folds | 74 of 150 |
| A2 exposure, full set | acc 0.932, balanced 0.910 |
| A2 exposure, batch-controlled (`0806A-10`, 20 arrays) | balanced **0.969** |
| γ vs HZE batch balance | 8 each on `0806A-10`, 10 each on `1006A-03` |

### Negative, and load-bearing

| Result | Number |
| --- | --- |
| Dose (OSD-782) | balanced 0.361, p = 0.353 |
| Gravity (OSD-411) | balanced 0.500, p = 0.517 |
| Cross-study 46→78 | 16 of 16 settings identical at 0.667 / 0.500, control recall 0.00 |
| Within-study control on the same pipeline | 0.977 / 0.986 |
| ISS lettuce microbiome, flight vs ground | p = 0.904 (VEG-01A), p = 0.794 (VEG-03A) |

## Defects found and fixed

1. **Variance preselection on z-scored data.** Every gene's variance becomes exactly
   1.0, so "most variable genes" was an arbitrary tie-break. This manufactured a
   convincing false negative. Now guarded with a `ValueError` and a
   `variance_preselection` flag.
2. **Binary logistic coefficients stored under both class labels**, so the two classes
   could never disagree; surfaced only as an opaque non-finite error.
   `extract_linear_evaluator()` fixes it and is verified against sklearn to ~1e-16.
3. **Pipeline scaler looked up by literal step name.** A miss returned `None` and
   silently skipped standardisation. Now detected by fitted attributes, raising on
   ambiguity.
4. **Classifiers compared on a metric they do not have.** The registry read
   `metrics["MAE"]` for every model, so each classifier advertised "does not beat
   baseline" — a 0.898 balanced-accuracy model reported as worse than chance.
   Classifiers now compare on balanced accuracy.
5. **Test infrastructure had two structural problems**, both fixed: browser
   screenshots were written over their own baselines (making visual regression
   impossible), and the full three-viewport suite tripped the app's own 180/min
   request guard, failing unrelated tests. The guard is now operator-configurable with
   the shipped default unchanged at 180.

## Testing

| Gate | Result |
| --- | --- |
| Backend pytest on PostgreSQL 17 | **253 passed** (baseline 212) |
| Phase 9 model/leakage/integrity suite | 36 tests |
| Playwright, desktop / tablet / mobile | **24 passed** |
| Visual regression, existing viewports | 0.000 %, 0.001 %, 0.000 % pixel change |
| Visual regression, new cards | 6 first baselines committed |
| Frontend lint / `tsc --noEmit` / `vite build` | clean |
| Registry checksum verification | 8 of 8 OK |
| Training determinism | identical metrics across consecutive runs |

Scientific invariants asserted by tests include: permutation p-values are finite and
never zero; classifiers beat their baseline on the correct metric; validation is
group-held-out with ≥20 groups; the batch confound is published with a number;
γ/HZE are batch-balanced inside every batch that contains both; excluded models are
unreachable; partial and extra gene vectors are rejected with 422; and every
sentence mentioning yield on the served cards is a negation.

## Scope preserved

- **No UI redesign.** The new cards compose existing components and classes only.
  Measured: existing viewports unchanged to within 0.001 % of pixels.
- **No deployment** to Render or any host.
- **No fabricated data.** Reference profiles are training centroids, labelled
  synthetic in the payload and on screen.
- **No overclaiming.** Every response carries the batch confound, the permutation
  p-value, the group count and the model's own limitations.

## What remains unresolved

| Item | Blocker | Next action |
| --- | --- | --- |
| Crop-microbiome model | VEG-01A has 2 flight plants; leaf/root are repeated measures | wait for a study with ≥6 independent plants per class, or request per-plant metadata that separates them |
| Absorbed-dose prediction | dose confounded with processing order in OSD-782 | requires a study with randomised processing order |
| Cross-study transfer | microarray → RNA-seq collapse; 16 settings all fail | needs a harmonisation method (e.g. rank- or ortholog-level) evaluated as its own experiment, not as a model rescue |
| Probability calibration | 22 groups is too few for a reliability check | calibrate only after a larger study is acquired; the API states `calibrated: false` today |
| OSD-480 gravity data | 6.2 TB raw FASTQ, no processed matrix | would require a committed alignment/quantification pipeline |

## Merge status

Merged into `main` with `--no-ff` as commit **`8a90d48`**, whose parents are
`9669553` (the previous `main`) and `93465aa` (the Phase 9 tip), and pushed to
`origin/main`. Verified by re-reading the remote: `origin/main` resolves to
`8a90d48`, and `git branch -r --contains 8a90d48` lists `origin/main`.

All gates were run on the merged tree, not only on the feature branch: 253 backend
tests, 24 browser tests across three viewports, lint, typecheck, build and the
visual regression comparison.
