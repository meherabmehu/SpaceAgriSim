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

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.simulation import SimulationRequest
from app.workflows import cea_evidence
from app.workflows import cea_export as cea_export_module
from app.workflows import light_stress, units, water_demand

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

    @model_validator(mode="after")
    def _band_belongs_to_the_factor(self):
        """A band id from a different factor is not a valid pair, and must not answer 200.

        `co2Ppm` has no `low` band. Both names are legal on their own, so the Literal types cannot
        catch the mismatch: the pair passed validation, the service skipped it, and the endpoint
        answered `200` with an empty group list - which a client cannot tell apart from a real band
        holding no experiments. The pairing is checked here so the request fails as what it is.
        """
        allowed = cea_evidence.band_ids(self.factor)
        if self.band not in allowed:
            raise ValueError(f"band {self.band!r} does not exist for {self.factor!r}; "
                             f"bands for this factor: {', '.join(allowed)}")
        return self


class CeaRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selections: list[CeaSelection] = Field(min_length=1, max_length=6)


class CeaExportRequest(BaseModel):
    """The same selection, plus what to render it as and the mission being looked at."""
    model_config = ConfigDict(extra="forbid")
    selections: list[CeaSelection] = Field(min_length=1, max_length=6)
    format: Literal["csv", "pdf"] = "csv"
    # Optional: the Mission Control configuration the user was comparing against, recorded in the
    # file so an export is self-describing. It is never simulated here - the file says so.
    configuration: SimulationRequest | None = None


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
    try:
        return cea_evidence.run(selections)
    except ValueError as error:
        # An unknown factor or band is a client mistake with a known set of answers, so it is a 422
        # that names them - not a 200 carrying an empty group that reads like a real empty band.
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/light-stress/controlled-environment/export")
def cea_export(request: CeaExportRequest) -> Response:
    """The selected measured group as a downloadable file.

    CSV by default because it opens anywhere and diffs; PDF for a file that needs no tool. Both are
    rendered from `cea_evidence.run`, the same call the JSON endpoint makes, so the file and the
    screen cannot disagree.
    """
    selections = [item.model_dump() for item in request.selections]
    try:
        payload, media_type, filename = cea_export_module.build(
            selections, request.format,
            request.configuration.model_dump() if request.configuration else None)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    headers = {"Content-Disposition": f'attachment; filename="{filename}"',
               "Cache-Control": "no-store"}
    if isinstance(payload, bytes):
        return Response(payload, media_type=media_type, headers=headers)
    return Response(payload, media_type=media_type, headers=headers)
