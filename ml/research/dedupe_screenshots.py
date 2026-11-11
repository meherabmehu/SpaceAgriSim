"""Collapse byte-identical screenshot copies into one canonical file each.

Why this exists
---------------
The visual-regression baselines and the per-phase parent/candidate captures accumulate by design:
each phase archives the previous baselines, captures its own parent and its own candidate, and
installs the result. Many of those files are byte-identical - a capture that did not change is
copied, not re-rendered - so the same image ends up stored under three or four paths. At Phase 35
that was 115 files of which only 53 were unique: 46.9 MB of exact duplication.

Deleting a duplicate loses no information only if the equality is recorded, so this script does
three things:

  1. hashes every PNG under docs/screenshots;
  2. picks one canonical file per unique image - the committed baseline when the image is a
     baseline, otherwise the existing path;
  3. deletes the redundant copies and writes docs/screenshots/MANIFEST.json, which maps every
     removed path to the canonical file that holds the same bytes plus the SHA-256 both share.

`ml/research/phase34_visual_drift.py` and `ml/research/phase35_visual_drift.py` resolve a capture
through that manifest, so a re-run still compares the same pixels and still reports 0.000 % for a
capture that was merely duplicated.

Run:  python ml/research/dedupe_screenshots.py [--check]
      --check exits non-zero if duplicates exist, without deleting anything.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "docs" / "screenshots"
MANIFEST = SHOTS / "MANIFEST.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _preference(path: Path) -> tuple:
    """Canonical wins: a top-level baseline, then the shallowest path."""
    return (len(path.relative_to(SHOTS).parts), str(path))


def survey() -> tuple[dict[str, Path], dict[str, list[Path]]]:
    groups: dict[str, list[Path]] = collections.defaultdict(list)
    for path in sorted(SHOTS.rglob("*.png")):
        groups[sha256(path)].append(path)
    canonical: dict[str, Path] = {}
    duplicates: dict[str, list[Path]] = {}
    for digest, paths in groups.items():
        paths.sort(key=_preference)
        canonical[digest] = paths[0]
        if len(paths) > 1:
            duplicates[digest] = paths[1:]
    return canonical, duplicates


def apply(write: bool) -> int:
    canonical, duplicates = survey()
    removed: dict[str, dict] = {}
    saved = 0
    for digest, extra in duplicates.items():
        keeper = canonical[digest]
        for path in extra:
            saved += path.stat().st_size
            removed[str(path.relative_to(ROOT))] = {
                "identicalTo": str(keeper.relative_to(ROOT)),
                "sha256": digest,
            }
            if write:
                path.unlink()

    if write:
        for parent in sorted({(SHOTS / Path(p).parent).resolve()
                              for p in removed}, key=lambda p: -len(str(p))):
            # Remove directories the deletions emptied, deepest first.
            if parent != SHOTS and parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
        manifest = {
            "schema": "spaceagrisim.screenshot_manifest/1",
            "method": ("Every file below was byte-identical to `identicalTo`: same SHA-256, same "
                       "pixels. Nothing was re-rendered, resized or re-encoded. The canonical copy "
                       "is kept and the comparison scripts resolve a missing path through this "
                       "manifest, so a re-run compares the same bytes."),
            "canonical": {str(path.relative_to(ROOT)): digest
                          for digest, path in sorted(canonical.items(), key=lambda kv: str(kv[1]))},
            "removed": removed,
            "savedBytes": saved,
        }
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"unique images        {len(canonical)}")
    print(f"redundant copies     {sum(len(v) for v in duplicates.values())}")
    print(f"reclaimable          {saved / 1e6:.1f} MB")
    for digest, extra in list(duplicates.items())[:5]:
        print(f"  {canonical[digest].relative_to(ROOT)}  <-  "
              f"{', '.join(str(p.relative_to(ROOT)) for p in extra)}")
    if write:
        print(f"wrote {MANIFEST.relative_to(ROOT)}")
    return 0


def check() -> int:
    _, duplicates = survey()
    if duplicates:
        total = sum(p.stat().st_size for extra in duplicates.values() for p in extra)
        print(f"{sum(len(v) for v in duplicates.values())} byte-identical copies remain "
              f"({total / 1e6:.1f} MB); run without --check to collapse them")
        return 1
    if not MANIFEST.is_file():
        print("no duplicates, but the manifest is missing")
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    missing = [path for path in manifest["removed"] if (ROOT / path).is_file()]
    absent = [path for path in manifest["canonical"] if not (ROOT / path).is_file()]
    problems = []
    if missing:
        problems.append(f"{len(missing)} file(s) listed as removed are present again")
    if absent:
        problems.append(f"{len(absent)} canonical file(s) are missing")
    for path, row in manifest["removed"].items():
        target = ROOT / row["identicalTo"]
        if target.is_file() and sha256(target) != row["sha256"]:
            problems.append(f"{row['identicalTo']} no longer matches its recorded hash")
    if problems:
        print("screenshot manifest is inconsistent:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"screenshot store is deduplicated: {len(manifest['canonical'])} unique images, "
          f"{manifest['savedBytes'] / 1e6:.1f} MB of duplicates recorded")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    return check() if arguments.check else apply(write=True)


if __name__ == "__main__":
    sys.exit(main())
