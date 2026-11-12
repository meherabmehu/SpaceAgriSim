# Phase 11 — platform QA

Objective 7 was to improve the platform and merge verified work to `main`. This document
records what was actually run, with the numbers, and the two environment faults found along
the way that were **not** code defects.

**No deployment.** Nothing was pushed to Render or any other host, and no UI redesign was
attempted. Every frontend file is byte-identical to the Phase 10 merge.

---

## 1. Gates

| Gate | Command | Result |
| --- | --- | --- |
| Backend suite | `cd backend && SPACEAGRISIM_TEST_POSTGRES_URL=… pytest -q` | **291 passed** |
| Model registry | `python3 scripts/verify_model_registry.py` | **40/40 checks passed** |
| Frontend lint | `cd frontend && npm run lint` | clean |
| Frontend types | `npm run typecheck` | clean |
| Frontend build | `npm run build` | built in 11.77 s |
| End-to-end | `npx playwright test` (desktop / tablet / mobile) | **27 passed** (1.5 min) |
| UI preservation | `python3 scripts/compare_ui_screenshots.py` | `ui-extended-layout-preserved` |
| Demo (fast) | `./scripts/demo_phase9.sh --fast` | passes, ~5 s |
| Demo (full retrain) | `./scripts/demo_phase9.sh` | passes after the ordering fix in §3 |

The 291 figure is the full suite **with** the PostgreSQL URL set. Without it one database
test is skipped and the count reads 290 passed, 1 skipped — the same suite, not a
regression.

---

## 2. UI preservation, stated as a fact rather than a promise

```
git diff --stat 02eac8a -- frontend/
(no output)
```

Zero frontend files differ from the Phase 10 merge. Theme, layout, typography, navigation,
the 3D scene and responsive behaviour are unchanged because **not one byte of frontend
source changed**.

The screenshot comparison agrees but is the weaker evidence, and it is worth being precise
about why:

| Screenshot | Classification | Changed pixels | Max layout drift |
| --- | --- | --- | --- |
| mission-desktop | glyph rasterisation | 0.0096 % | 0 px |
| mission-tablet | glyph rasterisation | 0.0084 % | 0 px |
| mission-mobile | glyph rasterisation | 0.0047 % | 0 px |

Every difference is sub-pixel font rasterisation in the capture environment, with **zero**
layout drift. That is what a byte-identical source tree should look like across machines.
The script's own verdict is `ui-extended-layout-preserved`.

---

## 3. Two environment faults, neither a code defect

### 3a. Playwright browsers were missing their system libraries

First run: **27 failed**, every one with

```
chrome-headless-shell: error while loading shared libraries: libnspr4.so:
cannot open shared object file
```

The browsers had been downloaded but the container had no NSS/NSPR runtime. This is
infrastructure, not the suite. After `npx playwright install-deps chromium` and
`npx playwright install chromium`, the same command gives **27 passed**. Recorded because
"27 failed" and "27 passed" describe the same commit, and only the second one means anything.

### 3b. The full demo failed its own checksum gate — a real ordering bug

The full demo run reproduced every metric and then refused its artifacts:

```
== 4/7 Verify registry checksums and run the scientific test suite
ValueError: Model checksum verification failed: radiation-quality-osd46-v1
```

Cause: retraining rewrites the artifacts and, in doing so, **drops the Phase 10 explanation
metadata** (`explanationMethod`, `explanationArtifact`, `explanationAvailable`,
`explanationIsSurrogate`) because `train_radiation_osd46.py` never wrote those fields — they
were attached afterwards by `phase10_explain_radiation.py`. The registry was then never
rebuilt, so its checksums described files that no longer existed.

Fix, in `scripts/demo_phase9.sh`: **train → explain → build_registry → verify**. With that
order the diff between committed and regenerated artifacts is only:

| Artifact | Fields that differ after a full retrain |
| --- | --- |
| `ml/evaluation/phase9_osd46_radiation` | 2 — the two artifact SHA-256s |
| `ml/evaluation/phase10_explanations` | 1 — `generatedAt` |
| both radiation artifacts | `trainedAt` |

**Every measured number is bit-identical.** This is the difference between a demo that works
on the machine where it was developed and one that works from a clean checkout.

Because a full retrain rewrites tracked artifacts and rebuilds the registry, the committed
tree is left at the verified Phase 10 state after the run; the demo does not commit anything.

---

## 4. Registry and scientific scope

The registry is unchanged at **8 models** with 2 exclusions (`radiation-dose-osd782-v1`,
`gravity-reorientation-osd411-v1`) and **19 datasets**. Phase 11 promoted nothing:

| Model | Phase 11 action | Why |
| --- | --- | --- |
| `radiation-quality-osd46-v1` | kept, `calibrated: false` | nested re-selection 0.037 below shipped |
| `radiation-exposure-osd46-v1` | kept, `calibrated: false` | nested re-selection exactly level |
| `radiation-dose-osd782-v1` | stays excluded | dose not recoverable at 36 libraries |
| `mizuna-harvest-v1` | unchanged, failure documented | zero harvest candidates exist in the corpus |
| `mizuna-microbial-*` | unchanged | third campaign does not exist; prediction interval spans zero |
| `lettuce-earth-growth-*` | unchanged | no new data; coverage unchanged |
| `gravity-*` | unchanged | OSD-346 gravity is confounded with flight run |

`calibrated: false` remains on every model where it was set, and empirical coverage stays
distinct from nominal coverage in every served response.

---

## 5. Data provenance and repository hygiene

| Check | Result |
| --- | --- |
| Pinned NASA source files verified by SHA-256 | 13 files, all matched |
| Analysis matrices > 2 MB kept out of the runtime package | 23.8 MB OSD-320 matrix in `data/derived/` |
| New raw inputs gitignored | `data/raw/OSD-346`, `OSD-314`, `OSD-46` unchanged |
| Metadata cache committed | `data/metadata/osdr_study_metadata_phase11/` (231 payloads) |
| Credentials in history | none; PAT redacted in any logged remote URL |

---

## 6. Status

| Item | Classification |
| --- | --- |
| Backend, registry, lint, types, build, e2e gates | **Completed** — all pass |
| UI preservation | **Completed** — zero frontend diff vs Phase 10 merge |
| Full-demo reproducibility | **Completed** — ordering bug found and fixed |
| Playwright system-library failure | **Blocked by infrastructure**, resolved in-sandbox, no code change |
| Deployment | **Not attempted** — excluded by instruction |
| Claims guard | **Completed** — the suite includes tests that fail if a model claims unsupported scope |
