"""Scientific dataset/model endpoints; training is deliberately offline."""
import math
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app import research

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


@router.post('/predict/lettuce-earth-growth-v1')
def predict_lettuce(request: LettucePredictionRequest):
    model=artifact('lettuce-earth-growth-v1')
    value, warnings=research.predict_values(model,[request.daysAfterTransplant,request.airTemperature,request.rootTemperature,request.ppfd])
    if request.airTemperature >= 28 and request.rootTemperature <= 24 and request.ppfd >= 400:
        warnings.append('Tip-burn treatment combinations were omitted in the published analysis; this region is unsupported.')
    radius=model['interval']['radius']
    return {'modelId':model['id'],'prediction':value,'unit':model['unit'],'method':model['method'],'sourceStudy':'WUR-lettuce','sourceUrl':model['sourceUrl'],'interval':{'low':max(0,value-radius),'high':value+radius,'kind':model['interval']['kind']},'outOfDistribution':bool(warnings),'warnings':warnings+model['limitations'],'inputs':request.model_dump()}


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
    rows = [{k:v for k,v in d.items() if k != "files"} | {"downloadedFileCount": sum(f["downloaded"] for f in d["files"])} for d in registered["datasets"] if q.lower() in (d["id"] + " " + d["title"] + " " + " ".join(d["organisms"])).lower()]
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
