# Scientific data provenance

Acquisition date: 2026-11-06. Source: NASA Open Science Data Repository, official public metadata/file APIs documented at <https://api.nasa.gov/> and <https://www.nasa.gov/osdr-api/>.

Every requested study identifier was queried, rather than trusting the descriptions in the project brief. Raw API responses are a local cache excluded from Git; their SHA256 values, source URLs, version fields and verified timestamps are retained in the dataset manifest. Downloaded bytes have individual SHA256 hashes, exact byte lengths and UTC acquisition timestamps in `download_checksums.json`. The downloaded content is not generated from the simulator.

The source file API may redirect official requests to `genelab-repo-prod.s3.amazonaws.com`; this NASA-selected bucket is explicitly allowed. Downloads are capped at 12 MB/file. Redirect URLs and signed query strings are not written to manifests. The manifest preserves stable NASA download endpoints.

## Transformations

1. Validate downloaded file hashes and byte lengths.
2. Decode CSV as UTF-8 with BOM, falling back to Windows-1252 for legacy supplements. Preserve original files byte-for-byte.
3. For VEG04A irrigation, read the days-after-initiation header and individual pillow rows. Exclude the `Predicted` row, treatment totals, root-mat totals, and spreadsheet errors. Keep real zeros; exclude `---` and blanks. Verify event sums against the published pillow total. Convert mL to L only for whole-period irrigation features.
4. Join harvest to irrigation **within OSD-655 VEG04A**, by environment and pillow number. Use reported `Total (g)` as fresh-mass target. Ten missing masses are excluded, not assumed zero. Preserve established-plant counts. Confirm red-rich pillows 1–6 and blue-rich pillows 7–12 from official sample naming. Do not join VEG04B chemistry to VEG04A mass.
5. In OSD-767, match all 36 count-matrix columns to the official specimen names. Convert count to CPM using the **full** sample library sum, then `log1p(CPM)`. Derive flight/ground, tissue, spectrum and plant grouping from the exact verified sample names. Canonicalize plant SN numbers numerically to avoid leading-zero discrepancies.
6. Keep different plant tissues in the same fold. Feature selection, variance filtering and scaling are trained within each training fold. Never split genes into samples.

## Evidence boundaries

Mizuna irrigation is supplied water, not measured water demand or transpiration. Tomato experimental flight context is not a disease label, stress score or causal gravity effect. NASA nutritional assays do not establish lettuce yield. None of these files independently validates the simulator's lunar, Martian, radiation, gas-exchange or life-support assumptions.

Public files remain subject to [OSDR reuse terms](https://science.nasa.gov/reference/osdr-help-terms-and-conditions/). Retain original investigator attribution and study/publication references. No third-party repository data was mixed into the training tables.
