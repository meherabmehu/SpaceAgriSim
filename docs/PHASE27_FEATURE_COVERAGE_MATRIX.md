# Phase 27 — Feature Implementation Coverage Matrix

Generated from `data/research/phase27/feature_implementation_coverage.json` on 2026-11-10 by `ml/research/build_feature_coverage.py`. Edit the JSON, not this file.

Phase 26 asked what each feature may **claim**. This asks whether a user can actually **walk through** it: ten layers, from a scientific source to a rendered result. A layer is `present` only when a named artefact for it exists in the repository and the builder verified the path.

| State | Meaning |
| --- | --- |
| `present` | implemented and verified in this repository |
| `partial` | implemented for some inputs or some of the layer's meaning |
| `absent` | missing, and usable if built |
| `not-applicable` | the layer does not apply to this kind of feature |
| `retired` | removed in Phase 30 - the capability is gone and a test proves it is gone |

## Layer coverage

| Layer | present | partial | absent | n/a |
| --- | --- | --- | --- | --- |
| `data` — A dataset, artefact or documented assumption the calculation reads | 5 | 1 | 4 | 0 |
| `method` — The model or closed-form calculation | 4 | 3 | 3 | 0 |
| `service` — The backend module that assembles the result | 6 | 0 | 4 | 0 |
| `endpoint` — The HTTP route a client calls | 6 | 0 | 4 | 0 |
| `inputCheck` — Request validation that rejects impossible inputs | 8 | 0 | 0 | 3 |
| `outputCheck` — Validation that the result is physically coherent | 1 | 4 | 0 | 6 |
| `uncertainty` — A quantified spread, or an explicit statement that none exists | 1 | 1 | 4 | 5 |
| `provenance` — Sources and their limits travel with the answer | 9 | 1 | 0 | 2 |
| `frontend` — A screen a user can reach and read | 6 | 1 | 3 | 0 |
| `tests` — Automated tests covering the path | 10 | 0 | 0 | 2 |

## Per feature

| # | Feature | Tier | data | method | service | endpoint | inputCheck | outputCheck | uncertainty | provenance | frontend | tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Measured crop water use, compared against the platform's demand ✅ | `research-ready` | pres | pres | pres | pres | pres | pres | pres | pres | pres | pres |
| 2 | The ET0 target is itself correct | `research-ready` | pres | pres | pres | pres | pres | part | part | pres | pres | pres |
| 3 | Predicted harvest mass per plant | `removed` | reti | reti | reti | reti | reti | reti | reti | pres | reti | pres |
| 4 | Response to specific LED spectra and photoperiods | `experimental` | pres | part | abse | abse | pres | not- | not- | pres | part | pres |
| 5 | Nutrient solution management | `experimental` | part | abse | abse | abse | not- | not- | not- | pres | abse | pres |
| 6 | Heat-stress and VPD excursion claims | `research-ready` | pres | pres | pres | pres | pres | part | abse | part | pres | pres |
| 7 | Cultivar-specific growth parameters | `experimental` | abse | part | pres | pres | pres | not- | abse | pres | pres | pres |
| 8 | Energy and mass cost of a described mission | `experimental` | pres | pres | pres | pres | pres | part | abse | pres | pres | pres |
| 9 | Effect of Mars or lunar gravity on crop growth | `removed` | reti | reti | reti | reti | pres | not- | not- | pres | reti | pres |
| 10 | Root-zone water status | `data-blocked` | abse | part | pres | pres | pres | part | abse | pres | pres | pres |
| 11 | Plant health or growth stage from imagery | `data-blocked` | abse | abse | abse | abse | not- | not- | not- | not- | abse | not- |
| 12 | Siting for a future climate | `data-blocked` | abse | abse | abse | abse | not- | not- | not- | not- | abse | not- |

**1 of 12 features have every applicable layer implemented:** `measured-eta`.

The ✅ marks the one feature Phase 27 completed end to end. The layer codes are truncated to four characters; read the per-feature sections below for the meaning.

## Per-feature detail

### 1. Measured crop water use, compared against the platform's demand

Readiness tier: `research-ready` · Phase 27: completed

| Layer | State | Note |
| --- | --- | --- |
| `data` | `present` | 345 usable pot-days reduced to 11 treatment-mean dates, hash-verified |
| `method` | `present` | the shipped crop-relative demand path, called unmodified |
| `service` | `present` | assembles the benchmark, the comparison, the uncertainty and the limits |
| `endpoint` | `present` | GET /api/water-use-evidence and POST /api/water-use-evidence/compare |
| `inputCheck` | `present` | extra fields forbidden, area and light scale bounded, unknown crop 422 |
| `outputCheck` | `present` | the service must reproduce the independent pandas artefact's Spearman and pair count; every curve point must be positive and inside [0,1] |
| `uncertainty` | `present` | between-pot spread, measured; plus the three denominators shown side by side and the explicit statement that no confidence interval exists |
| `provenance` | `present` | DOI, licence, processed path and per-file SHA-256, with hashVerified computed |
| `frontend` | `present` | inside the existing simulation lab; verdict, curve, spread, denominators |
| `tests` | `present` | 24 backend tests and 4 browser tests across three viewports |

### 2. The ET0 target is itself correct

Readiness tier: `research-ready` · Phase 27: audited only

| Layer | State | Note |
| --- | --- | --- |
| `data` | `present` | POWER plus three cross-check sources |
| `method` | `present` |  |
| `service` | `present` |  |
| `endpoint` | `present` | GET /api/reference-et0/estimate and /model |
| `inputCheck` | `present` |  |
| `outputCheck` | `partial` | input-quality checks exist; no physical-plausibility gate on output |
| `uncertainty` | `partial` | cross-source spread is reported; no confidence interval |
| `provenance` | `present` |  |
| `frontend` | `present` | shown as method documentation, not as a per-simulation result |
| `tests` | `present` |  |

### 3. Predicted harvest mass per plant

Readiness tier: `removed` · Phase 27: audited only

| Layer | State | Note |
| --- | --- | --- |
| `data` | `retired` | the evaluation data is kept; the served model is not |
| `method` | `retired` | the model and its failed evaluation are recorded, not served |
| `service` | `retired` | the module itself was deleted in Phase 31; the record is kept |
| `endpoint` | `retired` | POST .../run answers 410; GET .../capability and .../parity remain |
| `inputCheck` | `retired` |  |
| `outputCheck` | `retired` |  |
| `uncertainty` | `retired` | the interval used to span a factor of 29; it is no longer served |
| `provenance` | `present` | the removal reason and every failed evaluation stay readable |
| `frontend` | `retired` | the tab is gone; the record lives in docs/PHASE31_REMOVED_MODELS.md |
| `tests` | `present` | the tests assert the capability is unavailable, not that a screen exists |

### 4. Response to specific LED spectra and photoperiods

Readiness tier: `experimental` · Phase 27: audited only

| Layer | State | Note |
| --- | --- | --- |
| `data` | `present` | two measured datasets: four spectral regimes in lettuce, and 39 controlled-environment wheat runs varying PPFD, photoperiod, CO2 and temperature |
| `method` | `partial` | measured group comparison ships; the fitted response surface failed its sealed holdout (297.46 % MAPE) and is not served |
| `service` | `absent` |  |
| `endpoint` | `absent` |  |
| `inputCheck` | `present` | lightSpectrum is a Literal of three values |
| `outputCheck` | `not-applicable` |  |
| `uncertainty` | `not-applicable` |  |
| `provenance` | `present` |  |
| `frontend` | `partial` | the selector says it is an annotation and infers no response |
| `tests` | `present` | the dataset is tested; the feature is not implemented |

### 5. Nutrient solution management

Readiness tier: `experimental` · Phase 27: audited only

| Layer | State | Note |
| --- | --- | --- |
| `data` | `partial` | acquired and verified, not preprocessed into a table |
| `method` | `absent` |  |
| `service` | `absent` |  |
| `endpoint` | `absent` |  |
| `inputCheck` | `not-applicable` |  |
| `outputCheck` | `not-applicable` |  |
| `uncertainty` | `not-applicable` |  |
| `provenance` | `present` |  |
| `frontend` | `absent` |  |
| `tests` | `present` | acquisition is tested; no nutrient feature exists |

### 6. Heat-stress and VPD excursion claims

Readiness tier: `research-ready` · Phase 27: audited only

| Layer | State | Note |
| --- | --- | --- |
| `data` | `present` |  |
| `method` | `present` | VPD is computed per scenario from temperature and humidity |
| `service` | `present` |  |
| `endpoint` | `present` | environment.vaporPressureDeficitKpa on /api/simulate |
| `inputCheck` | `present` |  |
| `outputCheck` | `partial` |  |
| `uncertainty` | `absent` | the reported VPD is a point value with no stated source error |
| `provenance` | `partial` | method named; the weather source is not attached per value |
| `frontend` | `present` |  |
| `tests` | `present` |  |

### 7. Cultivar-specific growth parameters

Readiness tier: `experimental` · Phase 27: audited only

| Layer | State | Note |
| --- | --- | --- |
| `data` | `absent` | no experiment in-repo carries a cultivar label usable as an input |
| `method` | `partial` | three species profiles, no cultivar field |
| `service` | `present` |  |
| `endpoint` | `present` | GET /api/crops lists the profiles |
| `inputCheck` | `present` |  |
| `outputCheck` | `not-applicable` |  |
| `uncertainty` | `absent` |  |
| `provenance` | `present` | 'Phase 1 simulation assumptions, not measured NASA values' |
| `frontend` | `present` |  |
| `tests` | `present` |  |

### 8. Energy and mass cost of a described mission

Readiness tier: `experimental` · Phase 27: audited only

| Layer | State | Note |
| --- | --- | --- |
| `data` | `present` | stated energy assumptions, not measurements |
| `method` | `present` |  |
| `service` | `present` |  |
| `endpoint` | `present` |  |
| `inputCheck` | `present` |  |
| `outputCheck` | `partial` |  |
| `uncertainty` | `absent` |  |
| `provenance` | `present` |  |
| `frontend` | `present` |  |
| `tests` | `present` |  |

### 9. Effect of Mars or lunar gravity on crop growth

Readiness tier: `removed` · Phase 27: audited only

| Layer | State | Note |
| --- | --- | --- |
| `data` | `retired` | no fractional-gravity growth dataset exists, and none was recoverable |
| `method` | `retired` | gravity_factor() no longer exists; a test asserts its absence |
| `service` | `retired` | the engine has no gravity term |
| `endpoint` | `retired` | /api/simulate rejects a gravity field and names the decision |
| `inputCheck` | `present` | extra='forbid' plus a model validator turn the field into a 422 |
| `outputCheck` | `not-applicable` |  |
| `uncertainty` | `not-applicable` |  |
| `provenance` | `present` | the radiation warning states that gravity is not modelled at all |
| `frontend` | `retired` | the gravity control and its presets were removed; the component that carried them was dead code and was deleted in Phase 31 |
| `tests` | `present` | the tests assert the input is refused and the factor is absent |

### 10. Root-zone water status

Readiness tier: `data-blocked` · Phase 27: audited only

| Layer | State | Note |
| --- | --- | --- |
| `data` | `absent` | no root-zone water-potential time series exists |
| `method` | `partial` | a single well-mixed store with a recovery-efficiency assumption |
| `service` | `present` |  |
| `endpoint` | `present` |  |
| `inputCheck` | `present` |  |
| `outputCheck` | `partial` |  |
| `uncertainty` | `absent` |  |
| `provenance` | `present` |  |
| `frontend` | `present` |  |
| `tests` | `present` |  |

### 11. Plant health or growth stage from imagery

Readiness tier: `data-blocked` · Phase 27: audited only

| Layer | State | Note |
| --- | --- | --- |
| `data` | `absent` | no paired imagery and harvest labels; the catalogue's imagery datasets are class E/F under their licences |
| `method` | `absent` |  |
| `service` | `absent` |  |
| `endpoint` | `absent` |  |
| `inputCheck` | `not-applicable` |  |
| `outputCheck` | `not-applicable` |  |
| `uncertainty` | `not-applicable` |  |
| `provenance` | `not-applicable` |  |
| `frontend` | `absent` |  |
| `tests` | `not-applicable` |  |

### 12. Siting for a future climate

Readiness tier: `data-blocked` · Phase 27: audited only

| Layer | State | Note |
| --- | --- | --- |
| `data` | `absent` | the CMIP6 downscaled product is catalogued at class D and not acquired |
| `method` | `absent` |  |
| `service` | `absent` |  |
| `endpoint` | `absent` |  |
| `inputCheck` | `not-applicable` |  |
| `outputCheck` | `not-applicable` |  |
| `uncertainty` | `not-applicable` |  |
| `provenance` | `not-applicable` |  |
| `frontend` | `absent` |  |
| `tests` | `not-applicable` |  |

## Cross-cutting gaps found by the audit

These are not attributable to a single feature. Each names its evidence, its severity, why it matters and how hard it is to build.

| Gap | Severity | Finding | Why | Feasibility |
| --- | --- | --- | --- | --- |
| `et0-parameter-not-in-frontend` | major | POST /api/simulate accepts et0MmPerDay and cropCoefficient, and the whole reference-ET0 water path is reachable only by hand-crafting an HTTP request. No frontend control sets either field. | a validated-by-construction capability that no user can reach | high: two optional request fields and one control group |
| `no-per-prediction-interval` | major | The harvest models report leave-one-experiment-out error as a single number. No individual prediction carries a range, so a user cannot tell whether a given scenario is inside or outside the model's envelope. | the platform's central claim is prediction, and a point estimate hides its own error | medium: quantile regression or a fold-based empirical interval |
| `no-out-of-distribution-warning` | major | Model endpoints validate types and ranges but not whether an input lies outside the training envelope. A prediction at day 60 with 1000 umol/m2/s returns a number with no warning. | an extrapolated prediction is indistinguishable from an interpolated one to a user | high: the training envelope is in the split artefacts |
| `water-paths-unarbitrated` | major | Two water demand paths ship - crop-relative and ET0-reference - and the response names which one ran but does not say they cannot both be right. | a ~60 % difference between two live calculations with no arbiter | done for the evidence half in Phase 27; the arbiter needs per-day weather |
| `comparison-is-parameter-only` | minor | The comparison module compares parameter sets. The measured benchmark cannot be included in a comparison because it is not a scenario, and there is no export of the comparison with its provenance. | users comparing scenarios cannot see how any of them relates to measurement | high |
| `units-not-machine-readable` | minor | Units appear in field names (`waterUsed` is litres, `co2Removed` grams) and in descriptions, but no response field carries a unit object, so a client must read prose to know what it has. | the stated goal includes consistent units across the platform | medium: an additive `units` map without breaking existing clients |

## What the pattern says

The audit's most useful finding is not any single `absent` cell. It is that the layers which are systematically weakest are `uncertainty` and `outputCheck` - the two that stand between a number and a defensible number. Data, method, service, endpoint and tests are largely present; what is missing is the layer that says how wrong a result might be and the layer that refuses to return an incoherent one.

That is a product problem rather than a data problem, which is why it is ranked above acquiring more datasets.
