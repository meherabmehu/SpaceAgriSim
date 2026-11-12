"""Phase 10: replicate the OSD-314 partial-gravity result in OSD-346.

OSD-314 gave 0 g versus 0.34 g at balanced accuracy 1.000 (p = 0.0055) inside flight,
on 11 libraries in one genotype, in two folds. That is a single experiment, and a single
experiment is not a fact about plant transcriptomes. OSD-346 is the independent test:

  * a different mission, a different genotype (phytochrome mutants, not wild type)
  * **six commanded gravity levels from 0 to 1 g**, in orbit throughout
  * two light treatments per genotype, each carrying the full gravity series

Because every sample is a flight sample, OSD-346 has **no flight-versus-ground
confound** at any gravity level - which OSD-314 could not avoid, since its 1 g samples
were ground controls. And because each light treatment contains the whole series, the
honest split (train on one treatment, test on the other) removes no gravity level.

Three questions, each with the protocol declared before the run:

  P1  does 0 g separate from partial gravity (0.25-0.38 g) for an unseen light
      treatment, as it did in OSD-314?          -> replication of the headline result
  P2  is gravity recoverable as a graded quantity across 0-1 g?    -> the stronger claim
  P3  does a phyA-trained classifier transfer to phyB?             -> cross-genotype

Selection and fitting reuse `phase10_partial_gravity_osd314.fit_fold`, so there is one
code path, one feature-selection rule and one in-sample self-check for both studies.
"""

from __future__ import annotations
import sys

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import Ridge
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from phase10_partial_gravity_osd314 import fit_fold, select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
PROCESSED = ROOT / "data" / "processed"
DERIVED = ROOT / "data" / "derived"
OUT = ROOT / "ml" / "evaluation" / "phase10_partial_gravity_replication"

SEED = 346
PERMUTATIONS = 2000
LOW_PARTIAL = (0.25, 0.38)   # the range that matches OSD-314's 0.34 g


def load():
    expression = pd.read_csv(DERIVED / "osd346_partial_gravity.csv")
    genes = expression["gene"].tolist()
    matrix = expression.drop(columns=["gene"]).to_numpy(float).T
    design = pd.read_csv(PROCESSED / "osd346_samples.csv")
    return matrix, genes, design


def perm_test(labels, prediction, strata, permutations=PERMUTATIONS, seed=SEED):
    generator = np.random.default_rng(seed)
    observed = float(balanced_accuracy_score(labels, prediction))
    null = np.empty(permutations)
    for index in range(permutations):
        shuffled = labels.copy()
        for level in np.unique(strata):
            rows = np.flatnonzero(strata == level)
            shuffled[rows] = generator.permutation(shuffled[rows])
        null[index] = balanced_accuracy_score(shuffled, prediction)
    exceed = int((null >= observed).sum())
    degenerate = bool(np.ptp(null) < 1e-12)
    return {
        "observed": round(observed, 4),
        "nullMedian": round(float(np.median(null)), 4),
        "degenerate": degenerate,
        "degenerateMeaning": (
            "Every permutation returns the same score, which happens when the model "
            "predicts a single class: the null is a point mass and this p-value carries "
            "no information. It must not be read as 'no effect'."
            if degenerate else None),
        "null95": [round(float(np.percentile(null, 2.5)), 4),
                   round(float(np.percentile(null, 97.5)), 4)],
        "permutations": permutations,
        "exceedances": exceed,
        "pCorrected": round((exceed + 1) / (permutations + 1), 5),
    }


def correlation_perm_test(truth, predicted, strata, permutations=PERMUTATIONS, seed=SEED):
    generator = np.random.default_rng(seed)
    observed = float(stats.spearmanr(truth, predicted).statistic)
    null = np.empty(permutations)
    for index in range(permutations):
        shuffled = truth.copy()
        for level in np.unique(strata):
            rows = np.flatnonzero(strata == level)
            shuffled[rows] = generator.permutation(shuffled[rows])
        null[index] = float(stats.spearmanr(shuffled, predicted).statistic)
    exceed = int((null >= observed).sum())
    return {
        "observedSpearman": round(observed, 4),
        "nullMedian": round(float(np.median(null)), 4),
        "null95": [round(float(np.percentile(null, 2.5)), 4),
                   round(float(np.percentile(null, 97.5)), 4)],
        "permutations": permutations,
        "exceedances": exceed,
        "pCorrected": round((exceed + 1) / (permutations + 1), 5),
    }


def held_out_light_treatment(expression, labels, treatments, k=100):
    """Train on one light treatment, predict the other. The OSD-314 protocol."""
    prediction = np.empty(len(labels), dtype=object)
    for train_index, test_index in LeaveOneGroupOut().split(expression, labels, treatments):
        assert not set(treatments[train_index]) & set(treatments[test_index])
        prediction[test_index] = fit_fold(expression, labels, train_index, test_index, k)
    return prediction


def held_out_light_regression(expression, gravity, treatments, k=100):
    prediction = np.empty(len(gravity))
    for train_index, test_index in LeaveOneGroupOut().split(expression, gravity, treatments):
        chosen = select(expression[train_index], np.array(
            [f"{g:.2f}" for g in gravity[train_index]]), k)
        model = Pipeline([("scale", StandardScaler()), ("model", Ridge(alpha=1.0))])
        model.fit(expression[np.ix_(train_index, chosen)], gravity[train_index])
        prediction[test_index] = model.predict(expression[np.ix_(test_index, chosen)])
    return prediction


def main() -> int:
    expression, genes, design = load()
    print(f"OSD-346: {expression.shape[0]} libraries x {expression.shape[1]} genes")
    print(pd.crosstab(design["genotypeShort"], design["lightTreatment"]).to_string())

    phya = design["genotypeShort"].to_numpy() == "phyA"
    phyb = ~phya
    gravity = design["gravityG"].to_numpy(float)
    commanded = design["gravityCommandedG"].to_numpy(float)
    treatments = design["lightTreatment"].to_numpy()
    genotype = design["genotypeShort"].to_numpy()

    # --- P1: 0 g versus partial gravity, phyA, unseen light treatment ---------
    partial = (commanded >= LOW_PARTIAL[0]) & (commanded <= LOW_PARTIAL[1])
    zero = np.isclose(commanded, 0.0)
    subset = phya & (partial | zero)
    labels = np.where(zero[subset], "microgravity", "partial")
    fold_labels = treatments[subset]
    p1_prediction = held_out_light_treatment(expression[subset], labels, fold_labels)
    p1 = {
        "scheme": "phyA, 0 g versus 0.25-0.38 g, train on one light treatment and test "
                  "on the other",
        "libraries": int(subset.sum()),
        "counts": {str(k): int(v) for k, v in zip(*np.unique(labels, return_counts=True))},
        "accuracy": round(float((p1_prediction == labels).mean()), 4),
        "balancedAccuracy": round(float(balanced_accuracy_score(labels, p1_prediction)), 4),
        "recallMicrogravity": round(float((p1_prediction[labels == "microgravity"]
                                           == "microgravity").mean()), 4),
        "recallPartial": round(float((p1_prediction[labels == "partial"]
                                      == "partial").mean()), 4),
        "predictedClassCounts": {str(k): int(v) for k, v in
                                 zip(*np.unique(p1_prediction, return_counts=True))},
        "collapsedToSingleClass": bool(len(set(p1_prediction)) == 1),
        "permutation": perm_test(labels, p1_prediction, fold_labels),
        "powerNote": (
            "ten libraries over two folds. A binary classifier on 100 selected genes has "
            "very little room here, so a failure to replicate is underpowered evidence, "
            "not proof that the OSD-314 signal is absent."),
    }

    # --- P1b: the same contrast at the lowest partial level (0 g vs 0.1 g) ----
    low = np.isclose(commanded, 0.1)
    subset_low = phya & (low | zero)
    labels_low = np.where(zero[subset_low], "microgravity", "low-partial-0.1g")
    low_perm = perm_test(labels_low,
                         held_out_light_treatment(expression[subset_low], labels_low,
                                                  treatments[subset_low]),
                         treatments[subset_low])
    p1b = {"scheme": "phyA, 0 g versus 0.1 g, held-out light treatment",
           "libraries": int(subset_low.sum()),
           "balancedAccuracy": low_perm["observed"],
           "permutation": low_perm}

    # --- P1c: 0 g versus every partial level, and a graded-model readout ------
    # A binary classifier that collapses tells us about power, not about biology. These
    # two views use more libraries and a continuous prediction instead.
    wider = phya & ((commanded >= 0.1) & (commanded <= 0.38) | zero)
    labels_wider = np.where(zero[wider], "microgravity", "partial")
    wider_prediction = held_out_light_treatment(expression[wider], labels_wider,
                                                 treatments[wider])
    wider_perm = perm_test(labels_wider, wider_prediction, treatments[wider])
    p1c = {
        "scheme": "phyA, 0 g versus 0.1-0.38 g (all partial levels), held-out light "
                  "treatment",
        "libraries": int(wider.sum()),
        "balancedAccuracy": wider_perm["observed"],
        "predictedClassCounts": {str(k): int(v) for k, v in
                                 zip(*np.unique(wider_prediction, return_counts=True))},
        "permutation": wider_perm,
    }

    # --- P2: gravity as a graded quantity across 0-1 g -----------------------
    graded = phya
    graded_gravity = gravity[graded]
    graded_prediction = held_out_light_regression(expression[graded], graded_gravity,
                                                  treatments[graded])
    by_level = {}
    for level in sorted(set(commanded[graded])):
        mask = np.isclose(commanded[graded], level)
        by_level[f"{level:.2f}g"] = {
            "n": int(mask.sum()),
            "meanPredicted": round(float(graded_prediction[mask].mean()), 3),
        }
    means = [value["meanPredicted"] for value in by_level.values()]
    p2 = {
        "scheme": "phyA, ridge on real g across six commanded levels 0-1 g, held-out "
                  "light treatment",
        "libraries": int(graded.sum()),
        "correlation": correlation_perm_test(graded_gravity, graded_prediction,
                                             treatments[graded]),
        "byCommandedLevel": by_level,
        "monotoneInLevelOrder": bool(np.all(np.diff(means) > 0)),
        "meanAbsoluteErrorG": round(float(np.abs(graded_prediction - graded_gravity).mean()), 4),
    }

    # The continuous model's prediction is a less brittle readout than a binary label:
    # ask whether predicted g is higher at partial levels than at microgravity.
    zero_rows = graded & zero
    rank_view = {}
    for level in sorted({float(v) for v in commanded[graded]}):
        if level == 0.0:
            continue
        rows = graded & np.isclose(commanded, level)
        if rows.sum() < 2:
            continue
        test = stats.mannwhitneyu(graded_prediction[zero_rows[graded]],
                                  graded_prediction[rows[graded]],
                                  alternative="less")
        rank_view[f"{level:.2f}g"] = {
            "nZero": int(zero_rows.sum()), "nLevel": int(rows.sum()),
            "medianPredictedZero": round(float(np.median(
                graded_prediction[zero_rows[graded]])), 3),
            "medianPredictedLevel": round(float(np.median(
                graded_prediction[rows[graded]])), 3),
            "oneSidedP": round(float(test.pvalue), 4),
        }

    # --- P3: cross-genotype transfer, phyA -> phyB ---------------------------
    partial_any = (commanded > 0.05) & (commanded < 0.6)
    transfer_rows = partial_any | zero
    train = phya & transfer_rows
    test = phyb & transfer_rows
    labels_transfer = np.where(zero, "microgravity", "partial")
    chosen = select(expression[train], labels_transfer[train])
    from phase10_partial_gravity_osd314 import classifier

    model = classifier().fit(expression[np.ix_(train, chosen)], labels_transfer[train])
    transfer_prediction = model.predict(expression[np.ix_(test, chosen)])
    transfer_truth = labels_transfer[test]
    p3 = {
        "scheme": "train on phyA (0 g versus 0.1-0.5 g), test on phyB, no phyB rows "
                  "seen in training",
        "trainLibraries": int(train.sum()),
        "testLibraries": int(test.sum()),
        "balancedAccuracy": round(float(balanced_accuracy_score(transfer_truth,
                                                                transfer_prediction)), 4),
        "recallMicrogravity": round(float((transfer_prediction[transfer_truth == "microgravity"]
                                           == "microgravity").mean()), 4),
        "recallPartial": round(float((transfer_prediction[transfer_truth == "partial"]
                                      == "partial").mean()), 4),
    }

    # --- Verdict -------------------------------------------------------------
    replicated = p1["permutation"]["pCorrected"] < 0.05 and p1["balancedAccuracy"] > 0.5
    graded_detected = (p2["correlation"]["observedSpearman"] > 0
                       and p2["correlation"]["pCorrected"] < 0.05)
    result = {
        "phase": 10,
        "study": "OSD-346 / GLDS-346",
        "task": "replicate the OSD-314 partial-gravity result in an independent study",
        "provenance": {
            "acquisition": "scripts/acquire_phase10_osd346.py",
            "checksums": "data/metadata/osd346_checksums",
            "rawCommitted": False,
            "rawNote": ("73 MB of per-sample RSEM quantifications are not committed; "
                        "their SHA-256 digests are, so the committed matrices rebuild "
                        "byte-identically."),
            "expression": "log2(TPM + 1), genes detected in at least half the libraries",
        },
        "design": {
            "genotypes": sorted(set(genotype.tolist())),
            "lightTreatments": sorted(set(treatments.tolist())),
            "commandedGravityG": sorted({float(v) for v in commanded}),
            "actualGravityRangeG": [round(float(gravity.min()), 3),
                                   round(float(gravity.max()), 3)],
            "libraries": int(len(design)),
            "allSamplesAreFlight": True,
            "noFlightConfound": (
                "Every library is a flight sample, so the whole 0-1 g series is "
                "comparable in orbit. OSD-314 could not do this: its 1 g samples were "
                "ground controls."),
            "fullSeriesInEachLightTreatment": True,
            "whyThatMatters": (
                "Holding out a light treatment removes no gravity level, so the split "
                "tests generalization rather than interpolation between missing levels."),
        },
        "P1_binaryReplication": p1,
        "P1b_lowestPartial": p1b,
        "P1c_widerContrast": p1c,
        "P2_gradedRegression": p2,
        "P2b_rankSeparationByLevel": rank_view,
        "P3_crossGenotype": p3,
        "decisionRule": (
            "The OSD-314 result replicates only if the 0 g versus partial contrast "
            "exceeds 0.5 balanced accuracy on an unseen light treatment with a "
            "design-preserving permutation p below 0.05. Graded recoverability requires "
            "a positive Spearman correlation with p below 0.05. Fixed before the run."),
        "replicated": bool(replicated),
        "gradedGravityDetected": bool(graded_detected),
        "registryChange": None,
        "notPromotedBecause": [
            "36 libraries across two genotypes and two light treatments",
            "commanded and realised gravity differ (centrifugation), so the label is a "
            "measured level, not a set point",
            "the genotypes are phytochrome mutants, so this is not wild-type physiology",
            "a servable predictor needs replication across missions, not two light "
            "treatments inside one",
        ],
    }
    safedata.dump(result, OUT)

    print(f"\nP1 0 g vs 0.25-0.38 g, held-out light treatment: balanced "
          f"{p1['balancedAccuracy']} (p={p1['permutation']['pCorrected']}), "
          f"n={p1['libraries']}")
    print(f"P1b 0 g vs 0.1 g: balanced {p1b['balancedAccuracy']} "
          f"(p={p1b['permutation']['pCorrected']})")
    print(f"P1c 0 g vs 0.1-0.38 g: balanced {p1c['balancedAccuracy']} "
          f"(p={p1c['permutation']['pCorrected']}, degenerate "
          f"{p1c['permutation']['degenerate']})")
    print(f"P2 graded 0-1 g: rho {p2['correlation']['observedSpearman']} "
          f"(p={p2['correlation']['pCorrected']}), monotone "
          f"{p2['monotoneInLevelOrder']}, MAE {p2['meanAbsoluteErrorG']} g")
    print(f"P3 phyA -> phyB transfer: balanced {p3['balancedAccuracy']}")
    print(f"replicated: {replicated}; graded detected: {graded_detected} -> "
          f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
