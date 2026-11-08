# Phase 13 — Simulator Validation and Boundary Behaviour

Artifact: none written — the checks are assertions, run by
`backend/tests/test_phase13_simulator_boundaries.py` (47 tests) alongside the existing
`test_scientific_invariants.py` and `test_phase8_scientific_integrity.py`.

This document covers two questions that are easy to conflate: *does the simulator stay numerically
coherent at its limits*, and *does it ever describe its output as something it is not*.

---

## 1. What the simulator is

`assumptions-2.0` is a transparent mechanistic model. Growth is driven by multiplicative response
factors for light, water, gravity, radiation, CO₂, intensity, temperature and humidity applied to a
per-crop reference productivity, with biomass carbon stoichiometry for CO₂/O₂. Every number in
`app/config/simulation_constants.py` is a documented assumption, not a fitted parameter.

`provenance.nasaValidated` is `false` in every response, `confidenceInterval` is `null`, and the
uncertainty field states that parameter sensitivity is not a confidence interval. Those are not
decoration: they are asserted.

## 2. Boundaries

Every numeric parameter is driven to its declared minimum and maximum
(`PARAMETER_RANGES`), and the response must remain physically coherent:

* every headline output is finite and non-negative;
* every value in the daily series is finite and non-negative;
* harvested mass never exceeds the biomass grown;
* the series has one row per simulated day **plus day 0** — a 365-day mission returns 366 rows and
  the last row is day 365 (an off-by-one here would silently truncate a mission by a day);
* area scaling is proportional across the full range (0.1 → 100 m², a factor of 1000, within the
  one-decimal rounding of the reported yields).

Values outside the declared range are rejected with 422 rather than clamped, so a caller is never
given a number computed from a silently adjusted input.

Boundary cases specifically exercised: zero water availability (a deficit, not a crash), zero
gravity (orbit — an estimate, still labelled), the smallest and largest growing area, and the
longest mission.

## 3. Invariants retained from earlier phases

`test_scientific_invariants.py` continues to pass unchanged: daily mass balance, harvest removing
standing biomass, monotonic growth within a cycle, non-negative biomass, water conservation,
no transpiration demand at planting, supply bounded by availability, oxygen/carbon stoichiometry,
carbon mass balance from dry matter, harvest-index consistency and linear area scaling. Phase 13
added no physics; it added boundaries to the same engine.

## 4. The language checks

Six assertions exist because a coherent number presented as a measurement is a worse failure than
an incoherent number:

1. **No forbidden phrasing.** No response, for Earth, Moon or Mars, contains "NASA validated",
   "guaranteed", "will produce", "measured crop yield on", "measured lunar/martian" or "proven to
   grow".
2. **Reduced gravity is labelled.** Moon and Mars responses carry `nasaValidated: false`, a null
   confidence interval, and a warning that names gravity or the planetary case as an assumption.
3. **The disclaimer travels.** JSON and CSV exports contain the not-validated statement; the PDF
   response is a PDF (its text content is generated from the same `LIMITATIONS` list, which the
   other formats assert directly).
4. **Stress factors are assumptions.** The method string says "assumed response-factor deficits,
   not a trained health classifier", and every factor is ≤ 1.
5. **Comparison is hypothetical.** `/api/compare` names its method "hypothetical" and every
   limitation is framed as a negation or an exploratory statement.
6. **The optimizer is bounded.** 81 candidates, method "bounded discrete Pareto search", and a
   limitation stating that the frontier is not a global optimum.

## 5. What this does not establish

* The model is **not calibrated** against measured crop data and no empirical prediction interval
  exists. Sensitivity is not uncertainty.
* Boundary coherence is not accuracy. A model can be perfectly self-consistent and wrong.
* No simulation output is a lunar or Martian crop measurement, and none is presented as one.
  There is no dataset in this repository that pairs partial gravity with a crop-production
  measurement — see `docs/PHASE13_DATASET_PROVENANCE.md` §5.
* The molecular and radiation classifiers are separate models; they do not feed the simulator, and
  they do not predict yield, biomass, survival or productivity.

## 6. Reproducing

```bash
python3 -m pytest -q backend/tests/test_phase13_simulator_boundaries.py   # 47 tests
python3 -m pytest -q backend/tests/test_scientific_invariants.py \
                      backend/tests/test_phase8_scientific_integrity.py    # retained invariants
```
