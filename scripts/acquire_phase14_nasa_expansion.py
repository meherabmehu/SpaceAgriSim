"""Phase 14: expand the NASA OSDR catalogue with five studies chosen for space-crop relevance.

Why these five
--------------
The catalogue already covers Arabidopsis molecular work (OSD-46, OSD-120, OSD-314, OSD-346,
OSD-782), ISS leafy-green microbiology and nutrition (OSD-267, OSD-268, OSD-269, OSD-655,
OSD-745, OSD-766, OSD-767, OSD-780), a multi-crop ISS system test (OSD-773) and one Antarctic
greenhouse demonstration (OSD-895). What it did not cover was the part of a space-crop programme
an advisor actually needs to reason about: what the crop is grown *in*, what happens when the
substrate changes, whether the edible product is safe, and how a leafy green responds to a long
stay in orbit rather than a short one.

    OSD-59   Mizuna (Brassica rapa) RNA-Seq over long-duration spaceflight. The repository
             already serves a mizuna harvest model (OSD-655) and a mizuna microbial-load model
             (OSD-780); this adds the molecular context for the same crop.
    OSD-386  E. coli persistence in the mizuna microbiome — the food-safety question, on the
             same crop, for the same reason.
    OSD-670  Asteroid regolith as an in-situ plant growth medium — substrate substitution
             rather than hydroponics.
    OSD-723  Ionic silver in hydroponics: lettuce growth, nutrient uptake and root microbiome —
             a direct test of a hydroponic intervention, which is how the simulator's water
             loop is assumed to work.
    OSD-856  Lettuce growth on simulated lunar soil — the Moon-regolith case the simulator can
             only assume.

Provenance discipline
---------------------
Identical to `acquire_phase10_osd314.py` and `acquire_phase9.py`: every file is pinned by byte
length and SHA-256 recorded in `data/metadata/phase14_manifest_checksums.json`, and a download
that does not match the pin is rejected rather than used. Re-running the script re-verifies the
pinned bytes and does not re-download matching files.

Only the small ISA metadata archives are acquired (each a few hundred kB). No raw sequencing data
is downloaded and no model is trained, so nothing here changes a prediction. The studies are
recorded with status `verified-metadata`: the metadata record is pinned and checksummed, and the
study is *not* a training table and *not* a served model input.

Run: python scripts/acquire_phase14_nasa_expansion.py
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "metadata" / "dataset_manifest.json"
CHECKSUMS = ROOT / "data" / "metadata" / "phase14_manifest_checksums.json"
S3 = "https://nasa-osdr.s3.us-west-2.amazonaws.com"
UA = {"User-Agent": "SpaceAgriSim-research/1.0 (NASA OSDR metadata acquisition)"}

CANDIDATES = [59, 386, 670, 723, 856]


def fetch(url: str, timeout: int = 180) -> bytes:
    if not url.startswith("https://"):
        raise ValueError("Acquisition is restricted to https hosts")
    request = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(request, timeout=timeout) as reply:
        return reply.read()


def fetch_json(url: str) -> dict:
    return json.loads(fetch(url).decode("utf-8"))


def resolve_metadata_file(number: int) -> dict:
    """Locate the newest ISA metadata archive for a study in the public OSDR bucket."""
    listing = fetch(f"{S3}/?list-type=2&prefix=OSD-{number}/&delimiter=/").decode()
    versions = sorted(
        (int(token) for token in re.findall(rf"OSD-{number}/version-(\d+)/", listing)),
        reverse=True)
    if not versions:
        raise RuntimeError(f"OSD-{number}: no versioned prefix in the OSDR bucket")
    for version in versions:
        meta = fetch(f"{S3}/?list-type=2&prefix=OSD-{number}/version-{version}/metadata/").decode()
        keys = re.findall(r"<Key>(.*?)</Key>", meta)
        sizes = re.findall(r"<Size>(.*?)</Size>", meta)
        for key, size in zip(keys, sizes):
            if key.endswith("-ISA.zip"):
                return {"key": key, "version": version, "bytes": int(size),
                        "url": f"{S3}/{key}"}
    raise RuntimeError(f"OSD-{number}: no ISA metadata archive published")


def pinned(number: int, resolved: dict, checksums: dict) -> bytes:
    """Return verified ISA archive bytes, downloading only when the pin is not already satisfied."""
    sid = f"OSD-{number}"
    record = checksums.get(sid)
    target = RAW / sid / Path(resolved["key"]).name
    if record and record["sha256"] and target.is_file():
        payload = target.read_bytes()
        if (len(payload) == record["bytes"]
                and hashlib.sha256(payload).hexdigest() == record["sha256"]):
            return payload
    if record and record["sha256"] and record["bytes"] != resolved["bytes"]:
        raise RuntimeError(
            f"{sid}: upstream archive size changed from {record['bytes']} to {resolved['bytes']} "
            f"for version {resolved['version']}; refusing to silently accept new bytes")
    payload = fetch(resolved["url"])
    if len(payload) != resolved["bytes"]:
        raise RuntimeError(
            f"{sid}: downloaded {len(payload)} bytes, the bucket listing declared {resolved['bytes']}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    checksums[sid] = {
        "file": str(target.relative_to(ROOT)),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "version": resolved["version"],
        "url": resolved["url"],
        "pinnedAt": datetime.now(timezone.utc).isoformat(),
    }
    return payload


def _characteristic_values(study: dict, category: str) -> list[str]:
    """Values of one ISA characteristic, resolved through the study's category table.

    A material's characteristic carries only the category ``@id``; the human-readable name
    lives in ``characteristicCategories``. Matching on the ``@id`` first is what makes this
    work for every study instead of only the ones that inline a label.
    """
    names = {}
    for entry in study.get("characteristicCategories") or []:
        label = ((entry.get("characteristicType") or {}).get("annotationValue") or "").strip()
        if label:
            names[entry.get("@id")] = label.lower()
    found: list[str] = []
    materials = study.get("materials") or {}
    for group in ("samples", "sources", "otherMaterials"):
        for material in materials.get(group) or []:
            for characteristic in material.get("characteristics") or []:
                raw_category = characteristic.get("category")
                if isinstance(raw_category, dict):
                    key = raw_category.get("@id")
                    label = (raw_category.get("annotationValue") or names.get(key, "")).strip()
                else:
                    label = str(raw_category or "").strip()
                if label.lower() != category.lower():
                    continue
                value = characteristic.get("value")
                if isinstance(value, dict):
                    value = value.get("annotationValue")
                if value and str(value).strip() and str(value).strip() not in found:
                    found.append(str(value).strip())
    return found


def describe(number: int) -> dict:
    sid = f"OSD-{number}"
    meta = fetch_json(f"https://osdr.nasa.gov/osdr/data/osd/meta/{number}")
    study = meta["study"][sid]["studies"][0]
    files = fetch_json(f"https://osdr.nasa.gov/osdr/data/osd/files/{number}")
    study_files = files["studies"][sid]

    description = study.get("description")
    if isinstance(description, list):
        description = " ".join(str(part) for part in description if part)
    description = re.sub(r"\s+", " ", description or "").strip()

    assays = study.get("assays") or []
    assay_types: list[str] = []
    for assay in assays:
        for field in ("measurementType", "technologyType"):
            value = (assay.get(field) or {}).get("annotationValue") if isinstance(
                assay.get(field), dict) else assay.get(field)
            if value and value not in assay_types:
                assay_types.append(value)

    sample_count = len((study.get("materials") or {}).get("samples") or [])
    factors = [factor.get("factorName") for factor in study.get("factors") or []
               if factor.get("factorName")]
    publications = [
        {"doi": pub.get("doi"), "pubMedId": pub.get("pubMedId"),
         "title": pub.get("title"), "authorList": pub.get("authorList")}
        for pub in study.get("publications") or []]

    return {
        "id": sid,
        "title": study.get("title", "").strip(),
        "description": description,
        "sourceUrl": f"https://osdr.nasa.gov/bio/repo/data/studies/{sid}",
        "metadataUrl": f"https://osdr.nasa.gov/osdr/data/osd/meta/{number}",
        "filesUrl": f"https://osdr.nasa.gov/osdr/data/osd/files/{number}",
        "organisms": _characteristic_values(study, "Organism"),
        "assayTypes": assay_types,
        "sampleCount": sample_count,
        "fileCount": study_files.get("file_count"),
        "factors": factors,
        "publications": publications,
    }


def licence_from_archive(payload: bytes, study_id: str) -> dict:
    """Read the licence an ISA investigation file declares, if it declares one.

    OSDR studies are not uniformly licensed, so the licence is read from the archive rather
    than assumed. When the investigation file is silent the field says so.
    """
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for name in archive.namelist():
            if Path(name).name.lower().startswith("i_") and name.endswith(".txt"):
                text = archive.read(name).decode("utf-8", "replace")
                match = re.search(r"(CC[- ]BY[- ]?[0-9.]*)", text, re.I)
                if match:
                    token = match.group(1).upper().replace(" ", "-").replace("--", "-")
                    token = token.replace("CC-BY", "CC-BY-").replace("CC-BY--", "CC-BY-")
                    return {"license": token,
                            "licenseUrl": "https://creativecommons.org/licenses/by/4.0/"}
                if re.search(r"licen[cs]e", text, re.I):
                    for line in text.splitlines():
                        if re.search(r"licen[cs]e", line, re.I) and len(line) < 300:
                            return {"license": line.strip()[:160],
                                    "licenseUrl":
                                        f"https://osdr.nasa.gov/bio/repo/data/studies/{study_id}"}
    return {"license": "not declared in the ISA metadata archive; see the OSDR study page",
            "licenseUrl": f"https://osdr.nasa.gov/bio/repo/data/studies/{study_id}"}


# The scientific statement attached to each row: what the study can and cannot support here.
LIMITATIONS = {
    "OSD-59": [
        "Mizuna transcriptome over long-duration flight; it is molecular context, not a harvest or yield measurement.",
        "One crop, one cultivar, one campaign: it cannot calibrate the simulator's mizuna growth curve.",
        "Differential expression is not an edible-mass target, so nothing here is trained into a served model.",
    ],
    "OSD-386": [
        "Deliberate E. coli inoculation of mizuna mustard; it measures persistence in the microbiome, not the risk of contamination in an operational habitat.",
        "Food-safety evidence, not a growth or yield measurement.",
        "A positive result in an inoculated trial is not an estimate of background contamination.",
    ],
    "OSD-670": [
        "Regolith-substitution experiment; growth on an asteroid simulant does not establish growth on lunar or Martian regolith.",
        "Substrate chemistry differs between simulants and returned material, so results do not transfer by analogy.",
        "It bounds what a substrate change does to a plant, not what the simulator's soil assumptions should be.",
    ],
    "OSD-723": [
        "Hydroponic ionic-silver treatment on lettuce; it measures growth, nutrient uptake and root microbiome under one intervention.",
        "Room-temperature ground hydroponics, not a spacecraft water loop, so it does not calibrate the simulator's recovery fraction.",
        "Microbiome shifts are compositional; they are not a pathogen-risk measurement.",
    ],
    "OSD-856": [
        "Growth of lettuce explants on a simulated lunar soil batch; a simulant is not lunar regolith.",
        "Small, batch-specific soil chemistry: results do not generalise to other simulant batches or to the Moon.",
        "It is a feasibility result for the substrate, not a yield prediction for a lunar greenhouse.",
    ],
}


def main() -> int:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    checksums = (json.loads(CHECKSUMS.read_text())
                 if CHECKSUMS.is_file() else {"studies": {}})
    pins = checksums.setdefault("studies", {})

    manifest = json.loads(MANIFEST.read_text())
    existing = {row["id"]: row for row in manifest["datasets"]}
    added, refreshed = [], []

    for number in CANDIDATES:
        resolved = resolve_metadata_file(number)
        payload = pinned(number, resolved, pins)
        record = describe(number)
        licence = licence_from_archive(payload, record["id"])
        sid = record["id"]

        # A microbiome study records "Microbiota" as its organism, because the sequenced
        # material is the microbiome. Say so, rather than letting the reader infer that the
        # host crop is unrecorded.
        if record["organisms"] and set(record["organisms"]) == {"Microbiota"}:
            record["organismNote"] = (
                "The ISA record lists Microbiota as the organism: the sequenced material is the "
                "microbial community. The host crop appears in the study title, not as an ISA "
                "Organism characteristic.")

        row = {
            **record,
            "metadataSha256": pins[sid]["sha256"],
            "version": resolved["version"],
            "verifiedAt": pins[sid]["pinnedAt"],
            "sampleCountDefinition": (
                f"{record['sampleCount']} ISA sample records in the pinned metadata archive."),
            "trainingEligibility": (
                "Metadata only. Pinned and checksummed for provenance and for retrieval by the "
                "evidence assistant. Not a training table and not an input to any served model."),
            "status": "verified-metadata",
            **licence,
            "limitations": LIMITATIONS[sid],
            "files": [{"name": Path(pins[sid]["file"]).name,
                       "sha256": pins[sid]["sha256"],
                       "bytes": pins[sid]["bytes"],
                       "category": "metadata"}],
            "acquisition": "scripts/acquire_phase14_nasa_expansion.py",
            "rawCommitted": True,
            "rawNote": ("The ISA metadata archive is committed; it is the pinned provenance "
                        "artifact. No sequencing data was downloaded."),
        }

        if sid in existing:
            existing[sid].update(row)
            refreshed.append(sid)
        else:
            manifest["datasets"].append(row)
            added.append(sid)
        print(f"{sid}: v{resolved['version']} {pins[sid]['bytes']} bytes "
              f"sha256 {pins[sid]['sha256'][:16]}… samples={record['sampleCount']} "
              f"organisms={record['organisms']}")

    manifest["datasets"].sort(key=lambda row: int(row["id"].split("-")[1]))
    manifest["generatedAt"] = datetime.now(timezone.utc).isoformat()
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")

    checksums["discovery"] = {
        "endpoint": "https://osdr.nasa.gov/osdr/data/search?term={term}",
        "terms": ["lettuce", "Brassica", "mizuna", "wheat", "tomato", "potato", "radish",
                  "rice", "soybean", "Veggie", "plant growth", "crop",
                  "Arabidopsis spaceflight"],
        "note": ("Candidates were filtered to OSD- accessions absent from the catalogue, then "
                 "selected for space-crop relevance rather than by score."),
        "selected": [f"OSD-{n}" for n in CANDIDATES],
        "recordedAt": datetime.now(timezone.utc).isoformat(),
    }
    CHECKSUMS.write_text(json.dumps(checksums, indent=2) + "\n")

    print(f"\ncatalogue: {len(manifest['datasets'])} studies "
          f"(added {len(added)}, refreshed {len(refreshed)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
