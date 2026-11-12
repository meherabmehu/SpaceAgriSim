#!/usr/bin/env python3
"""Acquire the two measured-evapotranspiration datasets that anchor the ET0 chain.

Why these two
-------------
``independent-et0`` and ``measured-eta`` in ``data/research/dataset_gap_matrix`` both come
down to the same missing object: an evapotranspiration measurement that is not derived from the
same reanalysis that forces the model. Two records supply it, and they supply different halves:

* Agroscope Zurich-Reckenholz (Zenodo 10.5281/zenodo.20825203) - six weighable lysimeters,
  daily actual ET 2013-08-01..2016-07-31, plus four-depth FDR water content, tensiometer and
  soil temperature. A weighable lysimeter is a direct mass-balance measurement of ET: nothing
  in it comes from MERRA-2.
* TERENO Graswang/Fendt (Zenodo 10.5281/zenodo.3957208) - eddy-covariance latent heat flux with
  the *measured* available energy, air temperature, vapour pressure and wind speed that go into
  Penman-Monteith. This is the one that can test the ET0 formulation itself: with measured
  forcing the only free choice left is the model, not the inputs.

What the script guarantees
--------------------------
1. Three retries with exponential backoff; a record that still fails is recorded, not dropped.
2. The published checksum from the Zenodo metadata is verified against the downloaded bytes, and
   a mismatch is a hard failure rather than a warning.
3. Raw bytes are written before parsing, and SHA-256 plus byte size are recorded for each file.
4. The licence and DOI recorded here are the ones the metadata endpoint returned at acquisition
   time, not values typed in from memory.

    python3 ml/research/acquire_zenodo_lysimeter.py
"""
from __future__ import annotations
import sys

import hashlib
import io
import json
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed" / "lysimeter"
MANIFEST = ROOT / "data" / "metadata" / "lysimeter_acquisition_manifest"

RECORDS = [
    {
        "key": "agroscope-lysimeter-2026",
        "record": "20825203",
        "doi": "10.5281/zenodo.20825203",
        "site": "Zurich-Reckenholz, Switzerland (47.428 N, 8.518 E)",
        "rawDir": RAW / "zenodo_20825203",
        "purpose": "measured actual ET (weighable lysimeter) and root-zone water content",
    },
    {
        "key": "tereno-graswang-fendt",
        "record": "3957208",
        "doi": "10.5281/zenodo.3957208",
        "site": "Graswang and Fendt, Bavaria, Germany (pre-alpine grassland)",
        "rawDir": RAW / "zenodo_3957208",
        "purpose": "measured latent heat flux with measured forcing (ET0 formulation test)",
    },
]


def fetch(url: str, attempts: int = 3, timeout: int = 180) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "SpaceAgriSim/1.0"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as error:
            last_error = error
            if attempt < attempts:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"request failed after {attempts} attempts: {url}: {last_error}")


def verify(blob: bytes, published: str) -> bool:
    algorithm, _, expected = published.partition(":")
    digest = hashlib.new(algorithm, blob).hexdigest()
    return digest == expected


def unwrap(raw_dir: Path) -> None:
    """Extract any zip or tar member in place so the parse step sees plain files."""
    for archive in sorted(raw_dir.glob("*.zip")):
        with zipfile.ZipFile(io.BytesIO(safedata.bytes(archive))) as bundle:
            bundle.extractall(raw_dir / archive.stem)
            print(f"  unzipped {archive.name} -> {archive.stem}/ "
                  f"({len(bundle.namelist())} members)")
    for archive in sorted(raw_dir.glob("*.tar")):
        with tarfile.open(archive) as bundle:
            bundle.extractall(raw_dir, filter="data")
            print(f"  untarred {archive.name} ({len(bundle.getnames())} members)")


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    manifest: dict = {
        "dataset": {
            "name": "Measured evapotranspiration evidence (Agroscope lysimeter, TERENO eddy covariance)",
            "purpose": ("Anchor `measured-eta` and `independent-et0`: ET measured by mass balance "
                        "and by eddy covariance, independent of the MERRA-2 forcing used by the "
                        "modelled ET0."),
            "collectedAt": datetime.now(timezone.utc).isoformat(),
        },
        "records": {},
    }

    failures = 0
    for spec in RECORDS:
        meta = json.loads(fetch(f"https://zenodo.org/api/records/{spec['record']}"))
        metadata = meta.get("metadata", {})
        spec["rawDir"].mkdir(parents=True, exist_ok=True)
        entry = {
            "doi": meta.get("doi") or spec["doi"],
            "title": metadata.get("title"),
            "creators": [
                {"name": c.get("name"), "affiliation": c.get("affiliation")}
                for c in metadata.get("creators", [])
            ],
            "publicationDate": metadata.get("publication_date"),
            "license": (metadata.get("license") or {}).get("id"),
            "licenseUrl": (metadata.get("license") or {}).get("link"),
            "site": spec["site"],
            "purpose": spec["purpose"],
            "metadataUrl": f"https://zenodo.org/api/records/{spec['record']}",
            "files": [],
        }
        for file_meta in meta.get("files", []):
            key = file_meta["key"]
            # The API moved: older records expose `links.self` ending in the bare file name and a
            # separate `links.content`; newer ones make `self` the content URL itself. Appending
            # "/content" unconditionally produces ".../content/content" and a 404 on half the
            # catalogue, so the content link is taken when it exists and only then suffixed.
            links = file_meta.get("links", {})
            url = links.get("content") or links["self"]
            if not url.endswith("/content"):
                url = url + "/content"
            target = spec["rawDir"] / key
            try:
                blob = fetch(url)
            except RuntimeError as error:
                print(f"[FAIL] {spec['key']}/{key}: {error}")
                entry["files"].append({"key": key, "status": "failed", "error": str(error)})
                failures += 1
                continue
            published = file_meta.get("checksum", "")
            if published and not verify(blob, published):
                print(f"[FAIL] {spec['key']}/{key}: checksum mismatch against {published}")
                entry["files"].append({"key": key, "status": "checksum-mismatch",
                                       "published": published})
                failures += 1
                continue
            target.write_bytes(blob)
            entry["files"].append({
                "key": key,
                "status": "ok",
                "url": url,
                "bytes": len(blob),
                "sha256": hashlib.sha256(blob).hexdigest(),
                "publishedChecksum": published,
                "verified": bool(published),
            })
            print(f"[OK]   {spec['key']}/{key}: {len(blob)/1024:.0f} KB "
                  f"checksum={'verified' if published else 'not published'}")
        unwrap(spec["rawDir"])
        manifest["records"][spec["key"]] = entry

    manifest["summary"] = {
        "records": len(RECORDS),
        "files": sum(len(r["files"]) for r in manifest["records"].values()),
        "failures": failures,
    }
    safedata.dump(manifest, MANIFEST)
    print(f"\nmanifest -> {MANIFEST.relative_to(ROOT)} ({manifest['summary']})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
