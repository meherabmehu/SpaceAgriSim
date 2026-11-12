#!/usr/bin/env python3
"""Acquire the measurement tables from the IoT4Lettuce record without downloading 39 GB.

The problem
-----------
Zenodo 10.5281/zenodo.20759414 is a single 39,149 MB ``IoT4Lettuce.zip`` holding 20,679 members:
3D point clouds, images, hyperspectral cubes and a small number of CSV tables. The tables that
carry the measurements are under 300 kB in total. Downloading the archive to reach them is not
defensible in a repository that also has to stay clonable.

The method
----------
The zip central directory lives at the end of the file, and the object *does* support HTTP range
requests (its earlier metadata response advertised no ``accept-ranges`` header, which is why the
first probe concluded the archive was opaque - the actual object does support them and answers
206). So ``zipfile`` is pointed at a file-like object that fetches byte ranges on demand
(:class:`HttpRangeFile` below) and only the requested members are ever transferred.

What this does NOT establish
----------------------------
* The published MD5 (``2c7543bceec4a9c54838f6349c21bcdc``) is an MD5 of the *whole* 39 GB
  object. It cannot be checked without downloading the whole object, so it is recorded as
  unverified rather than claimed.
* Everything outside ``MEMBERS`` was not acquired. The manifest lists the member count that was
  not taken, so "the archive was inspected" can never be read as "the archive was downloaded".

    python3 ml/research/acquire_iot4lettuce.py
"""
from __future__ import annotations
import sys

import hashlib
import io
import json
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
RAW = ROOT / "data" / "raw" / "zenodo_20759414"
MANIFEST = ROOT / "data" / "metadata" / "iot4lettuce_acquisition_manifest"

RECORD = "20759414"
API = f"https://zenodo.org/api/records/{RECORD}"
ARCHIVE_BYTES = 39_149_276_870

MEMBERS = [
    "IoT4Lettuce/03_Climate/readme.md",
    "IoT4Lettuce/03_Climate/inside.csv",
    "IoT4Lettuce/03_Climate/outside.csv",
    "IoT4Lettuce/03_Climate/PAR.csv",
    "IoT4Lettuce/13_Manual_measurements/full_db.csv",
    "IoT4Lettuce/11_SPAD/full_db.csv",
    "IoT4Lettuce/14_Utilities/OpenSILEX/data.csv",
    "IoT4Lettuce/14_Utilities/OpenSILEX/scientific_objects.csv",
    "IoT4Lettuce/14_Utilities/OpenSILEX/variables.csv",
    "IoT4Lettuce/14_Utilities/OpenSILEX/devices.csv",
    "IoT4Lettuce/14_Utilities/OpenSILEX/experiment",
    "IoT4Lettuce/14_Utilities/OpenSILEX/facility",
]


class HttpRangeFile(io.RawIOBase):
    """Read-only, seekable file over HTTP range requests."""

    def __init__(self, url: str, size: int, block: int = 1 << 20):
        self.url = url
        self.size = size
        self.block = block
        self._pos = 0
        self._cache: dict[tuple[int, int], bytes] = {}
        self.requests = 0
        self.bytes_fetched = 0

    def _fetch(self, start: int, end: int) -> bytes:
        key = (start, end)
        if key in self._cache:
            return self._cache[key]
        request = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{end}"})
        with urllib.request.urlopen(request, timeout=180) as response:
            data = response.read()
        self.requests += 1
        self.bytes_fetched += len(data)
        if len(self._cache) > 128:
            self._cache.clear()
        self._cache[key] = data
        return data

    def read(self, n: int = -1) -> bytes:  # type: ignore[override]
        if n is None or n < 0:
            n = self.size - self._pos
        if n == 0 or self._pos >= self.size:
            return b""
        end = min(self._pos + n, self.size) - 1
        data = self._fetch(self._pos, end)
        self._pos += len(data)
        return data

    def seek(self, offset: int, whence: int = 0) -> int:  # type: ignore[override]
        if whence == 0:
            self._pos = offset
        elif whence == 1:
            self._pos += offset
        else:
            self._pos = self.size + offset
        return self._pos

    def tell(self) -> int:  # type: ignore[override]
        return self._pos

    def seekable(self) -> bool:  # type: ignore[override]
        return True

    def readable(self) -> bool:  # type: ignore[override]
        return True


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)

    meta = json.load(urllib.request.urlopen(API, timeout=120))
    license_block = meta.get("metadata", {}).get("license") or {}
    archive = (meta.get("files") or [{}])[0]
    url = archive.get("links", {}).get("content") or (
        f"{API}/files/{archive.get('key')}/content")

    handle = HttpRangeFile(url, size=ARCHIVE_BYTES)
    with zipfile.ZipFile(handle) as bundle:
        names = bundle.namelist()
        extracted = []
        for member in MEMBERS:
            if member not in names:
                print(f"[FAIL] {member} not present in archive")
                extracted.append({"member": member, "status": "absent"})
                continue
            payload = bundle.read(member)
            relative = Path(member).relative_to("IoT4Lettuce")
            target = RAW / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            extracted.append({
                "member": member,
                "status": "ok",
                "path": str(target.relative_to(ROOT)),
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            })
            print(f"[OK]   {member}  {len(payload)/1024:.0f} KB")
        archive_member_count = len(names)

    manifest = {
        "dataset": {
            "name": "IoT4Lettuce - multimodal high-throughput phenotyping of hydroponic lettuce",
            "doi": meta.get("doi"),
            "record": RECORD,
            "title": meta.get("metadata", {}).get("title"),
            "license": license_block.get("id"),
            "licenseUrl": license_block.get("link"),
            "publicationDate": meta.get("metadata", {}).get("publication_date"),
            "creators": [c.get("name") for c in meta.get("metadata", {}).get("creators", [])],
            "archiveKey": archive.get("key"),
            "archiveBytes": ARCHIVE_BYTES,
            "publishedMd5": archive.get("checksum"),
            "archiveMd5Verified": False,
            "archiveMd5Note": ("the published MD5 covers the whole 39 GB object; it is not "
                               "verified because the object is not downloaded whole"),
            "acquisitionMethod": ("HTTP range requests against the zip central directory; only "
                                  "the listed members are transferred"),
            "membersTotal": archive_member_count,
            "membersAcquired": sum(1 for e in extracted if e.get("status") == "ok"),
            "membersNotAcquired": archive_member_count - sum(
                1 for e in extracted if e.get("status") == "ok"),
            "bytesFetched": handle.bytes_fetched,
            "rangeRequests": handle.requests,
            "collectedAt": datetime.now(timezone.utc).isoformat(),
        },
        "members": extracted,
    }
    safedata.dump(manifest, MANIFEST)
    print(f"\nfetched {handle.bytes_fetched/1024:.0f} KB in {handle.requests} range requests "
          f"of a {ARCHIVE_BYTES/1e9:.1f} GB archive")
    print(f"manifest -> {MANIFEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
