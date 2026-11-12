"""Rebuild ml/artifacts/registry from the artifacts that actually exist.

Why this exists
---------------
Each training script previously rewrote `registry` from only the model it
had just trained. Running them in the wrong order therefore silently deleted
other models from the registry, and the API would then report a perfectly good
artifact as "not registered". That happened during Phase 6 development.

This builder is the single source of truth for the registry: it scans
`ml/artifacts/`, hashes every model card, and writes a registry that is always a
superset of what is on disk. It is idempotent and safe to run after any training
script.

Run: python scripts/build_registry.py
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
sys.path.insert(0, str(ROOT / "scripts"))
from nasa_pipeline import save_json, stamp  # noqa: E402

ARTIFACTS = ROOT / "ml" / "artifacts"
REGISTRY = ARTIFACTS / "registry"

# Files in ml/artifacts that are not model cards.
NON_MODEL = {"registry", "tomato_example"}


def is_model_card(name: str) -> bool:
    """A model artifact is any record in ml/artifacts that is not the registry itself."""
    return Path(name).stem not in NON_MODEL


def main() -> int:
    import numpy
    import pandas
    import sklearn

    previous_rows = {}
    if safedata.exists(REGISTRY):
        for row in safedata.load(REGISTRY).get("models", []):
            if row.get("id"):
                previous_rows[row["id"]] = row

    def registry_row(card: dict) -> dict:
        """The registry row for one artifact, preserving what the previous row recorded.

        Rebinding this script to only id/artifact/sha256 deleted the `supersedes` chain, the
        `status` and the recorded independent validation every time it ran - so a withdrawal would
        quietly become an ordinary model after any retrain. Everything except the three fields
        this script actually recomputes is carried forward from the previous row.
        """
        row = {"id": card["id"], "artifact": card["artifact"], "sha256": card["sha256"]}
        for key, value in (previous_rows.get(card["id"]) or {}).items():
            if key not in row:
                row[key] = value
        return row

    cards = []
    for path in safedata.records(ARTIFACTS):
        if not is_model_card(path.name):
            continue
        body = safedata.resolve(path).read_bytes()
        try:
            card = safedata.loads_python_module(body.decode('utf-8'), where=str(path))
        except json.JSONDecodeError:
            print(f"  SKIP (invalid JSON): {path.name}")
            continue
        model_id = card.get("id")
        if not model_id:
            print(f"  SKIP (no id): {path.name}")
            continue
        if path.stem != model_id:
            print(f"  SKIP (filename/id mismatch): {path.name} vs {model_id}")
            continue
        cards.append({
            "id": model_id,
            "artifact": f"ml/artifacts/{path.name}",
            "sha256": hashlib.sha256(body).hexdigest(),
            "evidenceStatus": card.get("evidenceStatus"),
            "sourceStudy": card.get("sourceStudy"),
            "samples": card.get("samples"),
        })

    previous = safedata.load(REGISTRY) if safedata.exists(REGISTRY) else {}
    registry = {
        "schemaVersion": 1,
        "trainedAt": stamp(),
        "environment": {
            "python": platform.python_version(),
            "numpy": numpy.__version__,
            "pandas": pandas.__version__,
            "sklearn": sklearn.__version__,
        },
        "models": [registry_row(c) for c in cards],
    }
    # Preserve data-version digests if a previous registry recorded them.
    for key in ("dataVersion", "externalDataVersion", "externalTrainingEnvironment"):
        if key in previous:
            registry[key] = previous[key]
    save_json(REGISTRY, registry)

    print(f"registry models: {len(cards)}")
    for card in cards:
        print(f"  {card['id']:<28} samples={card['samples']!s:<6} "
              f"status={card['evidenceStatus'] or '(card default)'}  "
              f"sha256={card['sha256'][:16]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
