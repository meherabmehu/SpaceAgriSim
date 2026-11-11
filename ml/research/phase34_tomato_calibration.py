"""Phase 34: are the tomato classifier's class probabilities usable as probabilities?

The Phase 32 audit closed the same question for the two OSD-46 radiation classifiers and left the
tomato one open:

    tomato-flight-response-v1   calibration   probabilities documented as uncalibrated

"Documented as uncalibrated" is honest but unmeasured. This script measures it, using only the
out-of-fold probabilities the shipped model produced, so the numbers describe the model that
actually serves `/api/models/tomato-flight-response-v1/predict`.

What is measured, and from which observations
---------------------------------------------
`ml/evaluation/tomato_out_of_fold.csv` holds one row per sample with the probability produced by
the outer fold that did not contain that sample's plant. The script

1. recomputes the hard-label accuracy from those probabilities and **stops** unless it equals the
   committed artifact (0.916666…). A calibration study for a different model than the one that
   ships is worthless;
2. scores the probabilities: log loss, Brier, and top-label ECE in 10 bins;
3. resamples **whole plants** (the biological group), not rows, for every interval — the two
   tissues taken from one plant are not independent evidence;
4. reports the reliability table so the number can be inspected rather than trusted.

What this script refuses to do
------------------------------
It fits nothing. A temperature (or any other monotone rescaling) would have to be chosen in a
nested scheme — for each held-out plant, fitted on predictions from models that also never saw that
plant — and that requires refitting every fold from the raw expression matrix, which is not vendored
in this repository. Fitting a temperature on the very rows that are then scored would produce an
in-sample number presented as a calibration, so no scaling is fitted, and the served surface
continues to apply none.

Output: ml/evaluation/phase34_probability_calibration.json
Run:    python ml/research/phase34_tomato_calibration.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, log_loss

ROOT = Path(__file__).resolve().parents[2]
OUT_OF_FOLD = ROOT / "ml" / "evaluation" / "tomato_out_of_fold.csv"
ARTIFACT = ROOT / "ml" / "artifacts" / "tomato-flight-response-v1.json"
TARGET = ROOT / "ml" / "evaluation" / "phase34_probability_calibration.json"

MODEL_ID = "tomato-flight-response-v1"
SEED = 20261107
BOOTSTRAP = 2000
ECE_BINS = 10


def brier_binary(probability: np.ndarray, labels: np.ndarray) -> float:
    return float(((probability - labels) ** 2).mean())


def expected_calibration_error(probability: np.ndarray, labels: np.ndarray,
                               bins: int = ECE_BINS) -> dict:
    """Top-label ECE for a binary classifier with equal-width confidence bins.

    For a binary task the top label is "flight" when p >= 0.5 and "ground" otherwise, so the
    confidence is max(p, 1-p) and the outcome is whether that call was right. The bin count is
    carried in the output because an ECE quoted without its bins cannot be compared to anything.
    """
    confidence = np.maximum(probability, 1.0 - probability)
    predicted = (probability >= 0.5).astype(int)
    correct = (predicted == labels).astype(float)
    edges = np.linspace(0.5, 1.0, bins + 1)
    rows, total = [], 0.0
    for low, high in zip(edges[:-1], edges[1:]):
        member = (confidence > low) & (confidence <= high) if low > 0.5 else (confidence >= low) & (confidence <= high)
        if not member.any():
            rows.append({"low": round(float(low), 4), "high": round(float(high), 4), "count": 0})
            continue
        gap = abs(float(correct[member].mean()) - float(confidence[member].mean()))
        rows.append({
            "low": round(float(low), 4), "high": round(float(high), 4),
            "count": int(member.sum()),
            "meanConfidence": round(float(confidence[member].mean()), 4),
            "accuracy": round(float(correct[member].mean()), 4),
            "gap": round(gap, 4),
        })
        total += member.sum() / len(labels) * gap
    return {"bins": bins, "ece": round(float(total), 4), "reliability": rows}


def group_bootstrap(metric, groups: np.ndarray, n: int = BOOTSTRAP, seed: int = SEED) -> dict:
    """Percentile interval resampling whole plants, because tissues share a plant."""
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
    return {
        "lower": round(float(np.percentile(values, 2.5)), 4),
        "upper": round(float(np.percentile(values, 97.5)), 4),
        "resamples": len(values),
        "unit": "biological group (plant)",
    }


def main() -> int:
    if not OUT_OF_FOLD.is_file():
        raise SystemExit(f"missing {OUT_OF_FOLD.relative_to(ROOT)}; it is produced by "
                         "ml/training/train_models.py and committed with the artifact")
    frame = pd.read_csv(OUT_OF_FOLD)
    probability = frame["outerCvProbabilityFlight"].to_numpy(dtype=float)
    labels = frame["observedFlight"].to_numpy(dtype=int)
    groups = frame["group"].astype(str).to_numpy()

    if not ((probability >= 0) & (probability <= 1)).all():
        raise SystemExit("out-of-fold probabilities are outside [0, 1]")

    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    published = float(artifact["metrics"]["accuracy"])
    recomputed = float(accuracy_score(labels, (probability >= 0.5).astype(int)))
    if abs(recomputed - published) > 1e-9:
        raise SystemExit(
            f"out-of-fold accuracy {recomputed:.6f} does not match the committed artifact "
            f"{published:.6f}; the calibration below would describe a different model than the "
            "one that ships")

    full = np.arange(len(labels))
    ece = expected_calibration_error(probability, labels)
    log_loss_value = float(log_loss(labels, probability, labels=[0, 1]))
    brier_value = brier_binary(probability, labels)

    # How often does the model state a high confidence and get it wrong? This is the quantity a
    # reader actually cares about, and it is invisible in an accuracy.
    high = probability >= 0.9
    wrong = (probability >= 0.5).astype(int) != labels
    high_confidence_wrong = int((high & wrong).sum())
    high_confidence_total = int(high.sum())

    record = {
        "schema": "spaceagrisim.probability_calibration/1",
        "phase": 34,
        "generatedBy": "ml/research/phase34_tomato_calibration.py",
        "source": {
            "model": MODEL_ID,
            "outOfFoldFile": str(OUT_OF_FOLD.relative_to(ROOT)),
            "artifact": str(ARTIFACT.relative_to(ROOT)),
            "study": "NASA OSDR OSD-767 (VEG-05 tomato transcriptome, flight versus ground)",
            "licence": artifact.get("license"),
            "licenceUrl": artifact.get("sourceLicenseUrl"),
        },
        "independenceUnit": "biological group (plant): the two tissues sampled from one plant stay "
                            "in one fold",
        "rule": ("Every scored probability is out of fold under the committed 4-fold "
                 "stratified-group split. The hard-label accuracy is recomputed from those same "
                 "probabilities and asserted equal to the artifact. No rescaling is fitted, "
                 "because a nested fit would require refitting folds whose input expression "
                 "matrix is not vendored in this repository; fitting on the scored rows "
                 "themselves would be an in-sample number and is not reported."),
        "models": {
            MODEL_ID: {
                "classes": ["ground", "flight"],
                "samples": int(len(labels)),
                "groups": int(len(np.unique(groups))),
                "positiveRate": round(float(labels.mean()), 4),
                "hardLabelAccuracy": round(recomputed, 4),
                "accuracyMatchesArtifact": True,
                "probability": {
                    "logLoss": round(log_loss_value, 4),
                    "logLossInterval": group_bootstrap(
                        lambda idx: log_loss(labels[idx], probability[idx], labels=[0, 1]), groups),
                    "brier": round(brier_value, 4),
                    "brierInterval": group_bootstrap(
                        lambda idx: brier_binary(probability[idx], labels[idx]), groups),
                    "ece": ece["ece"],
                    "eceInterval": group_bootstrap(
                        lambda idx: expected_calibration_error(probability[idx],
                                                              labels[idx])["ece"], groups),
                    "eceBins": ece["bins"],
                    "reliability": ece["reliability"],
                    "meanMaxProbability": round(float(np.maximum(probability, 1 - probability).mean()), 4),
                    "confidenceBands": {
                        ">=0.9": {
                            "count": high_confidence_total,
                            "wrong": high_confidence_wrong,
                        },
                    },
                },
                "temperatureScaling": {
                    "fitted": False,
                    "reason": ("Not fitted. A temperature that is chosen on the same out-of-fold "
                               "predictions it then scores is an in-sample number, and a nested "
                               "fit cannot be reproduced because the expression matrix behind the "
                               "committed folds is not vendored."),
                },
                "servedScaling": "none",
            },
        },
    }

    # The interpretation is derived from the measured numbers rather than written by hand, so it
    # cannot drift away from them.
    model = record["models"][MODEL_ID]
    band = model["probability"]["confidenceBands"][">=0.9"]
    base_rate = model["positiveRate"]
    record["models"][MODEL_ID]["interpretation"] = (
        f"Out of fold, {model['samples']} samples from {model['groups']} plants: log loss "
        f"{model['probability']['logLoss']} (95 % plant-resampled interval "
        f"{model['probability']['logLossInterval']['lower']}-"
        f"{model['probability']['logLossInterval']['upper']}), Brier "
        f"{model['probability']['brier']}, top-label ECE {model['probability']['ece']} over "
        f"{model['probability']['eceBins']} bins. "
        + (f"{band['wrong']} of {band['count']} predictions at or above 0.9 were wrong. "
           if band["count"] else "")
        + f"The ground/flight base rate is {base_rate}. Treat the score as a ranking of "
        "recorded flight context, not as the probability the class is correct, and not as a "
        "statement about plant health, stress or yield."
    )

    TARGET.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"{MODEL_ID}: {model['samples']} samples / {model['groups']} plants")
    print(f"  accuracy reproduced {recomputed:.4f} (artifact {published:.4f})")
    print(f"  log loss {model['probability']['logLoss']} "
          f"[{model['probability']['logLossInterval']['lower']}, "
          f"{model['probability']['logLossInterval']['upper']}]  "
          f"Brier {model['probability']['brier']}  ECE {model['probability']['ece']}")
    print(f"  wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
