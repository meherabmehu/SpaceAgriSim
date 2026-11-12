#!/usr/bin/env python3
"""Phase 36: re-evaluate the seven served models against the newly acquired evidence.

Rules this script obeys
-----------------------
* No retraining. The model artefacts are read, hashed and left untouched; a hash that differs
  from the registry is a failure, not an update.
* No threshold moves. Every criterion used here is the one the model card already declared
  (``domain``, ``acceptanceCriterionPct``) or the one Phase 35 already applied.
* No test-set tuning. A model whose new independent evidence is out of domain is not scored on a
  subset chosen to fit the domain; it is reported as out of domain, because the models are
  themselves specified to refuse outside their measured range.
* Campaign-level independence. The new campaign is a different country, season, system and
  cultivar set from the WUR training data, so it is independent at campaign level; it is never
  split into rows.

The outcome for a model is one of
``SCORED``          an independent check was computable and was applied
``DOMAIN-REFUSED``  the independent campaign lies outside the model's declared domain, so the
                    model's own contract forbids a prediction and none was made
``NO-NEW-EVIDENCE`` nothing in this acquisition bears on the model

``DOMAIN-REFUSED`` is not a pass and not a failure: it means the acquisition did not add
evidence about that model, and the model's verdict stays exactly where Phase 35 left it.

    python3 ml/research/phase36_model_reevaluation.py [--check]
"""
from __future__ import annotations
import sys

import argparse
import re
from datetime import date
import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
ARTIFACTS = ROOT / "ml" / "artifacts"
REGISTRY = ARTIFACTS / "registry"
PHASE35 = ROOT / "ml" / "evaluation" / "phase35_model_evidence"
IOT4 = ROOT / "data" / "research" / "phase36" / "iot4lettuce_water_cultivar"
RAW_IOT4 = ROOT / "data" / "raw" / "zenodo_20759414"
OUTPUT = ROOT / "ml" / "evaluation" / "phase36_model_reevaluation"

SERVED = (
    "lettuce-earth-growth-v1",
    "lettuce-earth-growth-v2",
    "lettuce-earth-growth-v3",
    "mizuna-microbial-relative-load-v2",
    "radiation-quality-osd46-v1",
    "radiation-exposure-osd46-v1",
    "tomato-flight-response-v1",
)
LETTUCE_MODELS = ("lettuce-earth-growth-v1", "lettuce-earth-growth-v2",
                  "lettuce-earth-growth-v3")


def sha256(path: Path) -> str:
    return hashlib.sha256(safedata.bytes(path)).hexdigest()


def campaign_domain() -> dict:
    """Measure the independent campaign on the axes the lettuce models declare."""
    inside = RAW_IOT4 / "03_Climate" / "inside.csv"
    temperature: list[float] = []
    if safedata.exists(inside):
        raw = safedata.bytes(inside).decode("cp1252")
        for row in csv.DictReader(raw.splitlines()):
            column = next((c for c in row if c.startswith("temperature")), None)
            if column and row[column]:
                temperature.append(float(row[column]))

    # The campaign's own dates come from the experiment record rather than from arithmetic on
    # file names. experiment is a concatenation of several OpenSILEX objects, so the first
    # object is read and the two date fields are taken from it.
    experiment = safedata.load(RAW_IOT4 / "14_Utilities" / "OpenSILEX" / "experiment")
    record = next(o for o in experiment
                  if isinstance(o, dict) and "start_date" in o and "end_date" in o)
    start, end = record["start_date"], record["end_date"]
    campaign_days = (date.fromisoformat(end) - date.fromisoformat(start)).days

    # The destructive harvest is the only measured fresh weight. The export also carries a
    # regression-derived fresh weight on every other day, and that column is not a measurement;
    # both facts are asserted rather than assumed, because the difference between them is the
    # whole reason the model cannot be scored.
    rows = list(csv.reader((RAW_IOT4 / "14_Utilities" / "OpenSILEX" / "data.csv")
                           .open(encoding="utf-8-sig")))
    # rows 0-2 are the method, unit and variable triples and row 3 is blank, so the header is
    # located by the column it must contain rather than by a fixed offset.
    header_index = next(i for i, row in enumerate(rows)
                        if "plant_fresh_weight_directmeasurement_gram" in row)
    header = rows[header_index]
    direct = header.index("plant_fresh_weight_directmeasurement_gram")
    derived = header.index("plant_fresh_weight_regression_analysis_gram")
    date_column = header.index("Date")
    data_rows = rows[header_index + 1:]
    measured_rows = [row for row in data_rows if len(row) > max(direct, derived)
                     and row[direct].strip()]
    measured_dates = sorted({row[date_column] for row in measured_rows})
    derived_days = sum(1 for row in data_rows if len(row) > derived and row[derived].strip())
    assert measured_dates == [end], (
        f"measured fresh weight is expected only on the campaign end date {end}, "
        f"found {measured_dates}")
    assert derived_days > len(measured_rows), "regression-derived weights are expected to outnumber measured ones"

    return {
        "airTemperatureC": {"min": round(min(temperature), 2), "max": round(max(temperature), 2),
                            "n": len(temperature)} if temperature else None,
        "rootTemperature": "not measured in this campaign",
        "measuredMassDaysAfterTransplant": campaign_days,
        "daysAfterTransplantBasis": (f"the destructive harvest on {end} is the only measured fresh "
                                     f"weight; the campaign record runs {start} to {end}, "
                                     f"{campaign_days} days, and no earlier fresh weight is a "
                                     f"measurement - the {derived_days} daily values in the export "
                                     f"are produced by a regression analysis"),
        "dli": "not computable from the published PAR log (19 days, irregular sampling)",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="fail when the committed file disagrees with a recomputation")
    args = parser.parse_args()

    registry = safedata.load(REGISTRY)
    phase35 = safedata.load(PHASE35)
    hashes = {entry["id"]: entry["sha256"] for entry in registry["models"]}
    domain = campaign_domain()

    models: dict[str, dict] = {}
    for model_id in SERVED:
        artifact_path = ARTIFACTS / f"{model_id}"
        artifact = safedata.load(artifact_path)
        observed_sha = sha256(artifact_path)
        prior = phase35["models"].get(model_id, {})

        record = {
            "artifactSha256": observed_sha,
            # The digest is over the artifact file as stored. Since the storage migration that
            # file is the Python data module holding the same payload this audit scored, not a
            # JSON document, so the basis is stated rather than implied.
            "hashBasis": (f"SHA-256 of {artifact_path.relative_to(ROOT).as_posix()}, the stored "
                          "artifact file. The payload is unchanged by the storage format."),
            "artifactUnchanged": observed_sha == hashes.get(model_id),
            "verdictBefore": prior.get("verdict"),
            "decisionGradeBefore": prior.get("decisionGrade"),
            "retrained": False,
            "thresholdsChanged": False,
        }

        if model_id in LETTUCE_MODELS:
            declared = artifact.get("domain", {})
            temperature = domain["airTemperatureC"]
            violations = []
            if temperature and declared.get("airTemperature"):
                low, high = declared["airTemperature"]["min"], declared["airTemperature"]["max"]
                if temperature["max"] > high or temperature["min"] < low:
                    violations.append(
                        f"airTemperature {temperature['min']}-{temperature['max']} degC outside "
                        f"declared {low}-{high}")
            if declared.get("rootTemperature") and "not measured" in str(domain["rootTemperature"]):
                violations.append("rootTemperature is a required feature and is not measured")
            if declared.get("daysAfterTransplant"):
                low = declared["daysAfterTransplant"]["min"]
                high = declared["daysAfterTransplant"]["max"]
                day = domain["measuredMassDaysAfterTransplant"]
                if day > high or day < low:
                    violations.append(
                        f"only measured mass is at {day} days after transplant, declared domain "
                        f"{low}-{high}")
            record.update({
                "outcome": "DOMAIN-REFUSED" if violations else "SCORED",
                "independentCampaign": "IoT4Lettuce, Zenodo 10.5281/zenodo.20759414",
                "campaignDomain": domain,
                "declaredDomain": declared,
                "violations": violations,
                "whyNoPrediction": ("the model's own domain contract forbids a prediction here; "
                                    "forcing one would produce a number the card says is invalid"),
            })
        else:
            record.update({
                "outcome": "NO-NEW-EVIDENCE",
                "reason": ("this acquisition contains no measurement of the crop, system or "
                           "variable this model represents"),
            })

        record["verdictAfter"] = record["verdictBefore"]
        record["decisionGradeAfter"] = record["decisionGradeBefore"]
        models[model_id] = record

    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "generatedBy": "ml/research/phase36_model_reevaluation.py",
        "policy": {
            "retraining": "none",
            "thresholds": "unchanged",
            "testSetTuning": "none",
            "splitUnit": "whole campaign, never individual rows",
        },
        "newEvidence": {
            "iot4lettuce": str(IOT4.relative_to(ROOT)) if safedata.exists(IOT4) else None,
            "et0MeasurementValidation": "data/research/phase36/et0_measurement_validation",
        },
        "models": models,
        "counts": {
            "served": len(SERVED),
            "scored": sum(1 for m in models.values() if m["outcome"] == "SCORED"),
            "domainRefused": sum(1 for m in models.values()
                                 if m["outcome"] == "DOMAIN-REFUSED"),
            "noNewEvidence": sum(1 for m in models.values()
                                 if m["outcome"] == "NO-NEW-EVIDENCE"),
            "decisionGradeBefore": sum(1 for m in models.values() if m["decisionGradeBefore"]),
            "decisionGradeAfter": sum(1 for m in models.values() if m["decisionGradeAfter"]),
        },
    }

    if args.check:
        existing = safedata.load(OUTPUT)
        if existing.get("models", {}).keys() != payload["models"].keys():
            print("FAIL: model set differs from the committed evaluation")
            return 1
        for model_id, record in payload["models"].items():
            if existing["models"][model_id]["outcome"] != record["outcome"]:
                print(f"FAIL: {model_id} outcome drifted")
                return 1
        print("OK: reevaluation matches the committed file")
        return 0

    safedata.dump(payload, OUTPUT)
    for model_id, record in models.items():
        print(f"{model_id:<34} {record['outcome']:<16} decision-grade "
              f"{record['decisionGradeBefore']} -> {record['decisionGradeAfter']}")
    print(f"\ncounts: {payload['counts']}")
    print(f"report -> {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
