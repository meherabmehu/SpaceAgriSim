# Phase 2 baseline verification

Verified on 2026-11-06 from branch `feat/phase2-scientific-validation`, created from `main` at merge commit `804a901`.

## Repository state

- The prior `feat/scientific-mission-platform` branch is an ancestor of `main`; its work was merged by `804a901`.
- No tracked uncommitted files existed before the Phase 2 audit.
- Remote is `https://github.com/meherabmehu/SpaceAgriSim.git`.

## Observed implementation

| Area | Verification result | Status |
| --- | --- | --- |
| Frontend workspace | `MissionPlatform` and module views cover dashboard, laboratory, comparison, evidence, analytics, advisor and methodology | Implemented |
| Backend | FastAPI routes provide simulation, workspace, research/model, report and readiness endpoints | Implemented |
| Simulation | Configurable mathematical scenario engine with explicit simulation-method documentation | Implemented but assumption-driven |
| NASA registry | 13 OSDR study entries, manifest, checksums and selected downloaded files are present | Implemented; scientific suitability requires Phase 2 audit |
| ML artifacts | Mizuna, tomato molecular-context and Earth-only WUR lettuce JSON artifacts plus offline training scripts are present | Implemented but experimentally limited |
| Provenance | Dataset/model manifests, checksums, source categories and limitation text are present | Implemented |
| Deployment | Docker/Compose, GitHub CI, Render manifest and Vercel service configuration are present | Configuration verified; live production release requires separate smoke test |
| Persistence | SQLite/PostgreSQL-compatible storage and migration files are present | Implemented; production database provisioning not verified |

## Current test evidence

| Check | Actual result |
| --- | --- |
| `backend/.venv/Scripts/python.exe -m pytest -q backend/tests` | 95 passed; 2 third-party deprecation warnings |
| `npm run lint` | passed after excluding generated Playwright report bundles from lint scope |
| `npm run typecheck` | passed |
| `npm run build` | passed; Vite reports two large JavaScript chunks (673 kB and 922 kB minified) |
| `npm audit --audit-level=high` | 0 known vulnerabilities |
| `docker compose config --quiet` | passed |
| Playwright | A fresh all-project run passed desktop (5), tablet (5), and the first three mobile tests before this environment's 30-second command window ended. A full uninterrupted Phase 2 run remains required; it is not claimed as passed here. |

## Audit correction

Playwright leaves generated `playwright-report/` and `test-results/` directories below `frontend/`. The original ESLint scope linted those bundled third-party files and produced 564 irrelevant errors. These generated directories are now explicitly ignored by ESLint; application-source lint passes.

## Scientific baseline and limitations

- The simulator is not a calibrated mission digital twin.
- The NASA mizuna artifact is appropriately exploratory: its recorded grouped-CV R2 is negative and it must not be treated as an operational predictor.
- The tomato artifact is a molecular flight-context classifier, not a tomato health, disease or yield model.
- The WUR lettuce artifact is explicitly external, Earth-only and restricted to its measured domain.
- Moon and Mars views remain hypothetical scenarios unless independent evidence is identified and documented.

## Phase 2 next actions

1. Audit official NASA sources for additional directly measurable crop and life-support data.
2. Reassess candidate datasets by unit, independent experiment, controls, licensing and ML suitability.
3. Reproduce and stress-test each existing training pipeline before replacing any artifact.
4. Add scientific-sanity, domain and uncertainty tests only where evidence supports them.
