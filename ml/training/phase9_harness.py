"""Phase 9 shared evaluation harness for transcriptomic classifiers.

Every model in Phase 9 is evaluated through this module so that the anti-leakage
rules are enforced in one place rather than re-implemented (and re-broken) per
script.

The rules this encodes
----------------------
1.  **Group-aware splitting.** Samples are split by their *biological group*
    (a distinct genotype x treatment x timepoint combination), never by sample.
    The two or three replicate arrays inside a group are technical/biological
    siblings measured together; letting one land in train and another in test is
    the standard way to manufacture a high accuracy that means nothing.
2.  **Feature selection inside the fold.** High-variance/ANOVA filtering and any
    supervised gene ranking happen *after* the split, on training samples only.
    Selecting genes on all 44 samples and then cross-validating would leak the
    test labels into the feature set through the selection statistic.
3.  **Baseline on identical folds.** The majority/mean baseline sees exactly the
    same splits, so "beats baseline" is a like-for-like statement.
4.  **Finite-sample corrected permutation p-values.** Reporting `p = 0.0` from a
    permutation test is never correct: with B permutations the smallest
    attainable value is 1/(B+1). This module reports
    `p = (1 + #{null >= observed}) / (1 + B)`.
5.  **Per-group metrics.** Pooled accuracy can hide a class that is never
    predicted. Per-group recall is always returned alongside the pooled number.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, balanced_accuracy_score, confusion_matrix,
                             f1_score)
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

SEED = 42

# Gene filtering is part of the model, not of the data, precisely so that it can
# be fitted inside a fold.
MIN_EXPRESSION_FRACTION = 0.20   # gene must be detected in >= 20 % of training samples
TOP_VARIABLE_GENES = 1000        # variance preselection, fitted per fold
TOP_ANOVA_GENES = 150            # supervised selection, fitted per fold


def classification_learners() -> dict:
    """The four model families required by the Phase 9 brief, plus one baseline.

    No deep learning: the largest task here has 64 samples over 16 groups, where a
    neural network would have far more parameters than independent observations
    and could not be identified.
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
            n_estimators=400, min_samples_leaf=1, random_state=SEED, n_jobs=-1),
        "gradient_boosting": lambda: HistGradientBoostingClassifier(
            max_iter=200, learning_rate=0.06, max_leaf_nodes=7, random_state=SEED),
    }


def select_features(x_train: np.ndarray, y_train: np.ndarray,
                    column_names: list[str], variance_preselection: bool = True) -> np.ndarray:
    """Fold-internal gene selection. Returns indices into the full gene axis.

    Two stages, both fitted only on training data:
      1. drop genes that are unexpressed or flat across the training samples;
      2. keep the most variable, then rank the survivors by one-way ANOVA F on the
         training labels.
    """
    # Stage 1: detection filter.
    detected = (x_train > 0).mean(axis=0) >= MIN_EXPRESSION_FRACTION
    variance = x_train.var(axis=0)
    keep = np.flatnonzero(detected & (variance > 0))
    if keep.size == 0:
        raise ValueError("No genes survived the detection filter")

    # Stage 2a: variance preselection (unsupervised, still training-only).
    #
    # This stage silently degenerates if the input has already been z-scored per
    # gene, because then every gene has variance exactly 1 and the "most variable"
    # genes become an arbitrary tie-break. That failure mode was observed during
    # Phase 9 on a cross-study z-scored matrix and produced a convincing-looking
    # negative result that was actually a pipeline artefact. The guard below turns
    # it into a loud error instead.
    if variance_preselection and keep.size > TOP_VARIABLE_GENES:
        spread = variance[keep]
        if spread.max() > 0 and (spread.max() - spread.min()) / spread.max() < 1e-6:
            raise ValueError(
                "Gene variances are degenerate (all equal); variance preselection "
                "would pick arbitrary features. Pass raw-scale data, or disable the "
                "variance stage for already-standardised input.")
        order = np.argsort(variance[keep])[::-1][:TOP_VARIABLE_GENES]
        keep = keep[order]

    # Stage 2b: supervised selection on training labels only.
    scores = _anova_f(x_train[:, keep], y_train)
    if np.all(~np.isfinite(scores)):
        return keep
    scores = np.nan_to_num(scores, nan=-np.inf)
    rank = np.argsort(scores)[::-1][:TOP_ANOVA_GENES]
    return keep[rank]


def _anova_f(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """One-way ANOVA F statistic per column, implemented without sklearn's selector
    so the call stays explicit about what it is doing and when."""
    classes = np.unique(y)
    overall_mean = x.mean(axis=0)
    between = np.zeros(x.shape[1])
    within = np.zeros(x.shape[1])
    for label in classes:
        block = x[y == label]
        if block.shape[0] == 0:
            continue
        between += block.shape[0] * (block.mean(axis=0) - overall_mean) ** 2
        within += ((block - block.mean(axis=0)) ** 2).sum(axis=0)
    dof_between = max(len(classes) - 1, 1)
    dof_within = max(x.shape[0] - len(classes), 1)
    denominator = (within / dof_within)
    with np.errstate(divide="ignore", invalid="ignore"):
        f = (between / dof_between) / denominator
    return f


def warn_on_fold_imbalance(y: np.ndarray, groups: np.ndarray) -> list[str]:
    """Report held-out folds that contain only one class.

    This is not an error - a held-out biological group genuinely has one condition -
    but it must be *stated*, because a fold whose test set is single-class turns the
    pooled accuracy into a sensitive measure and can look like a catastrophic failure
    when a model simply guesses the other class.
    """
    notes = []
    for group in np.unique(groups):
        labels = np.unique(y[groups == group])
        if len(labels) == 1:
            notes.append(str(labels[0]))
    return notes


def grouped_cv_score(x: np.ndarray, y: np.ndarray, groups: np.ndarray,
                     learner, n_splits: int | None = None,
                     column_names: list[str] | None = None,
                     seed: int = SEED) -> dict:
    """Leave-one-group-out CV with in-fold gene selection.

    Leave-one-group-out is used rather than a k-fold partition because with these
    designs every group belongs to exactly one class, and StratifiedGroupKFold
    cannot balance class membership across folds when the group determines the
    label. Measured on OSD-411 it produced a fold whose entire test set was
    'vertical', which drove the random forest to a pooled accuracy of 0.000 - a
    number that reads as a model failure but is an artefact of the fold partition.

    Leave-one-group-out is deterministic, gives every group the same treatment, and
    guarantees every training fold contains all classes whenever the study has at
    least two groups per class. The price is more fits, which is affordable here.
    """
    column_names = column_names or [f"g{i}" for i in range(x.shape[1])]
    n_groups = len(np.unique(groups))
    splitter = LeaveOneGroupOut()

    prediction = np.empty(len(y), dtype=object)
    filled = np.zeros(len(y), dtype=bool)
    selected_per_fold = []

    for train_idx, test_idx in splitter.split(x, y, groups):
        if set(groups[train_idx]) & set(groups[test_idx]):
            raise AssertionError("Group leakage between train and test")
        chosen = select_features(x[train_idx], y[train_idx], column_names)
        selected_per_fold.append(set(column_names[i] for i in chosen))
        model = learner()
        model.fit(x[np.ix_(train_idx, chosen)], y[train_idx])
        prediction[test_idx] = model.predict(x[np.ix_(test_idx, chosen)])
        filled[test_idx] = True

    if not filled.all():
        raise AssertionError("Some samples were never held out")

    labels = np.unique(y)
    report = {
        "accuracy": float(accuracy_score(y, prediction)),
        "balancedAccuracy": float(balanced_accuracy_score(y, prediction)),
        "macroF1": float(f1_score(y, prediction, average="macro")),
        "nSamples": int(len(y)),
        "nGroups": int(n_groups),
        "confusionMatrix": confusion_matrix(y, prediction, labels=labels).tolist(),
        "classLabels": [str(label) for label in labels],
        "perGroupRecall": {
            str(label): float((prediction[y == label] == label).mean()) for label in labels
        },
        "genesPerFold": [len(s) for s in selected_per_fold],
        "genesSharedAcrossFolds": len(set.intersection(*selected_per_fold))
        if selected_per_fold else 0,
        "singleClassHeldOutGroups": warn_on_fold_imbalance(y, groups),
        "validationScheme": "leave-one-biological-group-out",
    }
    report["bootstrapCi"] = bootstrap_ci(y, prediction, seed=seed)
    return report


def bootstrap_ci(y: np.ndarray, prediction: np.ndarray, seed: int = SEED,
                 n_boot: int = 2000) -> dict:
    """Percentile bootstrap over samples, stratified by true class.

    Reported because a held-out accuracy from 44 samples is a point estimate with a
    very wide interval, and quoting the point alone would overstate certainty.
    """
    rng = np.random.default_rng(seed)
    labels = np.unique(y)
    scores = []
    for _ in range(n_boot):
        indices = []
        for label in labels:
            pool = np.flatnonzero(y == label)
            indices.extend(rng.choice(pool, size=pool.size, replace=True))
        indices = np.array(indices)
        scores.append(accuracy_score(y[indices], prediction[indices]))
    return {
        "metric": "accuracy",
        "lower": float(np.quantile(scores, 0.025)),
        "upper": float(np.quantile(scores, 0.975)),
        "confidence": 0.95,
        "method": "stratified percentile bootstrap over held-out samples",
    }


def permutation_test(x: np.ndarray, y: np.ndarray, groups: np.ndarray, learner,
                     observed: float, n_permutations: int = 100,
                     seed: int = SEED, n_splits: int | None = None) -> dict:
    """Label-permutation null for the held-out accuracy.

    Labels are permuted **between groups, not between samples**, because the group
    is the exchangeable unit: shuffling individual replicates would break the
    within-group concordance that the real data has and make the null too easy to
    beat.

    The p-value uses the finite-sample correction of Phipson & Smyth (2010):
        p = (1 + #{null >= observed}) / (1 + n_permutations)
    and is therefore never exactly zero.
    """
    rng = np.random.default_rng(seed)
    unique_groups = np.unique(groups)
    # Group-level labels: all samples in a group must share a label for this to be
    # a valid permutation scheme.
    group_label = {}
    for group in unique_groups:
        labels = np.unique(y[groups == group])
        if len(labels) != 1:
            raise ValueError(f"Group {group} spans multiple labels: {labels}")
        group_label[group] = labels[0]

    null = []
    for _ in range(n_permutations):
        shuffled = dict(zip(unique_groups, rng.permutation(
            [group_label[g] for g in unique_groups])))
        permuted = np.array([shuffled[g] for g in groups])
        try:
            score = grouped_cv_score(x, permuted, groups, learner,
                                     seed=int(rng.integers(1_000_000)))["accuracy"]
        except (ValueError, AssertionError):
            continue
        null.append(score)

    null = np.array(null)
    at_least = int((null >= observed).sum())
    return {
        "observedAccuracy": float(observed),
        "nPermutations": int(len(null)),
        "nullMean": float(null.mean()) if null.size else None,
        "nullP95": float(np.quantile(null, 0.95)) if null.size else None,
        "pValue": (1 + at_least) / (1 + len(null)),
        "correction": "finite-sample corrected: (1 + #{null >= observed}) / (1 + B)",
        "scheme": "labels permuted between biological groups",
    }


def summarize_learners(x, y, groups, column_names, n_splits=None, seed=SEED) -> dict:
    results = {}
    for name, factory in classification_learners().items():
        results[name] = grouped_cv_score(x, y, groups, factory, n_splits=n_splits,
                                         column_names=column_names, seed=seed)
    return results


def extract_linear_evaluator(fitted_model, feature_names: list[str]) -> dict:
    """Convert a fitted (possibly pipelined) linear classifier to a JSON evaluator.

    Binary and multiclass need different treatment, and getting it wrong is silent:

    * Multiclass (`coef_` shape (k, n)) - one coefficient row and one intercept per
      class, used directly.
    * Binary (`coef_` shape (1, n)) - sklearn stores a single row describing the
      decision function, with `classes_[1]` on the positive side. Storing that same
      row under both class labels, which is what a naive loop does, gives both
      classes identical scores and the model can never disagree with itself. The
      correct softmax-equivalent encoding fixes `classes_[0]` at score zero and
      puts the decision function on `classes_[1]`, which reproduces the sigmoid.
    """
    steps = getattr(fitted_model, "named_steps", None)
    if steps:
        values = list(steps.values())
        linear = values[-1]
        # Find the scaler by capability, not by step name. Looking it up by the
        # literal name "scale" silently yields None for any pipeline that names the
        # step differently, and a missing scaler does not raise - it produces a model
        # whose standardisation is the identity, which is wrong but plausible-looking.
        scalers = [step for step in values
                   if hasattr(step, "mean_") and hasattr(step, "scale_")]
        if len(scalers) > 1:
            raise ValueError("Ambiguous pipeline: more than one fitted scaler")
        scaler = scalers[0] if scalers else None
        if scaler is None and len(values) > 1:
            raise ValueError(
                "Pipeline has transformers but no fitted scaler was found; refusing "
                "to emit an evaluator that silently skips standardisation")
    else:
        linear, scaler = fitted_model, None
    if not hasattr(linear, "coef_"):
        raise ValueError("Not a linear model")
    width = len(feature_names)
    classes = [str(c) for c in linear.classes_]
    coefficients = np.atleast_2d(linear.coef_)
    intercepts = np.atleast_1d(linear.intercept_)
    if coefficients.shape[0] == 1 and len(classes) == 2:
        per_class = {
            classes[0]: [0.0] * width,
            classes[1]: [float(v) for v in coefficients[0]],
        }
        per_intercept = [0.0, float(intercepts[0])]
    elif coefficients.shape[0] == len(classes):
        per_class = {label: [float(v) for v in coefficients[i]]
                     for i, label in enumerate(classes)}
        per_intercept = [float(v) for v in intercepts]
    else:
        raise ValueError(
            f"Coefficient shape {coefficients.shape} does not match {len(classes)} classes")
    return {
        "kind": "linear-softmax",
        "features": list(feature_names),
        "classes": classes,
        "mean": [float(v) for v in scaler.mean_] if scaler is not None else [0.0] * width,
        "scale": [float(v) for v in scaler.scale_] if scaler is not None else [1.0] * width,
        "coefficients": per_class,
        "intercept": per_intercept,
    }
