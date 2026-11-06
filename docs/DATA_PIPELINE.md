# Reproducing scientific data and model artifacts

Use Python 3.12 or newer. From the repository root (Windows examples):

```powershell
backend/.venv/Scripts/python.exe -m pip install -r ml/requirements.txt
backend/.venv/Scripts/python.exe scripts/discover_datasets.py --refresh
backend/.venv/Scripts/python.exe scripts/download_nasa_data.py
backend/.venv/Scripts/python.exe scripts/validate_datasets.py
backend/.venv/Scripts/python.exe scripts/preprocess_datasets.py
backend/.venv/Scripts/python.exe ml/training/train_models.py
```

On Unix, replace the interpreter with `python` in an activated environment. The scripts resolve repository paths independently of the working directory.

Discovery queries all thirteen specified OSD studies. Download selects the small OSD-655/745 physiological CSVs and OSD-767 STAR gene counts. It intentionally does not acquire gigabytes of sequencing reads or unlabelled photography. Requests retry transient network failures three times and accept only official NASA endpoints plus the NASA-selected S3 bucket. Checksums support cached acquisition; rerun discovery with `--refresh` to detect new upstream file versions. Files with unexpected lengths fail rather than silently train against a changed source.

`build_training_tables.py` is an explicit alias for the audited preprocessing procedure. It writes CSV and Parquet harvest/irrigation tables, a specimen metadata CSV, normalized RNA Parquet, and machine-readable quality reports. Missing outcomes, normalization and group identities are recorded. No imputation is performed on target values.

The training job runs outside HTTP requests. It performs grouped nested validation and writes real out-of-fold predictions, fold assignments, comparison baselines, PNG evaluation figures, safe JSON coefficient artifacts, model cards and an artifact registry with SHA256 hashes. The registry records interpreter/library versions and a source-checksum manifest digest. Reproduction with another library version may change fitted coefficients; use the recorded versions for exact comparisons.

Small physiological source CSVs, processed CSVs, provenance and compact JSON models are versioned in Git. Large raw RNA count/cache files and Parquet intermediates are ignored and regenerated with these commands. No pickle or executable model serialization is loaded by the API. Inference uses verified JSON coefficients and the Python standard library. The Docker image must include `data/metadata`, selected previews under `data/raw`/`data/processed`, and `ml/artifacts`; it does not require training dependencies.
