# The no-JSON policy

**This repository stores no data in JSON files.** Not in a hidden directory, not in a generated
one, not inside a `.txt` with a JSON payload in it. The rule exists because a repository-wide
storage format should not also be the wire format: when every record is JSON, "the data" and
"the API response" stop being distinguishable, and a hand-edited configuration file looks
exactly like a machine-generated report.

Two files are exempt, and only two: `frontend/package.json` and `frontend/package-lock.json`.
They are the npm toolchain's own manifest format. `npm ci` exits with `ENOENT` without them and
`vite` cannot resolve a dependency graph without them, so no alternative exists short of
abandoning the frontend build. They hold no project data, no configuration this project chose,
and no scientific record. Everything else - 186 files - was converted or removed.

## What a record is stored as now

| Shape | Used for | How it is read |
| --- | --- | --- |
| `name.py` | Nested, irregular records: model artifacts and cards, the registry, the catalogue, evidence and provenance records, checksum manifests, generated evaluation reports | A single `DATA = <literal>` parsed with `ast.literal_eval` - never executed, so a data file cannot run code |
| `name.csv` | Genuinely tabular series, where a table loses nothing | `csv.DictReader` |
| `name.yaml` | Configuration a person edits by hand, and the backup manifest | `yaml.safe_load` |

A `.py` record is a literal, not an importable module with logic: `DATA = {...}` at module
scope and nothing else. It diffs line by line, it is checked by the same tools as the code
around it, and it needs no parser dependency.

## The one data layer

`safedata/` is the only thing that reads or writes a record. Callers name a record, not an
encoding:

```python
import safedata
registry = safedata.load("ml/artifacts/registry")      # resolves .py, .csv, .yaml
safedata.dump(record, "data/metadata/dataset_manifest")  # writes the canonical shape
```

- `load(path)` / `dump(obj, path)` / `render(obj)` - read, write, serialise in memory.
- `resolve(path)` - the file that holds a record; appends a known suffix, and accepts a legacy
  `.json` spelling left in an archived reference.
- `records(directory)` - data files in a directory, replacing `glob("*.json")`.
- `text(path)` / `bytes(path)` - raw content, for hashing and for the non-record files.
- `exists(path)` - a record exists in any known shape.

`dump()` is deterministic, which is what lets every `--check` gate regenerate a file in memory
and compare bytes with the committed one. Those gates are the reason a record cannot drift from
the script that produced it.

## Rules that follow from this

1. **No new `.json` file, anywhere.** Not as a fixture, not as a build product committed to the
   tree, not as an example in a document that a script later copies.
2. **No JSON text in another extension.** A `.txt`, `.yaml` or `.py` file holding a JSON
   document is a `.json` file with a misleading name.
3. **No feature may depend on a repository JSON file.** If a capability can only work by reading
   one, the capability is removed, along with the code, tests, UI and documentation that reach
   it.
4. **JSON on the wire is fine.** HTTP request and response bodies are JSON because HTTP APIs
   speak JSON; FastAPI's `/openapi.json` is generated at request time. Neither is a file in this
   repository, and no feature reads a JSON file from disk to serve them.

## What the exceptions cost

`frontend/package.json` and its lockfile are the boundary of the policy, and it is worth being
explicit about why the boundary sits there rather than being worked around. The lockfile records
the exact dependency tree that `npm ci` reproduces; it is machine-generated, and npm requires it
as JSON. Converting it to YAML would not remove a JSON dependency, it would break the install.

## The check

`backend/tests/test_zero_json_policy.py` enforces the rule on every test run:

- no `*.json` file anywhere in the tree outside the two npm manifests, including hidden
  directories, `dist/`, and Playwright output;
- no source file opens, imports or names a `.json` path, apart from the two manifests;
- the data layer itself resolves records and rejects a `.json` name.
