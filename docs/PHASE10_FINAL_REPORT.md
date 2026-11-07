# Phase 10 — final report

Branch `feat/phase10-advanced-nasa-ai`, six commits on top of `05f6950`.
**Registry: 8 models, no additions, no removals, no status changes.**

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

## 4. The cross-study negative was over-attributed — corrected

Four label-free harmonisations (z-score, rank, quantile-map, training-only pathway
modules) all collapse to the majority class: accuracy 0.667, balanced 0.500, control
recall 0.00.

But the within-study reference changes what that means. **OSD-782's own
leave-one-group-out balanced accuracy is 0.438, 95 % CI [0.300, 0.591]** — it spans
chance. The target study's own irradiated-vs-control contrast is not learnable by
this pipeline, so the transfer experiment **cannot distinguish a harmonisation
failure from an absent signal**.

The Phase 9 conclusion as written implied harmonisation was the obstacle. It is not
supported. The accurate statement is that transfer fails under every harmonisation
tried, and the experiment is *inconclusive about harmonisation*. What would settle it
is a target study whose own contrast is learnable — that is now the stated
requirement, and it is a more useful output than a rescued hyperparameter.

Detail: `PHASE10_CROSS_STUDY_VALIDATION.md`.

## 5. No new datasets, and the reason is specific

Phase 9's sweep of OSD-1…900 found 587 studies, 231 with usable processed matrices.
Phase 10 added none, because each weak model is blocked on a specific missing
observation and **nothing in those 231 supplies it**: mizuna needs harvests inside one
design (merging experiments confounds experiment with treatment), lettuce needs a 5th
and 6th greenhouse experiment (none exist at NASA), dose needs randomised processing
order, gravity needs a real partial-gravity study with processed expression (OSD-480
is 6.2 TB of raw FASTQ and no matrix), and transfer needs a learnable target. Adding
an unrelated dataset would inflate the catalogue without improving a model.

Detail: `PHASE10_NASA_DATASET_EXPANSION.md`.

## Verification

Every gate below was run on the merged state, not asserted:

| Gate | Result |
| --- | --- |
| Backend suite | **279 passed** |
| Playwright (3 viewports) | **27 passed** |
| Visual regression | **9/9 within tolerance** (mission 0.002–0.004 %, radiation 0.000 %) |
| ESLint / `tsc --noEmit` / production build | clean / clean / ✓ |
| Demo script (`scripts/demo_phase9.sh`) | runs end to end, live API included |
| Determinism | conformal slice re-run in test |

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

1. **Find a transfer target whose own contrast reproduces.** Every conclusion about
   harmonisation is blocked on this.
2. **Run OSD-480 end to end**, or state permanently that it is out of scope. The
   partial-gravity question stays unanswerable until it is.
3. **Get a third microbial campaign**, which is the only thing that turns a two-campaign
   calibration into a predictive interval.
4. **Stop re-tuning `mizuna-harvest-v1`.** It has 14 rows and one experiment. Collect
   harvests, not hyperparameters.
