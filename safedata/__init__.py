"""The repository's one data-file layer. No JSON is ever read or written here.

Every structured record this project keeps - model cards, the model registry, the dataset
catalogue, evidence records, provenance and checksum manifests, the scientific gap matrix,
feature readiness and coverage, configuration, fixtures and generated evaluation reports -
lives in one of exactly three shapes:

    name.py      A Python module holding a single ``DATA`` literal. Used for nested,
                 irregular records where a table would lose structure. This is the format
                 for code-owned metadata: it is parsed with ``ast.literal_eval`` and never
                 executed, so loading a data file cannot run code.
    name.csv     Long- or wide-format tables, for genuinely tabular series.
    name.yaml    Human-maintained configuration, where a person edits by hand.

``load(path)`` accepts a path with or without a known suffix and resolves whichever file
actually exists, so callers name a record rather than an encoding. ``dump(obj, path)``
writes the record back in its canonical shape, deterministically, which is what lets the
``--check`` gates regenerate a file in memory and compare bytes with the committed one.

Why not JSON: see docs/NO_JSON_POLICY.md. The short version is that a repository-wide
storage format should not also be the wire format, and a nested literal in a Python module
is readable, diffable, type-exact and importable without a parser dependency.
"""
from __future__ import annotations

import ast
import csv
import io
import pprint
from pathlib import Path
from typing import Any

__all__ = ["load", "dump", "render", "resolve", "exists", "records", "text", "bytes",
           "loads_python_module", "SUFFIXES"]

#: Formats a record may be stored in, in resolution order.
SUFFIXES = (".py", ".csv", ".yaml", ".yml")

_MISSING = object()


class DataFileError(RuntimeError):
    """A data record is missing, unreadable or stored in an unknown shape."""


def resolve(path) -> Path:
    """Return the file that holds the record named by ``path``.

    ``path`` may name the record without a suffix (``data/research/dataset_gap_matrix``),
    carry the format suffix (``.../dataset_gap_matrix.py``), or carry a legacy ``.json``
    spelling left in an archived reference. Resolution appends a known suffix first, so a
    name that already ends in its own dot-suffix - a fixture's ``.units`` sidecar, say -
    is not mistaken for a stem that lost an extension.
    """
    p = Path(path)
    if p.is_file():
        return p
    if p.suffix in SUFFIXES:
        raise DataFileError(f"{p}: named file is absent")
    for suffix in SUFFIXES:
        candidate = Path(str(p) + suffix)
        if candidate.is_file():
            return candidate
    if p.suffix == ".json":          # legacy spelling in an archived reference
        stem = p.with_suffix("")
        for suffix in SUFFIXES:
            candidate = stem.with_suffix(suffix)
            if candidate.is_file():
                return candidate
    raise DataFileError(
        f"no data record at {p} (tried {', '.join(str(p) + s for s in SUFFIXES)})"
    )


def exists(path) -> bool:
    """True if ``path`` is a real file or directory, or a record held in a known format."""
    try:
        candidate = Path(path)
    except TypeError:
        return False
    if candidate.exists():
        return True
    try:
        resolve(candidate)
    except DataFileError:
        return False
    return True


def load(path, default=_MISSING) -> Any:
    """Read the record at ``path``. A copy is returned on every call, never a shared cache."""
    try:
        target = resolve(path)
    except DataFileError:
        if default is _MISSING:
            raise
        return default
    suffix = target.suffix.lower()
    if suffix == ".py":
        return loads_python_module(target.read_text(encoding="utf-8"), where=str(target))
    if suffix == ".csv":
        return _load_csv(target)
    if suffix in (".yaml", ".yml"):
        import yaml

        return yaml.safe_load(target.read_text(encoding="utf-8"))
    raise DataFileError(f"{target}: unsupported data format {suffix}")


def bytes(path) -> bytes:
    """The bytes of a record's file, after resolution. Used wherever a digest is taken."""
    return resolve(path).read_bytes()


def text(path) -> str:
    """The raw text of a record, for callers that hash or diff it."""
    return resolve(path).read_text(encoding="utf-8")


def loads_python_module(source: str, where: str = "<string>") -> Any:
    """Evaluate the ``DATA`` literal of a data module without executing the module.

    ``ast.literal_eval`` only accepts literals, so a data file cannot import, call or
    otherwise run anything. That property is the reason the format is a module and not a
    pickle.
    """
    tree = ast.parse(source, filename=where)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "DATA":
                    return ast.literal_eval(node.value)
    raise DataFileError(f"{where}: no DATA assignment")


def dump(obj: Any, path) -> Path:
    """Write ``obj`` to ``path`` in its canonical non-JSON shape and return the file.

    The suffix of ``path`` selects the format: ``.csv`` writes a table, ``.yaml``/``.yml``
    writes YAML, and anything else writes a Python data module with that name and ``.py``.
    """
    p = Path(path)
    if p.suffix == ".csv":
        _dump_csv(obj, p)
        return p
    if p.suffix == ".json":
        p = p.with_suffix("")
    if p.suffix in (".yaml", ".yml"):
        import yaml

        header = "# Data record. Generated - the generator is named inside the record itself.\n"
        p.write_text(header + yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=110),
                     encoding="utf-8")
        return p
    # A name that already carries its own dot-suffix (``x.dump.manifest``) keeps it; only a
    # bare stem or a legacy ``.json`` spelling is replaced by ``.py``.
    target = p if p.suffix == ".py" else Path(str(p) + ".py")
    target.write_text(_render_python_module(obj), encoding="utf-8")
    return target


def records(directory) -> list:
    """Every data record stored directly in ``directory``, sorted, as file paths.

    This replaces ``directory.glob("*.json")``. It returns files whose suffix is one of
    :data:`SUFFIXES`, so directories, caches and unrelated files are excluded by
    construction rather than by a glob pattern that has to be kept in step.
    """
    d = Path(directory)
    if not d.is_dir():
        return []
    return sorted(p for p in d.iterdir() if p.is_file() and p.suffix in SUFFIXES)


def render(obj: Any) -> str:
    """The canonical text of a record, so a generator can compare bytes without writing."""
    return _render_python_module(obj)


def _render_python_module(obj: Any) -> str:
    # compact=True packs a long sequence of numbers onto the lines it fits instead of one item
    # per line. A learned forest is thousands of short float lists, and the indentation the
    # unpacked form adds to every one of them doubled the size of the largest artifact; the
    # packed form is smaller than the JSON it replaced and still diffs key by key.
    body = pprint.pformat(obj, width=110, sort_dicts=False, compact=True)
    return (
        '"""Data record. Generated - the generator is named inside the record itself."""\n\n'
        f"DATA = {body}\n"
    )


def _load_csv(path: Path) -> list:
    with path.open(newline="", encoding="utf-8") as handle:
        return [_coerce_row(row) for row in csv.DictReader(handle)]


def _dump_csv(obj, path: Path) -> None:
    if not isinstance(obj, list) or not obj:
        raise DataFileError(f"{path}: CSV export expects a non-empty list of records")
    fields: list[str] = []
    for row in obj:
        for key in row:
            if key not in fields:
                fields.append(key)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in obj:
        writer.writerow({k: _format_cell(v) for k, v in row.items()})
    path.write_text(buffer.getvalue(), encoding="utf-8")


def _format_cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _coerce_row(row: dict) -> dict:
    return {key: _coerce_cell(value) for key, value in row.items()}


def _coerce_cell(value: str):
    if value == "":
        return None
    if value == "true":
        return True
    if value == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value
