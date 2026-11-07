"""Phase 6 NASA OSDR discovery pass.

Queries the official public OSDR APIs for every study in the verified baseline
plus the Phase 6 expansion candidates, and writes a reproducible inventory that
records *what is actually on the server* rather than what a document claims.

Official endpoints only:
    https://osdr.nasa.gov/osdr/data/osd/meta/{n}
    https://osdr.nasa.gov/osdr/data/osd/files/{n}

Run: python scripts/discover_expanded.py
Output: data/metadata/phase6_discovery.json
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "metadata" / "phase6_discovery.json"
UA = {"User-Agent": "SpaceAgriSim/1.0 (Phase 6 reproducible discovery)"}

# Verified baseline inventory (13 in the versioned acquisition path + OSD-895).
BASELINE = [267, 268, 269, 745, 766, 767, 773, 7, 120, 436, 625, 375, 655, 895]
# Phase 6 candidates named in the brief plus additional studies surfaced by
# targeted OSDR searches for plant biomass / growth / harvest measurements.
EXPANSION = [218, 307, 565, 780, 723, 412, 385, 386, 855, 883, 670]

# Categories whose presence indicates a measured (non-omics) plant phenotype
# that could in principle become a training label.
MEASUREMENT_CATEGORIES = {
    "Biomass", "Plant Growth", "Morphometric Photography", "Photography",
    "Plate Count ", "Plate Count", "Phenotypic Data", "Physiological Measurements",
}
OMICS = re.compile(r"(RNA-Seq|Microarray|Amplicon|Metagenom|Metatranscriptom|Methyl|Proteom|Metabolom)", re.I)
MEASUREMENT_TABLE = re.compile(r"\.(csv|tsv|xlsx|xls)$", re.I)


def fetch(url: str, attempts: int = 3) -> dict:
    if not url.startswith("https://osdr.nasa.gov/"):
        raise ValueError("Discovery is restricted to official NASA OSDR hosts")
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, TimeoutError):
            if attempt == attempts - 1:
                raise
    raise RuntimeError("unreachable")


def study_title(number: int) -> str:
    try:
        meta = fetch(f"https://osdr.nasa.gov/osdr/data/osd/meta/{number}")
        study = meta["study"][f"OSD-{number}"]["studies"][0]
        return study.get("title", "")
    except Exception:
        return ""


def describe(number: int) -> dict:
    sid = f"OSD-{number}"
    record = {"id": sid, "number": number,
              "metaUrl": f"https://osdr.nasa.gov/osdr/data/osd/meta/{number}",
              "filesUrl": f"https://osdr.nasa.gov/osdr/data/osd/files/{number}"}
    try:
        payload = fetch(f"https://osdr.nasa.gov/osdr/data/osd/files/{number}")
        if not payload.get("hits"):
            record["error"] = "no OSDR record"
            return record
        study = payload["studies"][sid]
        files = study.get("study_files", [])
        categories = {}
        for item in files:
            key = (item.get("category") or "unknown").strip() or "unknown"
            categories[key] = categories.get(key, 0) + 1
        tables = [item for item in files if MEASUREMENT_TABLE.search(item["file_name"])]
        measurement_tables = []
        for item in tables:
            category = (item.get("category") or "").strip()
            if OMICS.search(category) or OMICS.search(item["file_name"]):
                continue
            measurement_tables.append({
                "name": item["file_name"],
                "bytes": item.get("file_size"),
                "category": category,
                "url": "https://osdr.nasa.gov" + (item.get("remote_url") or ""),
            })
        raw_bytes = sum(item.get("file_size") or 0 for item in files)
        record.update({
            "title": study_title(number),
            "fileCount": study.get("file_count", len(files)),
            "totalBytes": raw_bytes,
            "categories": categories,
            "hasMeasurementCategory": sorted(c for c in categories if c in MEASUREMENT_CATEGORIES),
            "tabularFiles": len(tables),
            "measurementTables": sorted(measurement_tables, key=lambda x: x["name"]),
            "verifiedAt": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:  # pragma: no cover - network dependent
        record["error"] = repr(exc)
    return record


def main() -> int:
    numbers = BASELINE + EXPANSION
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(describe, numbers))
    for record in records:
        record["inBaseline"] = record["number"] in BASELINE
        record["inExpansion"] = record["number"] in EXPANSION

    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "NASA OSDR official public study and file APIs",
        "baselineIds": [f"OSD-{n}" for n in BASELINE],
        "expansionIds": [f"OSD-{n}" for n in EXPANSION],
        "studies": records,
    }
    body = json.dumps(payload, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(body, encoding="utf-8")
    digest = hashlib.sha256(body.encode()).hexdigest()

    ok = [r for r in records if "error" not in r]
    print(f"studies queried : {len(records)}")
    print(f"studies resolved: {len(ok)}")
    print(f"with measurement tables: {sum(1 for r in ok if r['measurementTables'])}")
    print(f"output          : {OUT.relative_to(ROOT)}")
    print(f"sha256          : {digest}")
    for record in records:
        if "error" in record:
            print(f"  {record['id']:<9} ERROR {record['error']}")
        else:
            tag = "BASE" if record["inBaseline"] else "NEW "
            print(f"  {tag} {record['id']:<9} files={record['fileCount']:<4} "
                  f"bytes={record['totalBytes']:>12,}  measurement_tables={len(record['measurementTables'])}")
    return 0 if len(ok) == len(records) else 1


if __name__ == "__main__":
    sys.exit(main())
