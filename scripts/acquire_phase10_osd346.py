"""Phase 10: acquire OSD-346, the first graded-gravity series with eight levels.

Why this study
--------------
OSD-314 gave a within-flight 0 g versus 0.34 g contrast, in one genotype, on 17
libraries, in two folds. One experiment cannot establish that a partial-gravity signal
is a general property of plant transcriptomes. OSD-346 is the independent replication:

  * Arabidopsis phytochrome mutants (phyA and phyB) flown to the ISS
  * **six commanded gravity levels covering 0 to 1 g**, with the realised level
    recorded per library as `Parameter Value[Actual Gravity Level]`
  * two independent light treatments per genotype, each containing the full gravity
    series, so a whole treatment can be held out without removing a gravity level
  * 36 libraries with per-sample RSEM gene quantifications

That last design property is what makes it usable: the same test that was honest in
OSD-314 - train on one light treatment, test on the other - is available again, and it
removes nothing from the gravity range.

Provenance discipline
---------------------
The deposit publishes one `.genes.results` file per library rather than a matrix. All
36 are downloaded, pinned by SHA-256 in `data/metadata/osd346_checksums`, and
combined here. The 73 MB of raw per-sample files are **not committed**; the checksums
are, so the matrix can be rebuilt byte-identically without storing them.

Run: python scripts/acquire_phase10_osd346.py
"""

from __future__ import annotations
import sys

import csv
import hashlib
import io
import json
import re
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
RAW = ROOT / "data" / "raw" / "OSD-346"
PROCESSED = ROOT / "data" / "processed"
# The combined matrix is 6 MB. data/processed is bundled into the API image, whose
# packager refuses assets over 2 MB, and this matrix backs an analysis rather than an
# inference endpoint, so it lives in data/derived.
DERIVED = ROOT / "data" / "derived"
CHECKSUMS = ROOT / "data" / "metadata" / "osd346_checksums"

BUCKET = "https://nasa-osdr.s3.us-west-2.amazonaws.com"
VERSION = "OSD-346/version-5"
ISA = f"{VERSION}/metadata/OSD-346_metadata_OSD-346-ISA.zip"

MIN_DETECTED_FRACTION = 0.5


def listing() -> list[str]:
    url = f"{BUCKET}/?list-type=2&prefix={VERSION}/&max-keys=1000"
    body = urllib.request.urlopen(url, timeout=180).read().decode()
    return sorted(m.group(1) for m in re.finditer(r"<Key>([^<]+)</Key>", body))


def download(key: str) -> bytes:
    target = RAW / key.split("/")[-1]
    if safedata.exists(target):
        return safedata.bytes(target)
    payload = urllib.request.urlopen(f"{BUCKET}/{key}", timeout=300).read()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return payload


def design_table() -> pd.DataFrame:
    """One row per library, from the study's own ISA sample table."""
    payload = download(ISA)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        text = archive.read("s_OSD-346.txt").decode("utf-8", "replace")
    rows = list(csv.reader(io.StringIO(text), delimiter="\t"))
    header = rows[0]
    body = [row for row in rows[1:] if len(row) >= len(header) - 2]
    columns = {
        "sampleName": "Sample Name",
        "genotype": "Factor Value[Genotype]",
        "gravityCommanded": "Factor Value[Altered Gravity]",
        "gravityActual": "Parameter Value[Actual Gravity Level]",
        "lightTreatment": "Factor Value[Treatment]",
        "flight": "Factor Value[Spaceflight]",
    }
    index = {key: header.index(value) for key, value in columns.items()}
    frame = pd.DataFrame({key: [row[index[key]] for row in body] for key in columns})
    frame["genotypeShort"] = np.where(
        frame["genotype"].str.contains("A mutant", case=False), "phyA", "phyB")
    frame["gravityG"] = frame["gravityActual"].str.replace("G", "", regex=False).astype(float)
    frame["gravityCommandedG"] = (
        frame["gravityCommanded"].str.replace("G", "", regex=False).astype(float))
    # The deposit names files GLDS-346_rna_seq_<Sample Name>.genes.results.
    frame["file"] = "GLDS-346_rna_seq_" + frame["sampleName"] + ".genes.results"
    return frame


def matrices(files: dict[str, Path]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """TPM and expected counts, genes as rows, libraries as columns."""
    tpm, counts, reference = {}, {}, None
    for name, path in files.items():
        frame = pd.read_csv(path, sep="\t", index_col=0,
                            usecols=["gene_id", "expected_count", "TPM"])
        if reference is None:
            reference = frame.index
        elif not frame.index.equals(reference):
            raise ValueError(f"gene order differs in {name}; refusing to align silently")
        tpm[name] = frame["TPM"]
        counts[name] = frame["expected_count"]
    return pd.DataFrame(tpm, index=reference), pd.DataFrame(counts, index=reference)


def catalogue_entry(checksums: dict, design: pd.DataFrame) -> dict:
    """The dataset manifest entry, with the same limits discipline as OSD-314."""
    return {
        "id": "OSD-346",
        "title": ("RNAseq analysis of the response of Arabidopsis thaliana phytochrome "
                  "mutants (PhyA, PhyB) to fractional gravity under blue-light "
                  "stimulation during spaceflight"),
        "description": (
            "Arabidopsis thaliana phytochrome A and B mutants flown to the ISS, grown "
            "under blue light at commanded gravity levels from 0 g to 1 g. Every sample "
            "is a flight sample, and each genotype has two light treatments that each "
            "carry the full gravity series. Per-sample RSEM quantifications are "
            "published."),
        "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-346",
        "metadataUrl": "https://osdr.nasa.gov/osdr/data/osd/meta/346",
        "filesUrl": "https://osdr.nasa.gov/osdr/data/osd/files/346",
        "metadataSha256": checksums["files"]["OSD-346_metadata_OSD-346-ISA.zip"]["sha256"],
        "version": 5,
        "verifiedAt": datetime.now(timezone.utc).isoformat(),
        "organisms": ["Arabidopsis thaliana"],
        "assayTypes": ["RNA Sequencing (RNA-Seq)"],
        "sampleCount": int(len(design)),
        "sampleCountDefinition": (
            f"{len(design)} libraries: 2 genotypes x 2 light treatments, each with the "
            "commanded gravity series 0-1 g."),
        "fileCount": len(checksums["files"]),
        "factors": ["Genotype", "Spaceflight", "Altered Gravity", "Treatment"],
        "publications": [],
        "trainingEligibility": (
            "Analysis only. Used to test whether the OSD-314 partial-gravity result "
            "replicates. Not eligible as a servable predictor: 36 libraries in two "
            "mutant genotypes and one mission."),
        "status": "analysed-not-served",
        "license": "CC-BY-4.0",
        "licenseUrl": "https://creativecommons.org/licenses/by/4.0/",
        "limitations": [
            "Only phytochrome mutant genotypes (phyA, phyB); no wild type, so this is "
            "not wild-type gravity physiology.",
            "Commanded and realised gravity differ because the levels come from "
            "centrifugation; the analysis uses the realised level recorded per library.",
            "36 libraries, one mission, two light treatments per genotype.",
            "0-1 g only, and no level above 1 g, so lunar or Mars gravity is still not "
            "observed anywhere in this catalogue.",
        ],
        "files": [{"name": name, "sha256": meta["sha256"], "bytes": meta["bytes"]}
                  for name, meta in sorted(checksums["files"].items())],
        "sampleCountReconciliation": (
            f"{len(design)} rows in the ISA sample table match {len(design)} per-sample "
            "quantification files; no sample lacks expression."),
        "gravityLevelsG": sorted({float(v) for v in design["gravityCommandedG"]}),
        "acquisition": "scripts/acquire_phase10_osd346.py",
        "rawCommitted": False,
        "rawNote": ("Per-sample RSEM files are 73 MB and are not committed; their "
                    "SHA-256 digests are in data/metadata/osd346_checksums."),
    }


def main() -> int:
    keys = [key for key in listing() if key.endswith(".genes.results")]
    if len(keys) != 36:
        raise SystemExit(f"expected 36 per-sample quantifications, found {len(keys)}")

    checksums = {"study": "OSD-346", "version": 5,
                 "source": f"{BUCKET}/{VERSION}", "files": {}}
    paths = {}
    for key in keys:
        name = key.split("/")[-1]
        payload = download(key)
        checksums["files"][name] = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
        }
        paths[name] = RAW / name
    isa_payload = download(ISA)
    checksums["files"][ISA.split("/")[-1]] = {
        "sha256": hashlib.sha256(isa_payload).hexdigest(), "bytes": len(isa_payload)}

    design = design_table()
    tpm, counts = matrices({row.file: paths[row.file] for row in design.itertuples()})
    tpm = tpm[list(design["file"])]
    counts = counts[list(design["file"])]

    detected = (counts > 0).mean(axis=1) >= MIN_DETECTED_FRACTION
    if int(detected.sum()) < 15000:
        raise SystemExit(f"only {int(detected.sum())} genes pass the detection filter")
    keep = tpm.loc[detected]
    expression = np.log2(keep + 1.0).round(4)
    expression.insert(0, "gene", expression.index)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    expression.to_csv(DERIVED / "osd346_partial_gravity.csv", index=False)
    design.to_csv(PROCESSED / "osd346_samples.csv", index=False)
    safedata.dump(checksums, CHECKSUMS)

    print(f"{len(design)} libraries, {int(detected.sum())} of {len(tpm)} genes pass the "
          f"detection filter")
    print("genotype x commanded gravity:")
    print(pd.crosstab(design["gravityCommandedG"], design["genotypeShort"]).to_string())
    print("light treatments:", design["lightTreatment"].nunique())
    print(f"wrote {DERIVED / 'osd346_partial_gravity.csv'} "
          f"({(DERIVED / 'osd346_partial_gravity.csv').stat().st_size/1e6:.1f} MB)")
    print(f"wrote {PROCESSED / 'osd346_samples.csv'}")

    manifest_path = ROOT / "data" / "metadata" / "dataset_manifest"
    manifest = safedata.load(manifest_path)
    manifest["datasets"] = [entry for entry in manifest["datasets"]
                            if entry["id"] != "OSD-346"]
    manifest["datasets"].append(catalogue_entry(checksums, design))
    manifest["datasets"].sort(key=lambda entry: entry["id"])
    safedata.dump(manifest, manifest_path)
    print(f"catalogue now holds {len(manifest['datasets'])} NASA datasets "
          f"(OSD-346 added or refreshed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
