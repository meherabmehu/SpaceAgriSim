"""Phase 29, step 4: does the conformal interval mean what the API says it means?

The served artifact reports an out-of-fold coverage of 0.899 at a nominal 90 %, and the workflow UI
repeats it. This script asks the questions that number cannot answer on its own:

1. **Is the coverage uniform, or is it an average over groups that hide each other?** Coverage is
   reported per experiment and per growth stage. A conformal interval calibrated by pooling four
   experiments is only exchangeable *within* those experiments if the experiments are exchangeable,
   and the diagnosis showed their yields differ by a factor of nearly three.
2. **How wide is the interval, really?** Coverage without width is meaningless: a 90 % interval that
   spans a factor of five covers everything and tells a user nothing. Width is reported as a
   multiplicative factor and in grams at three reference growth stages.
3. **Does the split-conformal variant agree with the CV+ variant?** The two use different
   calibration residuals; disagreement between them is a direct warning about exchangeability.
4. **What does the interval do on the protected holdout?** It is checked once, on the observation
   already scored by `phase29_harvest_final.py`. One observation cannot validate coverage; it can
   only fail to contradict it.

Nothing here refits a production model or changes a served interval. It measures the served one.

Output: `ml/evaluation/phase29_interval_audit`

Run: python ml/training/phase29_interval_audit.py
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
V3 = ROOT / "ml" / "artifacts" / "lettuce-earth-growth-v3"
OUT = ROOT / "ml" / "evaluation" / "phase29_interval_audit"
DENSITY, PHOTOPERIOD, SEED = 25.0, 16.0, 42


def coverage(lower, upper, y) -> float:
    return float(np.mean((y >= lower) & (y <= upper)))


def main() -> None:
    frame = pd.read_csv(DATA).sort_values(
        ["experiment", "daysAfterTransplant", "ppfd"]).reset_index(drop=True)
    dli = frame.ppfd.to_numpy(float) * PHOTOPERIOD * 3600.0 / 1e6
    X = np.column_stack([frame.daysAfterTransplant.to_numpy(float),
                         frame.airTemperature.to_numpy(float),
                         frame.rootTemperature.to_numpy(float), dli])
    y = frame.freshShootMassG.to_numpy(float) * DENSITY
    log_y = np.log(y)
    groups = frame.experiment.to_numpy()
    folds = list(GroupKFold(n_splits=4).split(X, log_y, groups))

    def learner():
        return GradientBoostingRegressor(n_estimators=220, learning_rate=0.05, max_depth=3,
                                         random_state=SEED)

    # ---- the served interval: CV+ style ------------------------------------------------
    oof = np.zeros_like(log_y)
    for train_idx, test_idx in folds:
        model = learner().fit(X[train_idx], log_y[train_idx])
        oof[test_idx] = model.predict(X[test_idx])
    residual = log_y - oof
    cv_low, cv_high = (float(v) for v in np.quantile(residual, [0.05, 0.95]))

    # ---- the split-conformal variant ---------------------------------------------------
    # Calibrate on the residual of one half of the folds, evaluate on the other half, then swap.
    # Residuals reused across halves would leak, so the residuals are recomputed for each half.
    def half_calibrated(first_half: bool):
        train_idx = np.concatenate([folds[i][0] for i in (range(2) if first_half else range(2, 4))])
        cal_idx = np.concatenate([folds[i][1] for i in (range(2) if first_half else range(2, 4))])
        other = np.concatenate([folds[i][1] for i in (range(2, 4) if first_half else range(2))])
        model = learner().fit(X[train_idx], log_y[train_idx])
        cal_residual = log_y[cal_idx] - model.predict(X[cal_idx])
        low, high = (float(v) for v in np.quantile(cal_residual, [0.05, 0.95]))
        other_pred = model.predict(X[other])
        return low, high, coverage(other_pred + low, other_pred + high, log_y[other]), len(cal_idx)

    split_results = [half_calibrated(True), half_calibrated(False)]
    split_low = float(np.mean([r[0] for r in split_results]))
    split_high = float(np.mean([r[1] for r in split_results]))
    split_calibration_rows = int(sum(r[3] for r in split_results))

    # ---- coverage by group and by growth stage ------------------------------------------
    frame = frame.assign(oofPerArea=np.exp(oof))
    covered = (log_y >= oof + cv_low) & (log_y <= oof + cv_high)
    frame = frame.assign(intervalCovers=covered,
                         intervalLowGPerPlant=np.exp(oof + cv_low) / DENSITY,
                         intervalHighGPerPlant=np.exp(oof + cv_high) / DENSITY)

    by_experiment = {}
    for experiment, sub in frame.groupby("experiment"):
        by_experiment[str(experiment)] = {
            "rows": int(len(sub)),
            "coverage": round(float(sub.intervalCovers.mean()), 4),
            "meanMeasuredGPerPlant": round(float(sub.freshShootMassG.mean()), 1),
            "meanIntervalWidthGPerPlant": round(
                float((sub.intervalHighGPerPlant - sub.intervalLowGPerPlant).mean()), 1),
        }

    bins = [(1, 5), (5, 10), (10, 15), (15, 20), (20, 25), (25, 30)]
    by_stage = {}
    for low_day, high_day in bins:
        sub = frame[(frame.daysAfterTransplant >= low_day) & (frame.daysAfterTransplant <= high_day)]
        if sub.empty:
            continue
        by_stage[f"{low_day}-{high_day} DAT"] = {
            "rows": int(len(sub)),
            "coverage": round(float(sub.intervalCovers.mean()), 4),
            "meanMeasuredGPerPlant": round(float(sub.freshShootMassG.mean()), 1),
            "meanIntervalWidthGPerPlant": round(
                float((sub.intervalHighGPerPlant - sub.intervalLowGPerPlant).mean()), 1),
        }

    # ---- width in absolute terms at three reference stages ------------------------------
    def interval_at(dat: float, air: float, root: float, ppfd: float) -> dict:
        value = float(oof_model.predict(np.array([[dat, air, root,
                                                   ppfd * PHOTOPERIOD * 3600 / 1e6]]))[0])
        return {
            "medianLikeGPerPlant": round(float(np.exp(value) / DENSITY), 1),
            "intervalLowGPerPlant": round(float(np.exp(value + cv_low) / DENSITY), 1),
            "intervalHighGPerPlant": round(float(np.exp(value + cv_high) / DENSITY), 1),
            "multiplicativeWidth": round(float(np.exp(cv_high - cv_low)), 2),
        }

    oof_model = learner().fit(X, log_y)
    reference_intervals = {
        "early (8 DAT, 24 C, 400 PPFD)": interval_at(8.0, 24.0, 24.0, 400.0),
        "mid (18 DAT, 24 C, 400 PPFD)": interval_at(18.0, 24.0, 24.0, 400.0),
        "late (28 DAT, 24 C, 400 PPFD)": interval_at(28.0, 24.0, 24.0, 400.0),
    }

    # ---- the holdout, once -------------------------------------------------------------
    final = safedata.load(ROOT / "ml" / "evaluation" / "phase29_harvest_final")
    holdout = final["holdout"]["observations"][0]

    served = safedata.load(V3)["interval"]
    payload = {
        "schema": "spaceagrisim.phase29_interval_audit/1",
        "generatedAt": stamp(),
        "servedInterval": {
            "artifact": "lettuce-earth-growth-v3",
            "kind": served["kind"],
            "logResidualLow": served["logResidualLow"],
            "logResidualHigh": served["logResidualHigh"],
            "multiplicativeWidth": round(float(np.exp(served["logResidualHigh"]
                                                      - served["logResidualLow"])), 2),
            "reportedOutOfFoldCoverage": served["outOfFoldCoverage"],
            "reproducedOutOfFoldCoverage": round(coverage(oof + cv_low, oof + cv_high, log_y), 4),
        },
        "calibration": {
            "method": "cross-conformal residual quantiles on the log target, pooled over four "
                      "leave-one-experiment-out folds",
            "exchangeabilityUnit": "individual plant-row, pooled across experiments",
            "calibrationResiduals": int(len(residual)),
            "nominalCoverage": 0.9,
        },
        "splitConformalComparison": {
            "logLow": round(split_low, 4),
            "logHigh": round(split_high, 4),
            "multiplicativeWidth": round(float(np.exp(split_high - split_low)), 2),
            "calibrationRows": split_calibration_rows,
            "coverageOnTheOtherHalf": [round(r[2], 4) for r in split_results],
            "agreementWithCvPlus": {
                "widthRatio": round(float(np.exp((split_high - split_low)
                                                 - (cv_high - cv_low))), 3),
                "reading": ("a width ratio near 1 means the two calibration paths agree; a ratio "
                            "far from 1 means the residual distribution depends on which "
                            "experiments happen to be in the calibration half"),
            },
        },
        "coverageByExperiment": by_experiment,
        "coverageByGrowthStage": by_stage,
        "widestDisagreement": max(by_experiment.items(),
                                  key=lambda kv: kv[1]["coverage"]),
        "referenceIntervals": reference_intervals,
        "holdoutCheck": {
            "observation": holdout["id"],
            "measuredG": holdout["measuredG"],
            "intervalLowG": holdout["intervalLowG"],
            "intervalHighG": holdout["intervalHighG"],
            "covered": bool(holdout["intervalLowG"] <= holdout["measuredG"] <= holdout["intervalHighG"]),
            "nObservations": 1,
            "reading": ("One observation covering the interval is not evidence of 90 % coverage. It "
                        "is recorded because it happened, and it cannot be used to claim the "
                        "interval is reliable on new environments."),
        },
        "conclusion": {
            "outOfFoldCoverageIsDescriptive": True,
            "canClaimIndependentCoverage": False,
            "why": ("The calibration residuals come from the same four experiments the coverage was "
                    "measured on, and the intervals are pooled across experiments whose yields "
                    "differ by a factor of nearly three. Coverage is therefore a statement about "
                    "held-out rows from experiments already represented in calibration, not about "
                    "a new site, and the width needed to reach nominal coverage is a factor of "
                    "about five."),
            "whatWouldBeNeeded": ("A set of independent experiments with all four model inputs, "
                                  "used only for calibration scoring, would let coverage be "
                                  "measured outside the training population. None exists in this "
                                  "repository."),
        },
    }
    save_json(OUT, payload)
    print(json.dumps({k: payload[k] for k in
                      ("servedInterval", "splitConformalComparison", "coverageByExperiment",
                       "coverageByGrowthStage")}, indent=1))


if __name__ == "__main__":
    main()
