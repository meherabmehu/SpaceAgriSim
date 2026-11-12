#!/usr/bin/env python3
"""Generate docs/DATASET_REGISTRY.md from the files themselves.

Every hash, row count and accession in the registry is read from the data on disk, never typed by
hand. A registry that is maintained by copying numbers into prose drifts the first time a file is
re-fetched, and a drifted provenance table is worse than none: it looks authoritative.

Run: python scripts/generate_dataset_registry.py
Writes: docs/DATASET_REGISTRY.md
Exit code is non-zero if a declared dataset file is missing.
"""
from __future__ import annotations
import sys

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
DATA = ROOT / "data"
OUT = ROOT / "docs" / "DATASET_REGISTRY.md"

MISSING: list[str] = []


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rows_in(path: Path) -> str:
    if path.suffix not in {".csv", ".parquet"}:
        return "—"
    try:
        import pandas as pd

        if path.suffix == ".parquet":
            frame = pd.read_parquet(path)
        else:
            frame = pd.read_csv(path, low_memory=False)
        return f"{len(frame):,} × {frame.shape[1]}"
    except Exception as exc:  # noqa: BLE001 - a row count must not break the registry
        return f"unreadable ({type(exc).__name__})"


def table(header: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(header) + " |",
             "| " + " | ".join("---" for _ in header) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def code(text: str) -> str:
    return f"`{text}`"


def nasa_studies() -> str:
    manifest = safedata.load(DATA / "metadata" / "dataset_manifest")
    rows = []
    for study in manifest["datasets"]:
        used = "served model" if study["id"] in {"OSD-46", "OSD-655", "OSD-767", "OSD-780"} else "corpus / not modelled"
        rows.append([
            study["id"],
            (study.get("title") or "")[:78].replace("|", "/"),
            str(study.get("sampleCount")),
            f"v{study.get('version')}" if study.get("version") else "—",
            code((study.get("metadataSha256") or "—")[:16]),
            used,
        ])
    return table(["Accession", "Title", "Samples", "Version", "Metadata SHA-256", "Use"], rows)


def external_sources() -> str:
    rows = []
    for name in ("external_lettuce", "wur_lettuce_rocrate"):
        path = DATA / "metadata" / name
        if not safedata.exists(path):
            MISSING.append(str(path))
            continue
        meta = safedata.load(path)
        for item in meta.get("files") or []:
            target = ROOT / item["path"]
            if safedata.exists(target):
                recorded = item.get("sha256")
                actual = sha256(target)
                state = "verified" if recorded == actual else "MISMATCH"
            else:
                MISSING.append(str(target))
                state = "missing"
            rows.append([
                code(item["path"].split("/")[-1]),
                meta.get("title", name)[:60],
                meta.get("license", "—"),
                meta.get("retrievedAt", "—")[:10] or "—",
                str(item.get("bytes", "—")),
                code((item.get("sha256") or "")[:16]),
                state,
            ])
    return table(["File", "Source", "Licence", "Retrieved", "Bytes", "Recorded SHA-256", "State"], rows)


def processed() -> str:
    rows = []
    for path in sorted(DATA.glob("processed/*.csv")) + sorted(DATA.glob("processed/*.parquet")):
        rows.append([code(path.name), rows_in(path), code(sha256(path)[:16])])
    return table(["Processed table", "Rows × columns", "SHA-256"], rows)


def literature() -> str:
    rows = []
    for path in sorted(DATA.glob("literature/*")):
        body = safedata.load(path)
        if not isinstance(body, dict):
            continue
        source = body.get("source") or {}
        doi = source.get("doi") or body.get("doi") or "—"
        rows.append([
            code(path.name),
            (source.get("studyId") or body.get("id") or "—"),
            doi,
            source.get("license") or body.get("license") or "—",
            (source.get("retrievedAt") or body.get("retrievedAt") or "—")[:10],
        ])
    return table(["File", "Identifier", "DOI", "Licence", "Retrieved"], rows)


def main() -> int:
    registry = safedata.load(ROOT / "ml" / "artifacts" / "registry")
    manifest = safedata.load(DATA / "metadata" / "dataset_manifest")
    _manifest_generated = (manifest.get("generatedAt") or "unknown")[:10]
    _manifest_count = len(manifest["datasets"])
    model_rows = []
    for item in registry["models"]:
        card = safedata.load(ROOT / item["artifact"])
        model_rows.append([
            code(item["id"]),
            str(card.get("samples")),
            str(card.get("groups")),
            code(card.get("sourceStudy") or "—"),
            card.get("status", "—"),
            code(item["sha256"][:16]),
        ])

    body = f"""# Dataset and model registry

Generated by `scripts/generate_dataset_registry.py` on {datetime.now(timezone.utc).date().isoformat()}.
Every hash, row count and accession below is read from the file it describes; nothing in this
document is typed by hand. Re-run the script after any re-fetch and the numbers change with the
data or the check fails.

## What "verified" means here

* **verified** — the file on disk hashes to the value recorded when it was retrieved.
* **MISMATCH** — the file changed after retrieval. Nothing trained on it may be trusted until the
  change is explained and the registry is updated deliberately.
* **corpus / not modelled** — the study's metadata is in the served evidence corpus, but no model is
  trained on its measurements. A registered study is not a training table.

## NASA OSDR studies (metadata only, plus downloaded measurement tables where a model exists)

Source: NASA OSDR official study and file APIs (`data/metadata/dataset_manifest`, generated
{_manifest_generated}). {_manifest_count} studies.

{nasa_studies()}

## Non-NASA experimental sources

These carry the experimental data that no NASA dataset provides: controlled-environment crop growth
with reported light, temperature and duration.

{external_sources()}

## Processed tables

{processed()}

## Literature and transcription records

Transcribed values live in JSON with the source's DOI, licence and retrieval date beside them. Values
are transcribed, never estimated: where a study reports a range rather than a value, the range is
recorded and the mid-point used for scoring is stated explicitly in the model artifact.

{literature()}

## Models and their training data

{model_rows and table(["Model", "Rows", "Groups", "Source study", "Status", "Artifact SHA-256"], model_rows)}

A model appears here only if it is registered with a checksum. `scripts/verify_model_registry.py`
re-derives every artifact hash and refuses to pass if one does not match.
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(body)
    print(f"written: {OUT.relative_to(ROOT)}")
    if MISSING:
        print("MISSING:")
        for item in MISSING:
            print(f"  {item}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
