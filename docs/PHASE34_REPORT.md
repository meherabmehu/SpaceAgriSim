# Phase 34 — evidence-driven scientific expansion, visual baseline repair, complete platform readiness

* Starting commit (verified with `git ls-remote` before the clone was used):
  **`e7ee85582bfc4224e9f94a4f0d3e85672dcc95fa`**
* Branch: `phase34/evidence`, merged fast-forward into `main`
* Delivery commit: recorded in `PHASE34_DELIVERY.txt` together with the verified remote `main`
  SHA, because a commit cannot contain its own hash

Phase 34 was scoped as an evidence phase, and it stays one: five open findings were answered by
measurement, two false statements were removed from served text, the visual gate was repaired, and
**no model was trained, promoted, reinstated or retired**.

---

## 1. Datasets — searched, verified, rejected

Full detail in `PHASE34_DATA_ACQUISITION.md`. Summary:

| source | verdict |
|---|---|
| NASA OSDR **OSD-780** (CC0-1.0, `10.26030/s3hn-cj93`) | **used** — contains *both* VEG-04A and VEG-04B campaigns; already in `data/processed/mizuna_microbial_load.csv` (356 rows) |
| **PeerJ 12:e17085** (CC BY 4.0, `10.7717/peerj.17085`) | **used** — six measured treatment means, full study conditions, committed transcription |
| Zenodo `17794636` (CC-BY-4.0) | verified and rejected — `Destructive harvest` 201×34 and `Overall fw`; no temperature, PPFD or photoperiod, so it cannot support any response model |
| Zenodo `20759414` (39.1 GB), `8410252` (49.8 GB) | rejected — too large to verify end to end in this environment |
| Dryad records screened | rejected — no controlled-environment crop water use or LED response |
| Agronomy `12:1026`, biorxiv `2025.01.16.633207`, JXB `erag222`, SCRI-OPTIMIA DLI report | rejected — papers and reports with treatment means, not acquirable datasets |
| OSDR registrations / metadata records | rejected — a registration is not a measurement table |

**No dataset was added in Phase 34.** The independence the phase needed was already in the
repository and had never been used as such; adding bytes would not have improved the measurement,
and two of the five results are negative, which no amount of extra data would have changed.

## 2. Capabilities actually improved

| capability | before | after |
|---|---|---|
| tomato classifier probability quality | undetermined | measured out of fold with plant-resampled intervals |
| interval scope for 5 models | "within the fitted campaign" | measured against an independent campaign, in the card and in the API's `scopeStatement` |
| mizuna campaign scope | false claim: no second campaign exists | both VEG-04 campaigns named, both calibration directions reported |
| visual regression gate | could not pass (stale baselines, one ungated panel) | 12/12 genuine passes, deterministic captures |

**No new prediction capability.** Nothing predicts anything it did not predict at `e7ee855`.

## 3. Models trained, evaluated, retained, rejected

| | |
|---|---|
| trained | **none** — this phase measures shipped artifacts through `app.research` |
| evaluated | 5 intervals (3 lettuce, 2 mizuna) + 1 classifier's probabilities |
| retained | all 9 registered artifacts and all 7 served models; no card was weakened |
| rejected / withdrawn | none newly; `mizuna-microbial-load-v1` stays unreachable (a test asserts `load_model` still raises) |

### 3.1 Probability calibration — `tomato-flight-response-v1`

Out of fold under the committed plant-grouped split (36 samples, 21 plants, both tissues of a
plant in one fold). No rescaling fitted; served scaling `none`; card says `measured: true`,
`calibrated: false`.

| metric | value | 95 % plant-resampled |
|---|---|---|
| log loss | 0.2827 | 0.1881 – 0.3902 |
| Brier | 0.0810 | 0.0440 – 0.1255 |
| ECE (10 bins) | 0.1621 | 0.1357 – 0.2342 |

7 predictions at or above 0.9, 0 wrong; ECE still says confidence ≠ accuracy.

### 3.2 Cross-campaign interval coverage

| model | within-campaign | independent campaign | ratio median (min–max) |
|---|---|---|---|
| `lettuce-earth-growth-v1` | 0.9393 | **0 / 6** | 3.655 (1.905–5.493) |
| `lettuce-earth-growth-v2` | 0.9606 | **0 / 6** | 3.212 (1.674–5.375) |
| `lettuce-earth-growth-v3` | 0.8993 | **6 / 6** | 1.163 (0.606–1.863) |
| `mizuna-microbial-load-v1` | 0.9919 | **107 / 123** pooled, both directions | 0.8699 achieved vs 0.90 nominal |
| `mizuna-microbial-relative-load-v2` | 0.9919 | **110 / 123** pooled, both directions | 0.8943 achieved vs 0.90 nominal |

Read this the way the evidence files do:

* v1 and v2 **over-predict the independent greenhouse by ~3×** and their 90 % intervals contain
  none of the six measured treatment means. Their 0.96 within-campaign figure measured the spread
  of four plant-factory experiments, not distance to another campaign.
* v3 covering 6/6 is **coverage, not accuracy** — six correlated means from one greenhouse, a wide
  interval, and its declared independent holdout (Touliatos 2016, 41.6 % MAPE vs a 30 % criterion)
  still fails. That failure is unchanged and still printed on its card.
* The mizuna intervals degrade mildly across campaigns (0.87–0.89 against nominal 0.90). Both
  directions were evaluated; calibration and evaluation never shared a campaign.

Artefacts: `ml/evaluation/phase34_probability_calibration.json`,
`ml/evaluation/phase34_cross_campaign_coverage.json`, reproducible with
`ml/research/phase34_tomato_calibration.py` and
`ml/research/phase34_cross_campaign_coverage.py`.

### 3.3 Two bugs this phase caught in its own work

1. v3 predicts **fresh yield per m²**, so comparing it to a per-plant measurement without dividing
   by planting density produced a 56× error and a false "0/6 covered". Fixed by reproducing the
   route's own arithmetic and dividing by the campaign's density.
2. The within-campaign coverage key differs per card (`achievedCoverage` vs `empiricalCoverage`);
   the fallback silently reported `None`. Fixed and asserted.

Both are recorded because a measurement script with a unit bug produces a confident wrong number.

### 3.4 Reproducibility re-check

The studies were re-run from scratch in a rebuilt interpreter environment (fresh virtualenv,
`pandas` 2.2.3 / `numpy` 2.3.5 / `scikit-learn` 1.6.1 per `ml/requirements-training.txt`) and the
outputs compared against the committed files: **both evaluation JSONs reproduced identically**,
apart from the `generatedAt` timestamp and the recorded environment block. Every number quoted
above is therefore reproducible from the committed scripts, not just recorded once.

## 4. The five audit limitations

| finding | outcome |
|---|---|
| `tomato-flight-response-v1` / calibration | **measured** — resolved by measurement, not by relabelling |
| `lettuce-earth-growth-v1` / calibration-scope | **measured** — 0/6, resolved as truthfully recorded (documentation gap closed, accuracy claim untouched) |
| `lettuce-earth-growth-v2` / calibration-scope | **measured** — 0/6 |
| `mizuna-microbial-load-v1` / calibration-scope | **measured** — 107/123 pooled |
| `mizuna-microbial-relative-load-v2` / calibration-scope | **measured** — 110/123 pooled |

Audit before: **161 checks, 0 failed, 5 documented gaps, 3 resolved**.
Audit after: **168 checks, 0 failed, 0 documented gaps, 7 resolved (3 Phase 32, 4 Phase 34)**.

No severity threshold was lowered, no gap was closed by a UI panel or endpoint, and the two
negative results (0/6) are recorded as failures rather than spun as limitations resolved. The
remaining open limitations that are **not** audit gaps (v3's failed holdout, the shape-only water
benchmark, no measured reference ET / substrate-moisture / LED-spectrum dataset, the ET0
emulator's withdrawal, `mizuna-harvest-v1`'s negative R²) all stay exactly as they were, listed in
§9.

## 5. Visual regression

Detail in `PHASE34_VISUAL_REGRESSION.md`, measurement in
`ml/evaluation/phase34_visual_drift.json`.

* Rebuilt the **Phase 33 parent commit `e7ee855`** in a worktree and ran the identical Playwright
  suite and viewports on both trees; all three image sets are committed.
* **Pre-existing drift:** every committed baseline had a different canvas size from the shipped
  page (mission desktop 1440×1569 → 1440×1649; radiation panels 1128 px → 1104 px wide). The gate
  could not have passed; it had simply stopped being run.
* **Phase 34's own change: none.** Parent → candidate is **0.000 % on 12/12 captures** after
  repairing two capture-determinism bugs (a hover/focus ring recorded because the screenshot
  followed a click, then a mid-transition tint because the blur was sampled in the same frame).
* **Decision:** regenerate the baselines from the **parent commit** (not the candidate's own
  output), archive the originals under `docs/screenshots/historical/phase9/` with both canvas
  sizes, and add the three `water-evidence-*` captures the suite had been producing but nothing
  was gating. No tolerance changed, no baseline written from failing output.
* Gate result: **12/12 PASS at 0.000 % differing**, recorded in
  `ml/evaluation/phase9_visual_regression.json`.

## 6. Bundle and performance

Measured with `npm run build:check` (no budget change, no warning suppression;
`chunkSizeWarningLimit` untouched):

| chunk | size | loaded |
|---|---|---|
| `vendor-react` | 192.91 kB (60.52 kB gz) | initial |
| `index` | 34.32 kB (11.94 kB gz) | initial |
| `vendor-icons` | 18.31 kB (6.56 kB gz) | initial |
| `vendor-charts` | 402.65 kB (115.99 kB gz) | **lazy** |
| `DigitalTwin3D` | 25.64 kB | lazy |
| `Evidence`, `GuidedWorkflows`, `ScientificWorkflow`, … | 11–30 kB | lazy |

* Initial request: **240 kB across 3 modules** — unchanged from baseline, within the 240 kB budget.
* `frontend/dist/index.html` references only `index`, `vendor-react`, `vendor-icons` and the CSS,
  so **no chart code is downloaded by a page that has no chart**.
* **Decision on the remaining large chart dependency: retain, with the measurement above.**
  Investigated three routes to reduction and rejected each for a stated reason:
  per-route splitting cannot help because one library is shared by four lazy routes and would
  either duplicate the chunk or move the same bytes; the `GrowthPlot` component inside the mission
  shell is already a dynamic import, so the first render of the dashboard does not fetch it; and
  replacing recharts with hand-written SVG would be a UI rewrite with no measured user-facing
  benefit and a real risk of unrelated layout change, which this phase is explicitly not allowed
  to make. The dependency remains lazy, and the budget remains enforced by `build:check`. The
  dependency-free SVG chamber from Phase 33 is unchanged.

## 7. Backend, database, API

* SQLite suite: **1225 passed, 23 skipped** (baseline 1213/23; +12 new tests).
* PostgreSQL 17.11 suite: **1248 passed, 0 skipped** (baseline 1236/0; +12 new tests), against an
  isolated schema on `127.0.0.1:55432`.
* Every skip is a PostgreSQL persistence test skipped in the SQLite run, with its reason printed;
  in the PostgreSQL run nothing is skipped. No test was deleted, skipped, weakened or rewritten.
* OpenAPI: 83 paths / 90 operations. No route added, removed or changed; the API contract tests
  and the removed-feature-absence tests pass unchanged.
* The new evidence reaches users through the existing `scopeStatement` field and the model detail
  payload — no new endpoint, and no capability claimed because a field exists.
* No migration, no schema change, no production data touched, `--workers 1` unchanged.

## 8. Gates

| gate | result |
|---|---|
| SQLite suite | 1225 passed, 23 skipped |
| PostgreSQL 17.11 suite | 1248 passed, 0 skipped |
| frontend lint | clean |
| frontend typecheck | clean |
| production build | 2698 modules, built in 4.52 s |
| `build:check` | passed — no cycles, no oversized chunk, initial request within the 240 kB budget |
| model audit | 9/9 models, 168 checks, 0 failed, 0 gaps, 7 resolved |
| registry verification | 60/60 |
| provenance verification | 9/9 artifacts |
| measurement reproduction | both Phase 34 evaluation files identical on a rebuild |
| feature readiness / coverage / gap matrix | all up to date (12 / 12 / 14) |
| card-vs-evidence check | 5 cards recorded, no drift |
| visual regression | 12/12 PASS, 0.000 % differing |
| Playwright | 123 passed ×3 viewports (desktop 1440×1100, tablet 820×1180, mobile Pixel 7) |
| scientific workflow regression | included in the Playwright suite, passing |
| API contract + removed-feature absence | passing within both suites |

## 9. Unresolved limitations, stated plainly

1. **v1 and v2 lettuce intervals do not transfer.** 0 of 6 independent treatment means covered,
   ~3× over-prediction. They stay served with the failure written into `servedScope`; a user who
   reads the card cannot mistake the interval for a general 90 % claim.
2. **v3's independent holdout failure stands** (Touliatos, 41.6 % MAPE vs 30 %). 6/6 coverage does
   not offset it.
3. **Two campaigns are not a sample of campaigns.** The mizuna cross-campaign coverage bounds the
   offset; it does not estimate its distribution, so a third campaign still needs its own baseline.
4. **PeerJ 2024 is not an untouched holdout** — it was a development check in an earlier phase, and
   the evidence files say so.
5. **The tomato calibration is one experiment** (OSD-767, 21 plants). A nested temperature fit is
   not possible here because the input expression matrix is not vendored.
6. **No measured reference ET, substrate-moisture series, LED-spectrum response surface or
   fractional-gravity data was acquired**, so the corresponding gaps stay open at their unchanged
   severities (`measured-eta` blocking, `substrate-water` blocking, `led-spectrum-response` major,
   `prediction-intervals-independent-coverage` major).
7. **Twelve screenshots are not a design review**, and the regenerated baselines are a property of
   this Chromium build and font set.

## 10. What Phase 34 did not do

No model training, no threshold change, no dataset added, no route added or removed, no schema
change, no test skipped or weakened, no warning suppressed, no budget raised, no production data
touched, and **no Render work of any kind** — no deployment, no environment variable, no service
setting, no plan or worker change, no database infrastructure.
