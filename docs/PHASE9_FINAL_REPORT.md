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
| `radiation-exposure-osd46-v1` | **new**, experimental | shipped logistic-L2 acc 0.932, balanced 0.910; best learner HistGBM 0.924; batch-controlled 0.969 |
| six Phase 6–8 models | unchanged | — |

### Excluded with retained evidence

| Candidate | Why | Evidence |
| --- | --- | --- |
| `radiation-dose-osd782-v1` | balanced 0.361 vs 0.333 chance, p = 0.2475; dose confounded with processing order | `ml/evaluation/excluded/` |
| `gravity-reorientation-osd411-v1` | balanced 0.500, p = 0.6931; failed every transfer direction | `ml/evaluation/excluded/` |

`ml/artifacts/registry.json` holds 8 entries and every SHA-256 is re-verified by the
test suite. A test asserts the two excluded models are absent from the registry and
return 404 from the API.

## Discovery correction

A systematic sweep of 587 OSDR studies found 231 with processed matrices; screening
those found six with processed taxonomic tables, including **OSD-267 (VEG-01A)** and
**OSD-269 (VEG-03A)** — ISS-grown red romaine lettuce microbiome studies.

**The inventory needed correcting; the modelling verdict did not.** An earlier draft
of this section called the Phase 8 conclusion "wrong". Checking the Phase 8 catalogue
showed that is too strong: OSD-267 and OSD-269 were already listed there, with the
note *"Metadata/omics only in this acquisition; not eligible for direct crop-yield
training"* — which is correct and which this phase confirms. The statement that no
crop-microbiome model was buildable referred to OSD-772 and OSD-412/413/414, which
publish only raw amplicon FASTQ, and that remains true.

What the sweep adds is the missing middle ground: these two studies publish processed
taxonomy tables, so compositional analysis is possible where prediction is not. And
it is not: VEG-01A has 2 flight leaf plants, leaf and root are repeated measures per
plant, and pooling the two missions confounds mission with condition. A descriptive
CLR analysis with a 5000-permutation test finds **no detectable flight effect**
(p = 0.904 and 0.794). No model was registered for it.

## Verified results

### Positive

| Result | Number |
| --- | --- |
| A1 radiation quality, LOGO over 22 groups | acc **0.932**, balanced **0.898**, macro F1 0.906 |
| A1 permutation test | **p = 0.0099** (floor at B = 100), null mean 0.305 |
| A1 bootstrap 95 % CI for balanced accuracy | 0.792 – 1.000 |
| A1 genes shared by all 22 folds | 75 of 150 |
| A2 exposure, full set | acc 0.932, balanced 0.910 |
| A2 exposure, batch-controlled (`0806A-10`, 20 arrays) | balanced **0.969** |
| γ vs HZE batch balance | 8 each on `0806A-10`, 10 each on `1006A-03` |

### Negative, and load-bearing

| Result | Number |
| --- | --- |
| Dose (OSD-782) | balanced 0.361, p = 0.2475 |
| Gravity (OSD-411) | balanced 0.500, p = 0.6931 |
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

## Post-merge audit: four more defects

A follow-up audit asked a simple question — does everything Phase 9 claims actually
hold together? Four things did not.

1. **Registered models cited studies the explorer did not list.** A new test walks
   every registry entry and asserts its `sourceStudy` resolves through the dataset
   API. It failed twice: `mizuna-microbial-load-v1` cites **OSD-780**, and the
   Phase 9 radiation models cite **OSD-46**, and neither was catalogued. A user
   could open a model card naming a study and find nothing behind it. Fixed with
   `scripts/catalog_phase9_studies.py`, which builds the rows from the ISA metadata
   and the verified checksum manifest instead of hand-written values — so every
   `sha256` in the catalogue is one the acquisition step actually checked, and a
   file is only marked `downloaded` when its bytes matched.

2. **The dataset explorer previewed nothing for the four new studies.** `preview()`
   had branches for the Phase 6/7 studies only. Added for OSD-46, OSD-782 and
   OSD-411. The browsable rows there are sample-to-condition assignments, because
   the measurements are expression matrices, so each table's note says the rows are
   design factors rather than outcomes.

3. **The regeneration coverage table was stale.** It still said no plant-specific
   radiation dataset existed while two radiation models were being served, and it
   described gravity as "requiring processing" without recording that OSD-411 had
   been tested and rejected. Corrected, and a test now ties the rows to the registry.

4. **The UI comparison script could not fail correctly.** It compared a directory
   against itself, could not distinguish a layout move from a missing capture, and
   passed when no capture existed. Rewritten with a three-outcome verdict; a missing
   capture is now exit code 2.

Two smaller things were corrected while verifying: the sample counts that were
ambiguous between metadata rows and processed samples (OSD-267 keeps both 12 and 11,
OSD-411 records that its 64 libraries come from 16 seedlings), and the `Wassilewskija`
genotype label in the cross-study records, which the ISA does not state — it records
`Wild Type` and `atm-1`.

## Testing

| Gate | Result |
| --- | --- |
| Backend pytest on PostgreSQL 17 | **261 passed** (baseline 212) |
| Phase 9 model/leakage/integrity suite | 46 tests |
| Playwright, desktop / tablet / mobile | **24 passed** |
| Visual regression, existing viewports | 0.002 %, 0.002 %, 0.003 % pixel change |
| Visual regression, new cards | 0.00-0.30 % pixel change, canvas sizes identical |
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
  Measured: all nine captures pass, existing viewports differ by 0.002-0.003 % of
  pixels and the two new cards by 0.00-0.30 %, with identical canvas sizes.
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

All gates were run on the merged tree, not only on the feature branch: 261 backend
tests, 24 browser tests across three viewports, lint, typecheck, build and the
visual regression comparison.
