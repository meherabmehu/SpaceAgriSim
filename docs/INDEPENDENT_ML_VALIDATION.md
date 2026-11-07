# Independent ML validation evidence

Reviewed 2026-11-07. An independent evaluation source must measure the same target, unit, crop/scope and inputs without sharing training observations.

| Model | Training evidence | Independent candidate review | Validation conclusion |
| --- | --- | --- | --- |
| `mizuna-harvest-v1` | 14 OSD-655 harvested-pillow endpoints | OSD-59 is mizuna RNA-seq after a separate spaceflight experiment, not harvested mass. No compatible independent mizuna fresh-mass table found. | No independent validation. Keep `baseline-only`. |
| `tomato-flight-response-v1` | OSD-767, 36 specimens / 21 plant groups | OSD-766 is from the same VEG-05 mission but microbiome rather than matching gene-expression input; using it would not independently test the classifier. | No independent validation. Keep experimental molecular-context scope. |
| `lettuce-earth-growth-v1` | WUR/4TU Batavia Othilie fresh shoot mass, four Earth experiments | Zenodo Piikkio has 402 lettuce point clouds with fresh-weight references, but its image/point-cloud inputs, cultivar/protocol and feature schema do not match the WUR temperature/PPFD model. | No compatible external holdout. Keep experimental, Earth-only scope. |

## Decisions

- No training dataset was reused as a claimed independent test set.
- No new accuracy, coverage or calibration metric was reported.
- Candidate studies can inform future collection plans, but not retrofit validation to incompatible artifacts.

