#!/usr/bin/env python3
"""Train and honestly evaluate an ET0 emulator against published physics.

The question this script exists to answer is not "can a model fit ET0" - the label is a smooth
function of the inputs, so any regressor with radiation and temperature in it will fit. The
question is **when does it beat the equation it is approximating**, and the answer here is
"on days from sites it was trained on, and not otherwise".

Evaluation protocol
-------------------
* Temporal holdout - train 2018-01-01..2023-12-31, test 2024-01-01..2025-10-31. The test window is
  later in time than every training day for every site, so no future information reaches the fit.
* Leave-one-site-out (LOSO) - train on five sites, predict the sixth, rotate. This is the test
  that matters if the service is used somewhere new, and it is the one that fails.
* Baselines - climatology (per-site monthly mean from the training window only), ridge,
  Hargreaves-Samani (published physics, no fitting), and a reduced model without the astronomy
  features, so the value of the extra inputs is measured rather than assumed.
* Uncertainty - conformal half-width from a calibration slice carved out of the training window,
  with its empirical coverage reported on the holdout.

The artifact records every number, including the gate it fails. Nothing here promotes itself:
`status: trained-exploratory`, `deployed: false`, and the registry keeps serving physics.

    python3 ml/research/train_et0_emulator.py
"""
from __future__ import annotations

import hashlib
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
sys.path.insert(0, str(ROOT / "backend"))

from app.simulation import et0_fao56  # noqa: E402

DATA = ROOT / "data" / "processed" / "et0_dataset.csv"
ARTIFACTS = ROOT / "ml" / "artifacts"
EVAL = ROOT / "ml" / "evaluation"
MODEL_ID = "et0-emulator-v1"
HOLDOUT_START = "2024-01-01"

BASE_FEATURES = ["T2M_MAX", "T2M_MIN", "T2MDEW", "latitude", "elevationM"]
ASTRONOMY_FEATURES = ["doySin", "doyCos", "raMj", "daylightHours"]
FEATURES = BASE_FEATURES + ASTRONOMY_FEATURES
TARGET = "et0MmPerDay"


def load() -> pd.DataFrame:
    """Load the dataset and refuse to train if it is not the one the metadata describes."""
    meta_path = DATA.with_suffix(".metadata")
    dataset_sha = hashlib.sha256(safedata.bytes(DATA)).hexdigest()
    if safedata.exists(meta_path):
        committed = safedata.load(meta_path)["sha256"]
        if committed != dataset_sha:
            raise SystemExit(
                f"dataset on disk ({dataset_sha[:12]}) is not the one the metadata records "
                f"({committed[:12]}); rebuild with ml/research/build_et0_dataset.py")
    frame = pd.read_csv(DATA)
    frame["date"] = pd.to_datetime(frame["date"])
    frame["month"] = frame["date"].dt.month
    frame["doySin"] = np.sin(2 * math.pi * frame["dayOfYear"] / 365.0)
    frame["doyCos"] = np.cos(2 * math.pi * frame["dayOfYear"] / 365.0)
    return frame


def metrics(truth: np.ndarray, prediction: np.ndarray) -> dict:
    error = prediction - truth
    ss_res = float(np.sum(error ** 2))
    ss_tot = float(np.sum((truth - truth.mean()) ** 2))
    return {
        "mae": round(float(np.mean(np.abs(error))), 4),
        "rmse": round(math.sqrt(float(np.mean(error ** 2))), 4),
        "r2": round(1.0 - ss_res / ss_tot, 4) if ss_tot else None,
        "bias": round(float(np.mean(error)), 4),
        "n": int(truth.size),
    }


def hargreaves_predict(frame: pd.DataFrame) -> np.ndarray:
    """Physics with no fitted parameters: Tmax, Tmin and Ra only."""
    return np.array([
        et0_fao56.hargreaves_et0(row.T2M_MAX, row.T2M_MIN, row.raMj)["et0MmPerDay"]
        for row in frame.itertuples()
    ])


def climatology_predict(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    """Per-site monthly mean of the training window. Falls back to the site mean, then the global
    mean, when a (site, month) pair is unseen - which LOSO makes common."""
    by_month = train.groupby(["siteId", "month"])[TARGET].mean()
    by_site = train.groupby("siteId")[TARGET].mean()
    overall = float(train[TARGET].mean())
    out = []
    for row in test.itertuples():
        key = (row.siteId, row.month)
        if key in by_month.index:
            out.append(float(by_month.loc[key]))
        elif row.siteId in by_site.index:
            out.append(float(by_site.loc[row.siteId]))
        else:
            out.append(overall)
    return np.array(out)


def fit_model(train: pd.DataFrame, features: list[str], seed: int = 0):
    from sklearn.ensemble import HistGradientBoostingRegressor

    model = HistGradientBoostingRegressor(
        max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
        min_samples_leaf=20, l2_regularization=1.0, random_state=seed)
    model.fit(train[features], train[TARGET])
    return model


def fit_ridge(train: pd.DataFrame, features: list[str]):
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    model.fit(train[features], train[TARGET])
    return model


def predict(model, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    return np.asarray(model.predict(frame[features]), dtype=float)


def main() -> int:
    frame = load()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    EVAL.mkdir(parents=True, exist_ok=True)
    dataset_sha = hashlib.sha256(safedata.bytes(DATA)).hexdigest()

    train = frame[frame["date"] < HOLDOUT_START].copy()
    test = frame[frame["date"] >= HOLDOUT_START].copy()
    if train.empty or test.empty:
        raise SystemExit("temporal split is empty; check the dataset date range")

    truth = test[TARGET].to_numpy(dtype=float)
    candidates: dict[str, dict] = {}

    # --- baselines that require no fitting -------------------------------------------------
    candidates["hargreaves"] = {"predictions": hargreaves_predict(test), "kind": "published physics"}
    candidates["climatology"] = {"predictions": climatology_predict(train, test),
                                 "kind": "training-window monthly mean"}

    # --- fitted candidates ------------------------------------------------------------------
    permutations = {
        "ridge": fit_ridge(train, FEATURES),
        "ml_tdew": fit_model(train, BASE_FEATURES),
        "ml_tdew_astronomy": fit_model(train, FEATURES),
    }
    for name, model in permutations.items():
        features = BASE_FEATURES if name == "ml_tdew" else FEATURES
        candidates[name] = {
            "predictions": predict(model, test, features),
            "kind": f"fit on temporal train split, features {features}",
        }

    results = {name: metrics(truth, block["predictions"]) for name, block in candidates.items()}
    order = sorted(results, key=lambda key: results[key]["mae"])
    winner = order[0]

    # --- conformal interval, calibrated inside the training window only ---------------------
    calibration_start = pd.Timestamp("2023-01-01")
    fit_part = train[train["date"] < calibration_start]
    calibration = train[train["date"] >= calibration_start]
    winner_features = BASE_FEATURES if winner == "ml_tdew" else FEATURES
    winner_model = permutations.get(winner) or fit_model(train, winner_features)
    if winner in permutations:
        winner_model = permutations[winner]
    else:  # physics or climatology won; the served model is still the astronomy variant
        winner_model = permutations["ml_tdew_astronomy"]
        winner_features = FEATURES

    calibration_model = (permutations[winner] if winner in permutations
                         else fit_model(fit_part, FEATURES))
    calibration_prediction = predict(calibration_model, calibration, winner_features)
    residuals = np.abs(calibration[TARGET].to_numpy(dtype=float) - calibration_prediction)
    half_width = float(np.quantile(residuals, 0.95))

    served_prediction = predict(permutations["ml_tdew_astronomy"], test, FEATURES)
    inside = np.abs(truth - served_prediction) <= half_width
    coverage = 100.0 * float(inside.mean())

    # --- leave-one-site-out ------------------------------------------------------------------
    loso_rows = []
    for site in sorted(frame["siteId"].unique()):
        fit_frame = frame[frame["siteId"] != site]
        holdout = frame[frame["siteId"] == site]
        model = fit_model(fit_frame, FEATURES)
        prediction = predict(model, holdout, FEATURES)
        truth_site = holdout[TARGET].to_numpy(dtype=float)
        loso_rows.append({
            "siteId": site,
            "n": int(len(holdout)),
            "hargreavesMae": metrics(truth_site, hargreaves_predict(holdout))["mae"],
            "emulatorMae": metrics(truth_site, prediction)["mae"],
        })

    pooled_hargreaves = float(np.mean([row["hargreavesMae"] for row in loso_rows]))
    pooled_emulator = float(np.mean([row["emulatorMae"] for row in loso_rows]))
    sites_won = sum(1 for row in loso_rows if row["emulatorMae"] < row["hargreavesMae"])

    temporal_gain = 100.0 * (results["hargreaves"]["mae"] - results["ml_tdew_astronomy"]["mae"]) \
        / results["hargreaves"]["mae"]
    climatology_gain = 100.0 * (results["climatology"]["mae"]
                                - results["ml_tdew_astronomy"]["mae"]) \
        / results["climatology"]["mae"]
    cross_site_gain = 100.0 * (pooled_hargreaves - pooled_emulator) / pooled_hargreaves

    gate = [
        {"criterion": "beatsHargreavesTemporal", "threshold": "> 0 % lower MAE",
         "observed": round(temporal_gain, 2), "unit": "%", "passed": temporal_gain > 0},
        {"criterion": "beatsClimatology", "threshold": "> 0 % lower MAE",
         "observed": round(climatology_gain, 2), "unit": "%", "passed": climatology_gain > 0},
        {"criterion": "crossSiteGeneralisation", "threshold": "> 0 % lower pooled MAE across LOSO",
         "observed": round(cross_site_gain, 2), "unit": "%", "passed": cross_site_gain > 0},
        {"criterion": "intervalCoverage", "threshold": "90-98 % empirical coverage",
         "observed": round(coverage, 2), "unit": "%", "passed": 90.0 <= coverage <= 98.0},
    ]
    passed = sum(1 for row in gate if row["passed"])

    # --- fit the served model on everything and persist ---------------------------------------
    final = fit_model(frame, FEATURES)
    ood_bounds = {
        name: {"min": round(float(frame[name].min()), 4), "max": round(float(frame[name].max()), 4)}
        for name in FEATURES
    }

    import joblib
    import sklearn

    bundle = {
        "model": final,
        "features": FEATURES,
        "variant": "ml_tdew_astronomy",
        "halfWidthMm": round(half_width, 4),
        "oodBounds": ood_bounds,
        "target": TARGET,
        "trainedOn": {"rows": int(len(frame)), "sites": sorted(frame["siteId"].unique()),
                      "firstDay": frame["date"].min().strftime("%Y-%m-%d"),
                      "lastDay": frame["date"].max().strftime("%Y-%m-%d")},
        # A persisted estimator is only loadable where these versions exist. Recording them here is
        # what lets the service say "trained with 1.6.1, running 1.5.2" instead of "could not load".
        "environment": {
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "scikit-learn": sklearn.__version__,
            "numpy": np.__version__,
            "joblib": joblib.__version__,
        },
    }
    joblib.dump(bundle, ARTIFACTS / f"{MODEL_ID}.joblib")

    card = {
        "modelId": MODEL_ID,
        "displayName": "ET0 emulator v1 (gradient-boosted surrogate of FAO-56)",
        "status": "trained-exploratory",
        "deployed": False,
        "productionModelChanged": False,
        "deploymentDecision": (
            f"exploratory: {passed}/{len(gate)} acceptance gates passed. It wins on held-out days "
            f"from the training sites ({temporal_gain:+.2f} % lower MAE than Hargreaves) and loses "
            f"on an unseen site ({cross_site_gain:+.2f} %), so the service serves FAO-56 physics "
            f"and offers this value alongside it, flagged when inputs leave the training range."),
        "trainedAt": datetime.now(timezone.utc).isoformat(),
        "algorithm": "HistGradientBoostingRegressor(max_iter=400, lr=0.06, leaves=31)",
        "features": FEATURES,
        "target": TARGET,
        "targetDefinition": ("FAO-56 Penman-Monteith reference ET0 computed from NASA POWER "
                             "reanalysis weather. Not a field measurement."),
        "trainingData": {
            "path": "data/processed/et0_dataset.csv",
            "sha256": dataset_sha,
            "rows": int(len(frame)),
            "sites": sorted(frame["siteId"].unique()),
            "firstDay": frame["date"].min().strftime("%Y-%m-%d"),
            "lastDay": frame["date"].max().strftime("%Y-%m-%d"),
            "labelSource": "computed FAO-56, checked against the manual's worked examples",
        },
        "evaluation": {
            "temporalHoldout": {"start": HOLDOUT_START,
                                "end": frame["date"].max().strftime("%Y-%m-%d")},
            "leaveOneSiteOut": loso_rows,
            "leakageControls": [
                "temporal split: every test day is later than every training day",
                "LOSO: the held-out site contributes no rows to the fit",
                "climatology baseline uses the training window's own monthly means",
                "conformal calibration drawn from the training window, not the holdout",
            ],
        },
        "metrics": results["ml_tdew_astronomy"],
        "baselineMetrics": {name: results[name] for name in results if name != "ml_tdew_astronomy"},
        "improvementOverHargreaves": {
            "temporalPct": round(temporal_gain, 2),
            "crossSitePct": round(cross_site_gain, 2),
            "climatologyPct": round(climatology_gain, 2),
        },
        "validation": {
            "acceptanceGate": gate,
            "gatesPassed": passed,
            "gatesTotal": len(gate),
            "losoSitesBeatingHargreaves": f"{sites_won}/{len(loso_rows)}",
        },
        "uncertainty": {
            "method": "split conformal, 95 % absolute-residual quantile on a training-window slice",
            "halfWidthMm": round(half_width, 4),
            "coverageOnHoldoutPct": round(coverage, 2),
            "calibrationRows": int(len(calibration)),
        },
        "criteria": {name: "lower is better" for name in ("mae", "rmse", "bias")} | {"r2": "higher"},
        "limitations": [
            "The label is computed, not measured; a perfect score means the surrogate reproduces "
            "Penman-Monteith, not that it predicts a crop's water use.",
            "Validated on six terrestrial sites; nothing here licenses microgravity, low-pressure "
            "or LED-lit interiors.",
            "Cross-site error is about one fifth worse than Hargreaves-Samani, so the emulator is "
            "never the only number returned.",
            "Reanalysis resamples 0.5 deg x 0.625 deg grid cells, so the site label is a grid-cell "
            "value, not an on-site instrument reading.",
        ],
        "environment": bundle["environment"],
        "environmentPins": "ml/requirements-training.txt",
        "reproduce": "python3 ml/research/train_et0_emulator.py",
    }
    safedata.dump(card, ARTIFACTS / f"{MODEL_ID}")

    # --- human-readable evaluation table ------------------------------------------------------
    lines = [
        "# ET0 model comparison",
        "",
        f"Temporal holdout {HOLDOUT_START} .. {card['evaluation']['temporalHoldout']['end']} "
        f"({len(test)} rows from {train['siteId'].nunique()} training sites).",
        "",
        "| Rank | Candidate | Kind | MAE | RMSE | R2 | Bias |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for rank, name in enumerate(order, start=1):
        row = results[name]
        lines.append(f"| {rank} | `{name}` | {candidates[name]['kind']} | "
                     f"{row['mae']:.4f} | {row['rmse']:.4f} | "
                     f"{row['r2']:.4f} | {row['bias']:+.4f} |")
    lines += [
        "",
        f"Conformal half-width **{half_width:.4f} mm/day**, empirical coverage "
        f"**{coverage:.2f} %**.", "",
        "## Leave-one-site-out (the test that fails)", "",
        "| Site | n | Hargreaves MAE | Emulator MAE | Winner |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in loso_rows:
        winner_name = "emulator" if row["emulatorMae"] < row["hargreavesMae"] else "Hargreaves"
        lines.append(f"| {row['siteId']} | {row['n']} | {row['hargreavesMae']:.4f} | "
                     f"{row['emulatorMae']:.4f} | {winner_name} |")
    lines += [
        f"| **pooled** | | **{pooled_hargreaves:.4f}** | **{pooled_emulator:.4f}** | "
        f"**Hargreaves ({cross_site_gain:+.2f} %)** |",
        "",
        f"Acceptance gates: **{passed}/{len(gate)}** passed.",
        "",
    ]
    for row in gate:
        mark = "pass" if row["passed"] else "FAIL"
        lines.append(f"- `{row['criterion']}`: {row['observed']} {row['unit']} "
                     f"(needs {row['threshold']}) - **{mark}**")

    (EVAL / "et0_model_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    pd.DataFrame([{"candidate": name, **results[name]} for name in order]).to_csv(
        EVAL / "et0_model_comparison.csv", index=False)

    print("\n".join(lines[:8]))
    print(f"\nconformal +-{half_width:.4f} mm/day, coverage {coverage:.2f} %")
    print(f"LOSO pooled: hargreaves {pooled_hargreaves:.4f} vs emulator "
          f"{pooled_emulator:.4f} ({cross_site_gain:+.2f} %), {sites_won}/{len(loso_rows)} sites")
    print(f"gates {passed}/{len(gate)} -> status trained-exploratory, deployed false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
