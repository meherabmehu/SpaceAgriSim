"""Source-level checks for failures that no runtime assertion can catch.

A duplicated key in a dict literal is legal Python: the interpreter keeps the last value and discards
the earlier one without a warning. Two of them existed in this repository - a response dict in
`routes/research.py` where the discarded value was an evidence warning, and the unit registry, where
the discarded value was a caution string - and neither produced a failing test, because in both cases
the *surviving* value happened to be the one that was wanted.

That is exactly the condition a test should watch for, and it cannot be expressed against the running
code: by the time the module is imported, the duplicate no longer exists. So this file reads the
source instead.
"""
from __future__ import annotations

import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def _python_sources() -> list[Path]:
    return sorted(path for path in APP.rglob("*.py") if "__pycache__" not in path.parts)


def _duplicate_literal_keys(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        keys = [key.value for key in node.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)]
        duplicates = sorted({key for key in keys if keys.count(key) > 1})
        if duplicates:
            found.append(f"{path.relative_to(APP.parent)}:{node.lineno} duplicates {duplicates}")
    return found


def test_the_scan_itself_finds_a_planted_duplicate():
    """The rest of this file is only worth something if the scan can see a duplicate at all."""
    planted = ast.parse('values = {"a": 1, "b": 2, "a": 3}\n')
    node = next(n for n in ast.walk(planted) if isinstance(n, ast.Dict))
    keys = [key.value for key in node.keys if isinstance(key, ast.Constant)]
    duplicates = {key for key in keys if keys.count(key) > 1}
    assert duplicates == {"a"}


def test_no_dict_literal_in_the_application_has_a_duplicate_key():
    offenders: list[str] = []
    for path in _python_sources():
        offenders.extend(_duplicate_literal_keys(path))
    assert offenders == [], (
        "a duplicate key in a dict literal is discarded silently; "
        "merge the entries instead:\n" + "\n".join(offenders)
    )


def test_the_unit_registry_declares_each_unit_once_with_its_description():
    """The specific regression: `g/plant` and `mm2` were each defined twice.

    The second definition won, so the API served one wording and dropped the other's caution. This
    asserts the merged state rather than merely that the scan is clean, so the information that was
    being discarded cannot come back as a shorter description.
    """
    from app.workflows import units

    for name in ("g/plant", "mm2"):
        entry = units.describe(name)
        assert entry["registered"] is True
        assert len(entry["cautions"]) >= 2, f"{name} lost a caution: {entry['cautions']}"

    # The registry is served as a map, so every name must describe something.
    body = units.registry()
    assert len(body["units"]) == len(units.UNITS)
    assert all(item["registered"] for item in body["units"].values())


def test_the_file_that_was_fixed_stays_fixed():
    path = APP / "workflows" / "units.py"
    assert path.exists()
    assert _duplicate_literal_keys(path) == []
