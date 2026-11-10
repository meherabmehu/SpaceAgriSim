"""Phase 29, step 3: the protected independent holdout, read exactly once.

Everything upstream of this file was decided without it: the diagnosis measured the training data,
the six candidates were scored by leave-one-experiment-out cross-validation, and the winner was
fixed by a rule written down before any candidate was scored. This script takes that winner, refits
it on all four training experiments, and scores it against Touliatos et al. (2016) once.

What the holdout is, precisely
------------------------------
One observation: horizontal hydroponics at 50 plants/m2, 16 h photoperiod, 455 umol/m2/s, air
17-18 C, harvested at day 35, 138 +/- 6 g per plant over n = 40.

Three of its four inputs are **outside the model's declared applicability domain**
(daysAfterTransplant 35 > 29, airTemperature 17 < 20, rootTemperature assumed 17 < 20). That is
recorded, not waved away: the honest reading of a failed score here is "the model does not transfer
to an environment outside its declared domain", not "the model is a bad interpolator". Both readings
are reported.

The 30 % acceptance criterion is **not modified**. The pass/fail verdict is computed against it for
whichever candidate wins, including when the answer is fail.

Promotion rule, fixed here
--------------------------
A new artifact is written only if it beats the served v3 on the protected holdout AND passes the
30 % criterion. Otherwise nothing is registered: the experiment is recorded in
`ml/evaluation/phase29_harvest_final.json` and the served model does not change. Either way the
result is written down.

Run: python ml/training/phase29_harvest_final.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from nasa_pipeline import save_json, stamp  # noqa: E402

DATA = ROOT / "data" / "processed" / "lettuce_earth.csv"
EXPERIMENTS = ROOT / "ml" / "evaluation" / "phase29_harvest_experiments.json"
ARTIFACTS = ROOT / "ml" / "artifacts"
OUT = ROOT / "ml" / "evaluation" / "phase29_harvest_final.json"
NEW_MODEL_ID = "lettuce-earth-growth-v4"

DENSITY, PHOTOPERIOD, SEED = 25.0, 16.0, 42
ACCEPTANCE_PCT = 30.0  # unchanged since Phase 19

TOULIATOS = [{"id": "hhs-50", "system": "horizontal hydroponic", "density": 50.0,
              "ppfd": 455.0, "ppfdRange": [340.0, 570.0], "measuredG": 138.0, "seG": 6.0, "n": 40,
              "air": 17.5, "dat": 35.0, "photoperiod": 16.0}]


def feature_matrix(frame: pd.DataFrame) -> np.ndarray:
    dli = frame.ppfd.to_numpy(float) * PHOTOPERIOD * 3600.0 / 1e6
    return np.column_stack([frame.daysAfterTransplant.to_numpy(float),
                            frame.airTemperature.to_numpy(float),
                            frame.rootTemperature.to_numpy(float), dli])


def build_selected(name: str):
    """Rebuild the winning candidate exactly as `phase29_harvest_experiments.py` defined it."""
    if name == "monotone-gbm":
        return HistGradientBoostingRegressor(max_iter=220, learning_rate=0.05, max_leaf_nodes=8,
                                             random_state=SEED, monotonic_cst=[1, 0, 0, 1])
    if name == "gbm-log":
        return GradientBoostingRegressor(n_estimators=220, learning_rate=0.05, max_depth=3,
                                         random_state=SEED)
    if name == "huber-gbm":
        return GradientBoostingRegressor(n_estimators=220, learning_rate=0.05, max_depth=3,
                                         random_state=SEED, loss="huber", alpha=0.9)
    raise SystemExit(f"candidate {name!r} has no serialisable builder here")


def domain_from_data(frame: pd.DataFrame) -> dict:
    """Derive the applicability domain from the training rows instead of hardcoding it.

    The v3 artifact hardcoded `dailyLightIntegral` to a maximum of 34.5 while the training design
    reaches 43.2, so it simultaneously refused valid light levels and advertised unsupported ones.
    A derived domain cannot drift from the data it describes, and a test asserts the derivation.
    """
    dli = frame.ppfd.to_numpy(float) * PHOTOPERIOD * 3600.0 / 1e6
    return {
        "daysAfterTransplant": {"min": float(frame.daysAfterTransplant.min()),
                                "max": float(frame.daysAfterTransplant.max())},
        "airTemperature": {"min": float(frame.airTemperature.min()),
                          "max": float(frame.airTemperature.max())},
        "rootTemperature": {"min": float(frame.rootTemperature.min()),
                           "max": float(frame.rootTemperature.max())},
        "dailyLightIntegral": {"min": round(float(dli.min()), 2), "max": round(float(dli.max()), 2)},
    }


def violations(domain: dict, obs: dict) -> list[str]:
    dli = obs["ppfd"] * obs["photoperiod"] * 3600 / 1e6
    found = []
    for name, value in (("daysAfterTransplant", obs["dat"]), ("airTemperature", obs["air"]),
                        ("rootTemperature", obs["air"]), ("dailyLightIntegral", dli)):
        bounds = domain[name]
        if not bounds["min"] <= value <= bounds["max"]:
            found.append(f"{name}={value:g} outside [{bounds['min']:g}, {bounds['max']:g}]")
    return found


def main() -> None:
    frame = pd.read_csv(DATA).sort_values(
        ["experiment", "daysAfterTransplant", "ppfd"]).reset_index(drop=True)
    experiments = json.loads(EXPERIMENTS.read_text())
    selected = experiments["selected"]
    X = feature_matrix(frame)
    y = np.log(frame.freshShootMassG.to_numpy(float) * DENSITY)
    groups = frame.experiment.to_numpy()

    # Out-of-fold predictions for the selected candidate, needed for its interval.
    oof = np.zeros_like(y)
    for train_idx, test_idx in GroupKFold(n_splits=4).split(X, y, groups):
        model = build_selected(selected).fit(X[train_idx], y[train_idx])
        oof[test_idx] = model.predict(X[test_idx])
    log_residual = y - oof
    low, high = (float(v) for v in np.quantile(log_residual, [0.05, 0.95]))

    served = build_selected(selected).fit(X, y)
    domain = domain_from_data(frame)

    scored = []
    for obs in TOULIATOS:
        dli = obs["ppfd"] * obs["photoperiod"] * 3600 / 1e6
        per_area = float(np.exp(served.predict(np.array([[
            obs["dat"], obs["air"], obs["air"], dli]]))[0]))
        per_plant = per_area / obs["density"]
        scored.append({
            "id": obs["id"], "system": obs["system"], "density": obs["density"],
            "measuredG": obs["measuredG"], "measuredSeG": obs["seG"], "n": obs["n"],
            "predictedG": round(per_plant, 1),
            "intervalLowG": round(float(np.exp(np.log(per_area) + low) / obs["density"]), 1),
            "intervalHighG": round(float(np.exp(np.log(per_area) + high) / obs["density"]), 1),
            "ratio": round(per_plant / obs["measuredG"], 3),
            "percentageError": round(100 * abs(per_plant - obs["measuredG"]) / obs["measuredG"], 2),
            "domainViolations": violations(domain, obs),
        })

    holdout_mape = float(np.mean([row["percentageError"] for row in scored]))
    passed = holdout_mape <= ACCEPTANCE_PCT
    interval_covers = all(row["intervalLowG"] <= row["measuredG"] <= row["intervalHighG"]
                          for row in scored)

    baseline_mape = experiments["candidates"]["gbm-log"].get("holdoutMAPE")  # not stored; recomputed below
    v3 = json.loads((ARTIFACTS / "lettuce-earth-growth-v3.json").read_text())
    v3_holdout = v3["validation"]["independent"]["metrics"]["MAPE"]

    payload = {
        "schema": "spaceagrisim.phase29_harvest_final/1",
        "generatedAt": stamp(),
        "candidateUnderTest": selected,
        "whyThisCandidate": experiments["selectionRule"]["primary"],
        "holdout": {
            "study": ("Touliatos D, Dodd IC, McAinsh M (2016) Vertical farming increases lettuce "
                      "yield per unit area compared to conventional horizontal hydroponics. "
                      "Food and Energy Security 5(3):184-191, doi:10.1002/fes3.83"),
            "license": "publisher open access; values transcribed, not redistributed as data",
            "observations": scored,
            "nObservations": len(scored),
            "MAPE": round(holdout_mape, 2),
            "acceptanceCriterionPct": ACCEPTANCE_PCT,
            "passed": bool(passed),
            "interval": {"logLow": round(low, 4), "logHigh": round(high, 4),
                         "coversTheObservation": interval_covers},
            "priorResultPhase19_v3": round(float(v3_holdout), 2),
            "changeVsV3PercentagePoints": round(holdout_mape - float(v3_holdout), 2),
        },
        "holdoutProvenance": {
            "usedInFitting": False,
            "usedInModelSelection": False,
            "usedInFeatureSelection": False,
            "timesReadAcrossPhases": [
                "Phase 19: scored once against v3 (41.6 %).",
                "Phase 28: quoted from the artifact when building the workflow UI; no new "
                "inspection of the observation itself.",
                "Phase 29: read once here, after the candidate was fixed.",
            ],
            "pristineClaim": ("This is NOT an untouched final test set. Its value has been known "
                              "since Phase 19, and a one-observation holdout cannot be called "
                              "untouched in any meaningful statistical sense."),
        },
        "domainOfTheHoldout": {
            "violations": scored[0]["domainViolations"],
            "reading": ("Three of the four inputs lie outside the declared applicability domain, "
                        "so this is an extrapolation test. A failure here is evidence about "
                        "transfer beyond the domain, and is not by itself evidence that the model "
                        "interpolates badly inside it."),
        },
        "outcome": "A-pass" if passed else "B-fail",
        "promotion": {
            "rule": ("register a new artifact only if the candidate beats the served v3 on this "
                     "holdout and passes the 30 % criterion"),
            "beatsV3": bool(holdout_mape < float(v3_holdout) - 1.0),
            "promoted": False,
            "reason": "",
        },
        "notChanged": ["the 30 % acceptance criterion", "the holdout observations",
                       "the evaluation metric"],
    }

    payload["promotion"]["promoted"] = bool(passed and payload["promotion"]["beatsV3"])
    payload["promotion"]["reason"] = (
        "passed the criterion and improved on v3" if payload["promotion"]["promoted"] else
        f"holdout MAPE {holdout_mape:.1f} % against a {ACCEPTANCE_PCT:.0f} % criterion; "
        "the candidate stays an experiment and no artifact is registered")

    save_json(OUT, payload)
    print(json.dumps({k: payload[k] for k in ("candidateUnderTest", "outcome", "promotion")},
                     indent=1))
    print(json.dumps(payload["holdout"], indent=1))


if __name__ == "__main__":
    main()
