"""Phase 9 Models B/C/D: RNA-seq candidates from OSD-782 and OSD-411.

This script trains the candidates the brief asks for and lets a pre-specified,
leakage-free evaluation decide whether any of them may be shipped. Three of the
four results here are negative. They are reported as negatives and no artifact is
written for them, because a model that cannot beat a majority baseline on
held-out biological units has no predictive claim to make.

B  radiation dose from OSD-782        3 classes: 0 / 10 / 100 Gy
C  gravity reorientation from OSD-411 2 classes: Reoriented / Vertical control
D  cross-study transfer                OSD-46 (microarray) -> OSD-782 (RNA-seq)

Unit definitions, taken from the ISA sample sheets rather than assumed
---------------------------------------------------------------------
OSD-782  36 rosette samples, Col-0, 3 doses x 4 collection times x 3 biological
         replicates. The independent unit is the (dose, time) cell: 12 groups.
OSD-411  64 samples described by the sample names 1-1 ... 16-4. The prefix is a
         **seedling** and the suffix is one of four tissues, so four rows come from
         one seedling. Treating those 64 rows as 64 independent observations is the
         classic pseudo-replication error. The independent unit is the seedling:
         16 groups of 4 tissues.

Quantification
--------------
OSD-782 uses GeneLab's variance-stabilising-transformed counts (the provider's own
processed product). OSD-411 publishes only RSEM raw counts, so it is converted with
log2(CPM + 1), computed within the study and without reference to any label.

Run: python ml/training/train_rnaseq_models.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "ml" / "training"))
from nasa_pipeline import save_json  # noqa: E402
import phase9_harness as H  # noqa: E402

RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
EVAL = ROOT / "ml" / "evaluation"

MIN_LIBRARY_READS = 5_000_000
# Populated by load_osd411 so the evidence file can state exactly what was removed.
LOW_LIBRARY_EXCLUSIONS: list[dict] = []


def load_osd782() -> tuple[np.ndarray, list[str], pd.DataFrame]:
    """GeneLab VST counts, 36 rosettes x genes."""
    frame = pd.read_csv(
        RAW / "OSD-782" / "GLDS-679_rna_seq_VST_Counts_GLbulkRNAseq.csv")
    samples = [c for c in frame.columns if c.startswith("GSM")]
    matrix = frame.set_index(frame.columns[0])[samples].astype(float)
    annotation = pd.read_csv(PROCESSED / "osd782_radiation_samples.csv", dtype=str)
    annotation = annotation.set_index("sample").loc[samples].reset_index()
    return matrix.to_numpy(dtype=float).T, list(matrix.index), annotation


def load_osd411() -> tuple[np.ndarray, list[str], pd.DataFrame]:
    """RSEM raw counts -> log2(CPM + 1), 64 samples x genes."""
    frame = pd.read_csv(
        RAW / "OSD-411" / "GLDS-411_rna_seq_RSEM_Unnormalized_Counts_GLbulkRNAseq.csv")
    samples = [c for c in frame.columns if c.startswith("GSM")] or \
              [c for c in frame.columns[1:]]
    counts = frame.set_index(frame.columns[0])[samples].astype(float)
    library = counts.sum(axis=0)
    # One library in this study is ~130x shallower than the rest (sample 14-4,
    # 258k reads against a median near 33M). Dropping it is a recorded QC decision,
    # not a silent filter: the exclusion is written to the evidence file.
    keep = library[library >= MIN_LIBRARY_READS].index.tolist()
    LOW_LIBRARY_EXCLUSIONS.extend(
        {"sample": name, "reads": float(library[name])}
        for name in library[library < MIN_LIBRARY_READS].index)
    counts = counts[keep]
    library = library[keep]
    cpm = counts.div(library, axis=1) * 1_000_000
    expression = np.log2(cpm + 1)
    annotation = pd.read_csv(PROCESSED / "osd411_gravity_samples.csv", dtype=str)
    annotation = annotation.set_index("sample").loc[keep].reset_index()
    return expression.to_numpy(dtype=float).T, list(expression.index), annotation


def report_task(name: str, model_id: str, matrix, labels, groups,
                description: str) -> dict:
    print(f"\n== {model_id}: {description}")
    print(f"   {matrix.shape[0]} samples x {matrix.shape[1]} genes, "
          f"{len(np.unique(groups))} groups, classes "
          f"{dict(pd.Series(labels).value_counts())}")
    learners = H.evaluate_all_learners(matrix, labels, groups)
    for learner, score in learners.items():
        print(f"   {learner:26s} acc {score['accuracy']:.3f}  "
              f"bal {score['balancedAccuracy']:.3f}  f1 {score['macroF1']:.3f}")

    baseline = learners["baseline_majority"]["balancedAccuracy"]
    best_name = max((n for n in learners if n != "baseline_majority"),
                    key=lambda n: learners[n]["balancedAccuracy"])
    best = learners[best_name]
    permutation = H.permutation_test(
        matrix, labels, groups, H.classification_learners()[best_name],
        best["balancedAccuracy"], n_permutations=100)
    verdict = ("insufficient-evidence"
               if best["balancedAccuracy"] <= baseline + 0.05
               or permutation["pValue"] > 0.05
               else "candidate")
    print(f"   best={best_name} bal={best['balancedAccuracy']:.3f} vs baseline "
          f"{baseline:.3f}, p={permutation['pValue']:.4f} -> {verdict}")
    return {
        "task": name,
        "modelId": model_id,
        "description": description,
        "samples": int(matrix.shape[0]),
        "genes": int(matrix.shape[1]),
        "groups": int(len(np.unique(groups))),
        "classCounts": {str(k): int(v) for k, v in pd.Series(labels).value_counts().items()},
        "learners": learners,
        "bestLearner": best_name,
        "baselineBalancedAccuracy": baseline,
        "permutation": permutation,
        "verdict": verdict,
    }


def cross_study() -> dict:
    """D: does an OSD-46 microarray classifier transfer to OSD-782 RNA-seq?

    Both studies are Arabidopsis thaliana and both use TAIR gene models, so the
    feature spaces can be intersected. Platforms and ecotypes differ (Ws on ATH1
    versus Col-0 on Illumina), which is exactly the difficulty being measured.

    Each study is standardised per gene on its own samples. That step uses no
    labels, so it cannot leak, and it is necessary because raw microarray log2
    intensities and VST counts are not on a comparable scale.

    Balanced accuracy is the metric that matters here: the test set is 12 control
    and 24 irradiated, so a classifier that always answers "irradiated" scores
    0.667 raw accuracy while being completely uninformative.
    """
    a_matrix, a_genes, a_annotation = load_reference_osd46()
    b_matrix, b_genes, b_annotation = load_osd782()

    shared = sorted(set(a_genes) & set(b_genes))
    a_index = [a_genes.index(g) for g in shared]
    b_index = [b_genes.index(g) for g in shared]
    a = a_matrix[:, a_index]
    b = b_matrix[:, b_index]

    def zscore(matrix):
        mean = matrix.mean(axis=0)
        sd = matrix.std(axis=0, ddof=1)
        sd[sd == 0] = 1.0
        return (matrix - mean) / sd

    a, b = zscore(a), zscore(b)
    a_labels = np.where(a_annotation["radiation"] == "non-irradiated",
                        "control", "irradiated")
    b_labels = np.where(b_annotation["ionizingRadiation"] == "non-irradiated",
                        "control", "irradiated")

    # Select genes on the training study only, using in-study ANOVA.
    chosen = H.select_features(a, a_labels, n_features=500,
                               variance_preselection=False)
    model = H.classification_learners()["logistic_l2"]()
    model.fit(a[:, chosen], a_labels)
    predicted = model.predict(b[:, chosen])

    from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix
    result = {
        "task": "cross-study transfer, irradiated vs control",
        "trainStudy": "OSD-46 (Affymetrix ATH1, Wild Type + atm-1)",
        "testStudy": "OSD-782 (Illumina RNA-seq, Col-0)",
        "sharedGenes": len(shared),
        "genesUsed": int(len(chosen)),
        "trainSamples": int(len(a_labels)),
        "testSamples": int(len(b_labels)),
        "harmonisation": "per-gene z-score within each study (no labels used)",
        "accuracy": float(accuracy_score(b_labels, predicted)),
        "balancedAccuracy": float(balanced_accuracy_score(b_labels, predicted)),
        "confusionMatrix": confusion_matrix(
            b_labels, predicted, labels=["control", "irradiated"]).tolist(),
        "classLabels": ["control", "irradiated"],
        "predictionDistribution": {str(k): int(v)
                                   for k, v in pd.Series(predicted).value_counts().items()},
        "majorityClassRate": float(max(pd.Series(b_labels).value_counts()) / len(b_labels)),
    }
    collapsed = set(result["predictionDistribution"]) == {"irradiated"}
    result["verdict"] = ("transfer-failed-collapsed-to-majority" if collapsed
                         else "transfers-with-signal" if result["balancedAccuracy"] > 0.7
                         else "transfer-weak")
    result["interpretation"] = (
        "Raw accuracy looks respectable because the test set is majority "
        "irradiated, but balanced accuracy of 0.5 with a single predicted class "
        "means the classifier learned nothing transferable. Reporting the accuracy "
        "alone would have been a false positive."
        if collapsed else
        "The classifier predicts both classes on the held-out study.")
    print(f"\n== cross-study transfer: {len(shared)} shared genes, "
          f"{len(chosen)} used")
    print(f"   acc {result['accuracy']:.3f}  bal {result['balancedAccuracy']:.3f}  "
          f"predicted {result['predictionDistribution']} -> {result['verdict']}")
    return result


def load_reference_osd46():
    from train_radiation_osd46 import load
    return load()


def main() -> int:
    results = []

    b_matrix, b_genes, b_annotation = load_osd782()
    b_groups = (b_annotation["absorbedDoseGy"].astype(str) + "|"
                + b_annotation["hoursAfterTreatment"].astype(str)).to_numpy()
    b_labels = (b_annotation["absorbedDoseGy"].astype(str) + " Gy").to_numpy()
    results.append(report_task(
        "B", "radiation-dose-osd782-v1", b_matrix, b_labels, b_groups,
        "absorbed dose (0 / 10 / 100 Gy) from Arabidopsis rosette RNA-seq"))

    c_matrix, c_genes, c_annotation = load_osd411()
    seedling = c_annotation["sample"].str.split("-").str[0]
    c_groups = (c_annotation["genotype"].astype(str) + "|"
                + c_annotation["treatment"].astype(str) + "|" + seedling).to_numpy()
    c_labels = np.where(c_annotation["treatment"].str.lower().str.startswith("reorient"),
                        "reoriented", "vertical")
    results.append(report_task(
        "C", "gravity-reorientation-osd411-v1", c_matrix, c_labels, c_groups,
        "90-degree reorientation vs vertical control, grouped by seedling"))

    results.append(cross_study())

    payload = {
        "phase": 9,
        "seed": H.SEED,
        "unitDefinitions": {
            "OSD-782": ("independent unit = (dose, collection time) cell, 12 groups; "
                        "the 3 replicates within a cell are biological replicates"),
            "OSD-411": ("independent unit = seedling, derived from the sample-name "
                        "prefix 1..16; the four tissues of a seedling are repeated "
                        "measures and are never split across folds"),
        },
        "quantification": {
            "OSD-782": "GeneLab VST counts (provider processed)",
            "OSD-411": f"log2(CPM + 1) from RSEM raw counts, min library {MIN_LIBRARY_READS:,} reads",
        },
        "qcExclusions": {
            "OSD-411": {
                "rule": f"library size below {MIN_LIBRARY_READS:,} reads",
                "dropped": LOW_LIBRARY_EXCLUSIONS,
                "note": ("A library two orders of magnitude shallower than the rest "
                         "yields unreliable relative abundances. Removed before any "
                         "label was inspected, and the removal is recorded here."),
            }
        },
        "results": results,
    }
    EVAL.mkdir(parents=True, exist_ok=True)
    save_json(EVAL / "phase9_rnaseq_candidates.json", payload)
    shippable = [r for r in results if r.get("verdict") == "candidate"]
    print(f"\nwrote ml/evaluation/phase9_rnaseq_candidates.json")
    print(f"shippable candidates: {[r['modelId'] for r in shippable] or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
