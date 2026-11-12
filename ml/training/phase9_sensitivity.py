"""Phase 9 sensitivity analysis: how much does the OSD-46 result depend on the
number of selected genes, and on which selection rule is used?

Written because an earlier OSD-46 artifact reported balanced accuracy 0.870 while
the current one reports 0.898 on the same data, and a reader deserves an
explained difference rather than a silent revision. The candidates were:

  1. a different number of selected genes k;
  2. a different feature-selection rule (global variance preselection taken once
     on the pooled matrix, versus in-fold ANOVA);
  3. a genuine change from a bug fix.

This script measures (1) and (2) so the answer is evidence rather than a guess.

Run: python ml/training/phase9_sensitivity.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "ml" / "training"))
from nasa_pipeline import save_json  # noqa: E402
import phase9_harness as H  # noqa: E402
from train_radiation_osd46 import group_key, load_matrix  # noqa: E402

EVAL = ROOT / "ml" / "evaluation"
KS = (25, 50, 100, 150, 300, 500)


def prepare():
    matrix, annotation, _batch = load_matrix()
    x = matrix.to_numpy(dtype=float).T          # samples x genes
    genes = list(matrix.index)
    groups = group_key(annotation)
    quality = annotation["radiation"].map(
        {"non-irradiated": "control", "gamma radiation": "gamma",
         "Fe-56 ion radiation": "hze"}).to_numpy()
    exposure = np.where(quality == "control", "control", "irradiated")
    return x, genes, groups, {"quality": quality, "exposure": exposure}


def main() -> int:
    x, genes, groups, tasks = prepare()
    print(f"{x.shape[0]} arrays, {x.shape[1]} genes, {len(set(groups))} groups")

    deployed = {"quality": [], "exposure": []}
    global_variance = []

    for task, y in tasks.items():
        for k in KS:
            H.TOP_ANOVA_GENES = k   # in-fold rule: the deployed one
            report = H.grouped_cv_score(
                x, y, groups,
                H.classification_learners()["logistic_l2"],
                column_names=genes)
            deployed[task].append({
                "k": k,
                "accuracy": report["accuracy"],
                "balancedAccuracy": report["balancedAccuracy"],
                "macroF1": report["macroF1"],
                "confusionMatrix": report["confusionMatrix"],
            })
            print(f"  {task:9s} k={k:4d} in-fold ANOVA  "
                  f"acc {report['accuracy']:.3f}  bal {report['balancedAccuracy']:.3f}")

    # Diagnostic only: choose the k highest-variance genes ONCE on the pooled
    # matrix, then cross-validate. Held-out arrays influence gene choice, so this
    # is not a number that may be reported as a model result. It is measured here
    # solely to show whether the historical discrepancy is explained by the rule.
    print("\nFor comparison only - global variance preselection (never deployed):")
    for task, y in tasks.items():
        for k in KS:
            top = np.argsort(x.var(axis=0))[::-1][:k]
            report = H.grouped_cv_score(
                x[:, top], y, groups,
                H.classification_learners()["logistic_l2"],
                column_names=[genes[i] for i in top])
            global_variance.append({
                "task": task, "k": k,
                "accuracy": report["accuracy"],
                "balancedAccuracy": report["balancedAccuracy"],
            })
            print(f"  {task:9s} k={k:4d} global var     "
                  f"acc {report['accuracy']:.3f}  bal {report['balancedAccuracy']:.3f}")

    payload = {
        "study": "OSD-46",
        "purpose": ("Explain the difference between the earlier OSD-46 artifact "
                    "(balanced accuracy 0.870) and the current one (0.898) as a "
                    "measured function of the number of selected genes and of the "
                    "selection rule."),
        "deployedRule": "in-fold ANOVA selection inside each leave-one-group-out fold",
        "deployedK": 150,
        "geneCountSweep": deployed,
        "globalVarianceComparison": {
            "warning": ("Diagnostic only. Selecting genes once on the pooled matrix "
                        "lets held-out arrays influence the feature set, so these "
                        "values must not be quoted as model performance."),
            "results": global_variance,
        },
        "verdict": (
            "Reported in PHASE9_ML_EVALUATION.md from these numbers: the current "
            "artifact's balanced accuracy is the in-fold ANOVA value at k=150, and "
            "the deployed k is recorded in the artifact as genesSelected."
        ),
    }
    EVAL.mkdir(parents=True, exist_ok=True)
    save_json(EVAL / "phase9_osd46_sensitivity", payload)
    print("\nwrote ml/evaluation/phase9_osd46_sensitivity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
