# Final scientific evidence report

The repository's scientific position, in one place, as of this delivery. Nothing in this pass changed
a verdict, trained a model, or acquired a dataset; what it did was make the evidence gates run in CI
so that the position cannot drift from the artifacts without the build failing.

## 1. Verdict per model

Derived by `ml/research/phase35_evidence_verdicts.py` from the committed evaluation files and cards;
`--check` fails when a card and the evidence disagree.

| model | independent check | measured | verdict | decision grade |
|---|---|---|---|---|
| `mizuna-microbial-relative-load-v2` | campaign-held-out R², permutation, pooled coverage | 0.444 (VEG-04A) / 0.373 (VEG-04B), p = 0.0 both, coverage 110/123 = 0.8943 against nominal 0.90 | passes | **yes** |
| `lettuce-earth-growth-v1` | cross-campaign interval coverage | 0 of 6 treatment means covered; ratio median 3.655 (1.905–5.493) | fails | no |
| `lettuce-earth-growth-v2` | cross-campaign interval coverage | 0 of 6; ratio median 3.212 (1.674–5.375) | fails | no |
| `lettuce-earth-growth-v3` | Touliatos 2016 holdout + coverage | 41.59 % MAPE against a pre-declared 30 %; coverage 6 of 6 | fails | no |
| `radiation-quality-osd46-v1` | none | within-study balanced accuracy only | no independent check | no |
| `radiation-exposure-osd46-v1` | none | within-study balanced accuracy only | no independent check | no |
| `tomato-flight-response-v1` | none | out-of-fold 0.9167 on 36 samples / 21 plants, one experiment | no independent check | no |
| `mizuna-harvest-v1` | campaign holdout | R² −0.333 against a baseline of −0.138 | withdrawn | no |
| `mizuna-microbial-load-v1` | campaign holdout | R² −0.55 / −0.58 | withdrawn | no |

Two facts about this table that are easy to lose and are therefore restated:

* **`lettuce-earth-growth-v3` fails while its intervals cover 6 of 6.** A pre-registered accuracy
  criterion was missed at 41.59 % against 30 %. Coverage is not accuracy, and a passing count does not
  outvote a failed criterion. Both numbers are on the card, in the API response and on the panel.
* **`mizuna-microbial-relative-load-v2` is decision grade only inside a campaign that supplies its own
  baseline samples.** It predicts a within-campaign z of log₁₀ CFU/g. It does not predict an absolute
  microbial load, and no surface offers it as one.

## 2. The single status change, recorded as a derivation

`mizuna-microbial-relative-load-v2`: `experimental` → `validated-exploratory`.

Its card already carried the rule that defines that status. Three of the four terms were true:
beats the baseline (pooled R² 0.509), positive held-out R² on every campaign (0.444 and 0.373), and
permutation p = 0.0 on both with 200 permutations. The fourth term was a boolean,
`intervalsEmpiricallyCalibrated`, which was `false` only because cross-campaign coverage had never
been measured. Phase 34 measured it — 110 of 123 samples covered, 0.8943 against a nominal 0.90,
inside the rule's own ±5-point tolerance — and the script scores the term from that measurement.

`docs/PHASE31_REMOVED_MODELS.md` still described the model as `experimental`; that sentence is
corrected in place, with the derivation and the file that supplies the number. "Validated" still never
means a calibrated probability, and the paragraph says so.

## 3. Datasets

**Acquired this pass: none.** No dataset was counted, catalogued or re-catalogued. The rule that a
dataset counts only when it is fully downloaded, licence-verified, SHA-256 checked and catalogued was
applied unchanged; nothing met it.

**Rejected, with reasons** (search results from the acquisition work; no candidate was reopened this
pass because none of the rejections depended on anything measured since):

| Candidate | Rejected because |
|---|---|
| Zenodo 20759414 (39.1 GB), Zenodo 8410252 (49.8 GB) | Volume: not retrievable or verifiable in this environment, so the SHA-256 could not be checked |
| Dryad CEA-adjacent records | Not controlled-environment agriculture; validating a CEA balance against open-field data is not a comparison |
| Zenodo 17794636 (Bannon 2025, CC-BY-4.0) | The sheets exist (`Destructive harvest` 201×34, `Overall fw`), but no temperature or PPFD columns, so it supports a cross-campaign yield comparison only — catalogued as a comparison source, never as a training set |
| Agronomy 12:1026, bioRxiv 2025.01.16.633207, JXB erag222, SCRI-OPTImia DLI report | Treatment-mean transcriptions from papers, not datasets. Transcribing a figure is not acquiring data, so none was used to fill an evidence gap |
| NASA OSDR OSD-480 (1.41 TB), GLDS-251 | Transcriptomic/root-gravitomics with no measured edible-biomass outcome at graded g-levels |
| Mendeley multi-sector irrigation telemetry, Figshare LED-spectrum supplements | Open-field or remote-sensing products; no controlled-environment water or spectrum series |

Retained from earlier phases and still the evidence base: Zenodo `10.5281/zenodo.17764612` (indoor
wheat, Exp_ID), Zenodo `10.5281/zenodo.14640245` (lettuce LUE, 53 means across 41 studies), OSDR
OSD-46 matrix (sha256 `f15c4179…efda27`), OSDR OSD-780 (VEG-04A/04B, CC0-1.0), Zenodo 20394352
(Phase 29 Greenlight light-quality study, CC BY 4.0, verified against the acquisition manifest before
every build).

## 4. What remains scientifically blocked

These are unchanged in severity, and writing them down does not close them:

1. **No measured reference ET or crop water use in a controlled environment** exists in this
   repository. The water balance therefore has no independent check; the ET0 emulator it replaced was
   withdrawn rather than tuned.
2. **No substrate-moisture / irrigation time series for a CEA crop** with the matching climate series.
   The closest public data is open-field drip irrigation, which cannot validate a CEA balance without
   pooling incompatible systems.
3. **No LED spectral response surface at plant level.** Papers with treatment means exist; a
   machine-readable per-plant table against spectral composition, PPFD and DLI does not, so the
   spectrum input is a design qualifier rather than a validated response.
4. **No fractional-gravity growth data at all.** The gravity input was removed rather than left as an
   unvalidated knob.
5. **No second independent lettuce campaign** outside WUR/PeerJ/Touliatos, so the lettuce intervals can
   be shown to fail but cannot be recalibrated on independent data.

## 5. Separation of measurement, prediction, derivation and setpoint

Every surface that shows a number labels its origin; the distinction is asserted in tests rather than
left to prose:

| Kind | Example | How it is labelled |
|---|---|---|
| measured | BPC chamber gas exchange; OSD-780 plate counts; Touliatos yields | `measured`, with the citation beside it |
| predicted | any model output | `prediction`, with the model id, its interval and its verdict |
| derived | per-area ratios, the leafy-green planning anchor, the demand-curve comparison | `derived`, with the formula in the payload |
| setpoint | every slider on the simulation lab | `setpoint` — inputs, never evidence |
| unavailable | a quantity with no evidence basis | rendered as unavailable, never as zero |

No fabricated dataset, metric, label, record, download, provenance entry or licence exists in the
repository. No training accuracy is presented as validation accuracy. No generated value fills an
evidence gap.

## 6. Gates that keep this true

`scripts/audit_models.py` (202 checks, 0 failed), `ml/research/phase35_evidence_verdicts.py --check`,
`ml/research/phase34_record_measurements.py --check`, `ml/training/phase32_provenance.py --check`,
`ml/research/build_feature_readiness.py --check`, `build_feature_coverage.py --check`,
`build_gap_matrix.py --check`. All nine now run in CI's `science` job, so a card that stops matching
its evidence fails the build rather than waiting for someone to notice.
