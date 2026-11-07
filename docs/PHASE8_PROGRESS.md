# Phase 8 — Progress Ledger

Chronological record of what was actually done, including the things that were
wrong on the first attempt. Kept because the corrections are more instructive than
the successes.

---

## 0. Baseline

- Re-established the git remote after the sandbox reset (`git remote add origin`),
  fetched, and **verified** rather than assumed: local `main` = `origin/main` =
  `ls-remote` = `fe6bbe2`.
- Confirmed Phase 7 is fully merged: `feat/phase7-nasa-scientific-completion` is an
  ancestor of `main`, and all six remote branches are ancestors of `main`. No
  unmerged work existed to integrate.
- Created `feat/phase8-complete-platform-improvement` from `fe6bbe2`.
- Reinstalled dev dependencies; baseline suite **187 passed, 1 skipped**.
- Provisioned a disposable PostgreSQL 17.11 cluster (UTF-8, port 55432) and
  re-ran: **188 passed, 0 skipped**.
- Captured latency baselines for nine endpoints before touching any code.

## 1. Engine robustness — no change made

Swept 6480 scenarios across three crops and every environment combination,
asserting finiteness, non-negativity, `water_recovered ≤ water_used`, and factor
ranges.

**First run: 9380 violations.** Investigated before fixing anything. All 9380 were
the probe's fault: it asserted the CO₂ factor must be ≤ 1.0, when CO₂ enrichment is
supposed to raise growth above the reference. The correct bound is ≤ 1.5 for `co2`
and `combined`, ≤ 1.0 for the others. Re-run: **0 violations**. Engine untouched.

Recorded because the temptation was to "fix" a simulation that was correct.

## 2. Performance — one real defect

Confirmed by direct observation on the baseline commit that
`research.load_model` was `lru_cache(maxsize=4)` against five registered models:
`CacheInfo(hits=0, misses=5, currsize=4)`, and `hits=0, misses=10` after two passes.
The cache never retained a working set.

Fixed by deriving the size from `len(MODEL_IDS)`, so it self-adjusts when a model is
added. Isolated A/B: **17.97 ms → 4.55 ms** on `GET /api/models`.

An earlier full-sequence benchmark appeared to show `/api/compare` improving 8×; it
was a harness ordering artefact and is **not** claimed. See `PHASE8_PERFORMANCE.md`.

## 3. Scientific classification

Added `backend/app/science_classification.py` — the six-category taxonomy, the
service permitted at each category, and a feature record per surface — served at
`GET /api/science/classification`.

Result: five category-3, one category-4, five category-5, **one category-6**, none
in categories 1 or 2. The single unsupported prediction was the absolute mizuna
microbial load endpoint.

## 4. Retiring the unsupported prediction

`POST /api/predict/mizuna-microbial-load-v1` now returns **410 Gone** with its own
leave-one-campaign-out R² values and a pointer to the v2 replacement, and is marked
deprecated in OpenAPI. Request validation is retained (422 still works). The
artifact stays registered and checksum-verified so the Phase 6 result remains
reproducible.

## 5. Machine-learning improvement

The Phase 7 benchmark had already measured gradient boosting ahead of the registered
random forest on the lettuce task (R² 0.880 vs 0.797) — so the platform was serving
the weaker of two model classes it had itself compared.

Trained `lettuce-earth-growth-v2` with classic gradient boosting: **R² 0.8699 vs
0.8131, MAE 34.9 g vs 39.1 g, better in 4 / 4 held-out experiments.** v1 was not
overwritten; it remains registered and served.

Shipped classic boosting rather than the marginally better HistGradientBoosting
because the latter's binned structured-array predictors would require
re-implementing sklearn's binning inside the dependency-free evaluator for 0.01 R².
The serialised ensemble reproduces sklearn to a **maximum absolute difference of
0.0**, checked at training time and re-checked by a test.

## 6. Security review

Attacked the authentication boundary with twelve probes: `alg: none`, wrong-key
signature, expired token, missing `jti`, repointed `sub`, missing/garbage/wrong
scheme headers, post-logout reuse, SQL injection in login. **All behaved correctly.**
Confirmed Argon2id at 3/65536/4, rate limiting at 30/min on auth paths (observed
429s), explicit CORS with wildcard rejection at load time, and no credential leakage.

Two findings raised and deliberately **not** patched, because the safe fix is
unverifiable without deployment access:

- **F1** — per-address rate limiting collapses to one shared bucket behind a
  reverse proxy. Not fixed by trusting `X-Forwarded-For`, which would be a worse
  vulnerability.
- **F2** — no HSTS/CSP at the edge. A CSP added without testing against the real
  three.js bundle is how dashboards break.

## 7. UI preservation

Zero frontend source changes (`git diff --stat fe6bbe2 -- frontend/` is empty),
Playwright **15/15** at three breakpoints, lint and build clean. The residual
screenshot drift was attributed by A/B rather than assertion: removing the one
change that could plausibly affect UI content produced byte-identical drift, so the
difference is environmental.

Regenerated screenshots and Phase 7 verification JSON were deliberately not
committed.

## 8. Errors made and corrected during the phase

| Error | Correction |
|---|---|
| Asserted CO₂ factor must be ≤ 1.0, producing 9380 false violations | Bound corrected to ≤ 1.5; engine was never at fault |
| Passed `postgresql://` to the PG test instead of `postgresql+psycopg://` | One test failed on its own guard; re-ran with the required driver prefix |
| Optimised `simulate`/`compare` claims from a full-sequence benchmark | Re-measured in isolated processes; no real change; claims withdrawn |
| Wrote a serialisation loop that indexed Python lists with arrays | Converted to numpy arrays; ensemble then matched sklearn exactly |
| Suspected a 12-byte JWT key in the app | It was the key in my own forged-token probe; app secret is 64 chars with `min_length=32` |
| Bundled artifacts were stale after training | Discovered `backend/scientific_data` shadows `ml/artifacts`; ran `package_runtime_data.py` |

## 9. Merge and push

- `git fetch origin`; remote `main` was `fe6bbe2`, unchanged since the branch point,
  so no rebase was needed and no force-push was ever considered.
- Pushed the feature branch **first** (`48c70e7..eea1dda`) and read back
  `refs/heads/feat/phase8-complete-platform-improvement` = `eea1dda`.
- Merged `--no-ff` into `main`. Result: `039cd6a`, a two-parent merge commit.
- **Re-ran every gate on `main` after the merge**: backend 212 passed / 0 skipped
  against live PostgreSQL, registry 32/32, deployment config 21/21, frontend lint
  and build clean, Playwright 15/15.
- Pushed `main` (`fe6bbe2..039cd6a`) and verified with `git ls-remote` that the
  remote HEAD equals the local HEAD: `039cd6aa…`.
- Verified `origin/feat/phase8-complete-platform-improvement` is an ancestor of
  `origin/main`, so no completed work was left unmerged.

## 10. Verification at the close of Phase 8

- Backend: **212 passed, 0 failed, 0 skipped** against live PostgreSQL.
- Model registry: **32 / 32**. Deployment config: **21 / 21**.
- Frontend: lint clean, build succeeds, Playwright **15 / 15**.
- Engine invariants: 6480 scenarios, 0 violations.
