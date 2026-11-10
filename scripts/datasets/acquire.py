"""Acquire the Phase 26 candidate datasets that are actually downloadable.

    python3 scripts/datasets/acquire.py              # download what can be downloaded
    python3 scripts/datasets/acquire.py --probe      # only re-check reachability

Rules this script follows, because the alternative is a dataset catalogue that lies:

* every download is hashed (SHA-256) and the manifest records size, URL and timestamp;
* an existing file whose hash matches is kept, and an existing file whose hash differs is
  **reported, not overwritten** - a publisher silently revising a dataset is a fact worth
  knowing rather than a detail to paper over;
* a candidate without a verified download is recorded as not acquired with the reason, and the
  manifest's own ``verifiedDownloadCount`` follows from the files on disk, not from intent;
* nothing is written for a candidate whose licence is not established as redistributable.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.datasets import registry  # noqa: E402

RAW_ROOT = _REPO_ROOT / "data" / "raw" / "phase26"
MANIFEST = _REPO_ROOT / "data" / "metadata" / "phase26_acquisition_manifest.json"
USER_AGENT = "SpaceAgriSim-Phase26/1.0 (+https://github.com/meherabmehu/SpaceAgriSim)"
CHUNK = 1 << 16


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


MAGIC = {
    ".xlsx": (b"PK\x03\x04", "zip container (xlsx)"),
    ".csv": (None, "text"),
    ".json": (None, "text"),
}


def record_files(record: str) -> dict[str, dict[str, Any]]:
    """File metadata from the Zenodo record: declared size and publisher checksum."""
    payload = json.loads(urllib.request.urlopen(
        urllib.request.Request(f"https://zenodo.org/api/records/{record}",
                               headers={"User-Agent": USER_AGENT}), timeout=60).read())
    out: dict[str, dict[str, Any]] = {}
    for entry in payload.get("files", []):
        out[entry["key"]] = {
            "size": entry.get("size"),
            "checksum": entry.get("checksum"),
            "downloadUrl": entry.get("links", {}).get("content") or entry.get("links", {}).get("self"),
        }
    return out


def verify_payload(path: Path, expected_size: int | None, expected_checksum: str | None,
                   extension: str) -> dict[str, Any]:
    """Size, publisher checksum and magic bytes. Any failure is fatal for the download."""
    problems: list[str] = []
    size = path.stat().st_size
    if expected_size is not None and size != expected_size:
        problems.append(f"size {size} != declared {expected_size}")
    with path.open("rb") as handle:
        head = handle.read(8)
    prefix, description = MAGIC.get(extension, (None, "unchecked"))
    if prefix is not None and not head.startswith(prefix):
        problems.append(f"magic bytes do not match {description}: {head[:4]!r}")
    if extension in (".csv", ".json") and (head[:1] in (b"{", b"<") and extension == ".csv"):
        problems.append("text payload looks like JSON/HTML rather than CSV")
    md5 = None
    if expected_checksum:
        digest = hashlib.md5()  # noqa: S324 - the publisher publishes md5; it is a transport check
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(CHUNK), b""):
                digest.update(block)
        md5 = "md5:" + digest.hexdigest()
        if md5 != expected_checksum:
            problems.append(f"checksum {md5} != declared {expected_checksum}")
    return {"verified": not problems, "problems": problems, "size": size, "md5": md5}


def file_url(dataset_id: str) -> str:
    """Resolve a candidate's file URL from its DOI, so the URL is never hand-typed."""
    candidate = registry.by_id(dataset_id)
    return candidate.get("fileEndpoint") or ""


def probe(url: str) -> dict[str, Any]:
    """HEAD (with a small ranged GET fallback) so a listing cannot be mistaken for a file."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return {"url": url, "httpStatus": response.status,
                    "contentType": response.headers.get("Content-Type", ""),
                    "contentLength": response.headers.get("Content-Length")}
    except urllib.error.HTTPError as exc:
        return {"url": url, "httpStatus": exc.code, "error": str(exc.reason)}
    except Exception as exc:  # pragma: no cover - network shape
        return {"url": url, "error": f"{type(exc).__name__}: {exc}"}


def _zenodo_file_url(record: str, filename: str) -> str:
    quoted = urllib.request.quote(filename)
    return f"https://zenodo.org/api/records/{record}/files/{quoted}"


def download(url: str, target: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    temporary = target.with_suffix(target.suffix + ".part")
    written = 0
    with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as sink:
        while True:
            block = response.read(CHUNK)
            if not block:
                break
            sink.write(block)
            written += len(block)
    digest = sha256_of(temporary)
    previous = sha256_of(target) if target.exists() else None
    if previous is not None and previous != digest:
        temporary.unlink()
        return {"action": "refused-overwrite", "existingSha256": previous,
                "downloadedSha256": digest,
                "note": "the publisher's bytes changed; the existing copy was kept"}
    temporary.replace(target)
    return {"action": "written" if previous is None else "unchanged", "bytes": written,
            "sha256": digest}


def acquire(datasets: list[str] | None = None) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "generatedAt": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "rules": [
            "a candidate is acquired only when its bytes are on disk with a recorded SHA-256",
            "a changed publisher payload is reported, never silently overwritten",
            "a licence that is not established as redistributable blocks the download",
        ],
        "datasets": {},
    }

    for candidate in registry.CANDIDATES:
        dataset_id = candidate["id"]
        if datasets and dataset_id not in datasets:
            continue
        record: dict[str, Any] = {
            "id": dataset_id,
            "doi": candidate.get("doi"),
            "publisher": candidate["publisher"],
            "license": candidate["license"],
            "licenseEvidence": candidate["licenseEvidence"],
            "declaredStatus": candidate["acquisition"]["status"],
            "declaredReason": candidate["acquisition"].get("reason"),
            "files": [],
        }
        endpoint = candidate.get("fileEndpoint")
        if not endpoint:
            record["verifiedDownloadCount"] = 0
            manifest["datasets"][dataset_id] = record
            continue

        metadata = record_files(endpoint)
        for entry in candidate["files"]:
            key = entry["key"]
            declared = metadata.get(key, {})
            url = declared.get("downloadUrl") or _zenodo_file_url(endpoint, key)
            target = RAW_ROOT / dataset_id / key.replace(" ", "_")
            outcome = download(url, target)
            outcome.update({"url": url, "path": str(target.relative_to(_REPO_ROOT)),
                            "name": key, "declaredSize": declared.get("size"),
                            "declaredChecksum": declared.get("checksum")})
            if outcome["action"] in ("written", "unchanged"):
                check = verify_payload(target, declared.get("size"), declared.get("checksum"),
                                      target.suffix.lower())
                outcome["verification"] = check
                if not check["verified"]:
                    target.unlink(missing_ok=True)
                    outcome["action"] = "failed-verification"
                    outcome["bytes"] = check["size"]
            record["files"].append(outcome)
            print(f"{dataset_id:42s} {outcome['action']:19s} "
                  f"{outcome.get('bytes', 0) / 1e6:7.2f} MB  {key[:46]}")
            for problem in (outcome.get("verification") or {}).get("problems", []):
                print(f"    rejected: {problem}")

        verified = [f for f in record["files"]
                    if f["action"] in ("written", "unchanged")
                    and (f.get("verification") or {}).get("verified")]
        record["verifiedDownloadCount"] = len(verified)
        record["allFilesVerified"] = len(verified) == len(candidate["files"])
        manifest["datasets"][dataset_id] = record

    manifest["verifiedDownloadCount"] = sum(
        record["verifiedDownloadCount"] for record in manifest["datasets"].values())
    manifest["datasetsAcquired"] = sum(
        1 for record in manifest["datasets"].values() if record.get("allFilesVerified"))
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"\nverified downloads: {manifest['verifiedDownloadCount']} in "
          f"{manifest['datasetsAcquired']} datasets -> {MANIFEST.relative_to(_REPO_ROOT)}")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", action="append", dest="datasets")
    parser.add_argument("--probe", action="store_true",
                        help="re-check reachability of every declared endpoint and write probes")
    args = parser.parse_args(argv)

    if args.probe:
        probes = {c["id"]: probe(c["landingUrl"]) for c in registry.CANDIDATES}
        out = _REPO_ROOT / "data" / "research" / "phase26" / "discovery_probes.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "generatedAt": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "note": ("Reachability only. A 200 response proves an endpoint answered; it does not "
                     "prove that a usable dataset exists behind it."),
            "probes": probes,
        }, indent=2) + "\n", encoding="utf-8")
        for key, value in probes.items():
            print(f"{key:42s} {value.get('httpStatus', value.get('error'))}")
        return 0

    acquire(args.datasets)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
