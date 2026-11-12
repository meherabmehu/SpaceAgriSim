# Final scientific data acquisition, evidence completion and project handover

SpaceAgriSim — what was acquired, what it proves, and what it does not.

Every number in this report was produced on the delivered tree by the command or script printed
beside it, and the artefact that contains it is named. Where something could not be verified, the
report says so and gives the reason rather than leaving a blank that reads like a pass.

---

## 1. Starting commit

| | |
|---|---|
| Branch at start | `main` |
| Commit | `f6f6da1fa3637c1d5b59bc57e00fb4085076eb43` |
| Working tree at start | clean except `docs/FINAL_LIVE_PRODUCTION_VERIFICATION.md` (untracked, from the preceding live-verification task, deliberately not carried into this branch) |
| `origin/main` at start | identical to the local `HEAD`, confirmed with `git ls-remote` |

The repository's `.git` directory was absent at the start of the session and was reattached with
`scripts/restore_git.sh` after backing the tree up. No file was modified by that step; the tracked
tree hashed identically to `f6f6da1` afterwards.

## 2. Final commit

Recorded in §17 and §18, after the merge and the push, from `git rev-parse HEAD` and
`git ls-remote origin refs/heads/main`.

---

## 3. Datasets discovered

Fifteen candidate sources were evaluated this phase. The search covered the Zenodo REST API with
seven targeted queries (`sort=bestmatch`, dataset resource type), NASA POWER (both the daily and
the hourly temporal endpoints), NASA NEX-GDDP-CMIP6 on the public S3 bucket, and the record-level
metadata of every Zenodo candidate before any download was attempted.

| # | Source | Identifier | What it is | Outcome |
|---|---|---|---|---|
| 1 | NASA POWER hourly | `power.larc.nasa.gov/api/temporal/hourly/point` | hourly agroclimatology, 6 sites | **acquired** |
| 2 | NASA NEX-GDDP-CMIP6 | `nex-gddp-cmip6` S3, ACCESS-CM2 | downscaled CMIP6 daily projections | **acquired** |
| 3 | Agroscope weighable lysimeter | `10.5281/zenodo.20825203` | daily ETa, FDR, tensiometer, 2013-2016 | **acquired** |
| 4 | TERENO Graswang/Fendt | `10.5281/zenodo.3957208` | eddy-covariance and lysimeter fluxes | **acquired** |
| 5 | IoT4Lettuce | `10.5281/zenodo.20759414` | 45-plant fertigation and cultivar trial | **acquired (partial, by design)** |
| 6 | Dryad vadose-zone VWC | `10.5061/dryad.f5220r3` | soil water-content time series | identified, not taken |
| 7-14 | eight Zenodo records screened | `21788135`, `15523958`, `24102602`, `8362912`, `8174579`, `17433301`, `14548936`, `20665025` | see §6 | **rejected** |
| 15 | POWER daily at the lysimeter site | same endpoint, new coordinates and window | forcing for the level test | **acquired** |

Item 6 was not rejected on merit: the Agroscope FDR series answers the same question at four
depths with a tighter licence and an in-repo parser, so a second soil-moisture source would have
added a file rather than a fact. It is recorded so that a later phase does not re-derive it.

## 4. Datasets downloaded

| Dataset | Objects / members | Bytes transferred | Checksum |
|---|---|---|---|
| POWER hourly | 6 JSON | 6.76 MB | SHA-256 per file in `data/metadata/power_hourly_manifest.json` |
| POWER daily (lysimeter site) | 1 JSON | small | SHA-256 in `power_validation_manifest.json` |
| NEX-GDDP-CMIP6 | 50 NetCDF objects | 12.62 GB | SHA-256 per object, computed while streaming |
| Agroscope lysimeter | 7 files | 6.24 MB | publisher MD5 verified for all 7 |
| TERENO | 1 TAR (5 workbooks) | 8.49 MB | publisher MD5 verified |
| IoT4Lettuce | 12 of 20,679 members | 3.19 MB in 40 HTTP range requests | member SHA-256 each; archive MD5 **not** verified |

**77 files or members in total.** The NEX objects were streamed, hashed and discarded rather than
retained: 12.62 GB of globally redundant gridded data to keep six point series is not a trade this
repository should make, and the SHA-256 of each object is retained so the derived series stays
traceable to an exact source object. The acquisition script reproduces the whole thing.

The IoT4Lettuce archive is 39.1 GB. The first probe concluded it could not be inspected remotely;
that conclusion was wrong. The object does support range requests on its real (redirected) URL, so
`ml/research/acquire_iot4lettuce.py` reads the zip central directory through a range-backed
file object and transfers only the twelve measurement tables.

## 5. Datasets inspected

Every acquired dataset was opened and its structure, units, encodings and missing-value conventions
recorded before any analysis touched it. Five findings changed the code:

1. **POWER hourly irradiance is published in MJ/hr, not W/m².** Reading it as W/m² understated
   irradiance by a factor of 278 and produced a daily light integral of 0.1 mol m⁻² d⁻¹, which is
   physically impossible and was caught by checking the number rather than the schema. The importer
   now asserts the provider's published units from the response itself.
2. **POWER hourly timestamps are local standard time**, as the response header states. They are
   stored as `timestamp_lst` and never relabelled as UTC. That the labelling is local was confirmed
   independently from the data: Tucson (−110.95°) peaks at 12:00 and not at 19:00.
3. **NEX-GDDP-CMIP6 stores temperature in kelvin and precipitation as a kg m⁻² s⁻¹ flux.** The
   first ingestion stored both as-is and rounded precipitation to three decimals, turning a monsoon
   site into a column of zeros. Units are now read from each file's `units` attribute and asserted.
4. **NEX-GDDP-CMIP6 longitudes run 0…360.** A naive nearest-neighbour search sent Reykjavik to an
   Atlantic cell of fill values (1×10²⁰). The conversion is explicit and the fill count per file is
   recorded.
5. **The IoT4Lettuce climate tables are cp1252, not UTF-8**, and several TERENO workbooks duplicate
   the same observations across sheets. Both are handled explicitly; the excluded sheets are listed
   with the reason in `data/metadata/lysimeter_processing_manifest.json`.

## 6. Datasets rejected

| Source | Identifier | Why |
|---|---|---|
| Zenodo record | `21788135` | PDF publication, no data |
| Zenodo record | `15523958` | PDF publication, no data |
| Zenodo record | `24102602` | PDF publication, no data |
| Zenodo record | `8362912` | PDF publication, no data |
| Zenodo record | `8174579` | PDF publication, no data |
| Zenodo record | `17433301` | PDF publication, no data |
| Zenodo record | `14548936` | PDF publication, no data |
| Zenodo record | `20665025` | 61 MB soil-moisture prediction set, wrong system and wrong scale |
| TERENO `GW2013_.xlsx` | sheet `all Data` | no wind-speed column, so the aerodynamic term of Penman-Monteith cannot be evaluated |

Rejection is a recorded outcome, not a silent skip. The seven PDF-only records are the most common
failure mode of a Zenodo search: a query returns a publication whose metadata says "dataset" nowhere
and whose files are one article.

## 7. Datasets accepted and integrated

Five datasets were accepted and integrated, and all five are class A in
`data/research/dataset_catalog.json` — acquired, used, and driving a committed artefact.

| Dataset | Licence | Integrated as | Drives |
|---|---|---|---|
| POWER hourly | NASA open, no restrictions | `data/processed/power_hourly/` | `data/research/phase36/hourly_environment.json` |
| NEX-GDDP-CMIP6 | open, CMIP6 terms | `data/processed/nex_gddp/` | `data/research/phase36/projected_climate.json` |
| Agroscope lysimeter | CC BY 4.0 | `data/processed/lysimeter/zurich_*.csv` | `data/research/phase36/et0_measurement_validation.json` |
| TERENO EC + lysimeter | CC BY 4.0 | `data/processed/lysimeter/tereno_hourly.csv` | the same artefact, formulation leg |
| IoT4Lettuce (12 members) | CC BY 4.0 | `data/raw/zenodo_20759414/` | `data/research/phase36/iot4lettuce_water_cultivar.json` |

Integration follows the architecture already in the repository: a raw file written before parsing,
a SHA-256 and byte size per file, a manifest naming the exact request parameters and provider
version, and a separate processing step that converts to a tidy CSV with every unit conversion
listed. `data/processed/` never contains a value that did not come from a named raw file, and no
value is interpolated, gap-filled or silently converted.

IoT4Lettuce is a **partial** acquisition in the deliberate sense: 12 of 20,679 members, 3.19 MB of
39.1 GB. The manifest records `archiveMd5Verified: false` and `membersNotAcquired: 20667`, so
no reader can mistake "the archive was inspected" for "the archive was downloaded".

## 8. Status of all 14 gaps

Source of truth: `data/research/dataset_gap_matrix.json`; rendered into
`docs/DATASET_GAP_MATRIX.md` by `ml/research/build_gap_matrix.py`, whose `--check` mode fails on
drift.

**2 closed by data, 2 closed by decision, 4 partially closed, 6 open.**

| # | Gap | Before | After | What changed |
|---|---|---|---|---|
| 1 | `measured-eta` | open, partially addressed | **PARTIALLY CLOSED** | Two measured ET records acquired. Neither crop is lettuce, so the original requirement stands; the *level* of ET is now anchored |
| 2 | `independent-et0` | open, partially addressed | **PARTIALLY CLOSED** | The missing half — measured latent heat — now exists: r = 0.971 over 536 days on measured forcing |
| 3 | `fractional-gravity` | closed by decision | **CLOSED** | Unchanged; no new candidate claimed |
| 4 | `led-spectrum-response` | open | **OPEN** | No new spectrum-resolved biological response dataset |
| 5 | `substrate-water` | open | **OPEN** | A four-depth field soil series was acquired, but it is not a CEA substrate |
| 6 | `sub-daily-weather` | open, too coarse | **CLOSED** | 52,560 hourly records, units and time standard verified, and used |
| 7 | `cultivar-metadata` | open | **PARTIALLY CLOSED** | First measured cultivar contrast: 1.82× harvest mass, p < 1/20,000 |
| 8 | `imagery` | open | **OPEN** | 5,245 annotated images located but not acquired; no canopy claim is made |
| 9 | `yield-labels` | closed by decision | **CLOSED** | 45 measured harvest weights acquired; too few to reinstate a removed capability |
| 10 | `mission-energy` | open, out of scope | **OPEN** | No change; no energy claim exists |
| 11 | `nutrient-balance` | open, out of scope | **OPEN** | Three nitrogen levels and SPAD acquired; that is a contrast, not a balance |
| 12 | `long-run-climate` | open | **CLOSED** | 50 NEX objects at six sites, both windows fill-free, deltas computed |
| 13 | `crop-water-response-ky` | open | **PARTIALLY CLOSED** | Two-level deficit experiment with measured harvest; Ky bounded near zero, not estimated |
| 14 | `prediction-intervals-independent-coverage` | open | **OPEN** | The new campaign is outside the models' declared domain, so coverage could not be measured |

Two of the four closures are closures by data; the other two are the Phase 30 decisions to remove
a capability rather than carry a placeholder, and they are counted separately because they are not
the same kind of result.

### What each partial closure actually rests on

**`measured-eta`.** Six weighable lysimeters at Zurich-Reckenholz measured daily actual ET for
1,096 days (`data/processed/lysimeter/zurich_eta_daily.csv`, 6,576 lysimeter-days, all seven
publisher checksums verified). A weighable lysimeter is a direct mass balance: no part of the
number comes from a model. Measured ETa divided by modelled ET0 gives an implied crop coefficient
whose median over the 673 days with ET0 ≥ 1 mm/day is **0.958**; the complete water years give
annual ratios of 1.096 (2014) and 0.946 (2015). The test is a factor-of-two band on the median,
because a level error is multiplicative and shifts the whole distribution, while the daily spread
is the phenomenon a crop coefficient exists to describe.

**`independent-et0`.** FAO-56 evaluated on *measured* available energy, air temperature, vapour
pressure and wind reproduces eddy-covariance latent heat at Graswang and Fendt:

| Quantity | Value |
|---|---|
| Daily aggregates (≥ 4 valid hours) | 536 |
| Correlation | **0.9711** |
| Bias (modelled − measured) | +0.568 mm/day |
| RMSE | 0.831 mm/day |
| Median measured/modelled | **0.816** |
| Hourly pairs | 6,263 (r = 0.913, slope 0.735) |

A median ratio of 0.816 is the value expected for a meadow rather than for the hypothetical
reference sward the equation defines, so it is evidence that the formulation is right, not that it
is biased. What this does **not** establish is site-level absolute correctness at the six siting
sites: the measurement sites are not those sites, and the 0.519 mm/day ERA5–POWER forcing
difference is untouched.

**`cultivar-metadata`.** Two cultivars under identical nitrogen and irrigation treatments:
Grand Rapid 41.93 g (n = 15, sd 11.11) against Lollo Rossa 23.07 g (n = 15, sd 7.42), a ratio of
**1.818**, permutation p below 1 in 20,000, bootstrap 95 % interval 11.93–25.80 g. The join between
the record's two published tables was verified by matching measured leaf number, height and
diameter on all 45 plants rather than inferred from identifier text; 45 of 45 matched and the
prefix rule held on every one.

**`crop-water-response-ky`.** The same trial replaces 50 % or 75 % of the water lost between
irrigations, and harvest mass is destructive and measured. The yield difference is **not**
distinguishable from zero: 42.73 g against 41.93 g, n = 15 each, difference −0.80 g, permutation
p = 0.843, bootstrap interval −7.93 to +6.20 g. Under the design's nominal water-use ratio of 0.667
the implied Ky is −0.057; under 0.75 it is −0.076 and under 0.90 it is −0.191. The honest reading is
that this experiment **bounds lettuce Ky as small over the 50–75 % application range**; it does not
produce a positive slope, and the water-use axis is a design variable, not a measurement.

## 9. Model evidence before re-evaluation

From `ml/evaluation/phase35_model_evidence.json`, unchanged throughout Phase 36:

| Model | Verdict before | Decision-grade |
|---|---|---|
| `lettuce-earth-growth-v1` | fails-independent-check | no |
| `lettuce-earth-growth-v2` | fails-independent-check | no |
| `lettuce-earth-growth-v3` | fails-independent-check | no |
| `mizuna-microbial-relative-load-v2` | passes-independent-check | **yes** |
| `radiation-quality-osd46-v1` | no-independent-check | no |
| `radiation-exposure-osd46-v1` | no-independent-check | no |
| `tomato-flight-response-v1` | no-independent-check | no |

One of seven.

## 10. Model evidence after re-evaluation

`ml/research/phase36_model_reevaluation.py` → `ml/evaluation/phase36_model_reevaluation.json`.
No model was retrained, no threshold moved, no artefact changed: the script hashes every card and
fails if a hash differs from the registry.

| Model | Outcome | Why |
|---|---|---|
| `lettuce-earth-growth-v1` | **DOMAIN-REFUSED** | Campaign air temperature 13.1–41.8 °C against a declared 20–32 °C domain; root temperature not measured; the only measured mass is at 42 days after transplant against a declared 2–29 day domain |
| `lettuce-earth-growth-v2` | **DOMAIN-REFUSED** | same three violations |
| `lettuce-earth-growth-v3` | **DOMAIN-REFUSED** | same three violations |
| `mizuna-microbial-relative-load-v2` | **NO-NEW-EVIDENCE** | nothing acquired bears on mizuna microbial load |
| `radiation-quality-osd46-v1` | **NO-NEW-EVIDENCE** | no new radiation-quality measurement |
| `radiation-exposure-osd46-v1` | **NO-NEW-EVIDENCE** | no new radiation-exposure measurement |
| `tomato-flight-response-v1` | **NO-NEW-EVIDENCE** | no new tomato flight data |

`DOMAIN-REFUSED` is not a pass and not a failure. It means the independent campaign could not
produce evidence about that model without violating the model's own declared domain, and the
refusal is the correct behaviour: forcing a prediction from a model whose card says the input range
is 20–32 °C at 41.8 °C would produce a number the card itself declares invalid. The temptation to
score it anyway was the single largest integrity risk in this phase.

## 11. Decision-grade outcomes

| | Before | After |
|---|---|---|
| Models served | 7 | 7 |
| Decision-grade | **1** | **1** |
| Scored on new independent evidence | — | **0** |

The count did not move, and this report does not pretend otherwise. The one decision-grade model is
still `mizuna-microbial-relative-load-v2`, and the acquisition added no evidence either for or
against it. What the phase did produce is a *measured* negative on the lettuce family: three models
whose domain excludes the only independent lettuce campaign the project now holds.

## 12. Evaluation results

All five analyses are reproducible from the committed scripts and their JSON outputs.

**Measured ET against modelled ET0** (§8). Formulation: r = 0.971, RMSE 0.831 mm/day over 536
days. Level: median implied Kc 0.958 over 673 active days, inside the factor-of-two band.

**Hourly environment** (`data/research/phase36/hourly_environment.json`). 2023, six sites:

| Site | DLI (mol m⁻² d⁻¹) | Mean diurnal ΔT (°C) | Hours > 2.5 kPa VPD | DLI within ±2 h of noon |
|---|---|---|---|---|
| Wageningen | 23.1 | 7.9 | 0 | 63 % |
| Tucson | 43.3 | 14.9 | **3,227** | 64 % |
| Singapore | 33.4 | 4.1 | 0 | 64 % |
| Dhaka | 32.5 | 9.2 | 672 | 65 % |
| Reykjavik | 16.8 | 4.2 | 0 | 69 % |
| Nairobi | 43.1 | 13.3 | 879 | 63 % |

The information-loss test is the point of the table: across 30 daily-mean VPD bins the number of
hours above 2.5 kPa varies by up to **8 hours** between days that share the same daily mean. A
controller sized on the daily mean would not see that, and this is what the hourly acquisition buys.

**Projected environment** (`data/research/phase36/projected_climate.json`). ACCESS-CM2, SSP2-4.5,
2000–2004 against 2045–2049:

| Site | ΔT (°C) | ΔTmax (°C) | ΔVPD (kPa) | ΔDLI (mol m⁻² d⁻¹) | Δ days > 30 °C | Δ precipitation (mm/yr) |
|---|---|---|---|---|---|---|
| Wageningen | +2.08 | +2.33 | +0.09 | +1.39 | +54 | +26 |
| Tucson | +1.90 | +1.88 | +0.23 | +0.26 | +117 | +31 |
| Singapore | +1.32 | +1.26 | +0.02 | −0.07 | +61 | +225 |
| Dhaka | +1.27 | +1.07 | +0.07 | −1.44 | +143 | +317 |
| Reykjavik | +0.93 | +0.85 | −0.00 | +0.34 | 0 | −82 |
| Nairobi | +1.70 | +1.47 | +0.05 | +0.39 | +178 | +173 |

These are one model's response. The inter-model spread is the uncertainty and it is not
characterised here; every use of the table has to carry that sentence.

**Cultivar and irrigation** (§8). 1.82× cultivar ratio at p < 1/20,000; irrigation null at p = 0.843.

## 13. Gate results

Run on the merged tree (§17).

| Gate | Result | Evidence |
|---|---|---|
| Backend suite, SQLite | **PASS** | 1,280 passed, 24 skipped |
| Backend suite, PostgreSQL 17 (skips are failures) | **PASS** | 1,304 passed, **0 skipped** |
| Phase 36 acquisition tests | **PASS** | 22 passed |
| `bandit -r backend/app` | **PASS** | 0 findings, 0 by severity |
| `pip-audit` | **PASS** | no known vulnerabilities |
| Model audit | **PASS** | 202 checks, 0 failed, 0 undocumented gaps |
| Registry checksums and training environment | **PASS** | 62/62 checks |
| Provenance manifest | **PASS** | 9 artefacts complete |
| Feature readiness · feature coverage | **PASS** | up to date, 12 features each |
| Dataset gap matrix `--check` | **PASS** | 14 gaps, no drift |
| Dataset catalogue `--check` | **PASS** | 34 datasets, no drift |
| Phase 34 measurements · Phase 35 verdicts `--check` | **PASS** | consistent |
| Screenshot store dedupe `--check` | **PASS** | 53 images, 46.9 MB duplicates recorded |
| Frontend lint | **PASS** | clean |
| Frontend typecheck | **PASS** | clean |
| Frontend unit tests | **PASS** | 20/20 |
| Frontend `build:check` | **PASS** | 240 kB initial request, within the 245,760 B budget; no cycles; no oversized chunk |
| Playwright end-to-end | **PASS** | 171 passed across desktop, tablet and mobile (3.9 min) |
| Visual regression | **FAIL — not attributable to this change** | see below |

**Visual regression.** `scripts/visual_regression.py` reports canvas-size changes and 6–13 % pixel
differences against the committed baselines. The baselines were **not** refreshed, because
refreshing them would bake this environment's rendering into the repository and erase the signal.

The difference is not caused by anything in this phase, and that is demonstrable rather than
asserted: the largest height change (128 px, mobile) is on the **mission page**, which renders no
acquired dataset, no model card and no catalogue entry — nothing this phase touched. A page that
reads none of the changed data cannot have been changed by it. The pattern across all the failures
— identical canvas widths, small height changes on text-dense pages, pixel differences on pages of
identical size — is the signature of different font metrics and antialiasing in a freshly installed
browser, not of a layout or content change.

The previous recorded result on `f6f6da1`, in the environment the baselines were captured in, was
18/18 comparisons at 0.000 % difference. This run is reported as a failure because it is one; it is
reported as *not attributable* because the evidence says so, and the two statements are kept apart
rather than merged into a comfortable one.

## 14. Audits

| Audit | Result |
|---|---|
| Every gap individually re-read and adjudicated | 14/14 carry a `phase36Decision` with evidence and remaining work |
| Every acquired file checksummed | 8/8 Zenodo files verified against the publisher's MD5; 12/12 IoT4Lettuce members carry SHA-256; 56/56 POWER and NEX objects carry SHA-256 |
| Every unit conversion declared | `UNIT_CONVERSIONS` in `process_lysimeter_evidence.py`; asserted units in both POWER and NEX importers |
| Every model artefact unchanged | hash-checked in `phase36_model_reevaluation.py`, `artifactUnchanged: true` for all 7 |
| Licence verified before use | 5/5 new datasets carry `licenseEvidence: verified` in the catalogue |
| No fabricated record | no dataset is counted unless downloaded and checksummed; the one partial acquisition states its partiality in its own manifest |

## 15. Documentation

| Document | Status |
|---|---|
| `docs/FINAL_SCIENTIFIC_DATA_ACQUISITION_REPORT.md` | this file |
| `docs/DATASET_GAP_MATRIX.md` | regenerated, 14 gaps, new status section |
| `data/research/DATASET_CATALOG.md` | regenerated, 34 datasets, 10 class A |
| `data/research/dataset_gap_matrix.json` | the adjudication itself |
| `data/research/dataset_catalog.json` | five new entries, NEX promoted D → A |
| `ml/evaluation/phase36_model_reevaluation.json` | per-model outcome |
| `data/research/phase36/*.json` | four analysis artefacts |
| `data/metadata/*_manifest.json` | five acquisition manifests and one processing manifest |

## 16. What this phase did not achieve, stated plainly

- **No lettuce or mizuna evapotranspiration was measured.** The lysimeter crop is a rotation; the
  eddy-covariance sites are grassland.
- **No CEA substrate water series exists in the record.** Field soil at four depths is not a
  substrate, and gap 5 stays open for that reason.
- **No LED spectrum biological-response dataset was acquired.**
- **No lettuce model could be scored** on the new independent campaign, because the campaign lies
  outside the models' declared domains in three separate fields.
- **The climate projection is one model.** No ensemble, no uncertainty range.
- **The Ky estimate is conditional**, because the water-use axis is a design variable.
- **The visual-regression gate fails in this environment** (font metrics), on a page that
  renders none of the changed data. It was not refreshed to make it green.

Six of the fourteen gaps remain open or partial for reasons that are about the state of the world,
not about effort: the data does not exist openly, and the product's claims are correspondingly
narrower.

---

## 17. Merge and push

Recorded after the fact in §20.

## 18. Working tree

Recorded after the fact in §20.

## 19. Render and production database

**Render was not touched.** No deployment was triggered, no service, environment variable, secret,
plan, worker, region or infrastructure setting was changed. The platform was used only as a
read-only target in the preceding live-verification task; nothing in this phase contacted
`api.render.com` or the running services.

**The production PostgreSQL database was not touched.** No migration, seed, reset, delete or write
was issued against it. The only database used in this phase is a throwaway cluster initialised at
`/var/tmp/pgdata36` on port 55436 for the test suite, with a randomly chosen local password and a
database named `spaceagrisim_test`. It was created for this session and is not persisted.

## 20. Delivery record

| | |
|---|---|
| Branch | `final/scientific-data-completion` |
| Merge | fast-forward into `main` (no conflicts, no rewrite) |
| Push | `git push origin main` |
| Remote `HEAD` after push | verified with `git ls-remote origin refs/heads/main` |
| Working tree | clean; `docs/FINAL_LIVE_PRODUCTION_VERIFICATION.md` deliberately left untracked and unpushed, as it belongs to the preceding task |

## 21. Summary

Five datasets were acquired and integrated, every byte checksummed, with the units read from the
provider rather than assumed — which is how the MJ/hr and kelvin bugs were found before they became
results. Two gaps closed on data, four partially, and six remain open with the reason recorded.

The most useful result is not a closure. It is that the ET0 formulation now has an absolute check
against measured latent heat (r = 0.971) and the ET0 level an absolute anchor (implied Kc 0.958),
and that the lettuce models could not be scored on the one independent lettuce campaign the project
holds because the campaign is outside their declared domain. Both of those are stated in the
artefacts, not just in this report.
