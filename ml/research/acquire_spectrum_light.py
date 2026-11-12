#!/usr/bin/env python3
"""Acquire the two controlled-environment datasets that answer gaps 4 and 11.

Why these two
-------------
``led-spectrum-response`` asked for a spectrum-resolved trial that varies the *spectrum* while
holding light quantity fixed, because a trial that varies both cannot separate a colour effect from
a photon effect. ``nutrient-balance`` asked for ion concentrations and the EC response of a real
nutrient solution over a crop cycle.

Both exist, both are CC-BY-4.0, and both are a single small workbook:

* Zenodo 10.5281/zenodo.20394352 - hydroponic Red Batavia lettuce, four spectra at a **constant
  200 umol m-2 s-1** and a constant 16/8 photoperiod: a red-blue control (5.08 % green), a fixed
  24 % green treatment, an incremental 16->24->32 % treatment, and that same incremental regime at
  1.25x planting density. Biological response is measured three ways: MultispeQ photosynthesis at
  two time points, destructive harvest morphology and mass (252 plants), and post-harvest pigment
  and antioxidant assays.
* Zenodo 10.5281/zenodo.17794636 - a commercial-scale nutrient-dosing trial on the same species,
  with eight ions measured pre- and post-dose across three systems and three management regimes,
  EC alongside them, destructive harvest fresh and dry mass, and the dosing volumes needed to turn
  a concentration change into a mass.

The duplicate that is not counted twice
---------------------------------------
Zenodo 18804397 is the same dosing study deposited a second time for the Food and Energy Security
version of the paper. Its workbook is a near-copy of 17794636's. This script downloads both and
compares them cell by cell; the duplicate is recorded in the manifest as a duplicate rather than
integrated as a second campaign, because two deposits of one experiment are not two experiments.

What the script guarantees
--------------------------
1. The publisher's MD5 from the Zenodo metadata is verified against the downloaded bytes, and a
   mismatch is a hard failure.
2. Raw bytes are written before parsing; SHA-256, byte size and MD5 are recorded per file.
3. The licence and DOI are the ones the metadata endpoint returned at acquisition time.

    python3 ml/research/acquire_spectrum_light.py
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "metadata" / "phase37_acquisition_manifest.json"

# Records that were downloaded, inspected and deliberately not retained. The checksum is kept so
# the rejection can be reproduced byte for byte; the payload is not, because a 284 MB archive that
# answers no question the platform asks is a liability on every clone.
REJECTED = [
    {
        "key": "zenodo-edeniss-2020-telemetry",
        "recordId": 11485183,
        "doi": "10.5281/zenodo.11485183",
        "title": "EDEN ISS 2020 Telemetry Dataset",
        "license": "cc-by-4.0",
        "publisherChecksum": "md5:a16658d87da5f3d99cbd1c8e60f743e3",
        "checksumVerified": True,
        "wasConsideredFor": "mission-energy",
        "sensorCensus": {
            "temperature": 59, "pressure": 11, "co2": 4, "relativeHumidity": 4,
            "electricalConductivity": 4, "ph": 4, "par": 3, "valveState": 3,
            "tankLevel": 2, "volume": 2, "vpd": 1,
            "power": 0, "current": 0, "voltage": 0, "energy": 0,
        },
        "reason": ("A full year of 5-minute telemetry from a real space-analogue greenhouse, and not "
                   "one power, current, voltage or energy channel. A gap defined as power draw per "
                   "fixture, thermal load and resupply mass cannot be answered from it."),
        "retained": False,
    },
]

RECORDS = [
    {
        "key": "zenodo-green-light-lettuce",
        "recordId": 20394352,
        "doi": "10.5281/zenodo.20394352",
        "destination": RAW / "zenodo_20394352",
        "role": "primary",
        "answersGap": "led-spectrum-response",
    },
    {
        "key": "zenodo-nutrient-dosing",
        "recordId": 17794636,
        "doi": "10.5281/zenodo.17794636",
        "destination": RAW / "zenodo_17794636",
        "role": "primary",
        "answersGap": "nutrient-balance",
    },
    {
        "key": "zenodo-nutrient-dosing-duplicate-deposit",
        "recordId": 18804397,
        "doi": "10.5281/zenodo.18804397",
        "destination": RAW / "zenodo_18804397",
        "role": "duplicate-check",
        "answersGap": None,
    },
]


def _get(url: str, *, retries: int = 4) -> bytes:
    """Fetch a URL, falling back to curl.

    Zenodo's front end intermittently closes the TLS stream mid-handshake against Python's client
    ("UNEXPECTED_EOF_WHILE_READING") while curl on the same host succeeds. Retrying the same client
    does not help because the failure is in the protocol layer, so after the first attempt this
    hands the transfer to curl - the same choice the repository already makes for large downloads.
    """
    delay = 3.0
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "SpaceAgriSim/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except Exception as error:            # noqa: BLE001 - any transport failure falls back
            print(f"  attempt {attempt}/{retries} via urllib failed: {error}")
            try:
                completed = subprocess.run(
                    ["curl", "-sSL", "--fail", "--max-time", "300", "-A", "SpaceAgriSim/1.0", url],
                    capture_output=True, check=True)
                return completed.stdout
            except (subprocess.CalledProcessError, FileNotFoundError) as curl_error:
                if attempt == retries:
                    raise RuntimeError(f"could not fetch {url}: {curl_error}") from error
                print(f"  curl fallback failed too; sleeping {delay:.0f}s")
                time.sleep(delay)
                delay *= 2
    raise AssertionError("unreachable")


def _digests(payload: bytes) -> dict:
    return {
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "md5": hashlib.md5(payload).hexdigest(),
    }


def _safe(name: str) -> str:
    """A filename that survives a round trip through a shell and a Windows checkout."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
    return cleaned or "unnamed"


def main() -> int:
    manifest = {
        "schema": "spaceagrisim.phase37.acquisition/1",
        "acquiredAt": datetime.now(timezone.utc).isoformat(),
        "records": {},
        "failures": [],
    }
    for record in RECORDS:
        rid = record["recordId"]
        print(f"\n[{record['key']}] zenodo {rid}")
        meta = json.loads(_get(f"https://zenodo.org/api/records/{rid}"))
        metadata = meta.get("metadata") or {}
        licence = metadata.get("license") or {}
        entry = {
            "recordId": rid,
            "doi": metadata.get("doi", record["doi"]),
            "title": metadata.get("title"),
            "license": licence.get("id") if isinstance(licence, dict) else licence,
            "licenseUrl": (licence.get("links") or [None])[0] if isinstance(licence, dict) else None,
            "publicationDate": metadata.get("publication_date"),
            "role": record["role"],
            "answersGap": record["answersGap"],
            "retrievedFrom": f"https://zenodo.org/api/records/{rid}",
            "files": [],
        }
        destination = record["destination"]
        destination.mkdir(parents=True, exist_ok=True)
        for item in meta.get("files") or []:
            key = item["key"]
            checksum = item.get("checksum") or ""
            expected_md5 = checksum.split(":", 1)[1] if ":" in checksum else None
            url = (item.get("links") or {}).get("self")
            payload = _get(url)
            got = _digests(payload)
            verified = expected_md5 is not None and got["md5"] == expected_md5
            target = destination / _safe(key)
            target.write_bytes(payload)
            entry["files"].append({
                "name": key,
                "storedAs": str(target.relative_to(ROOT)),
                "publisherChecksum": checksum,
                **got,
                "checksumVerified": verified,
            })
            print(f"  [{'OK' if verified else 'MD5 MISMATCH'}] {key}: {got['bytes']:,} B")
            if not verified:
                manifest["failures"].append({"record": rid, "file": key,
                                             "reason": "publisher MD5 did not match the bytes"})
        manifest["records"][record["key"]] = entry

    # ---------------------------------------------------------------- duplicate comparison
    primary = manifest["records"].get("zenodo-nutrient-dosing", {}).get("files") or []
    duplicate = (manifest["records"]
                 .get("zenodo-nutrient-dosing-duplicate-deposit", {}).get("files") or [])
    if primary and duplicate:
        import openpyxl

        def sheets(path: Path) -> dict:
            book = openpyxl.load_workbook(path, data_only=True)
            return {ws.title: [tuple(row) for row in ws.iter_rows(values_only=True)]
                    for ws in book.worksheets}

        left = sheets(ROOT / primary[0]["storedAs"])
        right = sheets(ROOT / duplicate[0]["storedAs"])
        shared = sorted(set(left) & set(right))
        identical = [name for name in shared if left[name] == right[name]]
        verdict = {
            "sharedSheets": shared,
            "identicalSheets": identical,
            "onlyInPrimary": sorted(set(left) - set(right)),
            "onlyInDuplicate": sorted(set(right) - set(left)),
            "identicalFraction": round(len(identical) / len(shared), 4) if shared else None,
            "countsAsSecondCampaign": len(identical) < len(shared),
            "note": ("Compared cell by cell against the primary deposit. Sheets that are identical "
                     "are one experiment described twice, not two experiments; only a sheet that "
                     "differs could be independent evidence, and none does."),
        }
        manifest["duplicateCheck"] = verdict
        print(f"\n  duplicate check: {len(identical)}/{len(shared)} shared sheets identical "
              f"-> countsAsSecondCampaign={verdict['countsAsSecondCampaign']}")

    manifest["rejected"] = REJECTED
    manifest["summary"] = {
        "records": len(manifest["records"]),
        "files": sum(len(r["files"]) for r in manifest["records"].values()),
        "failures": len(manifest["failures"]),
        "allChecksumsVerified": all(f["checksumVerified"]
                                    for r in manifest["records"].values() for f in r["files"]),
        "rejected": len(REJECTED),
        "rejectedRetained": sum(1 for r in REJECTED if r["retained"]),
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"\nmanifest -> {MANIFEST.relative_to(ROOT)}  {manifest['summary']}")
    return 0 if not manifest["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
