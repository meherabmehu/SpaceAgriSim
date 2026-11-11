"""Resolve a screenshot path that may have been collapsed by the dedupe pass.

`ml/research/dedupe_screenshots.py` deletes byte-identical copies and records, for each removed
path, the canonical file with the same SHA-256. A comparison script that asks for
`docs/screenshots/phase34/candidate/mission-desktop.png` therefore still gets those exact bytes -
from the canonical copy - and can say so, instead of reporting the capture as missing.

Nothing here re-renders or approximates an image: `resolve()` either finds a file with the bytes
that were recorded or returns None.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "docs" / "screenshots"
MANIFEST = SHOTS / "MANIFEST.json"


@lru_cache(maxsize=1)
def _manifest() -> dict:
    if not MANIFEST.is_file():
        return {"removed": {}}
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def resolve(path: Path) -> tuple[Path | None, str | None]:
    """The file holding this capture's bytes, and where it came from.

    Returns `(path, None)` when the file itself exists, `(canonical, original)` when the file was
    collapsed into an identical copy, and `(None, None)` when neither exists.
    """
    if path.is_file():
        return path, None
    row = (_manifest().get("removed") or {}).get(str(path.relative_to(ROOT)))
    if not row:
        return None, None
    canonical = ROOT / row["identicalTo"]
    return (canonical if canonical.is_file() else None), str(path)


def names_in(*directories: Path) -> list[str]:
    """Capture names present directly in these directories, including deduplicated ones.

    A directory that lost files to the dedupe pass still has a name for each of them, because the
    manifest records the original path. Building the comparison list from the filesystem alone
    would silently shrink a run from 18 captures to 10.
    """
    names: set[str] = set()
    removed = (_manifest().get("removed") or {})
    for directory in directories:
        for path in directory.glob("*.png"):
            names.add(path.stem)
        prefix = str(directory.relative_to(ROOT)) + "/"
        for original in removed:
            if original.startswith(prefix):
                names.add(Path(original).stem)
    return sorted(names)
