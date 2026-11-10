"""Phase 28: two complete, self-contained scientific workflows.

These routes exist so a user never has to know a model id, an input schema or an endpoint name.
Each workflow publishes its own capability document (fields, units, ranges, why each control
matters) and then runs the whole envelope in one call: validate, compute, compare, attach
uncertainty, attach evidence, attach limitations.

They sit alongside — not on top of — `/api/workflow/*`. That surface runs a single model for a
caller who already knows which model it wants. This one runs a *journey*.

Nothing here is authenticated. Both workflows only execute served models, artefacts and committed
tables, exactly like the existing public prediction endpoints, and neither stores anything. A
visitor can reproduce every number; persisting a run belongs to `/api/analyses`, which has accounts.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.workflows import harvest, units, water_demand

router = APIRouter(tags=["workflows"], prefix="/workflows")

MAX_SCENARIOS = 4


class WaterScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    label: str | None = Field(default=None, max_length=60)
    crop: Literal["lettuce", "tomato", "radish"]
    growingAreaM2: float = Field(gt=0, le=10_000)
    daysAfterTransplant: float = Field(ge=0, le=365)
    tmaxC: float = Field(ge=-40, le=60)
    tminC: float = Field(ge=-50, le=55)
    relativeHumidityPct: float = Field(ge=1, le=100)
    solarRadiationMJm2: float | None = Field(default=None, ge=0, le=60)
    windSpeedMs: float | None = Field(default=None, ge=0, le=40)
    dayOfYear: int = Field(ge=1, le=366)
    latitude: float = Field(ge=-90, le=90)
    elevationM: float = Field(ge=-500, le=9000)
    plantsPerM2: float | None = Field(default=None, gt=0, le=2000)
    cropCoefficient: float | None = Field(default=None, gt=0.05, le=2.0)


class WaterRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenarios: list[WaterScenario] = Field(min_length=1, max_length=MAX_SCENARIOS)


class HarvestScenario(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    label: str | None = Field(default=None, max_length=60)
    daysAfterTransplant: float = Field(ge=0, le=60)
    airTemperature: float = Field(ge=5, le=40)
    rootTemperature: float = Field(ge=5, le=40)
    ppfd: float = Field(ge=0, le=1000)
    photoperiodHours: float = Field(default=16.0, gt=0, le=24)
    plantDensityPerM2: float = Field(default=25.0, gt=0, le=2000)


class HarvestRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenarios: list[HarvestScenario] = Field(min_length=1, max_length=MAX_SCENARIOS)


@router.get("")
def workflow_catalogue() -> dict[str, Any]:
    """Which workflows exist, and what each one's honest completion status is."""
    return {
        "workflows": [
            {
                "id": "water-demand",
                "title": "Water demand and irrigation intelligence",
                "status": "complete",
                "measures": "daily crop water demand in litres, at the plant, the square metre "
                            "and the cycle",
                "measuredEvidence": True,
                "endpoints": {
                    "capability": "GET /api/workflows/water-demand/capability",
                    "run": "POST /api/workflows/water-demand/run",
                },
            },
            {
                "id": "harvest-prediction",
                "title": "Crop growth and harvest prediction (lettuce)",
                "status": "complete",
                "modelStatus": "trained-exploratory",
                "modelValidatedForForecasting": False,
                "measures": "fresh shoot mass per plant and fresh yield per square metre",
                "measuredEvidence": True,
                "endpoints": {
                    "capability": "GET /api/workflows/harvest-prediction/capability",
                    "run": "POST /api/workflows/harvest-prediction/run",
                    "parity": "GET /api/workflows/harvest-prediction/parity",
                },
            },
        ],
        "documentedGaps": [
            {
                "id": "environmental-stress",
                "status": "not-complete",
                "blocker": ("No validated response surface for light spectrum, CO2 or irradiance "
                            "stress exists in the repository. The simulator moves a warning string "
                            "for those controls, not an outcome, so a workflow built on them would "
                            "present an assumption as a simulation."),
            },
        ],
        "note": ("A workflow is listed complete only when input, execution, comparison, evidence, "
                 "uncertainty and interface are all implemented and tested. Two are. The third "
                 "candidate is blocked on evidence, not on engineering effort."),
    }


@router.get("/units")
def unit_registry() -> dict[str, Any]:
    """Every unit the workflows name, with its dimension. Nothing here converts."""
    return units.registry()


@router.get("/water-demand/capability")
def water_capability() -> dict[str, Any]:
    return water_demand.capability()


@router.post("/water-demand/run")
def water_run(request: WaterRunRequest) -> dict[str, Any]:
    scenarios = [item.model_dump() for item in request.scenarios]
    try:
        return water_demand.compare(scenarios)
    except KeyError as error:  # unsupported crop cannot reach here: Literal validates it
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/harvest-prediction/capability")
def harvest_capability() -> dict[str, Any]:
    return harvest.capability()


@router.get("/harvest-prediction/parity")
def harvest_parity() -> dict[str, Any]:
    return harvest.parity()


@router.post("/harvest-prediction/run")
def harvest_run(request: HarvestRunRequest) -> dict[str, Any]:
    scenarios = [item.model_dump() for item in request.scenarios]
    try:
        return harvest.compare(scenarios)
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
