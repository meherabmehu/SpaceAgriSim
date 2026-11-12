"""Re-check the pinned NASA OSDR files against the live repository.

Phase 14 pinned every committed NASA file with a SHA-256 that was computed from the bytes
actually downloaded. A pin is only meaningful while it still describes what the repository
serves today, and a static manifest cannot tell you that. This script asks the live OSDR S3
bucket, for every study in the manifest:

* whether each pinned file URL still answers, and with the same byte count;
* whether a newer study version directory exists than the one that was pinned;
* optionally, whether a locally present copy still hashes to the pinned SHA-256.

It writes what it saw. It never edits the manifest and never "fixes" a pin: a study whose bytes
changed is reported as changed so a human can decide whether to re-pin it.

Output: data/metadata/osdr_live_status

Run:
    python scripts/resync_osdr.py                # all studies
    python scripts/resync_osdr.py --study OSD-46 --study OSD-7
    python scripts/resync_osdr.py --verify-local # also re-hash committed raw copies
"""
from __future__ import annotations
import sys

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
MANIFEST = ROOT / "data" / "metadata" / "dataset_manifest"
OUTPUT = ROOT / "data" / "metadata" / "osdr_live_status"
BUCKET = "https://nasa-osdr.s3.us-west-2.amazonaws.com"
NS = "{http://s3.amazonaws.com/doc/2006-03-01/}"
USER_AGENT = "SpaceAgriSim/4.0 dataset provenance re-sync"
TIMEOUT = 45


def _request(url: str, method: str = "GET"):
    request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=TIMEOUT)


def _ranged_size(presigned_url: str) -> int | None:
    """Total object size from a one-byte ranged GET against a presigned URL."""
    request = urllib.request.Request(presigned_url, headers={"User-Agent": USER_AGENT,
                                                             "Range": "bytes=0-0"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return _total_bytes(response.headers.get("Content-Range"))
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Surface the redirect so the signed target can be inspected instead of followed blindly."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_NO_REDIRECT = urllib.request.build_opener(_NoRedirect)


def head(url: str, follow: int = 3) -> dict:
    """Byte count and last-modified time for one pinned file URL.

    The OSDR "download" endpoints answer 302 to a short-lived signed S3 URL, so a single HEAD
    would only report the redirect. Each hop is followed explicitly to reach the object that
    would actually be served.
    """
    target = url
    hops: list[int] = []
    for _ in range(follow + 1):
        try:
            response = _NO_REDIRECT.open(
                urllib.request.Request(target, method="HEAD", headers={"User-Agent": USER_AGENT}),
                timeout=TIMEOUT)
        except urllib.error.HTTPError as error:
            if error.code == 403 and hops:
                # The redirect target is a presigned GET URL; see the ranged GET below.
                ranged = _ranged_size(target)
                if ranged is not None:
                    return {"reachable": True, "status": 206, "bytes": ranged,
                            "lastModified": None, "redirects": hops, "method": "ranged GET"}
                return {"reachable": False, "status": 403, "error": "HTTP 403"}
            if error.code in (301, 302, 303, 307, 308):
                hops.append(error.code)
                target = error.headers.get("Location", "")
                if not target:
                    return {"reachable": False, "status": error.code,
                            "error": "redirect without a location"}
                continue
            return {"reachable": False, "status": error.code, "error": f"HTTP {error.code}"}
        except (urllib.error.URLError, OSError) as error:
            return {"reachable": False, "status": None, "error": type(error).__name__}
        with response:
            length = response.headers.get("Content-Length")
            total = _total_bytes(response.headers.get("Content-Range"))
            return {"reachable": True, "status": response.status,
                    "bytes": total if total is not None else
                             (int(length) if length and length.isdigit() else None),
                    "lastModified": response.headers.get("Last-Modified"),
                    "redirects": hops}
        # A presigned S3 URL is signed for GET, so HEAD against it answers 403. Ask for the first
        # byte instead and read the object size out of Content-Range.
    return {"reachable": False, "status": None, "error": "too many redirects"}


def _total_bytes(content_range: str | None) -> int | None:
    match = re.search(r"/(\d+)$", content_range or "")
    return int(match.group(1)) if match else None


def available_versions(study_id: str) -> list[int]:
    """Version directories the bucket currently publishes for a study."""
    number = study_id.split("-")[-1]
    url = f"{BUCKET}/?list-type=2&prefix=OSD-{number}/&delimiter=/&max-keys=100"
    try:
        with _request(url) as response:
            payload = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return []
    try:
        root = ET.fromstring(payload)
    except ET.ParseError:
        return []
    versions = []
    for prefix in root.findall(f"{NS}CommonPrefixes"):
        name = prefix.findtext(f"{NS}Prefix", "")
        match = re.search(r"version-(\d+)/$", name)
        if match:
            versions.append(int(match.group(1)))
    return sorted(versions)


def local_sha256(path: Path) -> str | None:
    if not safedata.exists(path):
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _sample(files: list[dict], limit: int) -> list[dict]:
    """The files worth asking about.

    A study like OSD-7 pins forty-odd raw CEL files plus one processed matrix. Re-checking every
    CEL would take minutes and tell us nothing the matrix does not: the files the scientific
    results actually rest on are the pinned, hashed ones. So the hashed files are checked first,
    then the rest, capped at `limit` per study, and the cap is reported alongside the result.
    """
    hashed = [entry for entry in files if entry.get("sha256")]
    rest = [entry for entry in files if not entry.get("sha256")]
    return (hashed + rest)[:limit]


def check_study(study: dict, verify_local: bool, max_files: int) -> dict:
    all_files = study.get("files", [])
    files = []
    for entry in _sample(all_files, max_files):
        url = entry.get("url") or ""
        if not url:
            # No pinned URL (metadata-only records): there is nothing to ask the repository
            # about, and inventing a status here would be worse than saying so.
            files.append({"name": entry.get("name"), "checked": False,
                          "reason": "no pinned download URL in the manifest"})
            continue
        result = {"name": entry.get("name"), "checked": True, **head(url)}
        pinned_bytes = entry.get("bytes")
        if result.get("reachable") and pinned_bytes is not None and result.get("bytes") is not None:
            result["bytesMatch"] = result["bytes"] == pinned_bytes
        if verify_local and entry.get("sha256"):
            local = ROOT / entry["localPath"] if entry.get("localPath") else None
            digest = local_sha256(local) if local else None
            result["localSha256Match"] = (digest == entry["sha256"]) if digest else None
        files.append(result)

    checked = [item for item in files if item.get("checked")]
    sampled = len(files)
    total = len(all_files)
    missing = [item for item in checked if not item.get("reachable")]
    changed = [item for item in checked if item.get("bytesMatch") is False]
    versions = available_versions(study["id"])
    pinned = study.get("version")
    newest = max(versions) if versions else None

    if not checked:
        # No pinned URL to HEAD (these records were committed from the acquisition script and
        # pinned by hash only), so the published version list is the only live signal.
        if newest is not None and pinned is not None and newest > pinned:
            verdict = "newer-version-available"
        elif versions:
            verdict = "version-only"
        else:
            verdict = "not-checkable"
    elif missing:
        verdict = "missing-files"
    elif changed:
        verdict = "bytes-changed"
    elif newest is not None and pinned is not None and newest > pinned:
        verdict = "newer-version-available"
    else:
        verdict = "unchanged"

    return {"id": study["id"], "pinnedVersion": pinned, "versionsPublished": versions,
            "latestVersion": newest, "verdict": verdict,
            "filesTotal": total, "filesChecked": sampled, "files": files}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", action="append", default=None,
                        help="limit the re-sync to specific study ids (repeatable)")
    parser.add_argument("--verify-local", action="store_true",
                        help="also re-hash locally committed raw copies against their pins")
    parser.add_argument("--max-files-per-study", type=int, default=3,
                        help="cap on files checked per study (hashed files first)")
    arguments = parser.parse_args()

    manifest = safedata.load(MANIFEST)
    studies = manifest["datasets"]
    if arguments.study:
        wanted = {value.strip().upper() for value in arguments.study}
        studies = [study for study in studies if study["id"].upper() in wanted]
        if not studies:
            print(f"no study matched {sorted(wanted)}")
            return 2

    results = [check_study(study, arguments.verify_local, arguments.max_files_per_study)
               for study in studies]
    summary: dict[str, int] = {}
    for result in results:
        summary[result["verdict"]] = summary.get(result["verdict"], 0) + 1

    payload = {
        "schemaVersion": 1,
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "source": "https://nasa-osdr.s3.us-west-2.amazonaws.com (public OSDR bucket)",
        "method": ("HEAD each pinned file URL, compare the served byte count with the pinned "
                   "count, and list the study's published version directories. File bytes are "
                   "not re-downloaded unless --verify-local is used."),
        "scope": ("verifies availability, byte count and published version, not scientific "
                  "interpretation"),
        "sampling": ("up to --max-files-per-study files per study, pinned-and-hashed files first; "
                     "filesChecked/filesTotal are recorded per study"),
        "studiesChecked": len(results),
        "verdictCounts": dict(sorted(summary.items())),
        "verifyLocal": arguments.verify_local,
        "manifestGeneratedAt": manifest.get("generatedAt"),
        "studies": results,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    safedata.dump(payload, OUTPUT)

    print(f"checked {len(results)} studies at {payload['checkedAt']}")
    for verdict, count in payload["verdictCounts"].items():
        print(f"  {verdict}: {count}")
    for result in results:
        if result["verdict"] != "unchanged":
            print(f"  ! {result['id']}: {result['verdict']} "
                  f"(pinned v{result['pinnedVersion']}, published {result['versionsPublished']})")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
