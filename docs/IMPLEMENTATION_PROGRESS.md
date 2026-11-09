# Implementation progress

## Delivered

- Scientific-data acquisition, file checksums, preprocessing, model registries and offline training artifacts.
- FastAPI scientific endpoints, simulation extensions, validated request models, reporting, scenario history and optimizer endpoints.
- Responsive mission-control experience, research explorer, analysis/advisor views, comparison views, 3D greenhouse and accessible fallbacks.
- Docker/Compose, CI checks, Vercel multi-service configuration and runtime scientific-data packaging.
- Documentation of architecture, API, provenance, methodology, gaps, evaluation, limitations and verification.

## Hosted runtime design

The Vercel API service packages a small checksum-verified read-only copy of the data/model assets at build time. On serverless Vercel deployments, history writes are intentionally marked read-only unless a durable database and enabled write policy are configured. Local and container deployments can enable durable scenario history through `SPACEAGRISIM_DATABASE_URL`.

## Follow-up work

- Obtain sufficiently large, compatible mission and ground yield datasets before recalibrating the simulator.
- Add calibrated uncertainty before any model leaves exploratory status.
- Independent external validation for the lettuce model: screened, not yet obtained. `data/literature/external_validation_screen.json` records each candidate source, what it publishes, and the verdict, and is served at `GET /api/external-validation` and shown on the benchmarks page. PeerJ 17085 (Wicharuck et al. 2024, CC BY 4.0) is in domain on every input but publishes study averages across three light levels; it becomes usable once its per-level table is transcribed verbatim. Touliatos et al. 2016 sits below the model's 20 °C floor and was not extrapolated into. The model's own domain check flags that source `outOfDistribution` through the prediction route, which is what the panel displays.
- Configure a managed database and explicit CORS policy before enabling hosted history writes.
  Live check 2026-11-09: database-backed routes were failing on the hosted instance (login 500,
  share links 503) while `/api/health` stayed green. URL aliases are now normalised and `/api/ready`
  reports a `reason` code; the remaining step is setting `SPACEAGRISIM_DATABASE_URL` on the host.
- Profile and split the large WebGL bundle further if field performance requires it.
