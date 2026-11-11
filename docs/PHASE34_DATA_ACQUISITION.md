# Phase 34 — data acquisition

The brief puts external dataset acquisition first, so this document records what was searched,
what was verified, what was rejected and why, before any claim about capability. The short
version: **no new dataset was added in Phase 34**, because the question the phase exists to answer
— does a served interval survive a change of campaign — turned out to be answerable from data
already in the repository, verified against the primary sources. Adding more megabytes would not
have made that measurement better, and a count of new files is not evidence.

## 1. What the phase needed

The five open audit findings were all of one shape:

| finding | what was missing |
|---|---|
| `tomato-flight-response-v1` / calibration | an out-of-fold probability measurement with intervals |
| `lettuce-earth-growth-v1` / `calibration-scope` | coverage measured against a campaign no fit ever saw |
| `lettuce-earth-growth-v2` / `calibration-scope` | as above |
| `mizuna-microbial-load-v1` / `calibration-scope` | as above |
| `mizuna-microbial-relative-load-v2` / `calibration-scope` | as above |

"Coverage within the fitted campaign is not coverage" needs **one independent campaign per
model**, with the same measured variable, the same unit and enough metadata to reproduce the
model's own inputs. It does not need volume; it needs independence.

## 2. Sources used, and how each was verified

### NASA OSDR OSD-780 — CC0-1.0, DOI `10.26030/s3hn-cj93`

* Study page: <https://osdr.nasa.gov/bio/repo/data/studies/OSD-780> (ALSDA LSDS-128).
* Verified by reading the study description and the assay list, not by searching for a name:
  OSD-780 contains **two flight campaigns, VEG-04A (June–July 2019, harvest 35 DAI) and VEG-04B
  (October–November 2019, harvests 29/43/58 DAI)**, each with 48-hour-offset ground controls.
* The measured variable is mizuna plate counts per tissue (leaf, pillow, swab), which is exactly
  the target `mizuna-microbial-relative-load-v2` predicts.
* Already in the repository as `data/processed/mizuna_microbial_load.csv` (356 rows,
  `experiment` ∈ {VEG04A: 184, VEG04B: 172}). Re-read from disk this phase; no re-download.
* Licence: CC0-1.0 per the study record; OSDR public-access terms at
  <https://science.nasa.gov/reference/osdr-help-terms-and-conditions/>.
* **Effect on the work:** this single study is the independent campaign for both mizuna models.
  The Phase 32 card text claimed "there is no second campaign in the repository"; that was wrong,
  and the campaign was already sitting in the file. Corrected in both cards.

### Wicharuck et al. 2024, PeerJ 12:e17085 — CC BY 4.0, `doi:10.7717/peerj.17085`

* Open-access full text (PMC11015828), read for the design: six treatment means, two cultivars ×
  three vertical levels, 28 days after transplant, air/root 27.5 °C, 12 h photoperiod, PPFD
  322 / 391 / 697 µmol m⁻² s⁻¹ (DLI 13.9 / 16.9 / 30.1), planting density 600 plants m⁻².
* This is a **measured independent campaign**, not a model paper: the six fresh-weight treatment
  means are reported values, transcribed by hand into
  `data/literature/external_lettuce_peerj17085.json` (committed in an earlier phase) with the
  study conditions the models need as inputs.
* **Effect on the work:** the independent campaign for all three lettuce models. No value was read
  off a figure and nothing was interpolated.

### Zenodo `10.5281/zenodo.17794636` — CC-BY-4.0 (Bannon, 2025-12-02)

* Record and `xlsx` fetched; SHA-256 recorded; licence verified as CC-BY-4.0.
* Contents inspected: a `Destructive harvest` sheet (201 × 34) and an `Overall fw` sheet. Both are
  yield/biomass tables. **No temperature, no PPFD, no photoperiod, no substrate moisture.**
* Verdict: **not usable** for any response model that takes environmental inputs, and not a
  drop-in for the PeerJ comparison either (different cultivar set, different reporting basis). It
  would have been a fourth unconnected yield table. Recorded and rejected rather than acquired to
  raise a count.

### Rejected with reasons

| source | what it is | why not acquired |
|---|---|---|
| Zenodo `10.5281/zenodo.20759414` | 39.1 GB record | larger than the sandbox can verify end to end; a partial download cannot be checksummed |
| Zenodo `10.5281/zenodo.8410252` | 49.8 GB record | as above |
| Dryad records screened | plant physiology, non-CEA | no controlled-environment crop water use or LED response; wrong experimental unit for these models |
| `doi:10.3390/agronomy12051026` | romaine DLI trial, DLI 9.2–17.3, FW 215.0 vs 353.1 g | a paper with reported means, not a dataset. Transcribing two means is not acquisition, and two points cannot support a response surface |
| `biorxiv 2025.01.16.633207` | preprint | not peer-reviewed and no supplementary table with the measured series |
| `jxb erag222` | journal article | no downloadable measurement table |
| SCRI-OPTIMIA DLI report PDF | extension report | treatment means in figures; reading numbers off a plot is not acquisition |
| OSDR registration/metadata records | study registrations | a registration is not a measurement table |

The rule applied throughout: **a paper, abstract, registration or metadata record is not an
acquired dataset**, and a failed source is documented rather than replaced by a plausible-looking
number. Where no dataset existed, the phase shipped a measurement over data that does exist
instead of a new model over data that does not.

## 3. Datasets retained from earlier phases that this phase's results depend on

| dataset | identifier | licence | used for |
|---|---|---|---|
| OSD-780 mizuna plate counts | `10.26030/s3hn-cj93` | CC0-1.0 | mizuna cross-campaign conformal |
| PeerJ 2024 lettuce treatment means | `10.7717/peerj.17085` | CC BY 4.0 | lettuce cross-campaign coverage |
| OSD-767 tomato expression | OSDR public access | public access terms | out-of-fold probability calibration |
| WUR lettuce / four experiments | `10.4121/5a7472f0-8a67-4ec0-84c9-9d032990d654.v1` (CC-BY-4.0) | CC-BY-4.0 | the fitted models under test |
| OSD-46 Arabidopsis microarray | OSD-46, sha256 `f15c4179…efda27` | public access terms | not touched this phase |

## 4. Integrity of what is committed

* Every number in `ml/evaluation/phase34_*.json` is produced by a committed script
  (`ml/research/phase34_*.py`) from committed inputs; no value is typed in by hand.
* Transcription files under `data/literature/` carry their publisher, URL, licence and n of the
  source, and the models' own input conversions (DLI, per-area density) are applied in the script,
  not in the transcription.
* The OSD-46 matrix keeps its recorded SHA-256; OSD-780 and the PeerJ file are already under
  version control with their provenance in
  `ml/training/phase32_provenance.py`, which still verifies 9/9 artifacts.

## 5. What this phase did not do

* It did not acquire a dataset to increase a count.
* It did not pool the PeerJ greenhouse means with the WUR plant-factory rows; they are used as an
  independent check, never as training data.
* It did not fill a missing measurement with a modelled value.
* It did not treat two campaigns as a sample of campaigns: two campaigns bound the size of a
  campaign offset, they do not estimate its distribution.
