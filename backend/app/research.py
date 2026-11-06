"""Read-only scientific registry and safe, dependency-free JSON model inference."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = Path(__file__).resolve().parents[1] / 'scientific_data'
DATA = (BUNDLE if BUNDLE.exists() else ROOT) / "data"
ARTIFACTS = (BUNDLE if BUNDLE.exists() else ROOT) / "ml" / "artifacts"
MODEL_IDS = {"mizuna-harvest-v1", "tomato-flight-response-v1", "lettuce-earth-growth-v1"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def manifest():
    path = DATA / "metadata" / "dataset_manifest.json"
    return read_json(path) if path.is_file() else {"datasets": [], "status": "not-acquired"}


def coverage():
    return [
        {"feature": name, "status": status, "source": source, "method": method, "limitation": limitation}
        for name, status, source, method, limitation in [
            ("Plant growth", "NASA data available only as aggregated experimental results", "NASA BPC literature; external WUR lettuce endpoints (not NASA)", "Assumption-based habitat simulator; separate external Earth-only model", "No matched space-habitat growth time series acquired for lettuce/tomato/radish."),
            ("Biomass", "Direct NASA training data available", "OSD-655 VEG04A", "Exploratory mizuna regression only", "14 harvested pillow endpoints; retrospective irrigation input."),
            ("Harvest yield", "Direct NASA training data available", "OSD-655 VEG04A", "Exploratory mizuna regression only", "No transfer to lettuce/tomato/radish."),
            ("Gravity effects", "NASA data available but requiring processing", "OSD-436, OSD-7, OSD-120", "Heuristic simulator factor", "Molecular responses cannot calibrate edible-yield gravity factors."),
            ("Radiation effects", "No suitable NASA dataset identified", "No matched plant-specific dose/outcome dataset acquired", "Heuristic simulator factor", "ISS telemetry is not plant-specific dose; no RadLab pairing performed."),
            ("Water consumption", "NASA data available but requiring processing", "OSD-655 irrigation supplements", "Canopy-based water estimate", "Logs measure irrigation supplied, not transpiration/demand."),
            ("Water recovery", "NASA research exists but raw measurements are unavailable", "NASA BPC/CELSS literature", "User-configured loop efficiency", "Recovery fraction is a scenario assumption, not learned."),
            ("Light intensity", "NASA data available only as aggregated experimental results", "NASA BPC studies", "Assumed PPFD response", "No independently calibrated PPFD-to-yield surface."),
            ("Light spectrum", "NASA data available but requiring processing", "OSD-767, OSD-655", "Qualitative context; not calibrated simulator coefficient", "Spectral categories differ across crops/experiments."),
            ("CO2 uptake", "NASA data available only as aggregated experimental results", "NASA BPC gas-exchange literature", "Carbon mass-balance estimate", "No measured gas-exchange training table acquired."),
            ("Oxygen production", "NASA research exists but raw measurements are unavailable", "Photosynthetic mass balance", "Stoichiometric estimate", "Respiration and ecosystem gas fluxes not independently validated."),
            ("Temperature", "NASA data available but requiring processing", "OSDR growth protocol metadata", "Assumed thermal response", "Protocol setpoints are not paired response labels."),
            ("Humidity", "NASA data available but requiring processing", "OSDR growth protocol metadata", "VPD-based scenario estimate", "No fitted crop humidity-response model."),
            ("Plant stress", "NASA data available but requiring processing", "OSD-767 transcriptome", "Molecular flight-context classification only", "Flight label is not disease or stress severity."),
            ("Environmental optimization", "No suitable NASA dataset identified", "Simulator objective functions", "Constrained scenario optimization", "Recommendations optimize assumed equations, not real spacecraft safety."),
        ]
    ]


@lru_cache(maxsize=4)
def load_model(model_id):
    if model_id not in MODEL_IDS:
        raise KeyError(model_id)
    registry = read_json(ARTIFACTS / "registry.json")
    item = next((m for m in registry["models"] if m["id"] == model_id), None)
    if item is None:
        raise FileNotFoundError("Model not registered")
    path = ARTIFACTS / f"{model_id}.json"
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != item["sha256"]:
        raise ValueError("Model artifact failed SHA256 verification")
    model = json.loads(body)
    if model["id"] != model_id:
        raise ValueError("Model identifier mismatch")
    width = len(model["features"])
    if "forest" in model:
        if not 1 <= len(model["forest"]) <= 128:
            raise ValueError("Invalid forest size")
        for tree in model["forest"]:
            count = len(tree["value"])
            if not 1 <= count <= 4096 or any(len(tree[k]) != count for k in ("left","right","feature","threshold")):
                raise ValueError("Invalid tree dimensions")
            for i in range(count):
                if not math.isfinite(tree['value'][i]) or not math.isfinite(tree['threshold'][i]):
                    raise ValueError("Non-finite tree values")
                if tree['left'][i] != -1 and (not 0 <= tree['feature'][i] < width or not i < tree['left'][i] < count or not i < tree['right'][i] < count):
                    raise ValueError("Invalid or cyclic tree branches")
        return model
    linear = model["linear"]
    if any(len(linear[k]) != width for k in ("mean", "scale", "coefficients")):
        raise ValueError("Model feature dimensions mismatch")
    if not all(math.isfinite(v) for k in ("mean", "scale", "coefficients") for v in linear[k]) or not math.isfinite(linear["intercept"]) or min(linear["scale"]) <= 0:
        raise ValueError("Unsafe non-finite model artifact")
    return model


def model_registry():
    registry = read_json(ARTIFACTS / "registry.json")
    registered = {item["id"]: item for item in registry.get("models", [])}
    models = []
    for model_id in sorted(MODEL_IDS):
        try:
            model = load_model(model_id)
            # Keep executable coefficients/tree arrays private, but expose the
            # information a researcher needs to judge applicability.
            metrics = model.get("metrics", {})
            baseline = model.get("baselineMetrics", {})
            if model_id == "mizuna-harvest-v1":
                evidence_status = "baseline-only"
            elif model.get("status") == "trained-exploratory":
                evidence_status = "experimental"
            else:
                evidence_status = "insufficient-evidence"
            models.append({k: v for k, v in model.items() if k not in ("linear", "forest") } | {
                "artifactExists": True,
                "artifactSha256": registered.get(model_id, {}).get("sha256"),
                "predictionStatus": evidence_status,
                "baselineComparison": {
                    "available": bool(baseline),
                    "outperformsBaselineMAE": bool(baseline and metrics.get("MAE", float("inf")) < baseline.get("MAE", float("-inf"))),
                },
            })
        except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
            models.append({"id": model_id, "name": model_id, "status": "unavailable", "artifactExists": False, "limitations": ["Verified model artifact not available; run the offline training pipeline."]})
    return {"models": models, "simulatorMode": "Assumption-based mathematical estimates; separate from NASA-trained crop-specific and molecular models", "unsupportedTargets": ["Lettuce/tomato/radish ML yield", "measured water demand", "measured gas exchange", "disease image classification", "lunar/Martian predictive validation"]}


def predict_values(model, values):
    if len(values) != len(model['features']) or not all(math.isfinite(v) for v in values):
        raise ValueError('Invalid model feature vector')
    if 'forest' in model:
        predictions=[]
        for tree in model['forest']:
            index=0
            while tree['left'][index] != -1:
                index=tree['left'][index] if values[tree['feature'][index]] <= tree['threshold'][index] else tree['right'][index]
            predictions.append(tree['value'][index])
        result=sum(predictions)/len(predictions)
    else:
        linear = model["linear"]
        result = linear["intercept"] + sum((v - m) / s * c for v, m, s, c in zip(values, linear["mean"], linear["scale"], linear["coefficients"]))
    warnings = []
    for name, value in zip(model["features"], values):
        domain = model["domain"][name]
        if not domain["min"] <= value <= domain["max"]:
            warnings.append(f"{name} outside observed training range [{domain['min']:.3g}, {domain['max']:.3g}]")
    return result, warnings


def preview(study_id):
    tables = []
    if study_id == "OSD-655":
        targets = [("mizuna_harvest.csv", "Measured VEG04A endpoints; missing harvest outcomes excluded; irrigation is retrospective.", {"harvestFreshMassG": "g fresh mass/pillow", "waterSuppliedL": "L/pillow"}), ("mizuna_irrigation.csv", "Recorded irrigation events; irregular days, not physiological water demand.", {"waterSuppliedMl": "mL/event", "dayAfterInitiation": "days"})]
    elif study_id == "OSD-767":
        targets = [("tomato_samples.csv", "Actual RNA-seq specimen metadata. Labels are experimental context, not stress severity.", {})]
    elif study_id == "OSD-745":
        files = sorted((DATA / "raw" / study_id).glob("*TRANSFORMED.csv"))
        targets = [(p, "NASA-transformed nutritional assay; column headers state units. Not a yield table.", {}) for p in files]
    else:
        targets = []
    for name, note, units in targets:
        path = name if isinstance(name, Path) else DATA / "processed" / name
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle); rows = list(reader)
            tables.append({"name": path.name, "columns": reader.fieldnames, "rows": rows[:20], "rowCount": len(rows), "units": units, "note": note})
    return {"studyId": study_id, "tables": tables, "note": "Only acquired, processed measurements are previewed; absent tables are not synthetic."}
