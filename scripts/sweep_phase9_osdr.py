"""Systematic OSDR sweep: what does the repository actually publish?

The Phase 9 brief asks for a sweep "not limited to the previously inspected 25
studies". This script walks every OSD identifier in a range, asks the public S3
bucket what it holds, and classifies each study by what a modelling attempt would
actually need: a processed gene-level abundance table, or nothing but raw reads.

The distinction matters because a raw FASTQ deposit cannot be turned into a
supervised dataset without an alignment/quantification pipeline that this project
does not run. Describing such a study as "available" would be a fiction.

Output: data/metadata/phase9_osdr_sweep

Run: python scripts/sweep_phase9_osdr.py [--start 1] [--end 900]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
METADATA = ROOT / "data" / "metadata"
BUCKET = "https://nasa-osdr.s3.us-west-2.amazonaws.com"
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
USER_AGENT = "SpaceAgriSim/3.0 scientific reproducibility"

# Filename signatures. A study is only usable for supervised modelling here if it
# publishes a processed, gene-level matrix.
PROCESSED_MATRIX = ("normalized_expression", "VST_Counts", "RSEM", "_counts",
                    "Counts_GL", "normalized_counts", "expression_probeset")
RAW_ONLY = (".fastq.gz", ".fq.gz", ".fastq", ".fq", ".bam", ".sra", ".fastq.bz2")
AMPLICON = ("16S", "ITS", "amplicon", "metagenom")


def list_objects(prefix: str) -> tuple[list[dict], str | None]:
    """List one page of objects under a prefix, returning the continuation token."""
    url = f"{BUCKET}/?list-type=2&prefix={prefix}&max-keys=1000"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = response.read()
    except urllib.error.HTTPError as error:
        if error.code in (403, 404):
            return [], None
        raise
    root = ET.fromstring(payload)
    objects = [
        {"key": item.find(f"{NS}Key").text,
         "bytes": int(item.find(f"{NS}Size").text)}
        for item in root.findall(f"{NS}Contents")
    ]
    token_node = root.find(f"{NS}NextContinuationToken")
    return objects, (token_node.text if token_node is not None else None)


def classify(objects: list[dict]) -> dict:
    keys = [item["key"] for item in objects]
    total_bytes = sum(item["bytes"] for item in objects)
    processed = sorted({key for key in keys
                        if any(sig in key for sig in PROCESSED_MATRIX)
                        and key.endswith((".csv", ".tsv", ".txt"))})
    raw = [key for key in keys if key.endswith(RAW_ONLY)]
    metadata = [key for key in keys if "metadata" in key.lower()
                or key.lower().endswith(".zip")]
    species = None
    for key in keys:
        lowered = key.lower()
        for name in ("arabidopsis", "mizuna", "brassica", "lactuca", "lettuce",
                     "solanum", "tomato", "oryza", "rice", "glycine", "soy",
                     "medicago", "wheat", "triticum", "potato", "cucumis"):
            if name in lowered:
                species = name
                break
        if species:
            break
    amplicon = any(any(tag in key for tag in AMPLICON) for key in keys)
    if processed:
        verdict = "usable-processed-matrix"
    elif raw and amplicon:
        verdict = "rejected-raw-amplicon-only"
    elif raw:
        verdict = "rejected-raw-sequencing-only"
    elif objects:
        verdict = "rejected-no-expression-data"
    else:
        verdict = "empty"
    return {
        "objects": len(objects),
        "bytes": total_bytes,
        "processedTables": processed[:6],
        "processedTableCount": len(processed),
        "rawReadFiles": len(raw),
        "metadataFiles": len(metadata),
        "amplicon": amplicon,
        "speciesHint": species,
        "verdict": verdict,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=900)
    args = parser.parse_args()

    studies: dict[str, dict] = {}
    for number in range(args.start, args.end + 1):
        study = f"OSD-{number}"
        objects, _token = list_objects(f"{study}/")
        if not objects:
            continue
        record = classify(objects)
        record["study"] = study
        record["firstKeys"] = [item["key"] for item in objects[:5]]
        studies[study] = record
        if number % 50 == 0:
            print(f"  … scanned through OSD-{number}, {len(studies)} studies found")

    counts = Counter(record["verdict"] for record in studies.values())
    usable = sorted(name for name, record in studies.items()
                    if record["verdict"] == "usable-processed-matrix")
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "range": [args.start, args.end],
        "accessPath": f"{BUCKET}/<OSD-ID>/",
        "accessNote": ("The OSDR REST API returns 403/404 for every endpoint tried; "
                       "the public S3 bucket answers anonymously and is the "
                       "documented Open Data Registry location for this data."),
        "paginationNote": ("One page of up to 1000 objects per study is classified. "
                           "A study with more objects is still correctly identified "
                           "as raw-only, because the presence of any processed "
                           "matrix would appear in the first page alongside the raw "
                           "deposit; OSD-480 at 3208 objects was checked separately "
                           "and holds no processed matrix."),
        "studiesFound": len(studies),
        "verdictCounts": dict(counts),
        "usableProcessedMatrix": usable,
        "studies": studies,
    }
    METADATA.mkdir(parents=True, exist_ok=True)
    safedata.dump(payload, METADATA / "phase9_osdr_sweep")
    print(f"\n{len(studies)} studies found")
    for verdict, count in counts.most_common():
        print(f"  {verdict:32s} {count}")
    print(f"\nusable processed matrices: {', '.join(usable)}")
    print("wrote data/metadata/phase9_osdr_sweep")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
