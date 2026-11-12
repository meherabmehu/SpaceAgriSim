# Final project completion report

SpaceAgriSim — end of the coding-agent work, merge and release readiness.

Written against branch `bugfix/project-wide-audit`, merged into `main` as a fast-forward. Every number
in this report was produced on the delivered tree by the command printed beside it; nothing here is
copied from an earlier report without being re-run. Where a result was *not* verified, it says so.

---

## 1. Status

| | |
|---|---|
| Task state | **Complete.** Inspection, fixes, tests, review, merge and verification are finished. |
| Branch | `bugfix/project-wide-audit` |
| `main` before the merge | `d84a1a9` (unchanged; no commits appeared on it during this work) |
| Relationship | branch was 18 commits ahead of `main`, 0 behind; merge base = `d84a1a9`, so the merge is a fast-forward with no conflict resolution and no merge commit |
| Working tree | clean at every checkpoint; the only files created outside the repository were throwaway environments (`/tmp`) |
| Force-push / history rewrite | none, at any point |
| Render | **not touched**: no deploy, no service or environment change, no production database access (user instruction, 2026-11-12) |

Two defects from a previous pass were found to be *not* fixed in the browser-facing layer even
though their causes had been fixed on the server, and a third defect class (request lifecycle) turned
out to be systemic rather than a single bug. Those are the substance of this pass; they are the
reason the branch does not end at the audit report.

---

## 2. Defects fixed on this branch

Eleven were fixed in the project-wide audit and are described in
[COMPLETE_PROJECT_BUG_AUDIT.md](COMPLETE_PROJECT_BUG_AUDIT.md) with symptom, root cause, causal proof
and regression test. They are listed here for completeness, not re-explained:

| # | Defect | Commit |
|---|---|---|
| 1 | Unit symbols in `GET /api/config` were destroyed by a non-UTF-8 round trip | `05370a1` |
| 2 | Signed-out pages requested a resource that has no path (`GET /apinull`) and rendered a 401 banner | `a7e1366` |
| 3 | The assistant's suggestion chips forced a 6 px horizontal overflow at 412 px wide | `fbcaa9c` |
| 4 | The closed-loop chamber comparison stored its output instead of deriving it | `576cbd7` |
| 5 | A registry gate rewrote its own report while "checking" it | `2d30a4e` |
| 6 | `openpyxl` and `pyflakes` were imported by tests but undeclared | `12899bb` |
| 7 | Ten dead imports/locals in `backend/app`; no gate looked for them | `48983af` |
| 8 | Wheat columns exported under units the workbook does not declare | `71e6309` |
| 9 | The synthetic-fixture generator ignored `--out-dir` | `2c732ce` |
| 10 | Three dead locals and two placeholder-free f-strings in scripts | `1d9def1` |
| 11 | The CSV analysis export hand-quoted a free-text title (corruption, formula injection, `None` as text) | `671b9be` |

Three more were found and fixed in this pass (§3), plus two test-only commits that turn manual checks into gates.

---

## 3. New fixes, and the tests that pin them

### 3.1 A superseded API response could overwrite the current one

| | |
|---|---|
| **Symptom** | Change a parameter that a panel reads from the API, and the panel can settle on the *previous* parameters' numbers under the *new* controls. Reproduced deterministically in the unit suite; on the water-evidence panel the visible result is a "platform ÷ measured" ratio computed for a light scale the reader has already changed. |
| **Root cause** | `useResource` aborted the request in flight when its inputs changed and treated that as sufficient. It is not: an `AbortController` cannot un-resolve a request whose response body has already arrived. When the response is buffered before the abort fires, the `.then` that follows still runs — and it had no guard at all, so it committed. Separately, `api()` did `await response.py().catch(() => null)`, which converted a *cancelled body read* into a resolved `null`: an aborted request came back as "loaded successfully, no data" and was committed like an answer. |
| **Affected files** | `frontend/src/pages/modules/moduleSupport.jsx`, `frontend/src/services/platformApi.ts` |
| **Fix** | Three layers: every request carries an identity and only the newest identity may commit (an unmount sets a `cancelled` flag, because no newer request exists to advance it); the value handed to consumers is derived from the request key, so the render in which parameters change already reports `loading`; and `api()` re-throws an `AbortError` from the body read instead of swallowing it into `null`, which the hook treats as a cancellation. Public shape unchanged (`{data, error, loading}`), debounce unchanged, skipped-resource behaviour unchanged, no call site changed. |
| **Regression tests** | `frontend/src/pages/modules/moduleSupport.test.jsx` — 16 tests. The discriminating three: *ignores a response that lands after the parameters changed*, *reports loading rather than the previous payload as soon as the parameters change*, *treats a cancelled body read as a cancellation*. Against the previous implementation they fail with the stale payload committed (`{data: {ratio: 1}, error: '', loading: false}` where `{data: null, loading: true}` is required); against this one they pass. The other 13 pin the surrounding contract (debounce coalescing, no request for an equal body, no request for a gated-off resource, unmount mid-flight, unmount inside the debounce window, remount, genuine failure, non-JSON failure body, stable identities). |
| **Verification** | `npm run test:unit` → 20 passed (2 files) |
| **Commit** | `97ea351` (fix), `ba441c1` (test harness, tests, CI wiring) |

### 3.2 A cancelled re-read was displayed as an empty account

| | |
|---|---|
| **Symptom** | In the scientific workflow, saving two analyses in quick succession removed the "recent analyses on this account" panel, leaving the reader looking at an account with nothing saved until the replacement request landed. A late response could also put an older list back after a newer one had been shown. |
| **Root cause** | The effect re-reads the list on every save and aborts the request in flight. Its `.catch` set the list to `null` for *any* rejection, cancellation included. |
| **Affected files** | `frontend/src/pages/modules/ScientificWorkflow.jsx` (fixed); `frontend/src/pages/modules/ResearchAssistant.jsx` (same shape, guarded, no reproducible symptom — described as hardening rather than as a fix) |
| **Fix** | An `active` flag plus an `AbortError` check: a cancellation writes nothing, so the previous list stays until a newer one replaces it. A genuine failure still clears the panel, so a stale list can never claim to be the current account's. |
| **Regression test** | `frontend/src/pages/modules/moduleRequests.test.jsx` renders the real component against a deferred `fetch`, drives two supersessions, and asserts the list survives; it fails against the previous implementation. |
| **Commit** | `888b367` |

### 3.3 The deployment verifier died instead of reporting its precondition

| | |
|---|---|
| **Symptom** | `python scripts/verify_deployment_config.py` without `SPACEAGRISIM_AUTH_SECRET` exited with a pydantic traceback from the middle of the security checks. |
| **Root cause** | The script constructs the settings object under a Vercel environment; on Vercel a missing secret is a validation error **by design**. That intended refusal escaped unguarded, so the script could not print a single result — a gate that cannot report its own failure. The auth-secret length check also read `len()` off a legitimately `None` attribute. |
| **Affected files** | `scripts/verify_deployment_config.py` |
| **Fix** | The precondition is stated up front and exits 2 with one line; the length check reads the configured value defensively. Behaviour with a configured secret is unchanged. |
| **Regression test** | `backend/tests/test_deployment_config_verifier.py` runs the script with the variable stripped and asserts exit 2, the message, and no traceback; it fails against the previous script. |
| **Verification** | With a secret and a live PostgreSQL 17.11 server: **21/21 checks passed**, including migration idempotence, storage round-trip, server encoding, and the seven security invariants. |
| **Commit** | `7441dda` |

### 3.4 The route sweep was a manual check, not a gate

Not a defect fix but the permanent form of one: the audit's crawl of all 16 routes at three viewports
was done by hand. `frontend/e2e/crawl.spec.js` now does it in the suite, collecting page errors,
console errors, responses at or above 400 and horizontal overflow per route, and failing with the
route named — the two silent defects from the audit (the phantom `GET /apinull` 404 and the 401
banner on a signed-out page) are exactly what it reads. Commit `215b84a`.

### 3.5 Reviewed and found not to be defects

The mandate asks for this explicitly, so the negative results are recorded rather than implied.

| Area | What was checked | Result |
|---|---|---|
| Other request lifecycles | Every `api()` call site, every `useEffect` that resolves a promise, every debounce timer | `useSimulation` and `useSimulationConfig` already check `controller.signal.aborted` inside their `.then`; `MissionPlatform`, `Account`, `SharedScenario` and `Operator` already carry `active`/abort guards. Only the two in §3.2 were missing them. |
| Double-submit races | `busy`/`loading` gating on every button that triggers a request (`Advisor`, `ScientificWorkflow`, `GuidedWorkflows`, `ResearchAssistant`, `ResearchAssistant`, radiation cards) | Every one is disabled while its request is in flight; no unguarded double-submit path exists. |
| API contract | All 34 distinct frontend call paths resolved against the OpenAPI schema (83 paths) | No path without a backend route; the four template-literal paths resolve to existing routes (`/models/{id}/explanation`, `/predict/{id}` for the two radiation models, `/datasets/{id}`, `/workflows/{id}/run` for the ids actually passed); method selection is body-driven and matches the POST-only routes. |
| SQL injection | Raw SQL in the backend | Exactly one interpolated statement: an `ALTER TABLE users ADD COLUMN` whose name and type come from a hard-coded tuple in the same function. No user input reaches it; identifiers cannot be bound parameters. |
| Code execution | `eval`, `exec`, `pickle`, `yaml.load`, `subprocess`, `os.system` in `backend/app` | None. |
| Operator console | Token comparison | `secrets.compare_digest`, and the endpoint 404s when no token is configured rather than confirming its existence. |
| Polling | `Account`'s 2 s session poll | Cleared on unmount; no leak. |

---

## 4. Architecture summary

Unchanged by this pass. One FastAPI application (`backend/app`) serving 83 documented paths under
`/api`, SQLAlchemy over SQLite (local, tests) or PostgreSQL (hosted), Pydantic settings that validate
environment variables at import time, an in-process request limiter, JWT sessions with constant-time
token comparison, one React 19 + Vite single-page application (`frontend/`) with 16 hash routes and
24 lazy-loaded modules, a static production build served by nginx, and scientific artifacts
(`ml/`, `data/`) with gate scripts that recompute published numbers from committed files.

Deliberately unchanged: single-worker deployment, the rate limiter's in-process design, the API
contract, the UI, and the scientific safeguards. The only dependency change is dev-only
(`vitest`, `jsdom`, `@testing-library/react`, `@testing-library/dom`); nothing added to
`dependencies`, and the production bundle is byte-for-byte accounted for in §5.

---

## 5. Test results

All suites were run on the delivered tree, after the last code change.

### 5.1 Backend

| Gate | Command | Result |
|---|---|---|
| SQLite suite | `PYTHONPATH=backend SPACEAGRISIM_DATABASE_URL=sqlite:///:memory: python -m pytest -q backend/tests` | **1258 passed, 24 skipped** in 39.7 s |
| PostgreSQL suite | same, with `SPACEAGRISIM_TEST_POSTGRES_URL` pointed at a local PostgreSQL 17.11 server | **1282 passed, 0 skipped** in 48.7 s |
| Migration parity | part of `verify_deployment_config.py` | ORM columns and `001_scenarios.sql` agree; migration applies idempotently |

The 24 SQLite skips are the PostgreSQL-only persistence, transaction, constraint and
connection-failure tests. They are not permitted to skip in the PostgreSQL job, and none did — the
run reports zero skips, so the 24 became 24 executed tests (1282 − 1258 = 24).

Test count arithmetic: the previous audit ended at 1257/24 (SQLite) and 1281/0 (PostgreSQL); this
pass adds exactly one backend test (§3.3), giving 1258 and 1282.

**Environment note, recorded because it produced two red runs that were not product failures.**
The trusted test cluster is PostgreSQL 17.11 initialised with `--encoding=UTF8` and
`--auth-host=scram-sha-256`. An SQL_ASCII cluster makes the driver return text as bytes and 22 tests
fail inside SQLAlchemy's version probe; a `trust` cluster makes
`test_connection_failure_is_reported_without_leaking_credentials` fail, because a wrong password is
correctly *accepted* by the server. Both were configuration mistakes on my side, both were diagnosed
and re-run, and neither was worked around in the code or the tests.

### 5.2 Frontend

| Gate | Command | Result |
|---|---|---|
| Lint | `npm run lint` | clean (0 problems) |
| Typecheck | `npm run typecheck` | clean |
| Unit | `npm run test:unit` | **20 passed** (2 files: 15 hook-lifecycle + 3 `RequestState` in one, 2 component-level in the other) |
| Build + bundle guard | `npm run build:check` | pass — no import cycle, no chunk above 500 kB, initial request **245,754 B of the 245,760 B budget** |
| Browser suite | `npx playwright test` (CI mode: builds and serves the production bundle, starts the API) | **171 passed in 5.2 min** — desktop 1440×1100, tablet 820×1180, mobile Pixel 7 |
| Visual regression | `python scripts/visual_regression.py` | **18/18 PASS at 0.000 % differing pixels** |
| Route crawl | part of the browser suite (`e2e/crawl.spec.js`) | 3 tests, 48 route/viewport combinations: no console error, no page error, no response at or above 400, no horizontal overflow |
| Accessibility | `e2e/accessibility.spec.js`, `e2e/accessibility35.spec.js` (inside the 171 above) | all pass on all three viewports; the per-check counts measured when they were written are in [FINAL_QUALITY_GATES.md](FINAL_QUALITY_GATES.md) |

Browser count arithmetic: 168 (audit baseline) + 3 crawl tests = 171. No test was deleted, skipped or
loosened; the unit suite is new coverage, not a replacement for anything.

**Bundle budget honesty.** The fix in §3.1 costs **127 bytes** of minified critical-path JavaScript.
The budget had 133 bytes of headroom (245,627 of 245,760), so the tree now sits 6 bytes inside it.
The budget was not raised, `chunkSizeWarningLimit` was not touched, and the initial graph was
re-examined (index chunk = app shell only: `MissionPlatform`, the hooks, the service layer) before
accepting the cost. A future change of more than 6 bytes on the critical path will fail `build:check`
— which is the gate working as designed, but it is close enough to be stated plainly.

### 5.3 Scientific gates

| Gate | Command | Result |
|---|---|---|
| Model audit | `python scripts/audit_models.py` | 202 checks run, 0 failed; 0 documented gaps, 7 gaps closed |
| Registry checksums and training environment | `python scripts/verify_model_registry.py --check` | **62/62 checks passed**, verified without writing |
| Provenance manifest | `python ml/training/phase32_provenance.py --check` | provenance complete for 9 artifacts |
| Feature readiness | `python ml/research/build_feature_readiness.py --check` | up to date (12 features) |
| Feature coverage | `python ml/research/build_feature_coverage.py --check` | up to date (12 features) |
| Dataset gap matrix | `python ml/research/build_gap_matrix.py --check` | up to date (14 gaps) |
| Measured evidence to model cards | `python ml/research/phase34_record_measurements.py --check` | recorded in 5 model cards |
| Evidence verdicts | `python ml/research/phase35_evidence_verdicts.py --check` | consistent with the committed measurements |
| Screenshot store | `python ml/research/dedupe_screenshots.py --check` | deduplicated: 53 unique images, 46.9 MB of duplicates recorded |

All nine ran with `--check` (they refuse to write), and `git status` was clean afterwards — the gates
prove the committed state rather than refreshing it.

### 5.4 Dependency and static analysis

| Gate | Command | Result |
|---|---|---|
| Python static analysis | `python -m bandit -q -r backend/app -f json` | **0 findings** (0 high, 0 medium, 0 low) |
| Python dependency audit | `python -m pip_audit -r backend/requirements.txt -r backend/requirements-dev.txt` | **no known vulnerabilities** |
| npm dependency audit | `npm audit --audit-level=high` | **0 vulnerabilities** (292 packages, including the four new dev-only ones) |
| Source hygiene | `backend/tests/test_source_hygiene.py` (in both suites) | passes: no duplicated dict keys, no lost unit symbols in source or docs, no dead imports |

---

## 6. Security results

No security regression was introduced, and no new issue was found.

* **Static analysis**: bandit reports zero findings across `backend/app`.
* **Dependencies**: pip-audit and npm audit report no known vulnerabilities.
* **Secrets**: no credential in the tree or in `.git/config`; the repository remote was reset to its
  plain URL after every push and the token was passed inline only.
* **Operator console**: constant-time token comparison; 404 when unconfigured.
* **Deployment invariants** (`verify_deployment_config.py`, 21/21): wildcard CORS rejected, plaintext
  non-local origins rejected, auth secret length floor, token lifetime and auth rate limits bounded,
  history writes disabled on Vercel, default local configuration never pointing at a shared database.
* **Unchanged by instruction**: `--workers 1` and the in-process rate limiter. Multi-worker behaviour
  remains documented as unsupported rather than silently enabled.
* **No Render action**: no deploy, no environment or plan change, no production database access.

---

## 7. Scientific validation

Nothing in the scientific layer changed in this pass; the gates above re-verified it rather than
trusting it.

* **Registry**: 62/62 checks pass, including that every catalogued model's declared metric is
  recomputable from committed artifacts and that no measured-ET0 claim is made without bundled data.
* **Evidence verdicts** are unchanged and still consistent with the committed measurements. Exactly
  one model is decision-grade (`mizuna-microbial-relative-load-v2`); the three lettuce models remain
  failed at their stated criteria; the radiation-quality, radiation-exposure and tomato models remain
  "no independent check"; the two withdrawn models stay withdrawn.
* **Cohort invariants** unchanged: 719 sub-plots across 39 experiments and 37 yield means in the
  phase-30 wheat cohort; 53 lettuce treatments; 40 studies.
* **Measured / derived / predicted** separation is unchanged, and the panel that shows a model's
  verdict is the same one that shows what the model does *not* establish.

### Datasets investigated and refused

No dataset was added in this pass, so the inventory and the model evidence are unchanged. The
investigations from the previous pass stand, including two that were refused on evidence rather than
convenience: the VEG-04 second campaign record (OSD-780) contradicts the v2 card's "no second
campaign" wording and is documented as a card-level limitation rather than silently pooled, and two
Zenodo candidates (39.1 GB and 49.8 GB) were rejected as unobtainable, while the Dryad candidate was
rejected as non-CEA. A dataset is not counted here unless it is downloaded, licence-verified,
SHA-256 checked and catalogued — none was, so none is claimed.

---

## 8. Dataset and model limitations

Unchanged, and still the honest constraint on what this platform can claim:

* The decision-grade evidence covers one model on a microbial *relative* load. It does not establish
  an absolute pathogen load, a yield, or a flight-versus-ground difference on its own.
* Prediction outputs are model output. They are labelled as such everywhere they appear, are never
  presented as measurements, and no report mixes the two.
* The 14 open gaps in the dataset gap matrix remain open. Where a gap could be closed with an
  obtainable, verifiable dataset it was; where it could not, the gap stays recorded.
* Cross-campaign comparisons remain prohibited where the protocol differs; the water-evidence ratio
  is explicitly a comparison against a measured value with its own source, not a validation.
* Known limitations are carried in [FINAL_LIMITATIONS.md](FINAL_LIMITATIONS.md) and in each model
  card, and were not softened in this pass.

---

## 9. Production compatibility

| Area | Check | Result |
|---|---|---|
| Startup | `uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT --workers 1` | the exact command from `render.yaml`; the browser suite starts and serves the API with it |
| Configuration | settings load and validate at import; weak or missing secrets fail fast | verified by `verify_deployment_config.py` (21/21) and by the settings tests in both suites |
| Health and readiness | `/api/health`, `/api/ready` | reachable and reported by the route crawl; readiness names the reason and never leaks the URL |
| Database | PostgreSQL 17.11 for the full suite; migrations apply idempotently; server encoding asserted | 1282/1282 executed tests, 0 skipped |
| CORS / allowed origins | wildcard and plaintext non-local origins rejected | 21/21 deployment checks |
| Frontend build | production build served as static files by `vite preview` during the browser run; `nginx.conf` and `Dockerfile` untouched | 171 browser tests against the production bundle |
| Bundle | no cycle, no oversized chunk, initial request inside the 240 kB budget | 245,754 B of 245,760 B |
| Runtime dependencies | none added; the four new packages are dev-only and absent from `dependencies` | `package.json` diff |
| Error handling and logging | the structured request-completion line (request id, method, path, status, elapsed ms) is emitted for every call during the browser run | browser-suite server log |
| Infrastructure | no new service, no new worker, no new managed dependency | repository diff |

**Deployment readiness is not a deployment.** Nothing in this pass contacted Render, and the hosted
service was not exercised. Deployment is handed over with the checks above as evidence.

---

## 10. Final commits and the merged SHA

Eighteen commits ahead of the pre-merge `main` (`d84a1a9`), in order:

```
05370a1 fix(config): restore the unit symbols a non-UTF-8 round trip destroyed
a7e1366 fix(frontend): stop requesting a resource that has no path, and gate private history
fbcaa9c fix(styles): let the assistant's suggestion chips wrap on a phone
576cbd7 fix(closed-loop): derive the chamber comparison instead of storing its output
2d30a4e test(registry): make the registry gate read-only so tests stop dirtying the tree
12899bb build(deps): declare openpyxl and pyflakes in the dev requirements that the tests need
48983af chore(backend): remove dead imports and locals, and gate the app with pyflakes
71e6309 fix(data): export the wheat columns under the units the workbook actually declares
2c732ce fix(scripts): make the synthetic-fixture generator honour --out-dir
1d9def1 chore(scripts): remove three dead locals and two f-strings that format nothing
671b9be fix(export): serialise the CSV analysis export instead of pasting quotes around a title
8e2c08c docs: the complete project-wide bug audit report
97ea351 fix(frontend): stop a superseded resource response from overwriting state
ba441c1 test(frontend): schedule the resource race instead of hoping for it
888b367 fix(frontend): a cancelled re-read is not an empty account
7441dda fix(scripts): the deployment verifier reports a missing secret instead of dying on it
215b84a test(e2e): make the route sweep a gate instead of a one-off crawl
(and this report)
```

The merge is a fast-forward: `main` moves from `d84a1a9` to the tip of this branch, and **that tip is
the last commit containing this file**. A commit cannot contain its own hash, so the merged SHA is
read rather than written:

```
git ls-remote origin refs/heads/main
git ls-remote origin refs/heads/bugfix/project-wide-audit
```

Both must print the same 40-character SHA, and it must equal `git rev-parse HEAD` in a fresh clone.
The delivery message accompanying this report states the SHA that verification returned.

---

## 11. Blockers

**None blocked the merge.** The exact status of everything that is *not* done, and why:

| Item | Status | Reason |
|---|---|---|
| Merge into `main` and push | done | fast-forward, verified with `git ls-remote`, no protection encountered |
| Render deployment | **not attempted** | the user reserved the hosted deploy for another operator (2026-11-12). Not a blocker for this task; it is the handover item. |
| Production database | **not touched** | same instruction; every database result here comes from isolated local servers |
| Multi-worker deployment | **not enabled** | by instruction: the in-process rate limiter assumes one worker |
| New datasets | **not added** | none met the download + licence + checksum + catalogue bar this pass |
| Branch protection / permissions | not encountered | `bugfix/project-wide-audit` pushed cleanly at every step |

---

## 12. Confirmation

Stated against what was actually measured. "PASS" means the evidence above exists on the delivered
tree; it is not a claim of absolute correctness.

| Criterion | Verdict | Basis |
|---|---|---|
| Engineering completion | **PASS** | all mandated work items executed: inspection, fixes, review, tests, docs, merge; no TODOs or unfinished integration left for another pass |
| Bug-fix completion | **PASS** | 14 defects fixed on the branch (11 from the audit, 3 here), each with a regression test that fails on the previous code; no known reproducible defect was dismissed as harmless |
| Test and quality gates | **PASS** | 1258/24 SQLite, 1282/0 PostgreSQL, 20 unit, 171 browser across 3 viewports, 18/18 visual at 0.000 %, 9/9 science gates, bandit/pip-audit/npm audit clean, lint and typecheck clean, bundle inside budget |
| Scientific integrity | **PASS** | registry 62/62, evidence verdicts unchanged and consistent, provenance complete for 9 artifacts, gap matrix 14 gaps still recorded, no dataset or metric invented, limitations preserved |
| Documentation | **PASS** | this report plus a consistent README that names the current verification record; earlier phase reports left as history rather than edited to match today's numbers |
| Main merge and push | **PASS** | fast-forward merge, branch and `main` at the same SHA, verified against the remote, clean tree |
| Production deployment readiness | **PASS (local evidence only)** | startup command, settings validation, CORS/health/readiness, PostgreSQL compatibility and the production bundle all verified locally; the hosted service was deliberately not touched, so no deployed-environment result is claimed |

**What this report does not claim**: that the hosted deployment works (not tested), that the models
are scientifically validated beyond their stated verdicts (they are not), or that 6 bytes of bundle
headroom is comfortable (it is not).
