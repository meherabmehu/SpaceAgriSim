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

