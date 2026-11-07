"""Phase 9 Model E: does a radiation classifier transfer between NASA studies?

The question
------------
A within-study cross-validation can be impressive and still be useless, because
the same laboratory, array scanner, growth chamber and reagent lot sit behind both
the training and the held-out samples. The strongest evidence available in this
corpus is to train on one study and test on a *different* study that measured the
same contrast with a different platform.

Setup
-----
  train  OSD-46   Affymetrix ATH1 microarray, 44 arrays, genotype Wild Type + atm-1 (ISA)
  test   OSD-782  Illumina bulk RNA-seq, 36 libraries, Col-0 background
  task   irradiated versus non-irradiated

Both studies are Arabidopsis thaliana and both annotate to TAIR gene models, so the
features can be harmonised by gene identity. Platform and ecotype differ, which is
exactly the point: any transfer is evidence of a shared biological signal rather
than a shared instrument.

Harmonisation
-------------
Per-gene z-scoring **within each study** before training. This uses no labels, so it
cannot leak the test labels, and it puts two different measurement scales on a
comparable footing. It does NOT remove study-level batch structure, which is the
main reason a failure here is informative rather than merely disappointing.

Why the balanced accuracy is the number that counts
---------------------------------------------------
The two studies have very different class proportions (8/36 control/irradiated in
OSD-46, 12/24 in OSD-782). A classifier that predicts "irradiated" for everything
scores 0.667 accuracy on OSD-782 while being completely useless. Only balanced
accuracy, and per-class recall, expose that. Both are reported.

Run: python ml/training/train_cross_study_transfer.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "ml" / "training"))
from nasa_pipeline import save_json, stamp  # noqa: E402
import phase9_harness as H  # noqa: E402

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
EVAL = ROOT / "ml" / "evaluation"


def load_osd46() -> pd.DataFrame:
    """Genes x samples, log2 normalised microarray, TAIR-indexed."""
    frame = pd.read_csv(RAW / "OSD-46" / "GLDS-46_array_normalized_expression_probeset_GLmicroarray.csv")
    columns = [c for c in frame.columns if c.startswith("GSM")]
    frame = frame.set_index("ProbesetID")
    names = frame["TAIR"].fillna(frame.index.to_series()).astype(str)
    matrix = frame[columns].astype(float)
    matrix.index = pd.Index(names, name="gene")
    return matrix.groupby(level=0).mean()


def load_osd782() -> pd.DataFrame:
    """Genes x samples, GeneLab VST counts, already TAIR-indexed."""
    return pd.read_csv(RAW / "OSD-782" / "GLDS-679_rna_seq_VST_Counts_GLbulkRNAseq.csv", index_col=0)


def zscore_by_gene(matrix: pd.DataFrame) -> pd.DataFrame:
    """Per-gene z-score within a study. Unsupervised, so it cannot leak labels."""
    std = matrix.std(axis=1).replace(0, np.nan)
    return matrix.sub(matrix.mean(axis=1), axis=0).divide(std, axis=0).fillna(0.0)


def anova(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    return H._anova_f(x, y)


def main() -> None:
    a46, b78 = load_osd46(), load_osd782()
    common = sorted(set(a46.index) & set(b78.index))
    if len(common) < 5000:
        raise SystemExit(f"Too few shared gene models: {len(common)}")
    print(f"shared TAIR gene models: {len(common)}")

    ann46 = pd.read_csv(PROCESSED / "osd46_radiation_samples.csv", dtype=str).set_index("sample")
    ann78 = pd.read_csv(PROCESSED / "osd782_radiation_samples.csv", dtype=str).set_index("sample")
    ann46 = ann46.loc[a46.columns]
    ann78 = ann78.loc[b78.columns]

    y46 = np.array(["control" if r == "non-irradiated" else "irradiated" for r in ann46["radiation"]])
    y78 = np.array(["control" if d == "0" else "irradiated" for d in ann78["absorbedDoseGy"]])
    print("OSD-46 labels:", dict(zip(*[a.tolist() for a in np.unique(y46, return_counts=True)])))
    print("OSD-782 labels:", dict(zip(*[a.tolist() for a in np.unique(y78, return_counts=True)])))

    x_train = zscore_by_gene(a46.loc[common]).to_numpy().T
    x_test = zscore_by_gene(b78.loc[common]).to_numpy().T

    # Feature selection is ANOVA-only here, with the variance-preselection stage
    # disabled: after per-gene z-scoring every variance is exactly 1, so variance
    # preselection would select arbitrary genes and manufacture a false negative.
    # (The harness now raises rather than allowing this silently.)

    # Reference point: the same pipeline scored within OSD-46 under its own
    # group-held-out scheme, so a transfer failure can be compared against what the
    # pipeline can do when the study is shared.
    groups46 = (
        ann46["genotype"].fillna("NA").astype(str) + "|"
        + ann46["radiation"].fillna("NA").astype(str) + "|"
        + ann46["ageDays"].fillna("NA").astype(str) + "|"
        + ann46["hoursAfterIrradiation"].fillna("no-timepoint").astype(str)
    ).to_numpy()
    def within_fold(x_tr, y_tr):
        f = np.nan_to_num(anova(x_tr, y_tr), nan=-np.inf)
        return np.argsort(f)[::-1][:150]

    # Reimplemented locally so the ANOVA-only selection can be used inside the
    # harness's fold loop.
    x_lo, y_lo, g_lo = x_train, y46, groups46
    prediction = np.empty(len(y_lo), dtype=object)
    from sklearn.model_selection import LeaveOneGroupOut
    for tr, te in LeaveOneGroupOut().split(x_lo, y_lo, g_lo):
        selected = within_fold(x_lo[tr], y_lo[tr])
        model = Pipeline([("s", StandardScaler()),
                          ("m", LogisticRegression(max_iter=5000, C=1.0))])
        model.fit(x_lo[np.ix_(tr, selected)], y_lo[tr])
        prediction[te] = model.predict(x_lo[np.ix_(te, selected)])
    within = {
        "accuracy": float(accuracy_score(y_lo, prediction)),
        "balancedAccuracy": float(balanced_accuracy_score(y_lo, prediction)),
    }
    print(f"within-OSD-46 reference: acc {within['accuracy']:.3f} "
          f"bal {within['balancedAccuracy']:.3f}")

    # A full grid is reported rather than a single setting: if the transfer fails
    # identically at every regularisation strength and every gene count, that is
    # strong evidence it is a property of the data, not of one hyperparameter.
    results = []
    for C in (0.01, 0.1, 1.0, 10.0):
        for k in (50, 150, 500, 2000):
            selected = np.argsort(np.nan_to_num(anova(x_train, y46), nan=-np.inf))[::-1][:k]
            model = Pipeline([("s", StandardScaler()),
                              ("m", LogisticRegression(max_iter=5000, C=C))])
            model.fit(x_train[:, selected], y46)
            prediction = model.predict(x_test[:, selected])
            accuracy = float(accuracy_score(y78, prediction))
            balanced = float(balanced_accuracy_score(y78, prediction))
            recall = {str(label): float((prediction[y78 == label] == label).mean())
                      for label in np.unique(y78)}
            results.append({
                "C": C,
                "genesUsed": int(k),
                "accuracy": accuracy,
                "balancedAccuracy": balanced,
                "perClassRecall": recall,
                "confusionMatrix": confusion_matrix(y78, prediction,
                                                    labels=["control", "irradiated"]).tolist(),
                "classLabels": ["control", "irradiated"],
            })
            print(f"  C={C:<5} k={k:<5} acc {accuracy:.3f}  balanced {balanced:.3f}  "
                  f"recall(control) {recall['control']:.2f}")

    best = max(results, key=lambda r: r["balancedAccuracy"])
    # The decisive diagnostic: predicting one class for every sample gives exactly
    # this accuracy, and a balanced accuracy of 0.5 is the signature of collapse.
    majority_rate = max(np.mean(y78 == "control"), np.mean(y78 == "irradiated"))
    collapsed = abs(best["balancedAccuracy"] - 0.5) < 1e-9

    verdict = (
        "transfer-failed-collapsed-to-majority"
        if collapsed else
        "transfer-failed" if best["balancedAccuracy"] <= 0.6 else
        "partial-transfer" if best["balancedAccuracy"] < 0.75 else
        "transfer-supported"
    )
    print(f"\nverdict: {verdict}")
    if collapsed:
        print(f"  interpretation: pooled accuracy {best['accuracy']:.3f} equals the "
              f"majority-class rate {majority_rate:.3f}; balanced accuracy is exactly "
              f"0.500, so the model predicted a single class for every library. The "
              f"apparently respectable accuracy is meaningless.")

    save_json(EVAL / "phase9_cross_study_transfer.json", {
        "phase": 9,
        "task": "irradiated versus non-irradiated",
        "generatedAt": stamp(),
        "trainStudy": "OSD-46 (Affymetrix ATH1 microarray, Wild Type + atm-1)",
        "testStudy": "OSD-782 (Illumina RNA-seq, Col-0, GeneLab VST)",
        "sharedGeneModels": len(common),
        "harmonisation": "per-gene z-score within each study (unsupervised, no label use)",
        "majorityClassRateInTest": float(majority_rate),
        "withinStudyReference": {
            "accuracy": within["accuracy"],
            "balancedAccuracy": within["balancedAccuracy"],
            "scheme": "leave-one-biological-group-out within OSD-46",
        },
        "results": results,
        "bestByBalancedAccuracy": best,
        "allSettingsIdentical": len({round(r["balancedAccuracy"], 6) for r in results}) == 1,
        "settingsTested": len(results),
        "verdict": verdict,
        "conclusion": (
            "A radiation-exposure classifier trained on OSD-46 does not transfer to "
            "OSD-782. Pooled accuracy is misleading here; balanced accuracy and "
            "per-class recall show the model collapses to a single class."
            if collapsed else
            f"Cross-study transfer verdict: {verdict}."),
        "interpretation": (
            "Two studies measuring nominally the same contrast (irradiated vs control "
            "Arabidopsis) do not yield a shared transferable signature under this "
            "harmonisation. Candidate explanations, none of which this data can "
            "separate: different platforms (3'-biased array vs RNA-seq), different "
            "ecotypes (Ws vs Col-0), different radiation qualities and dose levels "
            "(100 Gy gamma + 30 Gy Fe-56 vs 10/100 Gy Cs-137), different tissues and "
            "harvest timings, and study-level batch structure that per-gene "
            "standardisation does not remove. This is reported as a negative result, "
            "not adjusted until it becomes positive."),
        "deepLearningUsed": False,
    })
    print("\nwrote ml/evaluation/phase9_cross_study_transfer.json")


if __name__ == "__main__":
    main()
