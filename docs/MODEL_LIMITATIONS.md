# Model limitations

1. The simulator uses transparent equations and scenario coefficients; it is not calibrated as an operational spacecraft crop model.
2. Earth, Moon and Mars comparisons are matched scenario views, not experimentally validated extraterrestrial forecasts.
3. NASA OSDR provenance does not turn metadata into compatible yield labels. Research artifacts are explicitly named, checksum-verified and scoped.
4. `mizuna-harvest-v1` has weak grouped validation and must not guide yield planning.
5. `tomato-flight-response-v1` accepts normalized expression only and classifies recorded molecular context, not plant health or productivity.
6. `lettuce-earth-growth-v1` (superseded by v2, kept for comparison) is limited to Batavia Othilie lettuce on Earth, 2–29 days after transplant, 20–32 C air/root temperature and 200–750 umol/m2/s PPFD. It does not model radiation, gravity, CO2, nutrient or water stress, photoperiod changes, planting density or edible area yield.
7. Forecast ranges are descriptive residual summaries, not calibrated uncertainty coverage.
8. `lettuce-earth-growth-v2` **failed its external check**. Scored against six transcribed
   observations from Wicharuck et al. 2024 (PeerJ 12:e17085, CC BY 4.0) — an independent greenhouse
   trial in Thailand — it overpredicted every one, by ×1.67 to ×5.38 with a median of ×3.21. The
   failure is structural, not a calibration offset: the model takes no cultivar input although the
   two cultivars differ by 63 % in that study, and its light response is monotonic and stepwise
   while the observed response is not. Its published R² describes interpolation within four
   experiments by one research group and must not be read as transferable accuracy. Do not use it
   to forecast harvest weight, size a farm, or compare cropping systems. See
   `GET /api/external-validation` and `docs/PHASE19_ACCOUNT_SHARING_READINESS.md`.

9. `lettuce-earth-growth-v3` is the current Earth lettuce yield model and is still
   **`trained-exploratory`**, because it **failed** the independent criterion set for it. On
   Touliatos et al. 2016 — untouched during fitting and model selection — its MAPE is 41.6 % against
   a 30 % criterion; a second source (1000 plants/m², stacked vertical farm) is refused rather than
   scored, because the per-area identity that converts yield to per-plant mass does not hold at that
   density. It fixes the two structural gaps v2 had (light now enters as daily light integral, and
   density is a caller input), which cuts development error from 232.2 % to 42.7 % and bias from
   +246.6 g to +2.6 g, but it still takes no cultivar, CO2 or nutrient input, its light response is
   monotonic where the data are not, and the near-zero bias is two opposing errors cancelling. Do not
   use it to forecast harvest weight, size a farm, or compare cropping systems. Domain: DAT 2–29,
   air/root 20–32 C, DLI 11.5–34.5 mol m⁻² d⁻¹, density 10–200 plants/m². See
   `docs/MODEL_VALIDATION_REPORT.md` and `GET /api/external-validation`.

Use the tool for hypothesis generation and transparent planning conversations, not safety-critical mission decisions.

