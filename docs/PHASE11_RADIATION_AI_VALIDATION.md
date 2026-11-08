# Phase 11 — radiation model validation

Objective 1 was to make the existing NASA-trained models more reliable. For the two
radiation classifiers from OSD-46 that means answering one question honestly: **is there a
better learner, or only a better-looking number?**

Evidence: `ml/evaluation/phase11_radiation_validation.json`,
produced by `ml/training/phase11_radiation_validation.py`.

```
python ml/training/phase11_radiation_validation.py    # ~90 s
```

---

## 1. The baseline had to be reproduced before anything was compared to it

Six candidates were evaluated against the shipped model. If the "shipped" row is a
lookalike rather than the actual served model, every delta below is meaningless, so it is
checked first against the committed Phase 9 artifact:

| Model | Phase 9 committed | Phase 11 reproduced | Verdict |
| --- | --- | --- | --- |
| `radiation-quality-osd46-v1` | 0.8981 | **0.8981** | reproduced |
| `radiation-exposure-osd46-v1` | 0.9097 | **0.9097** | reproduced |

The first attempt at this script did *not* reproduce them — it invented its own
gene-selection step and got 0.880 and 0.986. Those numbers were wrong in both directions
and would have supported two false conclusions (that the shipped model was worse than it
is, and that a challenger was better). The fix was to call the harness the model was
actually trained with; the fidelity check now fails loudly if that ever drifts.

---

## 2. Protocol, fixed before the run

- outer loop: **leave-one-biological-group-out**, 22 folds, two arrays per group never split
- gene selection: **inside each outer fold, training rows only**
- hyper-parameters: fixed a priori, no inner search on the test side
- promotion bar: beat the shipped model by **≥ 0.02 balanced accuracy**, win on **more than
  half of the groups**, and keep permutation p < 0.05

44 arrays over 22 groups means 0.02 balanced accuracy is roughly **one array**. The bar is
set there so that a "win" has to be bigger than a single sample.

---

## 3. The candidates

| Candidate | What it is |
| --- | --- |
| `shipped` | top-150 ANOVA genes + L2 logistic, the served model |
| `sparse` | L1 logistic, most gene weights exactly zero |
| `linear_svm` | linear support vector classifier |
| `shallow_25genes` | L2 logistic on a 25-gene panel — does less generalise better? |
| `coexpression_modules` | training-only co-expression modules, so features are not single genes |
| `auto_selected_nested` | configuration chosen by inner group-out CV **inside every outer fold** |

The last row exists because the first five are compared on the same 22 folds. Picking the
best of five on one set of folds makes that winner optimistic — the number includes our
having chosen it. `auto_selected_nested` redoes the choice of configuration inside each
fold, so a held-out group cannot influence the configuration that predicts it. **It is the
only row whose score is not inflated by our own search.**

---

## 4. Results

### `radiation-quality-osd46-v1` (3-class: control / gamma / HZE)

| Candidate | Balanced accuracy | Δ vs shipped | Groups won / lost / tied | p |
| --- | --- | --- | --- | --- |
| shipped | 0.8981 | — | — | 0.0005 |
| sparse | 0.6481 | −0.250 | 1 / 4 / 17 | 0.0005 |
| linear_svm | 0.8611 | −0.037 | 0 / 2 / 20 | 0.0005 |
| shallow_25genes | **0.9167** | +0.0186 | **1 / 0 / 21** | 0.0005 |
| coexpression_modules | 0.2222 | −0.676 | 0 / 20 / 2 | 0.9865 |
| auto_selected_nested | 0.8611 | −0.037 | 0 / 2 / 20 | 0.0005 |

### `radiation-exposure-osd46-v1` (binary: control / irradiated)

| Candidate | Balanced accuracy | Δ vs shipped | Groups won / lost / tied | p |
| --- | --- | --- | --- | --- |
| shipped | 0.9097 | — | — | 0.0005 |
| sparse | 0.4722 | −0.438 | 0 / 4 / 18 | 1.0 |
| linear_svm | 0.9583 | +0.0486 | 1 / 1 / 20 | 0.0005 |
| shallow_25genes | **0.9722** | +0.0625 | **1 / 0 / 21** | 0.0005 |
| coexpression_modules | 0.5000 | −0.410 | 1 / 4 / 17 | 1.0 |
| auto_selected_nested | 0.9097 | 0.000 | 0 / 0 / 22 | 0.0005 |

---

## 5. What that means: the improvement is one array

Two rows look like wins, and both are artefacts of the comparison.

**The fixed-k gains are single groups.** `shallow_25genes` improves quality by 0.0186 and
exposure by 0.0625, and in both cases the per-group breakdown is **1 win, 0 losses, 21
ties**. Twenty-one of the twenty-two held-out groups are predicted identically; the entire
"improvement" is one group changing from wrong to right. Exposure looks like a 6-point gain
and is one array.

No two-array binomial test can distinguish that from noise, and this is exactly why the
0.02 margin was declared in advance — quality's +0.0186 does not even clear it.

**The nested row removes the remaining gain.** With the configuration chosen inside each
fold:

- quality: 0.8611, i.e. **0.037 below** the shipped model
- exposure: 0.9097, i.e. **exactly** the shipped model, 0 wins and 0 losses across all 22 groups

The inner loop's choices are spread rather than stable — quality picks k=25 ten times,
k=75 six times, k=150/svm five times, k=150 one time. An inner loop that cannot agree with
itself across folds is not evidence of a better pipeline, and when its disagreement is
carried through to prediction it lands at or below the shipped model.

**Therefore: no model is promoted, and the registry is unchanged.** Not because the
challengers are bad, but because the only honest estimate of "a pipeline that tunes itself
on this dataset" is that it does no better than what is already served.

---

## 6. Rejected experiments

| Experiment | Result | Why rejected |
| --- | --- | --- |
| L1 sparsity | 0.648 / 0.472 | collapses; the signal is distributed, matching Phase 10's permutation result |
| co-expression modules | 0.222 / 0.500 | at or below chance; averaging genes into modules destroys the signal |
| 25-gene panel | +0.019 / +0.063 | one group in both cases; fails the pre-declared bar and does not survive nested re-selection |
| linear SVM | −0.037 / +0.049 | mirrors the 25-gene panel once properly nested |
| deeper hyper-parameter search | not run | an inner loop is what `auto_selected_nested` already measures, and it underperformed |

The module result is worth keeping: Phase 10 showed the radiation signature is spread
across many weakly-contributing genes. Phase 11 shows that compressing those genes into
co-expression summaries **destroys** the signal instead of concentrating it. Distributed
does not mean redundant.

---

## 7. Calibration and uncertainty

Only the binary model supplies a positive-class probability, and it is left
**`calibrated: false`** in the registry:

| Candidate | ECE | Brier | Log loss |
| --- | --- | --- | --- |
| shipped | 0.0489 | 0.0394 | 0.1208 |
| shallow_25genes | 0.1025 | 0.0575 | 0.2175 |
| sparse | 0.2270 | 0.2095 | 0.6109 |
| coexpression_modules | 0.1110 | 0.1669 | 0.5915 |

ECE 0.0489 looks good and must not be over-read: five bins over 44 arrays cannot validate
a calibration curve. It is recorded as a descriptive check, not a calibration claim, and
the registry flag stays false. Widening the panel does not make the sample bigger.

---

## 8. Did this narrow a Phase 10 uncertainty?

Yes, one. Phase 10 recorded that the radiation signal is distributed rather than
concentrated, with a top-gene permutation drop near 0.004. That left open "would a better
model concentrate it?" Phase 11 answers no: every attempt to compress the signal — sparse
selection, module averaging, small panels, larger panels — either matches the shipped model
or loses to it, and the one apparent gain is a single held-out group. **The distributed
signature is a property of the biology at this sample size, not a failure of the learner.**

---

## 9. Status

| Item | Classification |
| --- | --- |
| Six candidates under a pre-declared, group-aware, fold-internal protocol | **Completed** |
| Reproduction of the committed Phase 9 baselines | **Completed** (exact) |
| Nested re-selection to remove the comparison effect | **Completed** |
| Calibration diagnostics for the binary model | **Completed** (descriptive only) |
| Any radiation model improved enough to promote | **Rejected by scientific evaluation** |
| Registry change | **None** — 8 models unchanged |
| Cross-study replication of these numbers | **Blocked by data** — the one independent-looking study, OSD-320, is a duplicate of OSD-46 (see `PHASE11_NASA_DATA_DISCOVERY.md`) |
