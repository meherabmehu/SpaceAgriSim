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


# ---------------------------------------------------------------------------------------------------
# Lost Unicode symbols.
#
# `GET /api/config` publishes the unit for every control, and `services/insights.js` renders that
# unit verbatim in the advisor's "what changed" list. A non-UTF-8 round trip through an editor had
# replaced `µ`, `²` and `°` with `?`, so the API served `?mol/m?/s` and `?C`, and the same loss hit
# the docstrings in `simulation/factors.py` and `simulation/model_description.py` plus
# `docs/SIMULATION_METHODOLOGY.md`. Nothing failed: `?` is a perfectly valid character. The runtime
# assertion below pins the served values; the source scan stops the mangling coming back in the
# prose that documents them.
# ---------------------------------------------------------------------------------------------------

# A question mark welded to a token that should carry a symbol. Deliberately narrow so that a
# genuine interrogative (`... OSD-46?`), a JS ternary (`match ? a : b`) and a URL query
# (`...pdf?attachment=true`) do not match.
_LOST_SYMBOL = __import__("re").compile(
    r"\?mol"                      # ?mol/m?/s          ->  µmol/m²/s
    r"|\bm\?(?=[/\s.,)]|$)"      # mol/m?/day, area in m?,  ->  m²
    r"|\d\?C\b|\"\?C\""          # 22?C, "unit": "?C"      ->  °C
    r"|[A-Za-z]\?(?=[A-Z][a-z])"   # Penman?Monteith        ->  Penman–Monteith
)
_DOCS = APP.parent.parent / "docs"


def _mangled(paths: list[Path]) -> list[str]:
    offenders: list[str] = []
    for path in paths:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if _LOST_SYMBOL.search(line):
                offenders.append(f"{path}:{number}: {line.strip()[:120]}")
    return offenders


def test_the_lost_symbol_scan_is_not_vacuous():
    for damaged in (
        "PPFD in ?mol/m?/s",
        "0.0036 mol/m?/day",
        "cultivated area in m?,",
        "relative to 22?C/60% RH",
        '{"unit": "?C"}',
        "the full Penman?Monteith model",
    ):
        assert _LOST_SYMBOL.search(damaged) is not None, damaged
    for intact in (
        "Is OSD-320 an independent replication of OSD-46?",
        "return match ? match[0] : 'vendor'",
        ".../report.pdf?attachment=true",
        "PPFD in µmol/m²/s at 22 °C",
    ):
        assert _LOST_SYMBOL.search(intact) is None, intact


def test_no_source_or_document_has_lost_its_unit_symbols():
    sources = _python_sources() + sorted(_DOCS.glob("*.md"))
    assert _mangled(sources) == [], (
        "a unit symbol was replaced by a question mark; restore µ, ², ° or the operator "
        "rather than shipping the mangled text:\n" + "\n".join(_mangled(sources))
    )
