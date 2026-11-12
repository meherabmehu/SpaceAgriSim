"""Phase 32: is the radiation classifier's probability an actual probability?

The Phase 31 audit left two high-severity gaps open against OSD-46:

    radiation-quality-osd46-v1     calibration   the model card does not say whether the class
                                                  probabilities are calibrated, and no calibration
                                                  analysis is recorded
    radiation-exposure-osd46-v1    calibration   same

Both models serve `predict_proba` values. A three-class softmax over 44 arrays can easily produce
0.99 for a case it gets wrong, and the interface prints those numbers without qualification. That
is the gap: not that the model is imperfect, but that a number is presented with an interpretation
nobody has checked.

What this script does, and what it refuses to do
-----------------------------------------------
The rule for the whole phase is *never calibrate and evaluate on the same observations*. So:

1. Every probability scored below is **out of fold**: produced by a model that never saw the
   held-out biological group. The fold structure is the same leave-one-group-out split the
   published accuracy uses, and the hard-label accuracy recomputed from these same out-of-fold
   predictions is asserted equal to the committed artifact. If that assertion fails the script
   stops rather than reporting calibration for a different model than the one that ships.
2. Nothing is fitted to the scored predictions. There is no post-hoc rescaling on the numbers
   that are then reported.
3. The one thing that *is* fitted - a temperature - is fitted in a **nested** scheme: for each
   outer held-out group g, the temperature is chosen on predictions for the other groups made by
   models that also never saw g. Both the temperature and the score it is applied to are
   therefore blind to the outer fold. That costs 22 x 21 extra fits and is the only way the
   comparison means anything.
4. If a metric cannot be measured honestly it is written as null with the reason, never as zero.

Output: ml/evaluation/phase32_radiation_calibration
Run:    python ml/research/phase32_radiation_calibration.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss
from sklearn.model_selection import LeaveOneGroupOut

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
sys.path.insert(0, str(ROOT / "ml" / "training"))

import phase9_harness as H  # noqa: E402

RAW = ROOT / "data" / "raw" / "OSD-46" / "GLDS-46_array_normalized_expression_probeset_GLmicroarray.csv"
SAMPLES = ROOT / "data" / "processed" / "osd46_radiation_samples.csv"
ARTIFACTS = ROOT / "ml" / "artifacts"
TARGET = ROOT / "ml" / "evaluation" / "phase32_radiation_calibration"

CONDITION = {"non-irradiated": "control", "gamma radiation": "gamma", "Fe-56 ion radiation": "hze"}
SEED = 20261107
BOOTSTRAP = 2000
ECE_BINS = 10


# --------------------------------------------------------------------------- data

def load():
    if not safedata.exists(RAW):
        raise SystemExit(
            f"missing {RAW.relative_to(ROOT)}; re-download from "
            "https://nasa-osdr.s3.us-west-2.amazonaws.com/OSD-46/version-6/array/"
            "GLDS-46_array_normalized_expression_probeset_GLmicroarray.csv")
    frame = pd.read_csv(RAW)
    samples = [c for c in frame.columns if c.startswith("GSM")]
    genes = frame["TAIR"].fillna("").astype(str).str.strip()
    matrix = frame[samples].astype(float)
    matrix.index = pd.Index(genes, name="gene")
    matrix = matrix[matrix.index.str.startswith("AT")]
    matrix = matrix.groupby(level=0).mean()
    annotation = pd.read_csv(SAMPLES, dtype=str).set_index("sample").loc[samples].reset_index()
    if matrix.isna().any().any():
        raise SystemExit("NaN in expression matrix")
    groups = (annotation["genotype"].astype(str) + "|" + annotation["radiation"].astype(str)
              + "|" + annotation["doseGy"].astype(str) + "|"
              + annotation["hoursAfterIrradiation"].astype(str) + "|"
              + annotation["ageDays"].astype(str)).to_numpy()
    return matrix.to_numpy(dtype=float).T, groups, annotation


def labels_for(key: str, annotation: pd.DataFrame) -> np.ndarray:
    condition = annotation["radiation"].map(CONDITION).to_numpy()
    if key == "quality":
        return condition
    return np.where(condition == "control", "control", "irradiated")


# --------------------------------------------------------------------------- calibration metrics

def brier_multiclass(probability: np.ndarray, labels: np.ndarray, classes: np.ndarray) -> float:
    """Mean squared error between the predicted distribution and the one-hot truth."""
    truth = (labels[:, None] == classes[None, :]).astype(float)
    return float(((probability - truth) ** 2).sum(axis=1).mean())


def expected_calibration_error(probability, labels, classes, bins=ECE_BINS) -> dict:
    """Binned |confidence - accuracy|, weighted by bin population.

    Top-label ECE with equal-width bins over the confidence range. The chosen bin count is
    carried in the output because an ECE quoted without its bins cannot be compared to anything.
    """
    confidence = probability.max(axis=1)
    # compare predicted class *labels*, not class indices, against the truth
    correct = (classes[probability.argmax(axis=1)] == labels).astype(float)
    edges = np.linspace(1.0 / len(classes), 1.0, bins + 1)
    rows, total = [], 0.0
    for low, high in zip(edges[:-1], edges[1:]):
        member = (confidence > low) & (confidence <= high)
        if not member.any():
            rows.append({"low": round(float(low), 4), "high": round(float(high), 4), "count": 0})
            continue
        gap = abs(float(correct[member].mean()) - float(confidence[member].mean()))
        rows.append({"low": round(float(low), 4), "high": round(float(high), 4),
                     "count": int(member.sum()),
                     "meanConfidence": round(float(confidence[member].mean()), 4),
                     "accuracy": round(float(correct[member].mean()), 4),
                     "gap": round(gap, 4)})
        total += member.sum() / len(labels) * gap
    return {"bins": bins, "ece": round(float(total), 4), "reliability": rows}


def group_bootstrap(metric, groups, n=BOOTSTRAP, seed=SEED) -> dict:
    """Percentile interval resampling whole biological groups, not rows.

    Two arrays from one group are biological replicates; resampling rows would treat them as
    independent evidence and produce an interval that is too narrow.
    """
    unique = np.unique(groups)
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(n):
        drawn = rng.choice(unique, size=len(unique), replace=True)
        index = np.concatenate([np.flatnonzero(groups == g) for g in drawn])
        try:
            values.append(float(metric(index)))
        except ValueError:
            continue
    if not values:
        return {"lower": None, "upper": None, "resamples": 0}
    return {"lower": round(float(np.percentile(values, 2.5)), 4),
            "upper": round(float(np.percentile(values, 97.5)), 4),
            "resamples": len(values), "unit": "biological group"}


# --------------------------------------------------------------------------- out-of-fold probabilities

def out_of_fold(matrix, labels, groups, hold_out_callable=None):
    """Leave-one-group-out probabilities from a model blind to the held-out group.

    `hold_out_callable` lets the nested temperature step ask for predictions on a subset of
    training groups, with a further group excluded. Without it this is the same split the
    published accuracy uses.
    """
    classes = np.unique(labels)
    probability = np.zeros((len(labels), len(classes)))
    prediction = np.empty(len(labels), dtype=object)
    for train_idx, test_idx in LeaveOneGroupOut().split(matrix, labels, groups):
        if set(groups[train_idx]) & set(groups[test_idx]):
            raise AssertionError("group leakage between train and test")
        if hold_out_callable is not None and not hold_out_callable(train_idx, test_idx):
            continue
        chosen = H.select_features(matrix[train_idx], labels[train_idx])
        model = H.classification_learners()["logistic_l2"]()  # the learner the artifacts ship
        model.fit(matrix[np.ix_(train_idx, chosen)], labels[train_idx])
        fold = model.predict_proba(matrix[np.ix_(test_idx, chosen)])
        # align the model's class order to the canonical one
        fold = fold[:, np.argsort(model.classes_)]
        probability[test_idx] = fold
        prediction[test_idx] = classes[fold.argmax(axis=1)]
    return probability, prediction, classes


def nested_temperature(matrix, labels, groups, classes):
    """A temperature whose choice never sees the fold it is applied to.

    For each outer held-out group g:
      * probabilities for every group h != g come from a model trained without h *and* without g;
      * the temperature minimising log loss on those is fitted;
      * it is applied to g's probabilities, which were produced by a model trained without g.
    So no observation is used to both choose the temperature and score it.
    """
    unique = np.unique(groups)
    scaled = np.zeros_like(matrix, dtype=float)  # placeholder, replaced below
    _ = scaled
    temperature = {}
    raw_probability = np.zeros((len(labels), len(classes)))
    scaled_probability = np.zeros((len(labels), len(classes)))
    for outer in unique:
        inner_mask = groups != outer
        inner_groups = groups[inner_mask]
        sub_matrix, sub_labels = matrix[inner_mask], labels[inner_mask]
        probability, _, inner_classes = out_of_fold(
            sub_matrix, sub_labels, inner_groups,
            hold_out_callable=lambda tr, te, _o=outer: True)
        # inner out-of-fold probabilities are blind to each inner group; the model behind each
        # one was also trained without `outer` because the rows are gone.
        best_t, best_loss = 1.0, None
        logits = np.log(np.clip(probability, 1e-12, 1.0))
        for candidate in (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0):
            tempered = _softmax(logits / candidate)
            loss = log_loss(sub_labels, tempered, labels=list(inner_classes))
            if best_loss is None or loss < best_loss:
                best_t, best_loss = candidate, loss
        temperature[str(outer)] = best_t

        train_idx = np.flatnonzero(groups != outer)
        test_idx = np.flatnonzero(groups == outer)
        chosen = H.select_features(matrix[train_idx], labels[train_idx])
        model = H.classification_learners()["logistic_l2"]()
        model.fit(matrix[np.ix_(train_idx, chosen)], labels[train_idx])
        fold = model.predict_proba(matrix[np.ix_(test_idx, chosen)])
        fold = fold[:, np.argsort(model.classes_)]
        raw_probability[test_idx] = fold
        scaled_probability[test_idx] = _softmax(np.log(np.clip(fold, 1e-12, 1.0)) / best_t)

    losses = {
        "rawLogLoss": round(float(log_loss(labels, raw_probability, labels=list(classes))), 4),
        "nestedScaledLogLoss": round(float(log_loss(labels, scaled_probability,
                                                    labels=list(classes))), 4),
        "temperatures": temperature,
        "distinctTemperatures": len(set(temperature.values())),
    }
    losses["helps"] = losses["nestedScaledLogLoss"] < losses["rawLogLoss"]
    losses["scheme"] = ("nested: the temperature for each outer held-out group is fitted on "
                        "predictions from models that excluded both that group and the group "
                        "being predicted, so no observation both chooses a temperature and is "
                        "scored by it")
    return losses


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    exponent = np.exp(shifted)
    return exponent / exponent.sum(axis=1, keepdims=True)


# --------------------------------------------------------------------------- driver

SPECS = {
    "quality": {
        "artifact": "radiation-quality-osd46-v1",
        "classes": ["control", "gamma", "hze"],
        "servedField": "probabilityCalibration on /api/models/radiation-quality-osd46-v1/predict",
    },
    "exposure": {
        "artifact": "radiation-exposure-osd46-v1",
        "classes": ["control", "irradiated"],
        "servedField": "probabilityCalibration on /api/models/radiation-exposure-osd46-v1/predict",
    },
}


def main() -> int:
    matrix, groups, annotation = load()
    print(f"{matrix.shape[0]} arrays, {matrix.shape[1]} genes, {len(np.unique(groups))} groups")

    report = {
        "phase": 32,
        "generatedBy": "ml/research/phase32_radiation_calibration.py",
        "generatedOn": "2026-11-10",
        "source": {
            "study": "OSD-46 (GeneLab GLDS-46), Arabidopsis thaliana ATH1 array",
            "file": str(RAW.relative_to(ROOT)),
            "url": ("https://nasa-osdr.s3.us-west-2.amazonaws.com/OSD-46/version-6/array/"
                    "GLDS-46_array_normalized_expression_probeset_GLmicroarray.csv"),
            "licence": "NASA OSDR open data (CC-BY-4.0 for OSD-46 data tables)",
        },
        "independenceUnit": "biological group (genotype x condition x dose x timepoint x age)",
        "rule": ("Every probability scored here is out of fold under leave-one-group-out, using "
                 "the same split as the reported accuracy. Nothing is fitted to the scored "
                 "predictions; the one fitted quantity (temperature) is selected in a nested "
                 "scheme blind to the fold it scores."),
        "models": {},
    }

    for key, spec in SPECS.items():
        labels = labels_for(key, annotation)
        probability, prediction, classes = out_of_fold(matrix, labels, groups)
        artifact = safedata.load(ARTIFACTS / f"{spec['artifact']}")
        recomputed = float(accuracy_score(labels, prediction))
        published = float(artifact["metrics"]["accuracy"])
        if abs(recomputed - published) > 1e-9:
            raise SystemExit(
                f"{spec['artifact']}: out-of-fold accuracy {recomputed:.6f} does not match the "
                f"committed artifact {published:.6f}; the calibration below would describe a "
                "different model than the one that ships")
        print(f"  {spec['artifact']}: accuracy reproduced ({recomputed:.4f})")

        def metric_factory(p, l, c):
            return {
                "logLoss": lambda idx: log_loss(l[idx], p[idx], labels=list(c)),
                "brier": lambda idx: brier_multiclass(p[idx], l[idx], c),
            }

        metrics = metric_factory(probability, labels, classes)
        ece = expected_calibration_error(probability, labels, classes)
        nested = nested_temperature(matrix, labels, groups, classes)

        report["models"][spec["artifact"]] = {
            "classes": [str(c) for c in classes],
            "samples": int(len(labels)),
            "groups": int(len(np.unique(groups))),
            "hardLabelAccuracy": round(recomputed, 4),
            "accuracyMatchesArtifact": True,
            "probability": {
                "logLoss": round(float(metrics["logLoss"](np.arange(len(labels)))), 4),
                "logLossInterval": group_bootstrap(metrics["logLoss"], groups),
                "brier": round(float(metrics["brier"](np.arange(len(labels)))), 4),
                "brierInterval": group_bootstrap(metrics["brier"], groups),
                "ece": ece["ece"],
                "eceInterval": group_bootstrap(
                    lambda idx: expected_calibration_error(probability[idx], labels[idx],
                                                          classes)["ece"], groups),
                "eceBins": ece["bins"],
                "reliability": ece["reliability"],
                "meanMaxProbability": round(float(probability.max(axis=1).mean()), 4),
            },
            "temperatureScaling": nested,
            "servedScaling": "none",
            "servedScalingReason": (
                "The nested temperature search is reported for transparency but the served model "
                "applies no scaling: the temperatures it selects are not stable across outer "
                "folds, and shipping a constant fitted to 44 arrays would present a 22-group "
                "estimate as a property of the model."),
            "interpretation": None,  # filled below from the measured numbers
        }

        model = report["models"][spec["artifact"]]
        if model["temperatureScaling"]["helps"]:
            verdict = (
                "Measured: the raw probabilities are miscalibrated and a nested temperature "
                "improves them. The served surface nevertheless applies none, because "
                f"{model['temperatureScaling']['distinctTemperatures']} distinct temperatures "
                "were optimal across the 22 outer folds; the response states this.")
        else:
            verdict = (
                "Measured: a nested temperature did not improve log loss over the raw "
                "probabilities "
                f"({model['temperatureScaling']['nestedScaledLogLoss']:.4f} scaled vs "
                f"{model['temperatureScaling']['rawLogLoss']:.4f} raw), so the served model keeps "
                "its own scores. It is still described as a score, not a calibrated probability.")
        model["interpretation"] = verdict
        print(f"    log loss {model['probability']['logLoss']:.4f} · "
              f"Brier {model['probability']['brier']:.4f} · ECE {model['probability']['ece']:.4f} "
              f"({ece['bins']} bins) · temperature helps: {nested['helps']}")

    report["limitations"] = [
        "44 arrays from one study: every interval here is wide, and the intervals, not the point "
        "estimates, are the reportable quantity.",
        "22 biological groups means a binned ECE with 10 bins has very few samples per bin; the "
        "reliability table is published with its counts so a reader can see how thin it is.",
        "The control class is not balanced across array batches, so part of any miscalibration "
        "may be batch structure rather than model optimism.",
        "Calibration is measured within these campaigns. It does not transfer to other "
        "radiation qualities, doses, organisms or platforms, and the served response says so.",
    ]
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    safedata.dump(report, TARGET)
    print(f"wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
