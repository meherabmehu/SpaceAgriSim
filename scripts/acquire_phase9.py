"""Phase 9: acquire the verified NASA OSDR datasets used for the AI models.

Provenance discipline
---------------------
Every file is pinned by **expected byte length and SHA-256**, not merely by URL.
A download that does not match is rejected rather than used, so a silently
revised upstream release cannot change what the models were trained on.

Access path
-----------
`osdr.nasa.gov/geode-py/ws/...` currently answers 403 for every study, and the
GeneLab visualisation site is a single-page app with no public JSON API. The
same files are published with no restrictions in the NASA OSDR Open Data bucket
on AWS (`arn:aws:s3:::nasa-osdr`, us-west-2), which is what this script uses:

    https://nasa-osdr.s3.us-west-2.amazonaws.com/<OSD-ID>/<version>/...

Datasets acquired here
----------------------
OSD-46   Arabidopsis thaliana, Affymetrix ATH1 microarray, 44 samples.
         2 genotypes (WT, atm-1) x 3 radiation conditions (none, 100 Gy gamma,
         30 Gy Fe-56 HZE) x 5 post-irradiation timepoints.
OSD-782  Arabidopsis thaliana rosette, bulk RNA-seq, 36 samples.
         Wild type only, Cs-137 gamma at 0 / 10 / 100 Gy absorbed dose,
         4 collection times.
OSD-411  Arabidopsis thaliana, bulk RNA-seq, 64 samples.
         2 genotypes (WT, pgm-1) x 2 treatments (90-degree reorientation vs
         vertical control) x 4 tissues.

Deliberately not acquired (documented in PHASE9_DATASET_ELIGIBILITY.md):
OSD-480, OSD-772, OSD-412, OSD-413, OSD-414 publish only raw FASTQ with no
processed abundance table, so no defensible supervised dataset exists here
without a full alignment/assembly pipeline (6.2 TB for OSD-480 alone).

Run: python scripts/acquire_phase9.py
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import urllib.error
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
METADATA = ROOT / "data" / "metadata"
BUCKET = "https://nasa-osdr.s3.us-west-2.amazonaws.com"
USER_AGENT = "SpaceAgriSim/3.0 scientific reproducibility"

# Pinned by content. Any mismatch aborts the acquisition.
FILES = [
    {
        "study": "OSD-46", "name": "GLDS-46_array_normalized_expression_probeset_GLmicroarray.csv",
        "key": "OSD-46/version-6/array/GLDS-46_array_normalized_expression_probeset_GLmicroarray.csv",
        "bytes": 23_794_742,
        "sha256": "f15c4179dbbebdfd39c53ffb906f6251ed1fc3fa3c926efc3c71c4736eefda27",
        "role": "log2-normalised probeset expression, 22810 probesets x 44 samples",
    },
    {
        "study": "OSD-46", "name": "GLDS-46_array_SampleTable_GLmicroarray.csv",
        "key": "OSD-46/version-6/array/GLDS-46_array_SampleTable_GLmicroarray.csv",
        "bytes": 4_139,
        "sha256": "0ae05ae0938670bce8e923889093658eac4f9e26537197b9a54d4ad96061532e",
        "role": "sample to experimental-group assignment, 44 rows",
    },
    {
        "study": "OSD-782", "name": "GLDS-679_rna_seq_RSEM_Unnormalized_Counts_GLbulkRNAseq.csv",
        "key": "OSD-782/version-2/rna_seq/GLDS-679_rna_seq_RSEM_Unnormalized_Counts_GLbulkRNAseq.csv",
        "bytes": 4_527_540,
        "sha256": "dc98d786d7970f7258aa5474325ff4e9e19ff13b7a6c17e95282a97d924f2f9d",
        "role": "RSEM unnormalised gene counts, 32833 genes x 36 samples",
    },
    {
        "study": "OSD-782", "name": "GLDS-679_rna_seq_VST_Counts_GLbulkRNAseq.csv",
        "key": "OSD-782/version-2/rna_seq/GLDS-679_rna_seq_VST_Counts_GLbulkRNAseq.csv",
        "bytes": 14_679_817,
        "sha256": "6f1d41e0d2debeee6abb7cdce04064ee8d8afe41cb8f705c6189b5aff59caee4",
        "role": "GeneLab variance-stabilising-transformed counts, 23667 genes x 36 samples",
    },
    {
        "study": "OSD-782", "name": "OSD-782_metadata_OSD-782-ISA.zip",
        "key": "OSD-782/version-2/metadata/OSD-782_metadata_OSD-782-ISA.zip",
        "bytes": 166_136,
        "sha256": "9564320f24498ddcec0d47895bf697d04113fcdf2277d592663c8b65c83e595c",
        "role": "ISA-Tab study metadata (sample sheet, assay, investigation)",
    },
    {
        "study": "OSD-411", "name": "GLDS-411_rna_seq_RSEM_Unnormalized_Counts_GLbulkRNAseq.csv",
        "key": "OSD-411/version-4/rna_seq/GLDS-411_rna_seq_RSEM_Unnormalized_Counts_GLbulkRNAseq.csv",
        "bytes": 8_936_306,
        "sha256": "3a0d6c17473db8df6f84afe8af5648946e2ed74d686a9373ca43c71ca4cd954f",
        "role": "RSEM unnormalised gene counts, 32833 genes x 64 samples",
    },
    {
        "study": "OSD-411", "name": "GLDS-411_metadata_GLDS-411-ISA.zip",
        "key": "OSD-411/version-2/metadata/GLDS-411_metadata_GLDS-411-ISA.zip",
        "bytes": 123_676,
        "sha256": "ab6687e01802dfabffa8e891c982846e33bd7a239fe26b51a79c2b20c748870c",
        "role": "ISA-Tab study metadata (sample sheet, assay, investigation)",
    },
]

# Files above this size are fetched on demand rather than committed, following
# the same pattern as scripts/download_external_lettuce.py.
COMMIT_SIZE_LIMIT = 6_000_000


def fetch(spec: dict) -> Path:
    """Download and verify one file, or reuse a verified local copy."""
    folder = RAW / spec["study"]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / spec["name"]
    if path.is_file():
        if path.stat().st_size == spec["bytes"] and hashlib.sha256(path.read_bytes()).hexdigest() == spec["sha256"]:
            print(f"  cached+verified  {spec['study']}/{spec['name']}")
            return path
        print(f"  stale local copy, refetching {spec['name']}")
        path.unlink()
    url = f"{BUCKET}/{spec['key']}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = response.read(spec["bytes"] + 1)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"Download failed for {spec['name']}: HTTP {exc.code}") from exc
    if len(body) != spec["bytes"]:
        raise SystemExit(
            f"{spec['name']}: expected {spec['bytes']} bytes, received {len(body)}")
    digest = hashlib.sha256(body).hexdigest()
    if digest != spec["sha256"]:
        raise SystemExit(
            f"{spec['name']}: SHA-256 mismatch\n  expected {spec['sha256']}\n  received {digest}")
    path.write_bytes(body)
    print(f"  downloaded+verified {spec['study']}/{spec['name']} ({len(body):,} B)")
    return path


def read_isa_sample_sheet(archive: Path) -> tuple[list[str], list[dict]]:
    """Read the ISA-Tab sample sheet from an OSDR metadata archive."""
    with zipfile.ZipFile(archive) as zf:
        name = next(n for n in zf.namelist() if Path(n).name.startswith("s_"))
        text = zf.read(name).decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(text), delimiter="\t")
    header = next(reader)
    return header, [dict(zip(header, row)) for row in reader if row]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def build_osd46_annotations(paths: dict[str, Path]) -> dict:
    """OSD-46: parse the composite group string into analysable factors."""
    table = paths["GLDS-46_array_SampleTable_GLmicroarray.csv"]
    rows = list(csv.DictReader(table.open(encoding="utf-8")))
    annotated = []
    for row in rows:
        # Group format:
        # (age & genotype & radiation & dose & exposure duration & collection time)
        parts = [p.strip() for p in row["group"].strip("()").split("&")]
        if len(parts) != 6:
            raise SystemExit(f"Unexpected OSD-46 group layout: {row['group']!r}")
        age, genotype, radiation, dose, duration, after = parts
        annotated.append({
            "sample": row["sample"],
            "sourceGroup": row["group"],
            "ageDays": age.replace(" day", ""),
            "genotype": genotype,
            "radiation": radiation,
            "doseGy": dose.replace(" gray", ""),
            "exposureDuration": duration,
            "hoursAfterIrradiation": "" if after.startswith("nan") else after.replace(" hour", ""),
        })
    conditions = Counter(r["radiation"] for r in annotated)
    # The design is unbalanced and the code should preserve that fact rather than
    # smooth it: atm-1 has no 3 h timepoint and the non-irradiated controls carry
    # no collection time at all, so controls are 8 rather than 18.
    if conditions != Counter({"gamma radiation": 18, "Fe-56 ion radiation": 18,
                              "non-irradiated": 8}):
        raise SystemExit(f"Unexpected OSD-46 radiation balance: {dict(conditions)}")
    return {
        "rows": annotated,
        "fields": ["sample", "sourceGroup", "ageDays", "genotype", "radiation",
                   "doseGy", "exposureDuration", "hoursAfterIrradiation"],
        "samples": len(annotated),
    }


def build_osd782_annotations(paths: dict[str, Path]) -> dict:
    header, rows = read_isa_sample_sheet(paths["OSD-782_metadata_OSD-782-ISA.zip"])
    annotated = []
    for row in rows:
        annotated.append({
            "sample": row["Sample Name"],
            "organism": row.get("Characteristics[Organism]", ""),
            "ecotype": row.get("Characteristics[ecotype]", ""),
            "genotype": row.get("Characteristics[Genotype]", ""),
            "organismPart": row.get("Characteristics[organism part]", ""),
            "ionizingRadiation": row.get("Factor Value[Ionizing Radiation]", ""),
            "absorbedDoseGy": row.get("Factor Value[Absorbed Radiation Dose]", ""),
            "hoursAfterTreatment": row.get("Factor Value[Time of Sample Collection After Treatment]", ""),
        })
    doses = Counter(r["absorbedDoseGy"] for r in annotated)
    if doses != Counter({"0": 12, "10": 12, "100": 12}):
        raise SystemExit(f"Unexpected OSD-782 dose balance: {dict(doses)}")
    return {
        "rows": annotated,
        "fields": ["sample", "organism", "ecotype", "genotype", "organismPart",
                   "ionizingRadiation", "absorbedDoseGy", "hoursAfterTreatment"],
        "samples": len(annotated),
    }


def build_osd411_annotations(paths: dict[str, Path]) -> dict:
    header, rows = read_isa_sample_sheet(paths["GLDS-411_metadata_GLDS-411-ISA.zip"])
    annotated = []
    for row in rows:
        annotated.append({
            "sample": row["Sample Name"],
            "organism": row.get("Characteristics[Organism]", ""),
            "strain": row.get("Characteristics[Strain]", ""),
            "genotype": row.get("Factor Value[Genotype]", ""),
            "organismPart": row.get("Factor Value[Organism Part]", ""),
            "treatment": row.get("Factor Value[Treatment]", ""),
            "materialType": row.get("Characteristics[Material Type]", ""),
        })
    treatments = Counter(r["treatment"] for r in annotated)
    if treatments != Counter({"Reoriented": 32, "Vertical control": 32}):
        raise SystemExit(f"Unexpected OSD-411 treatment balance: {dict(treatments)}")
    return {
        "rows": annotated,
        "fields": ["sample", "organism", "strain", "genotype", "organismPart",
                   "treatment", "materialType"],
        "samples": len(annotated),
    }


def main() -> None:
    print("Phase 9 acquisition: NASA OSDR")
    paths = {spec["name"]: fetch(spec) for spec in FILES}

    osd46 = build_osd46_annotations(paths)
    osd782 = build_osd782_annotations(paths)
    osd411 = build_osd411_annotations(paths)

    write_csv(PROCESSED / "osd46_radiation_samples.csv", osd46["fields"], osd46["rows"])
    write_csv(PROCESSED / "osd782_radiation_samples.csv", osd782["fields"], osd782["rows"])
    write_csv(PROCESSED / "osd411_gravity_samples.csv", osd411["fields"], osd411["rows"])

    manifest = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "accessPath": (
            "osdr.nasa.gov GEODE API returns HTTP 403 for every study and the "
            "GeneLab visualisation site exposes no public JSON API; these files "
            "are the same releases served from the NASA OSDR Open Data S3 bucket."
        ),
        "bucket": "arn:aws:s3:::nasa-osdr (us-west-2), public, no credentials",
        "license": "NASA OSDR: no restrictions on use; attribution retained",
        "files": [
            {**{k: spec[k] for k in ("study", "name", "key", "bytes", "sha256", "role")},
             "url": f"{BUCKET}/{spec['key']}",
             "committed": spec["bytes"] <= COMMIT_SIZE_LIMIT}
            for spec in FILES
        ],
        "annotationTables": {
            "osd46": {"path": "data/processed/osd46_radiation_samples.csv", "samples": osd46["samples"]},
            "osd782": {"path": "data/processed/osd782_radiation_samples.csv", "samples": osd782["samples"]},
            "osd411": {"path": "data/processed/osd411_gravity_samples.csv", "samples": osd411["samples"]},
        },
        "excluded": {
            "OSD-480": "3208 objects, 6.2 TB, raw FASTQ only - no processed count matrix published",
            "OSD-772": "442 objects raw amplicon FASTQ; no taxonomy or OTU table published",
            "OSD-412": "87 objects raw amplicon FASTQ; no processed abundance table",
            "OSD-413": "25 objects raw amplicon FASTQ; no processed abundance table",
            "OSD-414": "21 objects raw amplicon FASTQ; no processed abundance table",
        },
    }
    METADATA.mkdir(parents=True, exist_ok=True)
    (METADATA / "phase9_nasa_datasets.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "osd46Samples": osd46["samples"],
        "osd782Samples": osd782["samples"],
        "osd411Samples": osd411["samples"],
        "committed": sum(1 for s in FILES if s["bytes"] <= COMMIT_SIZE_LIMIT),
        "onDemand": sum(1 for s in FILES if s["bytes"] > COMMIT_SIZE_LIMIT),
    }, indent=2))


if __name__ == "__main__":
    main()
