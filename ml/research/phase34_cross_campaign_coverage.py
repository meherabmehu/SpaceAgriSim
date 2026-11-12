"""Phase 34: does the lettuce model's 90 % interval hold outside the campaign it was fitted on?

The audit carries four calibration-scope gaps of the same shape:

    lettuce-earth-growth-v1 / -v2 / mizuna-microbial-load-v1 / -relative-load-v2
        measured coverage is within the documented campaigns, not across campaigns

For the lettuce pair the statement is literally true and has never been quantified: coverage was
measured by leaving out whole WUR experiments from the same four-experiment set, which is
within-campaign by construction. This script measures the same interval against a *separate*
study that no part of training ever saw:

    Wicharuck et al. 2024, PeerJ 12:e17085, doi:10.7717/peerj.17085  (CC BY 4.0)
    six treatment means (2 cultivars x 3 vertical levels), 28 days after transplant,
    air 27.5 C, photoperiod 12 h, PPFD 322 / 391 / 697 umol m-2 s-1, 48 plants per m2.

The transcription is already committed at `data/literature/external_lettuce_peerj17085`
(every number copied from the open-access full text; no value read off a figure). Nothing here
re-transcribes or interpolates it.

What the number means, and what it does not
-------------------------------------------
Six treatment means from one greenhouse are not a validation set; they are a **measured
cross-campaign check**. Counting how many of them fall inside the served interval is the honest
way to state what the interval can be expected to do outside the fitted campaign. The count is
reported as coverage of n=6 with the individual rows shown, never as a proportion with a
confidence interval, because a proportion over six correlated means would look more precise than
it is.

Predictions come from the shipped artifacts through the same code the API uses
(`app.research.predict_values` + `inverse_target_transform`), so this measures the served model,
not a re-fit of it.

The mizuna pair is handled the same way, from the committed out-of-fold predictions of the two
VEG-04 campaigns in OSD-780: the conformal radius is fitted on one campaign and its coverage is
measured on the other. That is the measurement the audit says is missing.

Output: ml/evaluation/phase34_cross_campaign_coverage
Run:    python ml/research/phase34_cross_campaign_coverage.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
sys.path.insert(0, str(ROOT / "backend"))

from app import research  # noqa: E402

ARTIFACTS = ROOT / "ml" / "artifacts"
OBSERVATIONS = ROOT / "data" / "literature" / "external_lettuce_peerj17085"
TARGET = ROOT / "ml" / "evaluation" / "phase34_cross_campaign_coverage"

# v1 is superseded but still shipped for reproducibility, so its interval is measured too: leaving
# one of the four audit findings unmeasured would make the record incomplete for no reason.
MODELS = ("lettuce-earth-growth-v1", "lettuce-earth-growth-v2", "lettuce-earth-growth-v3")

# Committed out-of-fold predictions: one row per sample, predicted by a fold that never saw it.
MIZUNA = {
    "mizuna-microbial-load-v1": {
        "outOfFold": ROOT / "ml" / "evaluation" / "microbial_out_of_fold.csv",
        "truth": "log10CfuPerG",
        "prediction": "prediction",
        "campaign": "experiment",
    },
    "mizuna-microbial-relative-load-v2": {
        "outOfFold": ROOT / "ml" / "evaluation" / "microbial_v2_out_of_fold.csv",
        "truth": "relativeTarget",
        "prediction": "ridgeFit",
        "campaign": "experiment",
    },
}
COVERAGE = 0.9


def external_rows() -> tuple[list[dict], dict]:
    record = safedata.load(OBSERVATIONS)
    conditions = record["studyConditions"]
    rows = []
    for observation in record["observations"]:
        photoperiod = float(conditions["photoperiodHours"])
        ppfd = float(observation["ppfdUmol"])
        rows.append({
            "id": observation["id"],
            "cultivar": observation["cultivar"],
            "level": observation["level"],
            "daysAfterTransplant": float(observation["daysAfterTransplant"]),
            "airTemperatureC": float(conditions["airTemperatureC"]),
            "rootTemperatureC": float(conditions["airTemperatureC"]),
            "ppfd": ppfd,
            "dailyLightIntegral": round(ppfd * photoperiod * 3600.0 / 1e6, 3),
            "measuredGPerPlant": float(observation["freshWeightGPerPlant"]),
            "sdG": float(observation["sd"]),
            "replicates": int(observation["n"]),
            "plantsPerM2": float(conditions["plantDensityPerM2"]),
        })
    return rows, record["source"]


def interval_for(model: dict, per_plant: float) -> tuple[float, float, str]:
    """The served interval for one prediction, using the artifact's own definition.

    v2 serves an absolute radius on a per-plant target. v3 serves conformal quantiles on the log
    *per-square-metre* target, which the route multiplies in and then divides by the planting
    density; the same arithmetic is applied here so the number is the one a caller receives.
    """
    interval = model["interval"]
    if "radius" in interval:
        radius = float(interval["radius"])
        return max(0.0, per_plant - radius), per_plant + radius, interval.get("kind", "absolute radius")
    low = per_plant * float(np.exp(interval["logResidualLow"]))
    high = per_plant * float(np.exp(interval["logResidualHigh"]))
    return low, high, interval.get("kind", "log-residual quantiles")


def evaluate(model_id: str, rows: list[dict]) -> dict:
    model = research.load_model(model_id)  # verifies the SHA-256 against the registry
    features = model["features"]
    predictions = []
    for row in rows:
        values = []
        for name in features:
            if name == "dailyLightIntegral":
                values.append(row["dailyLightIntegral"])
            elif name == "ppfd":
                values.append(row["ppfd"])
            elif name == "airTemperature":
                values.append(row["airTemperatureC"])
            elif name == "rootTemperature":
                values.append(row["rootTemperatureC"])
            elif name == "daysAfterTransplant":
                values.append(row["daysAfterTransplant"])
            else:  # pragma: no cover - a new feature must be handled explicitly
                raise SystemExit(f"{model_id}: no mapping for feature {name!r}")
        raw, warnings = research.predict_values(model, values)
        predicted = research.inverse_target_transform(model, raw)
        # A per-area target is divided by the campaign's planting density, exactly as the served
        # route does, instead of being compared to a per-plant measurement as if it were one.
        if "PerM2" in str(model.get("target", "")):
            predicted = predicted / row["plantsPerM2"]
        low, high, kind = interval_for(model, predicted)
        covered = bool(low <= row["measuredGPerPlant"] <= high)
        predictions.append({
            **row,
            "predictedGPerPlant": round(float(predicted), 2),
            "intervalLow": round(float(low), 2),
            "intervalHigh": round(float(high), 2),
            "intervalKind": kind,
            "covered": covered,
            "ratio": round(float(predicted) / row["measuredGPerPlant"], 3),
            "absoluteErrorG": round(abs(float(predicted) - row["measuredGPerPlant"]), 2),
            "domainWarnings": warnings,
        })
    covered = sum(1 for row in predictions if row["covered"])
    ratios = np.array([row["ratio"] for row in predictions], dtype=float)
    within = float(((ratios >= 0.5) & (ratios <= 2.0)).mean())
    return {
        "model": model_id,
        "target": model.get("target"),
        "unit": model.get("unit"),
        "intervalKind": predictions[0]["intervalKind"] if predictions else None,
        "withinCampaignCoverage": next(
            (model["interval"][key] for key in
             ("achievedCoverage", "empiricalCoverage", "outOfFoldCoverage")
             if model["interval"].get(key) is not None), None),
        "crossCampaign": {
            "observations": len(predictions),
            "covered": covered,
            "achievedCoverage": round(covered / len(predictions), 4),
            "ratioMedian": round(float(np.median(ratios)), 3),
            "ratioMin": round(float(ratios.min()), 3),
            "ratioMax": round(float(ratios.max()), 3),
            "shareWithinFactorOfTwo": round(within, 4),
            "rows": predictions,
        },
    }


def evaluate_campaigns(model_id: str, spec: dict) -> dict:
    """Fit the conformal radius on one campaign and measure its coverage on the other.

    This is the cross-campaign version of the split-conformal measurement the artifacts already
    carry: same nominal level, same residual definition, but calibration and evaluation never come
    from the same campaign.
    """
    import pandas as pd

    frame = pd.read_csv(spec["outOfFold"])
    truth = frame[spec["truth"]].to_numpy(dtype=float)
    predicted = frame[spec["prediction"]].to_numpy(dtype=float)
    campaign = frame[spec["campaign"]].astype(str).to_numpy()
    # mizuna-microbial-load-v1 is superseded and has no served route, so its card is read from
    # disk. Only the two served estimators below go through the API's loader.
    model = safedata.load(ARTIFACTS / f"{model_id}")

    residual = np.abs(truth - predicted)
    directions = {}
    for calibration in sorted(set(campaign)):
        for evaluation in sorted(set(campaign)):
            if calibration == evaluation:
                continue
            on_calibration = campaign == calibration
            on_evaluation = campaign == evaluation
            radius = float(np.quantile(residual[on_calibration], COVERAGE, method="higher"))
            covered = int((residual[on_evaluation] <= radius).sum())
            total = int(on_evaluation.sum())
            directions[f"calibratedOn{calibration}/evaluatedOn{evaluation}"] = {
                "radius": round(radius, 4),
                "covered": covered,
                "observations": total,
                "achievedCoverage": round(covered / total, 4),
            }

    pooled = [entry for entry in directions.values()]
    covered_total = sum(entry["covered"] for entry in pooled)
    observations_total = sum(entry["observations"] for entry in pooled)
    return {
        "model": model_id,
        "target": model.get("target"),
        "unit": model.get("unit"),
        "withinCampaignCoverage": (model["interval"].get("empiricalCoverage")
                                   or model["interval"].get("achievedCoverage")),
        "campaigns": sorted(set(campaign)),
        "method": ("90th percentile of |residual| on the calibration campaign, applied unchanged to "
                   "the other campaign; both directions reported, then pooled"),
        "directions": directions,
        "crossCampaign": {
            "covered": covered_total,
            "observations": observations_total,
            "pooledAchievedCoverage": round(covered_total / observations_total, 4),
        },
    }


def main() -> int:
    rows, source = external_rows()
    report = {
        "schema": "spaceagrisim.cross_campaign_coverage/1",
        "phase": 34,
        "generatedBy": "ml/research/phase34_cross_campaign_coverage.py",
        "question": ("Of the served lettuce predictions, how many independent-campaign treatment "
                     "means fall inside the served 90 % interval? Within-campaign coverage was "
                     "already measured by leaving out WUR experiments; that is not the same "
                     "question and this is the measurement that was missing."),
        "campaign": {
            "study": "Wicharuck et al. 2024, PeerJ 12:e17085",
            "doi": source["doi"],
            "licence": source["license"],
            "transcription": str(OBSERVATIONS.relative_to(ROOT)),
            "transcribedBy": "manual copy from the open-access full text; no value read off a figure",
            "system": "Thai greenhouse, six shelves at three levels, no supplemental light",
            "units": ("measured fresh weight is g per plant; the models' targets are converted by "
                      "the served code path, not by this script re-deriving a density"),
            "independenceUnit": "cultivar x shelf level (six treatment means; three replicates each)",
        },
        "rule": ("No refitting. Every prediction uses the committed artifact through "
                 "app.research.predict_values, the same path the API serves, with the artifact's "
                 "own interval definition. A coverage count over six correlated treatment means "
                 "is reported as a count, not as a proportion with a confidence interval."),
        "models": {},
    }

    for model_id in MODELS:
        result = evaluate(model_id, rows)
        result["kind"] = "independent-campaign predictions from the shipped artifacts"
        report["models"][model_id] = result

    for model_id, spec in MIZUNA.items():
        result = evaluate_campaigns(model_id, spec)
        result["kind"] = "cross-campaign conformal coverage from committed out-of-fold predictions"
        report["models"][model_id] = result
        campaign = result["crossCampaign"]
        print(f"{model_id}: within-campaign {result['withinCampaignCoverage']}, "
              f"cross-campaign {campaign['covered']}/{campaign['observations']} "
              f"(pooled {campaign['pooledAchievedCoverage']})")

    # The wording that goes into the model cards and the served scope is derived from the numbers,
    # so a card cannot drift away from its own measurement.
    for model_id, result in report["models"].items():
        campaign = result["crossCampaign"]
        if result["kind"].startswith("cross-campaign conformal"):
            result["statement"] = (
                f"Within-campaign coverage over both VEG-04 campaigns is "
                f"{result['withinCampaignCoverage']}. Calibrating the 90 % radius on one campaign "
                f"and evaluating it on the other covers {campaign['covered']} of "
                f"{campaign['observations']} samples (pooled {campaign['pooledAchievedCoverage']} "
                f"across both directions). The campaign offset is not a function of the features, "
                "so this is the bound that matters when the model meets a third campaign."
            )
            print(f"  {result['statement']}")
            continue
        covered = campaign["covered"]
        total = campaign["observations"]
        outcome = (
            f"covered {covered} of {total} independent treatment means"
            if covered else
            f"did not cover any of the {total} independent treatment means"
        )
        result["statement"] = (
            f"Within the four WUR experiments the 90 % interval covered "
            f"{result['withinCampaignCoverage']}. Against the independent PeerJ 2024 campaign it "
            f"{outcome} (prediction/measurement ratio median {campaign['ratioMedian']}, range "
            f"{campaign['ratioMin']}-{campaign['ratioMax']}). "
            + ("A wide interval covering six correlated greenhouse means is not evidence of "
               "accuracy: this model's declared independent holdout (Touliatos et al. 2016) "
               "missed its pre-registered 30 % MAPE criterion, and that failure stands. "
               if covered else
               "The interval therefore describes the fitted campaign and must not be read as a "
               "90 % coverage claim outside it. ")
            + "PeerJ 2024 was already used as a development check before this measurement, so it "
              "is a cross-campaign measurement, not an untouched holdout."
        )
        print(f"  {result['statement']}")

    safedata.dump(report, TARGET)
    print(f"wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
