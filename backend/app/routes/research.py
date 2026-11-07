"""Scientific dataset/model endpoints; training is deliberately offline."""
import math
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import research, science_classification

router = APIRouter(tags=["scientific data and models"])


class HarvestPredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    crop: Literal["mizuna"] = "mizuna"
    waterSuppliedL: float = Field(ge=0, le=10)
    establishedPlants: int = Field(ge=0, le=10)
    environment: Literal["flight", "ground"]
    spectrum: Literal["red", "blue"]


class MolecularPredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    expression: dict[str, float] = Field(min_length=1, max_length=128, description="Exact artifact gene IDs, each normalized log1p(CPM), never raw counts")


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
    model=artifact('lettuce-earth-growth-v1')
    value, warnings=research.predict_values(model,[request.daysAfterTransplant,request.airTemperature,request.rootTemperature,request.ppfd])
    if request.airTemperature >= 28 and request.rootTemperature <= 24 and request.ppfd >= 400:
        warnings.append('Tip-burn treatment combinations were omitted in the published analysis; this region is unsupported.')
    radius=model['interval']['radius']
    return {'modelId':model['id'],'prediction':value,'unit':model['unit'],'method':model['method'],'sourceStudy':'WUR-lettuce','sourceUrl':model['sourceUrl'],'interval':{'low':max(0,value-radius),'high':value+radius,'kind':model['interval']['kind']},'outOfDistribution':bool(warnings),'warnings':warnings+model['limitations'],'inputs':request.model_dump()}


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
        "warnings": warnings + model["limitations"],
        "inputs": request.model_dump(),
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
        "warnings": warnings + [spec["caveat"]] + model.get("limitations", []),
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


@router.get("/datasets")
def datasets(q: str = ""):
    registered = research.manifest()
    rows = []
    for d in registered["datasets"]:
        searchable = d["id"] + " " + d["title"] + " " + " ".join(d.get("organisms", []))
        if q.lower() in searchable.lower():
            row = {k:v for k,v in d.items() if k != "files"}
            row["downloadedFileCount"] = sum(f.get("downloaded", False) for f in d.get("files", [])) + int("file" in d)
            rows.append(row)
    return {"datasets": rows, "source": registered.get("source"), "generatedAt": registered.get("generatedAt"), "coverage": research.coverage()}


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


@router.post("/predict/mizuna-harvest-v1")
def predict_harvest(request: HarvestPredictionRequest):
    model = artifact("mizuna-harvest-v1")
    value, warnings = research.predict_values(model, [request.waterSuppliedL, request.establishedPlants, int(request.environment == "flight"), int(request.spectrum == "blue")])
    if value < 0:
        warnings.append("Linear estimate was negative and clipped to zero; do not interpret as a supported operating condition.")
    value = max(0., value)
    radius = model["interval"]["radius"]
    return {"modelId": model["id"], "prediction": value, "unit": model["unit"], "method": model["method"], "sourceStudy": model["sourceStudy"], "interval": {"low": max(0., value-radius), "high": value+radius, "kind": model["interval"]["kind"]}, "outOfDistribution": bool(warnings), "warnings": warnings + model["limitations"], "inputs": request.model_dump()}


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
    return {"modelId": model["id"], "prediction": "flight" if probability >= .5 else "ground", "probabilityFlight": probability, "calibrated": False, "sourceStudy": model["sourceStudy"], "method": model["method"], "outOfDistribution": bool(warnings), "warnings": warnings + model["limitations"]}


# ---------------------------------------------------------------------------
# Phase 6: NASA OSD-780 edible-leaf microbial load
# ---------------------------------------------------------------------------
class MicrobialPredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    experiment: Literal["VEG04A", "VEG04B"] = Field(
        description="VEG-04 campaign; the model does not transfer across campaigns, so this is a required input")
    environment: Literal["flight", "ground"]
    spectrum: Literal["red", "blue"]
    sanitised: bool = Field(description="Sampled after sanitisation (clean) or before (unclean)")
    freshWeightG: float = Field(ge=0, le=50, description="Mass of the tissue subsample weighed for the assay, in grams. NOT harvest biomass.")
    harvestIndex: int = Field(ge=1, le=5, description="VEG-04B harvest number; 1 for VEG-04A")


@router.post(
    "/predict/mizuna-microbial-load-v1",
    deprecated=True,
    responses={410: {"description": "Retired as a predictive feature by the Phase 8 "
                                   "scientific integrity audit; see detail for evidence."}},
)
def predict_microbial(request: MicrobialPredictionRequest):
    """Retired: absolute leaf microbial load is not predictable for an unseen campaign.

    The Phase 6 artifact is retained and still registered, because deleting it would
    destroy the reproducibility of the reported result. What has been withdrawn is the
    *claim to predict*: leave-one-campaign-out R2 is -0.55 (VEG-04A held out) and -0.58
    (VEG-04B held out), i.e. worse than predicting the training mean, on both held-out
    campaigns. Phase 7 established that the campaign offset - not the flight/ground
    effect - is the component that fails to transfer.

    Phase 8's policy is that a surface whose only honest description is "worse than the
    mean" must not answer 200 with a number. It keeps request validation so that a
    malformed call still fails with 422, and returns 410 Gone with the measured
    evidence instead of a prediction.

    Use /predict/mizuna-microbial-relative-load-v2, which predicts the within-campaign
    standardised load (held-out R2 +0.444 / +0.373, permutation p = 0.000).
    """
    model = artifact("mizuna-microbial-load-v1")
    raise HTTPException(status_code=410, detail={
        "error": "retired-prediction",
        "modelId": model["id"],
        "reason": (
            "Absolute microbial load does not transfer to an unseen experiment; the "
            "model is worse than the training mean on both held-out campaigns."
        ),
        "evidence": {
            "leaveOneExperimentOutR2": {
                campaign: result.get("R2")
                for campaign, result in (model.get("leaveOneExperimentOut") or {}).items()
            },
            "transfersToHeldOutExperiment": bool(
                (model.get("evidenceBasis") or {}).get("transfersToHeldOutExperiment", False)),
        },
        "retainedFor": (
            "The registered artifact and its evaluation remain available via GET /api/models "
            "so the Phase 6/7 result stays reproducible."
        ),
        "replacement": "/api/predict/mizuna-microbial-relative-load-v2",
        "classification": "category 6 - unsupported scientific prediction",
    })


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
        "warnings": warnings + model["limitations"],
        "inputs": request.model_dump(),
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
