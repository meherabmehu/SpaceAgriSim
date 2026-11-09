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

Use the tool for hypothesis generation and transparent planning conversations, not safety-critical mission decisions.

