# Phase 27 — Feature Implementation Coverage Matrix

Generated from `data/research/phase27/feature_implementation_coverage.json` on 2026-11-10 by `ml/research/build_feature_coverage.py`. Edit the JSON, not this file.

Phase 32 status: the list is closed. Every feature is either complete at the level it claims or removed from the product, so this document records what ships rather than a plan for what might.

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
| `data` — A dataset, artefact or documented assumption the calculation reads | 4 | 0 | 0 | 0 |
| `method` — The model or closed-form calculation | 4 | 0 | 0 | 0 |
| `service` — The backend module that assembles the result | 4 | 0 | 0 | 0 |
| `endpoint` — The HTTP route a client calls | 4 | 0 | 0 | 0 |
| `inputCheck` — Request validation that rejects impossible inputs | 4 | 0 | 0 | 8 |
| `outputCheck` — Validation that the result is physically coherent | 4 | 0 | 0 | 8 |
| `uncertainty` — A quantified spread, or an explicit statement that none exists | 4 | 0 | 0 | 8 |
| `provenance` — Sources and their limits travel with the answer | 12 | 0 | 0 | 0 |
| `frontend` — A screen a user can reach and read | 4 | 0 | 0 | 0 |
| `tests` — Automated tests covering the path | 12 | 0 | 0 | 0 |

## Per feature

| # | Feature | Tier | data | method | service | endpoint | inputCheck | outputCheck | uncertainty | provenance | frontend | tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Measured crop water use, compared against the platform's demand ✅ | `research-ready` | pres | pres | pres | pres | pres | pres | pres | pres | pres | pres |
| 2 | The ET0 target is itself correct ✅ | `research-ready` | pres | pres | pres | pres | pres | pres | pres | pres | pres | pres |
| 3 | Predicted harvest mass per plant | `removed` | reti | reti | reti | reti | not- | not- | not- | pres | reti | pres |
| 4 | Response to specific LED spectra and photoperiods ✅ | `research-ready` | pres | pres | pres | pres | pres | pres | pres | pres | pres | pres |
| 5 | Nutrient solution management | `removed` | reti | reti | reti | reti | not- | not- | not- | pres | reti | pres |
| 6 | Heat-stress and VPD excursion claims ✅ | `research-ready` | pres | pres | pres | pres | pres | pres | pres | pres | pres | pres |
| 7 | Cultivar-specific growth parameters | `removed` | reti | reti | reti | reti | not- | not- | not- | pres | reti | pres |
| 8 | Energy and mass cost of a described mission | `removed` | reti | reti | reti | reti | not- | not- | not- | pres | reti | pres |
| 9 | Effect of Mars or lunar gravity on crop growth | `removed` | reti | reti | reti | reti | not- | not- | not- | pres | reti | pres |
| 10 | Root-zone water status | `removed` | reti | reti | reti | reti | not- | not- | not- | pres | reti | pres |
| 11 | Plant health or growth stage from imagery | `removed` | reti | reti | reti | reti | not- | not- | not- | pres | reti | pres |
| 12 | Siting for a future climate | `removed` | reti | reti | reti | reti | not- | not- | not- | pres | reti | pres |

**4 of 12 features have every applicable layer implemented:** `measured-eta`, `independent-et0`, `led-spectrum-response`, `sub-daily-weather`.

The ✅ marks a feature at the top of its readiness ladder. The layer codes are truncated to four characters; the per-feature sections below carry the Phase 32 disposition and the evidence for each layer.

## Per-feature detail

### 1. Measured crop water use, compared against the platform's demand

Readiness tier: `research-ready` · Phase 27: completed · Phase 32: `complete`

| Layer | State | Note |
| --- | --- | --- |
| `data` | `present` | 345 usable pot-days reduced to 11 treatment-mean dates, hash-verified |
| `method` | `present` | the shipped crop-relative demand path, called unmodified |
| `service` | `present` | assembles the benchmark, the comparison, the uncertainty and the limits |
| `endpoint` | `present` | GET /api/water-use-evidence and POST /api/water-use-evidence/compare |
| `inputCheck` | `present` | extra fields forbidden, area and light scale bounded, unknown crop 422 |
| `outputCheck` | `present` | the service must reproduce the independent pandas artefact's Spearman and pair count; every curve point must be positive and inside [0,1]; the surface refuses a level claim |
| `uncertainty` | `present` | between-pot spread, measured; the three denominators shown side by side and an explicit statement that no confidence interval exists |
| `provenance` | `present` | DOI, licence, processed path and per-file SHA-256, hashVerified computed |
| `frontend` | `present` | inside the existing simulation lab; verdict, curve, spread, denominators |
| `tests` | `present` | backend suite and four browser tests across three viewports |

### 2. The ET0 target is itself correct

Readiness tier: `research-ready` · Phase 27: completed · Phase 32: `complete`

| Layer | State | Note |
| --- | --- | --- |
| `data` | `present` | FAO-56 published worked examples, transcribed with their source pages |
| `method` | `present` | FAO-56 Penman-Monteith with Hargreaves-Samani as the declared fallback; the fitted emulator was withdrawn in Phase 31 |
| `service` | `present` | one module selects the method and reports why |
| `endpoint` | `present` | GET /api/reference-et0/estimate, GET /api/reference-et0/model, and the Phase 32 validators GET/POST /api/reference-et0/validate |
| `inputCheck` | `present` | physical bounds on every weather input; 422 when vapour pressure is undefined; extra fields rejected |
| `outputCheck` | `present` | Phase 32: the result carries a plausibility verdict - 0 <= ET0 <= 30 mm/day and tmax >= tmin - returned rather than clamped |
| `uncertainty` | `present` | the response states that no measured-ET0 benchmark is bundled, that no interval is computed, and that the weather inputs are the caller's |
| `provenance` | `present` | method selection, missing inputs, weather provenance and the computed-not-measured class travel with the number |
| `frontend` | `present` | the water-demand workflow shows daily ET0, its primary method and per-scenario deltas |
| `tests` | `present` | worked examples, fallback behaviour and the output gate |

### 3. Predicted harvest mass per plant

Readiness tier: `removed` · Phase 27: removed · Phase 32: `removed`

| Layer | State | Note |
| --- | --- | --- |
| `data` | `retired` | no obtainable dataset supports this claim |
| `method` | `retired` | no implementation is served |
| `service` | `retired` | no module assembles a result |
| `endpoint` | `retired` | no route accepts it |
| `inputCheck` | `not-applicable` | no request schema accepts these inputs |
| `outputCheck` | `not-applicable` | no result is produced |
| `uncertainty` | `not-applicable` | no result is produced |
| `provenance` | `present` | the removal register, the failed evaluations and the retired card all stay committed; every model passage the assistant can quote carries its served scope |
| `frontend` | `retired` | no control, page or panel presents it |
| `tests` | `present` | no route, OpenAPI operation, catalogue row, request schema, assistant passage or workflow offers a harvest forecast |

### 4. Response to specific LED spectra and photoperiods

Readiness tier: `research-ready` · Phase 27: completed · Phase 32: `comparison-only`

| Layer | State | Note |
| --- | --- | --- |
| `data` | `present` | two measured datasets: four spectral regimes in lettuce, and the controlled-environment wheat runs varying PPFD, photoperiod, CO2 and temperature |
| `method` | `present` | a measured group comparison. The fitted response surface failed its sealed holdout (297.46 % MAPE) and was deleted in Phase 30 rather than served behind a caveat |
| `service` | `present` | both workflows assemble measured group summaries with their design caveats; a regime that changes spectrum and density at once is flagged |
| `endpoint` | `present` | GET/POST /api/workflows/light-stress/{capability,run} and the /controlled-environment equivalents |
| `inputCheck` | `present` | regime is a Literal of the measured regimes; traits and daysAfterSowing are bounded; extra fields forbidden |
| `outputCheck` | `present` | every reported group must exist in the measured table, and a group with a confounded design carries the flag |
| `uncertainty` | `present` | between-plant spread per regime, from the measured replicates; no interval is extrapolated beyond the measured groups |
| `provenance` | `present` | each regime names its source study, licence and design caveat |
| `frontend` | `present` | the guided workflows render the measured groups and their spread |
| `tests` | `present` | the workflows are tested against the measured table |

### 5. Nutrient solution management

Readiness tier: `removed` · Phase 27: removed · Phase 32: `removed`

| Layer | State | Note |
| --- | --- | --- |
| `data` | `retired` | no obtainable dataset supports this claim |
| `method` | `retired` | no implementation is served |
| `service` | `retired` | no module assembles a result |
| `endpoint` | `retired` | no route accepts it |
| `inputCheck` | `not-applicable` | no request schema accepts these inputs |
| `outputCheck` | `not-applicable` | no result is produced |
| `uncertainty` | `not-applicable` | no result is produced |
| `provenance` | `present` | No hydroponic nutrient series with a per-plant response is obtainable: the acquired archives record solution composition per treatment, not a response the platform could model. No control, page, endpoint or claim exists. |
| `frontend` | `retired` | no control, page or panel presents it |
| `tests` | `present` | the removal is asserted, not assumed |

### 6. Heat-stress and VPD excursion claims

Readiness tier: `research-ready` · Phase 27: completed · Phase 32: `complete`

| Layer | State | Note |
| --- | --- | --- |
| `data` | `present` | the scenario's own temperature, humidity and light, which are the caller's assumptions and are labelled as such |
| `method` | `present` | Tetens saturation vapour pressure; the light integral is PPFD x hours |
| `service` | `present` | assembled in the simulation response |
| `endpoint` | `present` | POST /api/simulate |
| `inputCheck` | `present` | temperature, humidity and light bounds are enforced |
| `outputCheck` | `present` | Phase 32: VPD and the light integral each carry a method, an assumptions flag and a statement that no error is propagated |
| `uncertainty` | `present` | explicit: `propagatedError: null` plus a sentence saying the value describes a scenario, not a place or a day |
| `provenance` | `present` | the VPD method and the assumption flag travel with the number |
| `frontend` | `present` | the environment panel and the digital-twin state read these values |
| `tests` | `present` | the output-check suite asserts the statements and the units map |

### 7. Cultivar-specific growth parameters

Readiness tier: `removed` · Phase 27: removed · Phase 32: `removed`

| Layer | State | Note |
| --- | --- | --- |
| `data` | `retired` | no obtainable dataset supports this claim |
| `method` | `retired` | no implementation is served |
| `service` | `retired` | no module assembles a result |
| `endpoint` | `retired` | no route accepts it |
| `inputCheck` | `not-applicable` | no request schema accepts these inputs |
| `outputCheck` | `not-applicable` | no result is produced |
| `uncertainty` | `not-applicable` | no result is produced |
| `provenance` | `present` | No experiment in the repository carries a cultivar label usable as a model input and no cultivar selector or parameter exists. A cultivar effect cannot be learned from one cultivar per study. |
| `frontend` | `retired` | no control, page or panel presents it |
| `tests` | `present` | the removal is asserted, not assumed |

### 8. Energy and mass cost of a described mission

Readiness tier: `removed` · Phase 27: removed · Phase 32: `removed`

| Layer | State | Note |
| --- | --- | --- |
| `data` | `retired` | no obtainable dataset supports this claim |
| `method` | `retired` | no implementation is served |
| `service` | `retired` | no module assembles a result |
| `endpoint` | `retired` | no route accepts it |
| `inputCheck` | `not-applicable` | no request schema accepts these inputs |
| `outputCheck` | `not-applicable` | no result is produced |
| `uncertainty` | `not-applicable` | no result is produced |
| `provenance` | `present` | No mission energy or mass budget dataset exists in the repository and the platform publishes no such figure; Phase 32 proves by test that no response carries one. |
| `frontend` | `retired` | no control, page or panel presents it |
| `tests` | `present` | the removal is asserted, not assumed |

### 9. Effect of Mars or lunar gravity on crop growth

Readiness tier: `removed` · Phase 27: removed · Phase 32: `removed`

| Layer | State | Note |
| --- | --- | --- |
| `data` | `retired` | no obtainable dataset supports this claim |
| `method` | `retired` | no implementation is served |
| `service` | `retired` | no module assembles a result |
| `endpoint` | `retired` | no route accepts it |
| `inputCheck` | `not-applicable` | no request schema accepts these inputs |
| `outputCheck` | `not-applicable` | no result is produced |
| `uncertainty` | `not-applicable` | no result is produced |
| `provenance` | `present` | Withdrawn in Phase 30: no recovered study measures production as a function of gravity - ground chambers and orbital runs compare a microgravity arm against a 1 g control, not a graded response. No input, card or route accepts a gravity value. |
| `frontend` | `retired` | no control, page or panel presents it |
| `tests` | `present` | the removal is asserted, not assumed |

### 10. Root-zone water status

Readiness tier: `removed` · Phase 27: removed · Phase 32: `removed`

| Layer | State | Note |
| --- | --- | --- |
| `data` | `retired` | no obtainable dataset supports this claim |
| `method` | `retired` | no implementation is served |
| `service` | `retired` | no module assembles a result |
| `endpoint` | `retired` | no route accepts it |
| `inputCheck` | `not-applicable` | no request schema accepts these inputs |
| `outputCheck` | `not-applicable` | no result is produced |
| `uncertainty` | `not-applicable` | no result is produced |
| `provenance` | `present` | No root-zone water-potential time series exists in the repository or in the searched sources. The simulator's single well-mixed store is a documented assumption inside the water-demand calculation, not a root-zone status feature. |
| `frontend` | `retired` | no control, page or panel presents it |
| `tests` | `present` | the removal is asserted, not assumed |

### 11. Plant health or growth stage from imagery

Readiness tier: `removed` · Phase 27: removed · Phase 32: `removed`

| Layer | State | Note |
| --- | --- | --- |
| `data` | `retired` | no obtainable dataset supports this claim |
| `method` | `retired` | no implementation is served |
| `service` | `retired` | no module assembles a result |
| `endpoint` | `retired` | no route accepts it |
| `inputCheck` | `not-applicable` | no request schema accepts these inputs |
| `outputCheck` | `not-applicable` | no result is produced |
| `uncertainty` | `not-applicable` | no result is produced |
| `provenance` | `present` | No paired imagery and harvest labels exist for a plant-health model, and the catalogue's imagery datasets are licence classes E/F, which cannot back a served model. No upload, camera view or plant-health card exists. |
| `frontend` | `retired` | no control, page or panel presents it |
| `tests` | `present` | the removal is asserted, not assumed |

### 12. Siting for a future climate

Readiness tier: `removed` · Phase 27: removed · Phase 32: `removed`

| Layer | State | Note |
| --- | --- | --- |
| `data` | `retired` | no obtainable dataset supports this claim |
| `method` | `retired` | no implementation is served |
| `service` | `retired` | no module assembles a result |
| `endpoint` | `retired` | no route accepts it |
| `inputCheck` | `not-applicable` | no request schema accepts these inputs |
| `outputCheck` | `not-applicable` | no result is produced |
| `uncertainty` | `not-applicable` | no result is produced |
| `provenance` | `present` | The CMIP6 downscaled product is catalogued at licence class D and could not be acquired; no projection data is in the repository and no climate-siting control or report exists. |
| `frontend` | `retired` | no control, page or panel presents it |
| `tests` | `present` | the removal is asserted, not assumed |

## Cross-cutting gaps found by the audit

These are not attributable to a single feature. Each names its evidence, its severity, why it matters and how hard it is to build.

| Gap | Severity | Finding | Phase 32 disposition |
| --- | --- | --- | --- |
| `water-paths-unarbitrated` | documented-limitation | Two water demand paths ship - crop-relative and ET0-reference. The response names which one ran, and the measured comparison states that it cannot decide between them because the trial publishes no pot geometry or spacing. | Not actionable with obtainable evidence. An arbiter needs per-day weather for the trial plus its pot area; neither is published, so choosing one would decide the answer before the comparison was made. |
| `no-measured-et0-benchmark` | documented-limitation | The reference-ET0 calculation is validated against the FAO-56 worked examples, not against a measured ET0 station record: none is bundled. | Stated in the response and on the model card. Acquisition of an independent station network failed reproducibly from this environment (USDA Ag Data Commons DNS, figshare search API, Dryad 401), so the claim is scoped down rather than faked. |
| `comparison-excludes-measurement` | resolved | The scenario comparison compares parameter sets; it deliberately does not mix a measured benchmark into a scenario ranking. | By design, and the measured-versus-modelled comparison now has its own panel with its own provenance, so a user does not have to infer it from a scenario table. |
| `et0-parameter-not-in-frontend` | resolved | POST /api/simulate accepts et0MmPerDay and cropCoefficient; no frontend control sets either field. | Resolved: the water-demand workflow exposes the ET0-reference path with the daily ET0, its primary method and per-scenario deltas. The simulator route keeps the fields for API callers; the served UI path is the workflow. |
| `units-not-machine-readable` | resolved | Units live in field names and prose only. | Resolved in Phase 32: /api/simulate returns a `units` map for every headline scalar, additively, so existing clients are unaffected. |
| `no-out-of-distribution-warning` | resolved | Predictions are returned without an out-of-domain flag. | Resolved: every prediction response carries `outOfDistribution` (or `outOfDomain`) with the violated bounds and the warnings that explain them. |

## What the pattern says

The audit's most useful finding was that the layers which were systematically weakest were `uncertainty` and `outputCheck` - the two that stand between a number and a defensible number.

Phase 32 closed that story rather than restating it. The output checks now exist where the arithmetic could go physically wrong (reference ET0 returns its own plausibility verdict instead of a bare number), the uncertainty statement is attached to the value it qualifies (VPD, classification scores), and the features that could not be completed were removed from every layer rather than left as `data-blocked` rows a reader could mistake for a roadmap.

Final dispositions: **1 comparison-only**, **3 complete**, **8 removed** across 12 features. No feature is left in a resting blocked state: either the claim is served with its limits, or the capability is gone.
