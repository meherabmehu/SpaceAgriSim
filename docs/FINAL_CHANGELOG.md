# Final changelog

Everything this pass changed, in commit order. `git log 44d863c..HEAD` prints the SHAs; a commit
cannot contain its own hash, so the delivery SHA is read from the remote
(`git ls-remote origin refs/heads/main`).

Base: `44d863c628ab45faa4d2f95eef47b587f7a1d14b`.

---

## 1. `fix(science): read each model's evidence verdict once per response`

**Files** `backend/app/research.py`, `backend/app/routes/research.py`

`research.verdict_fields(model_id, model)` returns `{"evidenceVerdict": …, "decisionGrade": …}` from a
single `evidence_verdict()` read. Six call sites now spread it into their response dict instead of
computing the verdict twice each.

The v1 lettuce route's response was one very long single-line dict with `"warnings"` under two keys —
Python kept the last and discarded the first silently — and the same dict recomputed the verdict twice.
It is now a multi-line dict whose `warnings` value is the one that used to survive, with a docstring
explaining why the superseded model is still served.

**Behaviour change** none observable: the surviving value is unchanged, and an AST scan confirms no
duplicate string keys remain in any dict literal in the backend.

**Tests** existing verdict tests in `backend/tests/test_research.py`, `test_phase35_model_evidence.py`;
SQLite 1 235 → still green, PostgreSQL green.

## 1b. `fix(workflows): one definition per unit in the registry`

**Files** `backend/app/workflows/units.py`, `backend/tests/test_source_hygiene.py` (new)

`g/plant` and `mm2` were each defined twice in the `UNITS` literal; the second definition won and the
first entry's caution was discarded. Merged to a single entry per unit with both cautions, and added a
source-level scan (plus a planted-duplicate self-test) so a duplicate key in any backend module fails
the suite. Behaviour change: `/api/workflows/units` now carries the caution that was being dropped; no
value, dimension or field name changed.

## 2. `fix(security): only http(s) LLM endpoints reach urlopen`

**Files** `backend/app/llm.py`, `backend/tests/test_phase13_llm.py`

`HttpProvider._validated_endpoint()` rejects any scheme outside `http`/`https`, and is called from
`complete()` (so an injected transport cannot bypass it) as well as `_post()`. Two tests: refusal for
four malformed endpoints with zero transport calls, and acceptance for both allowed schemes.

**Behaviour change** a deployment with a non-http endpoint now fails closed with `LLMUnavailable`
instead of reading a file.

## 3. `fix(test): build the Phase 29 dataset in a temp directory, and compare all five outputs`

**Files** `ml/research/build_light_stress_dataset.py`, `backend/tests/test_phase29_datasets.py`

The builder gained `--out-dir` (default unchanged). The test builds into a temporary directory,
compares four CSVs byte-for-byte and `light_stress_quality` field-by-field with `generatedAt`
removed, then asserts the committed files are untouched. Previously the test ran over the committed
outputs, rewrote `generatedAt` on every run, left the tree dirty, and never compared the quality record
— the file carrying the licence, source digest and exclusions.

**Tests** strictly stronger than before; the old assertion compared four files, the new one compares
five and adds an invariant.

## 4. `chore(ci): run the scientific gates, enforce the bundle budget, scan the application code`

**Files** `.github/workflows/ci.yml`, `scripts/verify_model_registry.py`,
`backend/requirements-dev.txt`

* new `science` job: nine `--check` gates (model audit, registry, provenance, readiness, coverage, gap
  matrix, Phase 34 measurements, Phase 35 verdicts, screenshot dedupe);
* frontend job runs `build:check` instead of `build`, so an import cycle, an oversized chunk or an
  initial request above 240 kB fails the build;
* `bandit -q -r backend/app` added to the backend job, failing on any finding;
* `pip-audit` now covers `requirements-dev.txt` as well;
* `verify_model_registry.py --check` verifies without rewriting the report;
* `httpx2` pinned in `requirements-dev.txt` so the suite no longer prints a library deprecation warning
  on every run. Declared, not filtered.

**Behaviour change** CI now fails where it previously stayed green.

## 5. `fix(frontend): a failed secondary request is reported, not silently dropped`

**Files** `frontend/src/pages/modules/moduleSupport.jsx`, `Benchmarks.jsx`, `ModelComparison.jsx`,
`frontend/e2e/degraded.spec.js` (new)

`RequestState` gained `secondary`: quiet while loading, loud on error. The three secondary resources —
`/external-validation` on benchmarks and models, `/closed-loop` on benchmarks — are now rendered
through it. New Playwright spec aborts `/api/external-validation` and asserts the page still renders,
shows a `role="alert"` banner, and that the interception actually fired; a second test pins the
"External check failed" annotation on `/#models`.

**Verification** the counterfactual was run — removing the new `<RequestState …/>` line makes the spec
fail. Bundle unchanged at 240 kB.

## 6. `docs: the eight final reports, and two sentences that had gone stale`

**Files** `docs/FINAL_*.md` (8 files), `docs/PHASE31_REMOVED_MODELS.md`,
`docs/PHASE29_ENVIRONMENTAL_STRESS_MODEL_REPORT.md`

The eight reports: `FINAL_DELIVERY_REPORT`, `FINAL_AUDIT_FINDINGS`, `FINAL_SECURITY_REVIEW`,
`FINAL_SCIENTIFIC_EVIDENCE`, `FINAL_QUALITY_GATES`, `FINAL_FRONTEND_REPORT`, `FINAL_OPERATIONS`,
`FINAL_LIMITATIONS`, plus this changelog.

Two corrections, both of stale statements rather than of history:

* `PHASE31_REMOVED_MODELS.md` said `mizuna-microbial-relative-load-v2` remains `experimental`; the card
  is `validated-exploratory` since Phase 34 measured the missing term. An `Update (Phase 35)` paragraph
  records the derivation and the file that supplies the number.
* `PHASE29_ENVIRONMENTAL_STRESS_MODEL_REPORT.md` described the reproducibility test as comparing CSV
  hashes; it now describes what the test does after change 3.

---

## What was not touched

* No deployment, Render setting, environment variable, plan or worker count (kept at 1).
* No production database access.
* No dataset acquired, catalogued or re-counted.
* No model trained, promoted or re-scoped.
* No test deleted, skipped or loosened; no threshold moved; no warning suppressed; no
  `chunkSizeWarningLimit` change; the 240 kB initial budget is unchanged.
* No API contract change: no request field, response field or status code was added, removed or renamed.
* `docs/screenshots` baselines unchanged — the visual gate compares against the same 18 committed
  captures and passes at 0.000 %.
