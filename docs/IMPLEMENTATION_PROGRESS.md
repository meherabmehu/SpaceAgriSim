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
- Add independent external validation and calibrated uncertainty before any model leaves exploratory status.
- Configure a managed database and explicit CORS policy before enabling hosted history writes.
- Profile and split the large WebGL bundle further if field performance requires it.
