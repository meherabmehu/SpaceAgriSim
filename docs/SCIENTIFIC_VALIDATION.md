# Scientific validation status

The simulator is not NASA validated, independently calibrated, or approved for spacecraft operations. NASA study discovery and molecular-model evaluation are separate from validation of agronomic forecasts.

## Verified computational properties

The original backend suite checks growth monotonicity, zero-light/zero-water boundaries, area scaling, harvest/replant bookkeeping, matching Earth comparisons, water accounting and biomass-derived gas stoichiometry. The extended suite checks PPFD/temperature/humidity effects, VPD units and saturation boundary, user-specified recovery without spurious growth changes, rejection of invalid/unknown inputs, and complete extended-factor impact decomposition. Workspace tests cover matched-resource scenario comparisons, advice reproducing output numbers, nondominated optimization results, hazard constraints, valid report attachments, persistence retention and readiness.

Tests prove implementation consistency, not physical predictive accuracy. The project does not report artificial accuracy scores for these calculations.

## Missing independent evaluation

No paired experiment spanning these crops, reduced gravity, chronic absorbed radiation dose, resource availability and measured biomass/water/gas labels has been used to calibrate the deterministic engine. The combined penalties are assumptions. Generic temperature/humidity/PPFD response functions require crop/cultivar-specific experiments. Water proportional to VPD is a deliberately simple approximation, not a calibrated mechanistic crop model. Molecular-response data cannot supply crop yield labels by assumption.

Biomass-derived gas totals omit independently measured respiration and transfer processes. Fixed harvest timing ignores stress-driven phenology. Replanting assumes no downtime. Calibration and external validation would require experiments with compatible units, measured outcomes, independently assigned groups and proper train/test isolation.

## Uncertainty policy

Mathematical simulations return no empirical confidence interval (`null`) and no fabricated confidence percentage. Bounds on controls express supported scenario input ranges, not scientifically established validity ranges. Optimizer sensitivity demonstrates the model response to explicit input changes; it is not a calibrated confidence interval. A molecular model can report its own held-out or grouped validation metrics only for the exact measured task, with limitations documented separately.

The verified vapor pressure formula follows the [FAO reference](https://www.fao.org/fileadmin/user_upload/faowater/docs/ReferenceManualV32.pdf); crop water scaling, response widths and simulator crop baselines remain assumptions. These distinctions are also in API provenance, downloadable reports and methodology documentation.
