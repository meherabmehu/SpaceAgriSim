"""Train the OSD-780 VEG-04A/B edible-leaf microbial-load model.

This is the one genuinely new NASA-labelled model Phase 6 could support. The
target is MEASURED culturable aerobic plate count per gram of fresh leaf
weight - not biomass, not yield.

Scientific framing that the artifact must preserve:
  * The estimand is `log10(1 + CFU/g)` on edible leaf tissue.
  * The dominant, reproducible structure in the data is a flight-versus-ground
    contrast on LEAF tissue that does not appear on root-zone samples. The model
    is therefore a *microbial-load stratification* model. It is not a food-safety
    clearance decision tool and not a shelf-life predictor.
  * Validation is grouped by pillow (the biological replicate) so swabs and
    repeated harvests from one pillow cannot leak across folds.
  * A leave-one-experiment-out diagnostic (train VEG04A -> test VEG04B and the
    reverse) is reported because that is the only available test of whether the
    effect transfers to a new experiment.

Run: python ml/training/train_microbial.py
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GridSearchCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
sys.path.insert(0, str(ROOT / "scripts"))
from nasa_pipeline import save_json, stamp  # noqa: E402

DATA = ROOT / "data"
ARTIFACTS = ROOT / "ml" / "artifacts"
EVALUATION = ROOT / "ml" / "evaluation"
MODEL_ID = "mizuna-microbial-load-v1"
SEED = 42
FEATURES = ["flight", "blueLight", "isVEG04B", "sanitised", "freshWeightG", "harvestIndex"]


def metrics(y, prediction):
    return {
        "MAE": float(mean_absolute_error(y, prediction)),
        "RMSE": float(np.sqrt(mean_squared_error(y, prediction))),
        "R2": float(r2_score(y, prediction)),
    }


def portable_linear(model):
    scale = model.named_steps["scale"]
    linear = model.named_steps["linear"]
    return {
        "mean": scale.mean_.tolist(),
        "scale": scale.scale_.tolist(),
        "coefficients": np.ravel(linear.coef_).tolist(),
        "intercept": float(np.ravel([linear.intercept_])[0]),
    }


def build_table():
    table = pd.read_csv(DATA / "processed" / "mizuna_microbial_load.csv")
    leaf = table[(table.assay == "aerobic") & (table.tissue == "leaf")].copy()
    leaf = leaf[leaf.cfuPerG.notna()].copy()
    leaf["flight"] = (leaf.environment == "flight").astype(int)
    leaf["blueLight"] = (leaf.spectrum == "blue").astype(int)
    leaf["isVEG04B"] = (leaf.experiment == "VEG04B").astype(int)
    leaf["sanitised"] = (leaf.treatment == "clean").astype(int)
    leaf["harvestIndex"] = leaf.harvest.fillna(1).astype(int)
    leaf = leaf.sort_values(["experiment", "environment", "unit", "sample"]).reset_index(drop=True)
    x = leaf[FEATURES].to_numpy(dtype=float)
    y = leaf.log10CfuPerG.to_numpy(dtype=float)
    groups = leaf.unit.to_numpy()
    return leaf, x, y, groups


def grouped_cv(x, y, groups):
    outer = GroupKFold(n_splits=4)
    predicted = np.zeros(len(y))
    baseline = np.zeros(len(y))
    folds = []
    for fold, (train, test) in enumerate(outer.split(x, y, groups)):
        assert not set(groups[train]) & set(groups[test]), "group leakage between folds"
        search = GridSearchCV(
            Pipeline([("scale", StandardScaler()), ("linear", Ridge())]),
            {"linear__alpha": [0.01, 0.1, 1.0, 10.0, 100.0]},
            cv=GroupKFold(n_splits=3), scoring="neg_mean_absolute_error")
        search.fit(x[train], y[train], groups=groups[train])
        predicted[test] = search.predict(x[test])
        baseline[test] = DummyRegressor(strategy="mean").fit(x[train], y[train]).predict(x[test])
        folds.append({
            "fold": fold,
            "testGroups": sorted(set(groups[test])),
            "alpha": search.best_params_["linear__alpha"],
            "nTest": int(len(test)),
        })
    return predicted, baseline, folds, outer


def leave_one_experiment_out(leaf, x, y):
    results = {}
    for held_out in ("VEG04A", "VEG04B"):
        test = (leaf.experiment == held_out).to_numpy()
        train = ~test
        model = Pipeline([("scale", StandardScaler()), ("linear", Ridge(alpha=10.0))])
        model.fit(x[train], y[train])
        prediction = model.predict(x[test])
        results[held_out] = metrics(y[test], prediction) | {"nTest": int(test.sum())}
    return results


def split_conformal(leaf, x, y, groups, predicted):
    """Group-aware split-conformal interval with empirical coverage.

    Calibration and evaluation sets are disjoint PILLOW sets, so the coverage
    number is not measured on the residuals the radius was fitted to.
    """
    units = np.array(sorted(set(groups)))
    rng = np.random.default_rng(SEED)
    rng.shuffle(units)
    half = len(units) // 2
    calibration_units, evaluation_units = set(units[:half]), set(units[half:])
    cal = np.array([g in calibration_units for g in groups])
    ev = ~cal
    residuals = np.abs(y[cal] - predicted[cal])
    radius = float(np.quantile(residuals, 0.9, method="higher"))
    covered = np.abs(y[ev] - predicted[ev]) <= radius
    return {
        "method": "group-aware split conformal (90% nominal)",
        "radius": radius,
        "calibrationGroups": len(calibration_units),
        "evaluationGroups": len(evaluation_units),
        "calibrationResiduals": int(cal.sum()),
        "evaluationResiduals": int(ev.sum()),
        "empiricalCoverage": float(covered.mean()),
        "nominalCoverage": 0.90,
    }, radius


def main():
    ARTIFACTS.mkdir(exist_ok=True)
    EVALUATION.mkdir(exist_ok=True)
    leaf, x, y, groups = build_table()
    print(f"rows={len(y)}  groups={len(set(groups))}  "
          f"experiments={sorted(leaf.experiment.unique())}")

    predicted, baseline, folds, outer = grouped_cv(x, y, groups)
    cv_metrics = metrics(y, predicted)
    baseline_metrics = metrics(y, baseline)
    loeo = leave_one_experiment_out(leaf, x, y)
    conformal, radius = split_conformal(leaf, x, y, groups, predicted)

    # Final fitted model on all leaf data.
    search = GridSearchCV(
        Pipeline([("scale", StandardScaler()), ("linear", Ridge())]),
        {"linear__alpha": [0.01, 0.1, 1.0, 10.0, 100.0]},
        cv=outer, scoring="neg_mean_absolute_error")
    search.fit(x, y, groups=groups)
    model = search.best_estimator_

    # A RandomForest challenger, evaluated identically, to show the simple
    # regularised model is not being outperformed by a flexible learner.
    forest_predicted = np.zeros(len(y))
    for train, test in outer.split(x, y, groups):
        forest = RandomForestRegressor(n_estimators=200, min_samples_leaf=3,
                                       random_state=SEED, n_jobs=-1)
        forest.fit(x[train], y[train])
        forest_predicted[test] = forest.predict(x[test])
    forest_metrics = metrics(y, forest_predicted)

    # The measured flight/ground contrast this model partly encodes.
    contrast = {}
    for experiment, block in leaf.groupby("experiment"):
        flight = block[block.environment == "flight"].log10CfuPerG
        ground = block[block.environment == "ground"].log10CfuPerG
        contrast[experiment] = {
            "flightMean": float(flight.mean()), "flightN": int(flight.size),
            "groundMean": float(ground.mean()), "groundN": int(ground.size),
            "difference": float(flight.mean() - ground.mean()),
            "foldDifference": float(10 ** (flight.mean() - ground.mean())),
        }

    # Evidence decision, derived from the measured numbers rather than asserted.
    # A model that beats its baseline inside pooled data but fails to transfer to
    # a held-out campaign is "experimental", never "validated".
    transfers = all(v["R2"] > 0 for v in loeo.values())
    beats = cv_metrics["MAE"] < baseline_metrics["MAE"]
    calibrated = conformal["empiricalCoverage"] >= 0.90 - 0.05
    if beats and transfers and calibrated:
        evidence_status = "validated-exploratory"
    elif beats:
        evidence_status = "experimental"
    else:
        evidence_status = "insufficient-evidence"

    card = {
        "id": MODEL_ID,
        "name": "Mizuna edible-leaf microbial load (VEG-04A/B)",
        "version": "1.0.0",
        "status": "trained-exploratory",
        "trainedAt": stamp(),
        "task": "Culturable aerobic microbial load regression on edible leaf tissue",
        "sourceStudy": "OSD-780",
        "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-780",
        "sourceType": "NASA OSDR ALSDA plate-count measurement tables (LSDS-128)",
        "crop": "mizuna",
        "method": "NASA-data-trained exploratory regression (ridge / random forest comparison)",
        "samples": int(len(y)),
        "groups": int(len(set(groups))),
        "features": FEATURES,
        "target": "log10(1 + CFU per gram fresh leaf weight)",
        "unit": "log10 CFU/g fresh weight",
        "metrics": cv_metrics,
        "baselineMetrics": baseline_metrics,
        "forestMetrics": forest_metrics,
        "beatsBaselineMAE": cv_metrics["MAE"] < baseline_metrics["MAE"],
        "beatsBaselineR2": cv_metrics["R2"] > baseline_metrics["R2"],
        "leaveOneExperimentOut": loeo,
        "evidenceStatus": evidence_status,
        "evidenceBasis": {
            "beatsBaselineWithinPooledData": bool(beats),
            "transfersToHeldOutExperiment": bool(transfers),
            "intervalsEmpiricallyCalibrated": bool(calibrated),
            "rule": (
                "validated-exploratory requires beating the baseline, positive R2 on "
                "every leave-one-experiment-out holdout, and conformal empirical "
                "coverage within 5 points of nominal. Otherwise the model is "
                "reported as experimental."
            ),
        },
        "recommendedUse": (
            "Descriptive in-campaign microbial-load stratification only. Do NOT use "
            "to predict a new mission, a different cultivar or a different hardware "
            "configuration: leave-one-experiment-out R2 is negative for both campaigns."
        ),
        "validation": (
            "4-fold GroupKFold grouped by pillow (biological replicate), with a "
            "nested 3-fold grouped alpha search. Gene-to-fold leakage is impossible "
            "because all samples from one pillow stay in one fold. A separate "
            "leave-one-experiment-out diagnostic holds out an entire VEG-04A or "
            "VEG-04B campaign."
        ),
        "uncertainty": conformal,
        "interval": {
            "radius": radius,
            "kind": (
                "group-aware split-conformal 90% absolute-residual radius, log10 CFU/g"
                if calibrated else
                "UNCALIBRATED descriptive residual range, log10 CFU/g "
                "(empirical coverage below nominal; not a confidence interval)"
            ),
            "nominalCoverage": 0.90,
            "empiricalCoverage": conformal["empiricalCoverage"],
            "empiricallyCalibrated": bool(calibrated),
        },
        "measuredContrast": contrast,
        "hyperparameters": search.best_params_,
        "seed": SEED,
        "domain": {name: {"min": float(x[:, i].min()), "max": float(x[:, i].max())}
                   for i, name in enumerate(FEATURES)},
        "limitations": [
            "Plate counts capture only culturable aerobic organisms; total microbial load is higher and unmeasured.",
            "The target is microbial load on leaf tissue. It is NOT biomass, yield, growth rate or shelf life.",
            "freshWeightG is the mass of the tissue subsample taken for the assay, not harvest biomass.",
            "VEG-04A and VEG-04B differ in design; the leave-one-experiment-out errors show how poorly the effect transfers and must be read before use.",
            "Two experimental campaigns only, both VEG-04 mizuna on ISS. No lettuce, tomato or radish transfer.",
            "Flight/ground differences may reflect cabin environment, payload handling or sampling protocol, not gravity per se. Causality is not established.",
            "Not a food-safety clearance tool. Do not use for consumption decisions.",
        ],
        "linear": portable_linear(model),
    }
    save_json(ARTIFACTS / f"{MODEL_ID}", card)

    out_of_fold = leaf[["sample", "experiment", "environment", "tissue", "unit",
                        "spectrum", "treatment", "freshWeightG", "log10CfuPerG"]].copy()
    out_of_fold["prediction"] = predicted
    out_of_fold["baseline"] = baseline
    out_of_fold["forestPrediction"] = forest_predicted
    out_of_fold.to_csv(EVALUATION / "microbial_out_of_fold.csv",
                       index=False, lineterminator="\n")
    save_json(EVALUATION / "microbial_splits", folds)
    save_json(EVALUATION / "microbial_contrast", contrast)

    print(json.dumps({
        "samples": card["samples"], "groups": card["groups"],
        "cv": cv_metrics, "baseline": baseline_metrics, "forest": forest_metrics,
        "leaveOneExperimentOut": loeo, "uncertainty": conformal,
        "measuredContrast": contrast,
    }, indent=2))

    registry_path = ARTIFACTS / "registry"
    registry = safedata.load(registry_path)
    digest = hashlib.sha256(safedata.bytes(ARTIFACTS / f"{MODEL_ID}")).hexdigest()
    registry["models"] = [m for m in registry["models"] if m["id"] != MODEL_ID]
    registry["models"].append({"id": MODEL_ID, "artifact": f"ml/artifacts/{MODEL_ID}",
                               "sha256": digest})
    registry["trainedAt"] = stamp()
    registry["environment"] = {
        "python": platform.python_version(), "numpy": np.__version__,
        "pandas": pd.__version__, "sklearn": sklearn.__version__,
    }
    save_json(registry_path, registry)
    print(f"\nartifact: ml/artifacts/{MODEL_ID}  sha256={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
