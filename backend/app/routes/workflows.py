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

from app.workflows import cea_evidence, light_stress, units, water_demand

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
    # ---- Phase 29: irrigation scheduling. All optional; the workflow is complete without them.
    totalAvailableWaterMm: float | None = Field(default=None, gt=0, le=400)
    initialDepletionMm: float | None = Field(default=None, ge=0, le=400)
    irrigationAmountMm: float | None = Field(default=None, ge=0, le=200)
    irrigationIntervalDays: int | None = Field(default=None, ge=1, le=30)


class WaterRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenarios: list[WaterScenario] = Field(min_length=1, max_length=MAX_SCENARIOS)


class LightStressScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str | None = Field(default=None, max_length=60)
    regime: Literal["control", "t1", "t2", "t3"]
    traits: list[str] | None = Field(default=None, max_length=12)
    daysAfterSowing: Literal[28, 35] | None = Field(default=None)


class LightStressRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenarios: list[LightStressScenario] = Field(min_length=1, max_length=MAX_SCENARIOS)


class CeaSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    factor: Literal["ppfdUmolPerM2S", "photoperiodHours", "co2Ppm", "airTemperatureC"]
    band: Literal["low", "mid", "high", "short", "standard", "long", "ambient", "enriched",
                  "cool", "warm"]


class CeaRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selections: list[CeaSelection] = Field(min_length=1, max_length=6)


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
                "id": "light-stress",
                "title": "Environmental stress and growth response under light quality (measured)",
                "status": "complete",
                "evidenceClass": "measured-observation",
                "measures": "measured growth traits and photophysiological stress indicators across "
                            "four spectral regimes",
                "measuredEvidence": True,
                "isSimulation": False,
                "endpoints": {
                    "capability": "GET /api/workflows/light-stress/capability",
                    "run": "POST /api/workflows/light-stress/run",
                },
            },
        ],
        "documentedGaps": [
            {
                "id": "environmental-stress-response-surface",
                "status": "not-complete",
                "blocker": ("A measured light-quality comparison now ships (workflow light-stress), "
                            "but no validated *response surface* exists for CO2, PPFD or "
                            "temperature stress in this repository: no controlled-environment "
                            "dataset here varies those factors with measured biomass outcomes at "
                            "three or more levels. CO2 in particular has no measured contrast "
                            "anywhere in the catalogue."),
                "whatWouldUnblockIt": ("A factorial controlled-environment experiment varying PPFD "
                                       "and/or CO2 at three or more levels with per-plant biomass "
                                       "and reported photoperiod, temperature and density."),
            },
        ],
        "note": ("A workflow is listed only when input, execution, comparison, evidence, "
                 "uncertainty and interface are all implemented and tested; anything else is a "
                 "documented gap rather than a placeholder entry. Three workflows meet that bar: "
                 "two model/calculation workflows and one measured-comparison workflow whose "
                 "evidence class is stated in every response. Phase 31 removed the "
                 "harvest-prediction entry: a workflow with no run path is not a workflow, and the "
                 "evaluations that failed it remain committed under ml/evaluation and in docs. The "
                 "response surface that Phase 28 recorded as blocked is still blocked, and the "
                 "reason is below."),
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


@router.get("/light-stress/capability")
def light_stress_capability() -> dict[str, Any]:
    return light_stress.capability()


@router.post("/light-stress/run")
def light_stress_run(request: LightStressRunRequest) -> dict[str, Any]:
    scenarios = [item.model_dump() for item in request.scenarios]
    try:
        return light_stress.compare(scenarios)
    except KeyError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/light-stress/controlled-environment/capability")
def cea_capability() -> dict[str, Any]:
    return cea_evidence.capability()


@router.post("/light-stress/controlled-environment/run")
def cea_run(request: CeaRunRequest) -> dict[str, Any]:
    selections = [item.model_dump() for item in request.selections]
    return cea_evidence.run(selections)
