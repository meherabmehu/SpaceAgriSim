"""Independent reference-ET0 validation against four weather sources.

Modules
-------
sources     acquisition with provenance, the credential gate and the CDS route
methods     hourly FAO-56 (eq. 53) and daily FAO-56 (eq. 6) plus Hargreaves
era5_land   CDS NetCDF reader, unit conversions and the radiation energy check
scoring     paired metrics computed on pairs, never on filled values
attribute   Shapley attribution of the per-site differences
run_validation, attribute   entry points
"""
