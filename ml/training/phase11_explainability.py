"""Phase 11: is the served explanation a property of the data or of the learner?

Phase 10 shipped per-gene importances for the radiation models and reported that 75 of 150
genes are chosen in every one of the 22 folds. Two questions were left open, and both decide
how far an explanation may be trusted:

  E1  Fold stability. "Chosen in all folds" is a claim about a 150-gene panel. What matters
      for a reader is the smaller, interpretable set: the top 40 genes. How much does that
      set move between folds, and does the gene a user sees first stay near the top?

  E2  Learner dependence. The served explanation is a logistic-regression coefficient. If a
      random forest and a gradient-boosted model rank the same genes completely differently,
      then the explanation describes the model class rather than the biology, and saying
      "this gene drives the prediction" is overreach.

Protocol: every fold is the same leave-one-biological-group-out split used for scoring, gene
selection happens on training rows only, and importance is measured by permuting a gene's
values in the *held-out* group and recording the drop in balanced accuracy. That is an
out-of-fold importance, so a gene cannot look important because the model memorised it.

Nothing here attributes causation. A gene with a high permutation drop is one whose values
the model uses; the experiment did not manipulate it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import LeaveOneGroupOut

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
sys.path.insert(0, str(ROOT / "ml" / "training"))
OUT = ROOT / "ml" / "evaluation" / "phase11_explainability"

SEED = 11900
TOP_GENES = 150
PANEL = 40
PERMUTATION_REPEATS = 5


def load(model_id: str):
    from train_radiation_osd46 import group_key, load as load_osd46

    matrix, genes, samples = load_osd46()
    labels = (samples["radiation"].to_numpy()
              if model_id == "radiation-quality-osd46-v1"
              else np.where(samples["radiation"].eq("non-irradiated"),
                            "control", "irradiated"))
    return matrix, np.asarray(genes), np.asarray(labels), group_key(samples)


def learner(name):
    from phase9_harness import classification_learners

    mapping = {"logistic_l2": "logistic_l2", "linear_svm": "logistic_l2",
               "random_forest": "random_forest",
               "hist_gradient_boosting": "hist_gradient_boosting"}
    if name == "linear_svm":
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.svm import LinearSVC
        return Pipeline([("scale", StandardScaler()),
                         ("model", LinearSVC(C=0.05, max_iter=20000, random_state=SEED))])
    return classification_learners()[mapping[name]]()


def out_of_fold_importance(matrix, labels, groups, model_name, panel_genes, repeats=PERMUTATION_REPEATS):
    """Drop in held-out balanced accuracy when each panel gene is permuted."""
    from phase9_harness import select_features

    generator = np.random.default_rng(SEED)
    drops = np.zeros(panel_genes.size)
    baseline_scores = []
    for train, test in LeaveOneGroupOut().split(matrix, labels, groups):
        chosen = select_features(matrix[train], labels[train], n_features=TOP_GENES)
        model = learner(model_name)
        model.fit(matrix[np.ix_(train, chosen)], labels[train])
        baseline = balanced_accuracy_score(labels[test],
                                           model.predict(matrix[np.ix_(test, chosen)]))
        baseline_scores.append(baseline)
        for position, gene in enumerate(panel_genes):
            column = int(np.flatnonzero(chosen == gene)[0]) if (chosen == gene).any() else None
            if column is None:
                continue
            for _ in range(repeats):
                shuffled = matrix[np.ix_(test, chosen)].copy()
                shuffled[:, column] = generator.permutation(shuffled[:, column])
                score = balanced_accuracy_score(labels[test], model.predict(shuffled))
                drops[position] += (baseline - score) / repeats
    return drops / len(baseline_scores), float(np.mean(baseline_scores))


def fold_stability(matrix, genes, labels, groups):
    """How much the interpretable top-40 panel moves between folds."""
    from phase9_harness import select_features

    deployed = select_features(matrix, labels, n_features=TOP_GENES)
    deployed_panel = set(deployed[:PANEL].tolist())
    jaccards, first_gene_hits, panels = [], [], []
    for train, _ in LeaveOneGroupOut().split(matrix, labels, groups):
        chosen = select_features(matrix[train], labels[train], n_features=TOP_GENES)
        panel = set(chosen[:PANEL].tolist())
        panels.append(panel)
        jaccards.append(len(panel & deployed_panel) / len(panel | deployed_panel))
        first_gene_hits.append(int(deployed[0]) in panel)
    frequency = {}
    for panel in panels:
        for gene in panel:
            frequency[genes[gene]] = frequency.get(genes[gene], 0) + 1
    stable = sorted(frequency.items(), key=lambda item: -item[1])[:15]
    return {
        "deployedPanelSize": PANEL,
        "meanJaccardVsDeployedPanel": round(float(np.mean(jaccards)), 4),
        "minJaccard": round(float(np.min(jaccards)), 4),
        "maxJaccard": round(float(np.max(jaccards)), 4),
        "foldCount": len(jaccards),
        "topGeneInPanelFraction": round(float(np.mean(first_gene_hits)), 3),
        "genesInEveryFoldPanel": int(sum(1 for _, count in frequency.items()
                                         if count == len(panels))),
        "genesInPanel": int(len(frequency)),
        "mostFrequentGenes": [{"gene": gene, "folds": count} for gene, count in stable],
        "interpretation": ("A Jaccard near 1 means the short panel a user reads is stable "
                           "across resampling; near 0 means the top of the list is noise. "
                           "Neither says anything about causation."),
    }


def main() -> int:
    report = {"phase": 11, "seed": SEED, "panelSize": PANEL,
              "importanceProtocol": ("held-out permutation of each panel gene, averaged "
                                     "over 22 group-held-out folds and 5 shuffles"),
              "models": {}}

    for model_id in ("radiation-quality-osd46-v1", "radiation-exposure-osd46-v1"):
        matrix, genes, labels, groups = load(model_id)
        print(f"\n{model_id}: {matrix.shape[0]} x {matrix.shape[1]}")
        stability = fold_stability(matrix, genes, labels, groups)
        print(f"  E1 panel Jaccard vs deployed {stability['meanJaccardVsDeployedPanel']:.3f}, "
              f"top gene in {stability['topGeneInPanelFraction']:.1%} of folds")

        from phase9_harness import select_features
        deployed = select_features(matrix, labels, n_features=TOP_GENES)
        panel = deployed[:PANEL]

        importances, baselines = {}, {}
        for model_name in ("logistic_l2", "linear_svm", "random_forest",
                           "hist_gradient_boosting"):
            drops, baseline = out_of_fold_importance(matrix, labels, groups, model_name, panel)
            importances[model_name] = drops
            baselines[model_name] = round(baseline, 4)
            top = [genes[panel[i]] for i in np.argsort(-drops)[:5]]
            print(f"  E2 {model_name:22s} baseline {baseline:.3f} top5 {', '.join(top)}")

        # A pairwise Spearman is undefined when either vector is constant, and a
        # constant importance vector is itself a finding: it means permuting any single
        # panel gene left the held-out prediction unchanged.
        agreement, top5, top10 = {}, {}, {}
        names = list(importances)
        for i, left in enumerate(names):
            for right in names[i + 1:]:
                key = f"{left}~{right}"
                if np.ptp(importances[left]) == 0 or np.ptp(importances[right]) == 0:
                    agreement[key] = None
                else:
                    agreement[key] = round(float(stats.spearmanr(importances[left],
                                                                 importances[right]).statistic), 3)
                for k, bucket in ((5, top5), (10, top10)):
                    left_top = {genes[panel[i2]] for i2 in np.argsort(-importances[left])[:k]}
                    right_top = {genes[panel[i2]] for i2 in np.argsort(-importances[right])[:k]}
                    bucket[key] = round(len(left_top & right_top) / k, 2)

        defined = [value for value in agreement.values() if value is not None]
        mean_rho = float(np.mean(defined)) if defined else None
        mean_top5 = float(np.mean(list(top5.values())))
        informative = [name for name in names if np.ptp(importances[name]) > 0]
        zero_drop = {name: round(float((importances[name] == 0).mean()), 3) for name in names}
        report["models"][model_id] = {
            "arrays": int(matrix.shape[0]),
            "groups": int(len(set(groups))),
            "E1_foldStability": stability,
            "E2_learnerAgreement": {
                "spearmanBetweenImportanceVectors": agreement,
                "pairsWithDefinedSpearman": f"{len(defined)}/{len(agreement)}",
                "meanSpearman": None if mean_rho is None else round(mean_rho, 3),
                "top5Overlap": top5,
                "top10Overlap": top10,
                "meanTop5Overlap": round(mean_top5, 3),
                "zeroDropFractionPerLearner": zero_drop,
                "learnersWithNonZeroImportance": informative,
                "baselineBalancedAccuracy": baselines,
                "topGenesPerLearner": {
                    name: [genes[panel[i]] for i in np.argsort(-importances[name])[:10]]
                    for name in importances},
                "verdict": (
                    "not-comparable-by-single-gene-permutation" if mean_rho is None else
                    ("agrees-at-the-top-only" if mean_top5 >= 0.6 else "learner-dependent")),
                "consequence": (
                    "no single panel gene is individually necessary: permuting any one of "
                    "them leaves the held-out prediction unchanged, which is what a "
                    "distributed signature looks like. Attribution must be reported as a "
                    "set, never as a rank-1 driver."
                    if mean_rho is None else
                    ("the first few genes agree across model classes while the rest of "
                     "the panel does not, so a short list is defensible and a long ranked "
                     "table is not" if mean_top5 >= 0.6 else
                     "the ranking changes with the learner, so the served explanation "
                     "must stay tied to the served model class and cannot be presented as "
                     "the study's biology")),
            },
            "causationClaim": False,
            "note": ("Permutation importance measures what the fitted model uses, out of "
                     "fold. It is an attribution, not an intervention, and the platform "
                     "must not describe a high-ranked gene as a cause."),
        }

    verdicts = {model["E2_learnerAgreement"]["verdict"]
                for model in report["models"].values()}
    report["summary"] = {
        "learnerDependence": sorted(verdicts),
        "registryChange": None,
        "statement": ("explanation stability is reported for the first time; where the "
                      "ranking is learner-dependent the served explanation is scoped to "
                      "the served model and no biological claim is attached to a gene "
                      "rank"),
    }
    safedata.dump(report, OUT)
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
