"""Read-only scientific registry and safe, dependency-free JSON model inference."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
ARTIFACTS = ROOT / "ml" / "artifacts"
MODEL_IDS = {"mizuna-harvest-v1", "tomato-flight-response-v1"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def manifest():
    path = DATA / "metadata" / "dataset_manifest.json"
    return read_json(path) if path.is_file() else {"datasets": [], "status": "not-acquired"}


def coverage():
    return [
        {"feature": name, "status": status, "source": source, "method": method, "limitation": limitation}
        for name, status, source, method, limitation in [
            ("Plant growth", "NASA data available only as aggregated experimental results", "NASA BPC literature; OSD-655 harvest endpoints", "Assumption-based simulator", "No matched crop growth time series acquired for lettuce/tomato/radish."),
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
    linear = model["linear"]
    width = len(model["features"])
    if any(len(linear[k]) != width for k in ("mean", "scale", "coefficients")):
        raise ValueError("Model feature dimensions mismatch")
    if not all(math.isfinite(v) for k in ("mean", "scale", "coefficients") for v in linear[k]) or not math.isfinite(linear["intercept"]) or min(linear["scale"]) <= 0:
        raise ValueError("Unsafe non-finite model artifact")
    return model


def model_registry():
    models = []
    for model_id in sorted(MODEL_IDS):
        try:
            model = load_model(model_id)
            models.append({k: v for k, v in model.items() if k not in ("linear", "domain") } | {"artifactExists": True})
        except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
            models.append({"id": model_id, "name": model_id, "status": "unavailable", "artifactExists": False, "limitations": ["Verified model artifact not available; run the offline training pipeline."]})
    return {"models": models, "simulatorMode": "Assumption-based mathematical estimates; separate from NASA-trained crop-specific and molecular models", "unsupportedTargets": ["Lettuce/tomato/radish ML yield", "measured water demand", "measured gas exchange", "disease image classification", "lunar/Martian predictive validation"]}


def predict_values(model, values):
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
