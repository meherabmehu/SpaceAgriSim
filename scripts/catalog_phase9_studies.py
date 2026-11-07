"""Add the Phase 9 studies to the dataset exploratory catalogue.

Why this is a separate script
-----------------------------
`scripts/discover_datasets.py` builds the catalogue by calling the OSDR REST API,
which now answers 403 for every study. The Phase 9 studies were verified from the
public S3 bucket instead, so their catalogue entries are derived from the files
that were actually acquired and checksum-verified, not from a live API call.

The catalogue matters because the UI's dataset explorer reads it. Before this
script, three studies that the Phase 9 models are trained on (OSD-46, OSD-782,
OSD-411) were absent from the explorer entirely, so a user following a model back
to its source data found nothing. It also records the sample-count reconciliation
for the two ISS lettuce microbiome studies, where the ISA sample sheet and the
processed assay table disagree.

Run: python scripts/catalog_phase9_studies.py
"""
from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
METADATA = ROOT / "data" / "metadata"
MANIFEST = METADATA / "dataset_manifest.json"

LICENSE = ("Public OSDR access; retain study attribution and comply with OSDR "
           "terms; do not assume every contributed file is public domain.")
LICENSE_URL = "https://science.nasa.gov/reference/osdr-help-terms-and-conditions/"


def isa_rows(study: str, filename: str) -> tuple[list[dict], dict]:
    path = RAW / study / filename
    with zipfile.ZipFile(path) as archive:
        files = archive.namelist()
        sample_name = next(n for n in files if n.lower().startswith("s_"))
        investigation = next(n for n in files if n.lower().startswith("i_"))
        samples = list(csv.DictReader(
            io.StringIO(archive.read(sample_name).decode("utf-8-sig", "replace")),
            delimiter="\t"))
        # The ISA investigation file is a headerless key/value table: the first
        # field is the attribute name and the second is its value. Parsing it with
        # DictReader would consume the first line as a header row and lose the
        # study title, so it is split explicitly.
        header = {}
        for line in archive.read(investigation).decode("utf-8-sig", "replace").splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0].startswith("Study"):
                header.setdefault(parts[0], parts[1])
    return samples, header


def files_from_manifest(study: str, manifest: dict) -> list[dict]:
    """Catalogue the acquired files, marking only checksum-verified ones downloaded."""
    entries = []
    for spec in manifest["files"]:
        if spec["study"] != study:
            continue
        entries.append({
            "name": spec["name"],
            "bytes": spec["bytes"],
            "category": "Processed assay data" if "metadata" not in spec["name"]
                      else "Study Metadata Files",
            "url": spec["url"],
            "restricted": False,
            # True because this file was fetched and its SHA-256 verified locally.
            "downloaded": True,
            "sha256": spec["sha256"],
            "role": spec["role"],
        })
    return entries


def build(study: str, manifest: dict) -> dict:
    if study == "OSD-46":
        samples, header = isa_rows(study, "OSD-46_metadata_OSD-46-ISA.zip")
        return {
            "id": study,
            "title": header["Study Title"],
            "description": header["Study Description"],
            "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-46",
            "metadataUrl": "https://osdr.nasa.gov/osdr/data/osd/meta/46",
            "filesUrl": "https://osdr.nasa.gov/osdr/data/osd/files/46",
            "metadataSha256": next(s["sha256"] for s in manifest["files"]
                                   if s["study"] == study
                                   and s["name"].endswith("ISA.zip")),
            "version": 6,
            "verifiedAt": datetime.now(timezone.utc).isoformat(),
            "organisms": ["Arabidopsis thaliana"],
            "assayTypes": ["Transcription profiling (Affymetrix ATH1 microarray)"],
            "sampleCount": len(samples),
            "sampleCountDefinition": (
                "44 arrays over 22 biological groups (genotype x condition x dose x "
                "timepoint x age); each group holds two replicate arrays."),
            "fileCount": len(files_from_manifest(study, manifest)),
            "factors": ["Ionizing Radiation", "Absorbed Radiation Dose", "Exposure Duration",
                        "Time of Sample Collection After Treatment", "Genotype", "Age"],
            "publications": [{
                "title": ("High atomic weight, high-energy radiation (HZE) induces "
                          "transcriptional responses shared with conventional stresses"),
                "doi": "10.3389/fpls.2014.00364",
            }],
            "trainingEligibility": (
                "Eligible and trained: radiation-quality and radiation-exposure "
                "classifiers, group-held-out. Not eligible for yield or dose-regression "
                "training."),
            "status": "verified-data",
            "license": LICENSE,
            "licenseUrl": LICENSE_URL,
            "limitations": [
                "Ground-based irradiation of Arabidopsis seedlings, not a crop and not spaceflight.",
                "Array batch is not reported in the ISA record and had to be recovered from "
                "the raw CEL headers; controls are not balanced across batches.",
                "100 Gy gamma and 30 Gy Fe-56 differ in both quality and absorbed dose.",
            ],
            "files": files_from_manifest(study, manifest),
        }

    if study == "OSD-782":
        samples, header = isa_rows(study, "OSD-782_metadata_OSD-782-ISA.zip")
        return {
            "id": study,
            "title": header["Study Title"],
            "description": header["Study Description"],
            "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-782",
            "metadataUrl": "https://osdr.nasa.gov/osdr/data/osd/meta/782",
            "filesUrl": "https://osdr.nasa.gov/osdr/data/osd/files/782",
            "metadataSha256": next(s["sha256"] for s in manifest["files"]
                                   if s["study"] == study
                                   and s["name"].endswith("ISA.zip")),
            "version": 2,
            "verifiedAt": datetime.now(timezone.utc).isoformat(),
            "organisms": ["Arabidopsis thaliana"],
            "assayTypes": ["RNA Sequencing (RNA-Seq)", "Bisulfite sequencing"],
            "sampleCount": len(samples),
            "sampleCountDefinition": (
                "36 rosette samples, 3 doses x 4 collection times x 3 replicates, "
                "so 12 independent conditions."),
            "fileCount": len(files_from_manifest(study, manifest)),
            "factors": ["Ionizing Radiation", "Absorbed Radiation Dose",
                        "Time of Sample Collection After Treatment"],
            "publications": [{
                "title": ("Multi-omics profiling reveals ethylene signalling as a key "
                          "pathway underlying responses to low-dose ionizing radiation"),
                "doi": "10.1101/2023.10.14.562363",
            }],
            "trainingEligibility": (
                "Acquired and evaluated; dose classification did NOT beat its baseline "
                "on held-out conditions, so no model is registered. Retained as a "
                "documented negative and as the cross-study transfer target."),
            "status": "verified-data",
            "license": LICENSE,
            "licenseUrl": LICENSE_URL,
            "limitations": [
                "All samples are one ecotype (Col-0) and one tissue (rosette).",
                "Dose classification failed to generalise to held-out conditions; see "
                "ml/evaluation/phase9_rnaseq_candidates.json.",
            ],
            "files": files_from_manifest(study, manifest),
        }

    if study == "OSD-411":
        samples, header = isa_rows(study, "GLDS-411_metadata_GLDS-411-ISA.zip")
        return {
            "id": study,
            "title": header["Study Title"],
            "description": header["Study Description"],
            "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-411",
            "metadataUrl": "https://osdr.nasa.gov/osdr/data/osd/meta/411",
            "filesUrl": "https://osdr.nasa.gov/osdr/data/osd/files/411",
            "metadataSha256": next(s["sha256"] for s in manifest["files"]
                                   if s["study"] == study
                                   and s["name"].endswith("ISA.zip")),
            "version": 4,
            "verifiedAt": datetime.now(timezone.utc).isoformat(),
            "organisms": ["Arabidopsis thaliana"],
            "assayTypes": ["RNA Sequencing (RNA-Seq)"],
            "sampleCount": len(samples),
            "sampleCountDefinition": (
                "64 samples from 16 seedlings (2 genotypes x 2 treatments x 4 "
                "seedlings); each seedling contributes four tissue samples, so 16 is "
                "the independent unit count, not 64."),
            "fileCount": len(files_from_manifest(study, manifest)),
            "factors": ["Genotype", "Organism Part", "Treatment"],
            "publications": [],
            "trainingEligibility": (
                "Acquired and evaluated; reorientation classification did not beat "
                "chance on held-out seedlings, so no model is registered. A 90-degree "
                "ground reorientation is not partial gravity in any case."),
            "status": "verified-data",
            "license": LICENSE,
            "licenseUrl": LICENSE_URL,
            "limitations": [
                "64 samples come from only 16 seedlings; the four tissues per seedling "
                "are repeated measures, not independent observations.",
                "One library (sample 14-4) is two orders of magnitude shallower than the "
                "rest and was excluded before modelling.",
                "Ground reorientation, not microgravity or partial gravity.",
            ],
            "files": files_from_manifest(study, manifest),
        }

    if study == "OSD-780":
        # Catalogued here because a registered model (mizuna-microbial-load-v1)
        # cites it and the explorer did not list it, so the model's source study
        # was unreachable from the UI. Provenance comes from the Phase 6 checksum
        # record, which verified these exact bytes.
        phase6 = json.loads((METADATA / "phase6_checksums.json").read_text())
        files = [{
            "name": Path(item["path"]).name,
            "bytes": item["bytes"],
            "category": "Processed assay data",
            "url": item["url"],
            "restricted": False,
            "downloaded": True,
            "sha256": item["sha256"],
            "role": item["scientificRole"],
        } for item in phase6 if item["studyId"] == "OSD-780"]
        return {
            "id": study,
            "title": "VEG-04A mizuna microbial load (plate counts)",
            "description": (
                "Aerobic and yeast/mould plate counts on mizuna harvested from the "
                "VEG-04A ISS and ground-control campaigns."),
            "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-780",
            "metadataUrl": "https://osdr.nasa.gov/osdr/data/osd/meta/780",
            "filesUrl": "https://osdr.nasa.gov/osdr/data/osd/files/780",
            "metadataSha256": None,
            "version": None,
            "verifiedAt": datetime.now(timezone.utc).isoformat(),
            "organisms": ["Brassica rapa var. nipposinica"],
            "assayTypes": ["Microbial plate counts"],
            # Two assay tables plus a data dictionary: the file count is 3 but the
            # measurement tables are 2, and neither is one row per plant.
            "sampleCount": sum("Plate_Count" in f["name"] for f in files),
            "sampleCountDefinition": (
                "Two measured assay tables (aerobic, yeast/mould) plus a data "
                "dictionary; counts are per harvest group, not per plant."),
            "fileCount": len(files),
            "factors": ["Spaceflight", "Harvest"],
            "publications": [],
            "trainingEligibility": (
                "Eligible and trained: exploratory mizuna microbial-load regressions "
                "(Phase 6/7)."),
            "status": "verified-data",
            "license": LICENSE,
            "licenseUrl": LICENSE_URL,
            "limitations": [
                "Plate counts are culture-based and do not describe total microbial load.",
                "Counts are per harvest group, so they are not independent per-plant measurements.",
            ],
            "files": files,
        }

    raise SystemExit(f"unsupported study {study}")


# Sample counts where the ISA sample sheet and the processed assay table disagree.
# Recording the disagreement is the point: a reader who sees "12 samples" in the
# explorer and 11 columns in the count table deserves an explanation.
SAMPLE_COUNT_RECONCILIATION = {
    "OSD-267": {
        "metadataSamples": 12,
        "processed16sSamples": 11,
        "explanation": (
            "The ISA sheet lists 12 samples but the processed 16S taxonomy-and-counts "
            "table has 11 columns; one sample has no processed 16S data. The Phase 9 "
            "microbiome analysis uses the 11 with data and says so."),
    },
    "OSD-269": {
        "metadataSamples": 15,
        "processed16sSamples": 15,
        "explanation": "ISA samples and processed 16S columns agree.",
    },
}


def main() -> int:
    manifest = json.loads((METADATA / "phase9_nasa_datasets.json").read_text())
    catalogue = json.loads(MANIFEST.read_text())
    existing = {entry["id"]: index for index, entry in enumerate(catalogue["datasets"])}

    for study in ("OSD-46", "OSD-782", "OSD-411", "OSD-780"):
        entry = build(study, manifest)
        if study in existing:
            catalogue["datasets"][existing[study]] = entry
            print(f"  updated {study}")
        else:
            catalogue["datasets"].append(entry)
            print(f"  added   {study}")

    for entry in catalogue["datasets"]:
        reconciliation = SAMPLE_COUNT_RECONCILIATION.get(entry["id"])
        if not reconciliation:
            continue
        entry["sampleCountReconciliation"] = reconciliation
        note = reconciliation["explanation"]
        if note not in entry.get("limitations", []):
            entry.setdefault("limitations", []).append(note)

    MANIFEST.write_text(json.dumps(catalogue, indent=2) + "\n")
    print(f"\nwrote {MANIFEST.relative_to(ROOT)} ({len(catalogue['datasets'])} datasets)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
