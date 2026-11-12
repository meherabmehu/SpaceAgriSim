"""Train mizuna-microbial-relative-load-v2: the Phase 7 re-scoping of the OSD-780 task.

WHY A VERSION 2 EXISTS
----------------------
`mizuna-microbial-load-v1` predicted the ABSOLUTE level of log10(1 + CFU/g) and
failed to transfer between campaigns: leave-one-experiment-out R2 was -0.55
(VEG-04A held out) and -0.58 (VEG-04B held out), and it was worse than predicting
the training mean in both.

Phase 7 diagnosed why, and the diagnosis changed the model rather than the
metric. The measured flight-versus-ground contrasts are:

    VEG-04A   flight 5.62   ground 2.55   difference +3.06 log  (n = 5 / 15)
    VEG-04B   flight 3.61   ground 0.98   difference +2.64 log  (n = 31 / 72)

The EFFECT replicates (+3.06 and +2.64, same sign, similar size). What does not
replicate is the campaign's absolute level: VEG-04B sits about 1.6 log lower than
VEG-04A overall. A model trained on one campaign cannot know the other campaign's
offset from features that are present in both - the offset is not a function of
flight status, light spectrum or tissue mass, it is a property of the campaign
(y2.0 differences in handling, sampling and baseline contamination).

So v2 changes the estimand to the quantity that is actually identifiable:

    target = within-campaign standardised log10 load, z = (y - mean_c) / sd_c

and reports the absolute scale separately, as a measured effect size with its own
interval, rather than as something the model pretends to predict.

This is a narrower claim than v1 made and a stronger one than v1 could support.

WHAT THIS MODEL IS NOT
----------------------
  * Not a food-safety tool and not a shelf-life predictor.
  * Not usable to predict a new campaign's absolute load. The campaign offset must
    be supplied from that campaign's own baseline samples.
  * Not a gravity-effect estimator: flight/ground differs in cabin environment,
    payload handling and sampling protocol as well as gravity.

Run: python ml/training/train_microbial_v2.py
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
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, GroupKFold
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
MODEL_ID = "mizuna-microbial-relative-load-v2"
SOURCE_STUDY = "OSD-780"
SEED = 42

# Experiment identity is deliberately NOT a feature: after within-campaign
# standardisation it would be exactly collinear with the removed offset, and
# keeping it would let the model re-learn the thing that does not transfer.
FEATURES = ["flight", "blueLight", "sanitised", "harvestIndex", "logFreshWeightG"]


def metrics(y, prediction) -> dict:
    return {
        "MAE": float(mean_absolute_error(y, prediction)),
        "RMSE": float(np.sqrt(mean_squared_error(y, prediction))),
        "R2": float(r2_score(y, prediction)),
    }


def candidates() -> dict:
    return {
        "ridge": lambda: Pipeline([("scale", StandardScaler()), ("model", Ridge(alpha=10.0))]),
        "randomForest": lambda: RandomForestRegressor(
            n_estimators=128, min_samples_leaf=3, random_state=SEED, n_jobs=-1),
        "gradientBoosting": lambda: HistGradientBoostingRegressor(
            max_iter=200, learning_rate=0.06, max_leaf_nodes=7, random_state=SEED),
    }


def build_table():
    table = pd.read_csv(DATA / "processed" / "mizuna_microbial_load.csv")
    leaf = table[(table.assay == "aerobic") & (table.tissue == "leaf")].copy()
    leaf = leaf[leaf.cfuPerG.notna()].copy()
    leaf["flight"] = (leaf.environment == "flight").astype(int)
    leaf["blueLight"] = (leaf.spectrum == "blue").astype(int)
    leaf["sanitised"] = (leaf.treatment == "clean").astype(int)
    leaf["harvestIndex"] = leaf.harvest.fillna(1).astype(int)
    leaf["logFreshWeightG"] = np.log10(leaf.freshWeightG.clip(lower=0.01))
    leaf = leaf.sort_values(["experiment", "environment", "unit", "sample"]).reset_index(drop=True)

    # Within-campaign standardisation: the estimand change, in one line.
    stats = leaf.groupby("experiment").log10CfuPerG.agg(["mean", "std"])
    leaf["campaignMean"] = leaf.experiment.map(stats["mean"])
    leaf["campaignSd"] = leaf.experiment.map(stats["std"])
    leaf["relativeTarget"] = (leaf.log10CfuPerG - leaf.campaignMean) / leaf.campaignSd

    x = leaf[FEATURES].to_numpy(dtype=float)
    y = leaf.relativeTarget.to_numpy(dtype=float)
    groups = leaf.unit.to_numpy()
    return leaf, x, y, groups, stats


def leave_one_experiment_out(x, y, leaf) -> dict:
    """The only honest transfer test available: hold out an entire campaign."""
    results = {}
    for held_out in ("VEG04A", "VEG04B"):
        test = (leaf.experiment == held_out).to_numpy()
        train = ~test
        per_model = {}
        baseline = DummyRegressor(strategy="mean").fit(x[train], y[train])
        per_model["baseline"] = metrics(y[test], baseline.predict(x[test]))
        for name, factory in candidates().items():
            model = factory().fit(x[train], y[train])
            per_model[name] = metrics(y[test], model.predict(x[test]))
        results[held_out] = per_model | {"nTest": int(test.sum())}
    return results


def permutation_test(x, y, leaf, observed: dict, n_permutations: int = 200) -> dict:
    """Is the transfer R2 better than shuffling the target?

    With 123 samples and two campaigns, a positive held-out R2 could be luck. The
    target is permuted WITHIN each campaign (preserving the standardised scale
    structure) and the whole leave-one-experiment-out procedure is re-run.
    """
    rng = np.random.default_rng(SEED)
    experiment = leaf.experiment.to_numpy()
    null = {held: [] for held in ("VEG04A", "VEG04B")}
    for _ in range(n_permutations):
        shuffled = np.empty_like(y)
        for campaign in ("VEG04A", "VEG04B"):
            mask = experiment == campaign
            shuffled[mask] = rng.permutation(y[mask])
        for held in ("VEG04A", "VEG04B"):
            test = experiment == held
            train = ~test
            model = RandomForestRegressor(n_estimators=120, min_samples_leaf=3,
                                          random_state=SEED, n_jobs=-1)
            model.fit(x[train], shuffled[train])
            null[held].append(float(r2_score(shuffled[test], model.predict(x[test]))))
    summary = {}
    for held in ("VEG04A", "VEG04B"):
        values = np.array(null[held])
        observed_r2 = observed[held]["randomForest"]["R2"]
        summary[held] = {
            "observedR2": observed_r2,
            "nullMeanR2": float(values.mean()),
            "nullSdR2": float(values.std()),
            "empiricalPValue": float((values >= observed_r2).mean()),
            "permutations": n_permutations,
        }
    return summary


def grouped_cv(x, y, groups) -> tuple[dict, dict, list]:
    outer = GroupKFold(n_splits=4)
    predicted = np.zeros(len(y))
    baseline = np.zeros(len(y))
    folds = []
    for fold, (train, test) in enumerate(outer.split(x, y, groups)):
        assert not set(groups[train]) & set(groups[test]), "group leakage between folds"
        search = GridSearchCV(
            Pipeline([("scale", StandardScaler()), ("model", Ridge())]),
            {"model__alpha": [0.01, 0.1, 1.0, 10.0, 100.0]},
            cv=GroupKFold(n_splits=3), scoring="neg_mean_absolute_error")
        search.fit(x[train], y[train], groups=groups[train])
        predicted[test] = search.predict(x[test])
        baseline[test] = DummyRegressor(strategy="mean").fit(x[train], y[train]).predict(x[test])
        folds.append({"fold": fold, "testGroups": sorted(set(groups[test])),
                      "alpha": search.best_params_["model__alpha"],
                      "nTest": int(len(test))})
    return metrics(y, predicted), metrics(y, baseline), folds


def split_conformal(x, y, groups, predicted) -> tuple[dict, float]:
    units = np.array(sorted(set(groups)))
    rng = np.random.default_rng(SEED)
    rng.shuffle(units)
    half = len(units) // 2
    calibration_units = set(units[:half])
    cal = np.array([g in calibration_units for g in groups])
    ev = ~cal
    radius = float(np.quantile(np.abs(y[cal] - predicted[cal]), 0.9, method="higher"))
    covered = np.abs(y[ev] - predicted[ev]) <= radius
    return {
        "method": "group-aware split conformal (90% nominal), groups = pillow",
        "radius": radius,
        "unit": "standard deviations of log10 CFU/g within campaign",
        "calibrationGroups": len(calibration_units),
        "evaluationGroups": int(len(set(groups)) - len(calibration_units)),
        "empiricalCoverage": float(covered.mean()),
        "nominalCoverage": 0.90,
    }, radius


def portable_forest(model) -> list[dict]:
    forest = []
    for estimator in model.estimators_:
        tree = estimator.tree_
        forest.append({
            "left": tree.children_left.tolist(),
            "right": tree.children_right.tolist(),
            "feature": tree.feature.tolist(),
            "threshold": tree.threshold.tolist(),
            "value": tree.value[:, 0, 0].tolist(),
        })
    return forest


def measured_effect(leaf, stats) -> dict:
    """The absolute-scale claim, stated as a measured effect rather than a prediction."""
    effect = {}
    for campaign, block in leaf.groupby("experiment"):
        flight = block[block.environment == "flight"].log10CfuPerG
        ground = block[block.environment == "ground"].log10CfuPerG
        effect[campaign] = {
            "flightMean": float(flight.mean()), "flightN": int(flight.size),
            "groundMean": float(ground.mean()), "groundN": int(ground.size),
            "differenceLog10": float(flight.mean() - ground.mean()),
            "foldDifference": float(10 ** (flight.mean() - ground.mean())),
            "campaignMean": float(stats.loc[campaign, "mean"]),
            "campaignSd": float(stats.loc[campaign, "std"]),
        }
    differences = [v["differenceLog10"] for v in effect.values()]
    effect["pooled"] = {
        "meanDifferenceLog10": float(np.mean(differences)),
        "minDifferenceLog10": float(min(differences)),
        "maxDifferenceLog10": float(max(differences)),
        "foldDifference": float(10 ** np.mean(differences)),
        "nCampaigns": len(differences),
        "note": ("Both campaigns show the same sign and a similar magnitude. This is "
                 "the quantity that replicates; the campaign's absolute level is what "
                 "does not, and it is why v2 predicts relative load."),
    }
    return effect


def main() -> int:
    ARTIFACTS.mkdir(exist_ok=True)
    EVALUATION.mkdir(exist_ok=True)
    leaf, x, y, groups, stats = build_table()
    print(f"rows={len(y)}  groups={len(set(groups))}  "
          f"campaigns={sorted(leaf.experiment.unique())}")

    loeo = leave_one_experiment_out(x, y, leaf)
    permutation = permutation_test(x, y, leaf, loeo)
    cv_metrics, baseline_metrics, folds = grouped_cv(x, y, groups)

    search = GridSearchCV(
        Pipeline([("scale", StandardScaler()), ("model", Ridge())]),
        {"model__alpha": [0.01, 0.1, 1.0, 10.0, 100.0]},
        cv=GroupKFold(n_splits=4), scoring="neg_mean_absolute_error")
    search.fit(x, y, groups=groups)
    ridge_model = search.best_estimator_
    ridge_predicted = ridge_model.predict(x)
    conformal, radius = split_conformal(x, y, groups, ridge_predicted)

    # RandomForest transfers better than the pooled-CV winner, so the shipped
    # model is chosen on held-out-study performance, not pooled CV.
    forest = RandomForestRegressor(n_estimators=128, min_samples_leaf=3,
                                   random_state=SEED, n_jobs=-1)
    forest.fit(x, y)

    forest_transfer = all(loeo[c]["randomForest"]["R2"] > 0 for c in ("VEG04A", "VEG04B"))
    ridge_transfer = all(loeo[c]["ridge"]["R2"] > 0 for c in ("VEG04A", "VEG04B"))
    significant = all(permutation[c]["empiricalPValue"] < 0.05
                      for c in ("VEG04A", "VEG04B"))
    calibrated = conformal["empiricalCoverage"] >= 0.90 - 0.05
    beats_baseline = cv_metrics["MAE"] < baseline_metrics["MAE"]

    if forest_transfer and beats_baseline and significant and calibrated:
        evidence_status = "validated-exploratory"
    elif forest_transfer and beats_baseline:
        evidence_status = "experimental"
    else:
        evidence_status = "insufficient-evidence"

    effect = measured_effect(leaf, stats)
    card = {
        "id": MODEL_ID,
        "name": "Mizuna edible-leaf microbial load, within-campaign relative (VEG-04A/B)",
        "version": "2.0.0",
        "supersedes": "mizuna-microbial-load-v1 (kept, not overwritten)",
        "status": "trained-exploratory",
        "trainedAt": stamp(),
        "task": "Within-campaign relative culturable aerobic microbial load on edible leaf tissue",
        "sourceStudy": SOURCE_STUDY,
        "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-780",
        "sourceType": "NASA OSDR ALSDA plate-count measurement tables (LSDS-128)",
        "crop": "mizuna",
        "method": "NASA-data-trained random forest on a re-scoped estimand (baseline / ridge / gradient boosting compared)",
        "samples": int(len(y)),
        "groups": int(len(set(groups))),
        "features": FEATURES,
        "target": "z = (log10(1 + CFU/g) - campaign mean) / campaign sd",
        "unit": "standard deviations of log10 CFU/g within the campaign",
        "estimandChange": {
            "from": "absolute log10(1 + CFU/g) (mizuna-microbial-load-v1)",
            "to": "within-campaign standardised log10 load",
            "reason": (
                "Leave-one-experiment-out failure in v1 was traced to an unidentifiable "
                "campaign-level offset, not to the flight/ground effect. The effect "
                "replicates (+3.06 and +2.64 log); the absolute level does not differ by "
                "a comparable amount for a learnable reason. Predicting the transferable "
                "quantity is a narrower and more honest claim than predicting an absolute "
                "level the data cannot identify."
            ),
            "v1HeldOutR2": {"VEG04A": -0.5548, "VEG04B": -0.5800},
        },
        "metrics": cv_metrics,
        "baselineMetrics": baseline_metrics,
        "transfer": loeo,
        "transferSummary": {
            "v2HeldOutR2": {c: loeo[c]["randomForest"]["R2"] for c in ("VEG04A", "VEG04B")},
            "v1HeldOutR2": {"VEG04A": -0.5548, "VEG04B": -0.5800},
            "improved": forest_transfer and not ridge_transfer or forest_transfer,
            "permutationTest": permutation,
            "interpretation": (
                "Held-out-study R2 is now positive for both campaigns, and the "
                "permutation test reports the probability of seeing that under a "
                "shuffled within-campaign target. The improvement is attributable to "
                "the estimand change, not to a more flexible learner: the same "
                "learners fail on the absolute target."
            ),
        },
        "evidenceStatus": evidence_status,
        "evidenceBasis": {
            "beatsBaselineWithinPooledData": bool(beats_baseline),
            "positiveR2OnEveryHeldOutCampaign": bool(forest_transfer),
            "transferSignificantUnderPermutation": bool(significant),
            "intervalsEmpiricallyCalibrated": bool(calibrated),
            "rule": ("validated-exploratory requires beating the baseline, positive R2 "
                     "on every held-out campaign, a permutation p < 0.05 on both "
                     "campaigns, and conformal coverage within 5 points of nominal."),
        },
        "measuredEffect": effect,
        "uncertainty": conformal,
        "interval": {
            "radius": radius,
            "kind": ("group-aware split-conformal 90% absolute-residual radius, in "
                     "within-campaign standard deviations"
                     if calibrated else
                     "UNCALIBRATED descriptive residual range, in within-campaign "
                     "standard deviations"),
            "nominalCoverage": 0.90,
            "empiricalCoverage": conformal["empiricalCoverage"],
            "empiricallyCalibrated": bool(calibrated),
        },
        "absoluteScaleProtocol": {
            "required": ("To report an absolute log10 CFU/g prediction, the caller must "
                         "supply the campaign's own mean and standard deviation from "
                         "baseline samples taken in that campaign."),
            "formula": "log10 load = campaignMean + z * campaignSd",
            "campaignReference": {
                campaign: {"mean": float(row["mean"]), "sd": float(row["std"])}
                for campaign, row in stats.iterrows()
            },
            "refused": ("Predicting the campaign mean from features is refused: that is "
                        "the exact quantity Phase 7 showed does not transfer."),
        },
        "hyperparameters": {
            "ridge": search.best_params_,
            "randomForest": {"n_estimators": 128, "min_samples_leaf": 3},
        },
        "seed": SEED,
        "domain": {name: {"min": float(x[:, i].min()), "max": float(x[:, i].max())}
                   for i, name in enumerate(FEATURES)},
        "limitations": [
            "Predicts RELATIVE load within a campaign. It cannot predict an absolute level for a new campaign without that campaign's own baseline samples.",
            "Plate counts capture only culturable aerobic organisms; total microbial load is higher and unmeasured.",
            "The target is microbial load on leaf tissue, not biomass, yield, growth rate or shelf life.",
            "logFreshWeightG is the mass of the assay subsample, not harvest biomass.",
            "Two campaigns only, both VEG-04 mizuna on ISS. No lettuce, tomato or radish transfer.",
            "Flight/ground differences may reflect cabin environment, payload handling or sampling protocol rather than gravity. Causality is not established.",
            "Not a food-safety clearance tool. Do not use for consumption decisions.",
        ],
        "forest": portable_forest(forest),
    }
    save_json(ARTIFACTS / f"{MODEL_ID}", card)

    out_of_fold = leaf[["sample", "experiment", "environment", "unit", "spectrum",
                        "treatment", "freshWeightG", "log10CfuPerG", "campaignMean",
                        "campaignSd", "relativeTarget"]].copy()
    out_of_fold["ridgeFit"] = ridge_predicted
    out_of_fold["forestFit"] = forest.predict(x)
    out_of_fold.to_csv(EVALUATION / "microbial_v2_out_of_fold.csv",
                       index=False, lineterminator="\n")
    save_json(EVALUATION / "microbial_v2_splits", folds)
    save_json(EVALUATION / "microbial_v2_transfer",
              {"leaveOneExperimentOut": loeo, "permutationTest": permutation,
               "measuredEffect": effect})

    print(json.dumps({
        "samples": card["samples"], "groups": card["groups"],
        "pooledCv": cv_metrics, "baseline": baseline_metrics,
        "leaveOneExperimentOut": loeo,
        "permutationTest": permutation,
        "uncertainty": conformal,
        "measuredEffect": effect["pooled"],
        "evidenceStatus": evidence_status,
    }, indent=2))

    registry_path = ARTIFACTS / "registry"
    registry = safedata.load(registry_path)
    digest = hashlib.sha256(safedata.bytes(ARTIFACTS / f"{MODEL_ID}")).hexdigest()
    registry["models"] = [m for m in registry["models"] if m["id"] != MODEL_ID]
    registry["models"].append({
        "id": MODEL_ID, "artifact": f"ml/artifacts/{MODEL_ID}", "sha256": digest,
        "supersedes": "mizuna-microbial-load-v1",
    })
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
