# Phase 8 — Final Report

Complete platform improvement: feature audit, scientific integrity, ML improvement,
security review, performance, and production-readiness assessment.

Baseline `fe6bbe2` → branch `feat/phase8-complete-platform-improvement`.

---

## Status in one line

The platform had one genuinely unsupported prediction in it and one model that was
knowingly behind a better alternative it had already measured. Both are fixed. No
interface pixel was touched, and the science it now serves is the science it can
defend.

---

## The 20-point checklist

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Baseline captured before any change | **Completed** | `PHASE8_BASELINE.md` |
| 2 | Phase 7 verified fully merged, no orphan branches | **Completed** | all six remote branches ancestors of `main` |
| 3 | Full feature inventory | **Completed** | `PHASE8_FEATURE_AUDIT.md` |
| 4 | Six-category scientific classification | **Completed** | `GET /api/science/classification`, 12 features |
| 5 | Unsupported predictions removed or disabled | **Completed** | absolute microbial load → 410 Gone |
| 6 | Evidence preserved when withdrawing a feature | **Completed** | artifact still registered and checksum-verified |
| 7 | Existing models improved where measured data supports it | **Completed** | lettuce v2, R² 0.8131 → 0.8699 |
| 8 | Improvement verified per held-out group, not pooled | **Completed** | wins on MAE in 4/4 experiments |
| 9 | Artifacts versioned, not overwritten | **Completed** | v1 byte-identical, still served and registered |
| 10 | Serialised model reproduces its training framework | **Completed** | max abs difference 0.0 |
| 11 | Performance defects found and fixed | **Completed** | `/api/models` 17.97 → 4.55 ms, 3.9× |
| 12 | Cache regression prevented by test | **Completed** | `maxsize` derived from registry size |
| 13 | Simulation invariants verified | **Completed** | 6480 scenarios, 0 violations |
| 14 | Authentication boundary attacked | **Completed** | 12 probes, all correct |
| 15 | Authorization/rate-limit/CORS verified | **Completed** | 429s observed, wildcard rejected at load |
| 16 | UI byte-identical, verified functionally and by A/B | **Completed** | `PHASE8_UI_PRESERVATION.md` |
| 17 | Backend suite green against real PostgreSQL | **Completed** | **212 passed, 0 failed, 0 skipped** |
| 18 | Frontend lint, build, e2e | **Completed** | lint clean, build ok, Playwright 15/15 |
| 19 | Gravity / radiation / PPFD / O₂ / per-crop yields calibrated | **Blocked by unavailable scientific evidence** | see below |
| 20 | Production database, TLS, multi-instance, load verified | **Blocked by infrastructure or credentials** | see below |

Nothing is labelled *partially completed* or *scientifically unsupported* at the
platform level: the one scientifically unsupported feature that existed has been
withdrawn rather than left in a half-measure.

---

## What changed

### 1. Scientific classification (`a843ad7`)

`app/science_classification.py` + `GET /api/science/classification`. Twelve
prediction and optimisation surfaces classified 1–6, each with its evidence basis,
the service permitted at that category, and its notes. Published rather than filed,
so the claim is checkable against the running system.

| Category | Count |
|---|---|
| 1 measured & directly supported | 0 |
| 2 calibrated with compatible measurements | 0 |
| 3 experimentally supported (non-NASA) | 5 |
| 4 mechanistic with assumptions | 1 |
| 5 hypothetical exploration | 5 |
| 6 unsupported — must not be served | 1 |

### 2. The unsupported prediction, withdrawn (`a843ad7`)

`POST /api/predict/mizuna-microbial-load-v1` predicted absolute leaf microbial load
with leave-one-campaign-out R² of **−0.55** and **−0.58**. Both held-out campaigns
were beaten by predicting the training mean. It now returns **410 Gone** carrying
those numbers and a pointer to the replacement, is deprecated in OpenAPI, still
validates input, and keeps its artifact registered so the Phase 6 result stays
reproducible.

### 3. The model that was behind its own benchmark (`266c200`)

Phase 7 had already measured gradient boosting beating the registered random forest
on the lettuce task, and registered the forest anyway. `lettuce-earth-growth-v2`
ships the boosting model:

| | R² | MAE | Wins on MAE |
|---|---|---|---|
| v1 random forest | 0.8131 | 39.14 g | — |
| **v2 gradient boosting** | **0.8699** | **34.92 g** | **4 / 4 held-out experiments** |

v1 is byte-identical and still served. Classic boosting was chosen over the
0.01-higher HistGradientBoosting because it serialises losslessly into the existing
dependency-free evaluator; the shipped ensemble reproduces sklearn to 0.0.

### 4. A cache that did nothing (`a843ad7`)

`lru_cache(maxsize=4)` against five models: `hits=0, misses=10` after two full
passes. Every request re-read and re-hashed about 1 MB of artifacts and evicted what
it had just loaded. Size now derives from the registry. **17.97 ms → 4.55 ms.**

### 5. Documentation

`PHASE8_BASELINE`, `PHASE8_PROGRESS`, `PHASE8_FEATURE_AUDIT`,
`PHASE8_SCIENTIFIC_INTEGRITY`, `PHASE8_ML_IMPROVEMENTS`, `PHASE8_SECURITY_REVIEW`,
`PHASE8_PERFORMANCE`, `PHASE8_PRODUCTION_READINESS`, `PHASE8_UI_PRESERVATION`, and
this report.

---

## Blocked items, with attempted methods and exact blockers

### Blocked by unavailable scientific evidence (item 19)

Each of these would need new measurements, not new code. Attempts were made in
Phase 7 against NTRS, OSDR and supplementary tables; the corpus is exhausted.

| Target | Attempted | Why still blocked |
|---|---|---|
| Gravity-dependent growth | Searched OSDR partial-gravity studies and NTRS BPC literature | No partial-gravity plant dataset recovered at all. The 15 %-loss-at-0 g value is a labelled placeholder. |
| Radiation dose–response | Searched for absorbed-dose/outcome pairs | Every "radiation" hit is a lamp spectrum, not absorbed dose. No RadLab pairing exists. |
| PPFD / photoperiod response surface | Extracted 2–3 operating points | Confounded with system phase and a copper deficiency. Rated `insufficient` in Phase 7. |
| O₂ evolution | Searched gas-exchange tables | Never measured in the corpus. Current output is stoichiometric and named "estimated". |
| Tomato / radish fresh-weight baselines | Searched for per-crop harvest series | No measured harvest series for either crop. |
| Water recovery | Checked against measured loop data | 0.924 measured from a *leaking* chamber gives a lower bound only; 0.90 stays a conservative assumption. |

**Next action:** none available within this repository. These require laboratory
data or an OSDR study that does not yet exist.

### Blocked by infrastructure or credentials (item 20)

| Item | Attempted | Blocker | Next action |
|---|---|---|---|
| Production PostgreSQL | Verified against disposable local PG 17.11 | No production credentials | Supply `SPACEAGRISIM_DATABASE_URL` |
| TLS / HSTS | Inspected `nginx.conf` | Terminator outside repo | Configure at ingress |
| Multi-instance tokens | Reasoned from settings and storage | Needs durable shared secret + shared revocation store | Durable `SPACEAGRISIM_AUTH_SECRET` |
| Load behaviour | Measured single-request latency only | No deployed target to load-test | Load test after deploy |
| Edge rate limiting | Found F1 (proxy collapses buckets) | Fix depends on ingress topology | Edge limiting or trusted-proxy config |

---

## Two things I deliberately did not do

**Did not "harden" the simulation.** A 6480-scenario sweep found zero violations,
and the only two apparent failures were wrong assertions in my own probe. Changing
correct code to look responsive to an audit would have been the worst available
outcome.

**Did not patch the two security findings.** Both fixes depend on production
topology. Trusting `X-Forwarded-For` to fix the rate limiter would introduce header
spoofing; adding an untested CSP to a three.js app would break the interface I am
required not to touch. Reporting the exact blocker is worth more than a plausible
patch that cannot be verified.

---

## Verification summary

| Gate | Result |
|---|---|
| Backend tests (live PostgreSQL 17.11, UTF-8) | **212 passed, 0 failed, 0 skipped** |
| Phase 8 integrity/performance tests | 18 |
| Model registry verifier | **32 / 32** |
| Deployment configuration | **21 / 21** |
| Frontend lint / build | clean / succeeds |
| Playwright desktop, tablet, mobile | **15 / 15** |
| Engine invariants | 6480 scenarios, 0 violations |
| Frontend source diff vs baseline | **0 files** |
| Auth attack probes | 12 / 12 behaved correctly |

Baseline was 188 passed / 0 skipped; Phase 8 adds 24 tests and breaks none.

## Merged

`feat/phase8-complete-platform-improvement` merged into `main` with `--no-ff` after
the gates above, and the remote HEAD verified to contain the merge commit. Merge
commit and verification output are recorded in `PHASE8_PROGRESS.md` history and the
git log; no claim of a push is made without a re-read of the remote.
