"""Phase 9 shared harness: group-held-out cross-validation with in-fold selection.

Design decisions that matter, and why
------------------------------------
1. **Leave-one-group-out, not stratified k-fold.** Every group here is a complete
   experimental condition (a genotype x treatment x timepoint cell, or a single
   seedling). Stratified k-fold splits *group members* across folds in ways that
   silently leak: on OSD-411 it produced a fold whose entire test set was one
   class, and a model that never saw a tissue type in training. LOGO is
   deterministic, gives every group the same treatment, and cannot leak.

2. **Feature selection inside the fold.** Filtering genes on the pooled matrix
   lets held-out groups influence the feature set. Every selection step here is
   fitted on the training rows of one fold only.

3. **Permutation at the group level.** Labels are permuted between groups, not
   between samples, because the group is the independent unit. Permuting samples
   would break the within-group correlation and produce a null that is too narrow,
   i.e. p-values that are too small.

4. **Permutation p-values are finite-sample corrected**: (1 + #{null >= observed})
   / (1 + B). With B permutations the smallest attainable p-value is 1/(B+1), and
   no honest implementation can report zero.
"""
from __future__ import annotations

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

SEED = 20261107
TOP_VARIABLE_GENES = 1000
TOP_ANOVA_GENES = 150
MIN_EXPRESSION_FRACTION = 0.2


def classification_learners() -> dict:
    """Five families, including the mandatory majority baseline.

    No deep learning: the largest task here has 44 samples over 22 groups, where a
    network would have more parameters than independent observations.
    """
    return {
        "baseline_majority": lambda: DummyClassifier(strategy="most_frequent"),
        "logistic_l2": lambda: Pipeline([
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=5000, C=1.0, random_state=SEED)),
        ]),
        "logistic_l1": lambda: Pipeline([
            ("scale", StandardScaler()),
            ("model", LogisticRegression(max_iter=5000, C=0.1, penalty="l1",
                                         solver="liblinear", random_state=SEED)),
        ]),
        "random_forest": lambda: RandomForestClassifier(
            n_estimators=300, min_samples_leaf=1, random_state=SEED, n_jobs=-1),
        "hist_gradient_boosting": lambda: HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.06, max_leaf_nodes=7, random_state=SEED),
    }


def _anova_f(matrix: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """One-way ANOVA F statistic per column."""
    classes = np.unique(labels)
    overall = matrix.mean(axis=0)
    between = np.zeros(matrix.shape[1])
    within = np.zeros(matrix.shape[1])
    for label in classes:
        block = matrix[labels == label]
        if block.shape[0] == 0:
            continue
        between += block.shape[0] * (block.mean(axis=0) - overall) ** 2
        within += ((block - block.mean(axis=0)) ** 2).sum(axis=0)
    dof_between = max(len(classes) - 1, 1)
    dof_within = max(matrix.shape[0] - len(classes), 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return (between / dof_between) / (within / dof_within)


def select_features(matrix: np.ndarray, labels: np.ndarray,
                    n_features: int = TOP_ANOVA_GENES,
                    variance_preselection: bool = True) -> np.ndarray:
    """Fold-internal gene selection. Returns indices into the gene axis.

    Stage 1 removes genes that are undetected or flat in the training rows.
    Stage 2 keeps the most variable survivors (unsupervised, training-only).
    Stage 3 ranks by ANOVA F on the training labels.

    `variance_preselection` exists because stage 2 is meaningless on data that has
    already been standardised per gene: every variance is exactly 1, so "most
    variable" becomes an arbitrary tie-break. That failure mode produced a
    convincing false negative during Phase 9, so it is now an explicit choice
    rather than a silent default.
    """
    detected = (matrix > 0).mean(axis=0) >= MIN_EXPRESSION_FRACTION
    variance = matrix.var(axis=0)
    keep = np.flatnonzero(detected & (variance > 0))
    if keep.size == 0:
        raise ValueError("No genes survived the detection filter")
    if variance_preselection and keep.size > TOP_VARIABLE_GENES:
        spread = variance[keep]
        if spread.max() > 0 and (spread.max() - spread.min()) / spread.max() < 1e-6:
            raise ValueError(
                "Gene variances are degenerate; variance preselection would choose "
                "arbitrary genes. Pass raw-scale data or set "
                "variance_preselection=False.")
        keep = keep[np.argsort(variance[keep])[::-1][:TOP_VARIABLE_GENES]]
    scores = _anova_f(matrix[:, keep], labels)
    if not np.any(np.isfinite(scores)):
        return keep
    scores = np.nan_to_num(scores, nan=-np.inf)
    return keep[np.argsort(scores)[::-1][:n_features]]


def warn_on_fold_imbalance(labels: np.ndarray, groups: np.ndarray) -> list[str]:
    """Held-out groups that contain a single class.

    These are not errors under LOGO when a group is one experimental condition,
    but the count is reported so a reader can see how much of the estimate comes
    from conditions the training folds never contained.
    """
    return [str(labels[groups == group][0]) for group in np.unique(groups)]


def grouped_cv_score(matrix, labels, groups, learner, n_features=TOP_ANOVA_GENES,
                     variance_preselection=True, seed=SEED) -> dict:
    """Leave-one-group-out CV. Every returned metric is out-of-fold."""
    splitter = LeaveOneGroupOut()
    prediction = np.empty(len(labels), dtype=object)
    filled = np.zeros(len(labels), dtype=bool)
    selected_per_fold = []

    for train_idx, test_idx in splitter.split(matrix, labels, groups):
        if set(groups[train_idx]) & set(groups[test_idx]):
            raise AssertionError("Group leakage between train and test")
        chosen = select_features(matrix[train_idx], labels[train_idx], n_features,
                                 variance_preselection)
        selected_per_fold.append(set(chosen.tolist()))
        model = learner()
        model.fit(matrix[np.ix_(train_idx, chosen)], labels[train_idx])
        prediction[test_idx] = model.predict(matrix[np.ix_(test_idx, chosen)])
        filled[test_idx] = True

    if not filled.all():
        raise AssertionError("Some samples were never held out")

    classes = np.unique(labels)
    return {
        "accuracy": float(accuracy_score(labels, prediction)),
        "balancedAccuracy": float(balanced_accuracy_score(labels, prediction)),
        "macroF1": float(f1_score(labels, prediction, average="macro")),
        "nSamples": int(len(labels)),
        "nGroups": int(len(np.unique(groups))),
        "confusionMatrix": confusion_matrix(labels, prediction, labels=classes).tolist(),
        "classLabels": [str(c) for c in classes],
        "perClassRecall": {str(c): float((prediction[labels == c] == c).mean())
                           for c in classes},
        "singleClassHeldOutGroups": warn_on_fold_imbalance(labels, groups),
        "genesSharedAcrossFolds": len(set.intersection(*selected_per_fold))
        if selected_per_fold else 0,
        "validationScheme": "leave-one-biological-group-out",
        "bootstrapCi": bootstrap_ci(labels, prediction, seed=seed),
        "prediction": prediction,
    }


def bootstrap_ci(labels, prediction, n_resamples=2000, seed=SEED) -> dict:
    """Stratified percentile bootstrap over held-out predictions."""
    generator = np.random.default_rng(seed)
    classes = np.unique(labels)
    scores = []
    for _ in range(n_resamples):
        picks = []
        for label in classes:
            members = np.flatnonzero(labels == label)
            picks.append(generator.choice(members, size=len(members), replace=True))
        index = np.concatenate(picks)
        scores.append(balanced_accuracy_score(labels[index], prediction[index]))
    return {"metric": "balancedAccuracy",
            "lower": float(np.percentile(scores, 2.5)),
            "upper": float(np.percentile(scores, 97.5)),
            "confidence": 0.95,
            "method": "stratified percentile bootstrap over held-out predictions"}


def permutation_test(matrix, labels, groups, learner, observed,
                     n_permutations=100, n_features=TOP_ANOVA_GENES,
                     variance_preselection=True, seed=SEED) -> dict:
    """Null distribution from permuting labels BETWEEN GROUPS.

    The group is the independent unit, so the labels travel with the group. This
    preserves the within-group correlation structure and therefore gives an honest
    null: permuting samples instead would understate the null spread.
    """
    generator = np.random.default_rng(seed)
    unique_groups = np.unique(groups)
    group_label = {group: labels[groups == group][0] for group in unique_groups}
    null = []
    for _ in range(n_permutations):
        shuffled = generator.permutation(unique_groups)
        mapping = {original: group_label[donor]
                   for original, donor in zip(unique_groups, shuffled)}
        permuted = np.array([mapping[group] for group in groups], dtype=object)
        if len(np.unique(permuted)) < len(np.unique(labels)):
            continue
        score = grouped_cv_score(matrix, permuted, groups, learner,
                                 n_features=n_features,
                                 variance_preselection=variance_preselection,
                                 seed=seed)["balancedAccuracy"]
        null.append(score)
    null = np.array(null)
    exceed = int((null >= observed).sum())
    return {
        "observedBalancedAccuracy": float(observed),
        "nPermutations": int(len(null)),
        "nullMean": float(null.mean()) if len(null) else None,
        "nullP95": float(np.percentile(null, 95)) if len(null) else None,
        "pValue": (1 + exceed) / (1 + len(null)),
        "correction": "finite-sample corrected: (1 + #{null >= observed}) / (1 + B)",
        "unit": "labels permuted between biological groups",
        "scheme": "labels permuted between biological groups",
    }


def evaluate_all_learners(matrix, labels, groups, n_features=TOP_ANOVA_GENES,
                          variance_preselection=True, seed=SEED) -> dict:
    results = {}
    for name, factory in classification_learners().items():
        score = grouped_cv_score(matrix, labels, groups, factory, n_features,
                                 variance_preselection, seed)
        score.pop("prediction", None)
        results[name] = score
    return results


def extract_linear_evaluator(model, feature_names: list[str]) -> dict:
    """Serialise a fitted linear classifier into a dependency-free scorer.

    The runtime must evaluate a model without sklearn, so the arithmetic is stored
    explicitly: standardise with the training mean and scale, apply the coefficient
    matrix, then softmax. Keeping it explicit also means a reviewer can check the
    served arithmetic by hand.

    Two traps are handled here, both of which produced wrong answers during Phase 9:

    * A **binary** logistic model stores a single coefficient row. Writing that row
      under both class labels makes the two classes score identically, so the model
      can never disagree with itself. The binary case is therefore expanded to two
      rows: zeros for class 0 and the decision function for class 1.
    * The scaler must not be looked up by the literal step name "scale".
      `named_steps` returns None on a miss instead of raising, so a renamed step
      would silently skip standardisation. It is detected by fitted attributes.
    """
    from sklearn.pipeline import Pipeline

    scaler = None
    estimator = model
    if isinstance(model, Pipeline):
        for _, step in model.steps[:-1]:
            if hasattr(step, "mean_") and hasattr(step, "scale_"):
                scaler = step
                break
        if scaler is None:
            raise ValueError(
                "No fitted scaler found in the pipeline; refusing to emit an "
                "evaluator that would silently skip standardisation")
        estimator = model.steps[-1][1]

    coefficients = np.atleast_2d(np.asarray(estimator.coef_, dtype=float))
    intercept = np.atleast_1d(np.asarray(estimator.intercept_, dtype=float))
    classes = [str(c) for c in estimator.classes_]

    if coefficients.shape[0] == 1 and len(classes) == 2:
        # Binary: class 0 gets the zero row so the decision function lands on
        # class 1. Both rows must exist or the classes are indistinguishable.
        coefficients = np.vstack([np.zeros_like(coefficients[0]), coefficients[0]])
        intercept = np.concatenate([[-intercept[0] * 0.0], intercept])
    if coefficients.shape[0] != len(classes):
        raise ValueError(
            f"Coefficient rows ({coefficients.shape[0]}) do not match classes "
            f"({len(classes)})")
    if len(intercept) != len(classes):
        raise ValueError("Intercept length does not match class count")
    if not np.all(np.isfinite(coefficients)) or not np.all(np.isfinite(intercept)):
        raise ValueError("Unsafe non-finite model artifact")

    return {
        "kind": "linear-softmax",
        "features": list(feature_names),
        "classes": classes,
        "mean": [float(v) for v in scaler.mean_],
        "scale": [float(v) for v in scaler.scale_],
        "coefficients": {label: [float(v) for v in row]
                         for label, row in zip(classes, coefficients)},
        "intercept": [float(v) for v in intercept],
    }


def softmax_probabilities(evaluator: dict, values: list[float]) -> dict:
    """Reference implementation of the served arithmetic, used by tests."""
    features = evaluator["features"]
    if len(values) != len(features):
        raise ValueError(f"Expected {len(features)} features, got {len(values)}")
    standardised = [
        (float(value) - mean) / (scale if scale else 1.0)
        for value, mean, scale in zip(values, evaluator["mean"], evaluator["scale"])
    ]
    scores = {}
    for label in evaluator["classes"]:
        coefficients = evaluator["coefficients"][label]
        scores[label] = sum(c * x for c, x in zip(coefficients, standardised)) \
            + evaluator["intercept"][evaluator["classes"].index(label)]
    peak = max(scores.values())
    exponentiated = {label: np.exp(score - peak) for label, score in scores.items()}
    total = sum(exponentiated.values())
    return {label: float(value / total) for label, value in exponentiated.items()}
