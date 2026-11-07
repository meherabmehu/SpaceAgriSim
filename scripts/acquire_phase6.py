"""Phase 6 acquisition of newly verified NASA measurement tables.

Downloads only explicitly named, size-bounded public files from official NASA
OSDR hosts, and records provenance: study, original URL, timestamp, SHA-256,
byte count and a re-verification of the published file size.

Run: python scripts/acquire_phase6.py
Output:
    data/raw/OSD-780/...           (VEG-04A microbial plate counts)
    data/raw/OSD-670/...           (asteroid-regolith substrate chemistry)
    data/raw/OSD-120/...           (image<->sample correlation index)
    data/metadata/phase6_checksums.json
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "metadata" / "phase6_checksums.json"
UA = {"User-Agent": "SpaceAgriSim/1.0 (Phase 6 reproducible acquisition)"}

BASE = "https://osdr.nasa.gov"

# (study, exact filename as published by the OSDR files API, scientific role)
# The exact remote_url is resolved from the live API rather than hand-built, so
# that encoding differences ('+' vs '%20') cannot silently 404.
TARGETS = [
    ("OSD-780", "LSDS-128_Plate Count_Aerobic_Plate_Count_TRANSFORMED.csv",
     "VEG-04A aerobic microbial plate counts (CFU)"),
    ("OSD-780", "LSDS-128_Plate Count_Yeast_Mold_Plate_Count_Transformed.csv",
     "VEG-04A yeast/mould plate counts (CFU)"),
    ("OSD-780", "OSD-780_dictionary_DataDictionary_OSD-780.csv",
     "OSD-780 data dictionary (units and factor definitions)"),
    ("OSD-670", "OSD-670_sup_Regolith-Analysis.csv",
     "Asteroid-regolith substrate chemistry (not a plant phenotype)"),
    ("OSD-120", "OSD-120_sup_images_correlated-08-June-2023.xlsx",
     "Image-to-sample correlation index (no numeric plant phenotype)"),
]

# NASA's ALSDA measurement archive is served from the official GeneLab S3 bucket
# that the OSDR download endpoint redirects to.
ALLOWED_REDIRECTS = (
    "https://osdr.nasa.gov/",
    "https://genelab-data.ndc.nasa.gov/",
    "https://genelab-repo-prod.s3.amazonaws.com/",
    "https://genelab-alsda-repo-prod.s3.amazonaws.com/",
    "https://genelab-shared-repo-prod.s3.amazonaws.com/",
)


def fetch(url: str, attempts: int = 3, max_bytes: int = 8_000_000) -> bytes:
    if not url.startswith(BASE + "/"):
        raise ValueError("Acquisition restricted to official NASA OSDR")
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(request, timeout=120) as response:
                if not response.url.startswith(ALLOWED_REDIRECTS):
                    raise ValueError("Unexpected NASA download redirect")
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise ValueError("File exceeds the explicit download budget")
                return body
        except (OSError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def resolve_targets() -> list[tuple[str, str, int, str]]:
    """Look up each target's exact remote_url and published size from the API."""
    resolved = []
    for study, filename, role in TARGETS:
        number = study.split("-")[1]
        payload = json.loads(fetch(f"{BASE}/osdr/data/osd/files/{number}").decode())
        files = payload["studies"][study]["study_files"]
        match = next((f for f in files if f["file_name"] == filename), None)
        if match is None:
            raise FileNotFoundError(f"{study}: {filename} not present in OSDR inventory")
        resolved.append((study, match["remote_url"], match["file_size"], role))
    return resolved


def main() -> int:
    previous = {}
    if OUT.exists():
        previous = {item["path"]: item for item in json.loads(OUT.read_text())}
    records = []
    targets = resolve_targets()
    for study, path, expected, role in targets:
        from urllib.parse import unquote_plus
        name = unquote_plus(path.split("file=", 1)[1])
        if Path(name).name != name:
            raise ValueError(f"Unsafe remote filename: {name}")
        destination = DATA / "raw" / study / name
        relative = destination.relative_to(ROOT).as_posix()
        url = BASE + path
        prior = previous.get(relative)
        if destination.exists() and prior:
            body = destination.read_bytes()
            digest = hashlib.sha256(body).hexdigest()
            downloaded_at = prior.get("downloadedAt", "")
            reused = digest == prior["sha256"]
        else:
            body = fetch(url)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(body)
            digest = hashlib.sha256(body).hexdigest()
            downloaded_at = datetime.now(timezone.utc).isoformat()
            reused = False
        size_ok = len(body) == expected
        records.append({
            "studyId": study, "path": relative, "url": url,
            "sha256": digest, "bytes": len(body), "publishedBytes": expected,
            "sizeMatchesRegistry": size_ok, "downloadedAt": downloaded_at,
            "scientificRole": role, "reusedFromCache": reused,
            "verifiedAt": datetime.now(timezone.utc).isoformat(),
        })
        flag = "ok" if size_ok else "SIZE MISMATCH"
        print(f"  {study}  {len(body):>7,} B  {flag:<14} {name}")
    body = json.dumps(records, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    OUT.write_text(body, encoding="utf-8")
    print(f"\nfiles: {len(records)}")
    print(f"checksums: {OUT.relative_to(ROOT)}")
    if not all(r["sizeMatchesRegistry"] for r in records):
        print("ERROR: at least one file size differs from the OSDR registry")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
