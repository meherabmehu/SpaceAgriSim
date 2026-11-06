# Phase 2 data harmonization policy

## Non-negotiable boundaries

- NASA spaceflight, NASA Earth analog, and external terrestrial data remain distinct source categories.
- Species, cultivar, growth system, harvest convention and output unit are not pooled by default.
- A source row is not duplicated to manufacture temporal observations or sample size.
- Any model card must expose its exact source category and support domain.

## Canonical fields

| Concept | Canonical representation | Conversion rule |
| --- | --- | --- |
| Fresh biomass | `g fresh mass/plant` | Convert area/tray values only when documented plant count and harvest protocol make the conversion defensible; otherwise retain native unit |
| Dry biomass | `g dry mass/plant` or native reported unit | Never substitute for fresh biomass without a same-sample dry-matter ratio |
| Light | PPFD in `umol m-2 s-1`, plus spectral treatment as categorical metadata | Photoperiod remains separate; do not treat different spectrum as identical PPFD exposure |
| Temperature | `degC`, air and root-zone retained separately | Do not infer root temperature from air temperature |
| Water | supplied irrigation, transpiration and recovery are separate variables | No conversion from supplied water to physiological transpiration |
| Gas exchange | leaf-area-normalized native units, e.g. `umol CO2 m-2 s-1` and `mmol H2O m-2 s-1` | Never scale to chamber/plant totals without measured leaf area and an explicit model |
| Time | days after sowing/transplant/experiment start, with the reference event retained | Do not combine age clocks without source protocol |

## Validation and missing data

- Split by independent experiment/cycle before any transform fitted from data.
- Fit imputation, scaling and feature selection inside training folds only.
- Record missingness as observed rather than silently filling scientific values.
- Treat unsupported combinations as out-of-domain even if each individual feature lies marginally within range.

## Current result

The WUR lettuce table is the only harmonized external table used for inference. NASA OSD-655 is evaluated independently. No cross-source “space crop” training table exists because the required target/protocol alignment has not been established.
