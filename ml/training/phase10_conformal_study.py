"""Phase 10: measure whether the platform's stated 90 % intervals actually cover.

Runs the conformal comparison in `ml/training/conformal.py` against the three
regression models that ship an interval, under one shared leave-group-out
protocol, and writes `ml/evaluation/phase10_conformal.json`.

The question is deliberately narrow: *does the interval the API reports contain
the held-out value as often as it claims?* Nothing here changes a shipped model.
It measures first; promotion is a separate decision recorded in
`ml/evaluation/phase10_uncertainty_decision.json`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import (GradientBoostingRegressor, HistGradientBoostingRegressor,
                              RandomForestRegressor)
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml" / "training"))
sys.path.insert(0, str(ROOT / "scripts"))
from conformal import evaluate  # noqa: E402
from nasa_pipeline import save_json, stamp  # noqa: E402

DATA = ROOT / "data" / "processed"
EVALUATION = ROOT / "ml" / "evaluation"
SEED = 42
ALPHA = 0.10


def microbial_relative():
    """mizuna-microbial-relative-load-v2: within-campaign standardised log load."""
    table = pd.read_csv(DATA / "mizuna_microbial_load.csv")
    leaf = table[(table.assay == "aerobic") & (table.tissue == "leaf")].copy()
    leaf = leaf[leaf.cfuPerG.notna()].copy()
    leaf["flight"] = (leaf.environment == "flight").astype(int)
    leaf["blueLight"] = (leaf.spectrum == "blue").astype(int)
    leaf["sanitised"] = (leaf.treatment == "clean").astype(int)
    leaf["harvestIndex"] = leaf.harvest.fillna(1).astype(int)
    leaf["logFreshWeightG"] = np.log10(leaf.freshWeightG.clip(lower=0.01))
    leaf = leaf.sort_values(["experiment", "environment", "unit", "sample"]).reset_index(drop=True)
    stats = leaf.groupby("experiment").log10CfuPerG.agg(["mean", "std"])
    leaf["relativeTarget"] = ((leaf.log10CfuPerG - leaf.experiment.map(stats["mean"]))
                              / leaf.experiment.map(stats["std"]))
    features = ["flight", "blueLight", "sanitised", "harvestIndex", "logFreshWeightG"]
    return (leaf[features].to_numpy(float), leaf.relativeTarget.to_numpy(float),
            leaf.unit.to_numpy(), leaf.experiment.to_numpy(), features)


def microbial_absolute():
    """mizuna-microbial-load-v1: the absolute log10 CFU/g task."""
    table = pd.read_csv(DATA / "mizuna_microbial_load.csv")
    leaf = table[(table.assay == "aerobic") & (table.tissue == "leaf")].copy()
    leaf = leaf[leaf.cfuPerG.notna()].copy()
    leaf["flight"] = (leaf.environment == "flight").astype(int)
    leaf["blueLight"] = (leaf.spectrum == "blue").astype(int)
    leaf["isVEG04B"] = (leaf.experiment == "VEG04B").astype(int)
    leaf["sanitised"] = (leaf.treatment == "clean").astype(int)
    leaf["freshWeightG"] = leaf.freshWeightG.astype(float)
    leaf["harvestIndex"] = leaf.harvest.fillna(1).astype(int)
    leaf = leaf.sort_values(["experiment", "environment", "unit", "sample"]).reset_index(drop=True)
    features = ["flight", "blueLight", "isVEG04B", "sanitised", "freshWeightG", "harvestIndex"]
    return (leaf[features].to_numpy(float), leaf.log10CfuPerG.to_numpy(float),
            leaf.unit.to_numpy(), leaf.experiment.to_numpy(), features)


def lettuce():
    frame = pd.read_csv(DATA / "lettuce_earth.csv")
    features = ["daysAfterTransplant", "airTemperature", "rootTemperature", "ppfd"]
    return (frame[features].to_numpy(float), frame["freshShootMassG"].to_numpy(float),
            frame["experiment"].to_numpy(), frame["experiment"].to_numpy(), features)


def microbial_fit(x_train, y_train, x_test):
    # n_jobs=1 is deliberate. With n_jobs=-1 the same seed and the same data gave
    # coverage 0.878 on one run and 0.886 on the next: parallel tree building sums
    # split gains in a different order, a near-tie flips, and one prediction moves
    # across the interval boundary. 123 rows do not need threads, and a calibration
    # figure that changes between identical runs is not a measurement.
    model = RandomForestRegressor(n_estimators=128, min_samples_leaf=3,
                                  random_state=SEED, n_jobs=1)
    return model.fit(x_train, y_train).predict(x_test)


def lettuce_v1_fit(x_train, y_train, x_test):
    """lettuce-earth-growth-v1's shipped class: the random forest."""
    model = RandomForestRegressor(n_estimators=64, max_depth=8, min_samples_leaf=5,
                                  random_state=42, n_jobs=1)
    return model.fit(x_train, y_train).predict(x_test)


def lettuce_fit(x_train, y_train, x_test):
    model = GradientBoostingRegressor(n_estimators=200, learning_rate=0.06,
                                      max_leaf_nodes=7, random_state=SEED)
    return model.fit(x_train, y_train).predict(x_test)


def main() -> int:
    results = {}

    for name, loader, fit, strata in (
        ("mizuna-microbial-relative-load-v2", microbial_relative, microbial_fit, True),
        ("mizuna-microbial-load-v1", microbial_absolute, microbial_fit, True),
        ("lettuce-earth-growth-v1", lettuce, lettuce_v1_fit, False),
        ("lettuce-earth-growth-v2", lettuce, lettuce_fit, False),
    ):
        x, y, groups, strata_values, features = loader()
        print(f"\n{name}: {len(y)} rows, {len(set(groups))} groups, {len(features)} features")
        # Lettuce has only four experiments, so conditioning on experiment leaves
        # strata too small to carry a quantile. It is evaluated unconditioned, and
        # the report says so instead of showing a duplicated method under a new name.
        evaluated = evaluate(fit, x, y, groups, alpha=ALPHA, outer_folds=4 if not strata else 5,
                             inner_folds=5, strata=strata_values if strata else None,
                             seed=SEED)
        if not strata:
            evaluated["summary"].pop("mondrian", None)
            evaluated["detail"].pop("mondrian", None)
            evaluated["mondrianOmitted"] = (
                "only 4 experiments; conditioning on experiment leaves strata below the "
                "10 residuals a finite 90% quantile needs")
        for method, values in evaluated["summary"].items():
            print(f"  {method:9s} coverage {values['empiricalCoverage']:.3f} "
                  f"(nominal {values['nominalCoverage']:.2f})  width {values['meanIntervalWidth']:.3f}")
        results[name] = {
            "samples": int(len(y)),
            "groups": int(len(set(groups))),
            "features": features,
            "task": ("within-campaign standardised log10 CFU/g" if "relative" in name
                     else "log10 CFU/g" if "microbial" in name else "fresh shoot mass (g)"),
            "shippedMethod": ("split conformal" if "microbial" in name else
                              "90th percentile residual range"),
            **evaluated,
        }

    report = {
        "phase": 10,
        "generatedAt": stamp(),
        "seed": SEED,
        "alpha": ALPHA,
        "purpose": ("Measure the coverage the platform's stated 90% intervals actually "
                    "achieve on held-out groups, and compare split conformal against "
                    "grouped cross-conformal on identical folds."),
        "methods": {
            "split": "Phase 9 method: fit on part of the training groups, calibrate on the rest",
            "cv_plus": "Grouped cross-conformal: out-of-fold residuals from all training groups",
            "mondrian": "As cv_plus, with the quantile taken within each campaign",
        },
        "caveat": ("Conformal coverage is marginal under exchangeability. Multiple tissues "
                   "from one pillow, and two campaigns, are not a sample of future "
                   "campaigns. These are measured held-out coverages, not guarantees."),
        "models": results,
    }
    save_json(EVALUATION / "phase10_conformal.json", report)

    print("\ncoverage summary (nominal 0.90):")
    for name, values in results.items():
        row = "  ".join(f"{m} {v['empiricalCoverage']:.3f}" for m, v in values["summary"].items())
        print(f"  {name:36s} {row}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
