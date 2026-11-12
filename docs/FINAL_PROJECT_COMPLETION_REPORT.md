# Final project completion report

SpaceAgriSim — the final scientific and engineering completion pass.

Every number below was produced on this branch by the command printed beside it, during this pass.
Where a result could not be measured, this report says so instead of estimating it. Where a gap
could not be closed because the evidence does not exist publicly, the gap is left open and the
search that failed to find it is recorded.

---

## 1. Repository state

| | |
|---|---|
| Repository | `github.com/meherabmehu/SpaceAgriSim` |
| Starting commit | `429097c` — the branch point, equal to `origin/main` at the start of this pass |
| Branch | `final/project-completion`, created off that commit |
| Commits on the branch | 7 (six before this report, one carrying it) |
| Force-push / history rewrite / protection bypass | none, at any point |
| Merge strategy | fast-forward only; no merge commit, no conflict resolution |
| Render | **not touched** — no deploy, no trigger, no service, environment, secret or plan change |
| Production PostgreSQL | **not touched** — no migration, reset, seed, delete or write |
| Test databases | isolated local instances only (`sqlite:///tmp/qa37.db` and a local PostgreSQL 17 cluster on port 55437) |

The branch tip before this report's own commit:

```
$ git rev-parse HEAD
a6553aaea81525812b4cbac7de0dd99180ae9634
$ git log --oneline 429097c..HEAD
a6553aa Serve this phase's evidence on the surface that already exists
a465dc9 Audit every served model against the new evidence without promoting any
544b117 Adjudicate the gap matrix against the evidence actually acquired
32f0068 Acquire two spectrum and nutrient datasets and analyse them
98c99e1 Replace the eighteen baselines with the Inter-rendered captures
be64e67 Bundle Inter instead of merely asking for it
```

This report is the seventh commit; it cannot contain its own SHA, and it does not pretend to. The
merge and push that follow it are recorded in the delivery message, with `git ls-remote` output, not
in this file.

### 1.1 A note on how this pass started

The workspace lost its `.git` directory between two working sessions: the sandbox that runs the
agent was reset, taking installed packages and the repository metadata with it while leaving the
working files intact. The repository was restored by cloning `origin` and moving the restored
`.git` back over the surviving tree, and the working tree was reconciled file by file against that
clone. Two consequences are worth recording rather than hiding:

* the eighteen visual baselines had been replaced by their committed copies during that
  reconciliation, so they were re-captured from the deterministic pipeline and re-verified
  (§8), not restored from a backup;
* `docs/FINAL_PROJECT_COMPLETION_REPORT.md` previously held the report of an unrelated earlier
  audit pass. That document is preserved at
  [docs/archive/FINAL_PROJECT_COMPLETION_REPORT_audit_pass.md](archive/FINAL_PROJECT_COMPLETION_REPORT_audit_pass.md)
  rather than deleted, and this file now holds the report the completion brief asks for.

---

## 2. The fourteen recorded gaps, before and after

Status is the token on each entry of `data/research/dataset_gap_matrix.json`, which is the source of
truth; the table below is generated from it by
`python3 ml/research/build_gap_matrix.py`.

| # | Gap | Before this pass | After this pass |
|---|---|---|---|
| 1 | `measured-eta` | PARTIALLY CLOSED | PARTIALLY CLOSED |
| 2 | `independent-et0` | PARTIALLY CLOSED | PARTIALLY CLOSED |
| 3 | `fractional-gravity` | CLOSED (capability removed) | CLOSED (unchanged) |
| 4 | `led-spectrum-response` | **OPEN** | **CLOSED** |
| 5 | `substrate-water` | OPEN | OPEN |
| 6 | `sub-daily-weather` | CLOSED | CLOSED (unchanged) |
| 7 | `cultivar-metadata` | PARTIALLY CLOSED | PARTIALLY CLOSED |
| 8 | `imagery` | OPEN | OPEN |
| 9 | `yield-labels` | CLOSED (capability removed) | CLOSED (unchanged) |
| 10 | `mission-energy` | OPEN | OPEN |
| 11 | `nutrient-balance` | **OPEN** | **PARTIALLY CLOSED** |
| 12 | `long-run-climate` | CLOSED | CLOSED (unchanged) |
| 13 | `crop-water-response-ky` | PARTIALLY CLOSED | PARTIALLY CLOSED |
| 14 | `prediction-intervals-independent-coverage` | OPEN | OPEN |

| Count | Before | After |
|---|---|---|
| Closed, by data | 2 | **3** |
| Closed, by withdrawing a capability | 2 | 2 |
| Partially closed | 4 | **5** |
| Open | 6 | **4** |
| Total | 14 | 14 |

The two kinds of closure are kept apart deliberately. A gap closed by finding a measurement and a
gap closed by removing the feature that needed one are not the same result, and a single "closed"
column would report progress the product does not have.

### 2.1 Why `led-spectrum-response` closed

The gap asked for a spectrum-resolved biological response — a trial in which light *quality*
changes while light *quantity* is held fixed, because otherwise a yield difference is
indistinguishable from a difference in photons delivered. `10.5281/zenodo.20394352` is that trial:
four spectra, every arm targeted at 200 µmol m⁻² s⁻¹ and the same 16/8 photoperiod, 252
destructively harvested Red Batavia plants.

### 2.2 Why `nutrient-balance` is only partially closed

The gap has three requirements: measured ion concentrations, the EC response, and an uptake rate in
mass per plant per day. The first two are now met by measurement across a real 28-day cycle. The
third is not derivable from the deposit: an uptake rate needs each sample paired to a dosing event,
and the deposit's Pre/Post labels are not self-consistent — the Treatment 1 sheet labels two samples
on 3 March both "Pre dose", then places a "Post dose" on a 10 March column followed by another "Pre
dose". No pH is deposited at all. `uptakeRate` is therefore published as `null`, with the reason and
the artefact that would close it recorded beside it.

### 2.3 Why the four remaining gaps stayed open

Each is recorded with its repository, query and rejection reasons in
`data/metadata/phase37_search_log.json`; the summary is §3.2. In one line each:

* **`substrate-water`** — no open dataset measures water content *inside a CEA substrate* together
  with an irrigation schedule and a drainage fraction. Field-soil series exist and are already
  catalogued as adjacent evidence; substituting them would repeat exactly the error the gap was
  held open to avoid.
* **`imagery`** — the requirement is imagery from the platform's own camera geometry, and the
  platform has no imaging pipeline. No external dataset can satisfy a self-referential requirement.
* **`mission-energy`** — the one real candidate has no power sensor (§3.3).
* **`prediction-intervals-independent-coverage`** — coverage needs independent observations
  *inside the model's declared domain*. Both newly acquired datasets fall outside it.

---

## 3. Searches, and what was accepted or rejected

### 3.1 Repositories queried

Zenodo, NASA OSDR, Dryad, Figshare and PANGAEA, with 19 distinct queries recorded in
`data/metadata/phase37_search_log.json`. That file is generated alongside the acquisition manifest
and is asserted by `backend/tests/test_phase37_acquisition.py::test_the_search_log_names_a_repository_and_a_query_for_what_it_looked_for`.

### 3.2 Accepted

| Identifier | What it is | Licence | Decision |
|---|---|---|---|
| `10.5281/zenodo.20394352` | Hydroponic lettuce under four spectra at constant PPFD, 252 destructively harvested plants | CC BY 4.0 | accepted, closes `led-spectrum-response` |
| `10.5281/zenodo.17794636` | Eight ions plus EC, three systems × three regimes, 28-day cycle, 191/194 harvested plants | CC BY 4.0 | accepted, moves `nutrient-balance` to partially closed |

### 3.3 Rejected, with the reason

| Identifier | Why it was rejected |
|---|---|
| `10.5281/zenodo.18804397` | **The same experiment deposited twice.** All five shared sheets are cell-for-cell identical to `17794636`; counting it would turn one trial into two pieces of evidence. Downloaded and compared precisely so the duplicate could be *demonstrated* rather than assumed. |
| `10.5281/zenodo.11485183` (EDEN ISS 2020 telemetry) | A full year of 5-minute telemetry from a real space-analogue greenhouse — and **no power, current, voltage or energy channel of any kind**. Its unit table lists 59 temperature, 11 pressure, 4 CO₂, 4 RH, 4 EC, 4 pH, 3 PAR, 3 valve, 2 level, 2 volume and 1 VPD sensor. A gap defined as "power draw per fixture, thermal load and resupply mass" cannot be answered from it. |
| Figshare `34671594` | Bell pepper, and the record is a publication rather than a measurement table. |
| Figshare `25976644`, `14051459`, `14051462` | Supplementary data sheets, rendered figures and table images from papers. A published figure is not a dataset. |
| NASA OSDR `OSD-655`, `OSD-780` | Already integrated in earlier phases; they add nothing to the gaps still open. |

The EDEN ISS archive was 260 MB unpacked and answered nothing, so it is not retained: its published
MD5 is kept in the manifest so the rejection stays reproducible byte for byte, and the payload is
gone. That decision is asserted by
`test_the_rejected_payload_is_not_retained_but_its_checksum_is`.

---

## 4. New data

Both files were downloaded through the Zenodo API, verified against the publisher's own MD5, and
catalogued with their SHA-256. Sizes are bytes on disk.

| Item | Value |
|---|---|
| Record | `10.5281/zenodo.20394352` — "Optimising Spectral Composition in Hydroponic Lettuce Cultivation: The Role of Green Light, Open Data" |
| File | `green_light_lettuce_open_data (1).xlsx`, stored as `data/raw/zenodo_20394352/green_light_lettuce_open_data_1_.xlsx` |
| Size / checksums | 94 162 B · MD5 `bb6ca334ca7e223089dc6c5faf253444` (matches publisher) · SHA-256 `cb79481841d520cdf741dff2a0857127817284a068fcc6f809cee8039f3b6f4c` |
| Licence | CC BY 4.0, verified on the record |
| Contents | 4 treatment arms; 252 destructively harvested plants across 7 measured variates; MultispeQ fluorescence on 165 leaf measurements at 28 and 35 DAS; post-harvest pigment and antioxidant assays, n = 24 per arm |

| Item | Value |
|---|---|
| Record | `10.5281/zenodo.17794636` — "Raw data: Temporal variation of nutrient ratios within hydroponic nutrient solutions" |
| File | `Raw data Dosing Experiment.xlsx`, stored as `data/raw/zenodo_17794636/Raw_data_Dosing_Experiment.xlsx` |
| Size / checksums | 52 889 B · MD5 `b59a320899a60d158019a2db23d492db` (matches publisher) · SHA-256 `da7ce5d7da119706a197bcb71809f49965702bc4fcd03a3135cdf729e8d01165` |
| Licence | CC BY 4.0, verified on the record |
| Contents | 8 ions + EC sampled repeatedly over a 28-day cycle; 3 independent nutrient systems × 3 regimes; 385 destructively harvested plants; 70 L per solution change; **no pH** |

The duplicate deposit `10.5281/zenodo.18804397` (55 099 B, MD5 `4aacaa7bb912bae5b9473178b305ef8b`)
is retained on disk only because the comparison is the evidence that it is a duplicate. It is
recorded in the manifest as `role: duplicate-check`, `countsAsSecondCampaign: false`, and it is
**not** a catalogue entry. The catalogue therefore moves 34 → 36, not 37.

Acquisition is reproducible:

```
python3 ml/research/acquire_spectrum_light.py    # 3 records, 3 files, 0 failures, all checksums verified
```

---

## 5. Findings, with n and uncertainty

### 5.1 Green light does not cost yield at constant photon supply

Fresh mass per plant, measured destructively at 35 days after sowing (`n` = plants):

| Arm | Spectrum | n | Mean (g) | SD (g) |
|---|---|---|---|---|
| Control | red-blue, ≈5.08 % green | 60 | 44.39 | 20.10 |
| T1 | fixed 24 % green | 48 | 48.50 | 13.72 |
| T2 | incremental 16 → 24 → 32 % green | 64 | 52.24 | 13.14 |
| T3 | T2 spectrum at 1.25× density | 80 | 46.31 | 13.57 |

T3 varies planting density as well as spectrum, so its difference cannot be attributed to colour
and it is excluded from every claim — enforced by test, not by care.

Derived contrasts, permutation test with 20 000 permutations and bootstrap interval with 4 000
resamples (seed 20261112):

| Contrast | Δ fresh mass | 95 % interval | p | Relative |
|---|---|---|---|---|
| Control → T1 (fixed 24 %) | +4.11 g | −2.15 to +10.52 | 0.229 | +9.3 % |
| Control → T2 (incremental) | +7.86 g | +2.07 to +13.72 | **0.011** | **+17.7 %** |
| T1 → T2 | +3.74 g | −1.13 to +8.76 | 0.144 | +7.7 % |

This is the finding that matters for the simulator: the platform's radiation-quality treatment has
always encoded the assumption that green photons are largely wasted. At a fixed photon budget that
assumption is **not supported** — no arm lost yield against the red-blue control, and the
incremental-green arm gained fresh mass with an interval that excludes zero.

What it does not show: one cultivar, one facility, one season, one destructive endpoint. The
deposit reports a *green percentage*, not a spectral power distribution, so the effect cannot be
attributed to a wavelength band.

### 5.2 Nutrient solution chemistry over a full cycle

Measured, Treatment 1 (the regime closest to the platform's default recipe), 15 sampling
intervals over the cycle, all three systems:

| Ion | Median change (mg L⁻¹ d⁻¹) | Total change over cycle (mg L⁻¹) |
|---|---|---|
| Nitrate-N | −0.71 | −47.7 |
| Phosphate | −0.16 | −7.67 |
| Potassium | −0.70 | −61.1 |
| Calcium | −0.83 | −59.7 |
| Magnesium | −0.24 | −20.7 |
| Sulphate | −0.56 | −50.7 |
| Iron | −0.05 | −2.67 |
| Manganese | −0.006 | −0.37 |
| EC | 0.00 | −0.6 |

Harvest, measured, endpoint = the yield-component fresh weight the deposit's own economic analysis
reports:

| Regime | n | Mean FW (g) | SD | Dry-matter fraction |
|---|---|---|---|---|
| Treatment 1 | 191 | 57.67 | 16.15 | 0.049 |
| Treatment 2 | 194 | 46.87 | 10.80 | 0.050 |

Two measurement traps were found and are now regression-tested, because both had already produced
wrong numbers during this pass:

1. **The harvest sheet is three 9-column system blocks side by side.** A single-column scan reads
   64 plants for Treatment 1 instead of 191 and nothing at all for Treatment 2.
2. **The workbook carries both an "Overall fw" and a "Yield component fw" column, differing by about
   a quarter.** Using the overall column gives 73.95 g against the study's own 57.49 g. The
   yield-component column reconciles to 57.67 g.

**No uptake rate is published.** `uptakeRate` is `null` and `whatIsNotDerivable` states why. A
number in that field would have been an assumption dressed as a measurement.

---

## 6. The seven served models

Read from `ml/evaluation/phase37_model_evidence.json`, generated by
`python3 ml/research/audit_models_phase37.py`. The served set is imported from the application, not
hard-coded, so a model withdrawn tomorrow cannot keep appearing here as served.

| Model | Verdict before | Verdict after | Decision-grade | Tested by this phase's data? |
|---|---|---|---|---|
| `lettuce-earth-growth-v1` | FAILS-INDEPENDENT-CHECK | FAILS-INDEPENDENT-CHECK | no | no |
| `lettuce-earth-growth-v2` | FAILS-INDEPENDENT-CHECK | FAILS-INDEPENDENT-CHECK | no | no |
| `lettuce-earth-growth-v3` | FAILS-INDEPENDENT-CHECK | FAILS-INDEPENDENT-CHECK | no | no |
| `mizuna-microbial-relative-load-v2` | PASS decision-grade | **PASS decision-grade** | **yes** | no |
| `radiation-exposure-osd46-v1` | NO-INDEPENDENT-CHECK | NO-INDEPENDENT-CHECK | no | no |
| `radiation-quality-osd46-v1` | NO-INDEPENDENT-CHECK | NO-INDEPENDENT-CHECK | no | no |
| `tomato-flight-response-v1` | NO-INDEPENDENT-CHECK | NO-INDEPENDENT-CHECK | no | no |

**Nothing was promoted, retrained or relabelled.** All seven artefacts still hash to their registry
entry (7/7); three retained-but-withdrawn artefacts remain on disk untouched.

*Why none could be tested.* The reason is recorded per model, and it is a property of the data, not
a judgement: the lettuce models require `rootTemperature` and a light measurement — the green-light
trial measures no temperature at all and its single destructive harvest at 35 DAS is outside the
declared 2–29-day domain, while the dosing trial measures no temperature and no light. The mizuna
model predicts from VEG-04 flight covariates that neither deposit contains. The transcriptomic
models consume a normalised expression vector, and neither deposit contains expression. A model that
could not be tested is reported as **not tested** — never as validated, and never as failed for want
of data it was never meant to see.

*Card completeness.* Three of seven cards are complete. The remaining four omit an embedded code
reference and a training-data hash; the reproduction script for each is resolved from the repository
and named in the audit rather than edited into artefacts whose checksums are published. Coverage:
domains declared 7/7, uncertainty statements 7/7, grouped (non-row-wise) splits 7/7, baselines 7/7,
reproduction scripts resolvable 7/7.

---

## 7. The eighteen visual comparisons

Cause, before any fix: the interface has always declared Inter first in its font stack and has never
shipped a font file, so every capture substituted whatever the host had. Two hosts, same page,
different pixels — the 5–13 % disagreement was a font substitution, and the proof is that the
magnitude tracks glyph coverage rather than layout.

The fix makes the typography a property of the repository: the four Inter weights bundled as a latin
subset under SIL OFL (108 KB) with the licence text, `font-display: block` so a capture cannot race
the fallback, and three Chromium flags (`--font-render-hinting=none`,
`--disable-font-subpixel-positioning`, `--disable-lcd-text`) so FreeType does not choose its strategy
from the host's font packages. The capture helper awaits `document.fonts.ready` in addition to its
data and layout waits.

| Capture | Differing before the fix | Differing against the new baseline |
|---|---|---|
| `mission-desktop.png` | 4.94 % | 0.000 % PASS |
| `mission-tablet.png` | canvas size changed | 0.000 % PASS |
| `mission-mobile.png` | canvas size changed | 0.000 % PASS |
| `predictions-desktop.png` | 10.27 % | 0.000 % PASS |
| `predictions-tablet.png` | 11.31 % | 0.000 % PASS |
| `predictions-mobile.png` | 10.88 % | 0.000 % PASS |
| `benchmarks-desktop.png` | 8.78 % | 0.000 % PASS |
| `benchmarks-tablet.png` | 12.22 % | 0.000 % PASS |
| `benchmarks-mobile.png` | 11.59 % | 0.000 % PASS |
| `radiation-desktop-radiation-quality-osd46-v1.png` | canvas size changed | 0.000 % PASS |
| `radiation-desktop-radiation-exposure-osd46-v1.png` | canvas size changed | 0.000 % PASS |
| `radiation-tablet-radiation-quality-osd46-v1.png` | canvas size changed | 0.000 % PASS |
| `radiation-tablet-radiation-exposure-osd46-v1.png` | canvas size changed | 0.000 % PASS |
| `radiation-mobile-radiation-quality-osd46-v1.png` | canvas size changed | 0.000 % PASS |
| `radiation-mobile-radiation-exposure-osd46-v1.png` | canvas size changed | 0.000 % PASS |
| `water-evidence-desktop.png` | canvas size changed | 0.000 % PASS |
| `water-evidence-tablet.png` | canvas size changed | 0.000 % PASS |
| `water-evidence-mobile.png` | canvas size changed | 0.000 % PASS |

Classification of the original mismatch, individually: **font substitution** for every capture. No
capture was classified as a layout regression, and none was dismissed as environmental without
evidence — the evidence being that the same page rendered on two different font hosts came out
byte-identical once a font was actually shipped, which rules out layout, viewport, DSF, animation
timing and responsive breakage as causes.

Two further facts, because they are the difference between a green gate and a meaningful one:

* the nine "canvas size changed" failures were the *fallback font* changing line height, not the
  layout moving: after the font was bundled the canvases returned to their recorded heights;
* seventeen of the eighteen captures compare byte-identical. `mission-mobile.png` carries exactly
  one pixel whose largest channel delta is 1 out of 255 — below the channel threshold of 16, so it
  is not counted as a changed pixel and the capture reports 0.000 %. It is recorded here rather
  than rounded away: the gate's claim is zero changed pixels at a stated threshold, not bitwise
  identity, and this report should not say more than the gate measured;
* the replacement was deliberate and recorded per image in
  `ml/evaluation/phase37_visual_baseline_migration.json`, with the previous images archived under
  `docs/screenshots/historical/phase37/`. The pixel budget (2 %), the channel threshold (16) and the
  dirty-baseline guard were **not** touched.

---

## 8. Gates, with exact commands and results

Run from the repository root at branch tip `a6553aa` unless stated. All were observed, none was
inferred.

| Gate | Command | Result |
|---|---|---|
| Backend, SQLite | `DATABASE_URL=sqlite:///tmp/qa37.db python3 -m pytest backend/tests -q -p no:randomly` | **1313 passed, 23 skipped, 0 failed** |
| Backend, PostgreSQL | `SPACEAGRISIM_TEST_POSTGRES_URL=postgresql+psycopg://…@127.0.0.1:55437/spaceagrisim_test DATABASE_URL=sqlite:///tmp/qa37.db python3 -m pytest backend/tests -q -p no:randomly` | **1336 passed, 0 skipped, 0 failed** |
| Frontend lint | `npm run lint` | pass, 0 errors |
| Frontend typecheck | `npm run typecheck` | pass |
| Frontend unit | `npm run test:unit` | **20 passed** (2 files) |
| Frontend build + budget | `npm run build:check` | pass — initial request 240 kB, within the 240 kB budget; no chunk over budget |
| Playwright, all routes × 3 viewports | `CI=1 npx playwright test` | **171 passed** in 4.9 min |
| Visual gate | `python3 scripts/visual_regression.py` | **18/18 PASS**, every capture 0.000 % |
| Model audit | `python3 scripts/audit_models.py` | **202 checks run, 0 failed** |
| Registry verification | `python3 scripts/verify_model_registry.py` | **62/62 checks passed** |
| Phase 37 model evidence | `python3 ml/research/audit_models_phase37.py` | 7 served, hashes 7/7, 0 promoted |
| Catalogue | `python3 ml/research/build_catalog.py --check` | up to date (36 datasets) |
| Gap matrix | `python3 ml/research/build_gap_matrix.py --check` | up to date (14 gaps) |
| Feature readiness | `python3 ml/research/build_feature_readiness.py --check` | up to date (12 features) |
| Feature coverage | `python3 ml/research/build_feature_coverage.py --check` | up to date (12 features) |
| Python dependency audit | `python3 -m pip_audit -r backend/requirements.txt` | no known vulnerabilities |
| Node dependency audit | `npm audit --omit=dev --audit-level=high` | 0 vulnerabilities |
| Accessibility | inside the Playwright run (`e2e/accessibility.spec.js`, `e2e/accessibility35.spec.js`) | 27 passed across three viewports |

### 8.1 Every skip, explained

**SQLite run — 23 skips, all one cause.** They are the PostgreSQL-only tests
(`test_postgresql_persistence.py`, `test_postgres_integration.py`,
`test_multi_worker_readiness.py` ×3, `test_phase22_backup_automation.py`) which require
`SPACEAGRISIM_TEST_POSTGRES_URL`; they skip with that exact message rather than failing quietly.
They are not left unexplained: the same suite was then run **against a real PostgreSQL 17.11
cluster and returned 0 skips**, listed in the row above.

**PostgreSQL run — 0 skips.** The one failure that appeared on the first attempt was in
`test_connection_failure_is_reported_without_leaking_credentials`, and the cause was the test
cluster, not the code: `initdb -A trust` accepts any password, so a deliberately wrong password did
not raise. The cluster was re-initialised with `scram-sha-256` for host connections and the test
passes. The test was not weakened — the environment was made faithful.

### 8.2 Tests added

26 new tests in `backend/tests/test_phase37_acquisition.py`, each encoding a way this pass's
conclusions could have been wrong and, in four cases, actually were:

* the three-block harvest sheet (191 plants read as 64);
* the duplicate deposit (`18804397` must not be a catalogue entry);
* the density-confound arm (no contrast may name T3);
* the yield-endpoint mismatch ("Yield component fw", not "Overall fw");
* the refusal to publish an uptake rate without a defensible pairing;
* the requirement that a closed gap points at evidence that exists on disk;
* the requirement that no model is promoted, retrained or threshold-moved.

No existing test was deleted, skipped or weakened. Four Phase 36 tests were **generalised**: they
asserted that the *Phase 36* decision block matched the status token, which stops being true the
moment a later phase adjudicates a gap. They now read the newest decision recorded for each gap and
assert it agrees with the token — a stronger check, since the old form would have had to be edited
or skipped the first time the matrix moved.

---

## 9. Limitations

Stated plainly, because the alternative is a report that reads like a release note.

1. **Four gaps remain open and this pass did not close them.** `substrate-water`, `imagery`,
   `mission-energy` and `prediction-intervals-independent-coverage`. For three of them the evidence
   does not exist publicly; for `imagery` the requirement is self-referential. The searches that
   failed are recorded query by query.
2. **`nutrient-balance` is only partially closed** and will stay that way until a dosing log with
   unambiguous pre/post pairing exists. No uptake rate is claimed.
3. **The spectrum result is one cultivar, one facility, one season, one endpoint.** It refutes a
   general assumption about green light; it does not calibrate a spectral response function, and
   the simulator does not gain a wavelength-resolved coefficient from it.
4. **Six of seven models are not decision-grade**, exactly as before this pass. Nothing here moved
   them, and the two datasets acquired could not test any of them without violating their own domain
   contracts.
5. **Four of seven model cards omit an embedded training-data hash.** The reproduction scripts are
   resolved and named, but the artefacts were not edited, because editing them would invalidate
   published checksums.
6. **The visual gate is a rasterisation gate, not a semantic one.** It proves the page did not
   change; it does not prove the page is right.
7. **The gap matrix's own counts are only as good as its entries.** They now recompute from the
   tokens rather than from a stored summary, which removes one class of drift, not all of them.

---

## 10. What was integrated into the product

Integration was confined to what the new evidence actually changes, and every existing contract was
left alone.

* `GET /api/acquisition-evidence` gained three additive blocks — `spectrumLight`, `nutrientSolution`
  and `modelEvidence` — plus `latestPhase`. Every existing key keeps its shape; the Phase 36 tests
  that assert response shapes still pass unmodified.
* The endpoint formerly read only `phase36Decision` and would have reported `led-spectrum-response`
  as closed while carrying no evidence for it, and would have gone on asserting that six gaps were
  open beside a count of four. It now serves the newest decision per gap with the phase that made
  it, and recomputes the interpretation sentence from the same entries the table is built from.
* The Evidence module renders the spectrum result: the four arms with measured mass, and the derived
  contrasts with their p-values and intervals. Numbers carry their label — measured, derived,
  predicted, unavailable.
* The nutrient-solution block is **served and labelled but not drawn**. A panel showing
  concentrations without the uptake rate the gap asked for would look like more than was
  established. That is a deliberate decision, not an oversight.
* No UI was added merely to display data nobody can act on, no route was removed, no contract was
  broken, and the frontend budget is unchanged at 240 kB.

---

## 11. Commits and push

Six commits before this report, one carrying it, all on `final/project-completion` off `429097c`:

```
be64e67  Bundle Inter instead of merely asking for it
98c99e1  Replace the eighteen baselines with the Inter-rendered captures
32f0068  Acquire two spectrum and nutrient datasets and analyse them
544b117  Adjudicate the gap matrix against the evidence actually acquired
a465dc9  Audit every served model against the new evidence without promoting any
a6553aa  Serve this phase's evidence on the surface that already exists
```

The branch was pushed and verified with `git ls-remote` before this report was written (the remote
answered `98c99e190e8bf43eff8b13de683dbea7caad7646` for the branch at that point). The merge into
`main` and the final push happen after this commit and are recorded in the delivery message with
the `ls-remote` output, not here — a file cannot contain the hash of the commit that contains it.

No force-push, no history rewrite, no branch-protection bypass.

---

## 12. Deployment boundary

**Render was not touched.** No deploy, no deploy hook, no trigger, no service setting, no
environment variable, no secret, no plan, no worker and no region was changed, and the Render API
token was never used.

**Production PostgreSQL was not touched.** No migration, reset, seed, delete or write was executed
against it. Every database operation in this pass ran against throwaway local instances:
`sqlite:///tmp/qa37.db` and a PostgreSQL 17.11 cluster under `/var/tmp/pgdata37` on port 55437.

**The new code is not live.** Nothing in this branch has been deployed. `spaceagrisim-web.onrender.com`
and `spaceagrisim-api.onrender.com` continue to serve whatever they served before this pass, and no
claim in this report should be read as a statement about what those services currently run.
