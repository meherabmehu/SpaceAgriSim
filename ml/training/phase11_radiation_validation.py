"""Phase 11: can the radiation classifiers be improved without fooling ourselves?

Both served radiation models rest on 44 Affymetrix arrays over 22 biological groups.
Phase 10 measured them honestly (balanced accuracy 0.898 and 0.910 group-held-out) and
showed the signal is distributed rather than concentrated in a few genes. The open
question for Phase 11 is whether a different, scientifically justified learner does
meaningfully better.

Five candidates, every one of them evaluated with the same nested group-aware protocol:

  shipped        top-150 ANOVA genes + L2 logistic, exactly what is served
  sparse         L1 logistic, so most gene weights are exactly zero
  linear_svm     linear support vector classifier
  shallow        logistic regression on a 25-gene panel, to test whether less is more
  module         training-only co-expression modules, so the features are not single genes

Protocol, fixed before the run:

  * outer loop is leave-one-biological-group-out (22 folds), so no group is ever split
  * gene selection happens inside each outer fold, on training rows only
  * the inner loop picks any hyper-parameter on training groups only
  * a candidate is promoted only if it beats the shipped model on held-out balanced
    accuracy by at least 0.02 AND wins on more than half of the groups it is compared
    on AND its permutation p stays below 0.05

That bar is deliberately hard. With 44 arrays a 0.02 difference in balanced accuracy is
roughly one array, so a marginal win is noise wearing a number.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (balanced_accuracy_score, brier_score_loss, f1_score,
                             log_loss)
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
sys.path.insert(0, str(ROOT / "ml" / "training"))
OUT = ROOT / "ml" / "evaluation" / "phase11_radiation_validation"

SEED = 1187
PERMUTATIONS = 2000
PROMOTION_MARGIN = 0.02
TOP_GENES = 150


def load_model_data(model_id: str):
    """Expression, labels and group keys exactly as the served model was trained."""
    from train_radiation_osd46 import group_key, load

    matrix, genes, samples = load()
    if model_id == "radiation-quality-osd46-v1":
        labels = samples["radiation"].to_numpy()
    else:
        labels = np.where(samples["radiation"].eq("non-irradiated"),
                          "control", "irradiated")
    return pd.DataFrame(matrix, columns=genes), np.asarray(labels), group_key(samples)


def anova_scores(matrix, labels):
    overall = matrix.mean(axis=0)
    between = np.zeros(matrix.shape[1])
    within = np.zeros(matrix.shape[1])
    groups = np.unique(labels)
    for value in groups:
        rows = matrix[labels == value]
        centre = rows.mean(axis=0)
        between += rows.shape[0] * (centre - overall) ** 2
        within += ((rows - centre) ** 2).sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        score = (between / max(len(groups) - 1, 1)) / (
            within / max(matrix.shape[0] - len(groups), 1))
    return np.nan_to_num(score, nan=0.0, posinf=0.0)


def select(matrix, labels, k):
    """Gene selection through the harness the shipped model was trained with.

    Reusing `select_features` rather than re-deriving it is what makes the "shipped"
    row a reproduction instead of a lookalike: same detection filter, same variance
    preselection, same ANOVA ranking.
    """
    from phase9_harness import select_features
    return select_features(matrix, labels, n_features=k)


def modules(matrix, labels, k_dims=20, k_genes=60):
    """Training-only co-expression modules: hierarchical clustering on gene correlation.

    Modules are formed without looking at labels, then each module is summarised by its
    first principal component. The point is to answer "does a gene-level classifier beat
    a module-level one?" rather than to chase accuracy.
    """
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform

    variance = matrix.var(axis=0)
    keep = np.flatnonzero(variance > 0)
    if keep.size > 800:
        keep = keep[np.argsort(variance[keep])[-800:]]
    block = matrix[:, keep]
    correlation = np.nan_to_num(np.corrcoef(block, rowvar=False), nan=0.0)
    distance = np.clip(1.0 - correlation, 0.0, 2.0)
    np.fill_diagonal(distance, 0.0)
    tree = linkage(squareform(distance, checks=False), method="average")
    clusters = fcluster(tree, t=k_dims, criterion="maxclust")
    features = []
    for cluster in np.unique(clusters):
        members = keep[clusters == cluster]
        if members.size < 3:
            continue
        chosen = members[np.argsort(-variance[members])[:k_genes]]
        block = matrix[:, chosen]
        block = block - block.mean(axis=0)
        # Project in gene space, not sample space: the first right singular vector has
        # one entry per gene, so a held-out row can be scored with the same direction.
        _, _, vt = np.linalg.svd(block, full_matrices=False)
        direction = vt[0]
        direction = direction * np.sign(direction[np.argmax(np.abs(direction))])
        features.append((chosen, direction))
    return features


def module_design(matrix, fit):
    """Project rows onto modules fitted on the training rows only."""
    columns = []
    for chosen, direction in fit:
        block = matrix[:, chosen]
        block = block - block.mean(axis=0)
        columns.append(block @ direction)
    return np.column_stack(columns)


GRID = ((25, "l2"), (75, "l2"), (150, "l2"), (150, "svm"))
AUTO_TRACE: list = []


def fit_config(matrix, y, train, test, k, family):
    """One (gene count, learner family) pair, fitted on training rows only."""
    from phase9_harness import classification_learners
    chosen = select(matrix[train], y[train], k)
    if family == "svm":
        model = Pipeline([("scale", StandardScaler()),
                          ("model", LinearSVC(C=0.05, max_iter=20000, random_state=SEED))])
    else:
        model = classification_learners()["logistic_l2"]()
    model.fit(matrix[np.ix_(train, chosen)], y[train])
    return model, chosen


def auto_selected(matrix, y, train, test, k, group_of):
    """Choose the configuration by inner group-out CV on the training rows only.

    This is the honest counterpart to the fixed-k rows: when a candidate wins after we
    compared five of them on the same 22 folds, the win may be the comparison rather
    than the model. Here the choice of configuration is made *inside* each outer fold,
    so a held-out group can never influence which configuration is used to predict it.
    """
    inner_groups = group_of[train]
    best = (-1.0, GRID[0])
    for config in GRID:
        prediction = np.empty(len(train), dtype=object)
        for inner_train, inner_test in LeaveOneGroupOut().split(train, y[train],
                                                                inner_groups):
            model, _ = fit_config(matrix, y, train[inner_train], train[inner_test],
                                  config[0], config[1])
            chosen = select(matrix[train[inner_train]], y[train[inner_train]], config[0])
            prediction[inner_test] = model.predict(matrix[np.ix_(train[inner_test], chosen)])
        score = balanced_accuracy_score(y[train], prediction)
        if score > best[0]:
            best = (score, config)
    AUTO_TRACE.append(f"k={best[1][0]}/{best[1][1]}")
    model, chosen = fit_config(matrix, y, train, test, best[1][0], best[1][1])
    return model.predict(matrix[np.ix_(test, chosen)]), None


def evaluate(name, predict_fold, expression, labels, groups, k=TOP_GENES):
    """Run one candidate through the outer leave-one-group-out loop."""
    prediction = np.empty(len(labels), dtype=object)
    probabilities = np.full(len(labels), np.nan)
    fold_scores = []
    for train_index, test_index in LeaveOneGroupOut().split(expression, labels, groups):
        assert not set(groups[train_index]) & set(groups[test_index]), "group leak"
        predicted, probability = predict_fold(expression, labels, train_index,
                                              test_index, k, groups)
        prediction[test_index] = predicted
        if probability is not None:
            probabilities[test_index] = probability
        truth = labels[test_index]
        fold_scores.append(float(balanced_accuracy_score(truth, predicted)))
    result = {
        "candidate": name,
        "accuracy": round(float((prediction == labels).mean()), 4),
        "balancedAccuracy": round(float(balanced_accuracy_score(labels, prediction)), 4),
        "macroF1": round(float(f1_score(labels, prediction, average="macro")), 4),
        "folds": int(len(fold_scores)),
        "foldBalancedAccuracySd": round(float(np.std(fold_scores)), 4),
        "foldsBelowChance": int(sum(1 for score in fold_scores if score < 1.0 / len(set(labels)))),
        "prediction": prediction,
        "probabilities": probabilities,
    }
    return result


def permutation_p(prediction, labels, groups, permutations=PERMUTATIONS, seed=SEED):
    """Shuffle labels within genotype so the null cannot be beaten by genotype."""
    generator = np.random.default_rng(seed)
    observed = float(balanced_accuracy_score(labels, prediction))
    null = np.empty(permutations)
    for index in range(permutations):
        null[index] = balanced_accuracy_score(generator.permutation(labels), prediction)
    exceed = int((null >= observed).sum())
    return {
        "observed": round(observed, 4),
        "null95": [round(float(np.percentile(null, 2.5)), 4),
                   round(float(np.percentile(null, 97.5)), 4)],
        "exceedances": exceed,
        "permutations": permutations,
        "pCorrected": round((exceed + 1) / (permutations + 1), 5),
    }


def calibration(probabilities, labels):
    """Reliability of the positive-class probability, where the model can supply one."""
    if np.isnan(probabilities).any():
        return None
    binary = (labels == np.unique(labels)[-1]).astype(int)
    bins = np.linspace(0.0, 1.0, 6)
    rows = []
    for low, high in zip(bins[:-1], bins[1:]):
        mask = (probabilities >= low) & (probabilities < high)
        if mask.sum() == 0:
            continue
        rows.append({"bin": f"{low:.1f}-{high:.1f}", "n": int(mask.sum()),
                     "meanPredicted": round(float(probabilities[mask].mean()), 3),
                     "observedRate": round(float(binary[mask].mean()), 3)})
    gaps = [abs(row["meanPredicted"] - row["observedRate"]) for row in rows]
    return {
        "expectedCalibrationError": round(float(np.average(
            gaps, weights=[row["n"] for row in rows])), 4),
        "brier": round(float(brier_score_loss(binary, probabilities)), 4),
        "logLoss": round(float(log_loss(binary, np.clip(probabilities, 1e-9, 1 - 1e-9))), 4),
        "bins": rows,
        "note": ("single-logit models on 44 arrays. The ECE is descriptive: five bins over "
                 "44 samples cannot validate a calibration curve."),
    }


def main() -> int:
    report = {"phase": 11, "promotionMargin": PROMOTION_MARGIN, "models": {}}

    for model_id in ("radiation-quality-osd46-v1", "radiation-exposure-osd46-v1"):
        frame, labels, groups = load_model_data(model_id)
        expression = frame.to_numpy(float)
        classes = sorted(set(labels.tolist()))
        print(f"\n{model_id}: {expression.shape[0]} arrays, {len(set(groups))} groups, "
              f"classes {classes}")

        def shipped(matrix, y, train, test, k, group_of=None):
            from phase9_harness import classification_learners
            chosen = select(matrix[train], y[train], k)
            model = classification_learners()["logistic_l2"]()
            model.fit(matrix[np.ix_(train, chosen)], y[train])
            probability = (model.predict_proba(matrix[np.ix_(test, chosen)])[:, -1]
                           if len(classes) == 2 else None)
            return model.predict(matrix[np.ix_(test, chosen)]), probability

        def sparse(matrix, y, train, test, k, group_of=None):
            from phase9_harness import classification_learners
            chosen = select(matrix[train], y[train], k)
            model = classification_learners()["logistic_l1"]()
            model.fit(matrix[np.ix_(train, chosen)], y[train])
            probability = (model.predict_proba(matrix[np.ix_(test, chosen)])[:, -1]
                           if len(classes) == 2 else None)
            return model.predict(matrix[np.ix_(test, chosen)]), probability

        def svm(matrix, y, train, test, k, group_of=None):
            chosen = select(matrix[train], y[train], k)
            model = Pipeline([("scale", StandardScaler()),
                              ("model", LinearSVC(C=0.05, max_iter=20000,
                                                  random_state=SEED))])
            model.fit(matrix[np.ix_(train, chosen)], y[train])
            return model.predict(matrix[np.ix_(test, chosen)]), None

        def shallow(matrix, y, train, test, k, group_of=None):
            chosen = select(matrix[train], y[train], 25)
            model = Pipeline([("scale", StandardScaler()),
                              ("model", LogisticRegression(C=0.5, max_iter=5000,
                                                           random_state=SEED))])
            model.fit(matrix[np.ix_(train, chosen)], y[train])
            probability = (model.predict_proba(matrix[np.ix_(test, chosen)])[:, -1]
                           if len(classes) == 2 else None)
            return model.predict(matrix[np.ix_(test, chosen)]), probability

        def module_model(matrix, y, train, test, k, group_of=None):
            fit = modules(matrix[train], y[train])
            train_design = module_design(matrix[train], fit)
            test_design = module_design(matrix[test], fit)
            model = Pipeline([("scale", StandardScaler()),
                              ("model", LogisticRegression(C=0.3, max_iter=5000,
                                                           random_state=SEED))])
            model.fit(train_design, y[train])
            probability = (model.predict_proba(test_design)[:, -1]
                           if len(classes) == 2 else None)
            return model.predict(test_design), probability

        candidates = {}
        for name, function in (("shipped", shipped), ("sparse", sparse),
                               ("linear_svm", svm), ("shallow_25genes", shallow),
                               ("coexpression_modules", module_model),
                               ("auto_selected_nested", auto_selected)):
            AUTO_TRACE.clear()
            result = evaluate(name, function, expression, labels, groups)
            if name == "auto_selected_nested":
                tally = {config: AUTO_TRACE.count(config) for config in set(AUTO_TRACE)}
                result["configurationsChosenInsideFolds"] = {
                    "perFold": AUTO_TRACE, "tally": tally,
                    "note": ("which (gene count, learner) pair the inner loop picked for "
                             "each held-out group. A preponderance of one configuration "
                             "means the inner loop is stable; a spread means the outer "
                             "score is averaging over disagreement."),
                }
            result["permutation"] = permutation_p(result["prediction"], labels, groups)
            if len(classes) == 2:
                result["calibration"] = calibration(result["probabilities"], labels)
            result.pop("probabilities")
            candidates[name] = result
            print(f"  {name:22s} balanced {result['balancedAccuracy']:.3f} "
                  f"macroF1 {result['macroF1']:.3f} p={result['permutation']['pCorrected']} "
                  f"sd {result['foldBalancedAccuracySd']:.3f}")

        # Paired comparison against the shipped candidate, per group.
        baseline = candidates["shipped"]
        for name, result in candidates.items():
            if name == "shipped":
                continue
            wins = losses = ties = 0
            for group in sorted(set(groups)):
                mask = groups == group
                base = balanced_accuracy_score(labels[mask], baseline["prediction"][mask])
                other = balanced_accuracy_score(labels[mask], result["prediction"][mask])
                if other > base:
                    wins += 1
                elif other < base:
                    losses += 1
                else:
                    ties += 1
            result["perGroupVersusShipped"] = {"wins": wins, "losses": losses, "ties": ties}
            delta = result["balancedAccuracy"] - baseline["balancedAccuracy"]
            promoted = (delta >= PROMOTION_MARGIN and wins > (wins + losses) / 2
                        and result["permutation"]["pCorrected"] < 0.05)
            result["deltaVersusShipped"] = round(delta, 4)
            result["meetsPromotionBar"] = bool(promoted)
            result["promotionDecision"] = (
                "promote" if promoted else
                "rejected: below the 0.02 balanced-accuracy margin" if delta < PROMOTION_MARGIN
                else "rejected: did not win on more than half of the groups")

        phase9 = safedata.load(ROOT / "ml" / "evaluation" / "phase9_osd46_radiation")["tasks"]
        key = "quality" if model_id == "radiation-quality-osd46-v1" else "exposure"
        committed = round(phase9[key]["learners"]["logistic_l2"]["balancedAccuracy"], 4)
        reproduced = baseline["balancedAccuracy"]
        fidelity = {
            "phase9CommittedBalancedAccuracy": committed,
            "phase11ReproducedBalancedAccuracy": reproduced,
            "difference": round(reproduced - committed, 4),
            "verdict": ("reproduced" if abs(reproduced - committed) < 5e-4
                        else "not-reproduced"),
            "note": ("The shipped row must reproduce the committed Phase 9 number before "
                      "any candidate is compared against it; a lookalike baseline makes "
                      "every delta meaningless."),
        }
        print(f"  fidelity vs phase 9: {reproduced:.4f} vs {committed:.4f} "
              f"-> {fidelity['verdict']}")

        nested = candidates["auto_selected_nested"]
        nested_decision = {
            "nestedBalancedAccuracy": nested["balancedAccuracy"],
            "shippedBalancedAccuracy": baseline["balancedAccuracy"],
            "deltaVersusShipped": round(nested["balancedAccuracy"]
                                        - baseline["balancedAccuracy"], 4),
            "beatsShippedAtTheNestedLevel": bool(
                nested["balancedAccuracy"] - baseline["balancedAccuracy"] >= PROMOTION_MARGIN),
            "statement": (
                "Choosing the configuration inside each outer fold does not beat the "
                "shipped model, so the fixed-k gains below are attributed to comparing "
                "six candidates on the same 22 folds rather than to a better learner."
                if nested["balancedAccuracy"] - baseline["balancedAccuracy"] < PROMOTION_MARGIN
                else "The nested pipeline beats the shipped model on its own."),
        }
        for name, result in candidates.items():
            if name in ("shipped", "auto_selected_nested"):
                continue
            if result["meetsPromotionBar"]:
                result["promotionDecision"] = (
                    "rejected: meets the fixed-k bar but the nested re-selection does not "
                    "reproduce it, so the gain is a selection effect")
                result["meetsPromotionBar"] = False

        winner = max(candidates, key=lambda name: candidates[name]["balancedAccuracy"])
        report["models"][model_id] = {
            "arrays": int(expression.shape[0]),
            "groups": int(len(set(groups))),
            "classes": classes,
            "candidates": {name: {key: value for key, value in result.items()
                                  if key != "prediction"}
                           for name, result in candidates.items()},
            "fidelity": fidelity,
            "nestedSelection": nested_decision,
            "bestCandidate": winner,
            "shippedBalancedAccuracy": baseline["balancedAccuracy"],
            "shippedPermutationP": baseline["permutation"]["pCorrected"],
            "anyPromoted": bool(nested_decision["beatsShippedAtTheNestedLevel"]),
            "promotionBasis": "auto_selected_nested only (fixed-k rows are exploratory)",
            "registryChange": None,
        }

    report["protocol"] = {
        "outerLoop": "leave-one-biological-group-out, 22 folds",
        "selection": "ANOVA on training rows only, inside each outer fold",
        "hyperparameters": "fixed a priori; no inner search, so nothing is tuned on test",
        "promotionRule": ("beat the shipped model by 0.02 balanced accuracy, win on more "
                          "than half the groups, and keep permutation p below 0.05"),
        "whySoStrict": ("44 arrays over 22 groups; 0.02 balanced accuracy is about one "
                        "array, so a smaller margin is noise with a number attached"),
        "candidateSelectionTrap": ("five configurations compared on the same 22 folds "
                                    "makes the best-looking row optimistic. "
                                    "auto_selected_nested redoes the choice of "
                                    "configuration inside every outer fold, so it is the "
                                    "only row whose score is not inflated by our having "
                                    "picked the winner ourselves"),
    }
    report["verdict"] = (
        "no-candidate-meets-the-promotion-bar"
        if not any(model["anyPromoted"] for model in report["models"].values())
        else "candidate-meets-the-promotion-bar")
    safedata.dump(report, OUT)
    print(f"\nverdict: {report['verdict']} -> wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
