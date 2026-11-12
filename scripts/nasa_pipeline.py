"""Versioned NASA OSDR acquisition. No API key; bounded public downloads only."""
from __future__ import annotations
import sys

import concurrent.futures
import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
DATA = ROOT / "data"
IDS = [267, 268, 269, 745, 766, 767, 773, 7, 120, 436, 625, 375, 655]
TERMS = "https://science.nasa.gov/reference/osdr-help-terms-and-conditions/"


def stamp():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, value):
    # Phase 32: every served artifact carries its source URL, source type, licence, terms URL,
    # citation, served scope and archival status. The values live in one reviewed table
    # (ml/training/phase32_provenance.py) rather than in nine training scripts, so a retrain
    # cannot drop them and a licence correction happens in one place. `apply` never overwrites a
    # value the caller already set.
    if isinstance(value, dict) and value.get("id"):
        try:
            import sys as _sys
            from pathlib import Path as _Path
            _sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "ml" / "training"))
            from phase32_provenance import apply as _apply_provenance
            value = _apply_provenance(value)
        except ImportError:  # pragma: no cover - the table is in-repo
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    safedata.dump(value, path)


def fetch(url, attempts=3, max_bytes=12_000_000):
    if not url.startswith("https://osdr.nasa.gov/"):
        raise ValueError("Downloads must originate from official NASA OSDR")
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "SpaceAgriSim/1.0 (research reproducibility)"})
            with urllib.request.urlopen(request, timeout=90) as response:
                if not response.url.startswith(("https://osdr.nasa.gov/", "https://genelab-data.ndc.nasa.gov/", "https://genelab-repo-prod.s3.amazonaws.com/")):
                    raise ValueError("Unexpected NASA download redirect")
                body = response.read(max_bytes + 1)
                if len(body) > max_bytes:
                    raise ValueError("File exceeds explicit download size budget")
                return body
        except (OSError, TimeoutError):
            if attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)


def annotation(value):
    return value.get("annotationValue", "") if isinstance(value, dict) else str(value or "")


def discover(refresh=False):
    def one(number):
        sid = f"OSD-{number}"
        payloads = {}
        for kind in ("meta", "files"):
            cache = DATA / "metadata" / f"{sid}_{kind}"
            url = f"https://osdr.nasa.gov/osdr/data/osd/{kind}/{number}"
            if refresh or not safedata.exists(cache):
                body = fetch(url)
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_bytes(body)
            payloads[kind] = safedata.load(cache)
        investigation = payloads["meta"]["study"][sid]
        study = investigation["studies"][0]
        files = payloads["files"]["studies"][sid]["study_files"]
        samples = study.get("materials", {}).get("samples", [])
        organisms = sorted({annotation(c.get("value")) for s in samples for c in s.get("characteristics", []) if isinstance(c.get("value"), dict) and "NCBITAXON" in c["value"].get("termAccession", "")})
        assay_types = sorted({annotation(a.get("technologyType")) for a in study.get("assays", [])})
        eligibility = ("Exploratory mizuna harvest regression; nutrient assays; irrigation is supplied water, not transpiration." if number == 655 else "Nutritional assays; no direct yield labels in transformed nutrient tables." if number == 745 else "Tomato molecular flight-context classification; not biomass, disease or stress severity." if number == 767 else "Metadata/omics only in this acquisition; not eligible for direct crop-yield training.")
        return {
            "id": sid, "title": study["title"], "description": study.get("description", ""),
            "sourceUrl": f"https://osdr.nasa.gov/bio/repo/data/studies/{sid}",
            "metadataUrl": f"https://osdr.nasa.gov/osdr/data/osd/meta/{number}",
            "filesUrl": f"https://osdr.nasa.gov/osdr/data/osd/files/{number}",
            "metadataSha256": hashlib.sha256(safedata.bytes(DATA / "metadata" / f"{sid}_meta")).hexdigest(),
            "version": investigation.get("version"), "verifiedAt": stamp(),
            "organisms": organisms, "assayTypes": assay_types,
            "sampleCount": len({s["name"] for s in samples}),
            "sampleCountDefinition": "Unique study-material sample names; assay-specific counts may differ.",
            "fileCount": len(files),
            "factors": [f.get("factorName") for f in study.get("factors", [])],
            "publications": [{"title": p.get("title"), "doi": p.get("doi")} for p in study.get("publications", [])],
            "trainingEligibility": eligibility, "status": "verified-metadata",
            "license": "Public OSDR access; retain study attribution and comply with OSDR terms; do not assume every contributed file is public domain.",
            "licenseUrl": TERMS,
            "limitations": ["No matched lunar or Martian crop experiments identified in this study.", "Study metadata and assay measurements are different evidence types."],
            "files": [{"name": f["file_name"], "bytes": f["file_size"], "category": f["category"], "url": "https://osdr.nasa.gov" + f["remote_url"], "restricted": f.get("restricted", False), "downloaded": False} for f in files],
        }
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        datasets = list(pool.map(one, IDS))
    result = {"schemaVersion": 1, "generatedAt": stamp(), "source": "NASA OSDR official study and file APIs", "datasets": datasets}
    save_json(DATA / "metadata" / "dataset_manifest", result)
    return result


def download():
    manifest_path = DATA / "metadata" / "dataset_manifest"
    manifest = safedata.load(manifest_path) if safedata.exists(manifest_path) else discover()
    checksum_path = DATA / "metadata" / "download_checksums"
    previous = {r["path"]: r for r in safedata.load(checksum_path)} if safedata.exists(checksum_path) else {}
    jobs = [(d, f) for d in manifest["datasets"] for f in d["files"] if not f["restricted"] and ((d["id"] in ("OSD-655", "OSD-745") and f["name"].endswith(".csv")) or (d["id"] == "OSD-767" and "STAR_Unnormalized_Counts" in f["name"]))]
    def one(job):
        study, info = job
        if Path(info["name"]).name != info["name"]:
            raise ValueError("Unsafe remote filename")
        path = DATA / "raw" / study["id"] / info["name"]
        relative = path.relative_to(ROOT).as_posix()
        prior = previous.get(relative)
        if safedata.exists(path) and prior and hashlib.sha256(safedata.bytes(path)).hexdigest() == prior["sha256"]:
            body = safedata.bytes(path)
            acquired_at = prior.get("downloadedAt", stamp())
        else:
            body = fetch(info["url"])
            if len(body) != info["bytes"]:
                raise ValueError(f"NASA file length differs from registry: {info['name']}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
            acquired_at = stamp()
        info["downloaded"] = True
        study["status"] = "downloaded-selected-files"
        return {"path": relative, "studyId": study["id"], "url": info["url"], "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body), "downloadedAt": acquired_at}
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(one, jobs))
    save_json(checksum_path, records)
    save_json(manifest_path, manifest)
    return records


def validate():
    checks = safedata.load(DATA / "metadata" / "download_checksums")
    issues = []
    for item in checks:
        path = ROOT / item["path"]
        if not safedata.exists(path) or hashlib.sha256(safedata.bytes(path)).hexdigest() != item["sha256"]:
            issues.append(item["path"])
    report = {"checkedAt": stamp(), "filesChecked": len(checks), "integrityFailures": issues, "valid": not issues}
    save_json(DATA / "metadata" / "integrity_report", report)
    if issues:
        raise ValueError(f"Integrity check failed: {issues}")
    return report
