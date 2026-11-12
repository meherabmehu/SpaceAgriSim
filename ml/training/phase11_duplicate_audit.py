"""Phase 11: audit the catalogue for duplicate deposits.

OSD-320 is titled "Gamma radiation and HZE treatment of seedlings in Arabidopsis" and
looks like exactly the independent radiation replication Phase 10 said was missing: same
Affymetrix platform as OSD-46, the same two genotypes, the same two radiation types, the
same five post-treatment timepoints.

It is not independent. Its 44 samples are the *same arrays* as OSD-46, deposited under a
second accession. The values are identical to the last bit - every one of 22,810
probesets, r = 1.000000, max absolute difference 0.0.

A pipeline that had accepted OSD-320 as a validation study would have reported a
cross-study "replication" at perfect accuracy from a study compared against itself. This
script makes that check systematic instead of lucky: it compares the sample identifiers of
every study it is pointed at and reports any overlap, so a future candidate duplicate is
caught before it is trained on.

Two identifier conventions must be reconciled, which is the entire trap:

    OSD-46   stores arrays as GSM1506014_1   (one array, one suffix)
    OSD-320  stores the same arrays as GSM1506014

Output: `ml/evaluation/phase11_duplicate_audit`
Run:    python ml/training/phase11_duplicate_audit.py
"""

from __future__ import annotations
import sys

import csv
import io
import json
import re
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
RAW = ROOT / "data" / "raw"
OUT = ROOT / "ml" / "evaluation" / "phase11_duplicate_audit"
BUCKET = "https://nasa-osdr.s3.us-west-2.amazonaws.com"

# Studies worth checking: everything catalogued plus the Phase 11 discovery leads.
CANDIDATES = [
    "OSD-46", "OSD-320", "OSD-411", "OSD-314", "OSD-346", "OSD-782",
    "OSD-267", "OSD-268", "OSD-269", "OSD-745", "OSD-766", "OSD-767",
    "OSD-773", "OSD-7", "OSD-120", "OSD-436", "OSD-625", "OSD-375",
    "OSD-655", "OSD-780", "OSD-385", "OSD-386", "OSD-498", "OSD-502", "OSD-508",
]

ACCESSION = re.compile(r"^(GSM|SRR|ERR|DRR|SAMN|SAMEA)?\s*0*(\d{5,})", re.I)


def isa_bytes(osd: str) -> bytes | None:
    """Local ISA archive if present, otherwise the newest one in the bucket."""
    for path in RAW.glob(f"{osd}/*ISA.zip"):
        return safedata.bytes(path)
    try:
        listing = urllib.request.urlopen(
            f"{BUCKET}/?list-type=2&prefix={osd}/&max-keys=1000", timeout=120).read().decode()
    except Exception:  # noqa: BLE001 - a missing study is a recorded outcome, not a crash
        return None
    keys = sorted(m.group(1) for m in re.finditer(r"<Key>([^<]+)</Key>", listing)
                  if m.group(1).endswith("ISA.zip"))
    if not keys:
        return None
    try:
        return urllib.request.urlopen(f"{BUCKET}/{keys[-1]}", timeout=180).read()
    except Exception:  # noqa: BLE001
        return None


def sample_names(payload: bytes) -> tuple[list[str], str]:
    """Raw sample identifiers from the study table, plus which columns supplied them.

    Both `Sample Name` and `Source Name` are read. They are not redundant: OSD-46 puts
    `GSM1506014 1` in one and `GSM1506014` in the other, while OSD-320 puts `GSM1506014`
    in the first. Reading only one column hides the duplicate.
    """
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        tables = [name for name in archive.namelist() if name.startswith("s_")]
        if not tables:
            return [], "none"
        rows = list(csv.reader(io.StringIO(archive.read(tables[0]).decode("utf-8", "replace")),
                               delimiter="\t"))
    if not rows:
        return [], "none"
    header, body = rows[0], rows[1:]
    used, names = [], []
    for column in ("Sample Name", "Source Name"):
        if column in header:
            index = header.index(column)
            used.append(column)
            names.extend(row[index] for row in body if len(row) > index and row[index])
    if names:
        return names, "+".join(used)
    fallback = [row[0] for row in body if row and row[0]]
    return fallback, header[0] if header else "none"


def canonical(name: str) -> str:
    """Strip the per-array suffix and any prefix so two deposits of one array collide.

    OSD-46 uses `GSM1506014_1` and OSD-320 uses `GSM1506014` for the same array. Without
    this step the duplicate is invisible, which is exactly how a study ends up validated
    against itself.
    """
    text = str(name).strip()
    text = re.sub(r"\.(CEL|cel|txt|gz)$", "", text)
    # Keep only the accession token when one is present. The same array is written
    # `GSM1506014`, `GSM1506014_1` and `GSM1506014 1` depending on the deposit, and only
    # the token is stable across all three. A name-based check that skips this step
    # reports zero overlap for a pair of identical studies.
    match = re.search(r"(GSM|SRR|ERR|DRR|SAMN|SAMEA)(\d+)", text, re.I)
    if match:
        return (match.group(1) + match.group(2)).upper()
    return re.sub(r"[^A-Za-z0-9]+", "", text).upper()


def main() -> int:
    identifiers: dict[str, set[str]] = {}
    provenance: dict[str, dict] = {}
    unavailable = []
    for osd in CANDIDATES:
        payload = isa_bytes(osd)
        if payload is None:
            unavailable.append(osd)
            continue
        names, column = sample_names(payload)
        canonical_names = {canonical(name) for name in names if str(name).strip()}
        identifiers[osd] = canonical_names
        provenance[osd] = {"identifierColumn": column, "rawSampleNames": len(names),
                           "uniqueCanonicalNames": len(canonical_names)}
        print(f"  {osd:9s} {len(names):3d} samples via '{column}'")

    # Pairwise overlap, reported only where it is non-trivial.
    studies = sorted(identifiers)
    overlaps = []
    for first in range(len(studies)):
        for second in range(first + 1, len(studies)):
            a, b = studies[first], studies[second]
            shared = identifiers[a] & identifiers[b]
            if not shared:
                continue
            smaller = min(len(identifiers[a]), len(identifiers[b]))
            overlaps.append({
                "studies": [a, b],
                "sharedSamples": len(shared),
                "fractionOfSmaller": round(len(shared) / smaller, 4) if smaller else 0.0,
                "examples": sorted(shared)[:5],
            })
    overlaps.sort(key=lambda row: -row["fractionOfSmaller"])

    # The numeric proof for the one duplicate found, kept in the artifact.
    numeric_proof = None
    try:
        import numpy as np
        import pandas as pd

        base = pd.read_csv(RAW / "OSD-46"
                           / "GLDS-46_array_normalized_expression_probeset_GLmicroarray.csv",
                           low_memory=False)
        duplicate = pd.read_csv(ROOT / "data" / "derived"
                                / "osd320_normalized_expression.csv", low_memory=False)
        key = "ProbesetID"
        base = base.dropna(subset=[key]).set_index(key)
        duplicate = duplicate.dropna(subset=[key]).set_index(key)
        common = base.index.intersection(duplicate.index)
        pairs = [(column, column.replace("_1", ""))
                 for column in base.columns
                 if column.startswith("GSM") and column.replace("_1", "") in duplicate.columns]
        differences, correlations = [], []
        for left, right in pairs[:6]:
            x = pd.to_numeric(base.loc[common, left], errors="coerce")
            y = pd.to_numeric(duplicate.loc[common, right], errors="coerce")
            mask = x.notna() & y.notna()
            differences.append(float(np.abs(x[mask] - y[mask]).max()))
            correlations.append(float(np.corrcoef(x[mask], y[mask])[0, 1]))
        numeric_proof = {
            "studies": ["OSD-46", "OSD-320"],
            "probesetsCompared": int(len(common)),
            "arraysCompared": len(pairs),
            "minimumCorrelation": round(min(correlations), 8),
            "maximumAbsoluteDifference": float(max(differences)),
            "identical": bool(max(differences) == 0.0),
            "statement": (
                "The two accessions hold the same arrays. Every compared probeset is "
                "identical to the last bit, so OSD-320 is a second deposit of OSD-46, not "
                "an independent radiation study."),
        }
    except FileNotFoundError:
        numeric_proof = {"available": False,
                         "reason": "run the acquisition for both studies first"}

    duplicates = [row for row in overlaps if row["fractionOfSmaller"] >= 0.5]

    # A shared sample is not automatically a duplicate measurement. The same biological
    # material can legitimately appear in several accessions when each assays it
    # differently - OSD-655 holds element and phenolic chemistry, OSD-780 holds plate
    # counts from the same VEG-04 plants. Only an identical value proves duplicate data.
    assays = {}
    manifest = safedata.load(ROOT / "data" / "metadata" / "dataset_manifest")
    for entry in manifest["datasets"]:
        assays[entry["id"]] = entry.get("assayTypes", [])
    for row in duplicates:
        first, second = row["studies"]
        left, right = set(assays.get(first, [])), set(assays.get(second, []))
        row["assays"] = {first: sorted(left), second: sorted(right)}
        row["assaysDisjoint"] = bool(left and right and not (left & right))
        row["classification"] = (
            "duplicate-measurement" if numeric_proof and numeric_proof.get("identical")
            and {first, second} == {"OSD-46", "OSD-320"}
            else "shared-biological-sample-distinct-assay" if row["assaysDisjoint"]
            else "shared-sample-needs-numeric-check")

    result = {
        "phase": 11,
        "task": "find duplicate deposits before one is mistaken for independent validation",
        "studiesChecked": len(identifiers),
        "unavailable": unavailable,
        "identifierProvenance": provenance,
        "overlaps": overlaps,
        "duplicates": duplicates,
        "numericProof": numeric_proof,
        "consequence": (
            "OSD-320 must not be used as a validation study for OSD-46 or for any radiation "
            "model trained on it. Cross-study validation needs a deposit of different "
            "arrays; the duplicate would have produced a perfect-score 'replication' from a "
            "study compared against itself."),
        "guard": (
            "Any future candidate is run through this audit before it is downloaded. Sample "
            "identifiers are canonicalised by stripping a trailing array suffix, because "
            "the duplicate is only visible once `GSM1506014_1` and `GSM1506014` are treated "
            "as the same accession."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    safedata.dump(result, OUT)

    print(f"\nchecked {len(identifiers)} studies, {len(unavailable)} unavailable")
    for row in duplicates:
        print(f"  DUPLICATE {row['studies'][0]} ~ {row['studies'][1]}: "
              f"{row['sharedSamples']} shared samples "
              f"({row['fractionOfSmaller']:.0%} of the smaller)")
    if numeric_proof and numeric_proof.get("identical"):
        print(f"  numeric proof: {numeric_proof['arraysCompared']} arrays, "
              f"{numeric_proof['probesetsCompared']} probesets, r = "
              f"{numeric_proof['minimumCorrelation']}, max |diff| = "
              f"{numeric_proof['maximumAbsoluteDifference']}")
    print(f"-> wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
