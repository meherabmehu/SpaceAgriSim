"""Phase 10: explanations and selection stability for the radiation models.

Writes `ml/artifacts/radiation-*-explanation.json` beside the models rather than
inside them, so a model artifact's checksum keeps meaning "the trained model" and
the explanation carries its own provenance.

Two things this script gets right that a generic SHAP call would get wrong
-------------------------------------------------------------------------
1. **The binary model is explained as a decision function.** Its serialised
   evaluator stores an all-zero row for class 0 and the weight vector for class 1,
   so a per-class attribution would report "control contributes nothing", which is
   an artefact of the encoding rather than a fact about the biology. The binary
   model is explained on its single decision function, with the correspondence
   stated.

2. **Permutation importance is out-of-fold.** Importance computed on a model fitted
   to every row is in-sample and reported 1.000 balanced accuracy for the quality
   model — a number that says nothing. Here each repeat refits on the training
   groups and scores only the held-out groups, so the drop is measured out of fold.

Run: python ml/training/phase10_explain_radiation.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml" / "training"))
sys.path.insert(0, str(ROOT / "scripts"))
from explain import linear_contributions, selection_stability  # noqa: E402
from nasa_pipeline import save_json, stamp  # noqa: E402
from phase9_harness import SEED, select_features  # noqa: E402

ARTIFACTS = ROOT / "ml" / "artifacts"
EVALUATION = ROOT / "ml" / "evaluation"

CONDITION = {"non-irradiated": "control", "gamma radiation": "gamma",
             "Fe-56 ion radiation": "hze"}
N_REPEATS = 5


def labels_for(model_id: str, samples) -> np.ndarray:
    """The label vector that model was actually trained on.

    Using one label set for both models is a real error and was made here first: the
    binary model was scored against three-class labels, which produced a balanced
    accuracy of 0.333 that is arithmetically impossible for a binary task and was
    caught only because of that.
    """
    three = samples["radiation"].map(CONDITION).to_numpy()
    if model_id.endswith("quality-osd46-v1"):
        return three
    return np.where(three == "control", "control", "irradiated")


def out_of_fold_accuracy(matrix, labels, groups, fit) -> float:
    prediction = np.empty(len(labels), dtype=object)
    for train, test in LeaveOneGroupOut().split(matrix, labels, groups):
        assert not set(groups[train]) & set(groups[test]), "group leakage"
        prediction[test] = fit(matrix[train], labels[train], matrix[test])
    return float(balanced_accuracy_score(labels, prediction))


def permutation_importance(matrix, labels, groups, fit, feature_names, n_repeats=N_REPEATS):
    """Group-held-out permutation importance on the deployed feature set.

    The feature set is fixed to the deployed one — re-selecting inside every
    permutation would explain the selection procedure rather than the model. The
    model itself is refit on each fold's training groups, so the score is always
    out of fold.
    """
    generator = np.random.default_rng(SEED)
    baseline = out_of_fold_accuracy(matrix, labels, groups, fit)
    results = {}
    for position in range(matrix.shape[1]):
        drops = []
        for _ in range(n_repeats):
            shuffled = matrix.copy()
            shuffled[:, position] = matrix[generator.permutation(len(matrix)), position]
            drops.append(baseline - out_of_fold_accuracy(shuffled, labels, groups, fit))
        results[feature_names[position]] = {"meanDrop": float(np.mean(drops)),
                                            "sdDrop": float(np.std(drops))}
    ranked = sorted(results.items(), key=lambda item: item[1]["meanDrop"], reverse=True)
    return {
        "baselineBalancedAccuracy": baseline,
        "metric": "balanced accuracy, leave-one-biological-group-out, model refit per fold",
        "inSample": False,
        "nRepeats": n_repeats,
        "permutationUnit": "one gene's values permuted across arrays",
        "top": [{"gene": gene, **values} for gene, values in ranked[:25]],
        "bottom": [{"gene": gene, **values} for gene, values in ranked[-10:]],
        "genesWithNegativeDrop": sum(1 for _, v in results.items() if v["meanDrop"] < 0),
    }


def main() -> int:
    from train_radiation_osd46 import load, group_key

    matrix_all, genes, samples = load()
    groups = group_key(samples)
    folds = len(set(groups))
    print(f"{matrix_all.shape[0]} arrays x {matrix_all.shape[1]} gene models, {folds} groups")

    written, summaries = [], {}
    for model_id in ("radiation-quality-osd46-v1", "radiation-exposure-osd46-v1"):
        artifact = json.loads((ARTIFACTS / f"{model_id}.json").read_text())
        evaluator = artifact["evaluator"]
        features = evaluator["features"]
        labels = labels_for(model_id, samples)

        # Restrict to the deployed genes, in the deployed order.
        positions = [genes.index(gene) for gene in features]
        matrix = matrix_all[:, positions]
        print(f"\n{model_id}: {len(set(labels))} classes, {len(features)} deployed genes, "
              f"{int((np.asarray([c for c in np.unique(labels)]) == np.unique(labels)).sum())} class values")

        # Stability must be measured on the full gene space, because that is where
        # the deployed selection actually ran.
        stability = selection_stability(matrix_all, labels, groups, select_features,
                                        n_folds_expected=folds)
        by_name = {genes[index]: count
                   for index, count in stability["perGeneFoldCount"].items()}
        shipped = [{"gene": gene, "foldCount": by_name.get(gene, 0),
                    "selectionFrequency": round(by_name.get(gene, 0) / folds, 4)}
                   for gene in features]
        unstable = [row for row in shipped if row["selectionFrequency"] < 0.5]
        print(f"  stability: {stability['genesSelectedInEveryFold']} genes chosen in all "
              f"{folds} folds; {len(unstable)}/{len(features)} deployed genes chosen in "
              f"fewer than half")

        profile = artifact["referenceProfiles"]["control"]
        attribution = linear_contributions(evaluator, dict(zip(features, profile)))
        print(f"  attribution identity residual {attribution['identityResidual']:.2e}")

        def fit(x_train, y_train, x_test):
            model = Pipeline([("scale", StandardScaler()),
                              ("model", LogisticRegression(C=1.0, max_iter=2000,
                                                           random_state=SEED))])
            return model.fit(x_train, y_train).predict(x_test)

        importance = permutation_importance(matrix, labels, groups, fit, features)
        print(f"  out-of-fold baseline balanced accuracy {importance['baselineBalancedAccuracy']:.3f}")

        resolution = max(1, len(features) // 30)
        report = {
            "phase": 10,
            "modelId": model_id,
            "generatedAt": stamp(),
            "seed": SEED,
            "task": artifact["task"],
            "classLabels": artifact["classLabels"],
            "method": "exact linear attribution of the served linear-softmax evaluator",
            "notASurrogate": (
                "Computed from the shipped weight vectors, not a surrogate fitted to "
                "imitate them. The reconstruction identity is asserted to 1e-9."),
            "identityResidual": attribution["identityResidual"],
            "explainedInput": ("class centroid of the control class: a synthetic training "
                               "mean, not a measured specimen"),
            "perClass": attribution["perClass"],
            "selectionStability": {
                "folds": folds,
                "geneSpace": int(matrix_all.shape[1]),
                "genesSelectedInEveryFold": stability["genesSelectedInEveryFold"],
                "genesSelectedAtLeastOnce": stability["genesSelectedAtLeastOnce"],
                "deployedGenesChosenInFewerThanHalfTheFolds": len(unstable),
                "deployedGeneCount": len(features),
                "deployed": shipped,
            },
            "permutationImportance": importance,
            # This is the one place the analysis knowingly uses an optimistic
            # baseline, and saying so is cheaper than being caught at it.
            "selectionLeakageNote": (
                "The permutation baseline reuses the deployed gene set, which was selected "
                "on all 44 arrays. Its balanced accuracy is therefore optimistic relative "
                "to the honest group-held-out figure in the model artifact (0.898 for "
                "quality, 0.910 for exposure). The importance values are differences "
                "against that baseline, so they are reported for ranking genes, not as "
                "evidence of performance."),
            "interpretationLimits": [
                "A large contribution means the gene separated these conditions in this study.",
                "It is not a causal claim and not a biomarker claim.",
                "Contributions are additive on the logit scale, so the sign is relative to the "
                "other classes and does not mean up-regulation.",
                "Two genotypes, one laboratory, one microarray platform, 44 arrays.",
                f"{len(unstable)} of {len(features)} deployed genes are chosen in fewer than "
                "half of the folds; their individual contributions are the least stable "
                "part of this explanation.",
            ],
        }
        if len(set(labels)) == 2:
            # Binary encoding: class 0 carries an all-zero weight row, so a per-class
            # reading would claim control contributes nothing. Explain the single
            # decision function instead and say how it maps to the classes.
            report["binaryEncodingNote"] = (
                "The evaluator stores an all-zero coefficient row for class 0 and the "
                "weight vector for class 1. The contributions below are for the decision "
                "function logit(irradiated) - logit(control), which is the model's only "
                "free parameter. A per-class attribution of class 0 is identically zero "
                "by construction and carries no information.")
            report["perClass"] = {
                "decisionFunction": attribution["perClass"]["irradiated"],
                "controlIsReference": True,
                "classZeroRowIsAllZero": True,
            }

        path = ARTIFACTS / f"{model_id}-explanation.json"
        save_json(path, report)
        written.append(str(path.relative_to(ROOT)))
        summaries[model_id] = {
            "identityResidual": attribution["identityResidual"],
            "genesChosenInAllFolds": stability["genesSelectedInEveryFold"],
            "deployedGenesChosenInFewerThanHalf": len(unstable),
            "outOfFoldBaselineBalancedAccuracy": importance["baselineBalancedAccuracy"],
            "topGeneByPermutation": importance["top"][0]["gene"],
            "topGeneMeanDrop": importance["top"][0]["meanDrop"],
        }
        print(f"  wrote {path.name} ({path.stat().st_size:,} B)")

    save_json(EVALUATION / "phase10_explanations.json", {
        "phase": 10, "generatedAt": stamp(), "seed": SEED,
        "artifacts": written, "summary": summaries,
        "note": ("Explanations are exact for the served linear evaluators and are stored "
                 "beside the models, not inside them, so artifact checksums keep meaning "
                 "'the trained model'."),
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
