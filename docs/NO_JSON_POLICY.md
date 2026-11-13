# The no-JSON policy

**This repository stores no data in JSON files.** Not in a hidden directory, not in a generated
one, not inside a `.txt` with a JSON payload in it. The rule exists because a repository-wide
storage format should not also be the wire format: when every record is JSON, "the data" and
"the API response" stop being distinguishable, and a hand-edited configuration file looks
exactly like a machine-generated report.

**There are no exceptions.** 190 files were converted, removed or moved out of the tree - every record, fixture,
generated report and configuration file, including the two npm manifests this repository used to
carry. `frontend/package.json` and `frontend/package-lock.json` are gone too.

npm still reads only `package.json` and `package-lock.json`, and that cannot be changed. So the
repository holds the dependency set in files it is allowed to hold - `frontend/dependencies.toml`
(the manifest) and `frontend/dependencies.lock.mjs` (the lock, a generated module) - and
`frontend/scripts/npm.mjs` writes npm's two files into a temporary directory *outside* the
checkout, installs from them, and deletes them before the command returns. See
[The npm toolchain](#the-npm-toolchain) below.

## What a record is stored as now

| Shape | Used for | How it is read |
| --- | --- | --- |
| `name.py` | Nested, irregular records: model artifacts and cards, the registry, the catalogue, evidence and provenance records, checksum manifests, generated evaluation reports | A single `DATA = <literal>` parsed with `ast.literal_eval` - never executed, so a data file cannot run code |
| `name.csv` | Genuinely tabular series, where a table loses nothing | `csv.DictReader` |
| `name.yaml` | Configuration a person edits by hand, and the backup manifest | `yaml.safe_load` |
| `name.toml` | Hand-maintained configuration with a fixed schema - the frontend's dependency manifest, and the API's own settings | `tomllib`, and a 40-line reader for the same subset in `frontend/scripts/npm.mjs` |

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

## The npm toolchain

The frontend builds with Vite, Vitest, ESLint and Playwright, and all of them are npm packages
that have to be installed before they can run. npm reads JSON and nothing else, so the toolchain
is moved rather than the format:

| File | Role |
| --- | --- |
| `frontend/dependencies.toml` | The manifest a person edits: name, scripts, dependency ranges |
| `frontend/dependencies.lock.mjs` | The lock: 386 pinned packages with resolved URLs and integrity hashes, written by `npm.mjs --refresh-lock`, not by hand |
| `frontend/scripts/npm.mjs` | Writes both as npm's JSON into `<tmpdir>/spaceagrisim-frontend/<hash>/`, runs `npm ci`, deletes the JSON, symlinks `node_modules` back, and runs the requested script |

The install is reproducible: the lock pins the tree `npm ci` reproduced before, and it is checked
from both sides. `backend/tests/test_zero_json_policy.py` parses `dependencies.toml` with Python's
`tomllib` and pins the scripts, the dependency set and the version ranges, so a manifest that lost
an entry fails the backend suite. And `npm ci` refuses to install when the generated manifest
disagrees with the lock, so a reader that mis-read a line fails the frontend job on its first
command rather than a user's build.

Nothing outside the toolchain changes. The generated JSON lives in the system temporary
directory, is removed in a `finally` block (and on `SIGINT`), and the helper refuses a
destination inside the repository - a property the test suite runs rather than asserts:

```console
$ SPACEAGRISIM_NPM_WORKDIR=./frontend/work node scripts/npm.mjs ci
Error: refusing to materialise npm manifests inside the repository: .../frontend/work is
inside .../frontend. Set SPACEAGRISIM_NPM_WORKDIR to a directory outside it.
```

Because no `package.json` is in the tree, `npm ci`, `npm run` and `npx` have nothing to read
inside it. The workflows, `render.yaml`, the Dockerfile and the Playwright config all call
`node scripts/npm.mjs <script>` instead, and tool binaries are invoked directly
(`node node_modules/playwright/cli.js test`).

## The check

`backend/tests/test_zero_json_policy.py` enforces the rule on every test run:

- no `*.json`, `*.json5` or `*.jsonl` file anywhere in the tree - no exemption list - including
  hidden directories, `dist/`, Playwright output, and a JSON file hiding behind a second
  extension (`registry.json.bak`);
- no line of executable code opens, imports or names a `.json` path; comments and Markdown may
  explain the policy, code may not reach for a file;
- no workflow or script runs `npm ci`, `npm install` or `npm run` inside the repository, because
  that is the one command that writes a `package.json` there;
- the npm helper refuses a destination inside the checkout, and creates no file when it does;
- the data layer itself resolves records and rejects a `.json` name.
