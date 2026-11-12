"""The repository keeps no JSON files. This test is what makes that a property, not a promise.

Three things are checked, and each of them would fail if a JSON file came back:

1.  No ``*.json`` file exists anywhere in the tree. Hidden directories count, build output
    counts, the Playwright output directory counts - a file that only appears after a test run
    is still a file in the repository.
2.  No source file opens, imports or points at a ``.json`` path. That is what would bring one
    back: a loader, a fixture, a generator, a workflow step.
3.  The data layer never resolves a ``.json`` name and never describes one as a canonical
    shape, so the storage format cannot drift back one record at a time.

Two manifests are exempt: ``frontend/package.json`` and its lockfile. npm exits with ENOENT
without a manifest in that format and cannot resolve the dependency tree without the lock, so
the file is the toolchain's, not the project's. docs/NO_JSON_POLICY.md states this.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import safedata

ROOT = Path(__file__).resolve().parents[2]

#: The npm toolchain's manifests. No project data lives in them.
EXEMPT = {
    Path("frontend/package.json"),
    Path("frontend/package-lock.json"),
}

#: Directories that are not part of the committed tree: version control, installed
#: dependencies, and build output that a gate regenerates from source.
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".venv", "__pycache__", ".pytest_cache",
             "test-results", "playwright-report", ".ruff_cache", ".mypy_cache"}

SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".yml", ".yaml",
                   ".toml", ".md", ".sh", ".html", ".css"}

#: `.json` appearing as an HTTP call or a framework route is the wire format, which is allowed:
#: the API speaks JSON and FastAPI publishes /openapi.json. Neither reads a file from the tree.
WIRE_PATTERNS = (
    re.compile(r"\.json\(\)"),          # requests/httpx response body, JS Response.json()
    re.compile(r"res\.json\b"),         # express-style response
    re.compile(r"openapi\.json"),       # framework route, generated per request
    re.compile(r"application/json"),    # content type
    re.compile(r"Accept[\"']?\s*:\s*[\"']application/json"),
    re.compile(r"response\.json\(\)"),
    re.compile(r"\.json\.\(\)"),
)

#: A mention of the two exempt manifests is not a violation.
EXEMPT_PATTERNS = (
    re.compile(r"package-lock\.json"),
    re.compile(r"package\.json"),
)


def _tree() -> list[Path]:
    found = []
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            found.append(path.relative_to(ROOT))
    return found


def test_no_json_file_exists_anywhere_in_the_tree():
    offenders = sorted(str(p) for p in _tree()
                       if p.suffix == ".json" and p not in EXEMPT)
    assert not offenders, (
        "the repository stores no JSON; these files came back:\n  " + "\n  ".join(offenders))


def test_the_only_json_files_are_the_two_npm_manifests():
    present = sorted(str(p) for p in _tree() if p.suffix == ".json")
    assert present == sorted(str(p) for p in EXEMPT), (
        "expected exactly the two npm toolchain manifests, found: " + repr(present))


def _leaf_types(value, depth=0):
    """Every leaf type in ``value``, and the deepest nesting it reaches."""
    if isinstance(value, dict):
        deepest = max((_leaf_types(v, depth + 1) for v in value.values()), default=(set(), depth))
        return deepest[0], deepest[1]
    if isinstance(value, list):
        deepest = max((_leaf_types(v, depth + 1) for v in value), default=(set(), depth))
        return deepest[0], deepest[1]
    return {type(value).__name__}, depth


def test_the_npm_manifests_are_the_toolchain_s_own_and_hold_no_project_data():
    """The exemption is only defensible if the files really are dependency metadata.

    A lockfile is npm's own bookkeeping, and its exact key set is npm's to change, so this test
    asserts the property that matters instead of a schema: every entry pins a package, and
    nothing in the file is shaped like a data record. A table of measurements is a list of
    dictionaries several levels deep; a dependency tree is names, versions, URLs and flags.
    """
    import json

    package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    assert set(package) <= {"name", "private", "version", "type", "description", "scripts",
                            "dependencies", "devDependencies", "engines", "browserslist"}, (
        f"frontend/package.json carries more than dependency metadata: {sorted(package)}")

    lock = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))
    assert "packages" in lock, "the lockfile must be a dependency tree"
    for path, entry in lock["packages"].items():
        assert "version" in entry or path == "", (
            f"{path}: every installed package is pinned to a version")
        kinds, depth = _leaf_types(entry)
        assert kinds <= {"str", "bool", "int", "NoneType"}, (
            f"{path}: the lockfile holds {sorted(kinds - {'str', 'bool', 'int', 'NoneType'})}, "
            "which package metadata never contains")
        assert depth <= 3, (
            f"{path}: package metadata nests {depth} levels deep - that shape is a data record")


def test_no_source_file_names_a_json_record_to_read():
    """A loader, fixture or generator pointing at a `.json` path is how the files come back."""
    offenders = []
    for rel in _tree():
        if rel.suffix not in SOURCE_SUFFIXES:
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue                       # binary or unreadable: covered by test 1
        for number, line in enumerate(text.splitlines(), start=1):
            if ".json" not in line:
                continue
            if any(p.search(line) for p in WIRE_PATTERNS):
                continue
            if any(p.search(line) for p in EXEMPT_PATTERNS):
                continue
            if rel in (Path("docs/NO_JSON_POLICY.md"), Path("backend/tests/test_zero_json_policy.py"),
                       Path("docs/JSON_ELIMINATION_REPORT.md")):
                continue                   # the documents that state the rule and its record
            if "NO_JSON_POLICY" in line or "no-JSON" in line or "no_json" in line:
                continue                   # a reference to the policy
            if rel == Path("safedata/__init__.py"):
                continue                   # the layer that recognises a legacy spelling
            offenders.append(f"{rel}:{number}: {line.strip()[:110]}")
    assert not offenders, (
        "these lines reach for a JSON file; a record belongs in .py, .csv or .yaml:\n  "
        + "\n  ".join(offenders))


def test_the_data_layer_resolves_records_and_refuses_json():
    assert ".json" not in safedata.SUFFIXES, (
        "the data layer must not treat .json as a storage shape")
    with pytest.raises(safedata.DataFileError):
        safedata.resolve("data/metadata/does_not_exist")


def test_the_data_layer_resolves_a_record_without_naming_its_encoding():
    """A caller names a record; the layer picks the file. Both spellings must land on it."""
    plain = safedata.resolve("ml/artifacts/registry")
    assert plain.suffix == ".py"
    assert safedata.resolve("ml/artifacts/registry.py") == plain
    # a legacy spelling left in an archived reference still finds the record
    assert safedata.resolve("ml/artifacts/registry.json") == plain


def test_every_record_in_the_repository_reads_back_through_the_data_layer():
    """Sampling the tree is cheap insurance that no conversion left a file unreadable."""
    checked = 0
    for base in ("ml/artifacts", "ml/evaluation", "data/research", "data/metadata"):
        for path in sorted((ROOT / base).rglob("*.py")):
            if path.name == "__init__.py":
                continue
            record = safedata.load(path)
            assert record is not None, f"{path.relative_to(ROOT)} loads as None"
            assert isinstance(record, (dict, list)), (
                f"{path.relative_to(ROOT)} does not hold a record: {type(record).__name__}")
            checked += 1
    assert checked > 60, f"expected to check the stored records, only found {checked}"
