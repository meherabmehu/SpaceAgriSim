# Guided Workflows — end-to-end fix report

**Branch:** `fix/guided-workflows-e2e` (off `71347d2` on `main`)
**Commits:** `b9bf9f2` — the three actions; `3624ba9` — bundle budget and header layout
**Remote verified:** `git ls-remote` → `3624ba98f7ee638554e08b91a39d566a563e4660` = local `HEAD`
**Deployment:** none. No Render trigger, no config or environment change, no production database
touched. The branch is not merged and nothing in this report describes running production code.

---

## 1. Root cause per reported failure

### 1.1 Factor + band → "Show measured results" returns the wrong response

Three defects, all reproduced before any change:

| # | Defect | Evidence |
|---|---|---|
| a | The capability shipped band **ids only** (`ambient`, `enriched`, `high`). Every label the page printed was a hand-written second copy of a predicate that lives in Python. | Band select rendered the raw ids. |
| b | The two copies had already diverged. The predicate was `low <= v <= high`; the label said `< 23 C`. | Five experiments measured at exactly **23.0 °C** appeared under a band whose label excluded them; five at 25.0 °C under `mid`. |
| c | The interval was `mean ± 1.96·sd/√n`, printed even at n = 2. | Photoperiod ≤ 12 h (n = 2): printed **−0.133 … 0.666** for a yield that cannot be negative. |

A fourth defect was found while testing (d): a selection naming a band that belongs to a *different
factor* (e.g. `co2Ppm` + `low`) passed validation, was skipped by the service, and answered **200
with an empty group list** — indistinguishable to a client from a real band holding no experiments.

**Fix.** Bands now carry explicit bounds (`min`, `minInclusive`, `max`, `maxInclusive`, `openUpper`,
`unitSymbol`) and their labels are *derived* from those same bounds, so the label and the filter
cannot disagree. The interval is Student-t (`df = n − 1`) and is reported only from
`MIN_INTERVAL_N = 3` experiments upward; below that the response carries
`ciStatus: "insufficient-observations"` and a note, and the table prints the count instead of an
interval. When a t-interval crosses below the observed minimum it is kept and carries `ciCaveat`.
Cross-factor pairs are rejected as 422 with the allowed band names for that factor. Empty bands are
returned as an explicit `empty: true` group rather than silently absent.

### 1.2 Save scenario does not work

Investigated against the running stack rather than assumed. What was actually wrong:

| # | Defect | Evidence |
|---|---|---|
| a | The confirmation was rendered in the page-wide notice at the **top** of a long page while the button sits in the footer. | On desktop the save button is at y ≈ 1611 in a 900 px viewport; the notice appeared at y ≈ −598 after the click. |
| b | No identifier was shown, and the saved row could not be reopened from the UI. | The message was the fixed string "Scenario saved to mission history." |
| c | Nothing prevented a double press; a second identical save wrote a second row. | Two POSTs → two rows. |
| d | A guided-workflow save recorded the habitat configuration and **nothing about the measured band** the user was reading, so reopening it lost the evidence. | No field existed for it. |
| e | The account page read `scenario.createdAt`, but the API returns `created_at`. | Every saved scenario showed "Invalid Date". |

**Fix.** `POST /api/scenarios` accepts an optional `context` (workflow, factor, band, band label,
the measured summary as returned, dataset, evidence class) and returns the stored row including it.
A byte-identical repeat — same name, configuration and context — answers **409** with the existing
`scenarioId` instead of writing a twin. The button reports the real UUID beside itself, is disabled
while in flight, and shows the duplicate answer as "already saved", not as a failure. The account
page reads `created_at`, prints the id, and prints the recorded band and summary.

### 1.3 Export mission does not work

| # | Defect | Evidence |
|---|---|---|
| a | The button POSTed `/reports/json` and named the file on the client (`spaceagrisim-mission.json`). | A PDF built from one configuration arrived under a name that knew nothing about it. |
| b | `fetch` resolves on 422 as happily as on 200, and the body was saved as a file. | A validation error would be downloaded as `report.pdf`. |
| c | The measured band had **no export at all**. | No route existed. |

**Fix.** New `POST /api/workflows/light-stress/controlled-environment/export` renders **CSV and PDF**
from the same service the run uses: provenance, licence, citation, raw-file SHA-256, the selection
and its bounds in the factor's units, every experiment in the band, the summary, the DLI correlation,
the model-attempt record and the limitations. The mission header offers **PDF and CSV**; the download
helper takes its filename from `Content-Disposition`, refuses an empty body, and surfaces the
server's message instead of saving an error page.

---

## 2. Endpoints

| Method | Path | Change |
|---|---|---|
| POST | `/api/workflows/light-stress/controlled-environment/run` | cross-factor rejections now 422 (was 200 + empty list); groups carry `bandLabel`, `bandBounds`, `unitSymbol`, `empty`; summaries carry `ciStatus`/`ciMethod`/`ciDf`/`ciNote`/`ciCaveat` |
| GET | `/api/workflows/light-stress/controlled-environment/capability` | new `fields[1].labels`, `statistics`, `dataset.classifiableExperiments` / `unclassifiableExperiments` |
| POST | `/api/workflows/light-stress/controlled-environment/export` | **new** — `{selections, format: "csv" \| "pdf", configuration?}` → attachment |
| POST | `/api/scenarios` | accepts optional `context`; returns it; 409 + `scenarioId` on an identical repeat |
| GET | `/api/scenarios`, `/api/scenarios/{id}` | return `context` (decoded) |

## 3. Database change

One additive column on `scenarios`:

```
context TEXT NULL
```

Applied by `storage._migrate_scenarios_context(engine)` — idempotent, additive, rewrites no row,
runs on every start. A plain Mission Control save stores `NULL`, which is a complete record, not a
partial one. Covered by a test that builds a pre-existing table, inserts a row, migrates twice, and
asserts the row is untouched.

## 4. Files changed (20; +2363 / −259)

```
M backend/app/routes/workflows.py           run→422, export route, CeaExportRequest, band/factor pairing
M backend/app/routes/workspace.py           WorkflowContext, context on save/read, 409 duplicate
M backend/app/storage.py                    context column + migration, find_duplicate_scenario
M backend/app/workflows/cea_evidence.py     bounds, derived labels, t-interval, validation, unitSymbol
A backend/app/workflows/cea_export.py       CSV + PDF renderer, server-side filename
A backend/tests/test_cea_evidence_api.py    28 API tests
A backend/tests/test_guided_workflow_save.py 20 persistence/ownership/migration tests
A frontend/e2e/guided-workflow-actions.spec.js 10 browser journeys × 3 viewports
M frontend/e2e/mission.spec.js              save confirmation now the id, beside the button
M frontend/e2e/workflow.spec.js             exact "CSV" selector (the header now also offers CSV)
A frontend/src/pages/AuthDialog.jsx         extracted modal, loaded on demand
M frontend/src/pages/MissionPlatform.jsx    export pair, save state, Metric restored
M frontend/src/pages/modules/Account.jsx    created_at, id, workflow record
M frontend/src/pages/modules/GuidedWorkflows.jsx band labels, CI, empty state, export, save
A frontend/src/services/downloads.ts        postForFile, filenameFromDisposition (dynamic import)
M frontend/src/services/platformApi.ts      structured error carries status + scenarioId
A frontend/src/services/downloads.test.js   8 unit tests
M frontend/src/styles/platform.css          export pair, save status, mobile icon column
M scripts/compare_ui_screenshots.py         uint8 comparison (was int64; OOM on capture host)
M docs/phase7/ui_preservation.py            regenerated record for this branch
```

## 5. Test results (all run in this session, on this tree)

| Suite | Result |
|---|---|
| Backend, SQLite | **1492 passed, 23 skipped** (base `71347d2`: 1444 passed, 23 skipped — **+48**, no existing test changed status) |
| Backend, PostgreSQL 17.11 (isolated) | **1515 passed, 0 skipped** |
| Frontend unit (vitest, jsdom) | **28 passed** in 3 files (8 new) |
| Frontend lint / typecheck | pass |
| `build:check` | pass — initial request **236 kB** across 3 modules, no cycles, no oversized chunk |
| Playwright (desktop / tablet / mobile) | **201 passed** (base: 171 → **+30**) |
| Science gates (9) | all pass — `audit_models`, registry checksums, provenance (9 artifacts), feature readiness (12), coverage (12), gap matrix (14 gaps), phase-34 measurements (5 cards), phase-35 verdicts, screenshot dedupe (71 unique, 0.0 MB duplicates) |
| Visual gate | `ui-extended-layout-preserved`, **0 px structural drift** at all three viewports |
| Zero JSON | `git ls-files` match for `.json/.json5/.jsonl/.jsonc/.ndjson/.geojson` = **0**; worktree = **0** |

The 23 SQLite skips are all PostgreSQL-gated assertions, each with its own recorded reason
(`SPACEAGRISIM_TEST_POSTGRES_URL is not set`); every one of them runs and passes in the PostgreSQL
row above. No skip was added, no test weakened, no threshold moved.

## 6. Verification of the three journeys (real, not asserted)

Reproduced in a real browser against the production build and the live API:

- band select reads `≤ 450 ppm · 29 experiments`, `> 450 to ≤ 800 ppm · 2 experiments`, `> 800 ppm · 5 experiments`;
- row for `co2Ppm / ambient`: 29 experiments, mean 0.671, interval 0.516–0.826, median 0.699, range 0.062–1.442;
- row for `photoperiodHours / short` (n = 2): count 2 and the sentence explaining that a 95 % interval
  needs at least 3 — no interval printed;
- CSV 5 128 bytes / 59 lines, PDF 2 pages starting `%PDF-`, both named
  `spaceagrisim-cea-wheat-co2Ppm-ambient-20261113.<fmt>` by the server;
- save → `Saved to your account as 4f91d64a-…`; second press → `This measured band is already saved as 4f91d64a-…`;
  `GET /api/scenarios/{id}` returns the identical `measured` object and `bandLabel`;
- mission header → PDF 2 447 bytes, CSV 2 006 bytes, both under the server's names;
- signed out → "Sign in to save…" and the dialog opens; nothing claims a save.

## 7. Limitations

- **CI did not run for this branch.** `.github/workflows/ci.yml` triggers on push to `main` or
  `feat/**` and on `pull_request`; `fix/guided-workflows-e2e` matches neither, and the API reports
  `total_count: 0`. I did not change the trigger. Every command the five CI jobs run was executed
  locally with the results above — that is local evidence, not a CI result.
- **Visual gate is a structure comparison, not a pixel-identical one.** Desktop 0.44 %, tablet 0.88 %
  and mobile 0.15 % of pixels differ, all classified `glyph-rasterisation` (the capture host's font
  build), with every structural edge present in both renders at 0 px drift. This is the same
  environment-attributed residual the repository already records; it is *not* a pixel-identical pass.
- **The two export buttons changed the phone header.** To keep the title's width and the page height
  they stack as icon buttons in the column the old single button used; that is why the verdict is
  `ui-extended-layout-preserved` rather than `ui-unchanged`.
- `POST /api/reports/json` still exists on the server and is still documented in
  `docs/API_DOCUMENTATION.md`; only the UI stopped offering it. Removing it is a separate decision
  about a public endpoint, not part of this fix.
- The dataset holds 39 experiments, 36 of which carry both a yield and an environment row. The three
  that do not are excluded from every band, and the capability now states that number and the reason
  instead of letting the partition silently add up to less than the series claims.
- Nothing was deployed and no production database was read or written.
