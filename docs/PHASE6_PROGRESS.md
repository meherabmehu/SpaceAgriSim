# Phase 6 — Progress Ledger

Every row records a completed feature. Commit hashes are verified against the
remote branch with `git ls-remote`.

**Branch:** `feat/phase6-nasa-ai-completion`
**Remote head:** `8c80acf6205612e3ea75c3277ff9ef09751e3eb0`

| # | Feature | Status | Tests | Commit | Push verified |
|---|---|---|---|---|---|
| 1 | Baseline audit + Phase 4 integration verification | ✅ Completed | pytest baseline reproduced (100 passed, 1 skipped); OSD-655 mass audit 8/8 + 6/6 | `197b460` | ✅ |
| 2 | Expanded verified NASA dataset inventory (25 studies) | ✅ Completed | `discover_expanded.py` resolves 25/25 | `385fbe6` | ✅ |
| 3 | NASA measurement extraction pipelines (OSD-780/670/120) | ✅ Completed | 5/5 files size-verified + SHA-256; 203+169 rows parsed, 0 unparsed | `8d0c608` | ✅ |
| 4 | Scientific calibration + simulation invariant audit | ✅ Completed | 1,170 sweep checks pass; 55 new invariant tests; mass-balance defect fixed | `e58e6ff` | ✅ |
| 5 | Model re-evaluation (mizuna / tomato / lettuce) | ✅ Completed | Mizuna fails baseline (14.771 vs 14.410); tomato permutation p=0.005; lettuce reproduces | `1e8363c` | ✅ |
| 6 | New NASA model + inference endpoints | ✅ Completed | Backend 155 → 162 tests | `b11bfec` | ✅ |
| 7 | Cross-platform browser test execution | ✅ Completed | Playwright 15/15 desktop+tablet+mobile | `f417db1` | ✅ |
| 8 | Database backup + restore verification | ✅ Completed | 7 new tests; seeded SQLite drill end-to-end | `633bf46` | ✅ |
| 9 | Serverless evidence packaging + production readiness | ✅ Completed | Bundle-only load verified; backend 162 → 169 tests | `f757f9e` | ✅ |

## Final verification snapshot

| Check | Result |
|---|---|
| Backend `pytest` | **169 passed, 1 skipped** |
| Frontend `eslint` / `tsc` / `vite build` | clean / clean / success |
| Playwright | **15 passed** (5 per viewport) |
| Simulation invariants | **1,170 checks, all pass** |
| UI source diff vs `cf1d6c3` | **empty** |
| Datasets integrity | 28 + 5 files SHA-256 verified |
| ML determinism (same env × 2) | identical |

## Blocked / partial items

| Item | Status | Reason |
|---|---|---|
| PostgreSQL integration execution | ⛔ Blocked (infra) | No managed instance or credentials supplied |
| Error tracking / alerting | ⛔ Blocked (infra) | No monitoring provider DSN |
| Production scenario writes | ⛔ Blocked (policy) | Awaiting PostgreSQL verification |
| Biomass / water / gas-exchange / light / gravity / radiation / stress models | ⛔ Blocked (data) | No machine-readable NASA measurements exist |
| Tomato cross-study transfer test | ⚠️ Partial | Only one applicable study exists |
| Lettuce baseline calibration | ⚠️ Partial | Plausibility-checked, not fitted (n=4) |
| Monitoring retention policy | ⚠️ Partial | Must be set at the hosting provider |

## Open engineering actions

1. **Pin `scikit-learn` exactly.** Regenerating artifacts under a different
   version moved mizuna R² from −0.153 to −0.333 and tomato macro-F1 from 0.805 to
   0.916. Conclusions held, point estimates did not. See
   `docs/ML_TRAINING_REPORT.md` §2.
2. **Commit scoping.** Commit `385fbe6` was staged with `git add -A` while later
   artifacts already existed, so it swept in OSD-780 data and the microbial model
   card not described by its message. Content is complete; history was not
   rewritten because force-push is prohibited.
3. **Inventory count alignment.** `nasa_pipeline.py IDS` still lists 13 studies
   while documentation refers to 14 (OSD-895 is acquired out-of-band).

## Legend

* **✅ Completed** — implemented, tested, pushed.
* **⚠️ Partial** — implemented but some acceptance criterion unmet.
* **⛔ Blocked (data)** — evidence not obtainable from public NASA sources.
* **⛔ Blocked (infra)** — needs credentials or paid infrastructure.
* **⛔ Blocked (policy)** — deliberately not enabled pending authorisation.
