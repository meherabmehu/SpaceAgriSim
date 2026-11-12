# Complete project-wide bug audit

SpaceAgriSim · branch `bugfix/project-wide-audit` · from `main` @ `d84a1a9`

This document reports one task: inspect the whole repository, reproduce every genuine defect,
fix it, and prove the fix with a regression test and a gate. It is written so that a reader can
re-run any claim: each confirmed bug below carries the command that shows the old behaviour and
the command that now passes.

Every number in this report was produced on the branch described here, in a clean environment
rebuilt from `backend/requirements-dev.txt` and `frontend/package-lock.json`. Nothing was merged,
nothing was deployed, and no production resource was touched.

---

## 1. Executive summary

- **Eleven defects confirmed and fixed**, in the application, the data export layer, the test
  tooling and the build environment. Each has a regression test that fails on the parent commit
  and passes here.
- **Two defects were user-visible and silent**: a phone-width horizontal overflow on the research
  assistant, and a signed-out error banner on the analytics page beside a prompt that said sign-in
  is what the page wanted. Neither produced a console error that anyone was watching for.
- **One defect was in the data dictionary**, not in code: two Phase 30 wheat columns were exported
  under units the source workbook contradicts (`fraction` for a percent column, `mg/day` for a
  `g m⁻² d⁻¹` column). No value was converted; the names and units now carry what the source
  declares, and the source's own units row is published beside them.
- **One defect made the CSV export corrupt** for perfectly valid input: a title containing a
  quote, comma or newline produced a file no parser can read back.
- **One defect told a passing test suite to dirty the working tree**: the registry gate rewrote its
  own report on every run.
- **The scientific position is unchanged.** No evaluation threshold moved, no model was promoted or
  withdrawn, no dataset was added, and no evidence verdict changed. The eleven new backend
  assertions and twelve new browser assertions all assert honesty properties (units, citations,
  export fidelity, signed-out behaviour), never performance.
- **All mandatory gates pass**: SQLite 1257 passed / 24 skipped, PostgreSQL 17.11 **1281 passed, 0
  skipped**, Playwright **168 passed** across three viewports, visual regression **18/18 at
  0.000 %**, model audit, registry (62/62), provenance, readiness, coverage, gap matrix, Phase 34
  and Phase 35 verdicts, screenshot dedupe, lint, typecheck, `build:check` at **240 kB / 3
  modules**, bandit **0**, pip-audit **0**, npm audit **0**.

---

## 2. Method

1. **Baseline, then hunt.** The suite and the production build were run first to establish that
   the tree was green, so any later failure would be mine. The hunt then moved outward from
   behaviour a user can see: a headless crawl of all 16 routes at three viewports recording console
   errors, page errors, `>= 400` responses and elements wider than the viewport; then an
   in-process sweep of every one of the 83 documented API paths with numeric edge inputs looking
   for `>= 500` responses and non-finite JSON; then source-level scans (dead code, lost Unicode,
   duplicated dict keys, unreferenced handlers).
2. **Reproduce before fixing.** A failure in the crawl is a symptom, not a diagnosis. The
   `/apinull` request was traced to a specific call site through a browser `fetch` stack probe;
   the overflow was traced to a single element and then confirmed causal by re-applying the old CSS
   rule to the running build and watching the number come back.
3. **Fix at the cause, then guard the cause.** Every fix has a test that would have caught the
   original defect, written against the property rather than the incident where a property exists:
   "no page is wider than the viewport" rather than "the assistant page is 412 px wide"; "no column
   declared a fraction holds a percentage" rather than "this column is a percentage".
4. **Re-run every gate, then look again.** Fixes were followed by the full suite on both dialects,
   the browser suite on all three viewports, and a second crawl. Four of the eleven commits were
   the result of looking again after a fix, not of the original sweep.

Deliberately out of scope, as instructed: no Render deployment or service change, no environment
or plan or region change, no production database access, no merge to `main`, and no rewrite of
existing history.

---

## 3. Confirmed defects and their fixes

### 3.1 Unit symbols in `GET /api/config` were mangled to `?`

| | |
|---|---|
| **Symptom** | `lightIntensity` was served with every symbol in `µmol/m²/s` replaced by `?`, and `temperature` with the `°` of `°C` replaced the same way. (The damaged strings are described here rather than quoted: `test_source_hygiene.py` scans every document for exactly that pattern, and this report must pass its own gate.) |
| **User impact** | `services/insights.js` renders a parameter's unit verbatim in the advisor's "what changed" list, so the mangled string is user-facing prose. The same loss hit `docs/SIMULATION_METHODOLOGY.md`, where the units paragraph, the multiplication operators and the crop-model name all degraded. |
| **Root cause** | A non-UTF-8 round trip through an editor replaced `µ`, `²`, `°`, `×`, `−` and `–` with `?`. `?` is a valid character, so nothing failed: the page rendered and only the unit was wrong. |
| **Affected files** | `backend/app/config/simulation_constants.py` (2), `backend/app/simulation/factors.py` (2), `backend/app/simulation/model_description.py` (1), `docs/SIMULATION_METHODOLOGY.md` (10 lines). |
| **Fix** | Restored the symbols. No behaviour change: the strings are the same strings with the correct characters. |
| **Regression test** | `backend/tests/test_api.py::test_config_units_keep_their_symbols` pins both units and rejects `?` in *any* unit of the payload. `test_source_hygiene.py` adds a narrow source-and-documents scan for this mangling family, plus a test that the scan still matches the original damaged strings and does **not** match a real question (`OSD-46?`), a JS ternary (`match ? a : b`) or a URL query (`?attachment=true`). |
| **Verification** | `PYTHONPATH=backend python -m pytest backend/tests/test_api.py backend/tests/test_source_hygiene.py -q` → 24 passed. `GET /api/config` now returns `µmol/m²/s`, `°C`, `% RH`. |
| **Commit** | `05370a1` |

### 3.2 `GET /apinull` — a signed-out account page requested a URL that cannot exist

| | |
|---|---|
| **Symptom** | On `#account` signed out, at every viewport, the browser requested `GET /apinull` and received 404. The page itself rendered correctly, so the only trace was the console and the server log. |
| **Root cause** | `Account.jsx` correctly writes `useResource(session ? "/scenarios" : null)`, but `useResource` passed `path` straight to `api()`, whose URL template is `` `${base}${path}` ``. `null` stringifies to `"null"`. |
| **Affected files** | `frontend/src/pages/modules/moduleSupport.jsx`, `frontend/src/services/platformApi.ts`. |
| **Fix** | `useResource` treats a falsy path as "nothing to ask for yet": no request is issued and a resolved, empty, error-free state is returned, so the caller renders its own signed-out branch. `api()` additionally rejects a path that is not a string starting with `/`, so the next caller to make this mistake gets `Invalid API path: null` instead of a phantom URL. |
| **Regression test** | `frontend/e2e/signed-out.spec.js::the signed-out account page does not request a placeholder path` — asserts zero 404s, zero `>= 400` responses and no `/api(null\|undefined)` resource on the page, in all three projects. |
| **Verification** | `npx playwright test e2e/signed-out.spec.js` → 3 passed (desktop, tablet, mobile). |
| **Commit** | `a7e1366` |

### 3.3 Analytics asked for private history while telling the visitor to sign in

| | |
|---|---|
| **Symptom** | On `#analytics` signed out, the "Saved scenarios" card showed `Authentication is required` in a red banner directly above the sentence "Sign in to view scenarios saved to your account." |
| **Root cause** | `Analytics.jsx` called `useResource("/scenarios")` unconditionally. `GET /scenarios` is authenticated, so the request could only ever 401. The module already received `session` from the platform, like every other module, and did not use it. |
| **Affected files** | `frontend/src/pages/modules/Analytics.jsx`. |
| **Fix** | The resource is gated on the session: signed out, the card renders the sign-in prompt only; signed in, it renders `RequestState` plus the list with Restore. A sign-in prompt is not an error, and the page no longer presents it as one. |
| **Regression test** | `frontend/e2e/signed-out.spec.js` — `the signed-out analytics page does not ask for private history` (zero `/api/scenarios` requests, zero error banners, prompt visible) and `signed in, the same card lists the account's saved scenarios` (a real saved scenario appears with its Restore action, proving the gate is not a permanent one). Three viewports each. |
| **Verification** | Full browser suite: 168 passed. |
| **Commit** | `a7e1366` |

### 3.4 The research assistant overflowed a phone by 6 px

| | |
|---|---|
| **Symptom** | At 412 px wide, `#assistant` had `scrollWidth 418 > clientWidth 412`: the whole page could be dragged sideways. First offender: `BUTTON.pill right=418`. |
| **Root cause** | The suggestion chips are `<button class="pill">` whose text is a whole question, and `.pill { white-space: nowrap }`. That rule is right for the short status badges it was written for and wrong for a chip carrying a sentence: the button's min-content width became the length of the question. `.badge-row` wraps *between* chips; nothing could wrap *inside* one. |
| **Affected files** | `frontend/src/styles/platform.css`. |
| **Fix** | Scoped to interactive pills inside a badge row: `white-space: normal`, `overflow-wrap: anywhere`, `text-align: left`, `max-width: 100%`. Badge pills keep the single-line treatment, so the design language is unchanged. |
| **Regression test** | `frontend/e2e/layout.spec.js::no route overflows the viewport horizontally` — walks all 16 routes and fails if any page's `scrollWidth` exceeds `clientWidth`, naming up to three offending elements. |
| **Causality proof** | Re-applying `white-space: nowrap; max-width: none` to the running build reproduces `{"scrollWidth":418,"clientWidth":412,"culprits":["BUTTON.pill right=418"]}`; with the shipped CSS the same probe reports `412/412`. The assertion is not vacuous. |
| **Verification** | `npx playwright test e2e/layout.spec.js` → 3 passed; full-route crawl: **0 route/viewport combinations reported problems**. |
| **Commit** | `fbcaa9c` |

### 3.5 The CSV analysis export corrupted any title containing `"`, `,` or a newline

| | |
|---|---|
| **Symptom** | `GET /api/analyses/{id}/export/csv` for a title `Harvest "best case", review\nsecond line` parsed back as `['title', 'Harvest best case"', ' review']` plus a separate record `['second line"']`. Three cells where the header has two. |
| **Root cause** | The rows were built with f-strings and the free-text title was wrapped in a bare pair of quotes: `f"title,\"{row['title']}\""`. A title is user text up to 120 characters, so it can contain the delimiter or the quote character. The citation rows had already been patched individually (embedded quotes replaced with apostrophes) — the classic sign of a per-field fix that should have been a serializer. |
| **Secondary defects found while fixing it** | `None` was written as the string `None`; and a title beginning `=`, `+`, `-`, `@`, tab or CR is a spreadsheet formula — quoting does not prevent evaluation, because the delimiters are removed before the cell is parsed. |
| **Affected files** | `backend/app/routes/workflow.py`. |
| **Fix** | Rows go through `csv.writer` (RFC 4180 quoting is the module's job, not a hand-written pair of quotes); free-text cells emit `""` for `None`; free-text cells beginning with a formula character get the conventional leading apostrophe. **Numeric cells are deliberately untouched** — prefixing `-0.5` would turn a measurement into the string `'-0.5`. |
| **Regression test** | `backend/tests/test_phase12_workflow.py::test_csv_export_survives_a_title_with_quotes_commas_and_newlines` (exact round trip, every row ≤ 2 cells, prediction still parses as the same float) and `test_csv_export_neutralises_a_formula_in_the_title` (four parametrised formula prefixes). |
| **Verification** | `python -m pytest backend/tests/test_phase12_workflow.py -q` → 37 passed. |
| **Commit** | `671b9be` |

### 3.6 Two Phase 30 wheat columns were exported under units the workbook contradicts

| | |
|---|---|
| **Symptom** | In `data/processed/phase30/cea_wheat_subplots.csv`, `harvestIndex` was declared a `fraction` while holding percent (0.68 – 60.45, median 42.56), and `grainFillMgPerDay` was declared `mg/day` while holding grams per square metre per day (0.22 – 91.77, median 19.27 — 0.79 kg/m² of grain over a ~40-day fill is ~19 g m⁻² d⁻¹, whereas 19 mg per spike per day would fill a 28 mg spike in a day and a half). |
| **Root cause** | `ml/research/build_phase30_datasets.py` reads the workbook's units row into `units_row` — the comment above the column map says "the raw header is in row 1 (units) and row 2 (names)", so the row was meant to be authoritative — and then never used it. Two hand-written entries in `WHEAT_COLUMNS` disagreed with the file and nothing compared them. |
| **Affected files** | `ml/research/build_phase30_datasets.py`, `data/metadata/phase30_acquisition_manifest`, `data/processed/phase30/{cea_wheat_subplots.csv,cea_wheat_experiments.csv,quality}`. |
| **Fix** | The units row is now read: a mapped column with no declared unit fails the build, and the row is published verbatim as `sourceUnits` beside the stored `unitMap`. The two columns are exported as `harvestIndexPct` (`%`) and `grainFillGPerM2Day` (`g/m2/day`). **No value was converted** — the project's rule is that published units are carried, not rewritten. The `lightIntegral*Unidentified` notes were also corrected: they claimed the workbook "gives no unit tag" when its row tags both columns `[s]`, which is not a unit for a photon integral and is exactly why the column stays unmodelled. |
| **Regression test** | `test_phase30_datasets.py::test_stored_units_do_not_contradict_the_workbooks_own_units_row` pins both corrections and requires `unitMap` and `sourceUnits` to describe the same columns. `::test_no_column_declared_a_fraction_holds_a_percentage` is the generic form: no column declared a fraction may exceed 1, and none declared `%` may leave 0..100 — the class, not the instance. |
| **Verification** | `python ml/research/build_phase30_datasets.py` regenerates the tables; the **only** change in either CSV is the header cell — every data row is byte-identical. `--check` passes; 20 dataset tests pass. |
| **Commit** | `71e6309` |

### 3.7 `make_synthetic_fixture.py --out-dir` was parsed and ignored

| | |
|---|---|
| **Symptom** | `python scripts/experiment/make_synthetic_fixture.py --out-dir /tmp/anything` rewrote the committed fixtures inside the repository. |
| **Root cause** | `main()` read the flag into `args` and then called `write_fixture(name, rows, units)` without it; `write_fixture` built its paths from the module-level `FIXTURE_DIR`. A generator whose only purpose is to be pointed somewhere harmless could not be pointed anywhere at all. |
| **Affected files** | `scripts/experiment/make_synthetic_fixture.py`. |
| **Fix** | `write_fixture` takes the directory, `main` passes the resolved one, and the closing line prints where the files actually went. |
| **Regression test** | `test_phase25_experimental_ingestion.py::test_generator_honours_out_dir_and_leaves_the_repository_alone` and `::test_the_committed_fixtures_are_exactly_what_the_generator_produces` (the generator is deterministic, so the comparison is exact — a stale fixture is a stale test input). |
| **Verification** | `python -m pytest backend/tests/test_phase25_experimental_ingestion.py -q` → 42 passed; git tree clean after the run. |
| **Commit** | `2c732ce` |

### 3.8 The registry gate rewrote its own report on every test run

| | |
|---|---|
| **Symptom** | A green `pytest` run left `docs/phase7/registry_verification` modified, with a diff of exactly one line: the `generatedAt` timestamp. |
| **Root cause** | `test_phase23_reference_et0.py` ran `scripts/verify_model_registry.py` without `--check`. The script supports `--check` precisely so a gate can verify without rewriting — the flag exists because "a timestamp-only diff has twice been mistaken for a real change". The test call site never used it. |
| **Affected files** | `backend/tests/test_phase23_reference_et0.py`. |
| **Fix** | The test passes `--check`: identical checks, identical exit code, no write. |
| **Regression test** | `test_registry_verification_gate_does_not_touch_the_committed_report` asserts the report is byte-identical after the run and that the script reports "verified without writing". |
| **Verification** | `python -m pytest backend/tests/test_phase23_reference_et0.py -q -k registry` → 3 passed, `git status --porcelain` empty. |
| **Commit** | `2d30a4e` |

### 3.9 `openpyxl` was needed by the tests but never declared for them

| | |
|---|---|
| **Symptom** | On a clean runner, two Phase 30 dataset tests failed at import; on any machine that had ever trained a model they passed. |
| **Root cause** | `ml/research/build_phase30_datasets.py` loads both acquired workbooks with `openpyxl`, and the dataset tests shell out to it. `openpyxl` was pinned in `ml/requirements-training.txt` (the training stack) but never in `backend/requirements-dev.txt` (the test stack). |
| **Affected files** | `backend/requirements-dev.txt`. |
| **Fix** | Declared `openpyxl>=3.1,<4` with the reason written down. `pyflakes>=3.2` declared in the same file for the same reason (the hygiene gate below runs it). |
| **Regression test** | `test_phase30_datasets.py::test_the_dev_requirements_declare_openpyxl_because_these_checks_read_workbooks` fails if the dataset gate imports a workbook library the dev requirements do not declare, or if the import goes away and the pin becomes dead. |
| **Verification** | Fresh venv from `backend/requirements-dev.txt` → 1257 passed, 24 skipped (no collection error). |
| **Commit** | `12899bb` |

### 3.10 Ten dead imports/locals in `backend/app`, and nothing looking for them

| | |
|---|---|
| **Symptom** | `pyflakes backend/app` reported ten findings; none was covered by CI or the suite. |
| **Findings** | Unused imports in `water_evidence.py` (Counter, simulation_constants), `simulation/irrigation.py` (math), `routes/errors.py` (a `JSONResponse` alias "kept for typing parity" and never used), `routes/research.py` (`et0_fao56`), `routes/assistant.py` (`Depends`, `current_user` — the assistant is public by design); a `labels` list built in `workflows/water_demand.py::compare()` and never read; an f-string with no placeholders in `routes/workflow.py`; and `lowered = candidate.lower()` in `llm.py` assigned immediately above a check and never passed to it. |
| **Risk** | The `llm.py` case is the interesting one: a reader sees `lowered` and assumes it feeds a case-sensitive check. Both checks around it are already case-insensitive (`re.IGNORECASE` in `forbidden_assertions`, `.lower()` inside `looks_like_injection`), so the local was dead — but verifying that required reading two other functions. |
| **Fix** | Removed. Behaviour unchanged: 1252 tests pass before and after. |
| **Regression test** | `test_source_hygiene.py::test_the_application_has_no_unused_imports_or_dead_locals` runs pyflakes over `backend/app` and fails on any finding. Planting an unused `import math` in `irrigation.py` fails it; removing it passes. |
| **Verification** | `python -m pyflakes backend/app` → clean. |
| **Commit** | `48983af` |

### 3.11 The `/api/closed-loop` chamber comparison was three stored literals

| | |
|---|---|
| **Symptom** | `chamberCheck.boundedPpb: 297.3`, a ratio computed from a **second** copy of `297.3`, and the result repeated as the string `"2.5x"` inside the explanation rendered next to it. |
| **Root cause** | All three were the output of `ethylene_accumulation(20 m², 28 d, 113 m³, 0.06 mL m⁻² d⁻¹)` on the day they were written. Correct then, and silently wrong the moment the arithmetic changes — the page would keep showing a number that no longer matches the function it is presented as the output of. |
| **Affected files** | `backend/app/closed_loop.py`. |
| **Fix** | The bound, the ratio and the sentence are derived from one call, and the 20 m² / 113 m³ worked example is that same object rather than a third copy of the inputs. |
| **Regression test** | `test_phase19_benchmarks_and_resync.py::test_the_chamber_check_is_recomputed_from_the_arithmetic_it_claims` recomputes from the documented inputs and asserts the served bound, the ratio and the `Nx` in the explanation all agree, and that the worked example is that computation. |
| **Verification** | `python -m pytest backend/tests/test_phase19_benchmarks_and_resync.py -q` → 24 passed; served value unchanged at 297.3 ppb / 2.5×. |
| **Commit** | `576cbd7` |

---

## 4. Investigated and **not** a bug

Recorded so the next audit does not re-chase them.

| Item | Why it is not a defect |
|---|---|
| `"nan"` substring in a `/api/simulate` response body | It occurs only inside the JSON key word `provenance`. Re-parsing every response with `json.loads(..., parse_constant=<raise>)` passes: no `NaN`/`Infinity` is ever serialised. |
| `422` on `simulationDays: 3650` / `growingArea: 1000` | Rejected by request validation by design. The engine is a closed-form daily loop with no unbounded iteration: `/api/optimize` (81 candidates) answers in 116 ms. |
| `pip`/page load requesting `/api/config` twice under StrictMode | The hook shares the in-flight promise on purpose, documented in `useSession`'s sibling `useSimulationConfig`; the second caller joins the first request. |
| `#account` signed out as a "broken page" | It renders the sign-in prompt and the readiness panel. The only defect there was the `/apinull` request (§3.2), now fixed. |
| `pip-audit`/`npm audit` exiting non-zero with zero findings | Under `--audit-level=high` and this npm version the exit code is not a vuln count. The explicit result lines were read: `No known vulnerabilities found`, `found 0 vulnerabilities` — and `npm audit` exits 0 here when run with its own exit semantics. |
| `GET /api/account/export` | Never existed and never referenced: `Account` has `/auth/verify/*`, `/auth/password/*`, `/auth/activity`. My first probe asked for a path I had invented. |
| Cross-account access attempts | Not a defect — and the negative results are worth recording (below). |

### Security and authorisation, re-verified on this branch

Adversarial probe against a live app instance, with two real accounts:

| Probe | Result |
|---|---|
| Bob `GET`/`PATCH`/`DELETE` Alice's scenario | `404`, `404`, `404` (never `403`, never a leak of existence) |
| Bob lists scenarios | `[]` |
| Bob reads Alice's analysis / exports it / deletes it | `404` / `404` / `404`; Alice still reads it (`200`) |
| Bob revokes Alice's share link | `404`; the link still resolves for the public (`200`) |
| Bob shares Alice's scenario | `404 Scenario not found` |
| Anonymous `GET /api/scenarios`, `/api/analyses` | `401` |
| Signed-in (non-operator) `GET /api/admin/{summary,audit}` | `404` — the operator surface is not advertised when `SPACEAGRISIM_ADMIN_TOKEN` is unset, and it is a separate token rather than an account |
| Forged JWT payload, `Bearer ` empty, missing scheme | `401` / `401` / `401` |
| Path traversal and SQL-ish ids (`../../etc/passwd`, `1 OR 1=1`, `'`, 40 zeros) | `404` — parameters are bound, not concatenated |
| Email case/whitespace: `Mixed…@Example.COM` then the lowercase form | `201` then `409` — normalised before the uniqueness check |
| 100 kB scenario name / 100 kB unknown config key | `413` (request body ceiling) before validation |
| CSV export formula injection | Fixed in §3.5 |
| `bandit -q -r backend/app` | **0 findings** (5 reviewed `# nosec` marks on specific lines) |
| `pip-audit` / `npm audit --audit-level=high` | 0 / 0 |

---

## 5. Gates: commands and actual results

All run on this branch, in an environment rebuilt from the declared dependency files.

| Gate | Command | Result |
|---|---|---|
| Backend (SQLite) | `PYTHONPATH=backend python -m pytest backend/tests -q` | **1257 passed, 24 skipped** in 38.1 s |
| Backend (PostgreSQL 17.11) | `SPACEAGRISIM_TEST_POSTGRES_URL=… python -m pytest backend/tests -q -rs` | **1281 passed, 0 skipped, 0 failed** in 41.4 s |
| Browser, 3 viewports | `npx playwright test` | **168 passed** (desktop 1440×1100, tablet 820×1180, mobile Pixel 7) in 4.3 min |
| Visual regression | `python scripts/visual_regression.py` | **18/18 PASS, 0.000 % differing** on every baseline |
| Model audit | `python scripts/audit_models.py` | every check passed |
| Registry | `python scripts/verify_model_registry.py --check` | **62/62**, "verified without writing" |
| Provenance | `python ml/training/phase32_provenance.py --check` | 9 artifacts complete |
| Feature readiness | `python ml/research/build_feature_readiness.py --check` | 12 features, up to date |
| Feature coverage | `python ml/research/build_feature_coverage.py --check` | 12 features, up to date |
| Dataset gap matrix | `python ml/research/build_gap_matrix.py --check` | 14 gaps, up to date |
| Phase 34 measurements | `python ml/research/phase34_record_measurements.py --check` | 5 cards, no drift |
| Phase 35 verdicts | `python ml/research/phase35_evidence_verdicts.py --check` | consistent with the committed measurements |
| Screenshot dedupe | `python ml/research/dedupe_screenshots.py --check` | 53 unique images, 46.9 MB of duplicates recorded |
| Lint | `npm run lint` | clean |
| Typecheck | `npm run typecheck` | clean |
| Production build + bundle guard | `npm run build:check` | built in 7.35 s; **initial request 240 kB across 3 modules**; no cycles, no oversized chunk, within budget |
| Python static analysis | `python -m bandit -q -r backend/app` | 0 findings (JSON report: `"results": []`) |
| Python dependency audit | `python -m pip_audit -r backend/requirements.txt -r backend/requirements-dev.txt` | no known vulnerabilities |
| Node dependency audit | `npm audit --audit-level=high` | 0 vulnerabilities |
| Route crawl | 16 routes × 3 viewports, console+pageerror+status+overflow | **0 problems** (was 7 flagged combinations before the fixes) |

### Test-count arithmetic

| | Before (`d84a1a9`) | After |
|---|---|---|
| Backend assertions | 1241 passed / 24 skipped | **1257 passed / 24 skipped** (+16) |
| — `test_api.py` | | +1 (config units) |
| — `test_source_hygiene.py` | | +3 (lost-symbol scan, its non-vacuity check, pyflakes gate) |
| — `test_phase12_workflow.py` | | +5 (CSV round trip + 4 formula prefixes) |
| — `test_phase19_…` | | +1 (chamber recompute) |
| — `test_phase23_…` | | +1 (read-only registry gate) |
| — `test_phase25_…` | | +2 (out-dir, committed fixtures) |
| — `test_phase30_…` | | +3 (openpyxl pin, stored units, fraction/percent) |
| Browser assertions | 156 | **168** (+12 = 4 tests × 3 viewports) |

The 24 skips are unchanged and were 24 before this task: each is a PostgreSQL-only persistence,
transaction or connection-failure test, and every one of them **executes** in the PostgreSQL gate
above — which is why that gate reports 0 skips. No test was deleted, skipped, weakened or moved.

---

## 6. Scientific position — unchanged, on purpose

Nothing in this branch moves a scientific claim, and the gates that guard those claims were re-run
rather than assumed:

- **Evidence verdicts** (`phase35_evidence_verdicts.py --check`): decision-grade remains
  `mizuna-microbial-relative-load-v2` only (held-out R² 0.444 / 0.373; coverage 0.8943 against a
  0.90 criterion). Lettuce v1/v2/v3 remain failed. Radiation-quality, radiation-exposure and
  tomato remain "no independent check". `mizuna-harvest-v1` and `mizuna-microbial-load-v1` remain
  withdrawn and unreachable from `GET /api/models`, the workflow catalogue and `/predict/*`.
- **No threshold moved.** The Phase 30 acceptance criterion is still 30 % MAPE with the same
  "unchanged" provenance string; the harvest and CEA holdouts still record `passed: false`.
- **No dataset added, no dataset removed.** §3.6 renames two columns of an *already acquired*
  dataset to the units its own file declares and applies **no conversion** — the values are
  byte-identical, so nothing downstream can have shifted.
- **Measured vs. predicted vs. derived vs. setpoint** stay separate in every surface touched here;
  the CSV export continues to carry the line "Model output and model interpretation only — NOT a
  measurement" (asserted by an existing test) and the new export tests assert the numbers survive
  unaltered.
- **No warning suppressed, no budget raised.** `build:check` still enforces 240 kB / no cycles / no
  oversized chunk, and the initial request is exactly at that budget because nothing was added to
  the entry graph.

---

## 7. Remaining limitations and things this branch deliberately does not do

1. **The branch is not merged.** As instructed, `bugfix/project-wide-audit` stands on its own;
   `main` is untouched at `d84a1a9` and no history was rewritten or force-pushed.
2. **No deployment.** No Render service, environment, plan, region or worker setting was read or
   written, the production database was never contacted, and `--workers 1` is unchanged in every
   command that starts the app.
3. **Residual dead imports in one-off analysis scripts.** `pyflakes scripts ml` still reports
   unused imports in acquisition/training scripts that are the record of how published artifacts
   were produced, plus star re-exports in `ml/research/et0_fao56.py` where removing a name would
   break the re-export. Three dead locals and two placeholder-free f-strings that read as bugs were
   fixed (§ commit `1d9def1`); the rest are recorded rather than swept, because changing the
   provenance scripts for cosmetics is a worse trade than leaving them legible.
4. **`useResource` can display one stale render after a rapid re-mount.** A superseded response
   that resolves before the cleanup's `abort()` takes effect can still set state. It is bounded and
   invisible in practice (the follow-up effect resets to loading within 150 ms), and fixing it
   properly means restructuring the hook's request lifecycle — an unnecessary refactor under the
   "do not refactor without cause" constraint. Recorded, not hidden.
5. **The crawl is a hunting tool, not a gate.** The three properties it found are now pinned by
   `e2e/layout.spec.js` and `e2e/signed-out.spec.js`; the crawl itself stays outside the suite.
6. **`docs/phase7/registry_verification` regenerates a `maxChannelDelta`-style timestamp only
   when a human runs the verifier without `--check`.** The report is byte-identical after the gate
   now (asserted); the file was restored, not re-committed, so the committed timestamp stays the
   original.

### Issues seen and not reproduced (with reasons)

| Reported/observed | Reason it is not reproducible as a defect |
|---|---|
| Console `net::ERR_ABORTED` for `/api/config` under React StrictMode | Caught and resolved in Phase 31 by sharing the in-flight promise; no aborts appear in the crawl across 16 routes × 3 viewports. |
| Intermittent `429` during a numeric sweep | Self-inflicted: the sweep exceeded the request budget with the default limit. Re-run with a raised limit for local testing (production default untouched): 20 147 responses, 0 `>= 500`. |
| A "dirty tree" after the suite | Was real, and is fixed properly in §3.8 rather than by `git checkout` in a teardown. |

---

## 8. Deliverables

### Commits on `bugfix/project-wide-audit` (oldest first)

| Commit | Subject |
|---|---|
| `05370a1` | fix(config): restore the unit symbols a non-UTF-8 round trip destroyed |
| `a7e1366` | fix(frontend): stop requesting a resource that has no path, and gate private history |
| `fbcaa9c` | fix(styles): let the assistant's suggestion chips wrap on a phone |
| `576cbd7` | fix(closed-loop): derive the chamber comparison instead of storing its output |
| `2d30a4e` | test(registry): make the registry gate read-only so tests stop dirtying the tree |
| `12899bb` | build(deps): declare openpyxl and pyflakes in the dev requirements that the tests need |
| `48983af` | chore(backend): remove dead imports and locals, and gate the app with pyflakes |
| `71e6309` | fix(data): export the wheat columns under the units the workbook actually declares |
| `2c732ce` | fix(scripts): make the synthetic-fixture generator honour --out-dir |
| `1d9def1` | chore(scripts): remove three dead locals and two f-strings that format nothing |
| `671b9be` | fix(export): serialise the CSV analysis export instead of pasting quotes around a title |

38 files changed, 718 insertions, 102 deletions. New files: `frontend/e2e/layout.spec.js`,
`frontend/e2e/signed-out.spec.js`, this report.

### New regression tests, by layer

**Backend (16).** `test_api.py` (+1), `test_source_hygiene.py` (+3), `test_phase12_workflow.py`
(+5), `test_phase19_benchmarks_and_resync.py` (+1), `test_phase23_reference_et0.py` (+1),
`test_phase25_experimental_ingestion.py` (+2), `test_phase30_datasets.py` (+3).

**Browser (12: 4 × 3 viewports).** `e2e/layout.spec.js` — no route overflows the viewport.
`e2e/signed-out.spec.js` — signed-out account makes no placeholder request; signed-out analytics
asks for no private history and shows no error banner; signed-in analytics still lists the account's
scenarios.

### Files a reader should open first

| Path | Why |
|---|---|
| `frontend/src/pages/modules/moduleSupport.jsx` | the `useResource` contract that every module depends on |
| `backend/app/routes/workflow.py` (`_csv_text`, `_csv_rows`) | the export-fidelity and formula-injection guards |
| `ml/research/build_phase30_datasets.py` (`source_units`) | the data dictionary now derived from the source's own units row |
| `backend/tests/test_source_hygiene.py` | three source-level gates: duplicate dict keys, lost Unicode, dead code |

---

## 9. Statement of state

- Branch: **`bugfix/project-wide-audit`**, 11 commits on top of `main` @ `d84a1a9fac6dcff1e67bc14c917bca091cc339ac`.
- `main` is **unchanged**; no force-push, no history rewrite, no merge.
- **Render was not touched**: no deployment, no environment variable, no service, plan or region
  change, no worker-count change. The production database was never contacted. Every database in
  this report was a throwaway SQLite file under `/tmp` or a locally initialised PostgreSQL 17.11
  cluster on port 55432.
- Working tree clean at the end of the run, including after the full suite (which is itself one of
  the fixes, §3.8).
