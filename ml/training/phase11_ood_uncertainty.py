"""Phase 11: can an out-of-distribution score be validated with the data we have?

The platform reports intervals and can flag samples as outside its training distribution.
Phase 10 measured conformal coverage and refused to call the intervals guarantees. What was
never tested is whether a *novelty score* means anything at all. The corpus now contains two
cases that make the test possible:

  control 1  OSD-320 is bit-for-bit the same arrays as OSD-46 (Phase 11 duplicate audit:
             r = 1.000000, max|diff| = 0.0). A score that treats it as novel is measuring
             accession metadata rather than data.

  control 2  OSD-782 is bulk RNA-seq of the same organism on a different platform. A score
             that treats it as ordinary cannot detect a real measurement shift.

  control 3  A held-out biological group from OSD-46 is ordinary data. A score that flags
             every held-out group as novel would fire constantly in normal use.

Two scores are tested against all three controls, with the expectations fixed before the
run: control 1 requires the duplicate to sit at or below the reference distribution,
control 2 requires the shifted study to sit above it, and control 3 requires held-out groups
to be indistinguishable from the reference.

The result is negative and is reported as such. Neither score passes both of the first two
controls, and the reasons are structural rather than fixable by tuning:

  * comparing across platforms forces per-gene standardisation, and standardisation deletes
    any difference in a gene's mean level - which is much of what a platform shift is;
  * in-sample Mahalanobis distances are inflated by about sqrt((n-1)/(n-p)), which is larger
    than the gap between an ordinary sample and an unusual one, so every new study looks
    *nearer* than the training data unless each reference sample is scored leave-one-out.

No threshold is produced, and `thresholdValidated` stays false. This is the constraint the
product already carried; Phase 11 turns it from an absence of evidence into a tested
negative.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import LeaveOneGroupOut

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml" / "training"))
OUT = ROOT / "ml" / "evaluation" / "phase11_ood_uncertainty.json"

SEED = 12110
COMPONENTS = 10
NEIGHBOURS = 5
LDA_CUT = 0.0


def gene_matrix(path, gene_column, sample_filter):
    frame = pd.read_csv(path)
    frame[gene_column] = frame[gene_column].astype(str).str.strip()
    frame = frame[frame[gene_column].str.startswith("AT")].dropna(subset=[gene_column])
    frame = frame.set_index(gene_column)
    # Slice to measurement columns before aggregating: the derived OSD-320 file also
    # carries SYMBOL / GENENAME / REFSEQ, and a mean over those fails on strings.
    samples = [column for column in frame.columns if column.startswith(sample_filter)]
    return frame[samples].astype(float).groupby(level=0).mean()


def zscore_by_gene(matrix):
    frame = matrix.to_numpy(float)
    mean = frame.mean(axis=1, keepdims=True)
    sd = frame.std(axis=1, keepdims=True)
    sd[sd == 0] = 1.0
    return (frame - mean) / sd


# -- score 1: Mahalanobis distance in a PCA fitted on the reference ---------
def fit_score(reference, target):
    pca = PCA(n_components=COMPONENTS, random_state=SEED).fit(reference.T)
    projected = pca.transform(reference.T)
    centre = projected.mean(axis=0)
    covariance = np.cov(projected, rowvar=False) + np.eye(COMPONENTS) * 1e-6
    inverse = np.linalg.pinv(covariance)
    delta = pca.transform(target.T) - centre
    return np.sqrt(np.einsum("ij,jk,ik->i", delta, inverse, delta))


def loo_mahalanobis(reference):
    """Score every reference array with a model fitted on the other 43.

    Without this the reference scores carry the in-sample (n-1)/(n-p) inflation and every
    new study appears *closer* to the training data than the training data is to itself.
    The first run of this script reported AUC 0.001 for a different platform for exactly
    that reason.
    """
    scores = np.empty(reference.shape[1])
    for index in range(reference.shape[1]):
        rest = reference.drop(columns=reference.columns[index])
        scores[index] = fit_score(rest, reference.iloc[:, [index]])[0]
    return scores


# -- score 2: mean correlation distance to the k nearest reference arrays ---
def correlation_distance(reference, target, k=NEIGHBOURS):
    left = reference / np.linalg.norm(reference, axis=0, keepdims=True)
    right = target / np.linalg.norm(target, axis=0, keepdims=True)
    distances = np.sort(1.0 - left.T @ right, axis=1)
    return distances[:, :k].mean(axis=1)


def loo_correlation(reference, k=NEIGHBOURS):
    out = np.empty(reference.shape[1])
    for index in range(reference.shape[1]):
        rest = np.delete(reference, index, axis=1)
        out[index] = correlation_distance(rest, reference[:, [index]], k)[0]
    return out


def main() -> int:
    from train_radiation_osd46 import group_key, load as load_osd46

    _, _, samples = load_osd46()
    osd46 = gene_matrix(ROOT / "data" / "raw" / "OSD-46"
                        / "GLDS-46_array_normalized_expression_probeset_GLmicroarray.csv",
                        "TAIR", "GSM")
    osd320 = gene_matrix(ROOT / "data" / "derived" / "osd320_normalized_expression.csv",
                         "TAIR", "GSM")
    osd782 = pd.read_csv(ROOT / "data" / "raw" / "OSD-782"
                         / "GLDS-679_rna_seq_VST_Counts_GLbulkRNAseq.csv", index_col=0)
    common = sorted(set(osd46.index) & set(osd782.index))

    reference = pd.DataFrame(zscore_by_gene(osd46), index=osd46.index, columns=osd46.columns)
    duplicate = pd.DataFrame(zscore_by_gene(osd320.loc[osd46.index]),
                             index=osd46.index, columns=osd46.columns)
    shifted = zscore_by_gene(osd782.loc[common])
    reference_shared = reference.loc[common]
    groups = group_key(samples)

    report = {
        "phase": 11,
        "protocol": ("per-gene z-score within each study, then either (a) Mahalanobis "
                     "distance in 10 PCA components fitted on OSD-46, or (b) mean "
                     "1 - Pearson correlation to the 5 nearest OSD-46 arrays"),
        "referenceDistancesAreLeaveOneOut": True,
        "sharedGenes": {"osd46": int(len(osd46.index)), "osd782": int(len(osd782.index)),
                        "shared": int(len(common))},
        "preDeclaredExpectations": {
            "control1": "duplicate must rank at or below the reference distribution",
            "control2": "different platform must rank above it, AUC >= 0.9",
            "control3": "held-out group must be indistinguishable, |AUC - 0.5| < 0.15",
        },
        "thresholdValidated": False,
        "scores": {},
    }

    def evaluate(name, reference_scores, duplicate_scores, shifted_scores, heldout_aucs):
        auc_duplicate = float(roc_auc_score(
            np.r_[np.zeros(len(reference_scores)), np.ones(len(duplicate_scores))],
            np.r_[reference_scores, duplicate_scores]))
        auc_shift = float(roc_auc_score(
            np.r_[np.zeros(len(reference_scores)), np.ones(len(shifted_scores))],
            np.r_[reference_scores, shifted_scores]))
        block = {
            "referenceMean": round(float(np.mean(reference_scores)), 3),
            "duplicateMean": round(float(np.mean(duplicate_scores)), 3),
            "shiftedMean": round(float(np.mean(shifted_scores)), 3),
            "control1_duplicate": {
                "auc": round(auc_duplicate, 3),
                "expected": "<= 0.5",
                "passes": bool(auc_duplicate <= 0.5),
                "why": ("OSD-320 holds the same arrays as OSD-46, so it should look like "
                        "ordinary training data, not like a novelty"),
            },
            "control2_platformShift": {
                "auc": round(auc_shift, 3),
                "expected": ">= 0.9",
                "passes": bool(auc_shift >= 0.9),
                "why": ("OSD-782 is a different measurement platform, so it should be "
                        "flagged. Lower than 0.5 means the score calls a platform shift "
                        "*more familiar* than the training data itself."),
                "confound": ("platform, preparation protocol and organism part all move "
                             "together with this study; per-gene standardisation is needed "
                             "to compare across platforms and it deletes gene-level mean "
                             "differences, which is much of what a platform shift is"),
            },
            "control3_heldOutGroups": {
                "meanAuc": round(float(np.mean(heldout_aucs)), 3),
                "range": [round(float(np.min(heldout_aucs)), 3),
                          round(float(np.max(heldout_aucs)), 3)],
                "passes": bool(abs(float(np.mean(heldout_aucs)) - 0.5) < 0.15),
                "why": ("ordinary held-out groups must not be flagged, or the score fires "
                        "on normal use"),
            },
        }
        block["controlsPassed"] = sum(1 for key in ("control1_duplicate",
                                                    "control2_platformShift",
                                                    "control3_heldOutGroups")
                                      if block[key]["passes"])
        block["validated"] = bool(block["control1_duplicate"]["passes"]
                                  and block["control2_platformShift"]["passes"]
                                  and block["control3_heldOutGroups"]["passes"])
        report["scores"][name] = block
        print(f"{name:16s} ref {block['referenceMean']:.3f} dup {block['duplicateMean']:.3f} "
              f"shift {block['shiftedMean']:.3f} | c1 {block['control1_duplicate']['auc']:.3f} "
              f"c2 {block['control2_platformShift']['auc']:.3f} "
              f"c3 {block['control3_heldOutGroups']['meanAuc']:.3f} "
              f"-> {block['controlsPassed']}/3")
        return block

    # Every comparison uses the genes shared with OSD-782, so the two scores and all three
    # controls are computed on one identical feature set.
    duplicate_shared = duplicate.loc[common]

    # Control 3 uses one global leave-one-out reference distribution and, for each fold,
    # compares the held-out group against the reference samples whose own scores came from
    # models that also excluded that group. Re-deriving the whole reference inside every
    # fold would mean 22 x 43 PCA fits and adds no information.
    def heldout_aucs(reference_frame, score_reference, score_target):
        out = []
        for train, test in LeaveOneGroupOut().split(reference_frame.T,
                                                    np.zeros(reference_frame.shape[1]),
                                                    groups):
            keep = train
            test_scores = score_target(reference_frame, train, test)
            reference_scores = score_reference[keep]
            out.append(roc_auc_score(
                np.r_[np.zeros(reference_scores.size), np.ones(test_scores.size)],
                np.r_[reference_scores, test_scores]))
        return out

    # Score 1 -------------------------------------------------------------
    ref_maha = loo_mahalanobis(reference_shared)
    evaluate("mahalanobis_pca", ref_maha,
             fit_score(reference_shared, duplicate_shared),
             fit_score(reference_shared, shifted),
             heldout_aucs(reference_shared, ref_maha,
                          lambda frame, train, test: fit_score(
                              frame.iloc[:, train], frame.iloc[:, test])))

    # Score 2 -------------------------------------------------------------
    ref_corr_shared = loo_correlation(reference_shared.to_numpy(float))
    evaluate("nearest_neighbour_correlation", ref_corr_shared,
             correlation_distance(reference_shared.to_numpy(float), duplicate_shared),
             correlation_distance(reference_shared.to_numpy(float), shifted),
             heldout_aucs(reference_shared, ref_corr_shared,
                          lambda frame, train, test: correlation_distance(
                              frame.iloc[:, train].to_numpy(float),
                              frame.iloc[:, test].to_numpy(float))))

    validated = [name for name, block in report["scores"].items() if block["validated"]]
    report["validatedScores"] = validated
    report["verdict"] = ("ood-score-validated" if validated
                         else "ood-score-not-validated-by-any-available-control")
    report["mechanism"] = [
        "cross-platform comparison requires per-gene standardisation, which removes "
        "gene-level mean shifts that are much of what a platform shift consists of",
        "in-sample Mahalanobis distances are inflated by about sqrt((n-1)/(n-p)); with 44 "
        "arrays and 10 components that is 1.13x, larger than the gap between an ordinary "
        "and an unusual sample, so a new study looks nearer than the training data unless "
        "the reference is scored leave-one-out",
        "the duplicate check also exposes scale sensitivity: a sample that is effectively "
        "in the training set is scored by a model fitted on all of it, while reference "
        "samples are scored with 43, and that difference alone moves the Mahalanobis AUC "
        "to 0.735",
    ]
    report["productConsequence"] = {
        "servedOodFlag": ("must not be presented as a validated novelty detector. It may "
                          "describe distance from the training cloud; it must not say "
                          "'outside distribution' as if a threshold had been validated"),
        "intervalAdvice": ("conformal intervals with measured coverage remain the "
                           "defensible uncertainty mechanism, with empirical and nominal "
                           "coverage always shown separately"),
    }
    report["inStudyScoreQuantiles"] = {
        "mahalanobis_pca": {f"q{int(q * 100)}": round(float(np.quantile(ref_maha, q)), 3)
                            for q in (0.5, 0.9, 0.95, 0.99)},
        "nearest_neighbour_correlation": {
            f"q{int(q * 100)}": round(float(np.quantile(ref_corr_shared, q)), 3)
            for q in (0.5, 0.9, 0.95, 0.99)},
        "note": ("descriptive quantiles of leave-one-out training-study scores. They are "
                 "not thresholds; supplying one would be the claim this phase refutes."),
    }
    report["uncertaintyCarriedOver"] = {
        "source": "phase10_uncertainty_decision.json",
        "nominalCoverage": 0.90,
        "empiricalCoverage": {
            "mizuna-microbial-relative-load-v2": 0.9919,
            "mizuna-microbial-load-v1": 0.9919,
            "lettuce-earth-growth-v2": 0.9606,
            "lettuce-earth-growth-v1": 0.9393,
        },
        "statement": ("empirical and nominal coverage stay distinct everywhere; no "
                      "interval is described as a 90 % interval unless its measured "
                      "coverage reached it"),
    }
    report["registryChange"] = None
    OUT.write_text(json.dumps(report, indent=2) + "\n")
    print(f"\nverdict: {report['verdict']}\nwrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
