# Final audit — what the whole-repository review found, and what was done about it

The audit covered every tracked file category: backend modules and routes, frontend components and
styles, the research scripts, the test suites, the CI workflow, the deployment configuration, and the
documentation. Each finding below is stated with the file, the consequence, the fix, and the test that
now fails if the defect returns. Findings that were reviewed and deliberately left alone are in §7,
with the reason.

Nothing in this document is an estimate. Each "before" was observed by running the code.

---

## 1. A duplicated dict key discarded a warning on the v1 lettuce route

**Where** `backend/app/routes/research.py`, `predict_lettuce` (v1).

**What** The response was one very long dict literal that contained `"warnings"` twice:

```python
'warnings': warnings+model['limitations'],
...
'warnings': warnings+model['limitations']+research.verdict_warning(model['id'],model)
```

Python keeps the **last** key and discards the first without an error, so the response was correct by
accident — the surviving value happened to be the more complete one. Any future edit that reordered
those two entries would have silently dropped the verdict warning from a response for a model that
failed its independent check.

The same route called `research.evidence_verdict(...)` twice inside the literal (once for
`evidenceVerdict`, once for `decisionGrade`), and the same duplicated pair appeared at five other
call sites.

**Why it matters here** The verdict warning is the sentence that tells a caller the lettuce models
failed their external check. A dict literal is not a place where that can be left to key order.

**Fix**
* `backend/app/research.py` — new `verdict_fields(model_id, model)` that reads the verdict once and
  returns `{"evidenceVerdict": …, "decisionGrade": …}`;
* all six call sites now spread `**research.verdict_fields(model["id"], model)`;
* the v1 route's return value is written as a normal multi-line dict with a docstring saying why it
  is still served.

**Verification**
* an AST scan over the whole backend for duplicate string keys in dict literals: none remain;
* `backend/tests/test_research.py` and the Phase 35 verdict tests assert the response carries
  `evidenceVerdict`, `decisionGrade` and the warning for every non-decision-grade model;
* SQLite and PostgreSQL suites both green afterwards.

**Not claimed** This was a latent defect, not an observed wrong answer: the surviving value was the
correct one. The report says so rather than presenting a fixed bug that never produced a bad response.

---

## 2. A failed request deleted a panel instead of reporting the failure

**Where** `frontend/src/pages/modules/Benchmarks.jsx`, `ModelComparison.jsx`,
`moduleSupport.jsx`.

**What** Secondary resources were rendered as `{data && <Panel/>}`:

```jsx
{closedLoop.data?.available && <ClosedLoop body={closedLoop.data} />}
{external.data && <ExternalValidation body={external.data} />}
```

`useResource` returns `{data: null, error: "…", loading: false}` on failure, so a failed request
removed the panel and left **nothing** — no banner, no skeleton, no hint that the page was missing a
section. The main `/benchmarks` request was guarded by `<RequestState>`, the two secondary ones were
not.

**Why it matters here** One of those panels exists to show that the lettuce model *failed* an
independent external check. On `/#models` the same endpoint supplies the "External check failed"
annotation inside the model table. A network error therefore removed the failed-check evidence from
the two pages whose purpose is to carry it — the exact failure mode the product's own rule forbids
("a failed check must stay visible wherever a user meets the model").

**Fix**
* `RequestState` gains `secondary`: a secondary resource stays silent while it loads (so a page does
  not show two skeletons), and still reports an error;
* the three secondary resources (`/external-validation` on benchmarks and models, `/closed-loop` on
  benchmarks) are now rendered through it.

**Verification** `frontend/e2e/degraded.spec.js`, new, three assertions:
* with `/api/external-validation` aborted, `/#benchmarks` still renders the main benchmark card and
  shows a `role="alert"` banner;
* the interception is asserted to have fired (`aborted > 0`), so a typo in the route pattern cannot
  make the test pass vacuously;
* with the endpoint healthy, `/#models` shows "External check failed"; with it cut, the models route
  reports the error rather than reading as if no check had been run.

The counterfactual was run: with the `<RequestState state={external} secondary />` line removed, the
first test fails on `expect(banner).toBeVisible()`. The test is load-bearing, not decorative.

---

## 3. The reproducibility test dirtied the working tree and never checked the important file

**Where** `backend/tests/test_phase29_datasets.py`, `ml/research/build_light_stress_dataset.py`.

**What** The test ran the Phase 29 builder over the committed output directory and compared the four
CSVs before and after. Two consequences:

1. the builder rewrites `light_stress_quality` with a fresh `generatedAt` on every run, so
   running the suite left a modified tracked file behind — noise that has to be reverted by hand
   before any commit, and noise in which a real change can hide;
2. the file that was **never compared** is the one that carries the licence, the source SHA-256, the
   exclusion record and the transformation log: `light_stress_quality`.

**Fix**
* the builder accepts `--out-dir DIR` (default unchanged, so the documented invocation and the Phase 29
  layout are the same);
* the test builds into a temporary directory, compares the four CSVs byte-for-byte and the quality
  record field-by-field with `generatedAt` removed, then asserts the committed files are
  byte-identical afterwards.

**Verification** the strengthened test passes, `git status` is clean after a full suite run, and the
Phase 29 report's row describing the gate now says what the gate actually does.

---

## 4. Unvalidated URL handed to `urlopen` in the LLM client

See `docs/FINAL_SECURITY_REVIEW.md` §2 for the full write-up: only `http`/`https` endpoints are now
accepted, enforced at `complete()` so injected transports cannot bypass it, with two tests.

---

## 5. CI did not run the scientific gates and did not enforce the bundle budget

**Where** `.github/workflows/ci.yml`.

**What** The frontend job ran `npm run build` and `npm audit`; `build:check` — the script that fails
on an import cycle, an oversized chunk, or an initial request above 240 kB — was only ever run by a
person. And none of the nine evidence gates (`audit_models`, `verify_model_registry`,
`phase32_provenance`, `build_feature_readiness`, `build_feature_coverage`, `build_gap_matrix`,
`phase34_record_measurements`, `phase35_evidence_verdicts`, `dedupe_screenshots`) ran in CI at all.

**Why it matters here** These scripts are the only thing that makes a model card's numbers and the
committed evaluation files the same numbers. A repository whose central scientific claim is "the
document and the artifact agree" cannot leave the agreement check to memory.

**Fix**
* new `science` job, nine `--check` steps, stdlib-only, on Python 3.12;
* `verify_model_registry.py` gained `--check` so the job does not rewrite
  `docs/phase7/registry_verification` (the timestamp-only diff had twice been mistaken for a real
  change);
* frontend job runs `build:check` instead of `build`;
* `pip-audit` now audits `requirements-dev.txt` as well as `requirements.txt`;
* `bandit -q -r backend/app` added to the backend job, failing on any finding.

**Verification** the workflow parses (all five jobs present), and every step was executed locally in
the same order with the same results (`docs/FINAL_QUALITY_GATES.md`).

---

## 6. A stale status sentence contradicted a model card

**Where** `docs/PHASE31_REMOVED_MODELS.md`.

**What** The file asserted `mizuna-microbial-relative-load-v2` stays "with `evidenceStatus:
experimental`". The card has been `validated-exploratory` since Phase 34 measured the one term of its
own recorded promotion rule that had not been measured — conformal coverage, 0.8943 against a nominal
0.90, inside the rule's own ±5-point tolerance.

**Why it matters here** Two documents in the same repository stating different statuses for the same
model is how a reader ends up quoting a limitation that was since measured, or the reverse.

**Fix** an `Update (Phase 35)` paragraph in place — not a rewrite of the history — naming the rule, the
file that supplied the measurement, and the fact that the promotion is derived rather than decided.
The paragraph is explicit that "validated" still never means a calibrated probability and that the
number remains bound to a campaign that supplies its own baseline samples.

---

## 7. Two units defined twice, so the registry served one wording and dropped the other's caution

**Where** `backend/app/workflows/units.py`, the `UNITS` literal.

**What** `"g/plant"` and `"mm2"` each appeared **twice** in the same dict literal. Python keeps the last
definition, so:

* `g/plant` was described as *"grams of fresh shoot mass per plant"* (first definition) and served as
  *"grams of fresh or dry mass per individual plant"* (second). The surviving wording is the right one —
  the unit is used by both `freshWeightG` and `dryWeightG` — but the first entry's caution ("fresh mass,
  not dry mass and not edible yield per square metre") was discarded;
* `mm2` lost the caution that leaf area per plant is not leaf area per square metre of bench.

**Why it matters here** The unit registry is what a client reads to label an axis or decide whether a
conversion is legitimate. A caution that exists in the source but not in the served payload is worse
than no caution: the code looks careful and the API is not.

**Fix** one entry per unit, with the accurate description and **both** cautions merged into the single
entry, plus a comment in place of the duplicates saying why the block looks shorter.

**Verification** `backend/tests/test_source_hygiene.py`, new:
* a source-level scan of every module under `backend/app` for duplicate string keys in dict literals;
* a planted-duplicate test proving the scan can see one at all (so a scanner that silently matches
  nothing cannot pass);
* an assertion that `g/plant` and `mm2` each keep **at least two** cautions, i.e. the merged state is
  pinned rather than merely "the scan is clean";
* a test that the specific file stays fixed.

Counterfactual run: re-adding a duplicate `g/plant` line makes three of the four tests fail.

This is why §1's duplicate-key defect was not treated as a one-off: the same pattern was present in two
files, and after this pass the repository has a test that reads for it instead of a person who
remembers it.

---

## 8. Reviewed and deliberately not changed

| Item | Why it stays |
|---|---|
| `docs/PHASE29_*`, `PHASE30_*` … prose describing the state at the time of that phase | These are phase records. Editing them to match today's state would destroy the audit trail that makes the later phases checkable. Where a later phase changed the fact, the later document says so. |
| The five bandit findings that are not defects | Each is marked on the line that raised it, with the reason; all five are listed in `docs/FINAL_SECURITY_REVIEW.md` §3. Marking them was chosen over a severity floor, which would have hidden the next real finding in the same rule. |
| `frontend/probe.mjs`, `probe2.mjs` | Untracked-free but committed debugging helpers used by the screen-capture work. They are not on any import path; removing them would break the documented capture procedure. |
| The 24 skipped SQLite tests | They are PostgreSQL-only by design, each prints its reason, and the PostgreSQL job fails on any skip — so the skip cannot mask a regression. |
| Two-campaign scope of `mizuna-microbial-relative-load-v2` | A real limitation, not a defect. It is on the card, in the API response and in the UI. |
| `lettuce-earth-growth-v1`/`v2` remaining served | Deliberate and disclosed: their failed external check is reproducible only while they answer. Removing them would delete the evidence. |

---

## 9. What was checked and found sound

Stated so that the absence of a finding is information too:

* **SQLAlchemy usage** — no string-built SQL in the application layer; every statement is bound
  (read across `storage.py`, `routes/*`), and the same statements pass on PostgreSQL 17.11.
* **Auth paths** — Argon2 hashing, JWT with `jti` revocation checked per request, ownership scoping on
  every scenario and analysis read/write/delete, per-address rate limiting with separate buckets.
  Exercised by the suites; no change made.
* **Share links** — cap, expiry and wholesale revoke all enforced; no change made.
* **Database portability** — the full suite passes on both engines, including the backup/restore drill
  (`pg_restore` present: 0 skips).
* **Removed capabilities** — no route, catalogue row, workflow, nav entry or assistant action for the
  withdrawn models or the retired workflows; the audit's removed-capability checks pass unchanged.
* **Frontend dependency tree** — `npm audit`: 0 vulnerabilities; no dependency was added in this pass.
* **Bundle** — no import cycle, no chunk above the 500 kB budget, initial request unchanged at 240 kB.
* **Python runtime dependencies** — `pip-audit` on runtime and dev pins: no known vulnerabilities.
