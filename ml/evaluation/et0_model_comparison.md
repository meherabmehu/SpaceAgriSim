# ET0 model comparison

Temporal holdout 2024-01-01 .. 2025-10-31 (3994 rows from 6 training sites).

| Rank | Candidate | Kind | MAE | RMSE | R2 | Bias |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | `ml_tdew_astronomy` | fit on temporal train split, features ['T2M_MAX', 'T2M_MIN', 'T2MDEW', 'latitude', 'elevationM', 'doySin', 'doyCos', 'raMj', 'daylightHours'] | 0.3981 | 0.5643 | 0.9336 | +0.0790 |
| 2 | `ml_tdew` | fit on temporal train split, features ['T2M_MAX', 'T2M_MIN', 'T2MDEW', 'latitude', 'elevationM'] | 0.5129 | 0.7130 | 0.8940 | +0.0671 |
| 3 | `ridge` | fit on temporal train split, features ['T2M_MAX', 'T2M_MIN', 'T2MDEW', 'latitude', 'elevationM', 'doySin', 'doyCos', 'raMj', 'daylightHours'] | 0.5701 | 0.7497 | 0.8827 | +0.0766 |
| 4 | `hargreaves` | published physics | 0.5748 | 0.8108 | 0.8628 | -0.2206 |
| 5 | `climatology` | training-window monthly mean | 0.6315 | 0.8784 | 0.8390 | +0.0755 |

Conformal half-width **0.9992 mm/day**, empirical coverage **91.99 %**.

## Leave-one-site-out (the test that fails)

| Site | n | Hargreaves MAE | Emulator MAE | Winner |
| --- | --- | --- | --- | --- |
| dhaka_bd | 2861 | 0.4952 | 0.6281 | Hargreaves |
| nairobi_ke | 2861 | 0.6347 | 1.0029 | Hargreaves |
| reykjavik_is | 2729 | 0.2137 | 0.2315 | Hargreaves |
| singapore_sg | 2861 | 0.7004 | 0.5203 | emulator |
| tucson_us | 2861 | 1.0728 | 1.0326 | emulator |
| wageningen_nl | 2848 | 0.3548 | 0.5361 | Hargreaves |
| **pooled** | | **0.5786** | **0.6586** | **Hargreaves (-13.82 %)** |

Acceptance gates: **3/4** passed.

- `beatsHargreavesTemporal`: 30.74 % (needs > 0 % lower MAE) - **pass**
- `beatsClimatology`: 36.96 % (needs > 0 % lower MAE) - **pass**
- `crossSiteGeneralisation`: -13.82 % (needs > 0 % lower pooled MAE across LOSO) - **FAIL**
- `intervalCoverage`: 91.99 % (needs 90-98 % empirical coverage) - **pass**
