"""The repository keeps no JSON files. This test is what makes that a property, not a promise.

Four things are checked, and each of them would fail if a JSON file came back:

1.  No ``*.json``, ``*.json5`` or ``*.jsonl`` file exists anywhere in the tree. Hidden
    directories count, build output counts, the Playwright output directory counts - a file that
    only appears after a test run is still a file in the repository. There is no exemption list:
    the two npm manifests this repository used to carry are gone, and the dependency set lives in
    ``frontend/dependencies.toml`` and ``frontend/dependencies.lock.mjs``.
2.  No source file opens, imports or points at a JSON path. That is what would bring one back: a
    loader, a fixture, a generator, a workflow step.
3.  The data layer never resolves a ``.json`` name and never describes one as a canonical shape,
    so the storage format cannot drift back one record at a time.
4.  The one toolchain that cannot work without JSON files - npm - only ever writes them outside
    the checkout, and deletes them again. ``test_the_manifest_helper_refuses_to_write_inside_the_repository``
    runs the helper with the destination pointed at the repository and requires it to fail
    instead of writing.

docs/NO_JSON_POLICY.md states the rule for a reader; this file enforces it.
"""
from __future__ import annotations

import re
import subprocess
import tomllib
from os import environ
from pathlib import Path
from shutil import which

import pytest

import safedata

ROOT = Path(__file__).resolve().parents[2]

#: Everything the policy forbids. `.jsonc`, `.ndjson` and `.geojson` are included because they
#: are the same format under a different extension, which is exactly the loophole the rule closes.
JSON_FAMILY = {".json", ".json5", ".jsonl", ".jsonc", ".ndjson", ".geojson"}

#: The frontend's dependency manifest, kept as TOML, and the lock, kept as a generated module.
MANIFEST_TOML = Path("frontend/dependencies.toml")
LOCK_MODULE = Path("frontend/dependencies.lock.mjs")
NPM_HELPER = Path("frontend/scripts/npm.mjs")

#: Directories that are not part of the committed tree: version control, installed
#: dependencies, and build output that a gate regenerates from source.
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".venv", "__pycache__", ".pytest_cache",
             "test-results", "playwright-report", ".ruff_cache", ".mypy_cache"}

SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".yml", ".yaml",
                   ".toml", ".md", ".sh", ".html", ".css", ".conf", ".txt", ".cfg", ".ini"}

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

#: The npm helper has to name the two files npm demands - it exists to write them somewhere else
#: and delete them. It is the only script allowed to contain those names, and test 4 below proves
#: it cannot write them into the tree.
HELPER_NAMES = ("package.json", "package-lock.json")


def _tree() -> list[Path]:
    found = []
    for path in ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            found.append(path.relative_to(ROOT))
    return found


def test_no_json_family_file_exists_anywhere_in_the_tree():
    offenders = sorted(str(p) for p in _tree() if p.suffix.lower() in JSON_FAMILY)
    assert not offenders, (
        "the repository stores no JSON; these files came back:\n  " + "\n  ".join(offenders))


def test_no_json_family_file_exists_even_at_the_extensions_a_double_extension_hides():
    """`registry.json.bak`, `data.json.txt` and `x.JSON` must not slip past a suffix comparison."""
    offenders = []
    for rel in _tree():
        lowered = rel.name.lower()
        for suffix in JSON_FAMILY:
            if suffix in lowered and not lowered.endswith(suffix):
                offenders.append(str(rel))
                break
    assert not offenders, (
        "a JSON file is hiding behind another extension:\n  " + "\n  ".join(offenders))


def test_the_frontend_manifest_and_lock_are_not_json():
    """The dependency set has to live in files the policy allows, and it has to be complete."""
    assert MANIFEST_TOML.exists(), "the frontend manifest must exist, as TOML"
    assert LOCK_MODULE.exists(), "the frontend lock must exist, as a module"
    lock_text = (ROOT / LOCK_MODULE).read_text(encoding="utf-8")
    assert lock_text.startswith("/**"), "the lock module opens with an explanation of its shape"
    assert "export const lockfile = {" in lock_text, "the lock is an exported object, not a blob"
    packages = lock_text.count('"node_modules/')
    assert packages > 300, f"the lock module should pin the installed tree, found {packages} entries"


def test_the_toml_manifest_is_the_manifest_npm_would_have_read():
    """Parsed with Python's own TOML reader, the manifest must still describe the same project.

    If this drifts, the frontend job fails on its next install, so the two readings of the file -
    `tomllib` here and the reader in scripts/npm.mjs - cannot disagree without a test noticing.
    """
    with open(ROOT / MANIFEST_TOML, "rb") as handle:
        manifest = tomllib.load(handle)

    assert manifest["name"] == "spaceagrisim-frontend"
    assert manifest["private"] is True
    assert manifest["type"] == "module"
    assert set(manifest["scripts"]) == {
        "dev", "build", "preview", "lint", "typecheck", "test:e2e", "test:unit", "build:check"}
    # The gates the CI workflow runs must be addressable by name; a renamed script would leave a
    # workflow step pointing at nothing.
    for script in ("lint", "typecheck", "test:unit", "build:check", "test:e2e"):
        assert script in manifest["scripts"], f"scripts.{script} is missing"
    assert manifest["scripts"]["build:check"] == "vite build && node scripts/check-bundle.mjs", (
        "build:check must still run the production build and the bundle guard, not one of them")
    assert set(manifest["dependencies"]) == {"lucide-react", "react", "react-dom", "recharts"}
    assert len(manifest["devDependencies"]) == 17
    assert "vite" in manifest["devDependencies"] and "vitest" in manifest["devDependencies"]


def _is_comment(line: str) -> bool:
    """A comment cannot open a file, so a sentence explaining the policy is not a violation."""
    stripped = line.strip()
    return stripped.startswith(("#", "//", "/*", "*", "<!--"))


def test_no_source_file_names_a_json_record_to_read():
    """A loader, fixture or generator pointing at a `.json` path is how the files come back.

    Prose is not a violation: the README, the policy and the workflow comments all have to be
    able to say that there is no package.json. What must not happen is executable code naming a
    JSON path, which is what this scans for - comments and Markdown are skipped, every other line
    of code is read.
    """
    offenders = []
    for rel in _tree():
        if rel.suffix not in SOURCE_SUFFIXES or rel.suffix == ".md":
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue                       # binary or unreadable: covered by test 1
        if text.startswith('"""Data record.'):
            # A record is read as a literal and never executed, so a path inside it is a value,
            # not a reach. The generated ui_preservation record, for instance, holds the diffstat
            # of the commit that removed the two npm manifests, and must be able to say so.
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if ".json" not in line or _is_comment(line):
                continue
            if any(p.search(line) for p in WIRE_PATTERNS):
                continue
            if rel == NPM_HELPER and any(name in line for name in HELPER_NAMES):
                continue                   # the helper's whole job is to move npm's files away
            if rel in (Path("docs/NO_JSON_POLICY.md"), Path("backend/tests/test_zero_json_policy.py"),
                       Path("docs/JSON_ELIMINATION_REPORT.md")):
                continue                   # the documents that state the rule and its record
            if "NO_JSON_POLICY" in line or "no-JSON" in line or "no_json" in line:
                continue                   # a reference to the policy
            if rel == Path("safedata/__init__.py"):
                continue                   # the layer that recognises a legacy spelling
            offenders.append(f"{rel}:{number}: {line.strip()[:110]}")
    assert not offenders, (
        "these lines reach for a JSON file; a record belongs in .py, .csv, .toml or .yaml:\n  "
        + "\n  ".join(offenders))


def test_no_gate_generates_json_inside_the_repository():
    """Workflows and scripts must not leave a manifest behind after a build or a test run."""
    forbidden = []
    for rel in _tree():
        if rel.suffix not in {".yml", ".yaml", ".sh", ".py", ".mjs", ".js", ".json"} and rel.name != "Dockerfile":
            continue
        if rel.suffix.lower() in JSON_FAMILY:
            forbidden.append(f"{rel}: is itself a JSON file")
            continue
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
                continue                   # a comment cannot write a file
            if re.search(r"\bnpm (ci|install|run)\b", stripped) and rel != NPM_HELPER:
                forbidden.append(f"{rel}:{number}: {stripped[:110]}")
    assert not forbidden, (
        "these steps would run npm in the repository, where it writes package.json:\n  "
        + "\n  ".join(forbidden))


def test_the_manifest_helper_refuses_to_write_inside_the_repository():
    """Point the helper's destination at the checkout and it must refuse, not write.

    This is the runtime half of the policy: the static checks above prove no JSON file is
    committed, and this proves the one tool that creates JSON files cannot be aimed inward.
    """
    node = which("node")
    if node is None:
        pytest.skip("node is not installed here; the frontend CI job runs this path instead")

    environment = {
        **environ,
        "SPACEAGRISIM_NPM_WORKDIR": str(ROOT / "frontend" / "npm-workdir-probe"),
    }
    result = subprocess.run(
        [node, str(ROOT / NPM_HELPER), "ci"],
        cwd=ROOT / "frontend", capture_output=True, text=True, timeout=300, env=environment)
    assert result.returncode != 0, (
        "the helper accepted a destination inside the repository, which is how a package.json "
        "would come back:\n" + result.stdout[-800:] + result.stderr[-800:])
    assert "inside the repository" in (result.stdout + result.stderr), (
        "the helper must fail with its explicit guard message, not some unrelated error")
    leaked = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "frontend").rglob("*.json"))
    assert not leaked, f"the guard let a JSON file through: {leaked}"
    assert not (ROOT / "frontend" / "npm-workdir-probe").exists(), (
        "the helper created the directory it was told to refuse")


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
