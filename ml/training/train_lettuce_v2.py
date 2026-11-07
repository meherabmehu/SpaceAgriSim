"""Phase 8: lettuce Earth growth v2 - gradient boosting, versioned beside v1.

Why this exists
---------------
Phase 7's benchmark compared Dummy, ridge, RandomForest and HistGradientBoosting
on this task under identical leave-one-experiment-out folds and found boosting
ahead (R2 0.8796 vs 0.7974). The registered artifact, however, was the random
forest (R2 0.8120 on its own nested protocol). So the platform was serving the
model class its own benchmark had already shown to be worse.

Phase 8 is not allowed to overwrite Phase 7 artifacts, so this trains a *second*
registered model. v1 stays byte-identical and checksum-verified; v2 is added
beside it and the registry records the supersession.

Two model classes are compared that can actually be shipped
-----------------------------------------------------------
`HistGradientBoostingRegressor` scored best in the Phase 7 harness, but its
internal predictor layout (binned, structured-array nodes) is awkward to
serialise into the dependency-free JSON artefact format this API uses, and a
hand-written re-implementation of its binning would be a correctness risk.

`GradientBoostingRegressor` (classic) uses ordinary decision trees with the same
`children_left` / `feature` / `threshold` / `value` arrays as the existing
forests, so it serialises losslessly and is evaluated additively:
`init + learning_rate * sum(tree(x))`. That is a few lines of arithmetic, not a
reimplementation of sklearn.

Both are measured here on the same folds, so the shipped choice is justified by
measurement rather than by convenience.

Run: python ml/training/train_lettuce_v2.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import (GradientBoostingRegressor,
                              HistGradientBoostingRegressor,
                              RandomForestRegressor)
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from nasa_pipeline import save_json, stamp  # noqa: E402

FEATURES = ["daysAfterTransplant", "airTemperature", "rootTemperature", "ppfd"]
SEED = 42
MODEL_ID = "lettuce-earth-growth-v2"


def metrics(y, prediction) -> dict:
    return {
        "MAE": float(mean_absolute_error(y, prediction)),
        "RMSE": float(np.sqrt(mean_squared_error(y, prediction))),
        "R2": float(r2_score(y, prediction)),
    }


def serialise_tree(estimator) -> dict:
    """Flatten one fitted DecisionTree into the project's JSON tree schema."""
    tree = estimator.tree_
    return {
        "left": tree.children_left.tolist(),
        "right": tree.children_right.tolist(),
        "feature": tree.feature.tolist(),
        "threshold": tree.threshold.tolist(),
        "value": tree.value[:, 0, 0].tolist(),
    }


def main() -> None:
    frame = pd.read_csv(ROOT / "data" / "processed" / "lettuce_earth.csv")
    x = frame[FEATURES].to_numpy()
    y = frame["freshShootMassG"].to_numpy()
    groups = frame["experiment"].to_numpy()

    splits = list(GroupKFold(4).split(x, y, groups))
    candidates = {
        "baseline_mean": lambda: DummyRegressor(strategy="mean"),
        "ridge": lambda: Pipeline([("scale", StandardScaler()), ("model", Ridge(alpha=10.0))]),
        "randomForest(): v1 class": lambda: RandomForestRegressor(
            n_estimators=64, max_depth=8, min_samples_leaf=5, random_state=SEED, n_jobs=-1),
        "gradientBoosting (classic)": lambda: GradientBoostingRegressor(
            n_estimators=200, learning_rate=0.06, max_leaf_nodes=7, random_state=SEED),
        "histGradientBoosting": lambda: HistGradientBoostingRegressor(
            max_iter=200, learning_rate=0.06, max_leaf_nodes=7, random_state=SEED),
    }

    comparison, out_of_fold = {}, {}
    for name, factory in candidates.items():
        prediction = np.zeros(len(y), dtype=float)
        fold_r2, fold_mae = [], []
        for train, test in splits:
            assert not set(groups[train]) & set(groups[test]), "group leakage"
            prediction[test] = factory().fit(x[train], y[train]).predict(x[test])
            fold_r2.append(float(r2_score(y[test], prediction[test])))
            fold_mae.append(float(mean_absolute_error(y[test], prediction[test])))
        comparison[name] = metrics(y, prediction)
        out_of_fold[name] = {"foldR2": fold_r2, "foldMAE": fold_mae}
        print(f"{name:30s} R2 {comparison[name]['R2']:+.4f}  MAE {comparison[name]['MAE']:7.3f}")

    shipped = "gradientBoosting (classic)"
    # The shipped class must win on the headline metric against the class that v1
    # actually ships, and must not win on a single fold alone.
    assert comparison[shipped]["R2"] > comparison["randomForest(): v1 class"]["R2"]
    assert comparison[shipped]["MAE"] < comparison["randomForest(): v1 class"]["MAE"]
    wins = sum(
        a < b for a, b in zip(out_of_fold[shipped]["foldMAE"],
                              out_of_fold["randomForest(): v1 class"]["foldMAE"]))
    print(f"shipped class beats v1 class on MAE in {wins}/4 held-out experiments")
    assert wins >= 3, "improvement is not consistent across held-out experiments"

    # Final fit on every experiment, then ship the trees.
    final = GradientBoostingRegressor(
        n_estimators=200, learning_rate=0.06, max_leaf_nodes=7, random_state=SEED).fit(x, y)
    boosted = {
        "init": float(np.ravel(final.init_.constant_)[0]),
        "learningRate": float(final.learning_rate),
        "trees": [serialise_tree(estimator) for estimator in final.estimators_[:, 0]],
    }

    # Verify the serialised ensemble reproduces sklearn before writing anything.
    manual = np.full(len(y), boosted["init"], dtype=float)
    rows = np.arange(len(y))
    for tree in boosted["trees"]:
        left = np.asarray(tree["left"], dtype=int)
        right = np.asarray(tree["right"], dtype=int)
        feature = np.asarray(tree["feature"], dtype=int)
        threshold = np.asarray(tree["threshold"], dtype=float)
        value = np.asarray(tree["value"], dtype=float)
        index = np.zeros(len(y), dtype=int)
        while True:
            active = left[index] != -1
            if not active.any():
                break
            go_left = x[rows, feature[index]] <= threshold[index]
            index = np.where(active, np.where(go_left, left[index], right[index]), index)
        manual += boosted["learningRate"] * value[index]
    difference = float(np.max(np.abs(manual - final.predict(x))))
    assert difference < 1e-9, f"serialised ensemble diverges from sklearn by {difference}"
    print(f"serialised ensemble matches sklearn to {difference:.2e}")

    oof_prediction = np.zeros(len(y), dtype=float)
    for train, test in splits:
        oof_prediction[test] = candidates[shipped]().fit(x[train], y[train]).predict(x[test])
    residual = np.abs(y - oof_prediction)

    card = {
        "id": MODEL_ID,
        "name": "Lettuce Earth growth \u00b7 WUR gradient boosting",
        "version": "2.0.0",
        "status": "trained-exploratory",
        "supersedes": "lettuce-earth-growth-v1 (kept, not overwritten)",
        "trainedAt": stamp(),
        "task": "Earth-only fresh shoot mass regression",
        "sourceStudy": "WUR-lettuce",
        "sourceUrl": "https://doi.org/10.4121/5a7472f0-8a67-4ec0-84c9-9d032990d654.v1",
        "sourceType": "external scientific data (not NASA)",
        "license": "CC-BY-4.0",
        "crop": "lettuce",
        "method": "External-scientific-data-trained exploratory gradient boosting",
        "samples": int(len(y)),
        "groups": int(len(set(groups))),
        "features": FEATURES,
        "target": "freshShootMassG",
        "unit": "g fresh shoot mass/plant",
        "metrics": comparison[shipped],
        "baselineMetrics": comparison["baseline_mean"],
        "predecessorMetrics": comparison["randomForest(): v1 class"],
        "validation": (
            "Leave-one-experiment-out CV (4 outer folds), identical folds for every "
            "learner including the baseline. Independent-study validation unavailable."),
        "modelSelection": {
            "compared": {name: value for name, value in comparison.items()},
            "perFold": out_of_fold,
            "shipped": shipped,
            "rule": (
                "Same folds and same grouping for every learner. The shipped class must "
                "beat the class v1 actually serves on pooled R2 and MAE and on MAE in at "
                "least three of the four held-out experiments."),
            "histGradientBoostingNote": (
                "HistGradientBoosting scored marginally higher but bins its features and "
                "stores structured-array predictors; shipping it would require "
                "re-implementing sklearn's binning in the dependency-free evaluator."),
            "serialisationCheck": {"maxAbsDifference": difference, "tolerance": 1e-9},
        },
        "seed": SEED,
        "hyperparameters": final.get_params(),
        "domain": {name: {"min": float(x[:, i].min()), "max": float(x[:, i].max())}
                   for i, name in enumerate(FEATURES)},
        "interval": {
            "radius": float(np.quantile(residual, 0.9, method="higher")),
            "kind": "90th percentile absolute leave-one-experiment-out residual; uncalibrated descriptive range",
            "nominalCoverage": None,
            "empiricalCoverage": float((residual <= np.quantile(residual, 0.9, method="higher")).mean()),
            "empiricallyCalibrated": False,
        },
        "limitations": [
            "Only Batavia Othilie lettuce on Earth; not calibrated for partial gravity or radiation.",
            "No inference for water stress, nutrient stress, CO2 response, other cultivars, or different photoperiods.",
            "Measured domain is 2-29 days after transplant, air/root 20-32 C, PPFD 200-750 umol/m2/s; the treatment grid is sparse.",
            "Environmental combinations omitted for tip burn are unsupported even inside marginal ranges.",
            "Fresh shoot mass per plant is not edible harvest per square meter; no planting-density conversion is assumed.",
            "Boosted trees extrapolate to a constant outside the training range; the out-of-domain flag is mandatory, not advisory.",
            "External data, not NASA data.",
        ],
        "boostedTrees": boosted,
    }

    path = ROOT / "ml" / "artifacts" / f"{MODEL_ID}.json"
    body = json.dumps(card, separators=(",", ":"), allow_nan=False) + "\n"
    path.write_text(body, encoding="utf-8")
    digest = hashlib.sha256(body.encode()).hexdigest()
    print(f"wrote {path.name} ({len(body)} bytes) sha256 {digest}")

    registry_path = ROOT / "ml" / "artifacts" / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["models"] = [m for m in registry["models"] if m["id"] != MODEL_ID]
    registry["models"].append({
        "id": MODEL_ID,
        "artifact": f"ml/artifacts/{MODEL_ID}.json",
        "sha256": digest,
        "supersedes": "lettuce-earth-growth-v1",
    })
    registry["trainedAt"] = stamp()
    registry_path.write_text(json.dumps(registry, indent=1) + "\n", encoding="utf-8")

    save_json(ROOT / "ml" / "evaluation" / "phase8_lettuce_benchmark.json", {
        "phase": 8,
        "task": "lettuce fresh shoot mass",
        "samples": int(len(y)),
        "groups": int(len(set(groups))),
        "validation": "leave-one-experiment-out (4 folds), identical for every learner",
        "environment": {"python": sys.version.split()[0], "numpy": np.__version__,
                        "pandas": pd.__version__, "sklearn": sklearn.__version__},
        "comparison": comparison,
        "perFold": out_of_fold,
        "shipped": shipped,
        "artifact": {"id": MODEL_ID, "sha256": digest, "bytes": len(body)},
    })


if __name__ == "__main__":
    main()
