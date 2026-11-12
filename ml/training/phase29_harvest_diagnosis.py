"""Phase 29, step 1: diagnose why `lettuce-earth-growth-v3` failed its independent holdout.

What this script does
---------------------
It re-derives the v3 pipeline exactly as `train_lettuce_v3.py` built it (same folds, same learner,
same seed, same target) and then measures *where* the error comes from rather than how large it is.
Nothing here changes a model, a threshold or a split; it only reads.

The questions it answers, each with a number attached:

1. **How much of the out-of-fold error is between-experiment and how much is within?** If almost all
   of it is between-experiment, the model is not learning an environmental response — it is learning
   four experiment means and losing one of them on every fold.
2. **What is actually varied in the training design?** Air and root temperature turn out to take two
   values each across four experiments, i.e. a 2x2 group-level design, while PPFD is a
   within-experiment gradient. Continuous temperature inference is therefore an illusion.
3. **Where does the model's error sit in the two external studies?** Computed here recomputed from
   the recorded observations, so the diagnosis and the artifact cannot drift apart.
4. **Is the independent holdout even inside the model's declared domain?** Every holdout observation
   is checked against the artifact's own `domain` block.
5. **Would the model pass if the holdout were in-domain?** PeerJ is inside the declared domain. It is
   also already spent as a development set, so its score is reported as development, not validation.

Output: `ml/evaluation/phase29_harvest_diagnosis`, consumed by
`docs/PHASE29_HARVEST_GENERALIZATION_REPORT.md`.

Run: python ml/training/phase29_harvest_diagnosis.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
sys.path.insert(0, str(ROOT / "scripts"))
from nasa_pipeline import save_json, stamp  # noqa: E402

DATA = ROOT / "data" / "processed" / "lettuce_earth.csv"
OUT = ROOT / "ml" / "evaluation" / "phase29_harvest_diagnosis"
ARTIFACT = ROOT / "ml" / "artifacts" / "lettuce-earth-growth-v3"

DENSITY = 25.0        # Carotti et al.: 15 trays x 4 plants -> 25 plants/m2
PHOTOPERIOD = 16.0    # Carotti et al.
SEED = 42

# PeerJ (development, spent) and Touliatos (the declared independent holdout). Transcribed in
# data/literature/external_lettuce_peerj17085 and in the v3 training script respectively.
PEERJ = [("baby-cos-upper", 697, 84.5), ("baby-cos-middle", 391, 123.8),
         ("baby-cos-lower", 322, 92.9), ("green-oak-upper", 697, 97.3),
         ("green-oak-middle", 391, 190.7), ("green-oak-lower", 322, 203.7)]
PEERJ_DENSITY, PEERJ_PHOTOPERIOD, PEERJ_AIR = 48.0, 12.0, 27.5
TOULIATOS = [{"id": "hhs-50", "density": 50.0, "ppfd": 455.0, "measuredG": 138.0,
              "air": 17.0, "photoperiod": 16.0, "dat": 35.0, "se": 6.0, "n": 40}]


def features(frame: pd.DataFrame, photoperiod: float) -> np.ndarray:
    dli = frame.ppfd.to_numpy(float) * photoperiod * 3600.0 / 1e6
    return np.column_stack([frame.daysAfterTransplant.to_numpy(float),
                            frame.airTemperature.to_numpy(float),
                            frame.rootTemperature.to_numpy(float), dli])


def predict_per_area(model, dat, air, root, ppfd, photoperiod) -> float:
    dli = ppfd * photoperiod * 3600.0 / 1e6
    return float(np.exp(model.predict(np.array([[dat, air, root, dli]]))[0]))


def main() -> None:
    frame = pd.read_csv(DATA).sort_values(
        ["experiment", "daysAfterTransplant", "ppfd"]).reset_index(drop=True)
    X = features(frame, PHOTOPERIOD)
    groups = frame.experiment.to_numpy()
    per_area_measured = frame.freshShootMassG.to_numpy(float) * DENSITY
    log_target = np.log(per_area_measured)

    # Same learner and folds as train_lettuce_v3.py, chosen there by out-of-fold MAE.
    folds = list(GroupKFold(n_splits=4).split(X, log_target, groups))
    oof = np.zeros_like(log_target)
    fold_report = []
    for index, (train_idx, test_idx) in enumerate(folds):
        model = GradientBoostingRegressor(n_estimators=220, learning_rate=0.05, max_depth=3,
                                          random_state=SEED)
        model.fit(X[train_idx], log_target[train_idx])
        oof[test_idx] = model.predict(X[test_idx])
        held_out = sorted(set(groups[test_idx]))
        fold_report.append({
            "fold": index,
            "heldOutExperiments": [str(g) for g in held_out],
            "trainRows": int(len(train_idx)),
            "trainExperiments": [str(g) for g in sorted(set(groups[train_idx]))],
            "testRows": int(len(test_idx)),
        })

    predicted = np.exp(oof)
    residual = predicted - per_area_measured
    rel = residual / per_area_measured

    # ---- 1. error decomposition -----------------------------------------------------------
    frame = frame.assign(predictionPerArea=predicted, residualPerArea=residual, relativeError=rel)
    decomposition = {}
    for experiment, sub in frame.groupby("experiment"):
        decomposition[str(experiment)] = {
            "rows": int(len(sub)),
            "measuredMeanGPerM2": round(float(sub.freshShootMassG.mean() * DENSITY), 1),
            "predictedMeanGPerM2": round(float(sub.predictionPerArea.mean()), 1),
            "meanBiasGPerM2": round(float(sub.residualPerArea.mean()), 1),
            "meanRelativeError": round(float(sub.relativeError.mean()), 4),
            "maeGPerM2": round(float(sub.residualPerArea.abs().mean()), 1),
        }

    # Within-experiment error is what is left when each experiment's own mean bias is removed. The
    # gap between the two is how much of the error is "which experiment is this" rather than
    # "what environment is this".
    within = frame.groupby("experiment").apply(
        lambda sub: (sub.residualPerArea - sub.residualPerArea.mean()).abs().mean(),
        include_groups=False)
    within_mae = float(np.average(within.to_numpy(), weights=frame.groupby("experiment").size()))
    overall_mae = float(np.mean(np.abs(residual)))

    # ---- 2. what the training design actually varies --------------------------------------
    design = {}
    for column in ("airTemperature", "rootTemperature", "ppfd"):
        values = sorted(frame[column].unique().tolist())
        design[column] = {
            "distinctValues": values,
            "distinctCount": len(values),
            "perExperimentDistinct": {str(k): int(v) for k, v in
                                      frame.groupby("experiment")[column].nunique().items()},
        }
    design["temperatureByExperiment"] = {
        str(k): {"air": sorted(v.airTemperature.unique().tolist()),
                 "root": sorted(v.rootTemperature.unique().tolist())}
        for k, v in frame.groupby("experiment")}
    design["conclusion"] = (
        "PPFD takes three values (200, 400, 750 umol/m2/s) and is varied inside every experiment. "
        "Air and root-zone temperature take four values overall (20, 24, 28, 32 C) but only two "
        "inside any one experiment, and the four experiments cover the four quadrants: EXP1 "
        "20/24-20/24, EXP2 20/24-28/32, EXP3 28/32-20/24, EXP4 28/32-28/32. So temperature is a "
        "gradient with two levels per experiment, confounded with experiment identity, while light "
        "is a clean three-level within-experiment gradient. Leave-one-experiment-out "
        "cross-validation therefore removes one temperature quadrant at a time and asks the model "
        "to place a quadrant it has never seen.")

    # ---- 3. the same model against the two external studies ------------------------------
    final = GradientBoostingRegressor(n_estimators=220, learning_rate=0.05, max_depth=3,
                                      random_state=SEED).fit(X, log_target)

    development = []
    for obs_id, ppfd, measured in PEERJ:
        per_area = predict_per_area(final, 28.0, PEERJ_AIR, PEERJ_AIR, ppfd, PEERJ_PHOTOPERIOD)
        development.append({"id": obs_id, "measuredG": measured,
                            "predictedG": round(per_area / PEERJ_DENSITY, 1),
                            "ratio": round(per_area / PEERJ_DENSITY / measured, 3)})
    dev_ratios = [row["ratio"] for row in development]

    holdout = []
    for obs in TOULIATOS:
        per_area = predict_per_area(final, obs["dat"], obs["air"], obs["air"], obs["ppfd"],
                                    obs["photoperiod"])
        predicted_g = per_area / obs["density"]
        holdout.append({
            "id": obs["id"], "measuredG": obs["measuredG"], "predictedG": round(predicted_g, 1),
            "dailyLightIntegral": round(obs["ppfd"] * obs["photoperiod"] * 3600 / 1e6, 2),
            "ratio": round(predicted_g / obs["measuredG"], 3),
            "percentageError": round(100 * abs(predicted_g - obs["measuredG"]) / obs["measuredG"], 2),
        })

    # ---- 4. domain check on every external observation ------------------------------------
    domain = safedata.load(ARTIFACT)["domain"]
    def violations(air: float, root: float, dat: float, dli: float) -> list[str]:
        found = []
        for name, value in (("daysAfterTransplant", dat), ("airTemperature", air),
                            ("rootTemperature", root), ("dailyLightIntegral", dli)):
            bounds = domain[name]
            if not bounds["min"] <= value <= bounds["max"]:
                found.append(f"{name}={value:g} outside [{bounds['min']:g}, {bounds['max']:g}]")
        return found

    peerj_dli = sorted({round(p * PEERJ_PHOTOPERIOD * 3600 / 1e6, 2) for _, p, _ in PEERJ})
    domain_check = {
        "peerj": {"observations": len(PEERJ),
                  "violations": violations(PEERJ_AIR, PEERJ_AIR, 28.0, peerj_dli[len(peerj_dli) // 2]),
                  "dailyLightIntegralValues": peerj_dli},
        "touliatos": {"observations": len(TOULIATOS),
                      "violations": violations(TOULIATOS[0]["air"], TOULIATOS[0]["air"],
                                               TOULIATOS[0]["dat"],
                                               TOULIATOS[0]["ppfd"] * TOULIATOS[0]["photoperiod"] * 3600 / 1e6)},
    }

    # ---- 4b. is the declared applicability domain the one the data actually has? -----------
    observed_ranges = {
        "daysAfterTransplant": [float(frame.daysAfterTransplant.min()), float(frame.daysAfterTransplant.max())],
        "airTemperature": [float(frame.airTemperature.min()), float(frame.airTemperature.max())],
        "rootTemperature": [float(frame.rootTemperature.min()), float(frame.rootTemperature.max())],
        "dailyLightIntegral": [round(float((frame.ppfd * PHOTOPERIOD * 3600 / 1e6).min()), 2),
                               round(float((frame.ppfd * PHOTOPERIOD * 3600 / 1e6).max()), 2)],
    }
    domain_audit = {}
    for name, (low, high) in observed_ranges.items():
        declared = domain[name]
        domain_audit[name] = {
            "observed": [low, high],
            "declared": [declared["min"], declared["max"]],
            "declaredMatchesObserved": (declared["min"] == low and declared["max"] == high),
            "declaredIsNarrower": declared["max"] < high or declared["min"] > low,
            "declaredIsWider": declared["max"] > high or declared["min"] < low,
        }
    domain_audit["finding"] = (
        "The declared dailyLightIntegral maximum is 34.5, but the training design reaches 43.2 "
        "(PPFD 750 at a 16 h photoperiod). The upper bound was hardcoded in train_lettuce_v3.py "
        "rather than derived from the data, so the served model reports a valid light level as "
        "out of domain and simultaneously advertises support up to a light level it never saw. "
        "The same hardcoding means a later change to the training data would silently leave the "
        "domain stale.")

    # ---- 5. what the target scale looks like inside vs outside the training experiments ---
    experiment_means = {
        str(k): round(float(v), 1)
        for k, v in frame.groupby("experiment").freshShootMassG.mean().items()}
    peak_per_area = {str(k): round(float(v.freshShootMassG.max() * DENSITY), 0)
                     for k, v in frame.groupby("experiment")}

    payload = {
        "schema": "spaceagrisim.phase29_harvest_diagnosis/1",
        "generatedAt": stamp(),
        "modelDiagnosed": "lettuce-earth-growth-v3",
        "reproduction": {
            "protocol": "leave-one-experiment-out (GroupKFold, 4 folds), gradient boosting, "
                        "log(fresh yield per m2) target, seed 42",
            "folds": fold_report,
            "outOfFoldMAEgPerM2": round(overall_mae, 1),
            "outOfFoldMedianAbsolutePercentageError": round(
                float(np.median(np.abs(rel)) * 100), 2),
            "outOfFoldMeanAbsolutePercentageError": round(float(np.mean(np.abs(rel)) * 100), 2),
            "matchesArtifactMAE": round(overall_mae, 1) == round(
                float(safedata.load(ARTIFACT)["metrics"]["MAE"]), 1),
        },
        "errorDecomposition": {
            "byExperiment": decomposition,
            "withinExperimentMAEgPerM2": round(within_mae, 1),
            "overallMAEgPerM2": round(overall_mae, 1),
            "betweenExperimentShareOfMAE": round(1 - within_mae / overall_mae, 4),
            "reading": ("Removing each experiment's own mean bias leaves "
                        f"{within_mae:.0f} g/m2 of error against {overall_mae:.0f} overall. The "
                        "difference is the model's inability to place a new experiment, not its "
                        "inability to describe growth within one."),
        },
        "trainingDesign": design,
        "externalChecks": {
            "development": {
                "study": "PeerJ 12:e17085 (Wicharuck et al. 2024)",
                "countsAsValidation": False,
                "whyNot": "its observations informed the v3 feature choice",
                "observations": development,
                "medianRatio": round(float(np.median(dev_ratios)), 3),
                "minRatio": round(float(np.min(dev_ratios)), 3),
                "maxRatio": round(float(np.max(dev_ratios)), 3),
            },
            "independentHoldout": {
                "study": "Touliatos et al. 2016",
                "observations": holdout,
                "meanAbsolutePercentageError": round(
                    float(np.mean([abs(o["predictedG"] - o["measuredG"]) / o["measuredG"]
                                   for o in holdout]) * 100), 2),
                "nObservations": len(holdout),
                "acceptanceCriterionPct": 30.0,
            },
        },
        "domainCheck": domain_check,
        "declaredDomainAudit": domain_audit,
        "trainingExperimentScale": {
            "meanFreshMassGPerPlant": experiment_means,
            "peakPerAreaYieldGPerM2": peak_per_area,
            "note": ("Four experiments by one group, in a CO2-enriched plant factory at 25 plants/m2 "
                     "and 16 h. The external studies are ambient greenhouse and a vertical farm; "
                     "the systematic overprediction is consistent with an environment-variable "
                     "difference the model has no input for."),
        },
        "notDoneHere": ("No model was refitted for production, no threshold was moved and no "
                        "holdout observation was used to choose anything. This file is a "
                        "diagnosis."),
    }
    save_json(OUT, payload)
    print(json.dumps({k: payload[k] for k in
                      ("reproduction", "errorDecomposition", "domainCheck", "externalChecks")},
                     indent=1)[:4000])


if __name__ == "__main__":
    main()
