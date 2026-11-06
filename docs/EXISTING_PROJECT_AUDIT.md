# Existing project audit

Audit baseline: commit `bbeb658`, inspected 2026-11-06. The checkout was clean on `main`; origin matched `https://github.com/meherabmehu/SpaceAgriSim.git`. Work proceeds on `feat/scientific-mission-platform` without replacing existing commits.

## Architecture and reusable work

The existing Vite/React 19 application has one `DashboardPage`, Tailwind 4 tokens, Recharts growth/water/gas charts, a procedural React Three Fiber greenhouse, abortable fetch helpers, backend-driven control ranges, and lightweight deterministic insight generation. The Python FastAPI application separates request schemas, routes, a framework-independent dataclass engine, crop profiles, response serialization, and scientific modules. Existing backend tests cover API validation, factors, growth, gas stoichiometry, water accounting, and impact attribution. These are useful foundations and should be retained.

## Findings at the baseline

| Area | Existing behavior | Gap / action |
| --- | --- | --- |
| Navigation | One long dashboard, sticky parameter column | Replace composition with responsive mission shell and distinct task modules |
| Visual identity | Dark panels and a starfield | Redesign hierarchy, navigation, hero, charts and controls; preserve readable contrast |
| Growth | Normalized logistic curve; fixed crop cycles; area scales fresh edible biomass | Assumed amplitudes and cycle lengths; environmental stress scales amplitude but never delays harvest; disclose this limitation |
| Harvest | Standing, cumulative and harvested totals distinguished | Daily biomass curve shows mature plants on harvest day while summary standing biomass is zero; explicitly explain end-of-day semantics |
| Gravity | Linear 15% microgravity penalty, crop sensitivity multipliers | Placeholder response, not established partial-gravity evidence; do not call lunar/Mars outputs validated |
| Radiation | Exponential penalty using mGy/day above a 0.01 background | Assumed coefficient; no cumulative dose, radiation quality, shielding or experiment matching |
| Light / CO2 | Saturating photoperiod and CO2 response | No PPFD, temperature, humidity or light spectrum controls; add explicit assumption models and avoid invented spectrum coefficients |
| Water | Canopy-scaled demand; availability fraction; fixed 90% condensate recovery | No measured transpiration calibration; no temperature/VPD effect; recovery not user configurable |
| Gas exchange | Biomass gain → total fresh mass → dry mass → carbon → CO2, O2 mass ratio 32/44 | Consistent units, but harvest-index and dry-fraction assumptions dominate; no respiration, photon or energy balance |
| Comparison | Earth reference in matched/baseline modes | Add separately labeled Earth/Moon/Mars hypothetical habitat comparison |
| 3D | Instanced leaves, water manifold, lighting and sensor illustration; lazy loading; WebGL fallback | Camera drifts automatically; add deliberate camera interaction and component inspection; motion must not imply measured flow |
| NASA data | README roadmap only; no downloaded data, manifests or registry | Verify official study metadata and actual files; classify molecular/phenotypic targets before training |
| ML | No artifact, training implementation or evaluation | Train only a task supported by real labels; show unavailable growth ML honestly |
| Persistence / exports | No durable scenarios or report API | Add explicit saved experiment storage and reproducible CSV/JSON/PDF exports |
| Optimization | No optimizer | Add constrained finite search and sensitivity; report mathematical-model limitations |
| API validation | Pydantic ranges; flat 422 field errors | Preserve validation, reject unknown request fields and nonfinite inputs; keep extended control contract synchronized |
| Security | Environment examples, .gitignore secrets, explicit localhost CORS | No user authentication, tenant isolation, gateway rate limiting, request audit trail or persistence policy; public scenario writes need protection |
| Performance | Debounced fetch; instancing; reduced-motion and offscreen rendering | Effect cleanup cancels debounce but delays aborting old request until next starts; old output may render after parameter change; fix stale result handling |
| Deployment | Vercel multi-service configuration | No Docker, CI, deployment smoke checks, immutable release/rollback instructions; provide independent Docker deployment |
| QA | Backend tests only, ESLint/build scripts | Add browser tests across desktop/tablet/mobile, evidence captures, type checks and dependency audits |

## Scientific units and assumptions

The original constants consistently document fresh biomass in g, growing area in m², water in L, gas masses in g, gravity in Earth g, absorbed radiation in mGy/day, photoperiod in h/day, and CO2 in ppm. Stoichiometric gas mass conversion is dimensionally sound. Fresh biomass is **not** dry biomass; genomic abundance is **not** harvest mass. The original simulator is an educational hypothesis model; constants themselves say they are not measured NASA values. No original model establishes operational life-support adequacy.

## Implementation roadmap and traceability

1. Preserve the engine and existing tests; extend environmental controls and provenance without silently recalibrating constants.
2. Replace `DashboardPage` with mission navigation, overview, laboratory, prediction/data/crop views, comparison, analytics, advisor and methodology.
3. Reuse charts, typed backend ranges and 3D scene where useful; improve camera controls, component inspection and accessible fallback.
4. Build official NASA discovery → metadata/checksums → download → schema/quality validation → measured-target processing. Record every verified study and gap.
5. Train and evaluate only a supported measured task using experiment grouping. Publish model cards and inference coverage; retain transparent scientific estimates for unsupported outputs.
6. Add scenario comparison, constrained optimization, deterministic advisory explanations, report exports and explicit persistence behavior.
7. Run existing and new backend tests, production build/lint/type checks, browser scenarios and dependency audits. Resolve observed failures.
8. Document actual results and blockers, publish feature commits individually, and prepare/deploy using available credentials without claiming unverified success.

Feature completion, checks, commit hashes and push evidence belong in `IMPLEMENTATION_PROGRESS.md`. Dataset and model evidence belong in their dedicated inventory and evaluation documents. This audit describes the original implementation, not a claim that the roadmap is complete.
