# Final quality gates

Every gate run on the delivered tree, in the order they were run, with the command, the exact result
and the interpretation. All of them were executed **after the last code change**; none of the numbers
below is carried over from an earlier tree.

Environment: Python 3.13 venv with `backend/requirements-dev.txt`, Node 22 with `npm ci`, Chromium via
Playwright, PostgreSQL 17.11 built from the Debian packages and initialised with
`initdb -E UTF8 --locale=C.UTF-8` (a `SQL_ASCII` cluster returns `bytes` from psycopg and fails the
suite for a reason that has nothing to do with the code).

---

## 1. Backend suites

| Gate | Command | Result |
|---|---|---|
| SQLite | `python -m pytest backend/tests -q` | **1 242 passed, 23 skipped** in 41.0 s |
| PostgreSQL 17.11 | `SPACEAGRISIM_TEST_POSTGRES_URL=postgresql+psycopg://postgres:pgpass@127.0.0.1:55432/spaceagri_test python -m pytest backend/tests -q -rs` | **1 265 passed, 0 skipped, 0 failed** in 44.2 s |

The 23 SQLite skips are all PostgreSQL-gated and each prints its reason (`SPACEAGRISIM_TEST_POSTGRES_URL
is not set; PostgreSQL-only assertion`), plus one that needs `pg_restore` on `PATH`. They are the same
tests the PostgreSQL run executes; 1 242 + 23 = 1 265. The CI `postgres` job fails the build if any
test skips, so a skip cannot hide a regression.

## 2. Scientific and evidence gates

All nine are `--check` (verify, do not rewrite) and all nine now also run in CI's `science` job.

| Gate | Command | Result |
|---|---|---|
| Model audit | `python scripts/audit_models.py` | **202 checks, 0 failed**, 9/9 models, 0 open gaps, 7 resolved |
| Registry verification | `python scripts/verify_model_registry.py --check` | **62/62**; "verified without writing" |
| Provenance | `python ml/training/phase32_provenance.py --check` | 9/9 artifacts complete |
| Feature readiness | `python ml/research/build_feature_readiness.py --check` | 12 features, up to date |
| Feature coverage | `python ml/research/build_feature_coverage.py --check` | 12 features, up to date |
| Dataset gap matrix | `python ml/research/build_gap_matrix.py --check` | 14 gaps, up to date |
| Phase 34 measurement sync | `python ml/research/phase34_record_measurements.py --check` | 5 cards, no drift |
| Phase 35 verdicts | `python ml/research/phase35_evidence_verdicts.py --check` | consistent with the committed measurements |
| Screenshot dedupe | `python ml/research/dedupe_screenshots.py --check` | 53 unique images, 46.9 MB of duplicates recorded |

`docs/phase7/registry_verification.json` is byte-identical to the committed file after the run — which
is the point of `--check`, and the reason the gate can run in CI at all.

## 3. Static analysis and dependency audits

| Gate | Command | Result |
|---|---|---|
| Code analysis | `bandit -q -r backend/app` | **0 unsuppressed findings** (6 raw: 1 fixed in code, 5 reviewed and marked at the line) |
| Python dependencies | `pip-audit -r backend/requirements.txt -r backend/requirements-dev.txt` | no known vulnerabilities |
| JS dependencies | `npm audit --audit-level=high` | **0 vulnerabilities** across 312 dependencies (45 prod, 267 dev) |

Details of the six bandit findings: `docs/FINAL_SECURITY_REVIEW.md` §2–§3.

## 4. Frontend build and bundle

| Gate | Command | Result |
|---|---|---|
| Lint | `npm run lint` | clean (0 errors, 0 warnings) |
| Types | `npm run typecheck` | clean |
| Build + budget | `npm run build:check` | **passed** — no cycle, no chunk above 500 kB, initial request **245 535 B / 245 760 B budget** |

Initial request: `vendor-react` 192 906 B + `index` 34 324 B + `vendor-icons` 18 305 B = **245 535 B**
(240 kB), across 3 modules; gzip 78 957 B. `vendor-charts` stays lazy (393 kB by the gate's decimal count, 402.65 kB as Vite prints it).

The budget was not raised, `chunkSizeWarningLimit` was not touched, and `build:check` was not relaxed.
The 225 bytes of headroom are reported rather than padded — see `docs/FINAL_LIMITATIONS.md` §2.4.

## 5. Browser gates

| Gate | Command | Result |
|---|---|---|
| Playwright, 3 viewports | `npx playwright test` (CI=1) | **156 passed in 4.5 min** — desktop 1440×1100, tablet 820×1180, mobile Pixel 7 |
| Accessibility | subset of the above: `e2e/accessibility.spec.js`, `e2e/accessibility35.spec.js` | contrast 12/12 (worst 4.97:1), reduced motion 12/12, keyboard-only 12/12, chart/chamber semantics 12/12 |
| Visual regression | `python scripts/visual_regression.py` | **18/18 PASS at 0.000 % differing pixels** |

The visual gate compares fresh captures against the committed baselines in `docs/screenshots`; the
fresh images come from the Playwright run and are never written over the baselines. No baseline was
refreshed in this pass, so the 0.000 % result means the delivered tree renders pixel-identically to the
tree that was delivered before it — the two UI-state fixes in `RequestState` are invisible in the
default state by construction (they only change what happens when a request fails).

Playwright count: 150 before this pass, 6 added (`e2e/degraded.spec.js`: two tests × three viewports).

## 6. Repository hygiene

| Check | Result |
|---|---|
| Working tree after the full gate set | clean apart from the intended changes (no `generatedAt`-only diffs, no rebuilt screenshots) |
| `docs/screenshots` size | 25 MB, 53 unique images, `--check` clean |
| Deployment configuration | `render.yaml`, `Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf` byte-identical to the starting tree |
| Node dependencies | no package added, removed or upgraded (`git diff frontend/package.json` empty) |
| Python runtime dependencies | unchanged (`requirements.txt` untouched); one test-only pin added (`httpx2`) |

## 7. Tests that changed, and why

Stated explicitly rather than buried in a diff:

1. **`test_phase29_datasets.py::test_build_is_reproducible_and_writes_nothing_new`** — replaced with a
   strictly stronger test: it builds into a temporary directory, compares five outputs instead of
   four (now including the quality record that carries the licence and the source digest), and adds an
   assertion that the committed outputs are untouched. The old version compared four files and
   rewrote a tracked one.
2. **Two tests added** in `test_phase13_llm.py` (`test_http_provider_refuses_a_non_http_endpoint`,
   `test_http_provider_accepts_https_and_http`).
3. **Four tests added** in `test_source_hygiene.py`: a duplicate-key scan over every backend module, a
   planted-duplicate self-test, a pinned assertion that the two merged units keep both cautions, and a
   regression pin on the file that was fixed.
4. **One new spec** `frontend/e2e/degraded.spec.js` (2 tests × 3 viewports).

Nothing was deleted. Nothing was skipped. No assertion was loosened, and no threshold — accuracy,
coverage, pixel budget, bundle budget, audit severity — was moved.
