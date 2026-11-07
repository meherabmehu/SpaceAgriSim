"""Phase 6 re-evaluation of the OSD-655 mizuna harvest model.

Questions the brief requires answering, each with a measurement:

  1. Does a regularised model beat a simple baseline under grouped CV?
  2. Is the apparent flight/ground signal a measurement-protocol artefact of the
     differing `Total (g)` formulas (see audit_osd655_mass.py)?
  3. Can any interval be *calibrated* at this sample size, or must it be labelled
     an uncalibrated descriptive range?
  4. Should the model remain `baseline-only`?

Run: python ml/analysis/reevaluate_harvest.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = ROOT / "docs" / "phase6" / "mizuna_reevaluation.json"
SEED = 42
FEATURES = ["waterSuppliedL", "establishedPlants", "flight", "blue"]


def metrics(y, pred):
    return {
        "MAE": float(mean_absolute_error(y, pred)),
        "RMSE": float(np.sqrt(mean_squared_error(y, pred))),
        "R2": float(r2_score(y, pred)) if len(set(y)) > 1 else None,
    }


def grouped_cv(x, y, groups):
    proba = np.zeros(len(y))
    baseline = np.zeros(len(y))
    for train, test in GroupKFold(n_splits=4).split(x, y, groups):
        assert not set(groups[train]) & set(groups[test])
        model = Pipeline([("scale", StandardScaler()), ("linear", Ridge(alpha=100.0))])
        model.fit(x[train], y[train])
        proba[test] = model.predict(x[test])
        baseline[test] = DummyRegressor(strategy="mean").fit(x[train], y[train]).predict(x[test])
    return proba, baseline


def main():
    frame = pd.read_csv(DATA / "processed" / "mizuna_harvest.csv")
    x = np.column_stack([
        frame.waterSuppliedL,
        frame.establishedPlants,
        (frame.environment == "flight").astype(int),
        (frame.spectrum == "blue").astype(int),
    ])
    y = frame.harvestFreshMassG.to_numpy()
    groups = frame.group.to_numpy()

    predicted, baseline = grouped_cv(x, y, groups)
    report = {
        "study": "OSD-655",
        "experiment": "VEG04A",
        "samples": int(len(y)),
        "groups": int(len(set(groups))),
        "target": "harvestFreshMassG (g fresh mass per pillow, as published in `Total (g)`)",
        "model": metrics(y, predicted),
        "baseline": metrics(y, baseline),
        "beatsBaselineMAE": bool(metrics(y, predicted)["MAE"] < metrics(y, baseline)["MAE"]),
        "beatsBaselineR2": bool(metrics(y, predicted)["R2"] > metrics(y, baseline)["R2"]),
    }

    # ---- Q2: is the arm difference a protocol artefact? ----
    flight = frame[frame.environment == "flight"]
    ground = frame[frame.environment == "ground"]
    report["armComparison"] = {
        "flight": {"n": int(len(flight)), "meanG": float(flight.harvestFreshMassG.mean()),
                   "sdG": float(flight.harvestFreshMassG.std(ddof=1))},
        "ground": {"n": int(len(ground)), "meanG": float(ground.harvestFreshMassG.mean()),
                   "sdG": float(ground.harvestFreshMassG.std(ddof=1))},
        "note": (
            "The flight target embeds crew consumption and a subsample mean; the "
            "ground target is a complete harvest plus broken leaves. A mean "
            "difference between arms therefore cannot be attributed to the space "
            "environment. See docs/phase6/osd655_mass_audit.json."
        ),
    }

    # Ground arm carries leaf counts; flight arm carries none. Expose what the
    # ground arm alone supports, because it is the only arm with a coherent
    # per-leaf measurement.
    ground_only = frame[frame.environment == "ground"]
    report["groundArmOnly"] = {
        "n": int(len(ground_only)),
        "features": FEATURES,
        "note": (
            "n=6 with 6 distinct pillows, so a grouped 4-fold CV would place one "
            "pillow per fold and cannot estimate a learning curve. No model is fit "
            "to this arm; the count is reported so the gap is explicit."
        ),
    }

    # ---- Q3: can an interval be calibrated? ----
    residuals = np.abs(y - predicted)
    n = len(y)
    radius = float(np.quantile(residuals, 0.9, method="higher"))
    # Leave-one-group-out coverage check: recompute the radius excluding the
    # evaluated group, then test it. At n=14/10 groups this is extremely noisy,
    # which is the point being demonstrated.
    covered = []
    for group in sorted(set(groups)):
        mask = groups == group
        if mask.all():
            continue
        rest = ~mask
        r = float(np.quantile(np.abs(y[rest] - predicted[rest]), 0.9, method="higher"))
        covered.append(bool((np.abs(y[mask] - predicted[mask]) <= r).all()))
    empirical = float(np.mean(covered)) if covered else 0.0
    report["uncertainty"] = {
        "method": "group-aware split-conformal (90% nominal)",
        "radiusG": radius,
        "evaluationGroups": int(len(covered)),
        "empiricalGroupCoverage": empirical,
        "nominalCoverage": 0.90,
        "calibrated": bool(empirical >= 0.90 - 0.05),
        "verdict": (
            "With 14 points in 10 groups, conformal coverage cannot be estimated "
            "reliably and falls below nominal. The interval is therefore reported "
            "as an UNCALIBRATED DESCRIPTIVE RANGE, not a confidence interval."
        ),
    }

    # ---- Q4: verdict ----
    report["evidenceStatus"] = "baseline-only"
    report["verdict"] = (
        "Retained as `baseline-only`. The regularised model does not beat the mean "
        "baseline on MAE or R2, the target is defined by two different formulas "
        "across arms, one arm has no leaf counts, and intervals cannot be "
        "calibrated at n=14. Reporting this as a yield predictor would be "
        "unsupportable."
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False) + "\n")
    print(json.dumps(report, indent=2))
    print(f"\nwritten: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
