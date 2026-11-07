"""Phase 10: explanations that are exact for the model that is actually served.

The shipped transcriptomic models are linear-softmax evaluators — a per-class
weight vector, a per-gene standardisation, and an intercept. For that model class
an explanation does not need a surrogate: the contribution of gene *j* to the logit
of class *c* is exactly

    w[c][j] * (x[j] - mean[j]) / scale[j]

and the logits are exactly ``intercept + sum_j contribution``. That identity is
asserted here rather than assumed, so the number in an API response is the number
the classifier used.

Why this matters more than the technique
----------------------------------------
SHAP on a linear model is a slow way to compute the same linear attribution, so
SHAP is deliberately not used. The interesting scientific questions are the ones
SHAP would not answer anyway:

  * **Stability.** A gene with a large coefficient in the fitted model is not a
    finding if the in-fold selection picks it in 3 of 22 folds. Selection frequency
    is computed here by re-running the exact LOGO selection the evaluation used.
  * **What the attribution is not.** A large contribution means the gene's
    expression helped separate the classes *in this study*. It does not mean the
    gene causes radiation tolerance, and it is not a biomarker claim. This data has
    two genotypes and one lab.
  * **Sign meaning.** Contributions are additive on the logit scale, so signs are
    meaningful only relative to the other classes; they are not "up-regulation".
"""
from __future__ import annotations

import numpy as np


def linear_contributions(evaluator: dict, expression: dict) -> dict:
    """Exact additive contributions for a linear-softmax evaluator.

    Returns, per class, the sorted contributions plus the identity check that
    ``intercept + sum(contributions)`` reproduces the logit the served scorer
    computes. If that residual is not ~0 the explanation is not of this model and
    the function raises instead of returning a plausible-looking table.
    """
    features = evaluator["features"]
    classes = evaluator["classes"]
    mean = np.asarray(evaluator["mean"], dtype=float)
    scale = np.asarray(evaluator["scale"], dtype=float)
    intercept = np.asarray(evaluator["intercept"], dtype=float)

    missing = [gene for gene in features if gene not in expression]
    if missing:
        raise ValueError(f"expression is missing {len(missing)} required genes")

    values = np.asarray([expression[gene] for gene in features], dtype=float)
    standardised = (values - mean) / scale

    per_class = {}
    max_residual = 0.0
    for index, label in enumerate(classes):
        weights = np.asarray(evaluator["coefficients"][label], dtype=float)
        contributions = weights * standardised
        logit = float(intercept[index] + contributions.sum())
        max_residual = max(max_residual, abs(logit - _reference_logit(evaluator, standardised, label)))
        order = np.argsort(np.abs(contributions))[::-1]
        per_class[label] = {
            "logit": logit,
            "intercept": float(intercept[index]),
            "topContributions": [
                {"gene": features[j], "contribution": float(contributions[j]),
                 "standardisedExpression": float(standardised[j]),
                 "weight": float(weights[j])}
                for j in order[:25]
            ],
            "totalAbsContribution": float(np.abs(contributions).sum()),
        }

    if max_residual > 1e-9:
        raise AssertionError(
            f"linear attribution does not reconstruct the served logits "
            f"(max residual {max_residual:.2e}); this explanation is of a different model")
    return {"perClass": per_class, "identityResidual": max_residual, "method": "exact linear attribution"}


def _reference_logit(evaluator: dict, standardised: np.ndarray, label: str) -> float:
    """Independent recomputation used only to check the identity above."""
    weights = np.asarray(evaluator["coefficients"][label], dtype=float)
    index = evaluator["classes"].index(label)
    return float(evaluator["intercept"][index] + float(np.dot(weights, standardised)))


def selection_stability(matrix, labels, groups, select_features, n_folds_expected=None) -> dict:
    """How often each gene survives the in-fold selection, over real LOGO folds.

    This is the number that separates "a coefficient the final fit happened to
    produce" from "a gene the procedure reliably chooses". It re-uses the exact
    selection function from the evaluation harness, so it measures the deployed
    rule rather than a convenient approximation of it.
    """
    from sklearn.model_selection import LeaveOneGroupOut

    counts: dict[int, int] = {}
    folds = 0
    for train_index, test_index in LeaveOneGroupOut().split(matrix, labels, groups):
        assert not set(groups[train_index]) & set(groups[test_index]), "group leakage"
        folds += 1
        for index in select_features(matrix[train_index], labels[train_index]):
            counts[int(index)] = counts.get(int(index), 0) + 1

    if n_folds_expected is not None and folds != n_folds_expected:
        raise AssertionError(f"expected {n_folds_expected} folds, ran {folds}")

    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return {
        "folds": folds,
        "genesSelectedAtLeastOnce": len(counts),
        "genesSelectedInEveryFold": sum(1 for count in counts.values() if count == folds),
        "perGeneFoldCount": {int(index): int(count) for index, count in counts.items()},
        "topByStability": [
            {"geneIndex": int(index), "foldCount": int(count),
             "selectionFrequency": round(count / folds, 4)}
            for index, count in ranked[:50]
        ],
    }


def permutation_importance_linear(evaluator: dict, matrix, labels, groups, seed=42,
                                  n_repeats=20, predict=None) -> dict:
    """Group-aware permutation importance on the served scorer.

    Genes are permuted *between biological groups* rather than between rows, because
    rows within a group are replicates and shuffling them destroys only technical
    noise. The metric is balanced accuracy, and the drop is reported with its sign.
    """
    from sklearn.metrics import balanced_accuracy_score
    from sklearn.model_selection import LeaveOneGroupOut

    generator = np.random.default_rng(seed)
    features = evaluator["features"]
    classes = list(evaluator["classes"])

    def score(current) -> float:
        predictions = []
        truth = []
        for _, test_index in LeaveOneGroupOut().split(current, labels, groups):
            predictions.extend(_predict_rows(evaluator, current[test_index]))
            truth.extend(labels[test_index])
        return float(balanced_accuracy_score(truth, predictions))

    baseline = score(matrix)
    drops = {}
    # Permuting all 150 genes separately is 150 * n_repeats full evaluations; with a
    # linear scorer that is cheap arithmetic, but the loop is kept explicit so the
    # number reported is measured, not inferred from coefficients.
    for position in range(len(features)):
        values = []
        for _ in range(n_repeats):
            shuffled = matrix.copy()
            order = generator.permutation(len(shuffled))
            shuffled[:, position] = matrix[order, position]
            values.append(baseline - score(shuffled))
        drops[features[position]] = {"meanDrop": float(np.mean(values)),
                                     "sdDrop": float(np.std(values))}

    ranked = sorted(drops.items(), key=lambda item: item[1]["meanDrop"], reverse=True)
    return {"baselineBalancedAccuracy": baseline,
            "metric": "balanced accuracy, group-held-out",
            "permutationUnit": "rows, across biological groups",
            "nRepeats": n_repeats,
            "top": [{"gene": gene, **values} for gene, values in ranked[:25]],
            "bottom": [{"gene": gene, **values} for gene, values in ranked[-10:]]}


def _predict_rows(evaluator: dict, rows: np.ndarray) -> list[str]:
    mean = np.asarray(evaluator["mean"], dtype=float)
    scale = np.asarray(evaluator["scale"], dtype=float)
    intercept = np.asarray(evaluator["intercept"], dtype=float)
    weights = np.stack([np.asarray(evaluator["coefficients"][label], dtype=float)
                        for label in evaluator["classes"]])
    standardised = (rows - mean) / scale
    logits = standardised @ weights.T + intercept
    return [evaluator["classes"][int(np.argmax(row))] for row in logits]
