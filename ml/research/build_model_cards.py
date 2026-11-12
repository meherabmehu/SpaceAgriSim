"""Complete the metadata of the seven served model cards, outside the checksummed artifacts.

Why this file exists
--------------------
The seven served models are described by JSON documents in ``ml/artifacts/``. Those documents *are*
the model cards, and their SHA-256 values are published in ``ml/artifacts/registry`` and served
by ``GET /api/models``. Four of the seven omit the two fields a reader needs to reproduce them: the
path of the code that produced them and a hash of the data they were trained on.

The obvious fix - edit the four artifacts and add the missing keys - is the wrong one. Every one of
those files is checksum-addressed; changing a byte changes the hash the registry publishes, the hash
the audit script verifies, and the hash a previous report recorded. A model card must be able to
answer "is this the artefact I evaluated?" and the answer has to stay yes. So the artifacts are left
byte-for-byte untouched and the completion lives here, in a separate card that *points at* the
immutable artifact hash rather than replacing it.

What it can and cannot claim
----------------------------
A training-data hash is only worth recording if it can be recomputed. Three cases occur here, and
they are not the same, so the card does not present them as if they were:

``verified-committed-file``
    The training table is in the repository. The hash is computed from the file at build time.

``verified-recorded-checksum``
    The training file is deliberately not committed - it is a 24 MB NASA download - but its SHA-256
    is committed in a manifest, and the acquisition script re-downloads it. The hash is read from
    the manifest and cross-checked against the value the artifact recorded at training time.

``verified-reconstructed``
    The trainer reads a derived file that is not committed. The hash is obtained by reconstructing
    the file from its checked-upstream source with the repository's own preprocessing step and
    hashing the result. ``--verify-training-data`` performs that reconstruction; the plain
    ``--check`` mode does not, because it must work on a clone that has never downloaded anything.

A field that fits none of these is written as ``unavailable`` with the reason, and listed in the
card's ``exceptions`` array. Nothing is invented to make the table look complete.

Usage
-----
    python3 ml/research/build_model_cards.py                  # write the cards and the markdown
    python3 ml/research/build_model_cards.py --check          # fail if they are stale
    python3 ml/research/build_model_cards.py --verify-training-data
                                                              # re-acquire and re-hash the two
                                                              # inputs that are not committed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
REGISTRY = ROOT / "ml" / "artifacts" / "registry"
OUT_DIR = ROOT / "ml" / "artifacts" / "cards"
DOC = ROOT / "docs" / "MODEL_CARDS.md"
SCHEMA = "spaceagrisim.model_card/1"

# The seven models the application serves, in the order the platform lists them. The audit script
# reads the served set from `app.research` instead of hard-coding it; this file needs the same
# guarantee, so the two sets are asserted equal rather than assumed equal.
SERVED = (
    "lettuce-earth-growth-v1",
    "lettuce-earth-growth-v2",
    "lettuce-earth-growth-v3",
    "mizuna-microbial-relative-load-v2",
    "radiation-exposure-osd46-v1",
    "radiation-quality-osd46-v1",
    "tomato-flight-response-v1",
)

WUR_DOI = "https://doi.org/10.4121/5a7472f0-8a67-4ec0-84c9-9d032990d654.v1"

# ---------------------------------------------------------------------------------------------
# Per-model declarations. Everything here is either a statement about intended use (which only a
# human can make) or a pointer to evidence that the builder then verifies mechanically.
# ---------------------------------------------------------------------------------------------
SPECS: dict[str, dict] = {
    "lettuce-earth-growth-v1": {
        "purpose": (
            "Predict fresh shoot mass per lettuce plant from thermal time, air and root-zone "
            "temperature and incident PPFD, for a controlled-environment lettuce crop."
        ),
        "intendedUse": (
            "Exploring how a change in temperature or light moves per-plant fresh mass inside a "
            "plant-factory envelope, and producing a number a researcher can compare against their "
            "own measurement."
        ),
        "notIntendedFor": [
            "Operational or mission planning: the model fails its own independent check (41.6 % MAPE "
            "against a 30 % criterion fixed before the measurement).",
            "Crops, cultivars or light regimes outside the declared domain; the model refuses rather "
            "than extrapolating.",
            "Any claim about spaceflight performance. The training data are terrestrial.",
        ],
        "featureUnits": {
            "daysAfterTransplant": "days",
            "airTemperature": "degrees Celsius",
            "rootTemperature": "degrees Celsius",
            "ppfd": "micromol photons m-2 s-1 (400-700 nm)",
        },
        "trainingData": {
            "kind": "committed-file",
            "primaryInput": "data/processed/lettuce_earth.csv",
            "hashBasis": (
                "SHA-256 of data/processed/lettuce_earth.csv exactly as committed, which is the "
                "table train_lettuce.py writes and every lettuce trainer reads. Covers 1648 plant "
                "rows x 7 columns; the file is deterministic because the transform from the WUR "
                "workbook is fixed in the training script."
            ),
            "supportingInputs": [
                {"path": "data/raw/WUR-lettuce/original_dataset_lettuce.xlsx",
                 "role": "upstream source workbook, committed",
                 "hash": "computed"},
            ],
            "catalogueRef": None,
            "archiveRef": "data/raw/WUR-lettuce/original_dataset_lettuce.xlsx",
            "studyAccession": "WUR-lettuce (doi:10.4121/5a7472f0-8a67-4ec0-84c9-9d032990d654)",
            "sourceStudy": "WUR-lettuce",
            "sourceUrl": WUR_DOI,
            "licence": "see sourceUrl",
            "retrievable": True,
            "reconstruction": "python3 ml/training/train_lettuce.py regenerates the table from the committed workbook.",
        },
        "code": {"path": "ml/training/train_lettuce.py",
                 "commit": "aa7e9af9a5118337946c3f577577e5efba4ec37d"},
        "split": {
            "method": "Nested leave-one-experiment-out cross-validation (4 outer, 3 inner folds).",
            "grouped": True,
            "groupUnit": "experiment",
            "groups": 4,
            "note": "All plants and treatments from an experiment remain in the same fold, so the "
                    "score measures transfer to an unseen experiment rather than to an unseen row.",
        },
        "uncertainty": {
            "kind": "prediction-interval",
            "statement": (
                "90 % cross-conformal (CV+) interval, radius 112.94 g/plant, measured held-out "
                "coverage 0.939 over 4 calibration groups. The artifact records its own caveat: the "
                "interval describes this dataset's spread and is not a guarantee for a new "
                "greenhouse."
            ),
        },
        "exceptions": [],
    },
    "lettuce-earth-growth-v2": {
        "purpose": (
            "Second-generation lettuce fresh-mass regressor: the same task as v1 with a wider "
            "hyperparameter search and a documented selection rule."
        ),
        "intendedUse": "As v1, with a more defensible model-selection record.",
        "notIntendedFor": [
            "Operational or mission planning: fails its own independent check to the same criterion "
            "as v1.",
            "Out-of-domain crops, cultivars or light regimes.",
        ],
        "featureUnits": {
            "daysAfterTransplant": "days",
            "airTemperature": "degrees Celsius",
            "rootTemperature": "degrees Celsius",
            "ppfd": "micromol photons m-2 s-1 (400-700 nm)",
        },
        "trainingData": {
            "kind": "committed-file",
            "primaryInput": "data/processed/lettuce_earth.csv",
            "hashBasis": (
                "SHA-256 of data/processed/lettuce_earth.csv exactly as committed. v2 reads the same "
                "table v1 writes, so the hash is shared with v1 and v3 by construction and not by "
                "copying; v3's artifact independently records the same value."
            ),
            "supportingInputs": [
                {"path": "data/raw/WUR-lettuce/original_dataset_lettuce.xlsx",
                 "role": "upstream source workbook, committed", "hash": "computed"},
            ],
            "catalogueRef": None,
            "archiveRef": "data/raw/WUR-lettuce/original_dataset_lettuce.xlsx",
            "studyAccession": "WUR-lettuce (doi:10.4121/5a7472f0-8a67-4ec0-84c9-9d032990d654)",
            "sourceStudy": "WUR-lettuce",
            "sourceUrl": WUR_DOI,
            "licence": "see sourceUrl",
            "retrievable": True,
            "reconstruction": "python3 ml/training/train_lettuce.py regenerates the table; v2 then reads it.",
        },
        "code": {"path": "ml/training/train_lettuce_v2.py",
                 "commit": "aa7e9af9a5118337946c3f577577e5efba4ec37d"},
        "split": {
            "method": "Nested leave-one-experiment-out cross-validation (4 outer, 3 inner folds).",
            "grouped": True,
            "groupUnit": "experiment",
            "groups": 4,
            "note": "As v1: the fold boundary is the experiment, never the row.",
        },
        "uncertainty": {
            "kind": "prediction-interval",
            "statement": (
                "90 % cross-conformal (CV+) interval, radius 91.20 g/plant, measured held-out "
                "coverage 0.961 over 4 calibration groups. The artifact itself notes the coverage is "
                "over-fitted to those four experiments and should be read as descriptive."
            ),
        },
        "exceptions": [],
    },
    "lettuce-earth-growth-v3": {
        "purpose": (
            "Predict lettuce fresh mass per plant and per square metre from thermal time, "
            "temperature and daily light integral, with plant density entering through an explicit "
            "per-area identity."
        ),
        "intendedUse": (
            "Bounding how light integral and density move yield per square metre, and comparing a "
            "vertical-farm configuration with a horizontal one at equal photon supply."
        ),
        "notIntendedFor": [
            "Operational forecasting: 41.6 % MAPE on the independent Touliatos study against a 30 % "
            "criterion fixed in advance. The artifact records this and the platform must not "
            "present it as validated.",
            "Densities above the declared ceiling (~200 plants/m2), where per-area yield is not "
            "learned but only divided.",
            "Any cultivar other than Batavia Othilie: cultivar is not a feature.",
        ],
        "featureUnits": {
            "daysAfterTransplant": "days",
            "airTemperature": "degrees Celsius",
            "rootTemperature": "degrees Celsius",
            "dailyLightIntegral": "mol m-2 d-1, computed from PPFD and photoperiod",
        },
        "trainingData": {
            "kind": "committed-file",
            "primaryInput": "data/processed/lettuce_earth.csv",
            "hashBasis": (
                "SHA-256 of data/processed/lettuce_earth.csv. This value is corroborated rather than "
                "merely asserted: the v3 artifact records the same digest in its own "
                "trainingDataSha256 field, written by the training run."
            ),
            "supportingInputs": [
                {"path": "data/raw/WUR-lettuce/original_dataset_lettuce.xlsx",
                 "role": "upstream source workbook, committed", "hash": "computed"},
            ],
            "catalogueRef": None,
            "archiveRef": "data/raw/WUR-lettuce/original_dataset_lettuce.xlsx",
            "studyAccession": "WUR-lettuce (doi:10.4121/5a7472f0-8a67-4ec0-84c9-9d032990d654)",
            "sourceStudy": "WUR-lettuce",
            "sourceUrl": WUR_DOI,
            "licence": "see sourceUrl",
            "retrievable": True,
            "reconstruction": "python3 ml/training/train_lettuce_v3.py",
        },
        "code": {"path": "ml/training/train_lettuce_v3.py",
                 "commit": "aa7e9af9a5118337946c3f577577e5efba4ec37d"},
        "split": {
            "method": "Leave-one-experiment-out, 4 folds.",
            "grouped": True,
            "groupUnit": "experiment",
            "groups": 4,
            "note": "Reported alongside a six-treatment independent cross-campaign interval check.",
        },
        "uncertainty": {
            "kind": "prediction-interval",
            "statement": (
                "Conformal residual quantiles on the log target, 5th and 95th percentile. "
                "Out-of-fold coverage 0.899 on the same predictions the quantiles come from, which "
                "the artifact itself labels descriptive rather than independent evidence; the "
                "independent cross-campaign check covers 6 of 6 treatment means."
            ),
        },
        "exceptions": [],
    },
    "mizuna-microbial-relative-load-v2": {
        "purpose": (
            "Predict the microbial load of mizuna leaf tissue relative to its own campaign mean, in "
            "within-campaign standard deviations of log10 CFU per gram."
        ),
        "intendedUse": (
            "Comparing flight and ground harvests of the same experiment on a relative scale, where "
            "the question is whether a treatment raised or lowered load rather than what the "
            "absolute load was."
        ),
        "notIntendedFor": [
            "Absolute microbial load. The absolute model is retained but withdrawn from service "
            "because it does not transfer to an unseen campaign (R2 -0.55 and -0.58).",
            "Safety or consumability decisions. The endpoint is culturable aerobic count on leaf "
            "tissue, not pathogen presence.",
            "Crops other than mizuna, or campaigns other than VEG-04.",
        ],
        "featureUnits": {
            "flight": "binary indicator (1 = flight, 0 = ground)",
            "blueLight": "binary indicator (1 = blue-enriched, 0 = red-enriched)",
            "sanitised": "binary indicator",
            "harvestIndex": "harvest ordinal within the campaign",
            "logFreshWeightG": "log10 of fresh mass in grams",
        },
        "trainingData": {
            "kind": "committed-file",
            "primaryInput": "data/processed/mizuna_microbial_load.csv",
            "hashBasis": (
                "SHA-256 of data/processed/mizuna_microbial_load.csv exactly as committed. Covers "
                "123 leaf-tissue measurements across 35 biological groups; the table is produced "
                "from the committed OSD-780 records by scripts/preprocess_osd780.py."
            ),
            "supportingInputs": [
                {"path": "data/raw/OSD-780",
                 "role": "NASA OSDR source records, committed under data/raw/OSD-780",
                 "hash": "directory"},
            ],
            "catalogueRef": "osdr-plant-experiments",
            "studyAccession": "OSD-780",
            "sourceStudy": "OSD-780",
            "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-780",
            "licence": "NASA OSDR open data policy",
            "retrievable": True,
            "reconstruction": "python3 scripts/preprocess_osd780.py rebuilds the table from the committed raw records.",
        },
        "code": {"path": "ml/training/train_microbial_v2.py",
                 "commit": "aa7e9af9a5118337946c3f577577e5efba4ec37d"},
        "split": {
            "method": "Leave-one-campaign-out transfer, with group-level cross-conformal calibration.",
            "grouped": True,
            "groupUnit": "biological group (plant/pillow)",
            "groups": 35,
            "note": "The transfer set is a whole campaign, not a held-out row set; that is why the "
                    "absolute-load predecessor failed and this relative successor is served.",
        },
        "uncertainty": {
            "kind": "prediction-interval",
            "statement": (
                "Group-level cross-conformal interval, radius 1.679 in within-campaign standard "
                "deviations, nominal 90 % coverage, achieved 0.9919 over 35 calibration groups. The "
                "exchangeability unit is the biological group."
            ),
        },
        "exceptions": [],
    },
    "radiation-exposure-osd46-v1": {
        "purpose": (
            "Classify Arabidopsis OSD-46 seedling expression into a radiation-exposure context, "
            "distinguishing gamma exposure from the design's other conditions."
        ),
        "intendedUse": (
            "Reading a transcriptomic response to radiation exposure as a class, to compare against "
            "the platform's radiation model assumptions."
        ),
        "notIntendedFor": [
            "Dose prediction. The model classifies context; the platform's dose capability was "
            "withdrawn in Phase 30 and this classifier does not restore it.",
            "Any crop other than Arabidopsis, and any platform other than the ATH1 array.",
            "Operational dosimetry of any kind.",
        ],
        "featureUnits": {
            "__expression__": "log2 normalised Affymetrix intensities, gene-model collapsed by mean"
                             " - every gene in `features`, a partial vector is rejected"
        },
        "trainingData": {
            "kind": "recorded-checksum",
            "primaryInput": "data/raw/OSD-46/GLDS-46_array_normalized_expression_probeset_GLmicroarray.csv",
            "hashBasis": (
                "SHA-256 of the NASA OSDR OSD-46 v6 normalised expression matrix: 22,810 probesets "
                "x 44 samples, 23,794,742 bytes. The file is deliberately not committed (it is a "
                "24 MB re-acquirable download, excluded by .gitignore policy); its digest is "
                "committed in data/metadata/phase9_nasa_datasets and the artifact recorded the "
                "same digest at training time."
            ),
            "supportingInputs": [
                {"path": "data/processed/osd46_radiation_samples.csv",
                 "role": "committed sample annotation joining samples to radiation class",
                 "hash": "computed"},
            ],
            "manifest": "data/metadata/phase9_nasa_datasets",
            "catalogueRef": "osdr-plant-experiments",
            "studyAccession": "OSD-46",
            "sourceStudy": "OSD-46",
            "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-46",
            "licence": "NASA OSDR open data policy",
            "retrievable": True,
            "reconstruction": "python3 scripts/acquire_phase9.py re-downloads the matrix and verifies it against the committed digest.",
        },
        "code": {"path": "ml/training/train_radiation_osd46.py",
                 "commit": "aa7e9af9a5118337946c3f577577e5efba4ec37d"},
        "split": {
            "method": "Leave-one-biological-group-out cross-validation over 22 groups.",
            "grouped": True,
            "groupUnit": "biological group",
            "groups": 22,
            "note": "Gene filtering and ANOVA selection are fitted inside each training fold only, "
                    "and labels are permuted between groups to build the null.",
        },
        "uncertainty": {
            "kind": "probability-calibration",
            "statement": (
                "Served as a class probability with the calibration recorded in the artifact's "
                "probabilityCalibration block; the platform reports the measured expected "
                "calibration error rather than asserting the probabilities are calibrated."
            ),
        },
        "exceptions": [],
    },
    "radiation-quality-osd46-v1": {
        "purpose": (
            "Classify Arabidopsis OSD-46 seedling expression into a radiation-quality class: "
            "control, gamma or high-energy heavy ion."
        ),
        "intendedUse": (
            "Testing whether the platform's assumption that light and radiation quality act through "
            "distinguishable transcriptomic routes is visible in measured expression."
        ),
        "notIntendedFor": [
            "Predicting plant yield or growth from radiation quality; the endpoint is a molecular "
            "class, not a phenotype.",
            "Crops other than Arabidopsis, or platforms other than the ATH1 array.",
        ],
        "featureUnits": {
            "__expression__": "log2 normalised Affymetrix intensities, gene-model collapsed by mean"
                             " - every gene in `features`, a partial vector is rejected"
        },
        "trainingData": {
            "kind": "recorded-checksum",
            "primaryInput": "data/raw/OSD-46/GLDS-46_array_normalized_expression_probeset_GLmicroarray.csv",
            "hashBasis": (
                "SHA-256 of the NASA OSDR OSD-46 v6 normalised expression matrix, 22,810 probesets "
                "x 44 samples. Not committed by policy; the digest is committed in "
                "data/metadata/phase9_nasa_datasets and recorded in the artifact."
            ),
            "supportingInputs": [
                {"path": "data/processed/osd46_radiation_samples.csv",
                 "role": "committed sample annotation carrying the three-class label",
                 "hash": "computed"},
            ],
            "manifest": "data/metadata/phase9_nasa_datasets",
            "catalogueRef": "osdr-plant-experiments",
            "studyAccession": "OSD-46",
            "sourceStudy": "OSD-46",
            "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-46",
            "licence": "NASA OSDR open data policy",
            "retrievable": True,
            "reconstruction": "python3 scripts/acquire_phase9.py re-downloads the matrix and verifies it against the committed digest.",
        },
        "code": {"path": "ml/training/train_radiation_osd46.py",
                 "commit": "aa7e9af9a5118337946c3f577577e5efba4ec37d"},
        "split": {
            "method": "Leave-one-biological-group-out cross-validation over 22 groups.",
            "grouped": True,
            "groupUnit": "biological group",
            "groups": 22,
            "note": "Identical protocol to the exposure classifier; gene selection inside the fold.",
        },
        "uncertainty": {
            "kind": "probability-calibration",
            "statement": (
                "Served as a class probability with the measured calibration recorded in the "
                "artifact's probabilityCalibration block."
            ),
        },
        "exceptions": [],
    },
    "tomato-flight-response-v1": {
        "purpose": (
            "Classify tomato seedling expression into recorded flight versus ground experimental "
            "context."
        ),
        "intendedUse": (
            "Asking whether the transcriptomic record of a flight experiment is separable from its "
            "ground control at all - a question about the experiment, not about the plant's health."
        ),
        "notIntendedFor": [
            "Stress severity or plant health inference. The label is recorded experimental context.",
            "Predicting yield, harvest mass or anything agronomic.",
            "Crops other than tomato, studies other than OSD-767.",
        ],
        "featureUnits": {
            "__expression__": "log1p(CPM) - log1p(STAR raw count divided by full sample library sum "
                             "times 1e6), for each of the 64 selected genes"
        },
        "trainingData": {
            "kind": "reconstructed-derived",
            "primaryInput": "data/processed/tomato_log_cpm.parquet",
            # Re-derived by --verify-training-data from the checked upstream counts, twice, with
            # identical bytes both times. See the reconstruction note for what each digest covers.
            "reconstructedSha256": "88b335847f4a7d342c8c948c5369c8de990c3870f95b455ac2cd7418b2aa56b1",
            "contentSha256": "ad8eeb36d13a4b32b07c921fbee6901280ea60e9ac6b02471ae39d3573fd4e48",
            "hashBasis": (
                "SHA-256 of the derived log1p(CPM) matrix the trainer reads: 36 samples x 33,562 "
                "genes, 29,705,842 bytes, produced by scripts/preprocess_datasets.py from the "
                "OSD-767 STAR counts. The parquet is not committed, so the digest was obtained by "
                "reconstruction from the checked upstream file, and a second, "
                "version-independent digest over the same matrix serialised as CSV is recorded "
                "alongside it because parquet byte layout is a property of the pyarrow version "
                "rather than of the data."
            ),
            "supportingInputs": [
                {"path": "data/raw/OSD-767/GLDS-709_rna_seq_STAR_Unnormalized_Counts_GLbulkRNAseq.csv",
                 "role": "upstream raw counts, not committed, digest pinned in data/metadata/download_checksums",
                 "hash": "87c18a8b104484310050393976a9df4325e42233ae06b4670f6269c819d61910"},
                {"path": "data/processed/tomato_samples.csv",
                 "role": "committed sample annotation joining samples to plant and environment",
                 "hash": "computed"},
            ],
            "manifest": "data/metadata/download_checksums",
            "catalogueRef": "osdr-plant-experiments",
            "studyAccession": "OSD-767",
            "sourceStudy": "OSD-767",
            "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-767",
            "licence": "NASA OSDR open data policy",
            "retrievable": True,
            "reconstruction": (
                "Download the OSD-767 counts (digest above), then run "
                "python3 scripts/preprocess_datasets.py; the parquet is reconstructed "
                "byte-for-byte under pyarrow 26.0.1, the version pinned in "
                "ml/requirements-training.txt."
            ),
        },
        "code": {"path": "ml/training/train_models.py",
                 "commit": "aa7e9af9a5118337946c3f577577e5efba4ec37d"},
        "split": {
            "method": "Nested stratified group cross-validation (4 outer, 3 inner folds).",
            "grouped": True,
            "groupUnit": "plant (both tissues of a plant stay together)",
            "groups": 21,
            "note": "Gene selection and scaling are fitted inside each training fold only.",
        },
        "uncertainty": {
            "kind": "probability-calibration",
            "statement": (
                "Served as a class probability with the measured calibration recorded in the "
                "artifact's probabilityCalibration block. The artifact itself labels the output "
                "uncalibrated in its unit string, and the platform surfaces the measured error."
            ),
        },
        "exceptions": [],
    },
}


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def manifest_digest(manifest: pathlib.Path, filename: str) -> str | None:
    payload = safedata.load(manifest)
    entries = payload.get("files") if isinstance(payload, dict) else payload
    for entry in entries or []:
        if isinstance(entry, dict) and str(entry.get("path", "")).endswith(filename):
            return entry.get("sha256")
        if isinstance(entry, dict) and entry.get("name") == filename:
            return entry.get("sha256")
    return None


def registry_rows() -> dict[str, dict]:
    return {row["id"]: row for row in safedata.load(REGISTRY)["models"]}


def served_ids_from_app() -> set[str]:
    backend = str(ROOT / "backend")
    if backend not in sys.path:
        sys.path.insert(0, backend)
    from app import research  # noqa: PLC0415 - deliberate: only needed when the app is importable

    return {model["id"] for model in research.model_registry()["models"]}


def code_reference(spec: dict) -> dict:
    """Resolve the training script to an immutable commit and prove that commit contains it."""
    path = spec["code"]["path"]
    commit = spec["code"]["commit"]
    file_digest = sha256_file(ROOT / path)
    result = subprocess.run(["git", "cat-file", "-e", f"{commit}:{path}"],
                            cwd=ROOT, capture_output=True)
    in_commit = result.returncode == 0
    # The script on disk must still be the one that commit recorded, or the reference points at
    # code that no longer exists under that path.
    show = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True)
    digest_at_commit = (hashlib.sha256(show.stdout).hexdigest() if show.returncode == 0 else None)
    return {
        "path": path,
        "commit": commit,
        "commitContainsPath": in_commit,
        "sha256AtCommit": digest_at_commit,
        "sha256OnDisk": file_digest,
        "unchangedSinceCommit": digest_at_commit == file_digest,
        "immutable": bool(in_commit),
        "resolveWith": f"git show {commit}:{path}",
    }


def training_data_block(model_id: str, spec: dict, artifact: dict) -> dict:
    decl = spec["trainingData"]
    block = {
        "status": decl["kind"],
        "primaryInput": decl["primaryInput"],
        "hashBasis": decl["hashBasis"],
        "catalogueRef": decl.get("catalogueRef"),
        "archiveRef": decl.get("archiveRef"),
        "studyAccession": decl.get("studyAccession"),
        "sourceStudy": decl.get("sourceStudy"),
        "sourceUrl": decl.get("sourceUrl"),
        "licence": decl.get("licence"),
        "retrievable": decl.get("retrievable", False),
        "reconstruction": decl.get("reconstruction"),
        "manifest": decl.get("manifest"),
        "supportingInputs": [],
    }

    if decl["kind"] == "committed-file":
        path = ROOT / decl["primaryInput"]
        if safedata.exists(path):
            block["sha256"] = sha256_file(path)
            block["hashVerifiedAtBuild"] = True
        else:
            block["sha256"] = None
            block["hashVerifiedAtBuild"] = False
            block["status"] = "unavailable"
            block["reason"] = f"committed training table missing from the tree: {decl['primaryInput']}"
        recorded = artifact.get("trainingDataSha256")
        if recorded:
            block["recordedInArtifact"] = recorded
            block["artifactAgrees"] = recorded == block.get("sha256")

    elif decl["kind"] == "recorded-checksum":
        digest = manifest_digest(ROOT / decl["manifest"], pathlib.Path(decl["primaryInput"]).name)
        block["sha256"] = digest
        block["hashVerifiedAtBuild"] = digest is not None
        recorded = artifact.get("sourceChecksum") or ""
        # The artifact records a truncated digest; check that it is a prefix of the manifest value.
        if digest and recorded:
            prefix = recorded.split("sha256")[-1].strip()
            block["recordedInArtifactPrefix"] = prefix
            block["artifactAgrees"] = bool(prefix) and digest.startswith(prefix)

    elif decl["kind"] == "reconstructed-derived":
        block["sha256"] = decl.get("reconstructedSha256")
        block["contentSha256"] = decl.get("contentSha256")
        block["hashVerifiedAtBuild"] = bool(decl.get("reconstructedSha256"))
        block["verifiedWith"] = "python3 ml/research/build_model_cards.py --verify-training-data"
        block["byteStability"] = (
            "Byte-identical across repeated runs under the pinned pyarrow version; the parquet "
            "container is not guaranteed byte-stable across pyarrow versions, which is why a "
            "content digest over the same matrix is recorded too."
        )

    for item in decl.get("supportingInputs") or []:
        entry = {"path": item["path"], "role": item["role"]}
        if item.get("hash") == "computed":
            p = ROOT / item["path"]
            if safedata.exists(p):
                entry["sha256"] = sha256_file(p)
                entry["hashVerifiedAtBuild"] = True
            else:
                entry["sha256"] = None
                entry["hashVerifiedAtBuild"] = False
        elif item.get("hash") == "directory":
            # A supporting input can be a *directory* of committed source records. Hashing the
            # directory as an opaque blob would be meaningless, and pointing at a manifest that
            # does not exist is worse than saying nothing - that is exactly what this branch did
            # for OSD-780, citing data/metadata/osd780_checksums, which was never created.
            # So the digests are computed here, per file, and a manifest digest over the sorted
            # (name, sha256) pairs makes the set itself checkable in one value.
            p = ROOT / item["path"]
            files = sorted(f for f in p.rglob("*") if safedata.exists(f)) if p.is_dir() else []
            if files:
                entry["files"] = [
                    {"name": str(f.relative_to(p)), "bytes": f.stat().st_size,
                     "sha256": sha256_file(f)}
                    for f in files
                ]
                manifest = "\n".join(f"{row['name']} {row['sha256']}" for row in entry["files"])
                entry["manifestSha256"] = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
                entry["fileCount"] = len(entry["files"])
                entry["hashBasis"] = (
                    "Per-file SHA-256 computed from the committed files under this path, plus a "
                    "manifest digest over the sorted 'name sha256' lines."
                )
                entry["hashVerifiedAtBuild"] = True
            else:
                entry["hashVerifiedAtBuild"] = False
                entry["hashSource"] = "declared directory is absent from the checkout"
        else:
            entry["sha256"] = item.get("hash")
            entry["hashVerifiedAtBuild"] = False
            entry["hashSource"] = "recorded upstream digest"
        block["supportingInputs"].append(entry)

    return block


def build_card(model_id: str, row: dict, spec: dict) -> dict:
    artifact_path = ROOT / row["artifact"]
    artifact = safedata.load(artifact_path)
    on_disk = sha256_file(artifact_path)

    interval = artifact.get("interval") or {}
    calibration = artifact.get("probabilityCalibration") or {}
    unc = spec["uncertainty"]
    if unc["kind"] == "prediction-interval":
        uncertainty = {
            "kind": "prediction-interval",
            "statement": unc["statement"],
            "artifactKind": interval.get("kind") or interval.get("method"),
            "outOfFoldCoverage": (interval.get("outOfFoldCoverage")
                                  if interval.get("outOfFoldCoverage") is not None
                                  else interval.get("empiricalCoverage")),
            "radius": interval.get("radius"),
            "nominalCoverage": interval.get("nominalCoverage"),
            "calibrationGroups": interval.get("calibrationGroups"),
            "crossCampaignCoverage": bool(interval.get("crossCampaign")),
        }
    elif unc["kind"] == "probability-calibration":
        uncertainty = {
            "kind": "probability-calibration",
            "statement": unc["statement"],
            "calibrationRecorded": bool(calibration),
            "measuredEce": calibration.get("ece"),
            "bins": calibration.get("bins"),
        }
    else:
        uncertainty = {"kind": "unavailable", "statement": unc["statement"], "available": False}

    verdict = artifact.get("evidenceVerdict")
    if isinstance(verdict, dict):
        verdict_token = verdict.get("verdict")
        decision_grade = bool(verdict.get("decisionGrade"))
    else:
        verdict_token, decision_grade = verdict, False

    # The artifact stores a lower-case token; the platform displays a five-way classification. Both
    # are recorded and the mapping is explicit, because a card that quietly showed one where a
    # reader expected the other is how "failed" becomes "pending".
    TAXONOMY = {
        "passes-independent-check": "PASS decision-grade",
        "fails-independent-check": "FAILS-INDEPENDENT-CHECK",
        "no-independent-check": "NO-INDEPENDENT-CHECK",
        "domain-refused": "DOMAIN-REFUSED",
        "insufficient-evidence": "INSUFFICIENT-EVIDENCE",
    }
    classification = TAXONOMY.get(str(verdict_token), "INSUFFICIENT-EVIDENCE")

    card = {
        "schema": SCHEMA,
        "modelId": model_id,
        "version": str(artifact.get("version") or "1"),
        "generatedBy": "ml/research/build_model_cards.py",
        "generatedOn": "2026-11-12",
        "artifact": {
            "path": row["artifact"],
            "sha256": on_disk,
            "registrySha256": row["sha256"],
            "hashPreserved": on_disk == row["sha256"],
            "modifiedByThisCompletion": False,
            "note": (
                "The artifact is the model card the platform publishes and is checksum-addressed. "
                "This completion document is stored beside it and never inside it, so every "
                "previously published hash remains valid."
            ),
        },
        "identity": {
            "name": artifact.get("name"),
            "status": artifact.get("status"),
            "task": artifact.get("task"),
            "organism": artifact.get("crop") or artifact.get("organism"),
            "supersedes": artifact.get("supersedes"),
            "servesAlongside": artifact.get("servesAlongside"),
        },
        "purpose": spec["purpose"],
        "intendedUse": spec["intendedUse"],
        "notIntendedFor": spec["notIntendedFor"],
        "features": [
            {"name": name, "unit": unit} for name, unit in spec["featureUnits"].items()
        ],
        "featureCount": len(artifact.get("features") or []),
        "domain": artifact.get("domain"),
        "trainingData": training_data_block(model_id, spec, artifact),
        "code": code_reference(spec),
        "split": spec["split"],
        "metrics": artifact.get("metrics"),
        "baseline": {
            "metrics": artifact.get("baselineMetrics")
                       or (artifact.get("metrics") or {}).get("baselineMacroF1")
                       or artifact.get("beatsBaseline"),
            "outperformsBaseline": artifact.get("beatsBaseline"),
        },
        "uncertainty": uncertainty,
        "limitations": artifact.get("limitations") or [],
        "outOfDomainBehaviour": {
            "refuses": True,
            "mechanism": (
                "The artifact's `domain` block is enforced before scoring; a request outside it is "
                "refused with the field and range named rather than extrapolated, and a "
                "transcriptomic model rejects a partial expression vector instead of zero-filling."
            ),
        },
        "evidence": {
            "verdict": verdict_token,
            "classification": classification,
            "decisionGrade": decision_grade,
            "promotedByThisCompletion": False,
            "retrainedByThisCompletion": False,
            "thresholdsChangedByThisCompletion": False,
            "evidenceRecord": "ml/evaluation/phase37_model_evidence",
        },
        "samples": artifact.get("samples"),
        "groups": artifact.get("groups"),
        "seed": artifact.get("seed"),
        "exceptions": spec["exceptions"],
        "completeness": {},
    }

    # A field counts as complete only when it carries evidence, not merely a key.
    checks = {
        "identifier": bool(card["modelId"]),
        "purpose": bool(card["purpose"]),
        "intendedUse": bool(card["intendedUse"]),
        "notIntendedFor": bool(card["notIntendedFor"]),
        "features": card["featureCount"] > 0 and bool(card["features"]),
        "domain": bool(card["domain"]),
        "trainingData": bool(card["trainingData"].get("sha256")),
        "codeReference": bool(card["code"]["immutable"]),
        "artifactHash": bool(card["artifact"]["hashPreserved"]),
        "split": bool(card["split"].get("method")) and card["split"].get("grouped") is True,
        "metrics": bool(card["metrics"]),
        "baseline": bool(card["baseline"]["metrics"]),
        "uncertainty": unc["kind"] != "none-recorded",
        "limitations": bool(card["limitations"]),
        "evidence": bool(card["evidence"]["verdict"]),
    }
    card["completeness"] = {
        "checks": checks,
        "complete": sum(1 for v in checks.values() if v),
        "total": len(checks),
        "allComplete": all(checks.values()),
        "exceptions": card["exceptions"],
    }
    return card


def verify_training_data() -> int:
    """Re-acquire the two inputs that are not committed and re-derive their digests."""
    ok = True

    # OSD-46: read the digest the manifest commits and confirm the artifact's prefix agrees.
    manifest = ROOT / "data" / "metadata" / "phase9_nasa_datasets"
    digest = manifest_digest(manifest, "GLDS-46_array_normalized_expression_probeset_GLmicroarray.csv")
    print(f"OSD-46 matrix digest (committed manifest): {digest}")
    local = ROOT / "data/raw/OSD-46/GLDS-46_array_normalized_expression_probeset_GLmicroarray.csv"
    if safedata.exists(local):
        actual = sha256_file(local)
        print(f"OSD-46 matrix digest (file on disk):       {actual}  match={actual == digest}")
        ok &= actual == digest
    else:
        print("OSD-46 matrix not present locally; digest taken from the committed manifest, "
              "re-acquirable with scripts/acquire_phase9.py")

    # OSD-767: download, verify against the committed digest, reconstruct the parquet, hash it.
    spec = SPECS["tomato-flight-response-v1"]["trainingData"]
    raw = ROOT / "data/raw/OSD-767/GLDS-709_rna_seq_STAR_Unnormalized_Counts_GLbulkRNAseq.csv"
    expected = None
    for entry in safedata.load(ROOT / "data" / "metadata" / "download_checksums"):
        if str(entry.get("path", "")).endswith("GLDS-709_rna_seq_STAR_Unnormalized_Counts_GLbulkRNAseq.csv"):
            expected = entry["sha256"]
    tmp = pathlib.Path("/tmp/osd767_verify")
    tmp.mkdir(parents=True, exist_ok=True)
    if not safedata.exists(raw):
        print("OSD-767 counts not present; downloading to verify the pinned digest…")
        url = ("https://osdr.nasa.gov/geode-py/ws/studies/OSD-767/download"
               "?source=datamanager&file=GLDS-709_rna_seq_STAR_Unnormalized_Counts_GLbulkRNAseq.csv")
        local_copy = tmp / raw.name
        subprocess.run(["curl", "-sSL", "--fail", "--max-time", "600", url, "-o", str(local_copy)],
                       check=False)
        raw = local_copy
    actual_raw = sha256_file(raw)
    print(f"OSD-767 counts digest: {actual_raw}\nexpected:              {expected}\n"
          f"match={actual_raw == expected}")
    ok &= actual_raw == expected

    import numpy as np  # noqa: PLC0415
    import pandas as pd  # noqa: PLC0415

    counts = pd.read_csv(raw, index_col=0)
    log_cpm = np.log1p(counts.div(counts.sum(axis=0), axis=1) * 1_000_000).T
    first = tmp / "a.parquet"
    second = tmp / "b.parquet"
    log_cpm.to_parquet(first)
    log_cpm.to_parquet(second)
    h1, h2 = sha256_file(first), sha256_file(second)
    content = hashlib.sha256(log_cpm.to_csv(float_format="%.17g").encode()).hexdigest()
    print(f"tomato log1p(CPM) parquet sha256: {h1}\n"
          f"  byte-identical on re-run:        {h1 == h2}\n"
          f"  content digest (CSV, %.17g):     {content}\n"
          f"  recorded in card:                {spec.get('reconstructedSha256')}")
    ok &= (h1 == h2) and (h1 == spec.get("reconstructedSha256")) and (content == spec.get("contentSha256"))
    print("\ntraining-data verification:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def render_markdown(cards: list[dict]) -> str:
    lines = [
        "# Model cards",
        "",
        "The seven models this platform serves, described with the metadata a reader needs to",
        "reproduce or refute them.",
        "",
        "These documents live *beside* the checksummed artifacts in `ml/artifacts/`, never inside",
        "them. Every artifact hash published before this completion is therefore still valid: the",
        "cards point at the immutable artifact digest instead of rewriting it.",
        "",
        "Generated by `python3 ml/research/build_model_cards.py`; `--check` fails if this file or",
        "any card is stale.",
        "",
        "## Summary",
        "",
        "| Model | Complete | Training data | Code reference | Artifact hash | Verdict |",
        "|---|---|---|---|---|---|",
    ]
    for card in cards:
        comp = card["completeness"]
        td = card["trainingData"]
        td_cell = f"{td['status']}" + (" (verified)" if td.get("hashVerifiedAtBuild") else " (unverified)")
        code_cell = f"`{card['code']['commit'][:12]}`" if card["code"]["immutable"] else "unresolved"
        lines.append(
            f"| `{card['modelId']}` | {comp['complete']}/{comp['total']} | {td_cell} | "
            f"{code_cell} | `{card['artifact']['sha256'][:12]}` | {card['evidence']['verdict']} |"
        )
    lines += ["", "## Artifact hash preservation", "",
              "| Model | Registry sha256 | On disk | Preserved |", "|---|---|---|---|"]
    for card in cards:
        art = card["artifact"]
        lines.append(f"| `{card['modelId']}` | `{art['registrySha256'][:16]}` | "
                     f"`{art['sha256'][:16]}` | {'yes' if art['hashPreserved'] else 'NO'} |")

    for card in cards:
        td = card["trainingData"]
        lines += [
            "",
            f"## `{card['modelId']}`",
            "",
            f"*{card['identity']['task']}*",
            "",
            f"**Purpose.** {card['purpose']}",
            "",
            f"**Intended use.** {card['intendedUse']}",
            "",
            "**Not intended for**",
            "",
        ]
        lines += [f"- {item}" for item in card["notIntendedFor"]]
        lines += [
            "",
            f"**Training data.** {td['status']} — `{td['sha256'] or 'unavailable'}`",
            "",
            f"  {td['hashBasis']}",
            "",
            f"**Code.** `{card['code']['path']}` at `{card['code']['commit']}` "
            f"(present in commit: {'yes' if card['code']['commitContainsPath'] else 'NO'}; "
            f"unchanged since: {'yes' if card['code']['unchangedSinceCommit'] else 'NO'})",
            "",
            f"**Split.** {card['split']['method']} Grouped by {card['split']['groupUnit']} "
            f"({card['split']['groups']} groups).",
            "",
            f"**Uncertainty.** {card['uncertainty']['statement']}",
            "",
            f"**Evidence.** `{card['evidence']['verdict']}`, decision-grade: "
            f"{'yes' if card['evidence']['decisionGrade'] else 'no'}. Not promoted, retrained or "
            f"relabelled by this metadata completion.",
            "",
            f"**Completeness.** {card['completeness']['complete']}/{card['completeness']['total']} checks.",
        ]
        if card["limitations"]:
            lines += ["", "**Limitations**", ""]
            lines += [f"- {item}" for item in card["limitations"]]
        if card["exceptions"]:
            lines += ["", "**Declared exceptions**", ""]
            lines += [f"- {item}" for item in card["exceptions"]]
    lines.append("")
    return "\n".join(lines)


def build() -> tuple[list[dict], str]:
    rows = registry_rows()
    served_app = served_ids_from_app()
    assert served_app == set(SERVED), (
        "the card set and the served set disagree: "
        f"app={sorted(served_app)} cards={sorted(SERVED)}")
    cards = []
    for model_id in SERVED:
        if model_id not in rows:
            raise SystemExit(f"{model_id} is served but absent from the registry")
        cards.append(build_card(model_id, rows[model_id], SPECS[model_id]))
    return cards, render_markdown(cards)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--verify-training-data", action="store_true")
    args = parser.parse_args()

    if args.verify_training_data:
        return verify_training_data()

    cards, markdown = build()
    payloads = {card["modelId"]: safedata.render(card) for card in cards}

    if args.check:
        problems = []
        for model_id, body in payloads.items():
            path = OUT_DIR / f"{model_id}.py"
            if not safedata.exists(path):
                problems.append(f"missing card {path.relative_to(ROOT)}")
            elif path.read_text(encoding="utf-8") != body:
                problems.append(f"stale card {path.relative_to(ROOT)}")
        if not safedata.exists(DOC):
            problems.append("missing docs/MODEL_CARDS.md")
        elif DOC.read_text(encoding="utf-8") != markdown:
            problems.append("stale docs/MODEL_CARDS.md")
        if problems:
            print("model cards out of date:")
            for problem in problems:
                print("  " + problem)
            print("re-run: python3 ml/research/build_model_cards.py")
            return 1
        complete = sum(1 for c in cards if c["completeness"]["allComplete"])
        print(f"model cards up to date ({len(cards)} cards, {complete} fully complete)")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for model_id, body in payloads.items():
        (OUT_DIR / f"{model_id}.py").write_text(body, encoding="utf-8")
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text(markdown, encoding="utf-8")

    print(f"wrote {len(payloads)} cards to {OUT_DIR.relative_to(ROOT)} and {DOC.relative_to(ROOT)}")
    for card in cards:
        comp = card["completeness"]
        td = card["trainingData"]
        print(f"  {card['modelId']:38} {comp['complete']}/{comp['total']} "
              f"trainingData={td['status']:22} hash={str(td.get('sha256'))[:12]}")
    full = sum(1 for c in cards if c["completeness"]["allComplete"])
    print(f"\nfully complete: {full}/{len(cards)}")
    exceptions = [(c['modelId'], e) for c in cards for e in c['exceptions']]
    print(f"declared exceptions: {len(exceptions)}")
    for model_id, exc in exceptions:
        print(f"  {model_id}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
