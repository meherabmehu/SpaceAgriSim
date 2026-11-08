# Phase 10 — final report

Branch `feat/phase10-advanced-nasa-ai`, ten commits on top of `05f6950`.
**Registry: 8 models, no additions, no removals, no status changes.**
**Catalogue: 19 NASA datasets, two new (OSD-314, OSD-346).**

The phase had one throughline: Phase 9 shipped models whose *claims* were less
rigorous than their *fits*. Every number in the registry was measured; what was
wrapped around the numbers — interval coverage, feature meaning, transfer validity —
was asserted. Phase 10 measured those too, and the measurements disagreed with the
prose in four places.

## 1. Intervals said 90 % and delivered 85 %

Phase 9 disclosed `empiricallyCalibrated: false` with coverage 0.811 and 0.849
against a nominal 0.90. A stated 90 % interval covering 85 % of held-out points is a
defect, and it was treated as one rather than as a caveat.

| Model | Phase 9 | Adopted | Measured |
| --- | --- | --- | --- |
| `mizuna-microbial-relative-load-v2` | 0.849 | group-level conformal | **0.992** |
| `mizuna-microbial-load-v1` | 0.811 | group-level conformal | **0.992** |
| `lettuce-earth-growth-v1` | untested | CV+ | **0.939** |
| `lettuce-earth-growth-v2` | untested | CV+ | **0.961** |

The scientific finding is why the microbial models were stuck: **every row-level
method landed between 0.862 and 0.886** no matter how the quantile was computed. That
is not a bad quantile, it is a broken exchangeability assumption — rows are tissues
inside a pillow, so a row-level interval was answering a question nobody asks.
Switching the unit to the biological group reaches 0.992 and costs width (3.40 vs
2.44 SD), and both figures ship together.

Also found: the first version of this study **was not deterministic** — identical
inputs returned 0.878 and 0.886 — because `RandomForestRegressor(n_jobs=-1)` sums
split gains in a completion-dependent order. A calibration figure that moves between
identical runs is not a measurement, so `n_jobs=1` is pinned and a test re-runs a
slice to prove it.

Detail: `PHASE10_UNCERTAINTY.md`.

## 2. The explanations are exact, and they say the genes are not biomarkers

For a linear-softmax evaluator, attribution needs no surrogate: the contribution is
`weight[c][j] · (x[j] − mean[j]) / scale[j]`, and the sum **reconstructs the served
logits** to 8.9e-16 (quality) and 0.0 (exposure). SHAP was not used, because on a
linear model it would compute the same numbers slowly and with added approximation.

Two results matter more than any top-gene list:

- **No single gene is necessary.** Permutation importance with the model refit inside
  each fold: largest drop **0.0037** balanced accuracy (quality, baseline 0.958) and
  **0.0000** (exposure, baseline 0.986). These genes are a *signature*, not
  biomarkers, and none should be reported as one.
- **Selection is unstable at the edges.** Of 150 deployed genes, **75** (quality) and
  **95** (exposure) are chosen in all 22 leave-one-group-out folds; **6** and **9**
  are chosen in fewer than half. Those are the weakest part of any explanation built
  on them.

Three bugs were caught by testing, not review: the binary model stores an all-zero
class-0 row (a per-class attribution would have said "control contributes nothing");
permutation importance was initially in-sample and reported a meaningless 1.000; and
the binary model was once scored against three-class labels, giving an impossible
0.333. Models without a valid explanation method return **404**, not a mimic's guess.

Detail: `PHASE10_EXPLAINABLE_AI.md`.

## 3. The weak models are evidence-limited, and one cannot be fixed

Each model was audited for its limiting factor before anything was retrained.

| Model | Mean baseline | Shipped | Best attempt | Verdict |
| --- | --- | --- | --- | --- |
| `mizuna-harvest-v1` (14 rows, 10 groups, 1 experiment) | R² −0.138 | — | RF R² **−0.106** | **no model possible** |
| `lettuce-earth-growth-v2` (1,648 rows, 4 experiments) | R² −0.054 | **0.870 / 34.92 MAE** | 0.868 / 35.33 | **no v3** |
| `tomato-flight-response-v1` (36 samples, 21 plants) | — | 0.917 acc | none run | no search |

The trap avoided in the first row: random forest beats the mean baseline by 0.03 R²
*while still being worse than the mean*. The promotion bar was fixed at **R² > 0**
before the run; nothing clears it. No synthetic augmentation was used anywhere —
manufacturing rows to make a number move is how a 14-row dataset becomes a fake
predictor. Every registry status byte is identical to Phase 9, and a test asserts it.

Detail: `PHASE10_WEAK_MODEL_AUDIT.md`, `PHASE10_MODEL_IMPROVEMENTS.md`.

## 4. The cross-study negative: over-attributed, then over-corrected, then measured

Four label-free harmonisations (z-score, rank, quantile-map, training-only pathway
modules) all collapse to the majority class: accuracy 0.667, balanced 0.500, control
recall 0.00.

The within-study reference then decided what that means — and it turned out to depend
on the protocol, which is why it is reported both ways:

| Within-OSD-782 reference | Balanced accuracy | Interval / p |
| --- | --- | --- |
| hold out (dose, timepoint) cells | 0.438 | [0.300, 0.591] |
| hold out whole timepoints | **0.812** | p = 0.001 |

The target is **not** signal-free. It carries a contrast that generalises across
timepoints and does not survive an unseen (dose, timepoint) cell — each of the 12 cells
is one sequencing batch, so a cell-held-out fold also demands batch generalisation,
which is exactly what a cross-study transfer faces.

Getting to this took two corrections in one phase. Phase 9 implied harmonisation was
the obstacle; the first Phase 10 reading said the target had no signal at all. Both
were single-protocol conclusions. The evidence supports a narrower one: transfer fails,
harmonisation stays implicated, and it is **not proven** to be the cause because
harmonisation cannot be separated from the target's cell-level batch structure. That
distinction is the most honest sentence 36 libraries can support, and the measurement
that would settle it is named.

Detail: `PHASE10_CROSS_STUDY_VALIDATION.md`, `PHASE10_DOSE_GRAVITY_RECOVERY.md`.

## 5. Two datasets added, found by searching instead of asserting

Phase 9 concluded that no plant study with processed expression and a real partial
gravity manipulation existed, based on one study (OSD-480, raw FASTQ only). That was an
inference from a single deposit, not a search.

Phase 10 fetched the ISA metadata of all **231** studies with a usable processed matrix
and scanned it for any vocabulary naming a non-1 g acceleration: 231/231 retrieved, 22
candidates, and **two graded-gravity plant experiments with processed RNA-seq**, both now
catalogued.

**OSD-314** — Arabidopsis on the ISS, a subset centrifuged to **0.34 g in orbit**,
microgravity and a 1 g ground control, every level crossed with red light and dark.
17 libraries. It is the first dataset here whose gravity label is a gravity level rather
than a reorientation direction. Acquisition is pinned by byte length and SHA-256.

What it supported is in section 6; what it did not is that no model is served from it.

**OSD-346** (six commanded levels, 0–1 g, phytochrome mutants, all in flight) was then
built and analysed as the independent test. See section 7 — it does not reproduce the
OSD-314 headline.

Detail: `PHASE10_NASA_DATASET_EXPANSION.md`, `PHASE10_DOSE_GRAVITY_RECOVERY.md`.

## 6. Dose and gravity: both exclusions stand, both explanations were wrong

**Dose.** The `absorbedDoseGy` label is valid (0 / 10 / 100 Gy, full factorial against
four timepoints). Phase 9's note that dose was "confounded with processing order" is
partly right — each (dose, timepoint) cell is one sequencing batch — but that makes the
label harder to evaluate, not unusable.

| Protocol on the same 36 libraries | Balanced accuracy | p |
| --- | --- | --- |
| hold out one (dose, timepoint) cell | **0.111** (worse than chance) | — |
| hold out one whole timepoint | **0.611** | 0.0005 |
| hold out one whole timepoint, ordinal | ρ = 0.197, monotone | 0.0155 |

The dose gradient is recoverable when the split matches the design. The cell-held-out
protocol returns *below* chance, which is what a split measuring batch membership looks
like. Nothing is promoted: 36 libraries in one genotype cannot support a dose predictor,
so the exclusion stands on better evidence than it did.

**Gravity.** OSD-411 remains excluded — every sample is at 1 g, and 90° reorientation is
not a gravity level. OSD-314 is different: the within-flight 0 g versus 0.34 g contrast
reaches balanced accuracy **1.000** (p = 0.0055) on held-out light treatments,
corroborated by the deposit's own **8,478–13,504** differentially expressed genes. It is
not served — 17 libraries, one mission, two folds, no sequencing-run identifier in the
deposit, and 0.34 g is neither Moon nor Mars gravity.

**The binary contrast, under both protocols** (this is what corrected section 4):

| Protocol | Balanced accuracy | Interval / p |
| --- | --- | --- |
| hold out (dose, timepoint) cell | 0.563 | group bootstrap [0.386, 0.729] |
| hold out whole timepoint | **0.813** | p = 0.0005 |

## 7. The partial-gravity headline does not replicate

OSD-346 is the independent check: a different mission, phytochrome-mutant genotypes,
blue light, six commanded gravity levels 0–1 g, **every library a flight sample** so
there is no flight confound at any level, and two light treatments that each carry the
full gravity series so the same held-out-treatment split is available.

| Analysis | Result |
| --- | --- |
| 0 g vs 0.25–0.38 g, held-out treatment | 0.500, **collapsed**, permutation null degenerate |
| 0 g vs all partial 0.1–0.38 g | 0.450, p = 1.00 (non-degenerate null) |
| 0 g vs 0.1 g | 0.875, p = 0.085 (underpowered) |
| graded ridge on realised g, 0–1 g | **ρ = 0.571, p = 0.0015**, not monotone, MAE 0.21 g |
| rank separation at each level | significant at 0.64/0.65 g (p = 0.029); not at 0.1/0.25/0.38 g |
| phyA-trained classifier on phyB | 0.667 |

A graded signal exists in OSD-346 and is statistically clear, but it emerges at **0.6 g
and above**, and the sharp microgravity-versus-0.34 g distinction is absent in every
framing tried. OSD-314's 1.000 is therefore **one experiment's finding, not a property
of plant transcriptomes** — plausibly specific to wild-type plants, to red-light/dark
treatments, or to that mission's batch structure, which cannot be separated with 36
libraries.

One methodological catch worth recording: a classifier that collapses to a single class
makes the permutation null a point mass, so the resulting p-value of 1.0 means
"uninformative", not "no effect". The script now detects a degenerate null and labels
it, rather than letting a power failure masquerade as evidence of absence.

## 8. The registry now proves it says only what its artifacts support

`ml/training/phase10_registry_api_audit.py` checks, for every model, that the artifact
exists, its digest matches, every claimed metric equals the artifact's, no excluded
candidate is served, no stated coverage falls short by more than 0.05, no explanation is
inexact, no model cites an uncatalogued study, and the API serves exactly the registry.

Result: **8 models, 0 findings.** It found two real gaps, both since fixed: the radiation
entries did not advertise the explanation capability they have, and
`verify_model_registry.py` had been counting explanation files as orphan models since the
XAI commit (40/40 checks now pass). Neither fix moved a metric, a radius or a status.

Detail: `PHASE10_REGISTRY_API.md`.

## Verification

Every gate below was run on the merged state, not asserted:

| Gate | Result |
| --- | --- |
| Backend suite | **291 passed** (including the PostgreSQL round-trip) |
| Playwright (3 viewports) | **27 passed** |
| Visual regression | **9/9 within tolerance** (mission 0.002–0.004 %, radiation 0.000 %) |
| ESLint / `tsc --noEmit` / production build | clean / clean / ✓ |
| Demo script (`scripts/demo_phase9.sh`) | runs end to end, live API included |
| Determinism | conformal slice re-run in test |
| Registry integrity | `verify_model_registry.py` **40/40**, API audit **0 findings** |
| Demo | `scripts/demo_phase9.sh` runs the phase end to end in **6 s** |

**UI preservation.** The only visual addition is the explanation block, appended at
the **end** of the radiation card — after the source link — so the change is additive.
Measured, not assumed: width identical on all three viewports, height +82 px
(desktop/tablet) and +215 px (mobile), and the region above the new block differs by
**0.16 %** of pixels (antialiasing plus a scrollbar strip on a taller page). An
earlier placement inserted mid-card and moved 4.5–7 % of the pixels above it; that
placement was rejected and the baselines for those 6 captures were refreshed
deliberately with `--refresh-only`, never the whole suite.

## Standing limits, unchanged

Two genotypes, one laboratory, one platform, 44 arrays for the radiation models;
35 pillows across two microbial campaigns; four lettuce experiments. A third
campaign's offset would still come from that campaign's own baseline samples. No
partial-gravity, Moon or Mars prediction is claimed; no absorbed-dose prediction; no
sequencing abundance converted to CFU; no yield inferred from expression. Nothing was
deployed, and none of this is a production verification.

## What Phase 11 should do

1. **Explain why OSD-314 and OSD-346 disagree.** The candidates are genotype
   (wild type vs phytochrome mutants), light spectrum, and batch structure; only a third
   mission with wild-type plants and a sequencing-run identifier can separate them.
2. **Get a transfer target whose contrast survives an unseen cell.** OSD-782's does not,
   so every conclusion about harmonisation stays blocked.
3. **Ask both missions for sequencing run identifiers.** The batch question cannot be
   answered from either deposit, and it is the leading candidate explanation for why a
   perfect separation in one study is absent in the other.
4. **Get a third microbial campaign**, which is the only thing that turns a two-campaign
   calibration into a predictive interval.
5. **Stop re-tuning `mizuna-harvest-v1`.** It has 14 rows and one experiment. Collect
   harvests, not hyperparameters.

## Documents

`PHASE10_BASELINE.md`, `PHASE10_UNCERTAINTY.md`, `PHASE10_EXPLAINABLE_AI.md`,
`PHASE10_WEAK_MODEL_AUDIT.md`, `PHASE10_CROSS_STUDY_VALIDATION.md`,
`PHASE10_DOSE_GRAVITY_RECOVERY.md`, `PHASE10_NASA_DATASET_EXPANSION.md`,
`PHASE10_MODEL_IMPROVEMENTS.md`, `PHASE10_REGISTRY_API.md`,
`PHASE10_COMPETITION_DEMO.md`, and this report.
