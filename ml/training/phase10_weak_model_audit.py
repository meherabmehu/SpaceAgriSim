"""Phase 10: audit every weak model, then try to improve the ones that can be.

The point is not to make each model look better. It is to answer, for each one,
*why* it is weak, and whether that reason is addressable with the evidence that
exists. A model that cannot be improved says so with numbers.

For each model this records: the failure mode, the limiting factor, whether the
problem is data or method, what baseline the model must beat, and the outcome of
whatever improvement attempt is justified.

Run: python ml/training/phase10_weak_model_audit.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from nasa_pipeline import save_json, stamp  # noqa: E402

DATA = ROOT / "data" / "processed"
EVALUATION = ROOT / "ml" / "evaluation"
SEED = 42


def cv(frame, features, target, groups, candidates, splits=4) -> dict:
    x = frame[features].to_numpy(float)
    y = frame[target].to_numpy(float)
    g = frame[groups].to_numpy()
    folds = list(GroupKFold(splits).split(x, y, g))
    out = {}
    for name, factory in candidates.items():
        prediction = np.zeros(len(y))
        per_fold = []
        for train, test in folds:
            assert not set(g[train]) & set(g[test]), "group leakage"
            prediction[test] = factory().fit(x[train], y[train]).predict(x[test])
            per_fold.append(float(r2_score(y[test], prediction[test]))
                            if len(test) > 1 else float("nan"))
        out[name] = {
            "R2": float(r2_score(y, prediction)),
            "MAE": float(mean_absolute_error(y, prediction)),
            "perFoldR2": [None if np.isnan(v) else round(v, 4) for v in per_fold],
            "prediction": prediction,
        }
    return out


# --------------------------------------------------------------------------- #
# Mizuna harvest: 14 outcomes, R2 -0.333
# --------------------------------------------------------------------------- #
def audit_mizuna_harvest() -> dict:
    frame = pd.read_csv(DATA / "mizuna_harvest.csv")
    print(f"\nmizuna-harvest: {len(frame)} rows, {frame.group.nunique()} pillow groups, "
          f"{frame.experiment.nunique()} experiment(s)")

    frame = frame.copy()
    frame["flight"] = (frame.environment == "flight").astype(int)
    frame["blue"] = (frame.spectrum == "blue").astype(int)
    features = ["waterSuppliedL", "establishedPlants", "flight", "blue"]

    # The question a 14-row dataset has to answer first: can anything beat "predict
    # the mean"? A model that cannot is not a model, and tuning it is theatre.
    candidates = {
        "baseline_mean": lambda: DummyRegressor(strategy="mean"),
        "ridge": lambda: Pipeline([("scale", StandardScaler()), ("model", Ridge(alpha=10.0))]),
        "randomForest": lambda: RandomForestRegressor(n_estimators=64, max_depth=6,
                                                     min_samples_leaf=3, random_state=SEED),
        "gradientBoosting": lambda: GradientBoostingRegressor(n_estimators=100, max_leaf_nodes=3,
                                                              learning_rate=0.05, random_state=SEED),
    }
    results = cv(frame, features, "harvestFreshMassG", "group", candidates)
    for name, values in results.items():
        print(f"  {name:18s} R2 {values['R2']:+.3f}  MAE {values['MAE']:7.2f}")

    best = max((n for n in results if n != "baseline_mean"), key=lambda n: results[n]["R2"])
    # Beating another negative number is not an achievement. R2 below zero means the
    # model is worse than predicting the mean, so the bar is R2 > 0, not "best of a
    # bad set" -- otherwise a -0.106 result would read as a win over a -0.138 baseline.
    beat_baseline = results[best]["R2"] > 0 and results[best]["R2"] > results["baseline_mean"]["R2"]

    return {
        "model": "mizuna-harvest-v1",
        "samples": int(len(frame)),
        "groups": int(frame.group.nunique()),
        "experiments": int(frame.experiment.nunique()),
        "features": features,
        "failureMode": ("only 14 harvested endpoints in a single experiment, and the "
                        "irrigation feature is recorded retrospectively"),
        "limitingFactor": "sample size, not model class",
        "addressable": False,
        "baseline": {"R2": results["baseline_mean"]["R2"], "MAE": results["baseline_mean"]["MAE"]},
        "candidates": {k: {"R2": v["R2"], "MAE": v["MAE"], "perFoldR2": v["perFoldR2"]}
                       for k, v in results.items()},
        "bestNonBaseline": best,
        "bestNonBaselineR2": results[best]["R2"],
        "beatsBaseline": bool(beat_baseline),
        "promotionBar": "R2 > 0 and R2 above the mean baseline",
        "decision": ("keep baseline-only status: no candidate reaches R2 > 0, so nothing "
                     "here is a predictor" if not beat_baseline else
                     "candidate reaches R2 > 0; promote only if it also holds on a "
                     "held-out experiment, which one experiment cannot provide"),
        "note": ("Synthetic augmentation is refused: generating training rows from 14 real "
                 "harvests would manufacture the evidence the model is supposed to rest on."),
    }


# --------------------------------------------------------------------------- #
# Lettuce: R2 0.870, is a v3 justified?
# --------------------------------------------------------------------------- #
def audit_lettuce() -> dict:
    frame = pd.read_csv(DATA / "lettuce_earth.csv")
    features = ["daysAfterTransplant", "airTemperature", "rootTemperature", "ppfd"]
    print(f"\nlettuce-earth-growth: {len(frame)} rows, {frame.experiment.nunique()} experiments")

    candidates = {
        "baseline_mean": lambda: DummyRegressor(strategy="mean"),
        "v2_shipped_gbm": lambda: GradientBoostingRegressor(
            n_estimators=200, learning_rate=0.06, max_leaf_nodes=7, random_state=SEED),
    }
    # Improvement attempts that are justified by the data structure: the response is
    # a growth curve, so a feature that lets a split isolate a growth stage is the
    # obvious first thing to try.
    for label, alpha, leaves, rate, depth in (
        ("v3_gbm_deeper", None, 15, 0.05, 3),
        ("v3_gbm_shallower_slow", None, 5, 0.03, 2),
    ):
        candidates[label] = (lambda leaves=leaves, rate=rate, depth=depth: GradientBoostingRegressor(
            n_estimators=300, learning_rate=rate, max_leaf_nodes=leaves,
            max_depth=depth, random_state=SEED))

    results = cv(frame, features, "freshShootMassG", "experiment", candidates, splits=4)

    # A growth-stage feature, tested as its own candidate rather than assumed to help.
    engineered = frame.copy()
    engineered["logDays"] = np.log1p(engineered.daysAfterTransplant)
    engineered["vpdProxy"] = engineered.airTemperature - engineered.rootTemperature
    engineered["ppfdXDays"] = engineered.ppfd * engineered.daysAfterTransplant
    extra = features + ["logDays", "vpdProxy", "ppfdXDays"]
    engineered_results = cv(engineered, extra, "freshShootMassG", "experiment",
                            {"v3_engineered_gbm": candidates["v2_shipped_gbm"]}, splits=4)

    for name, values in results.items():
        print(f"  {name:24s} R2 {values['R2']:+.4f}  MAE {values['MAE']:7.2f}")
    for name, values in engineered_results.items():
        print(f"  {name:24s} R2 {values['R2']:+.4f}  MAE {values['MAE']:7.2f}")

    shipped = results["v2_shipped_gbm"]
    alternatives = {k: v for k, v in results.items()
                    if k not in ("baseline_mean", "v2_shipped_gbm")}
    alternatives.update(engineered_results)
    best_name = max(alternatives, key=lambda k: alternatives[k]["R2"])
    best = alternatives[best_name]

    # Pre-specified promotion rule: beat the shipped model on pooled R2 AND on MAE,
    # and not lose on more than one held-out experiment.
    wins_r2 = best["R2"] > shipped["R2"]
    wins_mae = best["MAE"] < shipped["MAE"]
    fold_wins = sum(1 for a, b in zip(best["perFoldR2"], shipped["perFoldR2"])
                    if a is not None and b is not None and a > b)
    promote = wins_r2 and wins_mae and fold_wins >= 3

    return {
        "model": "lettuce-earth-growth-v2",
        "samples": int(len(frame)),
        "groups": int(frame.experiment.nunique()),
        "features": features,
        "failureMode": ("R2 0.870 with only four held-out experiments; the interval was "
                        "uncalibrated until Phase 10 recalibrated it"),
        "limitingFactor": "group count (4 experiments), not model class",
        "addressable": False,
        "baseline": {"R2": results["baseline_mean"]["R2"], "MAE": results["baseline_mean"]["MAE"]},
        "shipped": {"R2": shipped["R2"], "MAE": shipped["MAE"], "perFoldR2": shipped["perFoldR2"]},
        "attempts": {k: {"R2": v["R2"], "MAE": v["MAE"], "perFoldR2": v["perFoldR2"]}
                     for k, v in alternatives.items()},
        "bestAttempt": best_name,
        "promotionRule": ("must beat the shipped model on pooled R2 and MAE and win at least "
                          "3 of 4 held-out experiments"),
        "promotionChecks": {"pooledR2": bool(wins_r2), "pooledMAE": bool(wins_mae),
                            "heldOutWins": fold_wins},
        "promoted": bool(promote),
        "decision": "v3 registered" if promote else "no v3; keep v2",
        "note": ("With four experiments a 0.01 R2 difference is one experiment's worth of "
                 "noise, which is why the rule requires per-experiment wins rather than a "
                 "pooled gain."),
    }


# --------------------------------------------------------------------------- #
# Tomato: acc 0.917 on 36 samples
# --------------------------------------------------------------------------- #
def audit_tomato() -> dict:
    import json as _json

    artifact = _json.loads((ROOT / "ml" / "artifacts" / "tomato-flight-response-v1.json").read_text())
    metrics = artifact["metrics"]
    print(f"\ntomato-flight-response: {artifact['samples']} samples, "
          f"{artifact['groups']} plant groups, acc {metrics['accuracy']:.3f}")

    # Wider tuning on 36 samples with 21 groups would be fitting the fold structure,
    # so the audit's contribution is the honest decomposition that already exists in
    # the artifact rather than a new search.
    per_class = metrics.get("confusionMatrix")
    return {
        "model": "tomato-flight-response-v1",
        "samples": int(artifact["samples"]),
        "groups": int(artifact["groups"]),
        "features": len(artifact["features"]),
        "failureMode": ("36 samples over 21 plants; the classifier separates recorded "
                        "flight context, which is not stress or yield"),
        "limitingFactor": "sample size and label meaning, not model class",
        "addressable": False,
        "baseline": {"macroF1": metrics.get("baselineMacroF1")},
        "shipped": {"accuracy": metrics["accuracy"], "macroF1": metrics["macroF1"],
                    "confusionMatrix": per_class},
        "attempts": {},
        "promoted": False,
        "decision": "no new version",
        "note": ("No hyperparameter search is run. With 21 groups, a search that improves "
                 "the number without a held-out plant set to confirm it is a search over "
                 "noise."),
    }


def main() -> int:
    report = {
        "phase": 10,
        "generatedAt": stamp(),
        "seed": SEED,
        "protocol": ("Every candidate is scored on identical group-held-out folds, "
                     "including a mean baseline, so 'improvement' is always measured "
                     "against predicting the mean rather than against nothing."),
        "models": [audit_mizuna_harvest(), audit_lettuce(), audit_tomato()],
    }
    save_json(EVALUATION / "phase10_weak_model_audit.json", report)

    print("\n--- decisions")
    for entry in report["models"]:
        print(f"  {entry['model']:32s} {entry['decision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
