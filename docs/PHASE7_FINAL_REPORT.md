# Phase 7 — Final Report

**Phase:** NASA scientific completion
**Branch:** `feat/phase7-nasa-scientific-completion` (base `b4890e9`)
**Verdict in one sentence:** Phase 6's central scientific claim was **wrong and is now corrected with page-cited NASA data**, one model was genuinely fixed, and **zero simulator outputs changed** because the recovered data cannot justify a change in the simulator's own units.

Status categories used below, as specified:
**Completed** · **Partially completed** · **Blocked by unavailable scientific evidence** · **Blocked by infrastructure or credentials** · **Scientifically unsupported**

---

## 1. The Phase 6 conclusion was wrong, and this is the correction

Phase 6 searched the NASA Open Science Data Repository — a **genomics and multi-omics archive** — for 1980s–90s CELSS crop physiology, found nothing, and reported that biomass time series, transpiration, water use, CO₂ assimilation, water recovery, PPFD and photoperiod response were *not measured anywhere in NASA's public data*.

They were measured. They were published in **NASA Technical Memoranda**, which OSDR does not index and which carry no machine-readable tables.

**Status: Completed.** NTRS search: 39 target-driven queries → 256 unique documents → 110 with downloadable PDFs → 6 downloaded and SHA-256 verified → 3 extracted with full safeguards.

## 2. What was recovered — 8 of 12 targets, honestly counted

| Status | Count | Targets |
|---|---|---|
| Measured | 8 | biomass time series, harvest yield, water uptake, transpiration, CO₂ assimilation, irradiance response, PPFD/photoperiod, stress outcomes |
| Measured-approximate | 1 | water recovery (0.924, one balance, leaking chamber) |
| **Not measured** | **3** | **O₂ evolution, gravity-dependent growth, radiation dose-response** |

**Status: Completed.** The three absences are recorded with the searches that failed to find them, so a negative finding is distinguishable from a search never run (`data/metadata/phase7_measurement_catalog.json`).

## 3. Every extracted number is defensible three ways

`scripts/extract_ntrs_tables.py` runs three independent safeguards and exits non-zero if any fails:

- **Provenance (46 checks):** each value carries a page number *and* an evidence string that must literally appear on that page.
- **Arithmetic:** derived columns recomputed from primaries.
- **Aggregates:** all **8** published 16-tray mean/STD pairs reproduced.

**Status: Completed.** A build that fails any check writes nothing.

## 4. Six genuine source defects found and documented rather than smoothed

| Defect | Resolution |
|---|---|
| TM-102784 tray 7 total biomass reads `451` | Corrected to `231` — the only value that reproduces the published mean (371.0 g), tray-7 EBI (16 %) **and** the printed STD (96 g). With 451 the mean is 384.75 g |
| Tray 9 plant count contradicts its own derived columns | Primaries retained; the two derived columns excluded and flagged |
| Tray 11 EBI 37 % vs 38.6 % recomputed | Biomass retained (reproduces the mean); EBI flagged as mis-rounded |
| Day-24 %root 22.0 vs 22.95 | Dry mass retained; %root flagged |
| Two different per-m²→per-m³ heights | Table 7 assumes 0.526 m, Table 10 assumes 0.385 m. Both validated as printed; recorded as inconsistent, not reconciled |
| Tray area 0.24 m² vs seed column | 1546 g/m² reproduces at exactly 0.24; the seed column needs 0.2328 (printed average) or 0.238 (recomputed). All three recorded |

**Status: Completed.** No value was rounded toward an expected answer, and nothing is graph-digitised.

## 5. A Phase 6 "blocked" target is now measured

TM-103494 reports **3615 L condensed against 3914 L added** over 8 m² and 74 days → **0.924 recovered fraction** and **6.1 L/m²/day** transpiration.

The caveat is what makes this usable: that chamber **leaked 20–40 % of its volume per day** and the added total includes plumbing losses, so 0.924 is a **lower bound**, and the authors present condensate as a transpiration proxy, not a recovery test.

**Status: Completed** (recorded as measured-approximate).

## 6. Training eligibility — zero of twelve targets train

| Eligibility | Count |
|---|---|
| ready | **0** |
| statistical | 2 |
| plausibility-only | 5 |
| insufficient | 5 |

The matrix derives verdicts from the measurement catalog, so eligibility cannot drift from the evidence.

**Status: Completed.** The headline is uncomfortable and is the point: **measurement is not trainability**, which is precisely the confusion Phase 6 fell into from the opposite direction.

## 7. Two targets are measured yet refused — deliberately

**PPFD/photoperiod (target 9).** Three operating points exist (534 µmol/m²/s at 20 h, 660 at 24 h, 530 at 20 h), each with a yield. They also differ in chamber sealing, nutrient-control maturity and a **documented copper deficiency** in Phase IV. Fitting a response surface would produce a confident curve with no identifying variation.

**Stress outcomes (target 12).** Five binary tray labels, no severity, no stressor measurement, no control arm. Training on it would manufacture a label the source never measured.

**Status: Completed** as refusals, with both recorded in `refusedTasks`.

## 8. The microbial transfer failure was diagnosed, not papered over

`mizuna-microbial-load-v1` failed leave-one-experiment-out (R² **−0.55 / −0.58**). The diagnosis:

| Campaign | Flight | Ground | Difference | n |
|---|---|---|---|---|
| VEG-04A | 5.62 | 2.55 | **+3.06 log** | 5 / 15 |
| VEG-04B | 3.61 | 0.98 | **+2.64 log** | 31 / 72 |

**The effect replicates; the campaign's absolute level does not.** VEG-04B sits ~1.6 log lower for handling and sampling reasons no feature can encode. The offset is unidentifiable — so no learner could have recovered it.

**Status: Completed** (diagnosis).

## 9. The fix was a narrower estimand, not a bigger model

v2 predicts **within-campaign standardised load** rather than absolute load:

| Target | VEG-04A R² | VEG-04B R² |
|---|---|---|
| v1 absolute (RF) | −0.269 | −0.893 |
| **v2 relative (RF)** | **+0.444** | **+0.373** |

A 200-permutation within-campaign shuffle test puts both outside the null (null means −0.174 and −0.149; **p = 0.000 on both**). The same learners still fail on the absolute target — which is the evidence the gain comes from the estimand, not from capacity.

**Status: Completed.** `mizuna-microbial-load-v1` remains registered and on disk; v2 supersedes it explicitly. Nothing overwritten.

## 10. v2 is *not* promoted to validated, and the reason is arithmetic

The project's promotion rule requires beating the baseline, positive held-out R² on every study, **and** conformal coverage within 5 points of nominal.

v2 achieves **0.849 coverage against 0.90 nominal — 5.1 points short.** The artifact records `evidenceStatus: "experimental"` and labels its interval *uncalibrated*. A rule that only ever promotes is not a rule.

**Status: Completed.**

## 11. Absolute-scale predictions are refused by design

v2 returns within-campaign standard deviations. It emits an absolute log10 CFU/g figure **only** when the caller supplies a campaign reference, and then derives it from *that campaign's own measured* mean and sd. Predicting the campaign mean from features — the exact quantity that does not transfer — is refused inside the artifact.

**Status: Completed.**

## 12. Model-family benchmark — and it is not uniformly flattering

Five tasks × four families (Dummy / linear / RandomForest / gradient boosting) on identical grouped folds:

| Task | Best | Beats baseline? |
|---|---|---|
| Lettuce fresh shoot mass (n=1648) | GBM R² 0.880 | yes |
| Mizuna harvest mass (n=14) | RF MAE 13.95 vs 14.41 | marginally (3 %) |
| Microbial **absolute** | RF R² **−0.253** | no, still negative |
| Microbial **relative** | RF R² 0.381 | yes |
| Tomato classification (n=36) | **logistic** macroF1 0.861 | yes — **linear wins** |

**Status: Completed.** Where a flexible learner wins it is reported with its group count attached; where linear wins outright that is reported too. The best available learner still cannot predict an unseen campaign's absolute microbial load.

## 13. No deep learning

Largest measured target: 123 samples over 35 groups and 2 campaigns. With two groups there is no third to hold out and learn how badly a model generalises, so any reported error would be optimistically biased regardless of grouping discipline.

**Status: Completed** (decision documented with its arithmetic).

## 14. Part C calibration: four checks performed, zero parameters changed

| Parameter | Assumed | Measured | Verdict |
|---|---|---|---|
| `WATER_RECOVERY_EFFICIENCY` | 0.90 | 0.9236 | inside interval (+2.6 %) |
| `peak_water_l_per_day` | 2.0–4.5 | DLI-scaled 2.05–2.77 | lettuce ✓, radish ✓, **tomato 1.6× above** |
| `CARBON_FRACTION_OF_DRY_MASS` | 0.42 | 0.504 implied | within 20 % of a measured CO₂ balance |
| logistic curve shape | — | dry-matter series | max residual 0.147, mean 0.074 of peak |

**Status: Completed** as checks. The policy applied in code — *apply only when the measurement is the same quantity on the same crop class* — is met **zero times**, because the recovered corpus is entirely wheat and the simulator models lettuce, tomato and radish.

Two findings are reported rather than fixed:

- **Raising water recovery toward 0.924 would be backwards** — a leak-limited lower bound is not a calibration target. A regression test locks this reasoning.
- **Tomato's water demand falls outside the wheat envelope** — reported, because a wheat stand cannot bound a tomato parameter in *either* direction.

## 15. Phase 6's tomato and radish suggestions were not applied

| Crop | Simulator | Phase 6 suggested | Applied |
|---|---|---|---|
| Tomato | 3.50 kg/m² | 3.91 | **no** |
| Radish | 1.20 kg/m² | 1.58 | **no** |

n = 2, one Antarctic analogue greenhouse, age-normalised by an assumed linear accumulation. No Phase 7 evidence changes this — the recovered corpus has no tomato or radish data at all. Asserted unchanged by test.

**Status: Completed.**

## 16. Output definitions preserved — proven mechanically

A SHA-256 over every output field (`crop_yield_g`, `growth_rate_g_per_day`, `water_used_l`, `water_recovered_l`, `co2_removed_g`, `o2_produced_g`, all factors) across **54 scenario blocks** (3 crops × 3 environments × 3 resource settings × space/Earth).

`test_output_fingerprint_is_unchanged` recomputes it on every run. A future phase that changes a baseline must regenerate the artifact and justify the diff — converting "we did not change the outputs" from a claim into a mechanism.

**Status: Completed.** Mass balance re-verified: 54/54 checks pass (recovered ≤ supplied, O₂/CO₂ stoichiometry to 1e-9, yield ≥ 0).

## 17. PostgreSQL executed for real; deployment config verified without overclaiming

Phase 6 **skipped** the integration test — a skipped test proves nothing. Phase 7 stood up PostgreSQL **17.11** on port 55432 and ran it: **1 passed**, executed.

`verify_deployment_config.py`: **19/19** — migrations apply and are idempotent, all three tables and six columns and the owner index exist, a scenario round-trips through the API's storage layer, ORM and SQL cannot drift, and **7 Phase 4 security invariants still hold** (wildcard and plaintext non-local CORS rejected; default local config never points at shared PostgreSQL).

**Status of production PostgreSQL: Blocked by infrastructure or credentials.** No production database or credentials exist here. Not verified and not claimed: production database, pooling under load, multi-instance token revocation, TLS (the local cluster used `trust` on loopback, which would be a serious production defect). `PRODUCTION_DEPLOYMENT_VERIFICATION.md` conclusions are unchanged.

## 18. UI preservation — zero source changes, measured

- **Frontend source diff vs `b4890e9`: 0 files.** No JSX, CSS, config or asset touched.
- New functionality arrives through the **existing generic registry rendering** (`MissionPlatform` → `/api/models` → `Predictions` map), exactly as the constraint permits.
- Playwright: **15/15 passed** across desktop, tablet and mobile.
- Screenshot diff: structural edges (card borders, section rules) match **in count, order and within 0/1/3 px** across three viewports. Residual 3.3 % pixel difference is **attributed to font rasterisation** — the CSS asks for Inter/Segoe UI with no bundled webfont; installing Inter brings document height to an exact match, and an identical re-capture changes only 0.01 % of pixels.

**Status: Completed.**

## 19. Integration, checksums and reproducibility

- **Versioned endpoints:** `POST /predict/mizuna-microbial-relative-load-v2`, `GET /science/measurements`, `GET /science/checksums`. `/science/evidence` → schemaVersion 2; `/science/calibration` gains an additive `phase7` block with every Phase 6 field shape unchanged.
- **Registry self-checking, 26/26:** every artifact matches its SHA-256, no orphans, the API's own loader accepts all five, supersession one-directional, recorded versions equal the pins, and **no artifact may claim "validated" while a held-out study has negative R²**.
- **Pinned environment:** `ml/requirements-training.txt` (python 3.13.16, numpy 2.3.5, pandas 2.2.3, scikit-learn 1.6.1, scipy 1.17.1).
- **Determinism:** re-running all five pipelines changed **exactly 5 lines, all `generatedAt` timestamps** — no numeric field moved.

**Status: Completed.**

## 20. What remains blocked, and what is scientifically unsupported

| Item | Category | Why |
|---|---|---|
| **O₂ evolution** | Blocked by unavailable scientific evidence | Never measured; deriving it from CO₂ would relabel an assumption as a measurement |
| **Gravity-dependent growth** | Blocked by unavailable scientific evidence | Every recovered report is a 1 g ground chamber; no clinostat or flight growth series |
| **Radiation dose-response** | Blocked by unavailable scientific evidence | All "radiation" hits are lamp spectra; no absorbed dose paired with a response |
| **PPFD/photoperiod response** | Blocked by unavailable scientific evidence | 2–3 confounded operating points; no series at constant irradiance |
| **Per-crop fresh-weight harvest baselines** | Blocked by unavailable scientific evidence | Corpus is wheat grain dry matter; no lettuce/tomato/radish data |
| **Production PostgreSQL / TLS / multi-instance revocation** | Blocked by infrastructure or credentials | No production environment available |
| **Gravity and radiation simulator coefficients** | **Scientifically unsupported** | Retained as labelled assumptions; no measurement exists to calibrate them |
| **Absolute microbial load for a new campaign** | **Scientifically unsupported** | Campaign offset is unidentifiable; requires that campaign's own baseline samples |
| **Tomato/radish 3.91 / 1.58 baselines** | **Scientifically unsupported** | n = 2 plus an assumed linear accumulation; declined again in Phase 7 |

**The single most valuable additions to this evidence base** would be a *clean* water-recovery test on a sealed chamber, and any replicated partial-gravity plant-growth dataset. Neither exists in NASA's recovered public corpus, so both remain genuinely blocked rather than merely unfound.

---

## Verification totals

| Gate | Result |
|---|---|
| Backend tests | **187 passed, 1 skipped** |
| Playwright e2e (3 viewports) | **15 / 15 passed** |
| Extraction safeguards | **46 provenance + 8 aggregate + 6 derived** |
| Mass-balance checks | **54 / 54** |
| Registry checks | **26 / 26** |
| Deployment config checks | **19 / 19** (live PostgreSQL 17.11) |
| PostgreSQL integration test | **1 passed** (executed, not skipped) |
| Frontend source diff vs base | **0 files** |

## What Phase 7 did not do

It did not calibrate the simulator. Every parameter was checked and **none was changed**, because no recovered measurement is the same quantity on the same crop class as any simulator parameter. Reporting "zero applied" is the scientific result here, not a failure to deliver: the alternative — scaling wheat transpiration onto a lettuce parameter to show activity — is exactly the error Phase 6 made in the opposite direction.
