# SpaceAgriSim

SpaceAgriSim is an evidence-aware workspace for exploring controlled-environment crop scenarios for space habitats. It combines an explainable engineering simulator, a NASA OSDR catalogue and carefully scoped research models in one responsive web application.

![Mission Control](docs/screenshots/mission-desktop.png)

## What is implemented

- Mission dashboard, advanced laboratory controls, Earth/Moon/Mars comparison, crop explorer, NASA study explorer, analytics, advisor and methodology views.
- A FastAPI simulation API with bounded inputs, request guards, deterministic reports and optional scenario history.
- A verified NASA OSDR inventory (13 studies; 28 small acquired files with checksums), provenance and data-quality views.
- Offline-only model training and versioned artifacts. The application never trains a model from a browser request.
- An Earth-only lettuce fresh-mass model trained on licensed WUR/4TU data, explicitly kept separate from NASA and spaceflight evidence.
- A WebGL greenhouse with a usable 2D fallback, keyboard-accessible controls and responsive layouts.

## Evidence boundaries

The simulator is an assumption-driven decision-support prototype, not a calibrated mission digital twin. NASA metadata and source files are preserved with provenance, but most registered studies do not provide a compatible crop-yield calibration target. The mizuna research model is deliberately marked weak (grouped CV MAE 14.76; R2 -0.153), and the tomato artifact classifies recorded molecular flight context rather than crop health, stress or yield. The lettuce model is Earth-only and does not support claims about partial gravity, radiation, water stress or other cultivars.

See [scientific validation](docs/SCIENTIFIC_VALIDATION.md), [model evaluation](docs/MODEL_EVALUATION.md), [model limitations](docs/MODEL_LIMITATIONS.md), and the [dataset gap analysis](docs/DATASET_GAP_ANALYSIS.md) before using any result.

## Run locally

Requirements: Python 3.12+ and Node 20+.

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --reload
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api` to the backend.

## Verify

```powershell
backend/.venv/Scripts/python -m pytest -q backend/tests
cd frontend
npm run lint
npm run typecheck
npm run build
npm run test:e2e
```

The full verification record is in [docs/TEST_REPORT.md](docs/TEST_REPORT.md). For container and hosted deployment, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Data and attribution

NASA study records point to their official OSDR sources; the product is not endorsed by NASA. The mission dashboard's Earth image is NASA/NOAA/GSFC/Suomi NPP/VIIRS imagery, credited in [frontend/public/assets/ATTRIBUTION.md](frontend/public/assets/ATTRIBUTION.md). The external lettuce data are CC-BY-4.0 and retain their source and license in the model card.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API documentation](docs/API_DOCUMENTATION.md)
- [NASA dataset inventory](docs/NASA_DATASET_INVENTORY.md)
- [Data provenance](docs/DATA_PROVENANCE.md)
- [ML training report](docs/ML_TRAINING_REPORT.md)
- [Implementation progress](docs/IMPLEMENTATION_PROGRESS.md)
- [Phase 7 final report — NASA scientific completion](docs/PHASE7_FINAL_REPORT.md)
- [NASA measurement catalog](docs/NASA_MEASUREMENT_CATALOG.md)
- [Phase 7 ML training](docs/PHASE7_ML_TRAINING.md) · [evaluation](docs/PHASE7_ML_EVALUATION.md)
- [Phase 7 scientific calibration](docs/PHASE7_SCIENTIFIC_CALIBRATION.md)
- [Phase 7 PostgreSQL verification](docs/PHASE7_POSTGRESQL_VERIFICATION.md)
