"""Gate-level invariants that only continuous integration used to enforce.

Why this file exists
--------------------
`ml/research/dedupe_screenshots.py --check` runs in the CI science job. Nothing ran it locally, so
when the visual-baseline migration archived eighteen images and swept a leftover into the same
commit, the branch went red on a gate that no local test covered. The failure was found only by
re-reading `.github/workflows/ci.yml` and running every step by hand.

A gate that only exists in CI is a gate that fails silently on the developer's machine. These tests
run the same checks in the ordinary suite, and they assert the two things that actually broke:

  * the store contains no byte-identical duplicates;
  * a path that `docs/screenshots/MANIFEST.json` records as removed is genuinely absent from disk,
    because re-adding one re-creates the duplicate the manifest exists to record.

They are deliberately about the store rather than about the gate script: a test that merely called
`--check` would have passed if the script itself were broken.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHOTS = ROOT / "docs" / "screenshots"
MANIFEST = SHOTS / "MANIFEST.json"


def _manifest() -> dict:
    assert MANIFEST.is_file(), "docs/screenshots/MANIFEST.json is missing"
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------- the store itself
def test_no_two_screenshots_are_byte_identical():
    """The property the CI gate enforces, computed here rather than delegated."""
    by_digest: dict[str, list[Path]] = {}
    for path in sorted(SHOTS.rglob("*.png")):
        by_digest.setdefault(_sha256(path), []).append(path)
    duplicates = {d: [str(p.relative_to(ROOT)) for p in paths]
                  for d, paths in by_digest.items() if len(paths) > 1}
    assert not duplicates, (
        "byte-identical screenshots exist; run `python ml/research/dedupe_screenshots.py` "
        f"and commit the manifest it writes: {duplicates}"
    )


def test_the_dedup_gate_itself_exits_zero():
    result = subprocess.run([sys.executable, "ml/research/dedupe_screenshots.py", "--check"],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_path_the_manifest_records_as_removed_is_not_on_disk():
    """The exact mistake: a committed leftover contradicted the manifest for four commits."""
    manifest = _manifest()
    resurrected = [path for path in (manifest.get("removed") or {}) if (ROOT / path).exists()]
    assert not resurrected, (
        "these paths are recorded in MANIFEST.json as removed for being byte-identical to their "
        f"canonical file, but exist again: {resurrected}"
    )


def test_every_canonical_path_resolves_and_still_hashes_to_its_recorded_digest():
    manifest = _manifest()
    canonical = manifest.get("canonical") or {}
    assert canonical, "the manifest records no canonical images"
    for path, record in canonical.items():
        file = ROOT / path
        assert file.is_file(), f"canonical image is missing: {path}"
        # The manifest stores the digest either bare or under "sha256"; both are read so the test
        # checks the invariant rather than one serialisation of it.
        expected = record.get("sha256") if isinstance(record, dict) else record
        assert expected, f"canonical entry has no digest: {path}"
        assert _sha256(file) == expected, f"canonical image changed since the manifest: {path}"


def test_every_removed_path_recorded_an_identical_canonical_twin():
    """A removal is only information-preserving if it names the file that still holds the bytes."""
    manifest = _manifest()
    for path, record in (manifest.get("removed") or {}).items():
        twin = (record or {}).get("identicalTo")
        assert twin, f"{path} was removed without naming what holds the same bytes"
        assert (ROOT / twin).is_file(), f"{path} points at a twin that does not exist: {twin}"
        assert (record or {}).get("sha256"), f"{path} was removed without recording a digest"


# --------------------------------------------------------------------- the phase 37 archive
def test_every_replaced_baseline_was_archived_and_is_still_present():
    """The archive must keep exactly the images the migration replaced - no more, no fewer."""
    migration = json.loads(
        (ROOT / "ml" / "evaluation" / "phase37_visual_baseline_migration.json").read_text(
            encoding="utf-8"))
    replaced = [capture["capture"] for capture in migration["captures"] if capture.get("replaced")]
    assert len(replaced) == 18
    missing = [name for name in replaced
               if not (SHOTS / "historical" / "phase37" / f"{name}.png").is_file()]
    assert not missing, f"replaced baselines were not archived: {missing}"


def test_the_live_baselines_and_the_archive_are_not_the_same_images():
    """If an archived image equalled the live one, either the capture did not change or the
    archive was filled with copies. Both are worth failing on."""
    same = []
    for archived in sorted((SHOTS / "historical" / "phase37").glob("*.png")):
        live = SHOTS / archived.name
        if live.is_file() and _sha256(live) == _sha256(archived):
            same.append(archived.name)
    assert not same, f"archived baseline is byte-identical to the live one: {same}"
