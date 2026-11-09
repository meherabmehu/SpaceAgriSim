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

- Features without a dataset dropped from the UI rather than shown with a caveat: the gravity and
  radiation dose-rate sliders are gone from the simulation form, and the water-recovery control is
  capped at the measured ISS 98 %.
- Closed-loop measurements added: `GET /api/closed-loop` serves NASA's measured ethylene
  production and lettuce dose response (Wheeler et al. 1996) and the ISS 98 % water recovery figure;
  transcribed in `data/literature/nasa_air_and_water.json`. Ethylene stays out of the growth
  equations by design and a test enforces that.
- Obtain sufficiently large, compatible mission and ground yield datasets before recalibrating the simulator.
  For the lettuce model specifically, `docs/DATASET_GAP_ANALYSIS.md` now states the acquisition
  requirements as acceptance criteria: per-observation rows with root-zone temperature, at least two
  labelled cultivars and three light levels each, including one below ~350 µmol m⁻² s⁻¹.
- Add calibrated uncertainty before any model leaves exploratory status.
- Close the external-validation gap the check exposed: the served lettuce model has no cultivar
  input and no non-monotonic light response, so no amount of recalibration will fit the PeerJ
  observations. A replacement would need both features before it could be scored again.
- External validation of the lettuce model: **attempted and failed**. Wicharuck et al. 2024 (PeerJ
  12:e17085, CC BY 4.0) was transcribed verbatim into
  `data/literature/external_lettuce_peerj17085.json` (six observations: two cultivars × three
  canopy levels, fresh weight at 28 DAT, source SHA-256 recorded) and served at
  `GET /api/external-validation` with predictions computed live rather than stored. The model
  overpredicts every observation, by ×1.67 to ×5.38, with a median of ×3.21 and a mean absolute
  percentage error of 232 %. Probing the one unmeasured input (root temperature, 20–32 °C) moves
  the median ratio only between ×2.28 and ×3.21, so the assumption does not explain the gap. The
  model stays exploratory: its R² describes interpolation within four experiments by one group and
  must not be read as transferable accuracy.
- Configure a managed database and explicit CORS policy before enabling hosted history writes.
  Live check 2026-11-09: database-backed routes were failing on the hosted instance (login 500,
  share links 503) while `/api/health` stayed green. URL aliases are now normalised and `/api/ready`
  reports a `reason` code; the remaining step is setting `SPACEAGRISIM_DATABASE_URL` on the host.
- Profile and split the large WebGL bundle further if field performance requires it.
