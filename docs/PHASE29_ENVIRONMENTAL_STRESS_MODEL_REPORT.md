# Phase 29 — Environmental Stress: Model Report

**What this report is.** The brief asked for a model report for W3. The honest version of that
document has an unusual first line: **there is no model.** W3 is a measured comparison, and this
report explains why a fitted surface was refused, what statistics are computed instead, how they were
validated, and what a user is told about uncertainty and extrapolation.

Readers who want the evidence trail should read `PHASE29_ENVIRONMENTAL_STRESS_RESEARCH_REPORT.md`
first. This document is about the analytics layer.

---

## 1. Why no surface was fitted

A response surface is a function fitted over a continuous design. The available design has four
regimes:

- `control` and `t1` hold a fixed spectrum (green fraction ≈5.08 % and 24 %);
- `t2` varies the spectrum week by week (16 → 24 → 32 %);
- `t3` varies the spectrum week by week **and** raises density by 25 %.

So the predictor space effectively contains **two fixed spectral points, one of them the control**,
plus two time-varying regimes, one of which carries a confound. Fitting anything continuous through
that is fitting a curve to two usable levels; the resulting "prediction" for, say, 12 % green light
would be interpolation between two points and extrapolation everywhere else, presented with a
confidence interval derived from a model with no degrees of freedom to spare.

Two further constraints make it worse rather than better:

- PPFD and photoperiod are constant by design, so the two factors the brief cares about most have
  **zero variance** in this dataset. A surface in (green fraction, PPFD) has no PPFD axis at all.
- The measurement days are 28 and 35 DAS, so the time axis has two points.

The refusal is recorded in the API: `capability.supportedFactors == ["greenLightFractionPct"]` and
every other factor appears in `unsupportedFactors` with its reason. The workflow catalogue carries
the gap as `environmental-stress-response-surface`, status **blocked**.

---

## 2. What is computed instead

Every number W3 returns is a **statistic of measured observations**, computed at request time from the
committed CSVs. Nothing is a model output, and the response says `isSimulation: false`,
`isMeasurement: true`, `isModelPrediction: false`.

| Statistic | Method | Notes |
|---|---|---|
| Group mean | arithmetic mean of the replicate values | per trait, per regime, per day |
| Median, SD, SE, min, max | standard definitions | SD is the sample standard deviation |
| 90 % CI of the mean | bootstrap percentile interval, **2000 resamples, seed 20261107** | seeded, so the response is deterministic — a test asserts two identical calls return identical numbers |
| Difference vs control | treatment mean − control mean | with a bootstrap interval on the difference |
| Welch's t-test | two-sided, unequal variances, Welch–Satterthwaite df | p-value and df reported, not just the p |
| Effect size | Hedges' g with the small-sample correction | reported alongside p, because p alone confounds size with n |
| Relative difference | `difference / controlMean`, **withheld** when the control mean is small against its own spread | see §3 |

Unit metadata for every field travels with the response in a `units` block, and unknown units are
reported as unknown rather than guessed.

### Why bootstrap and not a parametric CI
Replicate distributions here are visibly non-normal (fresh mass spans 19.9–86.7 g in one regime) and
n differs by regime (48–80). A percentile bootstrap makes fewer assumptions and the interval is
reproducible because the seed is fixed.

---

## 3. A defect this phase found and fixed

NPQt at the control has mean −0.0018 with SD 0.303 — unstressed leaves do not dissipate regulated
heat, so the control mean sits essentially at zero by construction. Dividing a difference by that mean
produced a reported "−1017 % change" for `t1`.

That number was arithmetic, not a finding, and it was being served. The response now carries
`relativeDifferenceMeaningful` per comparison:

- when `|controlMean| ≥ 0.25 × controlSD`, the percentage is reported as before;
- otherwise `relativeDifference` is `null`, `relativeDifferenceMeaningful` is `false`, and the note
  says a percentage would be arithmetic rather than a finding, so the absolute difference and the
  effect size carry the comparison.

The UI prints "not meaningful" in that cell rather than a number. Two tests cover both branches
(NPQt suppressed, fresh mass still reported at +17.7 %).

---

## 4. Group-aware validation, and the pseudo-replication problem

The evaluation unit here is the **plant**, but plants were not independent: replicates shared a
chamber, a nutrient solution and a light fixture. This is pseudo-replication, and it has a specific
consequence:

- a Welch test answers *"do these two groups of plants differ in this one experiment?"*;
- it does **not** answer *"would this treatment reproduce in another facility?"*.

The response states this in `method.pseudoReplication` and in every comparison's `reading` field:

> A p-value here tests whether plants under this regime differ from plants under the control in one
> experiment. It is not a claim about repeating the treatment.

**There is no held-out experiment.** One trial, one facility, one cultivar, one season. The strongest
group-aware statement available is `withinExperimentOnly: true`, and that is what is returned. No
cross-validation is performed, because with four groups of which two are structurally confounded
there is nothing to hold out that would test generalisation rather than arithmetic.

---

## 5. Results as computed

Fresh mass, 35 DAS (g/plant), mean [90 % CI]:

| Regime | n | Mean | CI | Δ vs control | Hedges' g | Intervals separated |
|---|---|---|---|---|---|---|
| `control` | 60 | 44.38 | 39.28 – 49.43 | — | — | — |
| `t1` (24 % fixed) | 48 | 48.50 | 44.73 – 52.58 | +9.3 % | 0.233 | **no** |
| `t2` (increasing green) | 64 | 52.24 | 48.88 – 55.41 | +17.7 % | 0.463 | **no** |
| `t3` (increasing green, 1.25× density) | 80 | 46.31 | 43.46 – 49.30 | +4.3 % | 0.115 | **no** |

The biomass result is the scientifically important one and it is **negative**: no regime separates
from the control on fresh mass by this experiment's between-plant spread. A workflow that showed only
the photosynthetic indices would look far more decisive than the data are.

Photosystem indices do separate, 35 DAS:

| Trait | control | `t2` | Δ | Hedges' g | p (Welch) |
|---|---|---|---|---|---|
| Fv'/Fm' | 0.8321 (0.814–0.848) | 0.5785 (0.529–0.630) | −30.5 % | −2.788 | < 0.001 |
| PhiNO | 0.3481 (0.323–0.373) | 0.1645 (0.140–0.193) | −52.8 % | −2.866 | < 0.001 |
| NPQt | ≈ −0.002 | 2.96 (2.15–3.87) | absolute only | 1.968 | < 0.001 |
| SPAD | 29.89 (28.29–31.49) | 29.87 (28.05–31.65) | −0.07 % | −0.005 | 0.987 |

Read together: under the time-varying green spectrum, the photosystem shifts work away from
non-regulated energy loss and into regulated heat dissipation, with no detectable change in fresh
mass at harvest. That is a coherent physiological story **and** a caution: the stress indices moved
far more than the yield did, so a user who reads "stress" off the indices alone would overstate the
agronomic consequence.

The `t3` row shows why the confound matters: it carries the same spectral time course as `t2` but
lands at +4.3 % rather than +17.7 %, with a 25 % higher planting density. There is no way from this
design to say which factor produced the difference.

---

## 6. Uncertainty, extrapolation and unsupported combinations

**Uncertainty is reported, per group, and nothing more.** The interval is a bootstrap CI of a measured
mean — a statement about sampling spread among plants in one experiment. It is not a prediction
interval, because there is no prediction.

**Extrapolation is not possible, by construction.** The workflow accepts a regime, not an
environmental value. There is no code path that takes "400 µmol/m²/s" and returns a biomass, so there
is nothing to extrapolate. Asking for a PPFD value returns it in `unsupportedFactors` with the reason
that PPFD was constant across every regime.

**Unsupported combinations are visibly unsupported**, in the response:

| Factor | Status | Stated reason |
|---|---|---|
| `greenLightFractionPct` | supported | the only factor the experiment varied |
| `ppfdUmolPerM2S` | unsupported | constant at 200 in every regime |
| `photoperiodHours` | unsupported | constant at 16 h; no dataset at all |
| `co2Ppm` | unsupported | not varied, not reported in the deposit |
| `airTemperatureC` | unsupported | not varied, not reported per-plant |
| `relativeHumidityPct` | unsupported | not varied, not reported |

and in the interface: the panel's evidence card renders the same table, so a user cannot reach the
workflow without seeing the "no" rows.

---

## 7. Reproducibility

| Element | How it is fixed |
|---|---|
| Source | raw XLSX re-hashed against the acquisition manifest; mismatch fails the suite |
| Preprocessing | `build_light_stress_dataset.py`, byte-reproducible; a test re-runs it into a temporary directory and compares all five outputs (four CSVs byte-for-byte, the quality record field-by-field) |
| Bootstrap | 2000 resamples, seed 20261107, exposed in `method` |
| Determinism | identical requests return identical numbers; asserted |
| Tests | `backend/tests/test_phase29_workflows.py` (contract, statistics, provenance, units, refusals) and `backend/tests/test_phase29_datasets.py` (hash, build, design, replicates) |
| Frontend | Playwright: measured banner, table against API numbers, provenance, confound warning, trait deselection |

---

## 8. Verdict

W3 is a **complete measured-comparison workflow with no model**, and that is a deliberate outcome
rather than an unfinished one. It gives a user something genuinely useful — what four spectral
regimes did to 252 plants, with intervals, effect sizes and verified provenance — and it refuses the
thing the data cannot support.

`readinessTier: research-ready` for the comparison. The response surface stays **blocked** in the gap
matrix, at unchanged severity, with the search that established the block recorded in
`data/research/phase29/environmental_stress_search.json`.
