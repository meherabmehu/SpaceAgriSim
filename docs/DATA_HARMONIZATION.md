# Scientific Data Harmonization Rules — Phase 6

These rules are **enforced**, not aspirational. Each names the code or test that
enforces it. A dataset that violates a rule is excluded from training rather
than patched.

---

## H1 — Never merge quantities that are not the same measurement

A column name is not a measurement definition. Before any pooling, the actual
formula that produced each value must be recovered and shown to match.

**Worked example (violation found in Phase 6), OSD-655 `Total (g)`:**

| Arm | Verified formula | Underlying measurements |
|---|---|---|
| Flight | `mean(4 MMD replicate weighings) + crew consumption` | 4 replicate weighings of a subsample, plus a consumption estimate |
| Ground | `harvested leaf mass + broken-leaf mass` | complete harvest, no consumption |

Verified arithmetically: **8/8** flight rows and **6/6** ground rows reconstruct
exactly (≤0.05 g, allowing 2-dp rounding).

> Enforcement: `ml/analysis/audit_osd655_mass.py` asserts both reconstructions
> and fails the build if the arithmetic stops holding.
> Output: `docs/phase6/osd655_mass_audit`.

**Consequence:** the 14-row pooled mizuna table mixes two definitions. The
`flight` feature therefore partly encodes a protocol difference. The model is
labelled `baseline-only` and must never be presented as a like-for-like yield
comparison.

## H2 — Fresh mass ≠ dry mass; never convert by assumption

Fresh and dry biomass are different targets. `dry_matter_fraction` (0.05–0.06)
is a *modelling* parameter, never a measurement, and must not be used to
manufacture a dry-mass label from a fresh-mass measurement. No dry-mass model
is trained from fresh-mass data.

## H3 — Per-plant ≠ per-area; never convert without a measured area

OSD-655 records grams **per pillow**; the pillow's growing area is not published
in the acquired files. EDEN ISS records **kg/m²**. These were never converted
into each other. Where a conversion would be needed, the quantity is excluded.

**Enforcement:** `scripts/calibrate_simulation.py` compares kg/m² only against
kg/m² crop baselines, and records `normalisation` explicitly for every
comparison.

## H4 — Harvest mass ≠ standing biomass ≠ cumulative production

Three distinct quantities, kept in three distinct fields, in the simulation *and*
in the data tables. On a harvest day the crop is simultaneously at peak standing
biomass and cut; the engine exposes both cut-offs:

```
cumulative_biomass_g == harvested_through_previous_day_g + biomass_g   (always true)
post_harvest_standing_g == 0 on harvest days, else == biomass_g
```

**Enforcement:** `backend/tests/test_scientific_invariants.py::
test_mass_balance_identity_holds_every_day` and
`test_harvest_day_removes_standing_biomass`; plus 1,170 sweep checks in
`scripts/calibrate_simulation.py`.

## H5 — Water supplied ≠ water demand ≠ water recovered

| Quantity | What it is | Never treat as |
|---|---|---|
| irrigation **supplied** (OSD-655) | management input logged per event | transpiration, uptake or demand |
| **demand** (simulator) | what a healthy canopy wants | a measured value |
| **recovered** (simulator) | condensate returned at configured efficiency | a measured recovery |

No model predicts water demand: no NASA transpiration measurement exists in the
25 verified studies (see `docs/NASA_MEASUREMENT_INVENTORY.md` §4).

## H6 — Concentration ≠ flux

Cabin CO₂ concentration (ppm) is not CO₂ uptake. No measured CO₂-assimilation or
O₂-evolution table exists in the corpus, so the simulator's gas exchange remains
a transparent **carbon mass balance**, labelled as an estimate:

```
CO2_fixed = (edible_yield / harvest_index) × dry_matter_fraction
            × CARBON_FRACTION_OF_DRY_MASS × 44/12
O2_released = CO2_fixed × 32/44
```

**Enforcement:** `test_carbon_mass_balance_from_dry_matter` (whole-plant basis)
and `test_oxygen_carbon_stoichiometry`.

## H7 — Assay subsample mass is not biomass

OSD-780 `fresh_weight_gram` (5–9 g) is the mass of tissue taken *for the plate
assay*. It is **forbidden** as a biomass label or feature. It is used only as a
covariate in the microbial model, where it legitimately conditions the CFU/g
denominator.

**Enforcement:** stated in `docs/NASA_MEASUREMENT_INVENTORY.md` §2.1,
`data/metadata/osd780_quality_report` (`unitsNote`), and the model artifact's
`limitations[2]`.

## H8 — Molecular expression is not a plant phenotype

RNA-seq/microarray expression is never used as a biomass, yield, health or
stress-severity label. OSD-767 is used only for the *molecular context*
classifier, whose label is the recorded flight/ground condition.

**Enforcement:** only `tomato-flight-response-v1` consumes expression data, and
its `target` is `"recorded spaceflight experimental context"`.

## H9 — Nominal `flight` ≠ gravity treatment

A flight/ground label confounds microgravity with cabin environment, launch and
return stress, hardware, crew handling and sampling protocol. It is never
converted into a continuous lunar or Martian growth response. No gravity-response
model is trained.

**Enforcement:** `mizuna-microbial-load-v1.limitations[5]` states causality is
not established; the simulator's gravity factor remains a documented
**assumption**.

## H10 — Group awareness: biological replicate is the unit

Repeated measurements from one biological unit must never be split across
train/test folds. Group keys actually used:

| Model | Group key | Rationale |
|---|---|---|
| `mizuna-harvest-v1` | `pillow-N` | one pillow is one growth unit |
| `tomato-flight-response-v1` | `flight-N` / `ground-N` | root + leaf of the same plant |
| `lettuce-earth-growth-v1` | `experiment` | whole-experiment holdout |
| `mizuna-microbial-load-v1` | `experiment-environment-pillow` | repeated swabs/harvests from one pillow |

**Enforcement:** every training script asserts
`set(groups[train]) & set(groups[test]) == emptyset` inside its CV loop.

## H11 — No fabricated sample inflation

Sample counts are the count of independent measured units, never rows after
exploding replicates. Where replicates exist they are grouped (H10), not
multiplied.

## H12 — Zero is not missing

A measured zero (e.g. `colony_count = 0`) is a real "no growth" result and is
retained (`log10(1+0)=0`). Missing values are excluded, never imputed with
central tendency. Irrigated `---` entries in OSD-655 are excluded.

## H13 — External data is labelled external

WUR/4TU lettuce data is **not NASA**. It is tagged
`"external scientific data (not NASA)"` in its artifact and kept strictly
separate from NASA-derived claims.

## H14 — Literature transcription is not a dataset

OSD-895 ships only a PDF. `eden_iss_2018_biomass_summary.csv` is a **manual
transcription** of a table from that paper, and every artifact that touches it
says so. It is never described as a machine-readable NASA dataset.

**Enforcement:** `data/metadata/dataset_manifest` and
`scripts/calibrate_simulation.py` (`sourceCaveat`).

## H15 — Calibration ≠ independent validation

A parameter fitted or checked against a dataset cannot then be "validated" on
that same dataset. Phase 6 therefore reports:

| Quantity | Evidence status |
|---|---|
| lettuce `harvest_biomass_g` | *plausibility-checked* against EDEN ISS (within measured range); not fitted |
| tomato, radish baselines | *flagged*; suggested values recorded but **not applied** |
| all gravity/radiation/light/temperature/humidity curve shapes | **assumptions** |
| `lettuce-earth-growth-v1` | validated by leave-one-*experiment*-out on WUR data; not by EDEN ISS |
