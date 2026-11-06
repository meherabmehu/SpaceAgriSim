# ML training report

Training is offline and reproducible from the scripts in `ml/training/`; browser/API requests only load checksum-verified JSON artifacts. Registry hashes are validated before inference.

| Artifact | Source and task | Split / validation | Result | Appropriate use |
| --- | --- | --- | --- | --- |
| `mizuna-harvest-v1` | NASA OSD-655; harvested-mass exploratory regression | Grouped validation by experiment identity | MAE 14.76, RMSE 17.53, R2 -0.153; baseline MAE 14.19 | Demonstration of traceable inference only; weak model |
| `tomato-flight-response-v1` | NASA OSD-767 expression data; molecular recorded-context classification | Grouped by plant | macro-F1 0.8054, ROC-AUC 0.9414 | Molecular research context only, not crop performance |
| `lettuce-earth-growth-v1` | WUR/4TU CC-BY-4.0 lettuce data; fresh shoot mass | Nested leave-one-experiment-out CV | MAE 38.95 g, RMSE 71.74 g, R2 0.812; baseline MAE 125.83 g | Earth-only exploratory lettuce response within measured ranges |

For the lettuce artifact, all samples from each experiment stay together in outer folds. Its four inputs are days after transplant, air temperature, root temperature and PPFD. The displayed descriptive range is the 90th percentile absolute outer-CV residual (115.18 g); it is not a calibrated prediction interval.

No artifact is trained during application start-up or request handling. Exact source URL, license, domain, limitations, artifact version and checksums are retained in its model card.

