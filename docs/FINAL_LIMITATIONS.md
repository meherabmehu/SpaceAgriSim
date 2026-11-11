# Final limitations

Everything a reader could reasonably think is finished and is not. Each entry says what is missing,
what would be needed to close it, and what the product does today so that a user is not misled in the
meantime. None of these was downgraded, relabelled or moved to "fixed" in this pass.

## 1. Scientific limits

### 1.1 One decision-grade model, and it is narrow

`mizuna-microbial-relative-load-v2` predicts a **within-campaign z-score of log₁₀ CFU/g**, using a
campaign that supplies its own baseline samples. It does not predict an absolute microbial load, it
does not transfer to a new campaign without that campaign's baselines, and it is calibrated on two
campaigns (VEG-04A and VEG-04B), which is a sample of two.

*Missing to close:* three or more campaigns, ideally from a second programme, with baselines recorded
by the same protocol.

### 1.2 The lettuce regressions fail their independent checks

`lettuce-earth-growth-v1` and `-v2` cover 0 of 6 independent treatment means; `-v3` misses its
pre-registered accuracy criterion (41.59 % MAPE against 30 %) while covering 6 of 6 means. They remain
served, with the failure on the panel, in the API response and on the card.

*Missing to close:* an independent lettuce campaign — outside WUR/PeerJ/Touliatos — with per-plant
harvest mass, PPFD, DLI, air and root-zone temperature. Until then the intervals can be shown to fail
and cannot be recalibrated.

### 1.3 No independent check for three models

`radiation-quality-osd46-v1`, `radiation-exposure-osd46-v1` and `tomato-flight-response-v1` have
within-study validation only. They answer a classification question about experimental context, which
is what their measurement sets support, and no surface presents that as external validation.

*Missing to close:* a held-out experiment from a different programme for each.

### 1.4 No measured reference ET or crop water use in a controlled environment

The water balance has no independent check. The ET0 emulator was withdrawn rather than tuned, and the
panel says the balance is a model result.

*Missing to close:* a lysimeter or gravimetric water-use series with concurrent radiation, temperature,
humidity and wind, in a controlled environment.

### 1.5 No substrate-moisture or irrigation time series for a CEA crop

The closest public data is open-field drip irrigation, which cannot validate a controlled-environment
balance without pooling incompatible systems — which is not allowed here.

### 1.6 No LED spectral response surface

Papers with treatment means exist (and are transcribed as citations, never as data). A machine-readable
per-plant table against spectral composition, PPFD and DLI does not exist in what was searched, so the
spectrum input remains a design qualifier and not a validated response.

Note the additional constraint on the one spectrum study that *is* in the repository: its T3 regime
changes spectrum and planting density at once, and its spectrum moves through the experiment in T2 and
T3, so it cannot support a continuous response surface even in principle.

### 1.7 No fractional-gravity growth data at all

The gravity input was removed rather than left as an unvalidated knob. OSD-480 (1.41 TB root
gravitomics/transcriptomics) and GLDS-251 (5-day root RNA-seq) do not measure edible biomass against
g-level, so neither closes this.

### 1.8 Two-campaign offsets are protocol-driven

VEG-04A and VEG-04B differ in species composition and in what was sampled (5 of 19 species shared in
one harvest, 9 of 40 in the other). The models treat campaign as a grouping factor; they do not claim
to explain the offset.

## 2. Engineering limits

### 2.1 The rate limiter is in-process

Correct only at `--workers 1`, which is why the worker count is configuration and not a knob. Raising it
without shared rate-limit storage would multiply every budget by the worker count. No change was made.

### 2.2 SQLite is the default local store; PostgreSQL is required for durability

The application detects a volatile SQLite path (`:memory:`, `/tmp`) and reports it to the operator
instead of pretending the data will persist. Production durability needs `SPACEAGRISIM_DATABASE_URL`
pointed at PostgreSQL; the suite runs green on 17.11.

### 2.3 No deployment was performed

The repository describes how to deploy and the configuration is unchanged, but nothing was deployed,
verified in a live environment, or observed under production traffic in this pass. Any statement about
production behaviour in this documentation is a statement about the code, not about a running service.

### 2.4 The bundle budget has 225 bytes of headroom

The initial request is 245 535 B against a 245 760 B ceiling. The next component that wants to join the
critical path has to be lazy or removed; there is no room to add one. The budget was not padded, and
`chunkSizeWarningLimit` was not raised.

### 2.5 Visual regression is a per-machine rasterisation comparison

Baselines are captured with a pinned Chromium through `captureElement()`, which rounds the clip at page
coordinates to remove sub-pixel jitter. Antialiasing and font availability still differ between
machines, which is why the gate allows 2 % of pixels under a per-channel threshold of 16 rather than
demanding byte equality. It catches layout, palette and content changes, not a one-pixel font hinting
difference.

### 2.6 Tests cannot prove the absence of a defect

The suites cover what someone thought to assert. The specific gaps this pass knows about are in
`docs/FINAL_AUDIT_FINDINGS.md` §7 (reviewed and deliberately unchanged) and in §5 of the security review
(no penetration test; `pip-audit` cannot detect a compromised release with no advisory yet).

## 3. Documentation limits

* Phase documents (`PHASE29_*`, `PHASE30_*`, …) describe the repository **at the time of that phase** and
  were not rewritten. Where a later phase changed a fact, the later document says so — for example the
  `Update (Phase 35)` paragraph in `docs/PHASE31_REMOVED_MODELS.md`.
* Model cards are generated from evaluation artifacts. A card is exactly as good as the file it is
  derived from; the `--check` gates guarantee they agree, not that the evaluation was ideal.
* No document in this repository presents a paper, abstract, registration or model output as an
  acquired dataset, and none should be read as doing so.
