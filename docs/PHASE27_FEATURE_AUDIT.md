# Phase 27 — Feature Audit

Two audits in one document: **what exists behind each named feature** (ten workflow layers, machine
verified) and **what the platform is missing** (ranked, with evidence). The generated matrices are
`docs/PHASE27_FEATURE_COVERAGE_MATRIX.md` and
`data/research/phase27/feature_implementation_coverage`.

Every named path in the matrix is checked by `ml/research/build_feature_coverage.py`, which refuses
to write if a layer is marked present without an artefact that exists.

---

## 1. The four research-ready and four experimental features

The Phase 26 readiness audit classified twelve features. Phase 27 identifies exactly which reached
which tier, and audits each against the ten layers:

| Tier | Features |
| --- | --- |
| `research-ready` (4) | measured crop water use · the ET0 target itself · predicted harvest mass · heat-stress and VPD excursions |
| `experimental` (4) | LED spectra and photoperiod · nutrient solution management · cultivar-specific parameters · mission energy and mass |
| `data-blocked` (4) | fractional gravity · root-zone water status · imagery · siting for a future climate |

No feature is `production-ready`, and none was promoted. The readiness tiers are carried into the
coverage matrix and cross-checked by the builder, so a tier cannot be quietly raised in one file
without failing the build.

## 2. Workflow completeness, layer by layer

A layer counts as `present` only when a named artefact exists. `not-applicable` is distinguished
from `absent` throughout, because a layer that does not apply to a feature is not a gap.

| Layer | present | partial | absent | n/a |
| --- | --- | --- | --- | --- |
| data | 6 | 1 | 5 | 0 |
| method | 5 | 3 | 4 | 0 |
| service | 8 | 0 | 4 | 0 |
| endpoint | 7 | 1 | 4 | 0 |
| **inputCheck** | **9** | 0 | 0 | 3 |
| **outputCheck** | **1** | 5 | 0 | 6 |
| **uncertainty** | **1** | 2 | 5 | 4 |
| **provenance** | **9** | 1 | 0 | 2 |
| frontend | 7 | 1 | 4 | 0 |
| **tests** | **10** | 0 | 0 | 2 |

**Exactly one of twelve features has every applicable layer implemented**: the measured water-use
feature completed in this phase. That number is the honest headline. Eleven features have a hole
somewhere, and the pattern of holes is more useful than any individual one.

## 3. The finding that matters: the platform is weak at the last two inches

Data, method, service, endpoint, input validation, provenance and tests are largely present. The two
layers that stand between a number and a **defensible** number are the ones missing:

- **`uncertainty` — 5 absent, 2 partial, 1 present.** Nine of twelve features return a point value
  with no stated spread. The single feature with real uncertainty reporting is the one built this
  phase, and its uncertainty is a measured between-pot spread rather than a confidence interval on
  the model.
- **`outputCheck` — 5 partial, 0 absent, but only 1 validating a physical bound.** No feature
  refuses an incoherent result. A model asked for day 60 at 1000 µmol m⁻² s⁻¹ returns a number as
  confidently as one asked for day 20 at 300.

That is a **product** problem, not a data problem, which is why it is ranked above acquiring more
datasets. Six more datasets would not fix it; two layers of validation would.

## 4. Cross-cutting gaps, ranked

Ranked by scientific value, then user value, then feasibility, then validation evidence. Severity
comes from the gap matrix and the audit; feasibility is an engineering estimate, not a wish.

| Rank | Gap | Severity | Scientific value | User value | Feasibility | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **No per-prediction interval** — harvest models report one error number for all predictions | major | high: a point estimate hides its own error | high: users cannot tell if their scenario is inside the envelope | medium: quantile regression or fold-based empirical intervals | `ml/evaluation/lettuce_splits` |
| 2 | **No out-of-distribution warning** — endpoints validate types and ranges, not the training envelope | major | high: extrapolation is indistinguishable from interpolation | high | high: the envelope is already in the split artefacts | `backend/app/routes/research.py` |
| 3 | **Reference-ET0 water path unreachable from the UI** — `et0MmPerDay` and `cropCoefficient` exist on the API and no control sets them | major | medium: the path is implemented and untested by users | high | high: two optional fields and one control group | `backend/app/models/simulation.py`, `frontend/src/services/defaultConfig.js` |
| 4 | **Two water paths, no arbiter** — crop-relative and ET0-reference differ by ~60 % and the response names which ran without saying they disagree | major | high: this is the platform's largest unexplained internal difference | medium | done for the evidence half this phase; the arbiter needs per-day trial weather | `ml/evaluation/phase26_measured_et_validation` |
| 5 | **Comparison cannot include measurement** — compares parameter sets only, no provenance-bearing export | minor | medium | medium | high | `backend/app/routes/workspace.py` |
| 6 | **Units live only in prose** — no response field carries a unit object | minor | medium | medium | medium: additive `units` map | `backend/app/models/simulation.py` |

### Why #1 and #2 outrank #3

#3 is the cheapest to build and the most satisfying to demo. It is ranked below #1 and #2 because
exposing a fourth way to produce an unqualified point estimate, in a platform whose central weakness
is unqualified point estimates, adds surface without adding defensibility. #1 and #2 make every
existing prediction more honest at once.

## 5. UI/backend disconnection audit

Searched for the four failure modes the brief names.

| Failure mode | Finding |
| --- | --- |
| Features in UI not connected to backend logic | **none found.** Every control in the lab maps to a request field, and a test now proves all 15 fields change an output (`test_every_input_changes_at_least_one_output`). `lightSpectrum` is the one annotation-only control and it says so on screen and in the response. |
| APIs returning placeholders or incomplete results | **none found.** Every route either reads a pinned artefact or runs the model. The one deliberate null is `provenance.confidenceInterval`, which is `null` because no interval exists — and the response says so in words rather than leaving the field unexplained. |
| Models not integrated into user workflows | **partly real.** `lettuce-earth-growth-v2`/`v3`, the radiation models and the mizuna models are reachable through the Predictions and Model comparison screens. The ET0 emulator surfaces as method documentation only, not as a per-simulation result — which is correct, since it is `deployed: false`, but it means a user cannot see the emulator's output anywhere. |
| Simulation inputs not influencing calculations | **none, verified mechanically.** See above. |
| Results lacking uncertainty or provenance | **real and ranked #1–#2.** Provenance is strong (9 of 12 present); uncertainty is the weakest layer in the platform. |
| Missing comparison, forecasting or export | **partly real.** Comparison and export exist for scenarios; there is no forecasting at all (no dataset supports one) and no export that carries the evidence panel's provenance. |
| Inconsistent units or duplicated calculations | **one duplication found and fixed**, see §6. Unit identities now tested. |
| Missing error and out-of-distribution handling | **error handling is good** (typed 422s, no leaked internals, tested). **Out-of-distribution handling does not exist.** Ranked #2. |

## 6. The duplication that was found

`simulation/growth.py` defined the harvest formula twice: `simulate_growth()` repeated
`potential_harvest_g()` inline, and a module-level `potential_harvest_g()` gave the same expression.
Both were identical, so no number was wrong — and nothing would have caught them diverging.

Found by writing the invariant test `test_the_harvest_formula_has_a_single_definition`, which greps
for the expression and asserts exactly one occurrence. `simulate_growth()` now calls the function,
and a second test asserts the two agree exactly.

The same test-writing exercise caught a mistake in my own audit: my first unit test passed
`et0_reference_demand_l`'s arguments in the wrong order and compared two quantities that were not
what the test name claimed. Fixed, and the signature is now written into the test.

## 7. What was NOT done, and why

- **No experimental feature was promoted.** LED spectra, nutrient management, cultivar parameters and
  mission energy stay `experimental`. None of them gained independent validation in this phase.
- **No model was retrained.** Nothing in this phase produced training-grade evidence.
- **No new dataset was acquired.** The audit's conclusion is that the constraint is validation, not
  volume.
- **Features 2, 3, 6–10 got no implementation work.** The brief is explicit about not implementing
  several incomplete features at once, and the chosen feature's remaining layers were worth more
  than four half-built ones.
