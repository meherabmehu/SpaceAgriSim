# Phase 2 hybrid simulation science audit

## Scope

The simulation engine is retained as an assumption-based scenario estimator. This audit tests bookkeeping and physical bounds; it does not convert its coefficients into NASA-calibrated claims.

## Verified invariants

| Area | Invariant | Result |
| --- | --- | --- |
| Water accounting | demand = supplied/used + deficit | enforced and tested |
| Recovery accounting | 0 <= recovered <= used; net consumption = used - recovered | enforced and tested |
| Input bounds | recovery is clipped internally and API request values are bounded | enforced and tested |
| VPD | zero at 100% relative humidity; increases at higher temperature for a fixed RH | tested |
| Outputs | public biomass, water and gas outputs are finite and non-negative over bounded scenario inputs | tested |
| Spectral input | spectrum is annotation-only, avoiding an invented crop-specific effect | verified |

## Scientific interpretation

- Water **supplied** is not transpiration; the API maintains supplied, demand, deficit and recovered water separately.
- CO2 removal and O2 production are mass-balance estimates, not validated chamber gas-exchange measurements.
- Gravity, radiation, temperature, humidity and PPFD factors are scenario assumptions unless a model card says otherwise.
- Earth/Moon/Mars panels are hypothetical comparisons. They are not evidence of measured lunar or Martian crop performance.

## Calibration decision

No new simulator coefficient was calibrated in this phase. The NASA audit identified no independently usable, matched crop time-series for the necessary variables. Calibrating on the 14 OSD-655 endpoints or pooling unrelated external protocols would create misleading precision.
