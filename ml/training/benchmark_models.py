"""Phase 7 model-class benchmark: baseline / linear / RandomForest / gradient boosting.

Part B asks for a like-for-like comparison of the model families on every task
that has measured data, evaluated with the same grouping discipline. This script
is deliberately a *harness*, not a model trainer: it produces no artifacts and
registers nothing. Its only output is `ml/evaluation/phase7_benchmark`.

Two rules are enforced rather than documented:
  * every split is grouped by the biological replicate;
  * every learner sees exactly the same folds, including the baseline.

Run: python ml/training/benchmark_models.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.feature_selection import SelectKBest, VarianceThreshold, f_classif
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (accuracy_score, f1_score, mean_absolute_error,
                             mean_squared_error, r2_score)
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
DATA = ROOT / "data" / "processed"
OUT = ROOT / "ml" / "evaluation" / "phase7_benchmark"
SEED = 42


def regression_metrics(y, prediction) -> dict:
    return {
        "MAE": float(mean_absolute_error(y, prediction)),
        "RMSE": float(np.sqrt(mean_squared_error(y, prediction))),
        "R2": float(r2_score(y, prediction)),
    }


def regression_learners() -> dict:
    return {
        "baseline_mean": lambda: DummyRegressor(strategy="mean"),
        "ridge": lambda: Pipeline([("scale", StandardScaler()), ("model", Ridge(alpha=10.0))]),
        "randomForest": lambda: RandomForestRegressor(
            n_estimators=200, min_samples_leaf=3, random_state=SEED, n_jobs=-1),
        "gradientBoosting": lambda: HistGradientBoostingRegressor(
            max_iter=200, learning_rate=0.06, max_leaf_nodes=7, random_state=SEED),
    }


def classification_learners() -> dict:
    return {
        "baseline_majority": lambda: DummyClassifier(strategy="most_frequent"),
        "logistic": lambda: Pipeline([("scale", StandardScaler()),
                                      ("model", LogisticRegression(max_iter=2000))]),
        "randomForest": lambda: RandomForestClassifier(
            n_estimators=200, min_samples_leaf=2, random_state=SEED, n_jobs=-1),
        "gradientBoosting": lambda: HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.06, max_leaf_nodes=7, random_state=SEED),
    }


def run_regression(x, y, groups, splitter, learners) -> dict:
    results = {}
    splits = list(splitter.split(x, y, groups))
    for name, factory in learners.items():
        predicted = np.zeros(len(y), dtype=float)
        for train, test in splits:
            assert not set(groups[train]) & set(groups[test]), "group leakage"
            model = factory().fit(x[train], y[train])
            predicted[test] = model.predict(x[test])
        results[name] = regression_metrics(y, predicted)
    return results


def run_classification(x, y, groups, learners) -> dict:
    results = {}
    splits = list(StratifiedGroupKFold(n_splits=4, shuffle=True,
                                       random_state=SEED).split(x, y, groups))
    for name, factory in learners.items():
        predicted = np.zeros(len(y), dtype=int)
        for train, test in splits:
            assert not set(groups[train]) & set(groups[test]), "group leakage"
            model = factory().fit(x[train], y[train])
            predicted[test] = model.predict(x[test])
        results[name] = {
            "accuracy": float(accuracy_score(y, predicted)),
            "macroF1": float(f1_score(y, predicted, average="macro")),
        }
    return results


def verdict(results: dict, best_baseline_key: str, metric: str, higher_is_better: bool) -> dict:
    baseline = results[best_baseline_key][metric]
    scored = {k: v[metric] for k, v in results.items() if k != best_baseline_key}
    best_name = max(scored, key=scored.get) if higher_is_better else min(scored, key=scored.get)
    best_value = scored[best_name]
    better = best_value > baseline if higher_is_better else best_value < baseline
    flexible = max(("randomForest", "gradientBoosting"),
                   key=lambda k: results[k][metric] if higher_is_better
                   else -results[k][metric])
    linear = results["ridge" if "ridge" in results else "logistic"][metric]
    return {
        "metric": metric,
        "baseline": baseline,
        "bestLearner": best_name,
        "bestValue": best_value,
        "beatsBaseline": bool(better),
        "flexibleBeatsLinear": bool(
            results[flexible][metric] > linear if higher_is_better
            else results[flexible][metric] < linear),
        "note": ("Flexible learners are not assumed to win. Where they do not, the "
                 "simpler model is preferred, and where no learner beats the "
                 "baseline, the task is reported as not learnable from these "
                 "features."),
    }


def lettuce_task() -> dict:
    frame = pd.read_csv(DATA / "lettuce_earth.csv")
    features = ["daysAfterTransplant", "airTemperature", "rootTemperature", "ppfd"]
    x = frame[features].to_numpy()
    y = frame.freshShootMassG.to_numpy()
    groups = frame.experiment.to_numpy()
    results = run_regression(x, y, groups, GroupKFold(n_splits=4), regression_learners())
    return {
        "task": "lettuce fresh shoot mass",
        "target": "freshShootMassG",
        "samples": int(len(y)),
        "groups": int(len(set(groups))),
        "groupingVariable": "experiment",
        "validation": "leave-one-experiment-out (4 folds)",
        "results": results,
        "verdict": verdict(results, "baseline_mean", "R2", True),
    }


def harvest_task() -> dict:
    frame = pd.read_csv(DATA / "mizuna_harvest.csv")
    x = np.column_stack([
        frame.waterSuppliedL, frame.establishedPlants,
        (frame.environment == "flight").astype(int),
        (frame.spectrum == "blue").astype(int)]).astype(float)
    y = frame.harvestFreshMassG.to_numpy()
    groups = frame.group.to_numpy()
    results = run_regression(x, y, groups, GroupKFold(n_splits=4), regression_learners())
    return {
        "task": "mizuna harvest fresh mass",
        "target": "harvestFreshMassG",
        "samples": int(len(y)),
        "groups": int(len(set(groups))),
        "groupingVariable": "pillow group",
        "validation": "4-fold GroupKFold",
        "results": results,
        "verdict": verdict(results, "baseline_mean", "MAE", False),
    }


def microbial_task(relative: bool) -> dict:
    table = pd.read_csv(DATA / "mizuna_microbial_load.csv")
    leaf = table[(table.assay == "aerobic") & (table.tissue == "leaf")].copy()
    leaf = leaf[leaf.cfuPerG.notna()].copy()
    leaf["flight"] = (leaf.environment == "flight").astype(int)
    leaf["blueLight"] = (leaf.spectrum == "blue").astype(int)
    leaf["isVEG04B"] = (leaf.experiment == "VEG04B").astype(int)
    leaf["sanitised"] = (leaf.treatment == "clean").astype(int)
    leaf["harvestIndex"] = leaf.harvest.fillna(1).astype(int)
    leaf["logFreshWeightG"] = np.log10(leaf.freshWeightG.clip(lower=0.01))
    if relative:
        stats = leaf.groupby("experiment").log10CfuPerG.agg(["mean", "std"])
        leaf["y"] = ((leaf.log10CfuPerG - leaf.experiment.map(stats["mean"]))
                     / leaf.experiment.map(stats["std"]))
        features = ["flight", "blueLight", "sanitised", "harvestIndex", "logFreshWeightG"]
        label = "relative (within-campaign standardised)"
    else:
        leaf["y"] = leaf.log10CfuPerG
        features = ["flight", "blueLight", "isVEG04B", "sanitised", "harvestIndex",
                    "logFreshWeightG"]
        label = "absolute log10(1 + CFU/g)"

    x = leaf[features].to_numpy(dtype=float)
    y = leaf.y.to_numpy(dtype=float)
    groups = leaf.experiment.to_numpy()
    results = {}
    for name, factory in regression_learners().items():
        predicted = np.zeros(len(y))
        for held_out in ("VEG04A", "VEG04B"):
            test = groups == held_out
            train = ~test
            model = factory().fit(x[train], y[train])
            predicted[test] = model.predict(x[test])
        results[name] = regression_metrics(y, predicted)
    return {
        "task": f"mizuna microbial load, {label}",
        "target": "log10(1 + CFU/g)" if not relative else "within-campaign z-score",
        "samples": int(len(y)),
        "groups": 2,
        "groupingVariable": "experiment (campaign)",
        "validation": "leave-one-experiment-out (2 folds)",
        "results": results,
        "verdict": verdict(results, "baseline_mean", "R2", True),
    }


def tomato_task() -> dict:
    frame = pd.read_parquet(DATA / "tomato_log_cpm.parquet")
    metadata = pd.read_csv(DATA / "tomato_samples.csv").set_index("sample").loc[frame.index]
    frame = frame.loc[:, (frame != 0).any(axis=0)]
    x = frame.to_numpy()
    y = (metadata.environment == "flight").to_numpy().astype(int)
    groups = metadata.group.to_numpy()
    learners = classification_learners()
    # Feature selection has to live inside the split, so it is wrapped per learner.
    wrapped = {}
    for name, factory in learners.items():
        if name == "baseline_majority":
            wrapped[name] = factory
        else:
            wrapped[name] = (lambda f: (lambda: Pipeline([
                ("variance", VarianceThreshold()),
                ("select", SelectKBest(f_classif, k=min(20, x.shape[1]))),
                ("model", f())])))(factory)
    results = run_classification(x, y, groups, wrapped)
    return {
        "task": "tomato flight-versus-ground molecular classification",
        "target": "recorded flight context",
        "samples": int(len(y)),
        "groups": int(len(set(groups))),
        "groupingVariable": "sample group",
        "validation": "4-fold stratified group CV, feature selection inside each fold",
        "results": results,
        "verdict": verdict(results, "baseline_majority", "macroF1", True),
    }


def main() -> int:
    tasks = [
        lettuce_task(),
        harvest_task(),
        microbial_task(relative=False),
        microbial_task(relative=True),
        tomato_task(),
    ]
    payload = {
        "phase": 7,
        "purpose": (
            "Like-for-like comparison of Dummy, linear, RandomForest and gradient "
            "boosting on every task with measured data, under one grouping policy."
        ),
        "seed": SEED,
        "deepLearningUsed": False,
        "deepLearningReason": (
            "Largest measured target is 123 samples over 35 groups. A neural model "
            "would be unidentifiable at this size."
        ),
        "tasks": tasks,
        "summary": {
            "tasksBeatenBySomeLearner": sum(1 for t in tasks if t["verdict"]["beatsBaseline"]),
            "tasksWhereFlexibleBeatsLinear": sum(
                1 for t in tasks if t["verdict"]["flexibleBeatsLinear"]),
            "note": (
                "No learner class dominates. Where a flexible learner wins, it wins by "
                "a margin that is reported with the held-out study count attached; with "
                "two or four groups, a favourable split can drive the whole result."
            ),
        },
    }
    safedata.dump(payload, OUT)
    print("BENCHMARK COMPLETE")
    for task in tasks:
        verdict_block = task["verdict"]
        print(f"  {task['task'][:52]:<52} best={verdict_block['bestLearner']:<17}"
              f" {verdict_block['metric']}={verdict_block['bestValue']:.3f}"
              f" baseline={verdict_block['baseline']:.3f}"
              f" beats={'yes' if verdict_block['beatsBaseline'] else 'no'}")
    print(f"  written: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
