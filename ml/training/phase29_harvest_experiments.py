"""Phase 29, step 2: can the harvest model be made to generalise? Six candidates, one protocol.

The rule this script follows
-----------------------------
Model choice is made on **leave-one-experiment-out cross-validation over the four training
experiments**, and nothing else. The pre-registered selection rule is in `SELECTION_RULE` below and
was written before any candidate was scored:

    primary criterion   lowest out-of-fold MAE in g fresh mass per m2
    tie-break           within 1 % of the best MAE, prefer the candidate whose extrapolation is
                        structurally safer - a saturating light response and a monotone growth
                        curve cannot run away outside the training box the way unconstrained trees
                        can. Order: structured-saturating > monotone-gbm > structured-ridge >
                        gbm-log > huber-gbm > rate-gbm.

The protected independent holdout (Touliatos et al. 2016) is **not read in this script at all**. It
is read once, by `phase29_harvest_final.py`, after the winner is fixed. The PeerJ development set is
scored here for information only and is not part of the selection rule; it is already spent, having
informed the v3 feature choice, so it can never be validation again.

Why these six
-------------
The diagnosis (`phase29_harvest_diagnosis.py`) found three things worth attacking:

1. the light response is the only clean within-experiment gradient, and it is three levels
   (DLI 11.52, 23.04, 43.2) - a learner with 220 unconstrained trees will not necessarily respect
   the shape of a light-response curve between them;
2. temperature is confounded with experiment identity, so any temperature coefficient is learned
   from four group contrasts and needs to be estimated by a parametric form, not by splits;
3. the growth curve rises over 2-29 DAT and the trees can only ever interpolate it.

So the candidates differ in *structure*, not in seed-hunting: saturating light response, monotone
constraints, parametric temperature terms, and one deliberately simple rate model as a control.

Output: `ml/evaluation/phase29_harvest_experiments`

Run: python ml/training/phase29_harvest_experiments.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares
from sklearn.ensemble import GradientBoostingRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from nasa_pipeline import save_json, stamp  # noqa: E402

DATA = ROOT / "data" / "processed" / "lettuce_earth.csv"
OUT = ROOT / "ml" / "evaluation" / "phase29_harvest_experiments"

DENSITY, PHOTOPERIOD, SEED = 25.0, 16.0, 42

SELECTION_RULE = {
    "primary": "lowest leave-one-experiment-out MAE in g fresh mass per m2",
    "tieBreak": "within 1 % of the best MAE, prefer the structurally safer extrapolation",
    "tieBreakOrder": ["structured-saturating", "monotone-gbm", "structured-ridge",
                      "gbm-log", "huber-gbm", "rate-gbm"],
    "writtenBeforeScoring": True,
    "holdoutNotReadHere": True,
}

# PeerJ (development, spent) - reported for information only.
PEERJ = [("baby-cos-upper", 697, 84.5), ("baby-cos-middle", 391, 123.8),
         ("baby-cos-lower", 322, 92.9), ("green-oak-upper", 697, 97.3),
         ("green-oak-middle", 391, 190.7), ("green-oak-lower", 322, 203.7)]
PEERJ_DENSITY, PEERJ_PHOTOPERIOD, PEERJ_AIR = 48.0, 12.0, 27.5


def mape(y, p) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(np.mean(np.abs((p - y) / y)) * 100)


def metrics(y, p) -> dict:
    y, p = np.asarray(y, float), np.asarray(p, float)
    residual = p - y
    return {
        "MAE": round(float(np.mean(np.abs(residual))), 1),
        "RMSE": round(float(np.sqrt(np.mean(residual ** 2))), 1),
        "MAPE": round(mape(y, p), 2),
        "medianAPE": round(float(np.median(np.abs((p - y) / y)) * 100), 2),
        "meanBiasError": round(float(np.mean(residual)), 1),
        "n": int(len(y)),
    }


# ------------------------------------------------------------------ candidate model forms

class StructuredSaturating:
    """yield/m2 = A * light(DLI) * growth(DAT) * temperature(air, root).

    * light: a saturating Mitscherlich response `1 - exp(-k * DLI)`, the standard shape for a
      light-limited crop and the reason a light-response curve has a shoulder rather than a slope.
    * growth: a scaled logistic in days after transplant.
    * temperature: a multiplicative Gaussian penalty around a fitted optimum in air and root
      temperature, which is what makes a stress response expressible at all.

    Every parameter has an interpretation and a bound, so the fit cannot produce a negative yield or
    a growth curve that diverges after the last observation.
    """

    name = "structured-saturating"

    def __init__(self) -> None:
        self.parameters: dict[str, float] = {}
        self._fitted = False

    @staticmethod
    def _predict(theta, dat, air, root, dli):
        log_a, k, r, t0, t_air, s_air, t_root, s_root = theta
        light = 1.0 - np.exp(-k * dli)
        growth = 1.0 / (1.0 + np.exp(-r * (dat - t0)))
        # A Gaussian penalty on each temperature, so a treatment far from the optimum costs yield.
        temp = np.exp(-0.5 * (((air - t_air) / s_air) ** 2 + ((root - t_root) / s_root) ** 2))
        scale = np.exp(log_a)
        return np.log(np.maximum(scale * light * growth * temp, 1e-9))

    def fit(self, dat, air, root, dli, y_log):
        # Start from the middle of every plausible range rather than from a random draw, so the fit
        # is deterministic and reproducible.
        theta0 = np.array([np.log(10_000.0), 0.06, 0.25, 15.0, 24.0, 8.0, 24.0, 8.0])
        lower = np.array([np.log(100.0), 1e-4, 0.02, 1.0, 15.0, 1.0, 15.0, 1.0])
        upper = np.array([np.log(1e6), 1.0, 2.0, 40.0, 35.0, 40.0, 35.0, 40.0])

        def residual(theta):
            return self._predict(theta, dat, air, root, dli) - y_log

        solution = least_squares(residual, theta0, bounds=(lower, upper), method="trf",
                                 max_nfev=4000)
        self.parameters = {k: float(v) for k, v in zip(
            ["logScale", "lightSaturationK", "growthRate", "growthMidpointDays",
             "airOptimumC", "airToleranceC", "rootOptimumC", "rootToleranceC"],
            solution.x)}
        self._fitted = True
        return self

    def predict_log(self, dat, air, root, dli) -> np.ndarray:
        theta = list(self.parameters.values())
        return self._predict(np.array(theta), dat, air, root, dli)

    def predict_per_area(self, dat, air, root, dli) -> np.ndarray:
        return np.exp(self.predict_log(dat, air, root, dli))


def structured_matrix(frame: pd.DataFrame) -> np.ndarray:
    dli = frame.ppfd.to_numpy(float) * PHOTOPERIOD * 3600.0 / 1e6
    dat = frame.daysAfterTransplant.to_numpy(float)
    air = frame.airTemperature.to_numpy(float)
    root = frame.rootTemperature.to_numpy(float)
    return np.column_stack([np.log(dat), dat, np.log(dli), np.log(dli) ** 2, air, root,
                            air * root / 100.0, np.log(dat) * np.log(dli)])


def build_candidates():
    """Every candidate as a callable: fit(train_idx) -> predict(frame) in g/m2."""
    def gbm(**kwargs):
        def factory():
            return GradientBoostingRegressor(n_estimators=220, learning_rate=0.05, max_depth=3,
                                             random_state=SEED, **kwargs)
        return factory

    def fit_gbm(factory, X, y):
        model = factory().fit(X, y)
        return lambda frame: np.exp(model.predict(X_of(frame)))

    dli = lambda frame: frame.ppfd.to_numpy(float) * PHOTOPERIOD * 3600.0 / 1e6
    X_of = lambda frame: np.column_stack([
        frame.daysAfterTransplant.to_numpy(float), frame.airTemperature.to_numpy(float),
        frame.rootTemperature.to_numpy(float), dli(frame)])

    def rate_gbm_fit(X, y_log, frame):
        """Predict log(yield per day) instead of log(yield): the DAT scaling is forced."""
        dat = frame.daysAfterTransplant.to_numpy(float)
        target = y_log - np.log(dat)
        model = gbm()().fit(X, target)
        return lambda f: np.exp(model.predict(X_of(f)) + np.log(f.daysAfterTransplant.to_numpy(float)))

    return {
        "gbm-log": lambda X, y, frame: fit_gbm(gbm(), X, y),
        # Monotone constraints need the histogram learner: sklearn's exact-variance
        # GradientBoostingRegressor has no monotonic_cst parameter, and a constrained model that
        # silently ignored the constraint would be worse than no candidate at all.
        "monotone-gbm": lambda X, y, frame: (lambda model: (
            model.fit(X, y), (lambda f: np.exp(model.predict(X_of(f)))))[1])(
            HistGradientBoostingRegressor(
                max_iter=220, learning_rate=0.05, max_leaf_nodes=8, random_state=SEED,
                monotonic_cst=[1, 0, 0, 1])),  # increasing in days after transplant and in DLI
        "huber-gbm": lambda X, y, frame: fit_gbm(
            gbm(loss="huber", alpha=0.9), X, y),
        "rate-gbm": lambda X, y, frame: rate_gbm_fit(X, y, frame),
        "structured-ridge": lambda X, y, frame: (lambda pipe: (
            pipe.fit(structured_matrix(frame), y),
            (lambda f: np.exp(pipe.predict(structured_matrix(f))))
        )[1])(Pipeline([("scale", StandardScaler()), ("ridge", Ridge(alpha=1.0))])),
        "structured-saturating": lambda X, y, frame: (lambda m: (
            m.fit(frame.daysAfterTransplant.to_numpy(float), frame.airTemperature.to_numpy(float),
                  frame.rootTemperature.to_numpy(float), dli(frame), y),
            (lambda f: m.predict_per_area(
                f.daysAfterTransplant.to_numpy(float), f.airTemperature.to_numpy(float),
                f.rootTemperature.to_numpy(float), dli(f)))
        )[1])(StructuredSaturating()),
    }


def main() -> None:
    frame = pd.read_csv(DATA).sort_values(
        ["experiment", "daysAfterTransplant", "ppfd"]).reset_index(drop=True)
    groups = frame.experiment.to_numpy()
    measured_per_area = frame.freshShootMassG.to_numpy(float) * DENSITY
    log_target = np.log(measured_per_area)
    X = np.column_stack([frame.daysAfterTransplant.to_numpy(float),
                         frame.airTemperature.to_numpy(float),
                         frame.rootTemperature.to_numpy(float),
                         frame.ppfd.to_numpy(float) * PHOTOPERIOD * 3600.0 / 1e6])
    folds = list(GroupKFold(n_splits=4).split(X, log_target, groups))

    results = {}
    for name, build in build_candidates().items():
        oof = np.zeros_like(measured_per_area)
        fold_mae = []
        for train_idx, test_idx in folds:
            train_frame = frame.iloc[train_idx]
            predict = build(X[train_idx], log_target[train_idx], train_frame)
            test_frame = frame.iloc[test_idx]
            oof[test_idx] = predict(test_frame)
            fold_mae.append(round(float(np.mean(np.abs(
                oof[test_idx] - measured_per_area[test_idx]))), 1))

        # Conformal interval from the out-of-fold multiplicative residuals, in log space.
        log_residual = np.log(measured_per_area) - np.log(np.maximum(oof, 1e-9))
        low, high = (float(v) for v in np.quantile(log_residual, [0.05, 0.95]))
        covered = (np.log(measured_per_area) >= np.log(np.maximum(oof, 1e-9)) + low) & (
            np.log(measured_per_area) <= np.log(np.maximum(oof, 1e-9)) + high)

        # Full-data refit, then the (informational) PeerJ development score.
        predict_all = build(X, log_target, frame)
        peerj_predictions = []
        for obs_id, ppfd, measured in PEERJ:
            obs = pd.DataFrame([{
                "daysAfterTransplant": 28.0, "airTemperature": PEERJ_AIR,
                "rootTemperature": PEERJ_AIR, "ppfd": float(ppfd)}])
            per_area = float(predict_all(obs)[0])
            peerj_predictions.append({"id": obs_id, "measuredG": measured,
                                      "predictedG": round(per_area / PEERJ_DENSITY, 1)})

        entry = {
            "outOfFold": metrics(measured_per_area, oof),
            "foldMAE": fold_mae,
            "interval": {"logLow": round(low, 4), "logHigh": round(high, 4),
                         "multiplicativeWidth": round(float(np.exp(high - low)), 2),
                         "outOfFoldCoverage": round(float(np.mean(covered)), 4),
                         "nominalCoverage": 0.9},
            "developmentPeerJ": {
                "countsAsValidation": False,
                "MAPE": round(mape([r["measuredG"] for r in peerj_predictions],
                                   [r["predictedG"] for r in peerj_predictions]), 2),
                "medianRatio": round(float(np.median([r["predictedG"] / r["measuredG"]
                                                      for r in peerj_predictions])), 3),
                "rows": peerj_predictions,
            },
        }
        if isinstance(build, object) and name == "structured-saturating":
            entry["fittedParameters"] = None  # filled after the standalone fit below
        results[name] = entry

    # The structured model's parameters, from a fit on all four experiments, are reported in full so
    # the temperature optimum and the light-saturation constant can be argued about on their merits.
    structured = StructuredSaturating().fit(
        frame.daysAfterTransplant.to_numpy(float), frame.airTemperature.to_numpy(float),
        frame.rootTemperature.to_numpy(float),
        frame.ppfd.to_numpy(float) * PHOTOPERIOD * 3600.0 / 1e6, log_target)
    results["structured-saturating"]["fittedParameters"] = structured.parameters

    # ---- pre-registered selection ------------------------------------------------------
    best_mae = min(entry["outOfFold"]["MAE"] for entry in results.values())
    within = [name for name, entry in results.items()
              if entry["outOfFold"]["MAE"] <= best_mae * 1.01]
    order = SELECTION_RULE["tieBreakOrder"]
    selected = min(within, key=order.index) if within else min(
        results, key=lambda k: results[k]["outOfFold"]["MAE"])

    payload = {
        "schema": "spaceagrisim.phase29_harvest_experiments/1",
        "generatedAt": stamp(),
        "protocol": {
            "split": "leave-one-experiment-out (GroupKFold, 4 folds), identical folds for every "
                     "candidate",
            "target": "log(fresh yield per m2); per-area yield reconstructed as per-plant mass x 25",
            "seed": SEED,
            "sampleCount": int(len(frame)),
            "groupCount": int(frame.experiment.nunique()),
            "trainingDensityPlantsPerM2": DENSITY,
            "trainingPhotoperiodHours": PHOTOPERIOD,
        },
        "selectionRule": SELECTION_RULE,
        "candidates": results,
        "selected": selected,
        "selectedMAE": results[selected]["outOfFold"]["MAE"],
        "bestMAE": best_mae,
        "withinOnePercent": within,
        "holdoutReadHere": False,
        "honestLimits": [
            "Four experiments by one research group is the whole training population; every "
            "out-of-fold score here is an interpolative claim about that population.",
            "Selecting the best of six candidates on the same four folds inflates the winner's "
            "apparent quality. The inflation is not corrected for, and the winner must be judged "
            "on the protected holdout, not here.",
            "The PeerJ scores are development data and are excluded from the selection rule.",
        ],
    }
    save_json(OUT, payload)
    print(f"selected: {selected} (MAE {results[selected]['outOfFold']['MAE']} g/m2, "
          f"best {best_mae})")
    for name, entry in sorted(results.items(), key=lambda kv: kv[1]["outOfFold"]["MAE"]):
        print(f"  {name:24s} MAE {entry['outOfFold']['MAE']:8.1f}  MAPE {entry['outOfFold']['MAPE']:6.1f}"
              f"  coverage {entry['interval']['outOfFoldCoverage']:.3f}"
              f"  width x{entry['interval']['multiplicativeWidth']:.2f}"
              f"  peerJ MAPE {entry['developmentPeerJ']['MAPE']:6.1f}")


if __name__ == "__main__":
    main()
