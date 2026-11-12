"""Phase 9 Priority C: crop-microbiome feasibility on the ISS lettuce studies.

Why this file exists
--------------------
The first Phase 9 eligibility pass concluded that no crop-microbiome data was
usable, because the studies inspected published only raw amplicon FASTQ. A
systematic sweep of 587 OSDR studies (scripts/sweep_phase9_osdr.py) and a screen
of the 231 that publish processed matrices (scripts/screen_phase9_candidates.py)
found six with processed taxonomic count tables - including OSD-267 (VEG-01A) and
OSD-269 (VEG-03A), which are exactly ISS-grown lettuce microbiome studies.

So the earlier verdict was wrong on the facts and this file replaces it. What it
does **not** do is turn that correction into a classifier, because the design
cannot support one. The numbers that decide this are printed and recorded:

    VEG-01A leaf   2 flight vs 5 ground plants
    VEG-03A leaf   6 flight vs 5 ground plants
    roots          2 vs 2 in both missions

Two flight plants in VEG-01A is not a training class. Pooling the missions would
confound mission with condition. A leave-one-plant-out estimate on seventeen plants
would have an interval so wide that quoting a balanced accuracy from it would
misrepresent what is known.

What is defensible is a **descriptive** comparison within a single mission, with
the plant as the unit and a permutation test over plants. That is reported here as
a description of composition, explicitly not as a prediction model, and it is not
registered in the model registry.

Abundance is compositional. This file never converts it to CFU or to absolute
counts, and never claims a yield consequence.

Run: python ml/training/analyze_veg_microbiome.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from nasa_pipeline import save_json, stamp  # noqa: E402

RAW = ROOT / "data" / "raw"
EVAL = ROOT / "ml" / "evaluation"
PROCESSED = ROOT / "data" / "processed"
SEED = 20261107

STUDIES = {
    "OSD-267": {
        "mission": "VEG-01A",
        "table": RAW / "OSD-267" / "GLDS-267_GAmplicon_16S-taxonomy-and-counts.tsv",
    },
    "OSD-269": {
        "mission": "VEG-03A",
        "table": RAW / "OSD-269" / "GLDS-269_GAmplicon_taxonomy-and-counts.tsv",
    },
}


def load_counts(path: Path) -> tuple[pd.DataFrame, list[str]]:
    """Genus-level counts with plant host reads removed.

    Chloroplast and mitochondrial ASVs are plant-derived, not microbial, and they
    dominate leaf samples. Leaving them in would mean the "microbiome" signal was
    mostly lettuce.
    """
    frame = pd.read_csv(path, sep="\t")
    annotation = list(frame.columns[:8])
    samples = list(frame.columns[8:])
    host = (frame["order"].astype(str).str.contains("Chloroplast", na=False)
            | frame["family"].astype(str).str.contains("Mitochondria", na=False))
    frame = frame[~host].copy()
    frame["taxon"] = frame["genus"].fillna(
        "unclassified_" + frame["family"].astype(str))
    counts = frame.groupby("taxon")[samples].sum()
    return counts, samples


def design_row(sample: str) -> dict:
    lowered = sample.lower()
    return {
        "sample": sample,
        "mission": "VEG-01A" if lowered.startswith(("flight", "ground")) else "VEG-03A",
        "condition": "flight" if ("flt" in lowered or "flight" in lowered) else "ground",
        "tissue": "root" if "root" in lowered else "leaf",
    }


def clr(counts: pd.DataFrame, pseudocount: float = 0.5) -> pd.DataFrame:
    """Centred log-ratio. Compositional data must not be analysed on raw proportions
    with Euclidean distance, because proportions are constrained to sum to one."""
    shifted = counts + pseudocount
    proportions = shifted / shifted.sum(axis=0)
    logarithms = np.log(proportions)
    return logarithms - logarithms.mean(axis=0)


def permutation_test_centroid_distance(x: np.ndarray, labels: np.ndarray,
                                       n_permutations: int = 5000,
                                       seed: int = SEED) -> dict:
    """Distance between class centroids, tested by permuting the labels.

    A permutation test is used rather than a parametric test because the sample is
    far too small for the distributional assumptions of a t-test, and because the
    null of interest is "condition labels are exchangeable between plants".
    """
    def statistic(groups: np.ndarray) -> float:
        first = x[groups == np.unique(groups)[0]].mean(axis=0)
        second = x[groups == np.unique(groups)[1]].mean(axis=0)
        return float(np.linalg.norm(first - second))

    observed = statistic(labels)
    generator = np.random.default_rng(seed)
    null = np.array([statistic(generator.permutation(labels))
                     for _ in range(n_permutations)])
    exceedances = int((null >= observed).sum())
    return {
        "observedDistance": observed,
        "nPermutations": n_permutations,
        "nullMean": float(null.mean()),
        "nullP95": float(np.percentile(null, 95)),
        "pValue": (1 + exceedances) / (1 + n_permutations),
        "correction": "finite-sample corrected: (1 + #{null >= observed}) / (1 + B)",
    }


def describe_mission(study: str, spec: dict) -> dict:
    counts, samples = load_counts(spec["table"])
    frame = pd.DataFrame([design_row(name) for name in samples])
    record = {
        "study": study,
        "mission": spec["mission"],
        "samples": len(samples),
        "generaAfterHostRemoval": int(counts.shape[0]),
        "reads": int(counts.to_numpy().sum()),
    }

    leaf = frame[frame["tissue"] == "leaf"].reset_index(drop=True)
    leaf_counts = counts[leaf["sample"]]
    # Keep genera present in at least half the leaf samples; rarer taxa are
    # uninformative at this sample size and inflate the distance.
    keep = (leaf_counts > 0).mean(axis=1) >= 0.5
    leaf_counts = leaf_counts[keep]
    record["generaUsedLeaf"] = int(leaf_counts.shape[0])
    record["leafDesign"] = leaf["condition"].value_counts().to_dict()

    if leaf["condition"].nunique() == 2 and leaf["condition"].value_counts().min() >= 2:
        matrix = clr(leaf_counts).to_numpy().T
        labels = leaf["condition"].to_numpy()
        record["leafCompositionTest"] = permutation_test_centroid_distance(matrix, labels)
        composition = leaf_counts.div(leaf_counts.sum(axis=0), axis=1)
        means = composition.T.groupby(labels).mean()
        record["leafTopGeneraByClass"] = {
            str(condition): [f"{genus} {value:.3f}"
                             for genus, value in row.sort_values(ascending=False).head(6).items()]
            for condition, row in means.iterrows()
        }
    else:
        record["leafCompositionTest"] = None
        record["leafCompositionNote"] = (
            "fewer than two plants in one class; no test attempted")

    root = frame[frame["tissue"] == "root"]
    record["rootDesign"] = root["condition"].value_counts().to_dict() if len(root) else {}
    record["verdict"] = "descriptive-only-not-a-prediction-model"
    record["whyNotModelled"] = [
        f"Leaf samples per class are {record['leafDesign']}: one class has too few "
        "independent plants to train on.",
        "Each plant contributes leaf and root samples, so those are repeated "
        "measures rather than independent observations.",
        "Pooling VEG-01A and VEG-03A would confound mission with condition.",
        "Abundance is compositional and is never converted to CFU or absolute counts.",
    ]
    return record


def main() -> int:
    records = [describe_mission(study, spec) for study, spec in STUDIES.items()]

    payload = {
        "phase": 9,
        "task": "crop microbiome feasibility (Priority C)",
        "generatedAt": stamp(),
        "seed": SEED,
        "discovery": (
            "A systematic sweep of 587 studies found 231 with processed matrices; "
            "6 publish processed taxonomic count tables. OSD-267 (VEG-01A) and "
            "OSD-269 (VEG-03A) are ISS-grown red romaine lettuce microbiome studies "
            "and are the only crop-microbiome candidates in the repository."
        ),
        "transformation": ("host chloroplast and mitochondrial reads removed, "
                           "aggregated to genus, CLR-transformed for ordination"),
        "studies": records,
        "registration": ("Not registered. A descriptive compositional result is not "
                         "a predictor, and Phase 9 does not ship a model that cannot "
                         "be validated on held-out biological units."),
        "cannotSay": [
            "No absolute abundance, CFU count or total microbial load follows from this.",
            "No food-safety verdict follows from this.",
            "No yield or biomass consequence follows from this.",
            "This is not a partial-gravity or Mars-gravity result; the comparison is "
            "ISS flight versus ground control.",
        ],
    }
    EVAL.mkdir(parents=True, exist_ok=True)
    save_json(EVAL / "phase9_veg_microbiome_feasibility", payload)

    for record in records:
        print(f"\n{record['study']} ({record['mission']}): {record['samples']} samples, "
              f"{record['generaAfterHostRemoval']} genera, {record['reads']:,} reads")
        print(f"  leaf design: {record['leafDesign']}")
        test = record["leafCompositionTest"]
        if test:
            print(f"  CLR centroid distance {test['observedDistance']:.3f}, "
                  f"p={test['pValue']:.4f} over {test['nPermutations']} permutations")
    print("\nwrote ml/evaluation/phase9_veg_microbiome_feasibility")
    print("Verdict: descriptive only. No model registered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
