"""Train measured-data models offline; save portable JSON, never executable pickle."""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.feature_selection import SelectKBest, VarianceThreshold, f_classif
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score, mean_absolute_error,
                             mean_squared_error, precision_score, r2_score, recall_score, roc_auc_score)
from sklearn.model_selection import GridSearchCV, GroupKFold, StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from nasa_pipeline import DATA, save_json, stamp, validate

ARTIFACTS = ROOT / "ml" / "artifacts"
EVALUATION = ROOT / "ml" / "evaluation"
SEED = 42


def regression_metrics(y, prediction):
    return {"MAE": float(mean_absolute_error(y, prediction)), "RMSE": float(np.sqrt(mean_squared_error(y, prediction))), "R2": float(r2_score(y, prediction))}


def portable_linear(model):
    scale = model.named_steps["scale"]
    linear = model.named_steps["linear"]
    return {"mean": scale.mean_.tolist(), "scale": scale.scale_.tolist(), "coefficients": np.ravel(linear.coef_).tolist(), "intercept": float(np.ravel([linear.intercept_])[0])}


def train_harvest():
    frame = pd.read_csv(DATA / "processed" / "mizuna_harvest.csv")
    names = ["waterSuppliedL", "establishedPlants", "flight", "blue"]
    x = np.column_stack([frame.waterSuppliedL, frame.establishedPlants, (frame.environment == "flight").astype(int), (frame.spectrum == "blue").astype(int)])
    y = frame.harvestFreshMassG.to_numpy()
    groups = frame.group.to_numpy()
    outer = GroupKFold(n_splits=4)
    predicted = np.zeros(len(y)); baseline = np.zeros(len(y)); folds = []
    for fold, (train, test) in enumerate(outer.split(x, y, groups)):
        assert not set(groups[train]) & set(groups[test])
        inner = GroupKFold(n_splits=3)
        search = GridSearchCV(Pipeline([("scale", StandardScaler()), ("linear", Ridge())]), {"linear__alpha": [0.1, 1., 10., 100.]}, cv=inner, scoring="neg_mean_absolute_error")
        search.fit(x[train], y[train], groups=groups[train])
        predicted[test] = search.predict(x[test])
        baseline[test] = DummyRegressor(strategy="mean").fit(x[train], y[train]).predict(x[test])
        folds.append({"fold": fold, "trainGroups": sorted(set(groups[train])), "testGroups": sorted(set(groups[test])), "alpha": search.best_params_["linear__alpha"]})
    final = GridSearchCV(Pipeline([("scale", StandardScaler()), ("linear", Ridge())]), {"linear__alpha": [0.1, 1., 10., 100.]}, cv=outer, scoring="neg_mean_absolute_error")
    final.fit(x, y, groups=groups)
    model = final.best_estimator_
    residuals = np.abs(y - predicted)
    radius = float(np.quantile(residuals, .9, method="higher"))
    # A second, harder diagnostic holds out the entire flight or ground cohort.
    cohort_predictions = np.zeros(len(y))
    for cohort in ["flight", "ground"]:
        test = (frame.environment == cohort).to_numpy(); train = ~test
        diagnostic = Pipeline([("scale", StandardScaler()), ("linear", Ridge(alpha=10.))])
        diagnostic.fit(x[train], y[train]); cohort_predictions[test] = diagnostic.predict(x[test])
    card = {
        "id": "mizuna-harvest-v1", "name": "Mizuna harvest · exploratory ridge", "version": "1.0.0", "status": "trained-exploratory",
        "trainedAt": stamp(), "task": "Crop-specific fresh harvest mass regression", "sourceStudy": "OSD-655", "crop": "mizuna", "method": "NASA-data-trained exploratory regression", "samples": len(y), "groups": len(set(groups)),
        "features": names, "target": "harvestFreshMassG", "unit": "g fresh mass/pillow", "metrics": regression_metrics(y, predicted), "baselineMetrics": regression_metrics(y, baseline), "cohortHoldoutMetrics": regression_metrics(y, cohort_predictions),
        "validation": "Nested 4-fold GroupKFold, paired pillow numbers kept together; inner 3-fold alpha search. One experiment only; folds do not establish cross-study generalization.",
        "hyperparameters": final.best_params_, "seed": SEED,
        "domain": {name: {"min": float(x[:, i].min()), "max": float(x[:, i].max())} for i, name in enumerate(names)},
        "interval": {"radius": radius, "kind": "90th percentile absolute outer-CV residual, uncalibrated descriptive range", "nominalCoverage": None},
        "limitations": ["Only 14 measured harvest outcomes from VEG04A; not validated for another experiment or spacecraft.", "Crop is mizuna, not lettuce, tomato or radish. No cross-crop prediction.", "Full-period irrigation is a retrospective input; this is not an early harvest forecast or causal irrigation recommendation.", "Irrigation supplied is not physiological water demand or transpiration.", "Small-data regression may underperform its baseline; see measured metrics.", "No gravity-dose, radiation, temperature or humidity treatment effects can be learned from these tables."],
        "linear": portable_linear(model),
    }
    save_json(ARTIFACTS / "mizuna-harvest-v1.json", card)
    records = frame[["environment", "pillow", "group", "harvestFreshMassG"]].copy()
    records["prediction"] = predicted; records["baseline"] = baseline; records["cohortHoldoutPrediction"] = cohort_predictions
    records.to_csv(EVALUATION / "mizuna_out_of_fold.csv", index=False, lineterminator="\n")
    save_json(EVALUATION / "mizuna_splits.json", folds)
    fig, ax = plt.subplots(figsize=(5, 4)); ax.scatter(y, predicted, label="Outer grouped CV"); ax.plot([0, 90], [0, 90], "--", color="gray"); ax.set(xlabel="Measured mass (g/pillow)", ylabel="Predicted mass (g/pillow)", title="Mizuna: exploratory validation"); ax.legend(); fig.tight_layout(); fig.savefig(EVALUATION / "mizuna_validation.png", dpi=150); plt.close(fig)
    return card


def train_molecular():
    frame = pd.read_parquet(DATA / "processed" / "tomato_log_cpm.parquet")
    metadata = pd.read_csv(DATA / "processed" / "tomato_samples.csv").set_index("sample").loc[frame.index]
    # Remove genes that are universally zero (no sample-dependent information).
    frame = frame.loc[:, (frame != 0).any(axis=0)]
    x = frame.to_numpy(); y = (metadata.environment == "flight").to_numpy().astype(int); groups = metadata.group.to_numpy()
    def pipeline(c=1.):
        return Pipeline([("variance", VarianceThreshold()), ("select", SelectKBest(f_classif, k=64)), ("scale", StandardScaler()), ("linear", LogisticRegression(C=c, random_state=SEED, max_iter=2000))])
    outer = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=SEED)
    probabilities = np.zeros(len(y)); baseline = np.zeros(len(y)); splits = []
    for fold, (train, test) in enumerate(outer.split(x, y, groups)):
        assert not set(groups[train]) & set(groups[test])
        inner = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=SEED)
        search = GridSearchCV(pipeline(), {"linear__C": [.01, .1, 1.]}, cv=inner, scoring="f1_macro")
        search.fit(x[train], y[train], groups=groups[train])
        probabilities[test] = search.predict_proba(x[test])[:, 1]
        baseline[test] = DummyClassifier(strategy="prior").fit(x[train], y[train]).predict(x[test])
        splits.append({"fold": fold, "trainPlants": sorted(set(groups[train])), "testPlants": sorted(set(groups[test])), "C": search.best_params_["linear__C"]})
    predicted = (probabilities >= .5).astype(int)
    metrics = {"accuracy": float(accuracy_score(y, predicted)), "macroF1": float(f1_score(y, predicted, average="macro")), "precision": float(precision_score(y, predicted, zero_division=0)), "recall": float(recall_score(y, predicted, zero_division=0)), "ROC_AUC": float(roc_auc_score(y, probabilities)), "confusionMatrix": confusion_matrix(y, predicted).tolist(), "baselineMacroF1": float(f1_score(y, baseline, average="macro"))}
    final = GridSearchCV(pipeline(), {"linear__C": [.01, .1, 1.]}, cv=outer, scoring="f1_macro")
    final.fit(x, y, groups=groups); model = final.best_estimator_
    nonconstant = model.named_steps["variance"].get_support()
    selected = model.named_steps["select"].get_support(); genes = frame.columns[nonconstant][selected].tolist()
    card = {
        "id": "tomato-flight-response-v1", "name": "Tomato molecular flight context", "version": "1.0.0", "status": "trained-exploratory", "trainedAt": stamp(),
        "task": "Flight-versus-ground molecular context classification", "sourceStudy": "OSD-767", "crop": "tomato", "method": "NASA-data-trained exploratory molecular classification", "samples": len(y), "groups": len(set(groups)), "features": genes, "target": "recorded spaceflight experimental context", "unit": "probability of recorded flight class (uncalibrated)", "metrics": metrics,
        "validation": "Nested stratified group CV (4 outer, 3 inner folds); all tissues from each plant stay in one fold. Gene selection and scaling fit inside each training fold.",
        "normalization": "log1p(STAR raw count / full sample library count sum * 1e6). Full-library total required before selecting the 64 genes.",
        "hyperparameters": final.best_params_, "seed": SEED, "linear": portable_linear(model),
        "domain": {gene: {"min": float(frame[gene].min()), "max": float(frame[gene].max())} for gene in genes},
        "limitations": ["One VEG-05 experiment; cannot establish cross-study or causal gravity effects.", "Flight class is not disease, health, stress severity or biomass.", "Possible flight/ground batch confounding remains despite plant-grouped validation.", "Class probability is uncalibrated, not confidence or a medical/operational diagnostic.", "Requires laboratory RNA-seq, exact gene IDs and library normalization; environmental sliders are not compatible inputs."],
    }
    save_json(ARTIFACTS / "tomato-flight-response-v1.json", card)
    records = metadata.reset_index().copy(); records["observedFlight"] = y; records["outerCvProbabilityFlight"] = probabilities; records["outerCvClass"] = predicted
    records.to_csv(EVALUATION / "tomato_out_of_fold.csv", index=False, lineterminator="\n")
    save_json(EVALUATION / "tomato_splits.json", splits)
    # An explicit measured sample is provided for exercising schema/inference, not new validation.
    save_json(ARTIFACTS / "tomato_example.json", {"sample": str(frame.index[0]), "sourceStudy": "OSD-767", "isTrainingSample": True, "expression": {gene: float(frame.iloc[0][gene]) for gene in genes}})
    fig, ax = plt.subplots(figsize=(5, 4)); image = ax.imshow(metrics["confusionMatrix"], cmap="Blues"); ax.set(xticks=[0,1], yticks=[0,1], xticklabels=["Ground", "Flight"], yticklabels=["Ground", "Flight"], xlabel="Outer CV prediction", ylabel="Recorded condition", title="Tomato molecular context · grouped CV")
    for (i,j), value in np.ndenumerate(np.array(metrics["confusionMatrix"])): ax.text(j,i,str(value),ha="center",va="center")
    fig.colorbar(image,ax=ax); fig.tight_layout(); fig.savefig(EVALUATION / "tomato_confusion.png",dpi=150); plt.close(fig)
    return card


def main():
    validate(); ARTIFACTS.mkdir(exist_ok=True); EVALUATION.mkdir(exist_ok=True)
    cards = [train_harvest(), train_molecular()]
    checks = json.loads((DATA / "metadata" / "download_checksums.json").read_text())
    registry = {"schemaVersion": 1, "trainedAt": stamp(), "environment": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "sklearn": sklearn.__version__}, "dataVersion": hashlib.sha256(json.dumps(checks, sort_keys=True).encode()).hexdigest(), "models": [{"id": c["id"], "artifact": f"ml/artifacts/{c['id']}.json", "sha256": hashlib.sha256((ARTIFACTS / f"{c['id']}.json").read_bytes()).hexdigest()} for c in cards]}
    save_json(ARTIFACTS / "registry.json", registry)
    print(json.dumps([{k:c[k] for k in ['id','samples','metrics']} for c in cards],indent=2))


if __name__ == "__main__":
    main()
