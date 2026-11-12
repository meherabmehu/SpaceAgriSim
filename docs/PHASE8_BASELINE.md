# Phase 8 — Baseline

Recorded before any Phase 8 code change, so every later claim can be diffed
against it rather than against memory.

## Repository state

| Item | Value |
|---|---|
| Repository | `https://github.com/meherabmehu/SpaceAgriSim.git` |
| Baseline commit (`main`) | `fe6bbe2886ab6efc6006703654af298c8c8a449a` |
| Phase 7 branch | `feat/phase7-nasa-scientific-completion` @ `1f2a540` |
| Phase 8 branch | `feat/phase8-complete-platform-improvement` (created from `fe6bbe2`) |
| Working tree at baseline | clean |

### Phase 7 integration status

Phase 7 **is fully merged**. Verified rather than assumed:

```
git merge-base --is-ancestor origin/feat/phase7-nasa-scientific-completion main
→ contained
```

All six remote branches are ancestors of `main` — no unmerged work exists:

```
MERGED feat/phase2-scientific-validation
MERGED feat/phase3-production-ml
MERGED feat/phase4-production-security
MERGED feat/phase6-nasa-ai-completion
MERGED feat/phase7-nasa-scientific-completion
MERGED feat/scientific-mission-platform
```

Phase 8 therefore starts from `fe6bbe2` without needing to re-integrate history.

## Baseline test results

Executed against a disposable PostgreSQL 17.11 cluster (`UTF8`, port 55432), not
against documentation.

| Gate | Baseline result |
|---|---|
| Backend pytest (with live PostgreSQL) | **188 passed, 0 failed, 0 skipped** |
| PostgreSQL integration | 1 passed |
| Deployment configuration checks | 21 / 21 |
| Model registry checks | 26 / 26 |
| Frontend lint / typecheck / build | pass |
| Playwright e2e (desktop, tablet, mobile) | 15 / 15 |

## Baseline API latency

`docs/phase8/performance_baseline`, measured with `TestClient` on this
machine. Absolute values are machine-specific; the **relative** change is what
Phase 8 reports.

| Endpoint | Median | p95 |
|---|---|---|
| `GET /api/config` | 3.22 ms | 4.15 ms |
| `GET /api/crops` | 2.94 ms | 3.13 ms |
| **`GET /api/models`** | **19.73 ms** | **28.65 ms** |
| `GET /api/datasets` | 8.88 ms | 10.21 ms |
| `GET /api/science/measurements` | 4.92 ms | 6.08 ms |
| `POST /api/simulate` | 5.22 ms | 5.59 ms |
| `POST /api/compare` | 24.50 ms | 26.26 ms |
| `POST /api/advisor` | 8.37 ms | 9.20 ms |
| `POST /api/optimize` | 140.05 ms | 140.20 ms |

## Confirmed defect found during the audit

**Model artifact cache thrashes.** `research.load_model` is decorated
`@lru_cache(maxsize=4)`, but Phase 7 raised the registry from four models to
five. Observed directly:

```
CacheInfo(hits=0, misses=5, maxsize=4, currsize=4)
registered models: 5
```

Every `GET /api/models` request therefore re-reads and re-hashes roughly 1 MB of
JSON artifacts (the v2 forest artifact alone is 425 KB) with **zero** cache
hits, and one model is evicted on every pass. This is a Phase 7 regression, and
it is the single largest contributor to the 19.73 ms baseline above. Fixed in
`fix: improve API reliability`.

## Engine robustness probe (no change made)

Before changing any simulation code, the engine was swept across **6480
scenarios** (3 crops × 5 gravity levels × 4 radiation levels × 3 water levels ×
3 photoperiods × 3 CO₂ levels × 4 mission lengths), checking every output for
non-finite values, negative values, water recovered exceeding water supplied, and
every environment factor leaving its valid range.

**Result: 0 violations.**

Two apparent violations were initially reported and both were **errors in the
probe, not the engine**:

- The CO₂ factor legitimately exceeds 1.0 — CO₂ enrichment is meant to boost
  growth above the 420 ppm reference.
- The `combined` factor therefore also exceeds 1.0 in enriched scenarios.

Recorded here because it is the correct disposition: an audit that "finds" bugs
by asserting a wrong invariant produces false positives, and the fix belongs in
the test, not the product.

## What Phase 8 is *not* allowed to do

- Redesign the UI in any way.
- Recalibrate a crop using another crop's measurements.
- Fabricate NASA data or ML performance.
- Weaken security to make a test pass.
- Claim production readiness that has not been verified.
- Promote a model past its promotion rule.
