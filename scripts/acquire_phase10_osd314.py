"""Phase 10: acquire OSD-314, the first graded-gravity plant study in the catalogue.

Why this study
--------------
Phase 9 recorded that no plant study with processed expression and a real partial
gravity manipulation existed, on the evidence of OSD-480 being raw FASTQ only. A Phase
10 metadata scan over all 231 studies with a usable processed matrix found OSD-314:
Arabidopsis on the ISS, with a subset centrifuged to **0.34 g in orbit**, alongside
microgravity and a 1 g ground control, every level crossed against red light and dark.

That makes it the first dataset in this repository whose gravity label is a gravity
level rather than a reorientation direction.

Provenance discipline
---------------------
Same rule as `acquire_phase9.py`: every file is pinned by byte length and SHA-256, and
a download that does not match is rejected rather than used. Nothing here is
re-downloaded if it already matches, so the script is safe to re-run.

Only the small, citable files are acquired. The 70 MB differential expression table is
read once by the analysis script for corroboration and is not committed.

Run: python scripts/acquire_phase10_osd314.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "raw" / "OSD-314"
BASE = "https://nasa-osdr.s3.us-west-2.amazonaws.com/OSD-314/version-6"

FILES = {
    "GLDS-314_rna_seq_Normalized_Counts.csv": (
        "rna_seq", 6_960_192,
        "7eb1f8323f6d7a9f8119ec1f0728ee5ab658775749c4f1f4b2868fd200dd904c"),
    "GLDS-314_rna_seq_RSEM_Unnormalized_Counts.csv": (
        "rna_seq", 2_370_109,
        "4bf5433105b739623931cb76a834cd53622b53f3117b8463810b737507ea064b"),
    "GLDS-314_rna_seq_SampleTable_GLbulkRNAseq.csv": (
        "rna_seq", 1_354,
        "7a16604ab8357289ff8aa142ba0f508400f611525a88bf942a6a8706d2d2535a"),
    "GLDS-314_rna_seq_bulkRNASeq_v1_runsheet.csv": (
        "rna_seq", 7_397,
        "bed77300a1511fb66aa7a5e6ccca05aafc400ff7b8ec3b05e74791f622c26c96"),
    "GLDS-314_rna_seq_contrasts_GLbulkRNAseq.csv": (
        "rna_seq", 6_091,
        "af42f2b7740c0bfc1c8cda9150304c693a53139390d79e96a2430c790fa4f1a3"),
    "GLDS-314_rna_seq_software_versions_GLbulkRNAseq.md": (
        "rna_seq", 2_352,
        "23a1677dc6a91519bf5bc4d408c2cc22ad28bc401f62ad3d83584a30e8591276"),
    "OSD-314_metadata_GLDS-314-ISA.zip": (
        "metadata", 90_981,
        "132a37b9a97f39b4c96204aa9314ad8f59ebd6eb8edd8c67c2d0311f24a8f2c2"),
}


def digest(path: Path) -> tuple[int, str]:
    payload = path.read_bytes()
    return len(payload), hashlib.sha256(payload).hexdigest()


def acquire(name: str, subdir: str, size: int, sha: str) -> dict:
    target = DEST / name
    if target.exists():
        actual_size, actual_sha = digest(target)
        if actual_size == size and actual_sha == sha:
            return {"name": name, "sha256": sha, "bytes": size, "status": "verified-cached"}
    started = datetime.now(timezone.utc).isoformat()
    with urllib.request.urlopen(f"{BASE}/{subdir}/{name}", timeout=180) as reply:
        payload = reply.read()
    actual_size, actual_sha = len(payload), hashlib.sha256(payload).hexdigest()
    if actual_size != size or actual_sha != sha:
        raise SystemExit(
            f"REJECTED {name}: expected {size} B / {sha}, got {actual_size} B / {actual_sha}")
    DEST.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return {"name": name, "sha256": sha, "bytes": size, "status": "downloaded",
            "verifiedAt": started}


def catalogue_entry(files: list[dict]) -> dict:
    """The dataset manifest entry, written with its limits attached."""
    return {
        "id": "OSD-314",
        "title": ("Adaptive response of Arabidopsis seedlings in microgravity and Mars "
                  "reduced gravity environment is enhanced by red light photostimulation"),
        "description": (
            "Arabidopsis thaliana Col-0 seedlings flown to the ISS, with a subset "
            "centrifuged in orbit to 0.34 g, alongside microgravity samples and a 1 g "
            "ground control. Every gravity level is crossed with a red-light and a dark "
            "treatment. Processed RNA-seq abundance tables are published."),
        "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-314",
        "metadataUrl": "https://osdr.nasa.gov/osdr/data/osd/meta/314",
        "filesUrl": "https://osdr.nasa.gov/osdr/data/osd/files/314",
        "metadataSha256": next(f["sha256"] for f in files
                               if f["name"].endswith("ISA.zip")),
        "version": 6,
        "verifiedAt": datetime.now(timezone.utc).isoformat(),
        "organisms": ["Arabidopsis thaliana"],
        "assayTypes": ["RNA Sequencing (RNA-Seq)"],
        "sampleCount": 17,
        "sampleCountDefinition": (
            "17 libraries over 6 conditions: 3 gravity levels (0 g, 0.34 g, 1 g) x 2 "
            "light treatments (red, dark), with 2-3 replicates per cell."),
        "fileCount": len(files),
        "factors": ["Spaceflight", "Altered Gravity", "Light"],
        "publications": [],
        "trainingEligibility": (
            "Analysis only. Usable for measuring whether a graded gravity signal exists; "
            "not eligible as a servable predictor, because 17 libraries in one genotype "
            "and one mission cannot support one, and because two of the three gravity "
            "levels are confounded with flight versus ground."),
        "status": "analysed-not-served",
        "license": "CC-BY-4.0",
        "licenseUrl": "https://creativecommons.org/licenses/by/4.0/",
        "limitations": [
            "1 g samples are ground controls and 0 g / 0.34 g samples are in orbit, so "
            "gravity is confounded with flight across all three levels.",
            "The deposit carries no sequencing-run identifier, so a library-prep batch "
            "effect cannot be excluded from the record alone.",
            "17 libraries, one genotype (Col-0), one mission, 2-3 replicates per cell.",
            "0.34 g is a centrifugation level, not Moon (0.17 g) or Mars (0.38 g) "
            "gravity, and no prediction at those levels is claimed.",
        ],
        "files": [{"name": f["name"], "sha256": f["sha256"], "bytes": f["bytes"]}
                  for f in files],
        "sampleCountReconciliation": (
            "17 libraries in the sample table and 17 columns in the normalised count "
            "matrix agree; the deposit holds no sample that lacks expression."),
        "gravityLevelsG": [0.0, 0.34, 1.0],
        "acquisition": "scripts/acquire_phase10_osd314.py",
    }


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    files = [acquire(name, subdir, size, sha)
             for name, (subdir, size, sha) in FILES.items()]
    for entry in files:
        print(f"  {entry['status']:16s} {entry['bytes']:>9,} B  {entry['name']}")

    manifest_path = ROOT / "data" / "metadata" / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    existing = {entry["id"] for entry in manifest["datasets"]}
    if "OSD-314" in existing:
        manifest["datasets"] = [entry for entry in manifest["datasets"]
                                if entry["id"] != "OSD-314"]
    manifest["datasets"].append(catalogue_entry(files))
    manifest["datasets"].sort(key=lambda entry: entry["id"])
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"catalogue now holds {len(manifest['datasets'])} NASA datasets "
          f"(OSD-314 added or refreshed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
