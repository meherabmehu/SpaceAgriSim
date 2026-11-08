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
# Evaluation artifacts are not part of the packaged runtime bundle (they are analysis
# output, not inference assets), so they are resolved separately and their absence is
# handled rather than assumed.
EVALUATION = (BUNDLE / "ml" / "evaluation") if (BUNDLE / "ml" / "evaluation").is_dir() else (ROOT / "ml" / "evaluation")
MODEL_IDS = {
    "mizuna-harvest-v1",
    "tomato-flight-response-v1",
    "lettuce-earth-growth-v1",
    "lettuce-earth-growth-v2",
    "mizuna-microbial-load-v1",
    "mizuna-microbial-relative-load-v2",
    # Phase 9: NASA OSD-46 radiation response models.
    "radiation-quality-osd46-v1",
    "radiation-exposure-osd46-v1",
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
            ("Plant growth", "NASA closed-chamber canopy measurements acquired from NTRS technical reports; no orbital growth time series exists", "NTRS TM 102788 (wheat, 86-day chamber study), N90-16689 (wheat CO2 dynamics); external WUR lettuce endpoints (not NASA)", "Assumption-based habitat simulator; the acquired chamber data is quotable and citable but is not fitted into the simulator", "The chamber studies are ground-based at Kennedy Space Center: they do not validate a Moon, Mars or ISS growth curve for lettuce, tomato or radish."),
            ("Biomass", "Direct NASA training data available", "OSD-655 VEG04A", "Exploratory mizuna regression only", "14 harvested pillow endpoints; retrospective irrigation input."),
            ("Harvest yield", "Direct NASA training data available", "OSD-655 VEG04A", "Exploratory mizuna regression only", "No transfer to lettuce/tomato/radish."),
            ("Gravity effects", "NASA data available but no molecular model passed validation", "OSD-436, OSD-7, OSD-120; OSD-411 reorientation tested and rejected", "Heuristic simulator factor", "Molecular responses cannot calibrate edible-yield gravity factors; a 90-degree ground reorientation is not partial gravity."),
            ("Radiation effects", "NASA molecular data available and modelled", "OSD-46 (Arabidopsis, gamma vs Fe-56), OSD-782 (dose, evaluated and rejected)", "Molecular-response classification; the habitat simulator still uses a heuristic factor", "Classifiers identify the applied condition, not absorbed dose, damage severity or yield; dose prediction failed validation and is not served."),
            ("Water consumption", "NASA canopy water-exchange measurements acquired from NTRS technical reports", "NTRS TM 102788, N91-20026 (soybean stand); OSD-655 irrigation logs", "Canopy-based water estimate in the simulator; the chamber measurements are cited, not fitted", "Chamber transpiration is ground-based and cultivar-specific; irrigation records still measure water supplied, not demand."),
            ("Water recovery", "NASA research exists but raw measurements are unavailable", "NASA BPC/CELSS literature", "User-configured loop efficiency", "Recovery fraction is a scenario assumption, not learned."),
            ("Light intensity", "PPFD levels are recorded in the acquired NTRS chamber studies; the PPFD-to-yield response is still not a fitted surface", "NTRS TM 102788, N90-16689; NASA BPC literature", "Assumed PPFD response", "Measured irradiance setpoints do not constitute a calibrated PPFD-to-yield curve, so the simulator response remains an assumption."),
            ("Light spectrum", "NASA growth-chamber endpoints acquired for lettuce and radish at equal PPF; still no spectral response surface", "NTRS 20160006559 (red+blue LEDs vs white fluorescent, measured fresh mass, morphology and leaf area); OSD-767, OSD-655", "Spectrum remains a recorded annotation in the simulator; the chamber endpoints are cited, not fitted", "Two treatments cannot define a wavelength-to-yield curve, so the simulator still applies no spectrum response - the acquired comparison is evidence about direction, not a coefficient."),
            ("CO2 uptake", "NASA closed-chamber gas-exchange measurements acquired from NTRS technical reports", "NTRS TM 102788, N90-16689, N91-20026", "Carbon mass-balance estimate in the simulator; measured exchange rates are cited, not fitted", "Measured rates exist for ground chamber canopies of wheat and soybean only; no harmonised training table was built, and no lunar or Martian exchange data exists."),
            ("Oxygen production", "Derived from measured CO2 exchange acquired from NTRS; no direct O2 measurement acquired", "NTRS TM 102788 (CO2 drawdown), photosynthetic mass balance", "Stoichiometric estimate", "O2 is inferred from carbon exchange rather than measured, and the underlying measurements are ground-chamber only."),
            ("Temperature", "NASA data available but requiring processing", "OSDR growth protocol metadata", "Assumed thermal response", "Protocol setpoints are not paired response labels."),
            ("Humidity", "NASA data available but requiring processing", "OSDR growth protocol metadata", "VPD-based scenario estimate", "No fitted crop humidity-response model."),
            ("Plant stress", "NASA molecular data available and modelled for radiation", "OSD-767 transcriptome; OSD-46 radiation response", "Molecular classification of experimental condition", "The labels are applied treatment or experiment context, not disease, stress severity or yield loss."),
            ("CO2 supraoptimal response", "NASA evidence shows a limit the simulator's CO2 factor does not have", "NTRS 20040090155 (soybean at 500-5000 ppm; yield greatest at 1000 ppm); NTRS TM 102788 (CO2 saturation near 1000 ppm)", "Monotonic saturating CO2 factor with no supraoptimal penalty; runs above 1000 ppm now carry a warning", "One soybean cultivar in a ground chamber is not a response surface, so the factor is not bent to it - the platform states the limitation at the point of use instead of hiding it."),
            ("Crop qualification status", "NASA reference data acquired on which crops are actually flight-qualified", "NTRS 20250001897 (Table A-3: 9 crops at Crop Readiness Level 9 of 376 tested)", "Not modelled; shown as context for the crop choices the simulator offers", "CRL 9 is a testing-status record, not a productivity measurement, and no herb, microgreen or legume has reached CRL 9."),
            ("Trace-gas accumulation (ethylene)", "NASA research identified and disclosed; deliberately not modelled", "NTRS 20040087496 (Klassen & Bugbee 2002, wheat and rice in closed chambers)", "No ethylene term exists in the simulator", "Continuous ethylene reduced wheat yield 36 % and rice 63 % at 50 ppb in closed chambers. The simulator has no trace-gas model, so this risk is disclosed rather than estimated - a single crop pair is not a transferable yield factor."),
            ("Environmental optimization", "No suitable NASA dataset identified", "Simulator objective functions", "Constrained scenario optimization", "Recommendations optimize assumed equations, not real spacecraft safety."),
            ("Substrate and regolith", "NASA data available for simulants and substrate substitution, not for actual lunar or Martian regolith", "OSD-670 (carbonaceous-chondrite simulant), OSD-856 (simulated lunar soil batch #005)", "Exposed as a scenario assumption, not a calibrated response surface", "A simulant is not regolith: OSD-670 grows plants on an asteroid analogue and OSD-856 on one simulated lunar soil batch, so neither transfers to the Moon by analogy."),
            ("Edible-product microbiology", "NASA data available and modelled as a within-campaign relative load", "OSD-267, OSD-268, OSD-269, OSD-655, OSD-745, OSD-780, OSD-386, OSD-723", "Relative culturable-aerobic-load regression; no pathogen model", "Plate counts measure culturable aerobic load, not pathogens or consumer risk; OSD-386 is a deliberate inoculation trial and does not estimate background contamination."),
        ]
    ]


def _validate_trees(trees, width):
    """Structural validation shared by bagged forests and boosted ensembles.

    Both store plain decision trees as parallel arrays, so neither the branch
    bounds nor the cycle/width checks may diverge between them.
    """
    for tree in trees:
        count = len(tree["value"])
        if not 1 <= count <= 4096 or any(len(tree[k]) != count for k in ("left", "right", "feature", "threshold")):
            raise ValueError("Invalid tree dimensions")
        for i in range(count):
            if not math.isfinite(tree["value"][i]) or not math.isfinite(tree["threshold"][i]):
                raise ValueError("Non-finite tree values")
            if tree["left"][i] != -1 and (not 0 <= tree["feature"][i] < width
                                          or not i < tree["left"][i] < count
                                          or not i < tree["right"][i] < count):
                raise ValueError("Invalid or cyclic tree branches")


# The cache size must be at least the number of registered models. Phase 7 raised
# the registry from four models to five while this decorator stayed at maxsize=4,
# so every GET /api/models pass produced misses=5, currsize=4 and evicted an entry
# it had just loaded - zero reuse, and ~1 MB of artifacts re-read and re-hashed per
# request. Deriving the size from MODEL_IDS means adding a model can never silently
# reintroduce the thrash; backend/tests/test_phase8_performance.py asserts it.
@lru_cache(maxsize=len(MODEL_IDS))
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
        _validate_trees(model["forest"], width)
        return model
    if "boostedTrees" in model:
        boosted = model["boostedTrees"]
        if not 1 <= len(boosted["trees"]) <= 512:
            raise ValueError("Invalid boosting round count")
        if not math.isfinite(boosted["init"]) or not math.isfinite(boosted["learningRate"]):
            raise ValueError("Non-finite boosting parameters")
        if not 0 < boosted["learningRate"] <= 1:
            raise ValueError("Invalid learning rate")
        _validate_trees(boosted["trees"], width)
        return model
    if "evaluator" in model:
        evaluator = model["evaluator"]
        if evaluator.get("kind") != "linear-softmax":
            raise ValueError("Unsupported evaluator kind")
        classes = evaluator["classes"]
        if not 2 <= len(classes) <= 8:
            raise ValueError("Invalid class count")
        for key in ("mean", "scale"):
            if len(evaluator[key]) != width:
                raise ValueError("Model feature dimensions mismatch")
        if min(evaluator["scale"]) <= 0:
            raise ValueError("Unsafe non-finite model artifact")
        for name in ("mean", "scale"):
            if not all(math.isfinite(v) for v in evaluator[name]):
                raise ValueError("Unsafe non-finite model artifact")
        for label in classes:
            row = evaluator["coefficients"][label]
            if len(row) != width or not all(math.isfinite(v) for v in row):
                raise ValueError("Unsafe non-finite model artifact")
        if len(evaluator["intercept"]) != len(classes) or not all(
                math.isfinite(v) for v in evaluator["intercept"]):
            raise ValueError("Unsafe non-finite model artifact")
        if len(model.get("features", [])) != width:
            raise ValueError("Feature list does not match model width")
        return model
    linear = model["linear"]
    if any(len(linear[k]) != width for k in ("mean", "scale", "coefficients")):
        raise ValueError("Model feature dimensions mismatch")
    if not all(math.isfinite(v) for k in ("mean", "scale", "coefficients") for v in linear[k]) or not math.isfinite(linear["intercept"]) or min(linear["scale"]) <= 0:
        raise ValueError("Unsafe non-finite model artifact")
    return model


def _baseline_comparison(metrics, baseline):
    """Is this model better than its baseline, using the metric its task allows?

    Regression models are compared on MAE. Classifiers have no MAE at all, so
    evaluating them on that key silently reports False for a model that is in fact
    far better than its baseline - a classifier with balanced accuracy 0.90 against
    a 0.00 majority baseline would have been advertised as "does not beat
    baseline". Balanced accuracy is the correct classifier metric here because it
    is not inflated by class imbalance.
    """
    if not baseline:
        return {"available": False, "metric": None, "outperformsBaseline": False,
                "outperformsBaselineMAE": False}
    if "balancedAccuracy" in metrics and "balancedAccuracy" in baseline:
        better = metrics["balancedAccuracy"] > baseline["balancedAccuracy"]
        return {
            "available": True,
            "metric": "balancedAccuracy",
            "modelValue": metrics.get("balancedAccuracy"),
            "baselineValue": baseline.get("balancedAccuracy"),
            "outperformsBaseline": bool(better),
            "outperformsBaselineMAE": bool(better),
            "note": ("outperformsBaselineMAE is retained for schema compatibility and "
                     "carries the balanced-accuracy verdict for classifiers."),
        }
    better = metrics.get("MAE", float("inf")) < baseline.get("MAE", float("-inf"))
    return {"available": True, "metric": "MAE",
            "modelValue": metrics.get("MAE"), "baselineValue": baseline.get("MAE"),
            "outperformsBaseline": bool(better),
            "outperformsBaselineMAE": bool(better)}


@lru_cache(maxsize=1)
def _calibration_status():
    """Measured interval coverage per model, from the committed Phase 10 decision.

    Coverage is reported as a measurement with the split it was measured on. It is
    never relabelled as a guarantee, and `calibrated` stays false wherever it was
    false, because empirical coverage on held-out groups does not validate a future
    campaign.
    """
    path = EVALUATION / "phase10_uncertainty_decision.json"
    if not path.is_file():
        return {}
    decision = read_json(path)
    conformal_path = EVALUATION / "phase10_conformal.json"
    conformal = read_json(conformal_path) if conformal_path.is_file() else {"models": {}}
    status = {}
    for model_id, choice in (decision.get("decisions") or {}).items():
        measured = (conformal.get("models", {}).get(model_id, {})
                    .get("summary", {}).get(choice.get("adopted", ""), {}))
        status[model_id] = {
            "calibrated": False,
            "nominalCoverage": measured.get("nominalCoverage"),
            "measuredCoverage": choice.get("achievedCoverage"),
            "measuredWidth": measured.get("meanIntervalWidth"),
            "method": choice.get("adopted"),
            "measuredOn": "held-out biological groups",
            "statement": ("Coverage is a measurement on held-out groups, not a guarantee: "
                          "repeated tissues from one unit and a small number of campaigns "
                          "are not a sample of future campaigns."),
        }
    return status


def _explanation_available(model_id):
    path = ARTIFACTS / f"{model_id}-explanation.json"
    return path.is_file()


def _classification_record(model_id):
    """Attach the six-category classification to a model row.

    Imported lazily and defensively: the registry must still render if the taxonomy
    module is unavailable, and an unclassified model is a bug worth surfacing rather
    than hiding behind a default.
    """
    try:
        from app.science_classification import CATEGORY_NAMES, SERVICE_ALLOWED, feature_by_id
    except ImportError:  # pragma: no cover - taxonomy is part of the app package
        return None
    feature = feature_by_id(model_id)
    if feature is None:
        return None
    return {
        "category": feature.category,
        "categoryName": CATEGORY_NAMES[feature.category],
        "serviceAllowed": SERVICE_ALLOWED[feature.category],
        "servedStatus": feature.status,
        "surface": feature.surface,
        "evidence": feature.evidence,
        "userFacing": feature.user_facing,
        "notes": list(feature.notes),
    }


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
            models.append({k: v for k, v in model.items() if k not in ("linear", "forest", "boostedTrees") } | {
                "artifactExists": True,
                "artifactSha256": registered.get(model_id, {}).get("sha256"),
                "predictionStatus": evidence_status,
                "baselineComparison": _baseline_comparison(metrics, baseline),
                # Phase 12: the facts a researcher needs to judge applicability were
                # already computed and were simply not being served together.
                "scientificClassification": _classification_record(model_id),
                "calibration": _calibration_status().get(model_id) or {
                    "calibrated": False,
                    "measuredCoverage": None,
                    "statement": "No measured interval coverage is recorded for this model.",
                },
                "explanationAvailable": _explanation_available(model_id),
                # The artifact's own `supersedes` note is more specific than the registry
                # id (it records that the predecessor is kept rather than overwritten), so
                # the registry value only fills a gap and never overwrites it.
                "supersedes": model.get("supersedes")
                              or registered.get(model_id, {}).get("supersedes"),
            })
        except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
            models.append({"id": model_id, "name": model_id, "status": "unavailable", "artifactExists": False, "limitations": ["Verified model artifact not available; run the offline training pipeline."]})
    return {"models": models, "simulatorMode": "Assumption-based mathematical estimates; separate from NASA-trained crop-specific and molecular models", "unsupportedTargets": ["Lettuce/tomato/radish ML yield", "measured water demand", "measured gas exchange", "disease image classification", "lunar/Martian predictive validation"]}


def predict_probabilities(model, values):
    """Softmax class probabilities for a linear-softmax artifact.

    Plain arithmetic on Python floats: no numpy, no picking, no framework version to
    reproduce. The same numbers the training script measured are the numbers served.
    """
    evaluator = model["evaluator"]
    if len(values) != len(evaluator["features"]):
        raise ValueError("Feature vector length does not match the model")
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Non-finite feature value")
    standardised = [(v - m) / s for v, m, s in zip(values, evaluator["mean"], evaluator["scale"])]
    scores = {}
    for index, label in enumerate(evaluator["classes"]):
        row = evaluator["coefficients"][label]
        scores[label] = evaluator["intercept"][index] + sum(
            c * v for c, v in zip(row, standardised))
    peak = max(scores.values())
    exponent = {label: math.exp(s - peak) for label, s in scores.items()}
    total = sum(exponent.values())
    return {label: value / total for label, value in exponent.items()}


def _domain_warnings(model, values):
    """Flag features outside their observed training range.

    Supports both layouts: a per-gene map under domain['features'] (Phase 9
    transcriptomic artifacts) and a flat name -> {min,max} map (earlier models).
    """
    domain = model.get("domain") or {}
    per_gene = domain.get("features") if isinstance(domain.get("features"), dict) else domain
    warnings = []
    for name, value in zip(model["features"], values):
        bound = per_gene.get(name) if isinstance(per_gene, dict) else None
        if isinstance(bound, dict) and "min" in bound and "max" in bound:
            if not bound["min"] <= value <= bound["max"]:
                warnings.append(f"{name} outside observed training range "
                                f"[{bound['min']:.3g}, {bound['max']:.3g}]")
    return warnings


def _eval_tree(tree, values):
    """Walk one decision tree to a leaf and return its value."""
    index = 0
    while tree['left'][index] != -1:
        index = (tree['left'][index] if values[tree['feature'][index]] <= tree['threshold'][index]
                 else tree['right'][index])
    return tree['value'][index]


def predict_values(model, values):
    if len(values) != len(model['features']) or not all(math.isfinite(v) for v in values):
        raise ValueError('Invalid model feature vector')
    if 'forest' in model:
        result = sum(_eval_tree(tree, values) for tree in model['forest']) / len(model['forest'])
    elif 'boostedTrees' in model:
        # Additive ensemble: init + learning_rate * sum of tree outputs.
        boosted = model['boostedTrees']
        result = boosted['init'] + boosted['learningRate'] * sum(
            _eval_tree(tree, values) for tree in boosted['trees'])
    elif 'evaluator' in model:
        # Multinomial logistic regression evaluated without any numpy/sklearn
        # dependency, so the served model stays auditable in plain arithmetic.
        probabilities = predict_probabilities(model, values)
        best = max(probabilities, key=probabilities.get)
        return best, _domain_warnings(model, values)
    else:
        linear = model["linear"]
        result = linear["intercept"] + sum((v - m) / s * c for v, m, s, c in zip(values, linear["mean"], linear["scale"], linear["coefficients"]))
    warnings = []
    for name, value in zip(model["features"], values):
        domain = model["domain"][name]
        if not domain["min"] <= value <= domain["max"]:
            warnings.append(f"{name} outside observed training range [{domain['min']:.3g}, {domain['max']:.3g}]")
    return result, warnings


def explanation(model_id):
    """Load a precomputed explanation for a model, verifying it is of that model.

    Explanations are computed offline (`ml/training/phase10_explain_radiation.py`)
    rather than on request. Recomputing selection stability per request would mean
    22 leave-one-group-out selections inside a web handler, and the result would be
    identical every time, so it belongs in a build step.
    """
    if model_id not in MODEL_IDS:
        raise KeyError(model_id)
    path = ARTIFACTS / f"{model_id}-explanation.json"
    if not path.is_file():
        return None
    body = path.read_bytes()
    report = json.loads(body)
    if report.get("modelId") != model_id:
        raise ValueError("Explanation belongs to a different model")
    # The identity check is repeated at read time: an explanation whose residual is
    # not ~0 is not an explanation of the served arithmetic, whatever it says.
    if report.get("identityResidual") is None or report["identityResidual"] > 1e-9:
        raise ValueError("Explanation failed its reconstruction identity check")
    return report


def preview(study_id):
    tables = []
    if study_id == "OSD-655":
        targets = [("mizuna_harvest.csv", "Measured VEG04A endpoints; missing harvest outcomes excluded; irrigation is retrospective.", {"harvestFreshMassG": "g fresh mass/pillow", "waterSuppliedL": "L/pillow"}), ("mizuna_irrigation.csv", "Recorded irrigation events; irregular days, not physiological water demand.", {"waterSuppliedMl": "mL/event", "dayAfterInitiation": "days"})]
    elif study_id == "OSD-767":
        targets = [("tomato_samples.csv", "Actual RNA-seq specimen metadata. Labels are experimental context, not stress severity.", {})]
    elif study_id == "OSD-745":
        files = sorted((DATA / "raw" / study_id).glob("*TRANSFORMED.csv"))
        targets = [(p, "NASA-transformed nutritional assay; column headers state units. Not a yield table.", {}) for p in files]
    elif study_id == "OSD-46":
        # Design tables only: this study's measurements are microarray
        # intensities for 22,560 probes, which are not a browsable row set.
        targets = [
            ("osd46_radiation_samples.csv",
             "Sample-to-condition assignment for the 44 arrays. Condition, dose and "
             "collection time are design factors, not measured outcomes.", {}),
            ("osd46_array_batch.csv",
             "Array batch assignment. Controls are not balanced across batches, so this "
             "table is what the batch-controlled evaluation is checked against.", {}),
        ]
    elif study_id == "OSD-782":
        targets = [
            ("osd782_radiation_samples.csv",
             "Sample-to-condition assignment for the 36 libraries. Condition and dose are "
             "design factors; the transcriptome is the measurement.", {}),
        ]
    elif study_id == "OSD-411":
        targets = [
            ("osd411_gravity_samples.csv",
             "Sample-to-condition assignment for 64 libraries from 16 seedlings. A 90 "
             "degree ground reorientation is not partial gravity, and the 64 libraries "
             "are not 64 independent plants.", {}),
        ]
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
