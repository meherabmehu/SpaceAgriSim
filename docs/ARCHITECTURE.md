# Architecture

SpaceAgriSim retains the original Vite/React frontend and Python FastAPI scientific backend. The redesign adds task navigation around a centralized simulation configuration. Scientific outputs originate from API responses, not display-only constants.

## Boundaries

| Layer | Responsibility |
| --- | --- |
| `frontend/src` | Mission controls, charts, the SVG growth chamber, evidence browsing and API interactions |
| `backend/app/models` | Pydantic input constraints and response contracts |
| `backend/app/routes` | Simulation, mission services and research HTTP APIs |
| `backend/app/simulation` | Framework-independent growth, environment, water, gas and comparison calculations |
| `backend/app/config` | Runtime environment settings and explicit scientific assumptions |
| `data/metadata` | Verified NASA study registry, source URLs, file checksums and processing evidence |
| `data/processed` | Task-specific real measured tables with study/experiment identifiers |
| `scripts` | Discovery, acquisition, validation and transformation outside normal requests |
| `ml` | Reproducible training, grouped evaluation, model cards and inference artifacts |

## Scientific path

The simulator evaluates environmental response factors, scales crop-specific fresh biomass curves, separates harvested and standing biomass, estimates canopy water demand, and converts biomass carbon gain into gas mass. It reports the assumptions and limitations with the outputs. This remains a mathematical scenario estimator wherever measured growth, transpiration or gas labels do not support a trained prediction.

The research pipeline is independent: official NASA metadata → selected verified files → checksum and quality checks → a compatible measured target table → grouped model evaluation → versioned artifact. Molecular and microbial records are not paired with unrelated crop-yield labels. A trained model must retain its own target, units and input domain. Its existence does not validate the mission simulator.

Since Phase 35 that evidence path ends in a **verdict** rather than in prose.
`ml/research/phase35_evidence_verdicts.py` reads the committed evaluation files and each card's own
pre-declared criteria and writes one verdict per model into `ml/evaluation/phase35_model_evidence.json`
and into the card (`evidenceVerdict`). `backend/app/research.py` exposes
`evidence_verdict()` / `verdict_warning()`; every prediction route attaches them to its response,
the catalogue carries them on every row, and `scripts/audit_models.py` fails when a surface disagrees
with the file. A model is `decisionGrade` only when an independent campaign met every criterion set
for it — so a number, its scope and its verdict cannot travel separately.

Validation evidence has its own path since Phase 34, and it runs the other way: `ml/research/*.py` loads the **shipped** artifact through the same code the API uses, measures it against an independent campaign or an out-of-fold split, writes `ml/evaluation/*.json`, and `ml/research/phase34_record_measurements.py` is the only writer that copies those numbers into a model card. `scripts/audit_models.py` then checks the card against the evidence file and `scripts/build_registry.py` re-seals the artifact hash. A served claim therefore has a script that produced it, a file that holds it, and an audit that fails when the two disagree.

## State and storage

Current control state is held in React. Fetch operations support cancellation; stale responses must not replace current configuration. Server-side saved scenarios use a bounded SQLAlchemy table: SQLite for a local demonstration, or PostgreSQL through a configured database URL. Scenarios store reproducible input configuration and model version, not huge raw NASA files. Initial table creation is supported by the application; the PostgreSQL migration can be applied ahead of runtime with a restricted database role.

History is a shared workspace feature. Since Phase 19 the API also carries accounts (`/api/auth/register|login|me|logout`), verification and password-reset endpoints under `/api/account`, and read-only share links (`#shared/<token>`); saved scenarios are owned by their creator and access is checked per request, not inferred from the browser. Tenant isolation beyond per-user ownership is still not a tenancy boundary: a public multi-user deployment needs quotas and a retention policy before enabling unrestricted writes. CORS controls browser access and is not authentication.

## Rendering and operation

The growth chamber is plain SVG, rebuilt in Phase 33: no Three.js, no WebGL and no 3D dependency ships in the bundle. It is an illustration driven by simulation state, not computational fluid dynamics or measured telemetry, and it keeps a reduced-motion path and a 2D fallback that a device can fall back on without losing information. The chart library is the only large third-party UI dependency left; it is a lazy chunk, so a page without a chart never downloads it.

Local Vite proxies `/api` to FastAPI. Docker Compose places nginx before the API and preserves local scenario data in a named volume. Independent hosting uses a Vercel frontend and a Render API with an explicit public API URL and exact CORS origins. Acquisition and model training are offline processes; HTTP requests never run training.

## Deliberate limits

No claim is made of NASA certification, spacecraft safety, independent crop-yield validation or an experimentally established Moon/Mars gravity response. No LLM is required for numerical advice. Formula-based estimates, measured dataset previews and trained experimental models must remain visibly distinguishable.
