# Phase 8 — Scientific Integrity

The single question this document answers: **does anything in the product claim
more scientific support than the measurements behind it?**

It is answered by inspecting the running system, not by reading a changelog. The
classification is published at `GET /api/science/classification` and enforced by
`backend/tests/test_phase8_scientific_integrity.py`.

---

## The six categories

| # | Category | What the API may say |
|---|---|---|
| 1 | NASA-measured and directly supported | Measured-value prediction within the measured domain |
| 2 | NASA-calibrated with compatible measurements | Calibrated prediction with stated transfer assumptions |
| 3 | Experimentally supported by non-NASA data | Experimental prediction within the dataset's domain |
| 4 | Mechanistic calculation with explicit assumptions | Mechanistic estimate, assumptions attached |
| 5 | Hypothetical scenario exploration | What-if output, never a forecast |
| 6 | Unsupported scientific prediction | **Nothing. It must not be served as a prediction.** |

## Result

| Category | Count | Features |
|---|---|---|
| 1 | 0 | — |
| 2 | 0 | — |
| 3 | 5 | lettuce v1, lettuce v2, mizuna harvest, mizuna relative load, tomato flight response |
| 4 | 1 | O₂ production (photosynthesis stoichiometry) |
| 5 | 5 | simulation engine, optimizer frontier, gravity response, radiation response, PPFD/photoperiod response |
| 6 | 1 | mizuna absolute microbial load — **retired** |

Zero features sit in categories 1 or 2, and that is the correct answer rather
than a gap: no recovered NASA measurement is the same quantity, on the same crop
class, in the same units as anything the platform predicts. Phase 7 reached the
same conclusion by checking four candidate parameters against measured data and
changing none of them.

## The one category-6 feature, and what was done about it

`POST /api/predict/mizuna-microbial-load-v1` predicted absolute leaf microbial
load in log₁₀ CFU/g.

The model is not broken. It beats the mean within pooled data. What fails is
transfer: leave-one-experiment-out R² is **−0.55** when VEG-04A is held out and
**−0.58** when VEG-04B is held out. Predicting the training mean does better on
both held-out campaigns. Phase 7 diagnosed why — the campaign offset, not the
flight/ground effect, is the component that fails to move.

A surface whose only honest description is "worse than the mean" must not answer
200 with a number. It now returns **410 Gone**, with the R² values and the
replacement endpoint in the body, and is marked deprecated in OpenAPI.

Three deliberate choices in that retirement:

- **The artifact stays.** It is still registered and still checksum-verified.
  Deleting it would destroy the reproducibility of the Phase 6 result, which is
  itself a scientific asset.
- **Validation stays.** Malformed input still fails 422, so the retirement is not
  an excuse for sloppy input handling.
- **A replacement is named.** `mizuna-microbial-relative-load-v2` predicts the
  within-campaign standardised load: held-out R² +0.444 / +0.373 with permutation
  p = 0.000 on both campaigns.

## Surfaces that are honest and were left alone

These were checked specifically because they are the easiest places to
accidentally overclaim, and each already carries a disclosure:

- `/api/simulate`, `/api/compare`, `/api/advisor`, `/api/optimize` — every
  response carries `PHASE_1_DISCLAIMER`, the assumptions list, and a `LIMITATIONS`
  block. The advisor's insights label themselves "model response, not a measured
  stress probability".
- `frontend/src/pages/modules/Evidence.jsx` — states the models are "not
  independent validation" and that "NASA study associations provide research
  context, not parameter calibration".
- `frontend/src/components/ModelAssumptions.jsx` — describes the engine as a
  mathematical prototype, not validated NASA predictions.
- `/api/scientific-summary` — reports `platformMaturity: research-and-education`,
  `nasaEndorsed: false`, `missionCertified: false`, `validatedModels: []`.

## Artificial precision removed

`evidenceStatus` is computed from each artifact's own measured metrics, never
assigned by hand, and defaults to the weaker label when absent — a model cannot
acquire a confident label by omission. `mizuna-harvest-v1` is hard-pinned to
`baseline-only` because its target definition is not consistent between arms.

## What is still honestly blocked

These are not failures of this phase; they are targets for which no measurement
exists in the recovered corpus. Each would need new data, not new code:

| Target | Why it stays assumed |
|---|---|
| Gravity-dependent growth | No partial-gravity plant dataset recovered. The 15 %-loss-at-0 g figure is a placeholder and is labelled as one. |
| Radiation dose-response | Every "radiation" hit in the corpus is a lamp spectrum, not absorbed dose. |
| PPFD/photoperiod response surface | The 2–3 available operating points are confounded with system phase and a copper deficiency. Rated `insufficient` in Phase 7. |
| O₂ evolution | Never measured in the corpus. Derived stoichiometrically and named "estimated" in the response. |
| Per-crop fresh-weight baselines for tomato and radish | No measured harvest series for either crop. |
| Water recovery | 0.90 is conservative against a measured 0.924 lower bound from a leaking chamber — a scenario assumption, not a fitted coefficient. |

## Invariant check

The engine was swept across **6480 scenarios** (3 crops × 5 gravity levels × 4
radiation levels × 3 water levels × 3 photoperiods × 3 CO₂ levels × 4 mission
lengths) checking finiteness, non-negativity, `water_recovered ≤ water_used`, and
factor ranges. **Zero violations.**

Worth recording because the first pass reported 9380 violations, and all of them
were the probe's fault: it asserted that the CO₂ factor must be ≤ 1.0, when CO₂
enrichment is *supposed* to push growth above the reference. A wrong invariant
manufactures bugs. The fix belonged in the test, and the engine was not touched.
