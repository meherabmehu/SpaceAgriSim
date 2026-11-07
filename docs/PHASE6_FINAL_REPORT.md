# SpaceAgriSim — Phase 6 Final Report

**Executed:** 2026-11-07
**Branch:** `feat/phase6-nasa-ai-completion`
**Head commit:** `8c80acf` (verified present on `origin`)
**Baseline:** `main` @ `cf1d6c3`

> **Not merged to `main`. Nothing promoted to production.** Promotion requires
> owner authorisation after reviewing the blockers in §12.

---

## 1. Verified starting repository state

| Item | Value |
|---|---|
| Repository | `github.com/meherabmehu/SpaceAgriSim` |
| `main` at audit time | `cf1d6c37b430901f7fb052a9efe692e2adaa42ed` |
| Tracked files | 249 |
| Working tree | 7.3 MB |
| Git auth | Token supplied by the owner; `repo` scope; authenticated as `meherabmehu`; **every push below verified with `git ls-remote`** |

## 2. Phase 4 integration status — **the brief was out of date**

The brief states *"Phase 4 has yet been merged into main."* **This is false.**

```
$ git merge-base --is-ancestor origin/feat/phase4-production-security main
YES - merged
```

`main` @ `cf1d6c3` is the merge commit of `4ceba2a` (Phase 3) and `7193c56`
(Phase 4 tip). **No Phase 4 merge step was needed or performed.** Phase 6 was
based directly on `main := cf1d6c3`.

Phase 4's headline claim was independently reproduced: **100 passed, 1 skipped**.

Also corrected: the brief says the inventory holds "14 NASA OSDR records".
`scripts/nasa_pipeline.py` declares only **13** in its versioned `IDS`; OSD-895 is
acquired out-of-band. Effectively 14, but the code did not match the document.

## 3. NASA datasets discovered

25 studies re-queried against official OSDR APIs; **25/25 resolved**.

* **14 baseline** (OSD-7, 120, 267, 268, 269, 375, 436, 625, 655, 745, 766, 767, 773, 895)
* **11 new** (OSD-218, **307**, **565**, 670, 385, 386, 412, 723, **780**, 855, 883)

The three studies named in the brief — **OSD-218, OSD-307, OSD-565** — all exist
and were verified. Full detail: `docs/NASA_DATASET_EXPANSION.md`.

## 4. NASA datasets actually downloaded

5 new files, every one byte-size verified against the OSDR registry and SHA-256 recorded:

| Study | File | Bytes | Role |
|---|---|---|---|
| OSD-780 | Aerobic plate count | 11,708 | **Measured CFU/g** |
| OSD-780 | Yeast/mould plate count | 9,106 | Measured CFU/g |
| OSD-780 | Data dictionary | 1,012 | Unit definitions |
| OSD-670 | Regolith chemistry | 292 | Substrate chemistry (no plant phenotype) |
| OSD-120 | Image↔sample index | 107,991 | No numeric phenotype |

## 5. Numerical training targets actually obtained

| Target | Rows | Usable as a label? |
|---|---|---|
| OSD-780 aerobic CFU/g fresh weight (leaf) | 123 | **Yes** — measured |
| OSD-780 yeast/mould CFU/g | 169 total | Yes, but no leaf subset large enough to model |
| OSD-655 VEG-04A fresh mass/pillow | 14 | Marginal — **target defined differently per arm** |
| OSD-655 irrigation supplied | 512 events | No — a management input, not demand |
| OSD-767 gene counts | 36 samples | Only for molecular-context classification |
| EDEN ISS per-crop kg/m² | 19 rows | Plausibility check only — a PDF transcription |

## 6. Models trained or improved

### `mizuna-microbial-load-v1` — **new, the only supportable new model**

NASA OSD-780, 123 leaf samples, 35 biological units.

| | MAE | R² |
|---|---|---|
| Ridge (grouped nested CV) | **1.087** | **0.549** |
| Random forest challenger | 1.136 | 0.512 |
| Group-mean baseline | 1.718 | −0.007 |

**Honest limitation:** leave-one-experiment-out R² is **−0.555** (VEG-04A) and
**−0.580** (VEG-04B). Conformal 90 % intervals cover only **0.811**. Status:
`experimental`, intervals labelled uncalibrated.

### `tomato-flight-response-v1` — strengthened

* **Batch confounding ruled out for lane:** all 36 libraries are one lane (`_L008`).
  Recorded caveat: a lane effect is therefore not *estimable* by construction.
* **Permutation test:** observed macro-F1 0.916 vs null max 0.750 over 200
  plant-level permutations → **empirical p = 0.005**.
* **Not a tissue shortcut:** leaf-only 0.856, root-only 0.796.
* Gene-set stability only 29.7/64 shared across folds → no biomarker claim.

### `mizuna-harvest-v1` — re-evaluated, retained `baseline-only`

Model MAE 14.771 vs baseline **14.410** (R² −0.163 vs −0.138). Does not beat a
mean baseline. Retained as-is.

### `lettuce-earth-growth-v1` — verified reproducible

R² 0.81198 vs recorded 0.81196; MAE 38.939 vs 38.947. Validated by nested
**leave-one-experiment-out** — the strongest validation evidence in the repo.

## 7. Models rejected for insufficient evidence

All eight other candidate tasks in the brief (§11 A–H) were **rejected, not faked**:

| Task | Blocking fact |
|---|---|
| Crop biomass / harvest yield regression | No biomass table beyond OSD-655's 14 endpoints in 25 studies |
| Water demand / transpiration | No transpiration or uptake measurement exists anywhere |
| Photosynthesis / gas exchange | No CO₂-assimilation or O₂-evolution table exists |
| Light response | Light recorded as red/blue category, never measured PPFD × photoperiod |
| Gravity response | Flight/ground is a classification label, not a continuous response |
| Radiation response | No plant-specific dose–response data; ISS dosimetry is not plant-paired |
| Plant stress classification | No genuine labelled stress outcomes |

## 8. Real evaluation metrics

See §6 and `docs/ML_EVALUATION.md`. **No model reaches `validated`.**
`/api/scientific-summary` reports `validatedModels: []`.

## 9. Simulation calibration results

**Calibrated / plausibility-checked:**

| Crop | Baseline | EDEN ISS measured | Verdict |
|---|---|---|---|
| **Lettuce** | 2.00 kg/m² | 1.56–2.77 kg/m² (n=4) | ✅ **inside measured range** (−9.2 %) |
| Tomato | 3.50 | 3.65–4.17 (age-normalised, n=2) | ⚠️ flagged, suggestion recorded, **not applied** |
| Radish | 1.20 | 1.33–1.82 (n=2) | ⚠️ flagged, suggestion recorded, **not applied** |

**Real defect found and fixed.** `cumulative_biomass_g` and `harvested_g` used
different accounting cut-offs, so the documented identity
`cumulative == harvested + standing` was **false on every harvest day**, off by
exactly one cycle's harvest (verified: 2,000 g residual on a 35-day lettuce run).
Fixed additively in `growth.py` — no previously emitted value changed, all
155 existing tests still pass, and the identity now holds with zero residual
across 1,170 sweep checks.

## 10. New backend functionality

| Endpoint | Purpose |
|---|---|
| `POST /api/predict/mizuna-microbial-load-v1` | OSD-780 microbial load, returns evidence status, uncalibrated interval and transfer failure |
| `GET /api/science/calibration` | Per-crop calibration evidence level + 1,170-check invariant result |
| `GET /api/science/evidence` | Measured / assumed / blocked targets in separate fields |
| `GET /api/scientific-summary` | Machine-readable maturity: `nasaEndorsed:false`, `missionCertified:false`, `validatedModels:[]` |

## 11. UI regression verification

**No UI change whatsoever.**

```
$ git diff --stat cf1d6c3..HEAD -- frontend/src frontend/public frontend/index.html
(empty)
```

* The new model surfaces through the **existing generic model card** in
  Predictions — no component, style, layout or asset changed.
* `eslint` clean, `tsc --noEmit` clean, `vite build` success.
* Playwright **15/15** pass on desktop (1440×1100), tablet (820×1180), mobile (Pixel 7).
* Desktop mission-control capture visually confirmed intact.

## 12. Test results (actual, this run)

| Suite | Result |
|---|---|
| Backend `pytest` | **169 passed, 1 skipped** (was 100/1) |
| → of which scientific invariants | 55 new |
| → of which backup/restore | 7 new |
| → of which Phase 6 research API | 7 new |
| PostgreSQL integration | 1 skipped — no DSN supplied |
| Frontend lint / typecheck / build | clean / clean / success |
| Playwright desktop / tablet / mobile | 5 / 5 / 5 = **15 passed** |
| Simulation sweep invariants | **1,170 checks, all pass** |
| Dataset integrity | 28 + 5 files, SHA-256 verified |
| ML determinism (same env, 2 runs) | identical metrics and coefficients |

## 13. Git commit history — all pushed and verified

| # | Commit | Subject |
|---|---|---|
| 1 | `197b460` | docs: audit phase six baseline and phase four integration |
| 2 | `385fbe6` | data: expand verified NASA scientific dataset inventory |
| 3 | `8d0c608` | data: implement NASA measurement extraction pipelines |
| 4 | `e58e6ff` | science: calibrate hybrid simulation against measurements |
| 5 | `1e8363c` | ml: reevaluate NASA mizuna harvest evidence and strengthen tomato validation |
| 6 | `b11bfec` | feat: integrate new scientific inference endpoints |
| 7 | `f417db1` | test: restore cross-platform browser test execution |
| 8 | `633bf46` | ops: add database backup and restore verification workflows |
| 9 | `f757f9e` | ops: package Phase 6 evidence for serverless deployment |
| 10 | `8c80acf` | docs: finalize NASA scientific validation report |

**Push verification:** `git ls-remote --heads origin feat/phase6-nasa-ai-completion`
→ `8c80acf6205612e3ea75c3277ff9ef09751e3eb0`, matching local `HEAD`.

No force-push. No history rewrite. 68 files changed, +13,708 / −1,585.

> **Process note (disclosed rather than hidden):** commit 2 was staged with
> `git add -A` while later-work artifacts already existed in the tree, so it
> swept in the OSD-780 data and the microbial model artifact that the commit
> message does not describe. All content is delivered and no work was lost, but
> commits 2–3 are not perfectly scoped. Rewriting pushed history was avoided per
> the no-force-push rule.

## 14. Remaining scientific gaps

These are **evidence gaps in public NASA data**, not implementation gaps:

* No machine-readable biomass/harvest table beyond OSD-655's 14 endpoints.
* No dry-mass measurements for these crops.
* No repeated per-day growth observations.
* No transpiration, water-uptake or water-recovery measurements.
* No CO₂-assimilation or O₂-evolution measurements.
* No measured PPFD/photoperiod per sample (only red/blue categories).
* No plant-paired radiation dose–response data.
* No continuous gravity-response data; flight/ground is categorical.
* No labelled plant stress/disease severity outcomes.
* OSD-895 exists only as a PDF; its numbers are a literature transcription.

## 15. Exact operator actions required

| # | Action | Why |
|---|---|---|
| 1 | Review and authorise merge of `feat/phase6-nasa-ai-completion` → `main` | Not merged by design |
| 2 | Provision managed PostgreSQL; set `SPACEAGRISIM_DATABASE_URL`; run `SPACEAGRISIM_TEST_POSTGRES_URL=<dsn> pytest backend/tests/test_postgres_integration.py` | Only unexercised storage path |
| 3 | Set `SPACEAGRISIM_AUTH_SECRET` to a durable high-entropy value | Ephemeral fallback invalidates tokens on restart |
| 4 | Set `SPACEAGRISIM_CORS_ORIGINS` to the exact production origin(s) | Wildcards rejected by design |
| 5 | Keep `history_writes_enabled=false` until action 2 passes | Durability not yet proven on PostgreSQL |
| 6 | Choose an error-tracking/monitoring provider and configure alerting | No DSN supplied; not faked |
| 7 | Pin `scikit-learn` exactly before regenerating artifacts | Retraining in a different version moved mizuna R² −0.153 → −0.333 |
| 8 | Decide on the tomato (3.91) and radish (1.58 kg/m²) baseline suggestions | Would change user-visible numbers; n=2 |

## 16. Status classification

**Completed**
Baseline audit and Phase 4 verification · 25-study NASA discovery · 5-file acquisition
with provenance · OSD-780 grammar recovery and preprocessing · new microbial model ·
mizuna/tomato/lettuce re-evaluation with permutation and batch testing · simulation
calibration · mass-balance defect fix · 4 new API endpoints · registry builder ·
backup/restore workflows · cross-platform e2e fix · serverless evidence packaging ·
all documentation · 9 verified pushes.

**Partially completed**
Tomato molecular validation — strengthened, but only one study exists so
cross-study transfer remains untestable. Lettuce baseline calibration —
plausibility-checked, not fitted. Monitoring — code-side complete, provider
integration absent.

**Blocked by unavailable data**
Biomass, harvest-yield, water-demand, gas-exchange, light-response,
gravity-response, radiation-response and stress-classification models.
All documented in `docs/NASA_MEASUREMENT_INVENTORY.md` §4.

**Blocked by credentials / infrastructure**
PostgreSQL integration execution · managed monitoring and alerting · durable auth
secret · production deployment.

**Scientifically unsupported (and therefore not done)**
Any claim of mission-ready yield prediction · lunar/Martian validation ·
biomass labels from expression data · gravity response from flight/ground labels ·
radiation response from unpaired dosimetry · calibrated confidence intervals
anywhere in this repository.
