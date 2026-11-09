# Dataset gap analysis

## What is verified

The local NASA OSDR manifest registers 13 official studies and records source URLs, metadata, retrieval timestamps and file checksums. Twenty-eight small public files were acquired for schema inspection and preview; this is a catalogue/provenance layer, not a claim that every study is usable for crop production modelling.

## Gaps that prevent a calibrated space crop twin

| Needed for a calibrated decision model | Current evidence | Consequence |
| --- | --- | --- |
| Repeated plant-level yield/biomass endpoints | Mizuna has limited compatible endpoints; most records are molecular or other biology | No robust multi-crop yield calibration |
| Controlled environmental covariates | Incomplete or differently encoded across studies | Cannot estimate general PPFD, temperature, humidity or water effects from the catalogue |
| Independent mission/ground holdouts | Not available in the included small research tables | No claim of transportable operational accuracy |
| Matched partial-gravity/radiation experiments | Absent | Moon/Mars panels remain scenario assumptions, not validated predictions |
| Cultivar, density and harvest protocol alignment | Heterogeneous or unavailable | No safe conversion between fresh mass, edible yield and area-based production |

## Handling

The product exposes provenance, source links and uncertainty rather than filling these gaps with synthetic labels. The WUR lettuce dataset is separately labelled **external scientific data (not NASA)** and Earth-only. Future calibration requires a documented study protocol, sufficient raw measurements, grouped validation and an independent holdout before any predictive claim is promoted.

## Acquisition specification for the lettuce model

The external check against Wicharuck et al. 2024 (`GET /api/external-validation`) turned the gap
from a general statement into a list of things a usable dataset must contain. These are the
requirements a future acquisition has to meet before the model is retrained; they are written as
acceptance criteria so the same endpoint decides whether the gate was passed.

| Requirement | Why the failure demands it |
| --- | --- |
| One row per observation — cultivar, level or treatment, `daysAfterTransplant`, air temperature, **root-zone temperature**, PPFD — never a study average | The PeerJ study reports study averages across three light levels; scoring the model against those would have compared one PPFD with a mean over three. The model also takes root temperature, which that study does not report |
| At least two cultivars, labelled | The two cultivars in the PeerJ trial differ by 63 % in fresh weight — more than the light-level effect. The served model has no cultivar feature, so no recalibration can fit this |
| At least three light levels per cultivar, with per-level values, including one below ~350 µmol m⁻² s⁻¹ | The observed response is non-monotonic (highest at the middle level for one cultivar, the lower level for the other); a monotonic tree ensemble cannot represent a peak or a crossover |
| A time series, not only a harvest endpoint | The served model predicts mid-cycle mass from `daysAfterTransplant`; a single harvest point cannot show whether the growth curve is right or only the endpoint |
| Growing system, plant density, photoperiod, CO₂, water and nutrient regime recorded per trial | Without these the model cannot be told what it is being asked to predict, and per-area conversions stay impossible |
| Provenance pinned: DOI, licence, retrieval date and SHA-256 of the transcribed source | The PeerJ transcription carries all four; a dataset that cannot be pinned the same way should not enter the training set |

**Gate:** the model stays `trained-exploratory` and the failure stays on the benchmarks page until a
new artifact passes the external check with a stated domain that covers the sources used. A passing
in-domain cross-validation is not the gate — that is what failed to transfer.

## Gaps closed by search, and gaps that remain

A deep search of NASA sources on 2026-11-09 changed the status of two of the five rows above.
Both are now backed by measured numbers served at `GET /api/closed-loop`, transcribed into
`data/literature/nasa_air_and_water.json`.

| Gap | What was found | Status |
| --- | --- | --- |
| Ethylene / air quality | NASA CELSS Biomass Production Chamber: 20 m² stands reached **120 ppb (wheat), 60 ppb (soybean), 40–50 ppb (lettuce, potato)**; peak production **0.04–0.06 mL m⁻² d⁻¹ ≈ 0.8–1.1 nL g⁻¹ FW h⁻¹** (Wheeler et al. 1996, doi:10.1016/0273-1177(95)00877-H). Lettuce dose response: **25–50 % dry-weight loss at 120 nL L⁻¹, 1–25 % at 55 nL L⁻¹**, unaffected by temperature. | **Measured — served as a hazard screen.** Still not a growth term: no scrubbing, leakage or uptake kinetics were measured in a usable form, so no coefficient was invented. |
| Water loop | ISS ECLSS recovers **98 %** of the water brought aboard (93–94 % before the Brine Processor Assembly, 2023). NASA's own four-person, 900-day Mars example: **~12 t of water without recycling, ~250 kg of make-up at 98 %**. | **Measured — bounds the recycling control.** Anything above 98 % is not a demonstrated capability. |
| Radiation effects on crop yield at these dose rates | No crop-yield-measuring dataset at habitat-relevant chronic dose rates was recovered. The OSDR corpus is molecular. | **Open.** The simulator's radiation response stays a disclosed placeholder. |
| Yield versus gravity | No crop fresh-weight dataset across fractional gravity was recovered. The ISS fractional-g work (EMCS, Seedling Growth, OSD-346) is transcriptomic and morphometric; the published conclusions are that Mars gravity *may* not limit plant development and that microgravity effects on biomass are modest and mixed. | **Open.** No yield-versus-gravity coefficient is claimed. |
| Real regolith | NASA reports exist (lunar/Martian simulant trials, CI asteroid regolith dataset) with biomass reductions, but they are simulants, not returned regolith, and the trials are heterogeneous in substrate, fertilisation and cultivar. | **Open, on purpose.** No regolith term is modelled. |

The rule applied throughout: where a measurement exists it is transcribed and served with its DOI
and licence; where none exists the user-facing control is removed rather than given an invented
response curve.

Applied in this pass:

- **Removed from the simulation form:** the gravity slider and the radiation dose-rate slider. Both
  response curves are scenario coefficients with no dataset behind them, and offering them as
  controls implied a precision the evidence does not have. World presets still carry gravity and
  dose rate as scenario context and the coefficients stay documented in
  `simulation_constants.py` as assumptions, not measurements.
- **Constrained by measurement:** the water-recovery control now stops at 98 %, the ISS figure. A
  value above it is refused with a 422 rather than accepted as a scenario.
- **Added as measured data:** ethylene and water closure, above.
