# Phase 26 — Model Improvement Report

**Outcome: no model was retrained, and no model card changed.** This report explains why, in the
terms the brief set, and records what *was* measured about the existing models.

## 1. The gate, and why nothing passed through it

The brief permits improving or retraining a model only against the `trained-exploratory` gate, i.e.
only when new **training-grade** evidence exists. The five datasets acquired in this phase are, by
class:

| Dataset | Class | Training-grade? | Why |
| --- | --- | --- | --- |
| Schröder 2021 lettuce pots | A | **no** | used as an independent validation bench, not as training rows |
| Green-light lettuce | B | no | 252 plants but a single-factor spectrum trial; no model consumes it yet |
| Halbert-Howard tomato | B | no | row-level replication; not preprocessed |
| LED photoperiod tomato | C | no | 20 plants, open field |
| *Corymbia* gas exchange | D | no | wrong species; reference only |

The one dataset that could in principle become training-grade — the green-light lettuce trial — was
not used to train anything in this phase, and doing so without a leave-one-spectrum-out protocol
would have produced a number that could not be defended. It is preprocessed, tested, and waiting.

**Using the Schröder pots as training data would have been the specific failure the brief forbids:**
it is the only measured crop water use in the repository, and it is now the validation bench for the
water path. Training on it and then validating on it would have manufactured a pass.

## 2. What was measured about an existing model instead

No metric in this phase is a model score. The ET validation is an out-of-sample comparison against a
third-party measurement, and it is described as such everywhere it appears:

| Quantity | Value | What it is |
| --- | --- | --- |
| Spearman across 13 measurement days | **0.72** | shape agreement, denominator-free |
| Pearson across 13 measurement days | 0.48 | the same, penalised for level |
| pooled predicted/measured ratio | 0.143 | per pot, uncalibrated |
| fitted single scale, LOO-treatment range | 6.34 (5.88–6.61) | one free parameter, reported beside the uncalibrated numbers |
| per-gram ratio | 0.145 | fresh-mass denominator |

None of these is accuracy, none is presented as accuracy, and the artefact carries a `notClaimed`
list that says so.

## 3. The ET0 emulator is unchanged

`et0-emulator-v1` remains `trained-exploratory` with `deployed: false`. No new ET0 target data
arrived in this phase, so there was nothing to retrain it against, and its existing classification —
category 4, mechanistic-calculation-derived, with its documented "worse than Hargreaves" evidence and
its microgravity note — is untouched. `test_emulator_is_classified_as_a_mechanistic_calculation`
still passes.

## 4. What did change in the repository's model-facing surface

Nothing at runtime. The changes are:

- a **validation artefact** that constrains what the water feature may claim
  (`ml/evaluation/phase26_measured_et_validation.json`);
- a **readiness audit** that records, per feature, what would justify a model change and what would
  not (`docs/PHASE26_FEATURE_COVERAGE_MATRIX.md`);
- a **gap-matrix update** that keeps `measured-eta` at `blocking` while recording the partial
  evidence, so the gap cannot be read as closed.

## 5. What a future phase would need in order to improve a model

Stated now, so that a later phase cannot quietly relax the gate:

1. **For the water feature:** per-day weather and pot or canopy geometry from the same trial, so
   measured ET can be converted to a flux and compared with a reference ET0 for identical days. Only
   then does a crop coefficient become identifiable, and only then may `peak_water_l_per_day` be
   revisited.
2. **For the harvest models:** a controlled-environment tomato or mizuna trial with per-plant labels
   and documented conditions, split by experiment rather than by row.
3. **For a spectrum model:** a trial varying PPFD and photoperiod independently of spectrum, or a
   leave-one-spectrum-out evaluation on the 252-plant table that already exists in-repo.

None of these is available, and none was simulated.
