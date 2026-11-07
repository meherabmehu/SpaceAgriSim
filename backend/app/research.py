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
MODEL_IDS = {
    "mizuna-harvest-v1",
    "tomato-flight-response-v1",
    "lettuce-earth-growth-v1",
    "mizuna-microbial-load-v1",
    "mizuna-microbial-relative-load-v2",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def manifest():
    path = DATA / "metadata" / "dataset_manifest.json"
    base = read_json(path) if path.is_file() else {"datasets": [], "status": "not-acquired"}
    candidates = DATA / "metadata" / "phase2_nasa_candidates.json"
    if candidates.is_file():
        base = dict(base)
        base["datasets"] = [*base["datasets"], *read_json(candidates).get("datasets", [])]
    return base


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
            # Prefer the status the artifact computed from its own measured
            # metrics; fall back to a conservative default. A model must never be
            # able to acquire a confident label by omission.
            declared = model.get("evidenceStatus")
            if model_id == "mizuna-harvest-v1":
                # Target mixes two measurement definitions across arms; see
                # docs/DATA_HARMONIZATION.md H1. Never promotable.
                evidence_status = "baseline-only"
            elif declared:
                evidence_status = declared
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
    elif study_id == "OSD-895":
        targets = [("eden_iss_2018_biomass_summary.csv", "EDEN ISS terrestrial-analogue crop/cycle summaries. Values are not independent plant-level replicates and are not a general yield-training table.", {"harvestAgeDays": "days", "meanEdibleFreshweightKgM2": "kg/m2", "edibleFreshweightRangeGm2": "g/m2", "abovegroundDryBiomassGm2": "g/m2", "belowgroundDryBiomassGm2": "g/m2"})]
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


def phase6_report(name):
    """Load a Phase 6 evidence artifact, if the analysis has been run.

    These files are produced by the offline analysis scripts and committed, so
    the API can serve measured provenance without re-running any training.
    """
    candidates = [
        ROOT / "docs" / "phase6" / name,
        BUNDLE / "phase6" / name,
    ]
    for path in candidates:
        if path.is_file():
            return read_json(path)
    return None


def phase7_report(name):
    """Load a Phase 7 evidence artifact, if the analysis has been run.

    Same lookup discipline as phase6_report: served from the committed analysis
    output, never recomputed at request time.
    """
    candidates = [
        ROOT / "docs" / "phase7" / name,
        BUNDLE / "phase7" / name,
    ]
    for path in candidates:
        if path.is_file():
            return read_json(path)
    return None


def measurement_catalog():
    """The Phase 7 measurement catalog: what NASA measured, and whether it trains.

    Served with a checksum so a consumer can tell whether the catalog it read
    matches the extraction outputs it was built from.
    """
    path = ROOT / "data" / "metadata" / "phase7_measurement_catalog.json"
    eligibility_path = ROOT / "data" / "metadata" / "phase7_training_eligibility.json"
    if not path.is_file():
        return {"status": "not-run", "note": "Run scripts/build_measurement_catalog.py."}
    payload = read_json(path)
    body = path.read_bytes()
    result = {
        "status": "available",
        "schemaVersion": 1,
        "catalogSha256": hashlib.sha256(body).hexdigest(),
        "summary": payload.get("summary"),
        "statusVocabulary": payload.get("statusVocabulary"),
        "eligibilityVocabulary": payload.get("eligibilityVocabulary"),
        "sources": payload.get("sources"),
        "targets": payload.get("targets"),
        "outputChecksums": payload.get("outputs"),
        "trayAreaDiscrepancy": payload.get("trayAreaDiscrepancy"),
    }
    if eligibility_path.is_file():
        eligibility = read_json(eligibility_path)
        result["trainingEligibility"] = {
            "sha256": hashlib.sha256(eligibility_path.read_bytes()).hexdigest(),
            "summary": eligibility.get("summary"),
            "policy": eligibility.get("policy"),
            "refusedTasks": eligibility.get("refusedTasks"),
        }
    return result


def source_checksums():
    """Checksums for every Phase 7 evidence input and model artifact."""
    manifest_path = ROOT / "data" / "metadata" / "phase7_ntrs_checksums.json"
    documents = []
    if manifest_path.is_file():
        for entry in read_json(manifest_path):
            documents.append({
                "ntrsId": entry.get("id"), "label": entry.get("label"),
                "sha256": entry.get("sha256"), "bytes": entry.get("bytes"),
                "pages": entry.get("pages"), "url": entry.get("url"),
            })
    registry = read_json(ARTIFACTS / "registry.json")
    models = []
    for item in registry.get("models", []):
        path = ARTIFACTS / f"{item['id']}.json"
        verified = False
        if path.is_file():
            verified = hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
        models.append({"id": item["id"], "sha256": item["sha256"],
                       "supersedes": item.get("supersedes"), "verified": verified})
    report_path = ROOT / "data" / "metadata" / "ntrs_extraction_report.json"
    return {
        "schemaVersion": 1,
        "algorithm": "SHA-256",
        "sourceDocuments": documents,
        "sourceDocumentsNote": (
            "PDFs are not committed (large and publicly re-downloadable). These "
            "digests are what make the extraction auditable against the original "
            "documents."
        ),
        "extractionReport": (hashlib.sha256(report_path.read_bytes()).hexdigest()
                             if report_path.is_file() else None),
        "modelArtifacts": models,
        "registryEnvironment": registry.get("environment"),
    }


def calibration():
    """Crop-baseline calibration evidence and simulation invariant results."""
    payload = phase6_report("simulation_calibration.json")
    if payload is None:
        return {
            "status": "not-run",
            "note": "Run scripts/calibrate_simulation.py to generate calibration evidence.",
        }
    invariants = payload.get("invariants", {})
    result = {
        "status": "available",
        "source": payload.get("source"),
        "sourceCaveat": payload.get("sourceCaveat"),
        "normalisationPolicy": payload.get("normalisationPolicy"),
        "calibration": payload.get("calibration", {}),
        "invariants": {
            "checksRun": invariants.get("checksRun"),
            "allPassed": invariants.get("allPassed"),
            "failureCount": len(invariants.get("failures", [])),
        },
    }
    # Phase 7 calibration is additive: the Phase 6 block above keeps its exact
    # shape so no existing consumer sees a moved field.
    phase7 = phase7_report("scientific_calibration.json")
    if phase7 is not None:
        result["phase7"] = {
            "checks": phase7.get("checks", []),
            "appliedChanges": phase7.get("appliedChanges", []),
            "declinedChanges": phase7.get("declinedChanges", []),
            "massBalance": phase7.get("massBalance"),
            "outputFingerprint": phase7.get("outputFingerprint"),
            "applyPolicy": phase7.get("applyPolicy"),
        }
    return result


def evidence_summary():
    """One place that states what is measured, estimated, assumed or blocked.

    Phase 7 restructured this. Phase 6 listed plant physiology targets as
    "blocked" because OSDR - a genomics archive - had no crop-physiology tables.
    The measurements exist in NASA Technical Memoranda, so the honest categories
    are now four, not three:

        measured and trainable      a model exists and transfers
        measured, not trainable     real numbers, but too few or too confounded
        assumed                     simulator parameters with no source
        blocked                     searched for and genuinely absent
    """
    statuses = {}
    for model_id in sorted(MODEL_IDS):
        try:
            model = load_model(model_id)
        except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
            statuses[model_id] = "unavailable"
            continue
        statuses[model_id] = model.get("evidenceStatus") or (
            "baseline-only" if model_id == "mizuna-harvest-v1" else "experimental")
    return {
        "schemaVersion": 2,
        "modelEvidenceStatus": statuses,
        "measuredTargets": [
            "OSD-655 VEG-04A harvest mass per pillow (14 usable endpoints; target defined differently per arm)",
            "OSD-780 VEG-04A/B culturable aerobic and yeast/mould plate counts per g fresh weight (203 + 169 measured rows)",
            "OSD-745 VEG-01/03A elemental, phenolic, anthocyanin and ORAC assays",
            "EDEN ISS 2018 per-crop edible fresh mass in kg/m2 (OSD-895; transcribed from the published paper, not a NASA table)",
        ],
        "measuredNotTrainable": [
            {"target": "biomass time series", "source": "NASA TM-102784 Table 10 (1989)",
             "reason": "7 ages, 1 tray per age; a curve can be fitted, nothing validated"},
            {"target": "harvest dry-matter yield", "source": "NASA TM-102784 Tables 6-7",
             "reason": "16 trays, one study, wheat grain, dry basis; no transfer population"},
            {"target": "transpiration", "source": "NASA TM-102788 p.3/15; NASA TM-103494 p.12",
             "reason": "stand-level integrated values; bounds only, no per-day series"},
            {"target": "plant water uptake", "source": "NASA TM-102788; NASA TM-103494",
             "reason": "two studies, both leak-confounded; bounds only"},
            {"target": "water recovery", "source": "NASA TM-103494 p.12-13",
             "reason": "one balance (0.924) from a chamber leaking 20-40 %/day; lower bound"},
            {"target": "CO2 assimilation", "source": "NASA TM-102788 p.3/11/12",
             "reason": "peak, mean and net fixation are printed; no replication"},
            {"target": "photosynthetic response to irradiance", "source": "NASA TM-102788 p.13",
             "reason": "described linear response with two anchor points; no tabulated curve"},
            {"target": "PPFD and photoperiod response", "source": "NASA TM-102788 p.7; NASA TM-103494 p.9/18",
             "reason": "2-3 operating points confounded with phase, sealing and copper deficiency"},
            {"target": "measured stress outcomes", "source": "NASA TM-102784 p.40 footnotes",
             "reason": "binary per-tray labels, no severity, no control arm"},
        ],
        "assumedTargets": [
            "gravity, radiation, light-intensity, temperature and humidity response curve shapes",
            "crop growth duration, harvest index, dry-matter fraction and peak water demand",
            "water recovery efficiency (checked against a measured lower bound; retained)",
            "carbon fraction of dry mass (within 20 % of a measured CO2 balance; retained)",
        ],
        "blockedTargets": [
            "O2 evolution (never measured; deriving it from CO2 would be an assumption)",
            "continuous gravity response (every recovered report is a 1 g ground chamber)",
            "radiation dose paired with plant response (all 'radiation' hits are lamp spectra)",
            "harvest dry mass for lettuce, tomato or radish (the recovered corpus is wheat only)",
        ],
        "negativeFindingRecord": {
            "searchEngine": "NASA Technical Reports Server",
            "queries": 39,
            "uniqueDocuments": 256,
            "downloadablePdfs": 110,
            "reportsExtracted": 3,
            "note": ("Phase 6 concluded these targets were not measured anywhere; that was "
                     "wrong as stated. They were published in NASA Technical Memoranda, "
                     "which OSDR does not index. The corrected claim is narrower: they "
                     "are measured, and still not trainable."),
        },
        "note": (
            "Measured, measured-but-not-trainable, assumed and hypothetical quantities "
            "are kept in separate fields and are never blended into a single number "
            "presented as a prediction."
        ),
    }
