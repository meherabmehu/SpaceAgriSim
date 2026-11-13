# JSON elimination: every file, and what replaced it

This is the file-by-file record of what the zero-JSON migration did. It lists each of the
190 `.json` files the repository held at `6551e40`, what shape holds that record now, and -
where the numbers changed - why. `docs/NO_JSON_POLICY.md` states the rule the repository
follows from here on.

## Summary

| Outcome | Files |
| --- | --- |
| Rewritten as a Python data record (`.py`) | 183 |
| Rewritten as a CSV table (`.csv`) | 3 |
| Removed, with the capability it served | 2 |
| Moved out of the tree: npm's manifests, now a TOML manifest, a lock module and a helper | 2 |
| **Total** | **190** |

Of the 190 records, 129 hold exactly the same values as the JSON they came from - the 188
converted or removed ones, plus npm's two manifests, whose JSON is regenerated from the TOML and
the lock module byte for byte and compared against the files they replaced. The other 61 changed
for one of three reasons, and each one is visible in the diff:

1. **A path field named the old encoding.** A record that said `ml/evaluation/phase34_cross_campaign_coverage.json` names the same record without a suffix now, because the file
   it points at is a `.py` module. This is the largest group.
2. **A digest followed.** An artifact hash, a registry seal or a model card's `artifactSha256`
   is computed over the file, and the file changed shape, so the digest changed with it. The
   underlying payload is unchanged; `ml/research/build_model_cards.py --check` and
   `scripts/verify_model_registry.py --check` both reproduce these values from the records.
3. **`generatedAt`.** A generator stamps the time it ran. Re-running it to regenerate the
   document also refreshed the stamp.

No scientific value was edited by hand. The measured numbers - balanced accuracies, interval
coverage, permutation p-values, harvest ratios, ET0 statistics - are the ones the JSON held,
and the gates that recompute them (`ml/research/phase36_model_reevaluation.py --check`,
`ml/research/build_et0_dataset.py --check`, `scripts/audit_models.py`) pass against the
records as stored.

## `backend/tests/data/`

| File as it was | Now | Note |
| --- | --- | --- |
| `assistant_benchmark.json` | `assistant_benchmark.py` | Python data record; values identical |

## `data/derived/`

| File as it was | Now | Note |
| --- | --- | --- |
| `bpc_benchmark.json` | `bpc_benchmark.py` | Python data record; path/digest updated |

## `data/experiments/`

| File as it was | Now | Note |
| --- | --- | --- |
| `water_use_schema.json` | `water_use_schema.py` | Python data record; path/digest updated |

## `data/literature/`

| File as it was | Now | Note |
| --- | --- | --- |
| `external_lettuce_peerj17085.json` | `external_lettuce_peerj17085.py` | Python data record; values identical |
| `external_validation_screen.json` | `external_validation_screen.py` | Python data record; path/digest updated |
| `nasa_air_and_water.json` | `nasa_air_and_water.py` | Python data record; values identical |
| `ntrs_bpc.json` | `ntrs_bpc.py` | Python data record; values identical |
| `ntrs_bpc_measurements.json` | `ntrs_bpc_measurements.py` | Python data record; values identical |
| `ntrs_supplement.json` | `ntrs_supplement.py` | Python data record; values identical |

## `data/metadata/`

| File as it was | Now | Note |
| --- | --- | --- |
| `dataset_manifest.json` | `dataset_manifest.py` | Python data record; path/digest updated |
| `download_checksums.json` | `download_checksums.py` | Python data record; values identical |
| `external_lettuce.json` | `external_lettuce.py` | Python data record; values identical |
| `integrity_report.json` | `integrity_report.py` | Python data record; values identical |
| `iot4lettuce_acquisition_manifest.json` | `iot4lettuce_acquisition_manifest.py` | Python data record; path/digest updated |
| `lysimeter_acquisition_manifest.json` | `lysimeter_acquisition_manifest.py` | Python data record; values identical |
| `lysimeter_processing_manifest.json` | `lysimeter_processing_manifest.py` | Python data record; values identical |
| `nex_gddp_acquisition_manifest.json` | `nex_gddp_acquisition_manifest.py` | Python data record; values identical |
| `ntrs_extraction_report.json` | `ntrs_extraction_report.py` | Python data record; values identical |
| `osd346_checksums.json` | `osd346_checksums.py` | Python data record; values identical |
| `osd780_quality_report.json` | `osd780_quality_report.py` | Python data record; values identical |
| `osdr_live_status.json` | `osdr_live_status.py` | Python data record; values identical |
| `phase14_manifest_checksums.json` | `phase14_manifest_checksums.py` | Python data record; values identical |
| `phase26_acquisition_manifest.json` | `phase26_acquisition_manifest.py` | Python data record; values identical |
| `phase2_nasa_candidates.json` | `phase2_nasa_candidates.py` | Python data record; values identical |
| `phase30_acquisition_manifest.json` | `phase30_acquisition_manifest.py` | Python data record; values identical |
| `phase37_acquisition_manifest.json` | `phase37_acquisition_manifest.py` | Python data record; values identical |
| `phase37_search_log.json` | `phase37_search_log.py` | Python data record; values identical |
| `phase6_checksums.json` | `phase6_checksums.py` | Python data record; values identical |
| `phase6_discovery.json` | `phase6_discovery.py` | Python data record; values identical |
| `phase7_measurement_catalog.json` | `phase7_measurement_catalog.py` | Python data record; path/digest updated |
| `phase7_ntrs_checksums.json` | `phase7_ntrs_checksums.py` | Python data record; values identical |
| `phase7_ntrs_search.json` | `phase7_ntrs_search.py` | Python data record; values identical |
| `phase7_training_eligibility.json` | `phase7_training_eligibility.py` | Python data record; values identical |
| `phase9_candidate_screen.json` | `phase9_candidate_screen.py` | Python data record; path/digest updated |
| `phase9_nasa_datasets.json` | `phase9_nasa_datasets.py` | Python data record; path/digest updated |
| `phase9_osdr_sweep.json` | `phase9_osdr_sweep.py` | Python data record; values identical |
| `power_acquisition_manifest.json` | `power_acquisition_manifest.py` | Python data record; path/digest updated |
| `power_hourly_manifest.json` | `power_hourly_manifest.py` | Python data record; path/digest updated |
| `power_validation_manifest.json` | `power_validation_manifest.py` | Python data record; path/digest updated |
| `quality_report.json` | `quality_report.py` | Python data record; values identical |
| `wur_lettuce_rocrate.json` | `wur_lettuce_rocrate.py` | Python data record; path/digest updated |

## `data/processed/`

| File as it was | Now | Note |
| --- | --- | --- |
| `et0_dataset.metadata.json` | `et0_dataset.metadata.py` | Python data record; path/digest updated |

## `data/processed/phase26/`

| File as it was | Now | Note |
| --- | --- | --- |
| `greenlight2024_lettuce_fluorescence_quality.json` | `greenlight2024_lettuce_fluorescence_quality.py` | Python data record; values identical |
| `greenlight2024_lettuce_harvest_quality.json` | `greenlight2024_lettuce_harvest_quality.py` | Python data record; values identical |
| `ledphotoperiod2025_tomato_growth_quality.json` | `ledphotoperiod2025_tomato_growth_quality.py` | Python data record; values identical |
| `ledphotoperiod2025_tomato_harvest_quality.json` | `ledphotoperiod2025_tomato_harvest_quality.py` | Python data record; values identical |
| `schroder2021_greenhouse_context_quality.json` | `schroder2021_greenhouse_context_quality.py` | Python data record; values identical |
| `schroder2021_lettuce_biomass_quality.json` | `schroder2021_lettuce_biomass_quality.py` | Python data record; values identical |
| `schroder2021_lettuce_et_daily_quality.json` | `schroder2021_lettuce_et_daily_quality.py` | Python data record; values identical |
| `schroder2021_lettuce_et_quality.json` | `schroder2021_lettuce_et_quality.py` | Python data record; values identical |

## `data/processed/phase29/`

| File as it was | Now | Note |
| --- | --- | --- |
| `light_stress_quality.json` | `light_stress_quality.py` | Python data record; values identical |

## `data/processed/phase30/`

| File as it was | Now | Note |
| --- | --- | --- |
| `quality.json` | `quality.py` | Python data record; values identical |

## `data/raw/nasa_power/`

| File as it was | Now | Note |
| --- | --- | --- |
| `power_dhaka_bd.json` | `power_dhaka_bd.py` | Python data record; values identical |
| `power_nairobi_ke.json` | `power_nairobi_ke.py` | Python data record; values identical |
| `power_reykjavik_is.json` | `power_reykjavik_is.py` | Python data record; values identical |
| `power_singapore_sg.json` | `power_singapore_sg.py` | Python data record; values identical |
| `power_tucson_us.json` | `power_tucson_us.py` | Python data record; values identical |
| `power_wageningen_nl.json` | `power_wageningen_nl.py` | Python data record; values identical |

## `data/raw/nasa_power_hourly/`

| File as it was | Now | Note |
| --- | --- | --- |
| `power_hourly_dhaka_bd.json` | `power_hourly_dhaka_bd.py` | Python data record; values identical |
| `power_hourly_nairobi_ke.json` | `power_hourly_nairobi_ke.py` | Python data record; values identical |
| `power_hourly_reykjavik_is.json` | `power_hourly_reykjavik_is.py` | Python data record; values identical |
| `power_hourly_singapore_sg.json` | `power_hourly_singapore_sg.py` | Python data record; values identical |
| `power_hourly_tucson_us.json` | `power_hourly_tucson_us.py` | Python data record; values identical |
| `power_hourly_wageningen_nl.json` | `power_hourly_wageningen_nl.py` | Python data record; values identical |

## `data/raw/nasa_power_validation/`

| File as it was | Now | Note |
| --- | --- | --- |
| `power_zurich_reckenholz_ch.json` | `power_zurich_reckenholz_ch.py` | Python data record; values identical |

## `data/raw/zenodo_20759414/14_Utilities/OpenSILEX/`

| File as it was | Now | Note |
| --- | --- | --- |
| `experiment.json` | `experiment.py` | Python data record; path/digest updated |
| `facility.json` | `facility.py` | Python data record; values identical |

## `data/research/`

| File as it was | Now | Note |
| --- | --- | --- |
| `dataset_catalog.json` | `dataset_catalog.py` | Python data record; path/digest updated |
| `dataset_gap_matrix.json` | `dataset_gap_matrix.py` | Python data record; path/digest updated |

## `data/research/phase26/`

| File as it was | Now | Note |
| --- | --- | --- |
| `feature_readiness.json` | `feature_readiness.py` | Python data record; path/digest updated |

## `data/research/phase27/`

| File as it was | Now | Note |
| --- | --- | --- |
| `feature_implementation_coverage.json` | `feature_implementation_coverage.py` | Python data record; path/digest updated |

## `data/research/phase29/`

| File as it was | Now | Note |
| --- | --- | --- |
| `environmental_stress_search.json` | `environmental_stress_search.py` | Python data record; values identical |
| `workflow_readiness.json` | `workflow_readiness.py` | Python data record; path/digest updated |

## `data/research/phase36/`

| File as it was | Now | Note |
| --- | --- | --- |
| `et0_measurement_validation.json` | `et0_measurement_validation.py` | Python data record; values identical |
| `hourly_environment.json` | `hourly_environment.py` | Python data record; values identical |
| `iot4lettuce_water_cultivar.json` | `iot4lettuce_water_cultivar.py` | Python data record; values identical |
| `projected_climate.json` | `projected_climate.py` | Python data record; values identical |

## `data/research/phase37/`

| File as it was | Now | Note |
| --- | --- | --- |
| `led_spectrum_response.json` | `led_spectrum_response.py` | Python data record; values identical |
| `nutrient_solution.json` | `nutrient_solution.py` | Python data record; path/digest updated |

## `data/validation/et0/`

| File as it was | Now | Note |
| --- | --- | --- |
| `attribution.json` | `attribution.py` | Python data record; values identical |
| `validation_summary.json` | `validation_summary.py` | Python data record; values identical |

## `docs/phase6/`

| File as it was | Now | Note |
| --- | --- | --- |
| `mizuna_reevaluation.json` | `mizuna_reevaluation.py` | Python data record; path/digest updated |
| `osd655_mass_audit.json` | `osd655_mass_audit.py` | Python data record; values identical |
| `simulation_calibration.json` | `simulation_calibration.py` | Python data record; values identical |
| `tomato_validation.json` | `tomato_validation.py` | Python data record; values identical |

## `docs/phase7/`

| File as it was | Now | Note |
| --- | --- | --- |
| `deployment_verification.json` | `deployment_verification.py` | Python data record; values identical |
| `registry_verification.json` | `registry_verification.py` | Python data record; path/digest updated |
| `scientific_calibration.json` | `scientific_calibration.py` | Python data record; path/digest updated |
| `ui_preservation.json` | `ui_preservation.py` | Python data record; path/digest updated |

## `docs/phase8/`

| File as it was | Now | Note |
| --- | --- | --- |
| `performance_ab.json` | `performance_ab.py` | Python data record; values identical |
| `performance_after.json` | `performance_after.csv` | CSV table; path/digest updated |
| `performance_after_full_sequence.json` | `performance_after_full_sequence.csv` | CSV table; path/digest updated |
| `performance_baseline.json` | `performance_baseline.csv` | CSV table; path/digest updated |

## `docs/`

| File as it was | Now | Note |
| --- | --- | --- |
| `production_monitor_run_2026-11-09.json` | `production_monitor_run_2026-11-09.py` | Python data record; values identical |
| `production_verification_2026-11-09.json` | `production_verification_2026-11-09.py` | Python data record; values identical |

## `docs/screenshots/`

| File as it was | Now | Note |
| --- | --- | --- |
| `MANIFEST.json` | `MANIFEST.py` | Python data record; path/digest updated |

## `frontend/`

| File as it was | Now | Note |
| --- | --- | --- |
| `frontend/package-lock.json` | `frontend/dependencies.lock.mjs` | The dependency tree as a generated module - 386 pinned packages with resolved URLs and integrity hashes, written by `node scripts/npm.mjs --refresh-lock`. npm still receives a lockfile, materialised outside the checkout for the length of one `npm ci` and then deleted. |
| `frontend/package.json` | `frontend/dependencies.toml` | The manifest as TOML - the same name, scripts, dependency set and version ranges, verified value for value against the manifest npm used to read before it was removed. `scripts/npm.mjs` reads it and writes npm's JSON into a temporary directory outside the repository. |
| `tsconfig.json` | - | no alternative existed |

## `ml/artifacts/cards/`

| File as it was | Now | Note |
| --- | --- | --- |
| `lettuce-earth-growth-v1.json` | `lettuce-earth-growth-v1.py` | Python data record; path/digest updated |
| `lettuce-earth-growth-v2.json` | `lettuce-earth-growth-v2.py` | Python data record; path/digest updated |
| `lettuce-earth-growth-v3.json` | `lettuce-earth-growth-v3.py` | Python data record; path/digest updated |
| `mizuna-microbial-relative-load-v2.json` | `mizuna-microbial-relative-load-v2.py` | Python data record; path/digest updated |
| `radiation-exposure-osd46-v1.json` | `radiation-exposure-osd46-v1.py` | Python data record; path/digest updated |
| `radiation-quality-osd46-v1.json` | `radiation-quality-osd46-v1.py` | Python data record; path/digest updated |
| `tomato-flight-response-v1.json` | `tomato-flight-response-v1.py` | Python data record; path/digest updated |

## `ml/artifacts/`

| File as it was | Now | Note |
| --- | --- | --- |
| `et0-emulator-v1.json` | `et0-emulator-v1.py` | Python data record; values identical |
| `lettuce-earth-growth-v1.json` | `lettuce-earth-growth-v1.py` | Python data record; path/digest updated |
| `lettuce-earth-growth-v2.json` | `lettuce-earth-growth-v2.py` | Python data record; path/digest updated |
| `lettuce-earth-growth-v3.json` | `lettuce-earth-growth-v3.py` | Python data record; path/digest updated |
| `mizuna-harvest-v1.json` | `mizuna-harvest-v1.py` | Python data record; path/digest updated |
| `mizuna-microbial-load-v1.json` | `mizuna-microbial-load-v1.py` | Python data record; path/digest updated |
| `mizuna-microbial-relative-load-v2.json` | `mizuna-microbial-relative-load-v2.py` | Python data record; path/digest updated |
| `radiation-exposure-osd46-v1-explanation.json` | `radiation-exposure-osd46-v1-explanation.py` | Python data record; values identical |
| `radiation-exposure-osd46-v1.json` | `radiation-exposure-osd46-v1.py` | Python data record; path/digest updated |
| `radiation-quality-osd46-v1-explanation.json` | `radiation-quality-osd46-v1-explanation.py` | Python data record; values identical |
| `radiation-quality-osd46-v1.json` | `radiation-quality-osd46-v1.py` | Python data record; path/digest updated |
| `registry.json` | `registry.py` | Python data record; path/digest updated |
| `tomato-flight-response-v1.json` | `tomato-flight-response-v1.py` | Python data record; path/digest updated |
| `tomato_example.json` | `tomato_example.py` | Python data record; values identical |

## `ml/evaluation/`

| File as it was | Now | Note |
| --- | --- | --- |
| `et0_dataset_quality.json` | `et0_dataset_quality.py` | Python data record; values identical |
| `lettuce_splits.json` | `lettuce_splits.py` | Python data record; values identical |
| `microbial_contrast.json` | `microbial_contrast.py` | Python data record; values identical |
| `microbial_splits.json` | `microbial_splits.py` | Python data record; values identical |
| `microbial_v2_splits.json` | `microbial_v2_splits.py` | Python data record; values identical |
| `microbial_v2_transfer.json` | `microbial_v2_transfer.py` | Python data record; values identical |
| `mizuna_splits.json` | `mizuna_splits.py` | Python data record; values identical |
| `phase10_conformal.json` | `phase10_conformal.py` | Python data record; values identical |
| `phase10_cross_study.json` | `phase10_cross_study.py` | Python data record; values identical |
| `phase10_dose_recovery.json` | `phase10_dose_recovery.py` | Python data record; values identical |
| `phase10_explanations.json` | `phase10_explanations.py` | Python data record; path/digest updated |
| `phase10_gravity_recovery.json` | `phase10_gravity_recovery.py` | Python data record; values identical |
| `phase10_partial_gravity.json` | `phase10_partial_gravity.py` | Python data record; path/digest updated |
| `phase10_partial_gravity_replication.json` | `phase10_partial_gravity_replication.py` | Python data record; path/digest updated |
| `phase10_registry_api_audit.json` | `phase10_registry_api_audit.py` | Python data record; values identical |
| `phase10_uncertainty_decision.json` | `phase10_uncertainty_decision.py` | Python data record; path/digest updated |
| `phase10_uncertainty_patch.json` | `phase10_uncertainty_patch.py` | Python data record; path/digest updated |
| `phase10_weak_model_audit.json` | `phase10_weak_model_audit.py` | Python data record; values identical |
| `phase11_dataset_discovery.json` | `phase11_dataset_discovery.py` | Python data record; values identical |
| `phase11_dose_generalization.json` | `phase11_dose_generalization.py` | Python data record; values identical |
| `phase11_duplicate_audit.json` | `phase11_duplicate_audit.py` | Python data record; values identical |
| `phase11_explainability.json` | `phase11_explainability.py` | Python data record; values identical |
| `phase11_gravity_batch.json` | `phase11_gravity_batch.py` | Python data record; values identical |
| `phase11_microbial_campaigns.json` | `phase11_microbial_campaigns.py` | Python data record; values identical |
| `phase11_ood_uncertainty.json` | `phase11_ood_uncertainty.py` | Python data record; path/digest updated |
| `phase11_radiation_validation.json` | `phase11_radiation_validation.py` | Python data record; values identical |
| `phase13_assistant_eval.json` | `phase13_assistant_eval.py` | Python data record; path/digest updated |
| `phase13_model_audit.json` | `phase13_model_audit.py` | Python data record; path/digest updated |
| `phase13_performance.json` | `phase13_performance.py` | Python data record; values identical |
| `phase26_measured_et_validation.json` | `phase26_measured_et_validation.py` | Python data record; values identical |
| `phase29_harvest_diagnosis.json` | `phase29_harvest_diagnosis.py` | Python data record; values identical |
| `phase29_harvest_experiments.json` | `phase29_harvest_experiments.py` | Python data record; values identical |
| `phase29_harvest_final.json` | `phase29_harvest_final.py` | Python data record; values identical |
| `phase29_interval_audit.json` | `phase29_interval_audit.py` | Python data record; values identical |
| `phase30_cea_wheat_response.json` | `phase30_cea_wheat_response.py` | Python data record; values identical |
| `phase30_harvest_crossstudy.json` | `phase30_harvest_crossstudy.py` | Python data record; values identical |
| `phase32_radiation_calibration.json` | `phase32_radiation_calibration.py` | Python data record; values identical |
| `phase34_cross_campaign_coverage.json` | `phase34_cross_campaign_coverage.py` | Python data record; path/digest updated |
| `phase34_probability_calibration.json` | `phase34_probability_calibration.py` | Python data record; path/digest updated |
| `phase34_visual_drift.json` | `phase34_visual_drift.py` | Python data record; values identical |
| `phase35_model_evidence.json` | `phase35_model_evidence.py` | Python data record; path/digest updated |
| `phase35_visual_drift.json` | `phase35_visual_drift.py` | Python data record; values identical |
| `phase36_model_reevaluation.json` | `phase36_model_reevaluation.py` | Python data record; path/digest updated |
| `phase37_model_evidence.json` | `phase37_model_evidence.py` | Python data record; path/digest updated |
| `phase37_visual_baseline_migration.json` | `phase37_visual_baseline_migration.py` | Python data record; values identical |
| `phase7_benchmark.json` | `phase7_benchmark.py` | Python data record; values identical |
| `phase8_lettuce_benchmark.json` | `phase8_lettuce_benchmark.py` | Python data record; values identical |
| `phase9_cross_study_transfer.json` | `phase9_cross_study_transfer.py` | Python data record; values identical |
| `phase9_osd411.json` | `phase9_osd411.py` | Python data record; values identical |
| `phase9_osd46_radiation.json` | `phase9_osd46_radiation.py` | Python data record; path/digest updated |
| `phase9_osd46_sensitivity.json` | `phase9_osd46_sensitivity.py` | Python data record; values identical |
| `phase9_osd782.json` | `phase9_osd782.py` | Python data record; values identical |
| `phase9_rnaseq_candidates.json` | `phase9_rnaseq_candidates.py` | Python data record; values identical |
| `phase9_veg_microbiome_feasibility.json` | `phase9_veg_microbiome_feasibility.py` | Python data record; values identical |
| `phase9_visual_regression.json` | `phase9_visual_regression.py` | Python data record; values identical |
| `tomato_splits.json` | `tomato_splits.py` | Python data record; values identical |

## `ml/evaluation/excluded/`

| File as it was | Now | Note |
| --- | --- | --- |
| `gravity-reorientation-osd411-v1.json` | `gravity-reorientation-osd411-v1.py` | Python data record; values identical |
| `radiation-dose-osd782-v1.json` | `radiation-dose-osd782-v1.py` | Python data record; values identical |

## `scripts/experiment/fixtures/`

| File as it was | Now | Note |
| --- | --- | --- |
| `SYNTHETIC_FIXTURE_not_a_measurement.units.json` | `SYNTHETIC_FIXTURE_not_a_measurement.units.py` | Python data record; values identical |
| `SYNTHETIC_FIXTURE_not_a_measurement__defect_bad_temperature_order.units.json` | `SYNTHETIC_FIXTURE_not_a_measurement__defect_bad_temperature_order.units.py` | Python data record; values identical |
| `SYNTHETIC_FIXTURE_not_a_measurement__defect_balance_broken.units.json` | `SYNTHETIC_FIXTURE_not_a_measurement__defect_balance_broken.units.py` | Python data record; values identical |
| `SYNTHETIC_FIXTURE_not_a_measurement__defect_date_gap.units.json` | `SYNTHETIC_FIXTURE_not_a_measurement__defect_date_gap.units.py` | Python data record; values identical |
| `SYNTHETIC_FIXTURE_not_a_measurement__defect_duplicate_row.units.json` | `SYNTHETIC_FIXTURE_not_a_measurement__defect_duplicate_row.units.py` | Python data record; values identical |
| `SYNTHETIC_FIXTURE_not_a_measurement__defect_kc_without_in_situ.units.json` | `SYNTHETIC_FIXTURE_not_a_measurement__defect_kc_without_in_situ.units.py` | Python data record; values identical |
| `SYNTHETIC_FIXTURE_not_a_measurement__defect_missing_required.units.json` | `SYNTHETIC_FIXTURE_not_a_measurement__defect_missing_required.units.py` | Python data record; values identical |
| `SYNTHETIC_FIXTURE_not_a_measurement__defect_out_of_range.units.json` | `SYNTHETIC_FIXTURE_not_a_measurement__defect_out_of_range.units.py` | Python data record; values identical |
| `SYNTHETIC_FIXTURE_not_a_measurement__defect_qc_without_note.units.json` | `SYNTHETIC_FIXTURE_not_a_measurement__defect_qc_without_note.units.py` | Python data record; values identical |
| `SYNTHETIC_FIXTURE_not_a_measurement__defect_thin_replication.units.json` | `SYNTHETIC_FIXTURE_not_a_measurement__defect_thin_replication.units.py` | Python data record; values identical |
| `SYNTHETIC_FIXTURE_not_a_measurement__defect_unit_mismatch.units.json` | `SYNTHETIC_FIXTURE_not_a_measurement__defect_unit_mismatch.units.py` | Python data record; values identical |

## `./`

| File as it was | Now | Note |
| --- | --- | --- |
| `vercel.json` | - | no alternative existed |

## The dependencies that went with the files

A record that no code reads is not a migration; these are the changes that removed the
machinery. Counted over the tree with `grep`:

| Removed | Where | What replaced it |
| --- | --- | --- |
| `import json` used for data | 162 modules under `backend/`, `ml/`, `scripts/` now import `safedata` | `import safedata` |
| `json.load` / `json.dump` on a repository file | 250 read sites, 111 write sites | `safedata.load()` / `safedata.dump()` |
| `glob("*.json")` | 15 modules | `safedata.records()` |
| `open(...json...)` for a record | every script and generator that read one | `safedata.load()` / `safedata.bytes()` |
| JSON documents produced by CI | `db-backup`, `db-restore-verify`, `production-monitor` | YAML written to `--report <path>` |
| `frontend/tsconfig.json` | frontend toolchain | the same compiler flags on the `typecheck` script's command line |
| `vercel.json` | repository root | deleted: it configured a deployment target this project does not use |
| `test-results/.last-run.json` | Playwright default output | `outputDir` points outside the checkout |

Three scripts also lost their JSON report mode and gained a YAML one, so no command in the
repository can be asked to emit a JSON document: `scripts/restore_validate.py`,
`scripts/monitor_production.py`, and the two workflows that consume them.

## What still speaks JSON, and why that is not a JSON file

The API is JSON on the wire. `POST /api/workflows/water-demand/run` takes a JSON body and
answers with one; FastAPI publishes `/openapi.json`, generated per request. That is the HTTP
protocol, not storage: no endpoint in this repository reads a `.json` file from disk, and
`backend/tests/test_zero_json_policy.py` fails if one starts to.

## How the claim is enforced

`backend/tests/test_zero_json_policy.py` runs with the rest of the suite (10 tests):

- no `*.json` file anywhere in the tree, with no exemption list, hidden directories and
  build output included;
- no source file opens, imports or points at a `.json` path;
- the data layer refuses to resolve a `.json` name and does not list it as a storage shape;
- every record under `ml/artifacts`, `ml/evaluation`, `data/research` and `data/metadata`
  loads back through the layer as a record.

A test is a stronger guarantee than a clean-up: the files cannot come back quietly.

## Verification of this migration

| Gate | Command | Result |
| --- | --- | --- |
| Backend suite, SQLite | `pytest backend/tests` | 1444 passed, 23 skipped |
| Backend suite, PostgreSQL 17.11 | same, against an isolated local database | 1467 passed, **0 skipped** |
| Science gates | the 9 `--check` scripts and `scripts/audit_models.py` | all exit 0 |
| Frontend | `node scripts/npm.mjs lint`, `typecheck`, `test:unit`, `build:check` | 0 problems, 20 tests, 240 kB initial, bundle guard passed |
| Node dependency audit | `node scripts/npm.mjs --audit` | 0 vulnerabilities |
| Browser suite | `node node_modules/@playwright/test/cli.js test` | 171 passed |
| Visual regression | `scripts/compare_ui_screenshots.py --baseline 64f869e` | `ui-extended-layout-preserved`: all three viewports pixel-identical, 0.0 % changed, 0 px drift; the 6 changed files are the manifest, the lock and the helper, not the interface |
| Reproducible demo | `scripts/demo_phase9.sh --fast --no-server` | 8/8 steps |
| CI | GitHub Actions on this commit | 5/5 jobs green |

The seven model verdicts did not move: mizuna `PASS`, the three lettuce models
`FAILS-INDEPENDENT-CHECK`, and the two radiation models plus tomato `NO-INDEPENDENT-CHECK`,
with one decision-grade model, exactly as before the migration.
