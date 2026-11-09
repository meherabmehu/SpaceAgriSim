"""Phase 12: the scientific AI workflow, enforced in one place.

The brief asks for: select evidence -> choose compatible model -> validate input -> run
inference -> interpret results -> review limitations -> save or export findings.

The existing prediction endpoints already do inference and refusal correctly, but each
one is bespoke, so a caller has to know which endpoint accepts which schema. This module
adds a **registry-driven** surface on top of them: it answers "which models can run this
input", validates against the model's own recorded schema and training domain, delegates
to the same inference code the dedicated endpoints use, and attaches the interpretation,
limitations and provenance in a single response.

It is deliberately additive. Nothing here replaces a dedicated endpoint or reimplements
an evaluator; `run_model` calls the same functions the served routes call, so a number
from the workflow is the same number from the model.

Three refusals are structurally enforced:

  * a model whose category is 6 is never run — it returns `retired` with its evidence
  * a transcriptomic model is never run from environmental inputs; it requires exactly
    the gene features it was trained on
  * a value outside the recorded training domain is reported, and a value outside the
    *plausible physical* range is rejected rather than clamped
"""
from __future__ import annotations

import math

from app import research
from app.science_classification import CATEGORY_NAMES, feature_by_id

# Absolute sanitisers. These are not model domains: they are values that cannot be
# physically meaningful for the quantity, so accepting them would be a bug even if a
# model's recorded domain were wide enough to admit them.
PHYSICAL_LIMITS = {
    "daysAfterTransplant": (0.0, 400.0),
    "airTemperature": (-40.0, 60.0),
    "rootTemperature": (-40.0, 60.0),
    "ppfd": (0.0, 2500.0),
    "freshWeightG": (0.0, 1e4),
    "fly": (0.0, 1.0),
    "blue": (0.0, 1.0),
    "waterSuppliedL": (0.0, 1e4),
    "establishedPlants": (0.0, 1e4),
    "photoperiodHours": (0.0, 24.0),
    "plantDensityPerM2": (0.0, 2000.0),
    # Daily light integral in mol m-2 d-1. Even the brightest plant factory stays near 40; 100 is
    # already past any published crop response, so a value above it is a unit slip, not a setpoint.
    "dailyLightIntegral": (0.0, 100.0),
}

# Which input family each served model needs. A model is offered only for the family it
# was trained on, which is what stops an environmental input being fed to a molecular
# classifier "because both are numbers".
INPUT_FAMILY = {
    "lettuce-earth-growth-v1": "environment",
    "lettuce-earth-growth-v2": "environment",
    "lettuce-earth-growth-v3": "environment",
    "mizuna-harvest-v1": "harvest",
    "mizuna-microbial-load-v1": "microbial",
    "mizuna-microbial-relative-load-v2": "microbial",
    "tomato-flight-response-v1": "gene-expression",
    "radiation-quality-osd46-v1": "gene-expression",
    "radiation-exposure-osd46-v1": "gene-expression",
    "et0-emulator-v1": "weather",
}

FAMILY_DESCRIPTION = {
    "environment": "Environmental and management inputs (days, temperature, light).",
    "harvest": "Mizuna harvest records (water supplied, established plants, environment, spectrum).",
    "microbial": "VEG-04 microbial assay context (campaign, environment, spectrum, tissue mass, harvest).",
    "gene-expression": "A complete transcriptomic feature vector in the model's own gene space.",
    "weather": "A daily weather summary (temperature, dew point, day of year, site).",
}


_FEATURE_FAMILY: dict[str, str] | None = None


def _feature_family_map() -> dict[str, str]:
    """Map every served feature name to the input family that owns it.

    Built once from the registry, so a gene identifier can never be mistaken for an
    environmental descriptor merely because both arrive as numbers.
    """
    global _FEATURE_FAMILY
    if _FEATURE_FAMILY is None:
        mapping: dict[str, str] = {}
        for model in research.model_registry()["models"]:
            family = INPUT_FAMILY.get(model["id"])
            for name in model.get("features") or []:
                mapping.setdefault(name, family)
        _FEATURE_FAMILY = mapping
    return _FEATURE_FAMILY


def model_features(model_id: str) -> list[dict]:
    """The recorded feature schema of one model, as id/label pairs where known."""
    model = research.load_model(model_id)
    return [{"name": name, "family": _feature_family_map().get(name)}
            for name in model["features"]]


def _infer_family(names) -> str | None:
    families = {_feature_family_map().get(name) for name in names}
    families.discard(None)
    return families.pop() if len(families) == 1 else None


class WorkflowError(Exception):
    def __init__(self, code: str, message: str, detail: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}


def model_catalogue() -> dict:
    """Every served model, with what it accepts and whether it can run at all."""
    rows = []
    for model in research.model_registry()["models"]:
        model_id = model["id"]
        classification = feature_by_id(model_id)
        category = classification.category if classification else None
        family = INPUT_FAMILY.get(model_id, "unknown")
        retired = category == 6
        rows.append({
            "modelId": model_id,
            "name": model.get("name"),
            "inputFamily": family,
            "inputFamilyDescription": FAMILY_DESCRIPTION.get(family),
            "features": model.get("features") or [],
            "featureCount": len(model.get("features") or []),
            "outputUnit": model.get("unit"),
            "target": model.get("target"),
            "category": category,
            "categoryName": (CATEGORY_NAMES[classification.category]
                             if classification else None),
            "runStatus": ("retired" if retired
                          else "external-service" if model_id in research.EXTERNAL_SERVICES
                          else "runnable" if model.get("artifactExists") else "unavailable"),
            "servedAt": (research.EXTERNAL_SERVICES.get(model_id, {}).get("endpoint")
                         if model_id in research.EXTERNAL_SERVICES else None),
            "retiredReason": (classification.evidence if retired else None),
            "calibration": model.get("calibration"),
            "explanationAvailable": model.get("explanationAvailable"),
            "sourceStudy": model.get("sourceStudy"),
            "sourceType": model.get("sourceType"),
        })
    return {"models": rows,
            "families": FAMILY_DESCRIPTION,
            "note": ("A gene-expression model requires its full recorded feature vector. "
                     "Environmental inputs cannot drive a molecular classifier, and this "
                     "catalogue says so per model rather than leaving it to the caller.")}


def compatible_models(features: list[str]) -> list[dict]:
    """Which models accept exactly these feature names."""
    wanted = set(features)
    rows = []
    for row in model_catalogue()["models"]:
        if row["runStatus"] != "runnable":
            continue
        recorded = set(row["features"])
        if recorded == wanted:
            match = "exact"
        elif recorded and recorded.issubset(wanted):
            match = "superset"
        elif wanted and wanted.issubset(recorded):
            match = "subset"
        else:
            continue
        rows.append({"modelId": row["modelId"], "match": match,
                     "missing": sorted(recorded - wanted),
                     "extra": sorted(wanted - recorded),
                     "inputFamily": row["inputFamily"]})
    order = {"exact": 0, "superset": 1, "subset": 2}
    rows.sort(key=lambda r: (order[r["match"]], len(r["missing"])))
    return rows


def validate_input(model_id: str, inputs: dict) -> dict:
    """Check the input against the model's recorded schema and training domain."""
    model = research.load_model(model_id)
    classification = feature_by_id(model_id)
    if classification is None:
        raise WorkflowError("unclassified-model",
                            f"{model_id} has no scientific classification and cannot be run.")
    if classification.category == 6:
        raise WorkflowError("retired-model",
                            f"{model_id} is classified category 6 and may not answer with a "
                            f"number.", {"evidence": classification.evidence})

    expected = list(model["features"])
    provided = set(inputs)
    missing = [name for name in expected if name not in provided]
    unexpected = sorted(provided - set(expected))
    checks = {"schemaExact": not missing and not unexpected,
              "featureCount": len(expected),
              "providedCount": len(provided),
              "missing": missing[:20],
              "unexpected": unexpected[:20]}

    expected_family = INPUT_FAMILY.get(model_id)
    provided_family = _infer_family(provided)
    checks["expectedFamily"] = expected_family
    checks["providedFamily"] = provided_family

    if provided_family and expected_family and provided_family != expected_family:
        raise WorkflowError(
            "family-mismatch",
            f"This model consumes {expected_family} inputs, but the supplied features are "
            f"{provided_family} inputs. A molecular classifier is not run from "
            f"environmental descriptors, and vice versa.",
            checks)
    if missing:
        raise WorkflowError(
            "missing-features",
            f"{len(missing)} required feature(s) are absent. This model needs exactly its "
            f"recorded feature vector; the workflow will not impute values.", checks)
    if unexpected:
        raise WorkflowError(
            "unexpected-features",
            f"{len(unexpected)} feature(s) are not part of this model's schema: "
            f"{', '.join(unexpected[:5])}.", checks)

    values = []
    for name in expected:
        raw = inputs[name]
        if isinstance(raw, bool):
            value = float(raw)
        elif isinstance(raw, (int, float)):
            value = float(raw)
        else:
            raise WorkflowError("non-numeric-feature",
                                f"{name} must be numeric.", {"feature": name})
        if not math.isfinite(value):
            raise WorkflowError("non-finite-feature",
                                f"{name} is not a finite number.", {"feature": name})
        limits = PHYSICAL_LIMITS.get(name)
        if limits and not limits[0] <= value <= limits[1]:
            raise WorkflowError(
                "physically-impossible",
                f"{name} = {value} is outside the physically plausible range "
                f"[{limits[0]}, {limits[1]}] for this quantity.", {"feature": name,
                                                                 "value": value,
                                                                 "limits": list(limits)})
        values.append(value)

    domain_warnings = research._domain_warnings(model, values)
    checks["domainWarnings"] = domain_warnings
    checks["insideTrainingDomain"] = not domain_warnings
    checks["checksApplied"] = [
        "schema-exact-feature-set",
        "finite-values",
        "physically-plausible-range",
        "training-domain-range",
        "scientific-category-not-6",
    ]
    return {"model": model, "values": values, "checks": checks,
            "classification": classification}


def run_model(model_id: str, inputs: dict) -> dict:
    """Validate, run the served inference, and attach interpretation and provenance."""
    if model_id in research.EXTERNAL_SERVICES:
        service = research.EXTERNAL_SERVICES[model_id]
        raise WorkflowError(
            "external-service",
            (f"{model_id} is not run through this workflow: it is served by "
             f"{service['servedBy']} at {service['endpoint']}. Call that endpoint with a daily "
             "weather summary; this workflow drives the JSON-artifact models."),
            {"endpoint": service["endpoint"],
             "cardEndpoint": service["cardEndpoint"],
             "reason": service["why"]})
    validated = validate_input(model_id, inputs)
    model = validated["model"]
    values = validated["values"]
    classification = validated["classification"]

    registry_row = next((m for m in research.model_registry()["models"]
                         if m["id"] == model_id), {})
    family = INPUT_FAMILY.get(model_id, "unknown")
    if family == "gene-expression":
        probabilities = research.predict_probabilities(model, values)
        peak = max(probabilities, key=probabilities.get)
        output = {"kind": "classification",
                  "isMeasurement": False,
                  "prediction": peak,
                  "probabilities": {k: round(v, 6) for k, v in probabilities.items()},
                  "calibrated": False,
                  "note": ("Class probabilities are the evaluator's softmax output. They "
                           "are not calibrated probabilities: no calibration was measured "
                           "for this model, so they must not be read as confidence.")}
        interpretation = (f"The model assigns the largest probability to class "
                          f"'{peak}'. This is a classification of the applied "
                          f"experimental condition, not a measurement of dose, damage or "
                          f"yield.")
    else:
        raw, warnings = research.predict_values(model, values)
        # A model fitted on log(y) returns log(y). The transform is declared in the artifact, so it
        # is undone here as well as in the dedicated route - otherwise the workflow would report
        # 4.8 where the answer is 5924 g/m2 and nothing in the response would look wrong.
        value = research.inverse_target_transform(model, raw)
        interval = model.get("interval") or {}
        radius = interval.get("radius")
        workflow_meta = model.get("workflow") or {}
        unit = workflow_meta.get("unit") or model.get("unit")
        if radius is not None:
            bounds = {"low": max(0.0, value - radius), "high": value + radius,
                      "kind": interval.get("kind")}
        elif interval.get("logResidualLow") is not None:
            # Log-target intervals are ratios, so they scale with the prediction rather than
            # adding a fixed radius that would be meaningless across two orders of magnitude.
            bounds = {"low": max(0.0, value * math.exp(interval["logResidualLow"])),
                      "high": value * math.exp(interval["logResidualHigh"]),
                      "kind": interval.get("kind")}
        else:
            bounds = None
        output = {"kind": "regression",
                  "isMeasurement": False,
                  "prediction": value,
                  "unit": unit,
                  "interval": bounds,
                  "calibrated": False,
                  "note": ("The interval radius comes from conformal calibration on the "
                           "training distribution. Its measured coverage is reported "
                           "separately and is not a guarantee.")}
        if workflow_meta.get("note"):
            output["scopeNote"] = workflow_meta["note"]
        interpretation = (f"The model estimates {value:.4g} {unit or ''}. "
                          f"This is a model output, not a measurement of a real plant.")
        if warnings:
            output["warnings"] = warnings

    from app import assistant as assistant_module
    narrative = assistant_module.answer(
        f"What does {model_id} predict and what are its limitations?")
    narrative_body = narrative.render()

    return {
        "modelId": model_id,
        "workflow": ["validate-input", "run-inference", "interpret", "attach-limitations",
                     "attach-provenance"],
        "inputs": inputs,
        "validation": validated["checks"],
        "output": output,
        "interpretation": interpretation,
        "limitations": (registry_row.get("limitations") or [])[:6],
        "provenance": {
            "sourceStudy": registry_row.get("sourceStudy"),
            "sourceUrl": registry_row.get("sourceUrl"),
            "sourceType": registry_row.get("sourceType"),
            "artifactSha256": registry_row.get("artifactSha256"),
            "validationProtocol": registry_row.get("validation"),
            "samples": registry_row.get("samples"),
            "groups": registry_row.get("groups"),
        },
        "scientificClassification": {
            "category": classification.category,
            "categoryName": registry_row.get("scientificClassification", {}).get("categoryName"),
            "serviceAllowed": registry_row.get("scientificClassification", {}).get("serviceAllowed"),
        },
        "calibration": registry_row.get("calibration"),
        "explanationAvailable": bool(registry_row.get("explanationAvailable")),
        "evidence": narrative_body,
        "reproducible": {
            "artifactPinnedBySha256": True,
            "deterministic": True,
            "note": "The same inputs and the same pinned artifact produce the same output.",
        },
    }
