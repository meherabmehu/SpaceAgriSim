# Phase 31 — Zero-Backlog Complete Platform Audit, Repair, Scientific Validation & Finalization

Start state: remote `main` at `e3f41b6` (end of Phase 30). Every item below was executed against
that tree; nothing in this report is a plan, and no gate is claimed that was not run.

---

## 1. Start and final SHAs

| | Value |
|---|---|
| Start (remote `main`, verified) | `e3f41b684759727c7d6c159faa184a81e61cd419` |
| Delivery commit (code + this report) | `f1e5fd7806a3f390caa0039e6c75600517e6830e` |
| Final (this line added in a report-only follow-up commit) | `git log -1 --format=%H` on `main` |
| Branch | `main`, fast-forward history, Phase 30 work preserved |

---

## 2. Bugs found and fixed

| # | Bug | Where | Fix |
|---|---|---|---|
| 1 | Dashboard note *"Loading API configuration; bundled control ranges shown until connected"* never cleared | `frontend/src/hooks/useSimulationConfig.js` | Root cause: the hook `catch {}`-swallowed every failure, never retried, and reported `source: 'fallback'` for both "in flight" and "failed", so the caller rendered a loading message forever. Rewritten as an explicit `loading / live / error` state machine with a bounded backoff (1.2 s / 3 s / 6 s), a shared in-flight promise (one request per page, no StrictMode abort churn), a manual retry, and an error banner that says the sliders are placeholders. `run`/`save` are disabled unless the configuration is live. |
| 2 | First `/api/config` call paid the model-import cost | `backend/app/main.py` | `lifespan` warms `simulation_config()` at startup: first request 3182 ms cold → 12 ms; second 3.3 ms. `app.state.config_warmed` records it. |
| 3 | *"Shape supported · level not identified"* was a caution standing in for a claim | `backend/app/water_evidence.py`, `WaterEvidencePanel.jsx` | The level is **not** identifiable from this trial and no assumption can settle it (pot-surface vs canopy denominators differ by 0.247× to 2.7×, in opposite directions). The panel now states the claim it does support — rank agreement, ρ = 0.791 over 11 dates — names the observation that would settle the level, and labels the assumed-area ratio as "not a bias estimate". Wording is no longer a warning about a gap; it is the scope of a measured comparison. |
| 4 | Model category/source counts did not match the cards | `backend/app/research.py`, `sciencePanels.jsx` | The counts came from a regex over free-text artifact `sourceType`; two served models had no such field and were rendered "source type not recorded" while the header claimed full attribution. Counting now comes from a structured `PROVENANCE` record (institution, study, repository, category), `_served_row` publishes that label as `sourceType`, and a test recomputes the counts from the rows. |
| 5 | Retired models were still listed, labelled and reachable | `research.py`, `routes/research.py`, `science_classification.py`, `routes/workflows.py`, `frontend` | `mizuna-harvest-v1`, `mizuna-microbial-load-v1` and `et0-emulator-v1` are removed from `MODEL_IDS`, the workflow catalogue, the input families, the science classification table, the predict routes and every UI card. Tests assert absence (404 / not listed), not a tombstone. |
| 6 | ET0 emulator was classified as a mechanistic calculation | `app/et0.py`, `MODEL_IDS`/`EXTERNAL_SERVICES` | It is a fitted surrogate of a determined quantity, it lost to Hargreaves–Samani on leave-one-site-out (≈19 % worse), and its inputs are the same as FAO-56's — so there was nothing to emulate. Removed from serving. What remains is the FAO-56 Penman–Monteith calculation with Hargreaves–Samani as a documented low-input fallback, both checked against the published worked examples (Example 17 Bangkok: 5.768 vs 5.72 mm/day). |
| 7 | Duplicate/aborted requests on every page load (StrictMode) | `useSimulationConfig.js`, `MissionPlatform.jsx` | Shared promise for `/api/config`, module-level bootstrap promise for `/api/datasets` + `/api/models`. No `net::ERR_ABORTED` in the console and no duplicate calls. |
| 8 | Browser suite was non-deterministic | `playwright.config.js`, `vite.config.js` | The suite now runs against the production build through `vite preview` with the same `/api` proxy instead of the dev server, removing on-demand transforms and HMR from every assertion's timing. 120/120 across three viewports in 2.9 min. |
| 9 | Two stale e2e expectations survived the removals | `e2e/assistant.spec.js`, `e2e/water-evidence.spec.js` | The model-card test asserted a visible `retired` label; it now asserts there is **no** retired row and that every card shows its provenance. The water test asserted the old caution sentence; it now asserts the rank-only verdict, the "level identified? no" line, and the "would be identifiable with" sentence. |
| 10 | 24 orphan frontend modules (dead dashboard, unused charts, controls) | `frontend/src` | Deleted after proving nothing imports them (`npm run build` + `lint` + the full browser suite). |

---

## 3. Datasets searched, acquired, integrated

Phase 31 acquired **no** new dataset. That is a finding, not a shortcut: the three withdrawals are
validation failures on data already held, not data-starvation, and the one open measurement gap
(the water-denominator geometry) was searched for and does not exist in the publication record.

| Target | Repositories searched | Outcome |
|---|---|---|
| Pot geometry / plant spacing for the greenhouse lettuce water-use trial (Zenodo `10.5281/zenodo.5550230`) | Zenodo record, the Schröder et al. 2021 paper and its supplement, publisher page, Crossref | Not published. The trial reports pot **volume**, not diameter or spacing. Recorded in `water_evidence.py` as an irreducible ambiguity instead of an invented denominator. |
| Independent replication for a mizuna microbial **absolute** load model (withdrawn) | NASA OSDR / ALSDA (`OSD-780`, VEG-04A/B), GeneLab (`GLDS-46`), Zenodo, Dryad, Figshare, PANGAEA, Mendeley Data | Only `OSD-780` carries plate counts for ISS-grown mizuna; a single campaign cannot supply a held-out site. The absolute model was withdrawn; the within-campaign relative model (`mizuna-microbial-relative-load-v2`) is served and says so. |
| Independent sites for an ET0 surrogate (withdrawn) | Zenodo, Dryad, FAO CLIMWAT/AgriMet-type station records reachable from the sandbox | No second site network could be acquired reproducibly inside the sandbox (USDA Ag Data Commons DNS unresolvable, figshare search endpoint rejects scripted queries, Dryad download 401). The surrogate was withdrawn rather than excused; the deterministic FAO-56 calculation needs no site network. |

Phase 30 acquisitions (kept, unchanged): Zenodo `10.5281/zenodo.17764612` (indoor wheat, cc-by-4.0)
and Zenodo `10.5281/zenodo.14640245` (lettuce LUE compilation, cc-by-4.0). Rejected candidates and
their reasons remain in `data/metadata/dataset_manifest.json`.

---

## 4. Models retained, repaired, removed

**Served: 7.** Counts are recomputed from structured provenance, not free text — 4 trained on
NASA-measured data, 3 on non-NASA measured data, 0 retired.

| Model | Status | Evidence |
|---|---|---|
| `lettuce-earth-growth-v1` | retained | R² 0.812, MAE 38.94 g; nested leave-one-experiment-out (4 folds) |
| `lettuce-earth-growth-v2` | retained | R² 0.870, MAE 34.92 g |
| `lettuce-earth-growth-v3` | retained | R² 0.861, MAPE 41.68 %, n = 1648 |
| `mizuna-microbial-relative-load-v2` | retained | R² 0.509, MAE 0.539; positive on every held-out campaign, permutation p = 0.000; explicitly a **within-campaign relative** claim |
| `radiation-quality-osd46-v1` | retained | accuracy 0.932 / F1 0.898 on held-out NASA GeneLab groups |
| `radiation-exposure-osd46-v1` | retained | accuracy 0.932 / F1 0.910 |
| `tomato-flight-response-v1` | retained | accuracy 0.917 / F1 0.916 / AUC 0.975, grouped by sample |

**Withdrawn (records kept, surfaces gone):**

| Model | Reason |
|---|---|
| `mizuna-microbial-load-v1` | Leave-one-site-out R² −0.55 / −0.58. Cannot generalise to a new campaign. |
| `mizuna-harvest-v1` | Held-out R² −0.333 against a mean baseline R² −0.138; MAPE 41.7 % / 39.3 %; worse cross-study. |
| `et0-emulator-v1` | ≈19 % worse than Hargreaves–Samani leave-one-site-out, on inputs FAO-56 already needs. |

Artifacts, evaluations and the reasoning are kept in `ml/artifacts`, `ml/evaluation` and
`docs/PHASE31_REMOVED_MODELS.md`; `/api/science/checksums` still lists them with `served: false`.

---

## 5. Features completed

- Config loading has three honest states and recovers by itself.
- Scientific-status panel derives every count and every card label from recorded provenance.
- Water-use panel states a rank-only claim, the measured spread, the three denominators and their
  measured/assumed status, and the observation that would settle the level.
- Reference ET0 is a pure FAO-56 implementation with Hargreaves–Samani fallback and published-example
  checks served at `/api/reference-et0/model`.
- Withdrawal is now a first-class state: the catalogue, the input families, the routes, the classifier
  table and the UI all agree that three models do not exist as served capabilities.

## 6. Unsupported features removed

Harvest-prediction workflow (`/api/workflows/harvest-prediction/{run,capability,parity}` and
`app/workflows/harvest.py`), the mizuna harvest predict form and its route, the microbial absolute-load
predict route and input family, the ET0 emulator route/service/diagnostics and its UI card, the
retired-model listing and its "retired" pill, 24 orphan frontend modules, and the four UI strings that
described them. `docs/PHASE27_FEATURE_COVERAGE_MATRIX.md` was regenerated (12 features, 1 complete
workflow, 6 documented gaps) and the coverage builder's evidence paths now point at files that exist.

## 7. APIs verified

87 → 82 documented paths. Asserted absent (404, no route, no OpenAPI entry): the three
harvest-prediction endpoints, `/api/predict/mizuna-harvest-v1`,
`/api/predict/mizuna-microbial-load-v1`, `/api/reference-et0/model`'s emulator fields. Asserted
present and exercised with realistic valid and invalid bodies: `/api/config`, `/api/simulate`,
`/api/workflow/*`, `/api/workflows/{water-demand,light-stress}/*`, `/api/water-use-evidence[/compare]`,
`/api/reference-et0[/estimate|/model]`, `/api/models`, `/api/datasets/*`, `/api/assistant`,
`/api/explorer/*`, `/api/analyses/*`, `/api/auth/*`, `/api/health`, `/api/ready`.

## 8. Pages and workflows verified

Dashboard, simulator, lab (incl. water-evidence panel), guided workflows (water demand, light stress),
AI prediction centre, model comparison, benchmarks, evidence/assistant, research assistant, account,
shared scenarios — at 1440×1100, 820×1180 and Pixel 7. Every retained control was driven; every
removed control was asserted absent from both the page and the API.

## 9. Test results

| Gate | Result |
|---|---|
| Backend, SQLite | **1164 passed, 24 skipped, 0 failed** (29.8 s) |
| Backend, PostgreSQL 17.11 | **1187 passed, 1 skipped, 0 failed** (33.5 s) |
| Playwright (desktop / tablet / mobile) | **120 passed** (40 / 40 / 40), 2.9 min |
| Frontend lint / typecheck / production build | clean / clean / built |
| `scripts/audit_models.py` | **152 checks run, 0 failed**, 19 documented gaps |
| `scripts/verify_model_registry.py` | **60/60** |
| `ml/research/build_feature_coverage.py --check` | coverage up to date (12 features) |

New coverage added this phase: the `identification` block of the water comparison (rank-only claim,
no correction, no scale factor), the completeness of model provenance and the arithmetic of the
dashboard counts, absence of the withdrawn models from the loadable catalogue, and browser tests for
the absence of the removed harvest workflow and retired cards.

## 10. Model audit result

`ml/evaluation/phase13_model_audit.json` rewritten by the audit script: 7 served models, all with a
verified artifact (SHA-256 matched against `ml/artifacts/registry.json`), a recorded validation
scheme, a baseline comparison and a domain; 3 withdrawn models retained with `served: false`; 19
documented gaps (each a stated limitation, not a hidden one).

## 11. Remaining genuine external blockers

1. **No independent site network for ET0 emulation.** The surrogate is withdrawn, so the claim is no
   longer made; a future emulator would need multi-site station data that could not be acquired
   reproducibly here.
2. **No second mizuna microbial campaign.** The absolute-load model is withdrawn for that reason.
3. **Trial geometry unpublished.** The greenhouse water-use comparison can support a rank claim and
   never a level claim until per-pot area or spacing is published.
4. **Sandbox dataset endpoints.** USDA Ag Data Commons is DNS-unresolvable from this environment,
   figshare's search API rejects scripted queries, and Dryad returns 401 on direct downloads; any
   future acquisition from those hosts must be done outside the sandbox.

None of these leave a user-visible claim standing: each one is either removed, or stated as the scope
of what is shown.

## 12. Constraint compliance

No Render work of any kind: no deploy, no service settings, no environment variables, no production
database access, no paid resource. Local SQLite and a throwaway local PostgreSQL cluster only.
