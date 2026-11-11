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

## State and storage

Current control state is held in React. Fetch operations support cancellation; stale responses must not replace current configuration. Server-side saved scenarios use a bounded SQLAlchemy table: SQLite for a local demonstration, or PostgreSQL through a configured database URL. Scenarios store reproducible input configuration and model version, not huge raw NASA files. Initial table creation is supported by the application; the PostgreSQL migration can be applied ahead of runtime with a restricted database role.

History is a shared workspace feature. The application does not provide user authentication or tenant isolation. A public multi-user deployment needs an identity/gateway layer, quotas and retention policy before enabling unrestricted writes. CORS controls browser access and is not authentication.

## Rendering and operation

The existing Three.js scene uses instanced leaves and inexpensive procedural geometry. It is an illustration driven by simulation state, not computational fluid dynamics or measured telemetry. Lazy loading, reduced-motion handling, offscreen rendering controls and a 2D fallback constrain device cost.

Local Vite proxies `/api` to FastAPI. Docker Compose places nginx before the API and preserves local scenario data in a named volume. Independent hosting uses a Vercel frontend and a Render API with an explicit public API URL and exact CORS origins. Acquisition and model training are offline processes; HTTP requests never run training.

## Deliberate limits

No claim is made of NASA certification, spacecraft safety, independent crop-yield validation or an experimentally established Moon/Mars gravity response. No LLM is required for numerical advice. Formula-based estimates, measured dataset previews and trained experimental models must remain visibly distinguishable.
