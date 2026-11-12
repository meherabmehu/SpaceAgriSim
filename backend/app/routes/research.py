"""Scientific dataset/model endpoints; training is deliberately offline."""
import math
from functools import lru_cache
from typing import Literal

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app import (acquisition_evidence, benchmarks, closed_loop, et0, external_validation,
                 research, science_classification, water_evidence)

router = APIRouter(tags=["scientific data and models"])


class WaterUseComparisonRequest(BaseModel):
    """A live simulation's water demand, held against the measured lettuce benchmark.

    Only three inputs are accepted because only three matter on the crop-relative demand path:
    the crop, the area the demand is spread over, and the light scale. Everything else in a full
    simulation request affects growth and gas exchange, not this equation - accepting them would
    imply an influence this comparison does not have.
    """
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    crop: Literal["lettuce", "tomato", "radish"] = "lettuce"
    growingAreaM2: float = Field(
        default=0.0112, gt=0, le=10_000,
        description=("Area the demand is spread over, in m2. The default is the single-pot area "
                     "assumption, which is what makes the comparison like-for-like with the "
                     "measurement."))
    lightScale: float = Field(
        default=1.0, gt=0, le=3.0,
        description=("The platform's light multiplier for the demand equation. 1.0 is the "
                     "reference the measurement is compared at."))


class MolecularPredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    expression: dict[str, float] = Field(min_length=1, max_length=128, description="Exact artifact gene IDs, each normalized log1p(CPM), never raw counts")


class LettuceYieldPredictionRequest(BaseModel):
    """v3 inputs: v2's four plus the two variables v2 had to assume."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    crop: Literal['lettuce'] = 'lettuce'
    daysAfterTransplant: float = Field(ge=0, le=60)
    airTemperature: float = Field(ge=5, le=40)
    rootTemperature: float = Field(ge=5, le=40)
    ppfd: float = Field(ge=0, le=1000)
    # The two variables every source reports and v2 silently assumed. Photoperiod distinguishes a
    # 16 h plant factory from a 12 h greenhouse at the same instantaneous flux; density converts
    # fresh yield per square metre into mass per plant.
    photoperiodHours: float = Field(default=16.0, gt=0, le=24)
    plantDensityPerM2: float = Field(default=25.0, gt=0, le=2000)


class LettucePredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    crop: Literal['lettuce'] = 'lettuce'
    daysAfterTransplant: float = Field(ge=0, le=60)
    airTemperature: float = Field(ge=5, le=40)
    rootTemperature: float = Field(ge=5, le=40)
    ppfd: float = Field(ge=0, le=1000)


@router.post(
    '/predict/lettuce-earth-growth-v1',
    deprecated=True,
    responses={200: {"description": "Still served for reproducibility; superseded by "
                                   "/predict/lettuce-earth-growth-v2, which was better on "
                                   "every held-out experiment."}},
)
def predict_lettuce(request: LettucePredictionRequest):
    """Superseded v1 regression. Kept served so its failed external check stays reproducible."""
    model = artifact("lettuce-earth-growth-v1")
    value, warnings = research.predict_values(model, [
        request.daysAfterTransplant, request.airTemperature,
        request.rootTemperature, request.ppfd])
    if request.airTemperature >= 28 and request.rootTemperature <= 24 and request.ppfd >= 400:
        warnings.append("Tip-burn treatment combinations were omitted in the published analysis; "
                        "this region is unsupported.")
    radius = model["interval"]["radius"]
    return {
        "modelId": model["id"],
        "prediction": value,
        "unit": model["unit"],
        "method": model["method"],
        "sourceStudy": "WUR-lettuce",
        "sourceUrl": model["sourceUrl"],
        "interval": {"low": max(0, value - radius), "high": value + radius,
                     "kind": model["interval"]["kind"]},
        "outOfDistribution": bool(warnings),
        "warnings": (warnings + model["limitations"]
                     + research.verdict_warning(model["id"], model)),
        "inputs": request.model_dump(),
        "operationalForecast": False,
        "harvestForecastClaim": None,
        "scopeStatement": model.get("servedScope"),
        **research.verdict_fields(model["id"], model),
    }


@router.post("/predict/lettuce-earth-growth-v3")
def predict_lettuce_v3(request: LettuceYieldPredictionRequest):
    """v3: fresh yield per square metre, divided by the density the caller states.

    v2 predicted mass per plant from PPFD alone and overpredicted an independent greenhouse trial
    by a median of 3.2x. Two reported variables were missing from its inputs: the photoperiod,
    which decides how much light a plant actually receives per day, and the planting density,
    which decides how much of a square metre's yield belongs to one plant. Both are inputs here.

    The model is still `trained-exploratory`: its independent holdout (Touliatos et al. 2016)
    error is 41.6% against a 30% criterion fixed in advance, and this response says so.
    """
    model = artifact("lettuce-earth-growth-v3")
    daily_light_integral = request.ppfd * request.photoperiodHours * 3600.0 / 1e6
    raw, warnings = research.predict_values(
        model, [request.daysAfterTransplant, request.airTemperature,
                request.rootTemperature, daily_light_integral])
    # The artifact is fitted on log(fresh yield per m2); left uninverted that is a plausible number
    # three orders of magnitude out, so the transform is declared and applied centrally.
    raw_per_area = research.inverse_target_transform(model, raw)
    per_area = max(0.0, raw_per_area)
    value = per_area / request.plantDensityPerM2

    # The per-area identity is known to break at very high densities, so refuse to extrapolate it.
    density_bounds = model["densityDomain"]["plantsPerM2"]
    if not density_bounds["min"] <= request.plantDensityPerM2 <= density_bounds["max"]:
        warnings.append(
            f"plantDensityPerM2 {request.plantDensityPerM2:g} outside the supported "
            f"[{density_bounds['min']:g}, {density_bounds['max']:g}] range: per-plant mass there "
            "extrapolates the density identity itself, not the fitted growth response.")

    # Conformal interval on the log target, carried through the same density division.
    low = per_area * math.exp(model["interval"]["logResidualLow"]) / request.plantDensityPerM2
    high = per_area * math.exp(model["interval"]["logResidualHigh"]) / request.plantDensityPerM2

    independent = (model.get("validation") or {}).get("independent") or {}
    development = (model.get("validation") or {}).get("development") or {}
    return {
        "modelId": model["id"],
        "prediction": round(value, 3),
        "unit": model["unit"],
        "method": model["method"],
        "sourceStudy": "WUR-lettuce",
        "sourceUrl": model["sourceUrl"],
        "derived": {
            "dailyLightIntegral": round(daily_light_integral, 2),
            "unit": "mol m-2 d-1",
            "formula": model["derivedFeatures"]["dailyLightIntegral"]["formula"],
        },
        "perAreaYieldGPerM2": round(per_area, 1),
        "densityUsedPlantsPerM2": request.plantDensityPerM2,
        "interval": {
            "low": round(max(0.0, low), 3),
            "high": round(high, 3),
            "kind": model["interval"]["kind"],
            "calibrated": False,
        },
        "validationStatus": {
            "status": model["status"],
            "independentCheck": {
                "study": independent.get("study"),
                "metrics": independent.get("metrics"),
                "acceptanceCriterionPct": independent.get("acceptanceCriterionPct"),
                "passed": independent.get("passed"),
                "verdict": independent.get("verdict"),
            },
            "developmentCheck": {
                "study": development.get("study"),
                "metrics": development.get("metrics"),
                "countsAsValidation": development.get("countsAsValidation"),
                "usedForModelSelection": development.get("usedForModelSelection"),
            },
            "comparedWithV2": {
                "v2DevelopmentMAPEPct": 232.2,
                "v3DevelopmentMAPEPct": (development.get("metrics") or {}).get("MAPE"),
                "note": ("Both scored on the same six PeerJ observations. v2's figure came first and "
                         "is what motivated v3; the comparison is reported so the improvement can "
                         "be checked rather than asserted."),
            },
        },
        "outOfDistribution": bool(warnings),
        "warnings": warnings + model["limitations"] + research.verdict_warning(model["id"], model),
        "inputs": request.model_dump(),
        # Phase 32: a prediction is served under a stated scope and never as an
        # operational forecast. These three fields are asserted by
        # backend/tests/test_phase32_no_forecast.py on every prediction route, so a
        # future handler cannot quietly reintroduce a harvest forecast claim.
        "operationalForecast": False,
        "harvestForecastClaim": None,
        "scopeStatement": model.get("servedScope"),
        # Phase 35: the evidence verdict travels with the number. `decisionGrade` is false for
        # every model that failed an independent check or was never checked independently, and the
        # warning list then carries the measured reason, so a caller cannot receive an
        # experimental estimate without its verdict attached.
        **research.verdict_fields(model["id"], model),
    }


@router.post("/predict/lettuce-earth-growth-v2")
def predict_lettuce_v2(request: LettucePredictionRequest):
    """Phase 8 successor to the Earth lettuce model: same data, better model class.

    Phase 7's own benchmark had already shown gradient boosting ahead of the random
    forest that was actually registered (R2 0.8699 vs 0.8131 on identical
    leave-one-experiment-out folds, and better MAE in all four held-out
    experiments), so the served model was the weaker of the two candidates it had
    measured. v2 ships the boosting model; v1 is kept, not overwritten, so the
    Phase 7 result stays reproducible.
    """
    model = artifact("lettuce-earth-growth-v2")
    raw, warnings = research.predict_values(
        model, [request.daysAfterTransplant, request.airTemperature,
                request.rootTemperature, request.ppfd])
    # Fresh mass cannot be negative. Boosted trees will cross zero just below the
    # measured range, so clamp and say so rather than returning a physical
    # impossibility.
    value = max(0.0, raw)
    clamped = value != raw
    if request.airTemperature >= 28 and request.rootTemperature <= 24 and request.ppfd >= 400:
        warnings.append("Tip-burn treatment combinations were omitted in the published "
                        "analysis; this region is unsupported.")
    radius = model["interval"]["radius"]
    selection = model.get("modelSelection") or {}
    return {
        "modelId": model["id"],
        "prediction": value,
        "unit": model["unit"],
        "method": model["method"],
        "sourceStudy": "WUR-lettuce",
        "sourceUrl": model["sourceUrl"],
        "supersedes": model.get("supersedes"),
        "interval": {"low": max(0.0, value - radius), "high": value + radius,
                     "kind": model["interval"]["kind"],
                     "calibrated": False},
        "outputClamped": clamped,
        "modelSelection": {
            "shipped": selection.get("shipped"),
            "comparedOnIdenticalFolds": selection.get("compared"),
            "note": selection.get("rule"),
        },
        "outOfDistribution": bool(warnings),
        "warnings": warnings + model["limitations"] + research.verdict_warning(model["id"], model),
        "inputs": request.model_dump(),
        # Phase 32: a prediction is served under a stated scope and never as an
        # operational forecast. These three fields are asserted by
        # backend/tests/test_phase32_no_forecast.py on every prediction route, so a
        # future handler cannot quietly reintroduce a harvest forecast claim.
        "operationalForecast": False,
        "harvestForecastClaim": None,
        "scopeStatement": model.get("servedScope"),
        # Phase 35: the evidence verdict travels with the number. `decisionGrade` is false for
        # every model that failed an independent check or was never checked independently, and the
        # warning list then carries the measured reason, so a caller cannot receive an
        # experimental estimate without its verdict attached.
        **research.verdict_fields(model["id"], model),
    }


class TranscriptomicPredictionRequest(BaseModel):
    """Expression profile for a transcriptomic classifier.

    `expression` must contain exactly the genes listed in the model artifact's
    `features`. Missing genes are rejected rather than zero-filled: a zero is a
    plausible measurement value, so silently substituting one would corrupt the
    prediction while looking like it worked.
    """
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    expression: dict[str, float] = Field(
        min_length=1, max_length=400,
        description="Gene model ID -> expression value, in the units named by the "
                    "artifact's expressionUnits field.")


TRANSCRIPTOMIC_MODELS = {
    "radiation-quality-osd46-v1": {
        "labels": {"control": "non-irradiated", "gamma": "100 Gy Cs-137 gamma",
                   "hze": "30 Gy Fe-56 ion (HZE)"},
        "caveat": ("Classifies the radiation condition applied before sampling in a "
                   "ground-based Arabidopsis study. It does not measure absorbed dose, "
                   "does not predict damage severity, and does not predict yield, "
                   "biomass or survival."),
    },
    "radiation-exposure-osd46-v1": {
        "labels": {"control": "non-irradiated", "irradiated": "irradiated"},
        "caveat": ("Separates irradiated from non-irradiated Arabidopsis seedlings. It "
                   "does not distinguish radiation quality or dose, and the control "
                   "class is not batch-balanced on the full array set - prefer the "
                   "batch-controlled evaluation reported in supplementaryEvaluation."),
    },
}


def _transcriptomic_prediction(model_id: str, request: TranscriptomicPredictionRequest):
    model = artifact(model_id)
    expected = model["features"]
    supplied = request.expression
    missing = [gene for gene in expected if gene not in supplied]
    unexpected = [gene for gene in supplied if gene not in model["features"]]
    if missing or unexpected:
        raise HTTPException(422, detail={
            "error": "expression-feature-mismatch",
            "missingGenes": missing[:20],
            "missingGeneCount": len(missing),
            "unexpectedGenes": unexpected[:20],
            "unexpectedGeneCount": len(unexpected),
            "requiredGeneCount": len(expected),
            "note": ("All genes in the artifact feature list must be supplied and no "
                     "others. Retrieve the full list from GET /api/models and use "
                     "GET /api/models/{id}/reference-profiles for a labelled synthetic "
                     "starting point."),
        })
    values = [supplied[gene] for gene in expected]
    probabilities = research.predict_probabilities(model, values)
    prediction = max(probabilities, key=probabilities.get)
    warnings = research._domain_warnings(model, values)
    spec = TRANSCRIPTOMIC_MODELS[model_id]
    metrics = model.get("metrics", {})
    return {
        "modelId": model["id"],
        "prediction": prediction,
        "predictionLabel": spec["labels"].get(prediction, prediction),
        "probabilities": {label: round(p, 6) for label, p in
                          sorted(probabilities.items(), key=lambda kv: -kv[1])},
        "classLabels": model["classLabels"],
        "classDescription": model.get("classDescription", {}),
        # Phase 32: a probability is only interpretable with its calibration attached, so the
        # measurement travels with the numbers. `calibrated: false` is the honest verdict for
        # these two classifiers; the block also carries what was measured, on how many
        # biological groups, and the scope it holds in.
        "probabilityCalibration": model.get("probabilityCalibration"),
        # Phase 32: no transcriptomic classifier here predicts harvest, yield or health; the
        # scope says so in the response rather than only in a document.
        "operationalForecast": False,
        "harvestForecastClaim": None,
        "scopeStatement": model.get("servedScope"),
        "unit": "class label",
        "sourceStudy": model["sourceStudy"],
        "sourceUrl": model["sourceUrl"],
        "evidenceStatus": model.get("evidenceStatus"),
        "validation": {
            "scheme": model.get("validation"),
            "accuracy": metrics.get("accuracy"),
            "balancedAccuracy": metrics.get("balancedAccuracy"),
            "macroF1": metrics.get("macroF1"),
            "baselineAccuracy": (model.get("baselineMetrics") or {}).get("accuracy"),
            "permutationPValue": (model.get("permutationTest") or {}).get("pValue"),
            "samples": model.get("samples"),
            "biologicalGroups": model.get("groups"),
        },
        # Full cross-tabulation, not just the scalar: a reader can then judge the
        # confound instead of being asked to trust one number.
        "batchConfound": model.get("batchConfound"),
        # Present only where the model publishes a confound-reduced re-evaluation.
        "supplementaryEvaluation": model.get("supplementaryEvaluation"),
        "interval": {"kind": "none", "calibrated": False,
                     "note": ("A softmax probability from an uncalibrated linear model "
                              "is not a confidence interval. It is reported as a "
                              "relative score between the trained classes only.")},
        "outOfDomain": bool(warnings),
        # Phase 35: these two classifiers have never been scored by an independent campaign, and the
        # verdict says so on every response rather than only in a document. `warnings` carries the
        # same sentence the other prediction routes emit, so no surface has to reconstruct it.
        **research.verdict_fields(model["id"], model),
        "warnings": (warnings + [spec["caveat"]] + model.get("limitations", [])
                     + research.verdict_warning(model["id"], model)),
        "inputsUsed": len(values),
    }


@router.post("/predict/radiation-quality-osd46-v1")
def predict_radiation_quality(request: TranscriptomicPredictionRequest):
    """Radiation quality (control / gamma / HZE) from Arabidopsis expression, OSD-46."""
    return _transcriptomic_prediction("radiation-quality-osd46-v1", request)


@router.post("/predict/radiation-exposure-osd46-v1")
def predict_radiation_exposure(request: TranscriptomicPredictionRequest):
    """Irradiated versus non-irradiated from Arabidopsis expression, OSD-46."""
    return _transcriptomic_prediction("radiation-exposure-osd46-v1", request)


@router.get("/reference-et0/estimate")
def reference_et0_estimate(
    tmaxC: float = Query(ge=-90.0, le=60.0, description="Daily maximum air temperature, degC"),
    tminC: float = Query(ge=-90.0, le=60.0, description="Daily minimum air temperature, degC"),
    latitude: float = Query(ge=-90.0, le=90.0, description="Site latitude, degrees"),
    elevationM: float = Query(default=0.0, ge=-500.0, le=6000.0, description="Site elevation, m"),
    dayOfYear: int | None = Query(default=None, ge=1, le=366),
    tdewC: float | None = Query(default=None, ge=-100.0, le=60.0,
                                description="Daily mean dew point, degC"),
    relativeHumidityPct: float | None = Query(default=None, ge=0.1, le=100.0,
                                              description="Daily mean RH, % (used if tdewC is absent)"),
    solarRadiationMJm2: float | None = Query(default=None, ge=0.0, le=50.0,
                                             description="Incoming shortwave radiation, MJ m^-2 d^-1"),
    windSpeedMs: float | None = Query(default=None, ge=0.0, le=70.0,
                                      description="Wind speed at 2 m, m s^-1"),
    pressureKpa: float | None = Query(default=None, ge=50.0, le=110.0,
                                      description="Surface pressure, kPa (optional)"),
):
    """Reference ET0 for one day, by the published method the supplied inputs allow.

    FAO-56 Penman-Monteith needs radiation and wind. When either is missing the endpoint does not
    guess and does not fall back to anything learned: it computes Hargreaves-Samani (temperature
    and latitude only), names it as the primary method, and reports which inputs were missing and
    why. The result is a computed standard, never a measured ET0.
    """
    if tdewC is None and relativeHumidityPct is None:
        raise HTTPException(status_code=422,
                            detail="supply either tdewC or relativeHumidityPct to define vapour pressure")
    resolved_day = dayOfYear if dayOfYear is not None else datetime.now(timezone.utc).timetuple().tm_yday
    try:
        return et0.estimate(
            tmax_c=tmaxC, tmin_c=tminC, day_of_year=resolved_day, latitude=latitude,
            elevation_m=elevationM, tdew_c=tdewC,
            relative_humidity_pct=relativeHumidityPct,
            solar_radiation_mj=solarRadiationMJm2, wind_speed_ms=windSpeedMs,
            pressure_kpa=pressureKpa) | {"dayOfYearSource": ("supplied" if dayOfYear is not None
                                                             else "current UTC day")}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


class ReferenceEt0Request(BaseModel):
    """A whole-day ET0 request, so an impossible day can be rejected as a *payload*.

    The estimate endpoint takes its weather as query parameters, which is right for a client
    fetching one day; it is the wrong shape for validating a day that has already been read from
    a file. This mirrors the same fields and calls the same published equations - it does not
    re-implement them, and it deliberately does not call the estimate route function (whose
    defaults are `Query` objects and would be passed through as sentinels).
    """
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    tmaxC: float = Field(ge=-90, le=60)
    tminC: float = Field(ge=-90, le=60)
    latitude: float = Field(ge=-90, le=90)
    dayOfYear: int = Field(ge=1, le=366)
    elevationM: float = Field(default=0.0, ge=-500, le=6000)
    tdewC: float | None = Field(default=None, ge=-100, le=60)
    relativeHumidityPct: float | None = Field(default=None, ge=0.1, le=100)
    solarRadiationMJm2: float | None = Field(default=None, ge=0, le=50)
    windSpeedMs: float | None = Field(default=None, ge=0, le=70)
    pressureKpa: float | None = Field(default=None, ge=50, le=110)


def _et0_payload(request: ReferenceEt0Request) -> dict:
    if request.tdewC is None and request.relativeHumidityPct is None:
        raise HTTPException(status_code=422,
                            detail="supply either tdewC or relativeHumidityPct to define vapour "
                                   "pressure")
    try:
        return et0.estimate(
            tmax_c=request.tmaxC, tmin_c=request.tminC, day_of_year=request.dayOfYear,
            latitude=request.latitude, elevation_m=request.elevationM, tdew_c=request.tdewC,
            relative_humidity_pct=request.relativeHumidityPct,
            solar_radiation_mj=request.solarRadiationMJm2,
            wind_speed_ms=request.windSpeedMs, pressure_kpa=request.pressureKpa)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/reference-et0/validate")
def reference_et0_validate(
    tmaxC: float = Query(ge=-90.0, le=60.0),
    tminC: float = Query(ge=-90.0, le=60.0),
    latitude: float = Query(ge=-90.0, le=90.0),
    dayOfYear: int | None = Query(default=None, ge=1, le=366),
    elevationM: float = Query(default=0.0, ge=-500.0, le=6000.0),
    tdewC: float | None = Query(default=None, ge=-100.0, le=60.0),
    relativeHumidityPct: float | None = Query(default=None, ge=0.1, le=100.0),
    solarRadiationMJm2: float | None = Query(default=None, ge=0.0, le=50.0),
    windSpeedMs: float | None = Query(default=None, ge=0.0, le=70.0),
    pressureKpa: float | None = Query(default=None, ge=50.0, le=110.0),
):
    """Compute reference ET0 and answer the question the number cannot answer itself.

    A bad day - swapped temperatures, a solar flux for another planet - still produces a number
    out of any equation. This endpoint returns the value alongside `outputCheck`, which states
    whether the result is physically plausible and, when it is not, which rule it broke. The
    value is never clamped: a corrected number would hide the input error.
    """
    request = ReferenceEt0Request(
        tmaxC=tmaxC, tminC=tminC, latitude=latitude,
        dayOfYear=dayOfYear or datetime.now(timezone.utc).timetuple().tm_yday,
        elevationM=elevationM, tdewC=tdewC, relativeHumidityPct=relativeHumidityPct,
        solarRadiationMJm2=solarRadiationMJm2, windSpeedMs=windSpeedMs,
        pressureKpa=pressureKpa)
    payload = _et0_payload(request)
    payload["validatedInputs"] = request.model_dump()
    return payload


@router.post("/reference-et0/validate")
def reference_et0_validate_body(request: ReferenceEt0Request):
    """The same check for a whole day supplied as a payload, so a batch can be validated."""
    payload = _et0_payload(request)
    payload["validatedInputs"] = request.model_dump()
    return payload


@router.get("/reference-et0/model")
def reference_et0_model():
    """The model card for the served ET0 calculation.

    Phase 31 removed the fitted ET0 surrogate from the served pathway and replaced this card with
    the physics: the standard, the inputs each method needs, the FAO-56 worked examples recomputed
    on this call, and an explicit statement that no measured-ET0 benchmark is bundled.
    """
    return et0.physics_status() | {
        "servedAt": "/api/reference-et0/estimate",
        "waterDemand": ("POST /api/simulate accepts et0MmPerDay and cropCoefficient and reports "
                        "demandBasis"),
        "provenance": {
            "standard": "FAO-56 chapter 4 (Allen et al., 1998), eq. 6",
            "hargreaves": "Hargreaves & Samani (1985), temperature-based ET0",
            "weatherInputs": ("Supplied by the caller and typically NASA POWER community AG "
                              "reanalysis; reanalysis is not a station measurement."),
            "weatherLicense": "NASA POWER: no restrictions, citation requested",
            "workedExamples": "app.simulation.et0_fao56.run_published_examples(), asserted in tests",
        },
    }


@router.get("/models/{model_id}/explanation")
def model_explanation(model_id: str):
    """Exact attribution for a model that can carry one, with its stated limits.

    Returns 404 rather than a stub for models where no valid explanation method
    exists. A surrogate fitted to mimic a tree ensemble would produce a plausible
    table that is not of the model being served, which is the failure mode this
    endpoint is designed to avoid.
    """
    if model_id not in research.MODEL_IDS:
        raise HTTPException(404, "Unknown model")
    try:
        report = research.explanation(model_id)
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc
    if report is None:
        raise HTTPException(404, "No valid explanation method is implemented for this model")
    return {
        "modelId": report["modelId"],
        "method": report["method"],
        "notASurrogate": report["notASurrogate"],
        "identityResidual": report["identityResidual"],
        "explainedInput": report["explainedInput"],
        "perClass": report["perClass"],
        "selectionStability": report["selectionStability"],
        "permutationImportance": report["permutationImportance"],
        "singleGeneDependence": report.get("singleGeneDependence"),
        "selectionLeakageNote": report.get("selectionLeakageNote"),
        "binaryEncodingNote": report.get("binaryEncodingNote"),
        "interpretationLimits": report["interpretationLimits"],
        "generatedAt": report["generatedAt"],
    }


@router.get("/models/{model_id}/reference-profiles")
def reference_profiles(model_id: str):
    """Per-class mean expression profiles for a transcriptomic model.

    These are **class centroids computed from the NASA training data**, not
    individual measured specimens, and any prediction made from one is a synthetic
    demonstration. That is stated in the payload as well as here, because a demo
    that looks like a real specimen would be exactly the kind of quiet
    overstatement Phase 8 spent its time removing.
    """
    model = artifact(model_id)
    profiles = model.get("referenceProfiles")
    if not profiles:
        raise HTTPException(404, "No reference profiles are stored for this model")
    spec = TRANSCRIPTOMIC_MODELS.get(model_id, {})
    return {
        "modelId": model["id"],
        "synthetic": True,
        "label": "synthetic input - class centroid of the training data, not a measured sample",
        "note": model.get("referenceProfilesNote"),
        "expressionUnits": model.get("expressionUnits"),
        "requiredGeneCount": len(model["features"]),
        "features": model["features"],
        "classLabels": model["classLabels"],
        "classDescription": spec.get("labels", {}),
        "usage": ("profiles[class][i] is the value for features[i]. Build an "
                  "expression dict by zipping features with a profile."),
        "profiles": profiles,
    }


def dataset(study_id):
    found = next((d for d in research.manifest()["datasets"] if d["id"] == study_id.upper()), None)
    if found is None:
        raise HTTPException(404, "Study not registered")
    return found


def artifact(model_id):
    try:
        return research.load_model(model_id)
    except KeyError as exc:
        raise HTTPException(404, "Unknown model") from exc
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(503, "Verified model artifact unavailable; offline training required") from exc


# The dataset index is rebuilt from the manifest on every request in the Phase 12 code. With 34
# studies and per-row string assembly that measured 17 ms per call locally, against ~3.5 ms of
# request overhead - i.e. almost all of the cost was the rebuild. Caching the assembled rows per
# query string keeps the response identical (the rows are only read, never mutated, and the
# manifest itself is already cached) and removes the repeat work. Cache key is the query alone.
@lru_cache(maxsize=64)
def _dataset_rows(q: str) -> tuple[dict, ...]:
    registered = research.manifest()
    rows = []
    for d in registered["datasets"]:
        searchable = d["id"] + " " + d["title"] + " " + " ".join(d.get("organisms", []))
        if q.lower() in searchable.lower():
            row = {k:v for k,v in d.items() if k != "files"}
            row["downloadedFileCount"] = sum(f.get("downloaded", False) for f in d.get("files", [])) + int("file" in d)
            # Additive duplicate safeguards: a client that counts accessions must be able to
            # see that one of them does not count as an independent study.
            from app import explorer as _explorer  # local import: keeps import order simple
            redundant = _explorer.REDUNDANT_DEPOSITS.get(d["id"])
            row["countsAsIndependentStudy"] = redundant is None
            row["redundantWith"] = (redundant or {}).get("redundantWith")
            rows.append(row)
    return tuple(rows)


@router.get("/datasets")
def datasets(q: str = ""):
    registered = research.manifest()
    return {"datasets": list(_dataset_rows(q)), "source": registered.get("source"),
            "generatedAt": registered.get("generatedAt"), "coverage": research.coverage()}


@router.get("/closed-loop")
def closed_loop_measurements():
    """Measured ethylene production and dose response, and ISS water recovery."""
    return closed_loop.payload()


@router.get("/external-validation")
def external_validation_status():
    """Which external sources could validate the lettuce model, and why none does yet."""
    return external_validation.payload()


@router.get("/benchmarks")
def benchmark_panel():
    """Measured NASA anchors held against the simulator, with the caveats attached."""
    return benchmarks.payload()


@router.get("/water-use-evidence")
def water_use_evidence():
    """The measured crop water-use benchmark, its provenance and its limits.

    This is the evidence behind the water feature. It is served as a benchmark, not a
    calibration: `isValidation` is false everywhere it appears, and the limitations travel with
    the numbers instead of living in a separate document nobody opens.
    """
    return water_evidence.benchmark()


@router.post("/water-use-evidence/compare")
def water_use_comparison(request: WaterUseComparisonRequest):
    """Hold the shipped demand equation against the measured benchmark.

    Never returns `validated`. The study publishes neither pot geometry nor per-day weather, so
    the level cannot be identified from it and the simulator is left untouched.
    """
    try:
        return water_evidence.compare(request.crop, request.lightScale, request.growingAreaM2)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/datasets/live-status")
def dataset_live_status():
    """When the pinned OSDR files were last re-checked against the live repository."""
    return research.osdr_live_status()


@router.get("/datasets/{study_id}/preview")
def dataset_preview(study_id: str):
    dataset(study_id)
    return research.preview(study_id.upper())


@router.get("/datasets/{study_id}")
def dataset_detail(study_id: str):
    return dataset(study_id)


@router.get("/provenance")
def provenance():
    return {"coverage": research.coverage(), "checksums": research.read_json(research.DATA / "metadata" / "download_checksums.json") if (research.DATA / "metadata" / "download_checksums.json").exists() else [], "quality": research.read_json(research.DATA / "metadata" / "quality_report.json") if (research.DATA / "metadata" / "quality_report.json").exists() else {}, "termsUrl": "https://science.nasa.gov/reference/osdr-help-terms-and-conditions/"}


@router.get("/models")
def models():
    return research.model_registry()


@router.get('/external-datasets')
def external_datasets():
    path=research.DATA/'metadata/external_lettuce.json'
    return {'datasets':[research.read_json(path)] if path.exists() else [],'note':'External scientific sources; separate from NASA study registry.'}


# Phase 31 removed POST /api/predict/mizuna-harvest-v1. Held-out R2 was -0.333 against a
# baseline of -0.138, i.e. the model was worse than predicting the training mean, on 14
# samples from a single experiment. It was still reachable as a live form in the UI, so
# the route, the form and the guided workflow were removed together rather than left
# behind an error. The artifact and its evaluation remain as a recorded negative result.


@router.get("/models/tomato-flight-response-v1/example")
def molecular_example():
    artifact("tomato-flight-response-v1")
    return research.read_json(research.ARTIFACTS / "tomato_example.json")


@router.post("/predict/tomato-flight-response-v1")
def predict_molecular(request: MolecularPredictionRequest):
    model = artifact("tomato-flight-response-v1")
    if set(request.expression) != set(model["features"]):
        raise HTTPException(422, "Expression must include exactly the model's gene IDs; GET /api/models for schema. Supply normalized log1p(CPM), not raw counts.")
    values = [request.expression[g] for g in model["features"]]
    if any(not 0 <= v <= 20 for v in values):
        raise HTTPException(422, "Each gene must be finite normalized log1p(CPM) between 0 and 20")
    logit, warnings = research.predict_values(model, values)
    probability = 1 / (1 + math.exp(-max(-700, min(700, logit))))
    return {"modelId": model["id"], "prediction": "flight" if probability >= .5 else "ground", "probabilityFlight": probability, "calibrated": False, "sourceStudy": model["sourceStudy"], "method": model["method"], "outOfDistribution": bool(warnings), "warnings": warnings + model["limitations"] + research.verdict_warning(model["id"], model), **research.verdict_fields(model["id"], model)}


# ---------------------------------------------------------------------------
# Phase 7: NASA OSD-780 edible-leaf microbial load (within-campaign relative)
#
# Phase 31 removed the absolute-load surface entirely: no route, no request model,
# no catalogue entry, no workflow input family. The artifact and its evaluation
# remain in ml/artifacts and ml/evaluation as a documented negative result.
# ---------------------------------------------------------------------------
class MicrobialRelativePredictionRequest(BaseModel):
    """Inputs for the Phase 7 re-scoped microbial model.

    Note what is absent: the experiment/campaign identity. After within-campaign
    standardisation that feature would be collinear with the offset the model
    deliberately does not attempt to predict.
    """
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    environment: Literal["flight", "ground"]
    spectrum: Literal["red", "blue"]
    sanitised: bool = Field(description="Sampled after sanitisation (clean) or before (unclean)")
    freshWeightG: float = Field(ge=0, le=50, description="Mass of the tissue subsample weighed for the assay, in grams. NOT harvest biomass.")
    harvestIndex: int = Field(ge=1, le=5, description="VEG-04B harvest number; 1 for VEG-04A")
    campaignReference: Literal["VEG04A", "VEG04B"] | None = Field(
        default=None,
        description=("Optional. Supplying a campaign reference converts the relative "
                     "prediction to an absolute log10 CFU/g using that campaign's own "
                     "measured mean and sd. Without it the response stays relative."))


@router.post("/predict/mizuna-microbial-relative-load-v2")
def predict_microbial_relative(request: MicrobialRelativePredictionRequest):
    """Phase 7 model: within-campaign relative microbial load.

    Returns a value in within-campaign standard deviations. An absolute log10
    CFU/g figure is returned ONLY when the caller supplies a campaign reference,
    because the campaign offset is exactly the quantity Phase 7 showed does not
    transfer between campaigns.
    """
    model = artifact("mizuna-microbial-relative-load-v2")
    values = [
        int(request.environment == "flight"),
        int(request.spectrum == "blue"),
        int(request.sanitised),
        request.harvestIndex,
        math.log10(max(request.freshWeightG, 0.01)),
    ]
    value, warnings = research.predict_values(model, values)
    radius = model["interval"]["radius"]
    calibrated = bool(model["interval"].get("empiricallyCalibrated", False))

    payload = {
        "modelId": model["id"],
        "supersedes": model.get("supersedes"),
        "prediction": value,
        "unit": model["unit"],
        "method": model["method"],
        "sourceStudy": model["sourceStudy"],
        "sourceUrl": model["sourceUrl"],
        "evidenceStatus": model.get("evidenceStatus", "experimental"),
        "estimandChange": model.get("estimandChange"),
        "interval": {
            "low": value - radius,
            "high": value + radius,
            "kind": model["interval"]["kind"],
            "calibrated": calibrated,
            "empiricalCoverage": model["interval"].get("empiricalCoverage"),
            "nominalCoverage": model["interval"].get("nominalCoverage"),
        },
        "transfer": {
            "perCampaignR2": (model.get("transferSummary") or {}).get("v2HeldOutR2"),
            "v1PerCampaignR2": (model.get("transferSummary") or {}).get("v1HeldOutR2"),
            "permutationTest": (model.get("transferSummary") or {}).get("permutationTest"),
            "positiveOnEveryHeldOutCampaign": bool(
                (model.get("evidenceBasis") or {}).get("positiveR2OnEveryHeldOutCampaign", False)),
        },
        "measuredEffect": model.get("measuredEffect"),
        "absoluteScale": {
            "supplied": request.campaignReference is not None,
            "protocol": model.get("absoluteScaleProtocol", {}).get("required"),
            "formula": model.get("absoluteScaleProtocol", {}).get("formula"),
            "refused": model.get("absoluteScaleProtocol", {}).get("refused"),
        },
        "outOfDistribution": bool(warnings),
        "warnings": warnings + model["limitations"] + research.verdict_warning(model["id"], model),
        "inputs": request.model_dump(),
        # Phase 32: a prediction is served under a stated scope and never as an
        # operational forecast. These three fields are asserted by
        # backend/tests/test_phase32_no_forecast.py on every prediction route, so a
        # future handler cannot quietly reintroduce a harvest forecast claim.
        "operationalForecast": False,
        "harvestForecastClaim": None,
        "scopeStatement": model.get("servedScope"),
        # Phase 35: the evidence verdict travels with the number. `decisionGrade` is false for
        # every model that failed an independent check or was never checked independently, and the
        # warning list then carries the measured reason, so a caller cannot receive an
        # experimental estimate without its verdict attached.
        **research.verdict_fields(model["id"], model),
    }
    if request.campaignReference is None:
        payload["absoluteScale"]["note"] = (
            "No campaign reference supplied, so no absolute log10 CFU/g figure is "
            "offered. Add campaignReference to get one derived from that campaign's "
            "own measured baseline."
        )
    else:
        reference = (model.get("absoluteScaleProtocol", {})
                     .get("campaignReference", {}).get(request.campaignReference, {}))
        mean, sd = reference.get("mean"), reference.get("sd")
        if mean is not None and sd is not None:
            absolute = mean + value * sd
            payload["absoluteScale"].update({
                "campaign": request.campaignReference,
                "campaignMean": mean,
                "campaignSd": sd,
                "log10CfuPerG": absolute,
                "log10CfuPerGRange": [mean + (value - radius) * sd,
                                      mean + (value + radius) * sd],
                "caveat": ("Derived from a reference campaign, not predicted for a new "
                           "one. The interval inherits the model's uncalibrated 90 % "
                           "residual radius."),
            })
        else:
            payload["absoluteScale"]["note"] = "Campaign reference not present in the artifact."
    return payload


# ---------------------------------------------------------------------------
# Phase 7: measurement recovery surface
# ---------------------------------------------------------------------------
@router.get("/science/measurements")
def science_measurements():
    """What NASA actually measured, with status and training eligibility.

    Targets rated `insufficient` are listed as prominently as the measured ones:
    the point of the catalog is to make an absence as visible as a presence.
    """
    return research.measurement_catalog()


@router.get("/science/checksums")
def science_checksums():
    """SHA-256 for every Phase 7 source document and model artifact."""
    return research.source_checksums()


# ---------------------------------------------------------------------------
# Phase 6: scientific evidence surface
# ---------------------------------------------------------------------------
@router.get("/science/calibration")
def science_calibration():
    return research.calibration()


@router.get("/science/evidence")
def science_evidence():
    return research.evidence_summary()


@router.get("/science/classification")
def science_classification_of_features():
    """Every prediction surface classified against the Phase 8 evidence policy.

    Phase 8 requires that no feature claim more support than the measurements
    behind it. The classification is served rather than filed so the claim can be
    checked against the running system, not only against a document.
    """
    return science_classification.classifier_response()


@router.get("/acquisition-evidence")
def acquisition_evidence_surface():
    """What Phase 36 acquired, what it proved, and what it did not.

    Every value carries the label that says whether it is measured, derived or predicted, because
    the three are mixed on this surface by necessity and would be indistinguishable without it. The
    six gaps that remain open are returned with the same prominence as the four that closed, and
    the payload ends with the count that did not move: no model became decision-grade.
    """
    return acquisition_evidence.payload()


@router.get("/scientific-summary")
def scientific_summary():
    """Deliberately blunt machine-readable statement of platform maturity.

    This endpoint exists so no downstream consumer has to infer how strong the
    evidence is from prose.
    """
    registry = research.model_registry()["models"]
    calibration = research.calibration()
    return {
        "platformMaturity": "research-and-education",
        "nasaEndorsed": False,
        "missionCertified": False,
        "models": [
            {
                "id": m["id"],
                "evidenceStatus": m.get("predictionStatus"),
                "sourceStudy": m.get("sourceStudy"),
                "samples": m.get("samples"),
                "groups": m.get("groups"),
                "beatsBaseline": (m.get("baselineComparison") or {}).get("outperformsBaselineMAE"),
                "artifactVerified": m.get("artifactExists"),
            }
            for m in registry
        ],
        "calibration": {
            "status": calibration.get("status"),
            "invariantsAllPassed": (calibration.get("invariants") or {}).get("allPassed"),
            "invariantsChecks": (calibration.get("invariants") or {}).get("checksRun"),
        },
        "validatedModels": [m["id"] for m in registry if m.get("predictionStatus") == "validated"],
        "note": (
            "No model in this repository is validated for operational or mission "
            "use. Simulation outputs are transparent mechanistic estimates with "
            "explicitly labelled assumptions; they are not NASA-validated growth "
            "predictions."
        ),
    }
