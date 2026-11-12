# Phase 7 — Baseline Verification

**Verified:** 2026-11-07
**Branch:** `feat/phase7-nasa-scientific-completion`
**Base commit:** `b4890e9` (`docs: correct stale remote head reference in phase six ledger`)

---

## 1. Starting repository state

| Item | Verified value |
|---|---|
| Repository | `github.com/meherabmehu/SpaceAgriSim` |
| Phase 6 branch | `feat/phase6-nasa-ai-completion` |
| Phase 6 head | `b4890e9` — the brief's reported `8c80acf` plus one documentation-only commit |
| `main` | `cf1d6c3` (Phase 4 merge) — **Phase 6 is not merged into `main`**, as the brief states |
| Backend tests | **169 passed, 1 skipped** |
| Working tree | clean |

The brief's reported Phase 6 HEAD was `8c80acf`. `b4890e9` is one commit beyond it
and only corrects a stale git-hash reference inside
`docs/PHASE6_PROGRESS.md`. **No functional difference.**

## 2. Phase 6 reported results — reproduced

| Claim | Reproduced? | Evidence |
|---|---|---|
| 169 backend tests passed | ✅ | `169 passed, 1 skipped` |
| 1 skipped | ✅ | `test_postgres_integration.py`, gated on a DSN |
| 25 OSDR studies resolved | ✅ | `data/metadata/phase6_discovery` present, 25 studies |
| 5 NASA files downloaded | ✅ | `data/metadata/phase6_checksums`, all size-verified |
| 1 new microbial model | ✅ | `ml/artifacts/mizuna-microbial-load-v1`, 123 samples / 35 groups |
| Mass-balance defect fixed | ✅ | `growth.py` exposes `mass_balance_residual_g` |
| 4 scientific API endpoints | ✅ | `/predict/mizuna-microbial-load-v1`, `/science/calibration`, `/science/evidence`, `/scientific-summary` |
| No UI changes | ✅ | `git diff cf1d6c3 -- frontend/src` is empty |

## 3. Environment

| Component | Version |
|---|---|
| Python | 3.13.16 |
| numpy / pandas / scikit-learn | 2.3.5 / 2.2.3 / 1.6.1 |
| PostgreSQL (Phase 7, new) | **17.11** — installed and running in this sandbox |
| Docker | **not available** in this sandbox |

## 4. Phase 6's stated scientific blocker, restated

Phase 6 concluded that ten measurement types **do not exist** in public NASA
data, based on a sweep of 25 OSDR studies:

> biomass time series · fresh/dry harvest yield · water uptake · transpiration ·
> water recovery · CO₂ assimilation · oxygen evolution · photosynthesis · PPFD
> and photoperiod response · gravity-dependent growth · radiation dose-response ·
> measured stress outcomes

Phase 6 stated these absences were "evidence gaps in public NASA data, not
implementation gaps."

**Phase 7 tests that conclusion directly.** The OSDR repository is a *genomics
data* archive; it was never the right place to look for 1980s–1990s CELSS
physiology. Those results were published as **NASA Technical Memoranda and
conference papers**, indexed in the NASA Technical Reports Server (NTRS).

### 4.1 NTRS search executed in Phase 7

`scripts/ntrs_search.py` — 39 target-driven queries against the official NTRS
public search API, recorded with hit counts so negative results are not repeated.

| Result | Count |
|---|---|
| Queries executed | 39 |
| Unique documents found | **256** |
| Documents with a downloadable PDF | **110** |

The search recovered, among others:

* `19900016137` — **"Carbon dioxide and water exchange rates by a wheat crop in NASA's Biomass Production Chamber: results from an 86-day study"** (NASA TM-102788, Wheeler & Sager, 1990)
* `19900009537` — "Continuous hydroponic wheat production using a recirculating system" (NASA TM-102784, Mackowiak et al., 1989)
* `19910010713` — "Carbon dioxide and water exchange of a soybean stand grown in the biomass production chamber" (NASA/ASEE fellowship report, 1990)
* `19940009239` — "Biomass Production Chamber air analysis of wheat study (BWT931)" (NASA TM-109192, 1993)
* `19900016140` — "System development and early biological tests in NASA's Biomass Production Chamber" (NASA TM-103494, 1990)

**These documents contain exactly the measurements Phase 6 declared non-existent.**
See `docs/NASA_EXPERIMENTAL_MEASUREMENT_RECOVERY.md`.

## 5. Phase 7 scope

| Part | Work |
|---|---|
| A | Recover NASA experimental measurements from NTRS reports; extract validated numerical tables |
| B | Determine training eligibility; train what the evidence supports; fix reproducibility |
| C | Calibrate and validate the simulation against recovered measurements |
| D | Execute the PostgreSQL integration test on a real isolated instance; verify deployment config |
| E | Integrate, test, commit, push per feature |

## 6. UI preservation commitment

`frontend/src`, `frontend/public` and `frontend/index.html` are treated as
read-only. Baseline is `git diff cf1d6c3 -- frontend/src frontend/public
frontend/index.html` = empty. This is re-verified at the end of Phase 7.
