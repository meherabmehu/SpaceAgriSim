# Final delivery report — the whole repository, closed out

This is the last pass over the product. Phase 35 fixed what the audit found in that phase; this pass
re-audited everything the repository contains — backend, frontend, science, CI, tests, deployment
configuration, documentation — and fixed every defect that could be fixed without fabricating
evidence or touching a deployment. What it did not fix is listed, with the reason, in
`docs/FINAL_LIMITATIONS.md`.

Read this file first; each section points at the document that carries the detail.

| | |
|---|---|
| Starting point | `44d863c628ab45faa4d2f95eef47b587f7a1d14b` on `main`, verified with `git ls-remote` before the tree was used |
| Branch | `phase35/final-completion`, cut from that SHA (the branch was already an ancestor of `main`; the new work was added on top of it and fast-forwarded) |
| Final SHA | not written here — a commit cannot contain its own hash. Read it from the remote: `git ls-remote origin refs/heads/main`. The branch was pushed first, `main` was fast-forwarded, and both refs were re-read after the push. |
| Deployment | **none**. No Render resource, setting, environment variable, plan, worker count or production database was read or changed. `--workers 1` is unchanged in `render.yaml` and the `Dockerfile`. |

## 1. What changed, in one screen

**Seven defects fixed**, each found by the audit and each accompanied by a test that fails without
the fix:

1. **A duplicated dict key silently discarded the evidence warning on the v1 lettuce route.**
   `predict_lettuce` built one dict literal containing `warnings` twice; Python keeps the last, so the
   first (which carried the verdict warning) was thrown away. The route also computed
   `evidence_verdict()` twice per response. Both are gone: `research.verdict_fields()` returns the
   pair from one read, and the response is written as one readable dict. `docs/FINAL_AUDIT_FINDINGS.md` §1.
2. **A failed request removed a panel instead of reporting it.** `Benchmarks` and `ModelComparison`
   rendered their secondary resources as `{data && <Panel/>}`, so an API error deleted the panel with
   no message — including the panel that exists to show that an *external* check failed. New
   `e2e/degraded.spec.js` cuts `/api/external-validation` out of the network and asserts the page
   says so. `docs/FINAL_AUDIT_FINDINGS.md` §2.
3. **The reproducibility test rewrote a tracked file on every run.** The Phase 29 builder test ran the
   builder over the committed outputs, which rewrote `generatedAt` and left the tree dirty; it also
   never compared the quality record — the file carrying the licence, source digest and exclusions.
   The builder now takes `--out-dir`, and the test compares all five outputs and then asserts the
   committed files are byte-identical. `docs/FINAL_AUDIT_FINDINGS.md` §3.
4. **The LLM endpoint was passed to `urlopen` unvalidated.** A mistyped endpoint (`/etc/passwd`,
   `file://…`, `ftp://…`) would have been opened. Now only `http`/`https` are accepted, enforced in
   `complete()` so it holds for injected transports too, with a test that asserts refusal and that the
   network was never touched. `docs/FINAL_SECURITY_REVIEW.md` §2.
5. **The CI never ran the scientific gates and did not enforce the bundle budget.** A green CI said
   nothing about the model cards matching their evidence, and a `build` that merely compiled passed
   the frontend job. New `science` job runs nine `--check` gates; the frontend job runs
   `build:check`; `bandit` now runs on the application code with a zero-finding gate.
   `docs/FINAL_OPERATIONS.md` §1.
6. **Two units were defined twice, so the registry served one wording and discarded the other's
   caution.** `UNITS` in `backend/app/workflows/units.py` had `g/plant` and `mm2` twice each; Python keeps
   the last. Merged to one entry per unit with both cautions, plus a new source-level test that scans
   every backend module for duplicate dict keys (the same defect class as §1 — after finding it twice,
   the repository now has a test that reads for it). `docs/FINAL_AUDIT_FINDINGS.md` §7.
7. **A stale status sentence contradicted the model card.** `docs/PHASE31_REMOVED_MODELS.md` still said
   `mizuna-microbial-relative-load-v2` was `experimental`; Phase 34 measured the one missing term and
   the card is now `validated-exploratory`. Corrected with the derivation and the file that supplies it.
   `docs/FINAL_SCIENTIFIC_EVIDENCE.md` §2.

**Nothing was weakened.** No test deleted, skipped or loosened; no threshold moved; no warning
suppressed; the 240 kB initial budget is untouched (`docs/FINAL_QUALITY_GATES.md` §4); no acceptance
criterion reworded; no limitation relabelled as fixed.

## 2. Gates

Every gate was run on the delivered tree after the last code change. Full command list, exact
outputs and how to reproduce each one: `docs/FINAL_QUALITY_GATES.md`.

| Gate | Result |
|---|---|
| SQLite suite | 1 242 passed, 23 skipped (every skip is a PostgreSQL-only test, reason printed) |
| PostgreSQL 17.11 suite | 1 265 passed, 0 skipped, 0 failed |
| lint / typecheck | clean / clean |
| production build + `build:check` | passed — initial request 245 535 B of a 245 760 B budget (240 kB, unchanged) |
| model audit | 202 checks, 0 failed, 9/9 models, 7 gaps resolved |
| registry verification | 62/62 (`--check`, tree left clean) |
| provenance | 9/9 artifacts |
| readiness / coverage / gap matrix | 12 / 12 / 14, all `--check` up to date |
| Phase 34 measurement sync, Phase 35 verdicts | no drift / consistent |
| screenshot dedupe | 53 unique images, 46.9 MB of duplicates recorded, `--check` clean |
| bandit (application code) | 0 unsuppressed findings (5 reviewed, marked where raised) |
| pip-audit (runtime + dev) / npm audit | 0 known vulnerabilities / 0 vulnerabilities |
| visual regression | 18/18 PASS at 0.000 % differing pixels |
| Playwright | **156 passed in 4.5 min** across desktop 1440×1100, tablet 820×1180, mobile Pixel 7 (150 before this pass + 6 new: two tests × three viewports) |
| accessibility | contrast, reduced motion, keyboard-only: 12/12 at three viewports |

The suite grew from 1 235 to 1 242 SQLite tests and from 1 259 to 1 265 PostgreSQL tests: two new LLM
endpoint tests, four new source-hygiene tests, one Phase 29 assertion replaced by a strictly stronger
one, and one backup-recovery test that now executes because `pg_restore` is on `PATH` (it skips, with
the reason printed, when it is not). The Playwright suite grew by six: two degraded-network tests at
three viewports.

## 3. Science

Unchanged verdicts, and the change is a derivation rather than a decision:

| verdict | models |
|---|---|
| decision grade (passes an independent check) | `mizuna-microbial-relative-load-v2` |
| fails an independent check | `lettuce-earth-growth-v1`, `-v2`, `-v3` |
| no independent check | `radiation-quality-osd46-v1`, `radiation-exposure-osd46-v1`, `tomato-flight-response-v1` |
| withdrawn, retained and still listed as withdrawn | `mizuna-harvest-v1`, `mizuna-microbial-load-v1` |

No model was trained and no dataset was acquired in this pass; every candidate from earlier searching
was already rejected with a reason and none was reopened. Measured values, model predictions, derived
quantities and user setpoints remain separately labelled on every surface that shows a number.
Details: `docs/FINAL_SCIENTIFIC_EVIDENCE.md`.

## 4. Accessibility and frontend

The accessibility properties claimed in Phase 35 are measured at three viewports and pass; this pass
adds no accessibility change because none was needed, and says so rather than claiming an improvement
it did not make. The two UI-state fixes (§1.2) are the only frontend behaviour changes; the design
language, navigation, and the Phase 33 dependency-free SVG chamber are untouched.
`docs/FINAL_FRONTEND_REPORT.md`.

## 5. Removals and blocks

Nothing was removed in this pass. Previously withdrawn capabilities stay absent everywhere — no
route, catalogue row, workflow, nav entry or assistant action — and the audit's removed-capability
checks still pass. Four kinds of work remain blocked, each for a stated missing input rather than a
missing afternoon: measured reference ET, substrate-moisture series, a LED spectral response surface,
and fractional-gravity growth data. `docs/FINAL_LIMITATIONS.md`.

## 6. What a reader can check without trusting this document

```bash
git ls-remote origin refs/heads/main           # the delivered SHA
python -m pytest backend/tests -q              # SQLite suite
python scripts/audit_models.py                 # 202 checks
python scripts/verify_model_registry.py --check
python scripts/visual_regression.py            # needs the Playwright run first
npx playwright test                            # 156 tests, 3 viewports
```

Every number in this file was printed by one of those commands or by a script named beside it.
