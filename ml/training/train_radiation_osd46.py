"""Phase 9 Model A: radiation-response classifiers from NASA OSD-46.

Study (verified from the ISA record in data/raw/OSD-46/OSD-46_metadata_OSD-46-ISA.zip)
----------------------------------------------------------------------------------------
"Gamma radiation and HZE treatment of seedlings in Arabidopsis" (UC Davis / BNL).
44 Affymetrix ATH1 arrays, 2 genotypes (Wild Type, atm-1), three radiation
conditions (non-irradiated, 100 Gy gamma from Cs-137, 30 Gy Fe-56 ions), harvested
1.5 / 3 / 6 / 12 / 24 h after treatment, with two biological replicates per cell.

The independent biological unit is the **sample group** (genotype x condition x
dose x timepoint x age), giving 22 groups of 2 replicate arrays. Two models are
reported because they answer different questions:

A1  radiation quality, 3 classes: control / 100 Gy gamma / 30 Gy Fe-56
    The scientifically interesting comparison is gamma vs HZE: both are ionising,
    but Fe-56 deposits energy far more densely, so a transcriptional difference is
    a plausible biological result rather than an artefact of "irradiated or not".

A2  radiation exposure, binary: control vs irradiated (gamma and Fe-56 pooled)
    A simpler operational question, and deliberately reported separately so the
    three-class result is not the only thing available.

Neither model predicts absorbed dose in gray, survival, plant health or yield.
The classification labels are the **applied treatment**, which is what the study
measured. Nothing here is inferred from a label the study did not record.

Run: python ml/training/train_radiation_osd46.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "ml" / "training"))
from nasa_pipeline import save_json, stamp  # noqa: E402
import phase9_harness as H  # noqa: E402

RAW = ROOT / "data" / "raw" / "OSD-46"
PROCESSED = ROOT / "data" / "processed"
ARTIFACTS = ROOT / "ml" / "artifacts"
EVAL = ROOT / "ml" / "evaluation"

# Short class labels, with the full condition carried in classDescription. The
# labels appear in API responses and in the regression baselines, so they are kept
# stable and the dose detail lives in the description rather than the label.
CONDITION = {
    "non-irradiated": "control",
    "gamma radiation": "gamma",
    "Fe-56 ion radiation": "hze",
}


def load() -> tuple[np.ndarray, list[str], pd.DataFrame]:
    """Gene-level log2 expression, 44 arrays x genes, plus the sample table."""
    frame = pd.read_csv(RAW / "GLDS-46_array_normalized_expression_probeset_GLmicroarray.csv")
    samples = [c for c in frame.columns if c.startswith("GSM")]
    genes = frame["TAIR"].fillna("").astype(str).str.strip()
    matrix = frame[samples].astype(float)
    matrix.index = pd.Index(genes, name="gene")
    matrix = matrix[matrix.index.str.startswith("AT")]
    # Collapse probesets that map to the same gene model: ATH1 has several probes
    # per gene, and keeping them would let one gene contribute several features.
    matrix = matrix.groupby(level=0).mean()
    annotation = pd.read_csv(PROCESSED / "osd46_radiation_samples.csv", dtype=str)
    annotation = annotation.set_index("sample").loc[samples].reset_index()
    if matrix.isna().any().any():
        raise SystemExit("NaN in expression matrix; refusing to impute blindly")
    return matrix.to_numpy(dtype=float).T, list(matrix.index), annotation


def group_key(annotation: pd.DataFrame) -> np.ndarray:
    """The independent unit: genotype x condition x dose x timepoint x age.

    The two arrays inside a group are labelled "rep1"/"rep2" and are biological
    replicates, so they must travel together through every split.
    """
    return (
        annotation["genotype"].astype(str) + "|"
        + annotation["radiation"].astype(str) + "|"
        + annotation["doseGy"].astype(str) + "|"
        + annotation["hoursAfterIrradiation"].astype(str) + "|"
        + annotation["ageDays"].astype(str)
    ).to_numpy()


SPECS = {
    "quality": {
        "id": "radiation-quality-osd46-v1",
        "name": "Arabidopsis radiation-quality classifier (OSD-46)",
        "task": "Three-class radiation quality classification from seedling expression",
        "classDescription": {
            "control": "non-irradiated",
            "gamma": "100 Gy Cs-137 gamma radiation",
            "hze": "30 Gy Fe-56 ion (HZE) radiation",
        },
        "limitations": [
            "Ground-based irradiation of Arabidopsis seedlings, not spaceflight and not a crop.",
            "Three discrete conditions from a single study; not a continuous dose-response surface.",
            "100 Gy gamma and 30 Gy Fe-56 differ in BOTH quality and absorbed dose, so a "
            "classifier separating them cannot attribute the difference to radiation "
            "quality alone.",
            "Gamma and HZE are balanced across array batches, so batch cannot explain this "
            "discrimination - but the control class is not batch-balanced.",
            # Verified against s_OSD-46.txt: atm-1 has 4 treated timepoints to the wild
            # type's 5, and all 8 non-irradiated samples carry no collection time.
            "The design is unbalanced: atm-1 lacks a 3 hour timepoint and controls carry "
            "no collection time.",
            "Never predicts yield, biomass, survival or crop productivity; no such "
            "measurement exists in this study.",
        ],
        "recommendedUse": (
            "Demonstrating that radiation quality leaves a recoverable molecular signature "
            "that generalises to held-out biological groups and across array batches. Not a "
            "dosimeter and not a crop-performance predictor."),
    },
    "exposure": {
        "id": "radiation-exposure-osd46-v1",
        "name": "Arabidopsis radiation exposure classifier (OSD-46)",
        "task": "Binary irradiated-versus-control classification from seedling expression",
        "classDescription": {
            "control": "non-irradiated",
            "irradiated": "100 Gy gamma or 30 Gy Fe-56, pooled",
        },
        "limitations": [
            "Ground-based irradiation of Arabidopsis seedlings, not spaceflight and not a crop.",
            # Verified against the sample table: controls sit on 2 of the 3 array
            # batches and are absent from 1006A-03, which holds 20 of the 44 arrays.
            "Non-irradiated controls appear on only two of the three array batches and "
            "never on the batch holding 20 of the 44 arrays, so condition is associated "
            "with array batch (Cramer's V 0.506 on the full set).",
            "The batch-controlled evaluation on batch 0806A-10 alone is reported in "
            "supplementaryEvaluation and should be preferred over the full-set figure.",
            "Mixes two radiation qualities and two absorbed doses into one label; it does "
            "not separate quality from dose.",
            "Never predicts yield, biomass, survival or crop productivity; no such "
            "measurement exists in this study.",
        ],
        "recommendedUse": (
            "Evidence that an irradiation-exposure signature is recoverable, reported "
            "alongside a batch-controlled evaluation because the control class is not "
            "batch-balanced."),
    },
}


def batch_table() -> dict:
    """Array batch per sample, recovered from the raw CEL headers in a prior step."""
    path = PROCESSED / "osd46_array_batch.csv"
    if not safedata.exists(path):
        return {}
    frame = pd.read_csv(path, dtype=str)
    return dict(zip(frame["sample"], frame["arrayBatch"]))


def cramers_v(rows: list[tuple[str, str]]) -> dict:
    table = pd.crosstab(pd.Series([r[0] for r in rows], name="batch"),
                        pd.Series([r[1] for r in rows], name="label"))
    observed = table.to_numpy(dtype=float)
    total = observed.sum()
    expected = np.outer(observed.sum(axis=1), observed.sum(axis=0)) / total
    with np.errstate(divide="ignore", invalid="ignore"):
        chi2 = float(np.nansum((observed - expected) ** 2
                               / np.where(expected == 0, np.nan, expected)))
    v = float(np.sqrt((chi2 / total) / (min(observed.shape) - 1)))
    return {"cramersV": round(v, 4), "chiSquare": round(chi2, 3),
            "contingency": {str(b): {str(c): int(n) for c, n in row.items()}
                            for b, row in table.iterrows()}}


def write_artifact(key: str, matrix, genes, annotation, groups, labels, report) -> dict:
    """Fit the shipped learner on all data and serialise it for the runtime.

    Reported performance always comes from the group-held-out folds, never from
    this fit. Selecting genes on the full matrix for *deployment* is standard and
    is not leakage as long as no metric is quoted from the fitted-on-everything
    model, which is why the metrics stored here are copied from the CV report.
    """
    spec = SPECS[key]
    task = report["tasks"][key]
    chosen = H.select_features(matrix, labels, n_features=H.TOP_ANOVA_GENES)
    learner_name = "logistic_l2"   # the best *serialisable* family
    model = H.classification_learners()[learner_name]()
    model.fit(matrix[:, chosen], labels)
    feature_names = [genes[i] for i in chosen]
    evaluator = H.extract_linear_evaluator(model, feature_names)

    # Reference profiles: per-class means over the selected genes. Synthetic by
    # construction, and labelled as such wherever they are served.
    profiles = {}
    for label in np.unique(labels):
        profiles[str(label)] = [float(v) for v in matrix[labels == label][:, chosen].mean(axis=0)]

    batches = batch_table()
    pairs = [(batches[s], str(l)) for s, l in zip(annotation["sample"], labels) if s in batches]
    confound = cramers_v(pairs) if pairs else {}
    if confound:
        confound["interpretation"] = (
            "Association between array processing batch and the class label. Gamma and "
            "HZE are balanced across batches; the control class is not."
            if key == "quality" else
            "Association between array processing batch and the class label. Controls do "
            "not appear on the batch holding 20 of the 44 arrays, so part of the "
            "separation could be array handling rather than irradiation.")

    # The exposure task is confounded by array batch, so it is reported twice. The
    # supplementary figure uses the ONE batch containing all three conditions, where
    # the confound is removed by construction rather than adjusted for.
    supplementary = None
    if key == "exposure" and batches:
        members = np.array([batches.get(s) == "0806A-10" for s in annotation["sample"]])
        if members.sum() >= 8 and len(np.unique(labels[members])) == 2:
            sub_labels, sub_groups = labels[members], groups[members]
            score = H.grouped_cv_score(matrix[members], sub_labels, sub_groups,
                                       H.classification_learners()["logistic_l2"])
            supplementary = {
                "batch": "0806A-10",
                "arraysUsed": int(members.sum()),
                "groups": int(len(np.unique(sub_groups))),
                "classCounts": {str(k): int(v) for k, v in
                                pd.Series(sub_labels).value_counts().items()},
                "learner": "logistic_l2",
                "accuracy": score["accuracy"],
                "bestBalancedAccuracy": score["balancedAccuracy"],
                "macroF1": score["macroF1"],
                "rationale": (
                    "Controls never appear on batch 1006A-03, which holds 20 of the 44 "
                    "arrays, so condition is associated with array batch (Cramer's V "
                    "0.506). Batch 0806A-10 is the only batch containing all three "
                    "conditions, so evaluating there removes the confound by "
                    "construction. This is the figure to quote."),
                "allLearners": None,
            }
            print(f"   batch-controlled subset: {supplementary['arraysUsed']} arrays, "
                  f"{supplementary['classCounts']}, bal {score['balancedAccuracy']:.3f}")

    metrics = task["learners"][learner_name]
    payload = {
        "id": spec["id"],
        "name": spec["name"],
        "version": "1.0.0",
        "status": "trained-exploratory",
        "trainedAt": stamp(),
        "sourceStudy": "OSD-46",
        "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-46",
        "sourceType": "NASA OSDR microarray (GeneLab GLDS-46)",
        "platform": "Affymetrix ATH1 Arabidopsis Genome Array",
        "organism": "Arabidopsis thaliana (Wild Type, atm-1)",
        "task": spec["task"],
        "classLabels": [str(c) for c in np.unique(labels)],
        "classDescription": spec["classDescription"],
        "samples": int(matrix.shape[0]),
        "groups": int(len(np.unique(groups))),
        "genesAvailable": int(matrix.shape[1]),
        "genesSelected": int(len(chosen)),
        "features": feature_names,
        "expressionUnits": "log2 normalised Affymetrix intensities, gene-model collapsed by mean",
        "method": f"{learner_name} with in-fold ANOVA gene selection",
        "validation": ("Leave-one-biological-group-out cross-validation over 22 groups. "
                       "Gene filtering and ANOVA selection fitted inside each training "
                       "fold only. Labels permuted between groups for the null."),
        "evidenceStatus": "experimental",
        "metrics": {k: metrics[k] for k in
                    ("accuracy", "balancedAccuracy", "macroF1", "nSamples", "nGroups",
                     "confusionMatrix", "classLabels", "perClassRecall",
                     "bootstrapCi", "genesSharedAcrossFolds",
                     "singleClassHeldOutGroups", "validationScheme")},
        "baselineMetrics": {k: task["learners"]["baseline_majority"][k] for k in
                            ("accuracy", "balancedAccuracy", "macroF1", "nSamples",
                             "nGroups", "confusionMatrix", "classLabels",
                             "perClassRecall", "validationScheme")},
        "bestOverallLearner": {
            "name": task["bestLearner"],
            "balancedAccuracy": task["learners"][task["bestLearner"]]["balancedAccuracy"],
            "accuracy": task["learners"][task["bestLearner"]]["accuracy"],
            "note": ("Best learner among all five families. Tree ensembles cannot be "
                     "serialised into the dependency-free evaluator, so the shipped "
                     "artifact is the best linear learner instead."),
        },
        "allLearners": task["learners"],
        "permutationTest": task["permutation"],
        "beatsBaseline": task["beatsBaseline"],
        "batchConfound": confound,
        "supplementaryEvaluation": supplementary,
        "batchOfEachSample": batches,
        "seed": H.SEED,
        "environment": {
            "python": ".".join(map(str, __import__("sys").version_info[:3])),
            "numpy": np.__version__, "pandas": pd.__version__,
            "sklearn": __import__("sklearn").__version__},
        "evaluator": evaluator,
        "domain": {
            "note": ("Supply log2 normalised expression for every gene in 'features'. "
                     "Partial vectors are rejected rather than zero-filled."),
            "expressionRange": {"min": float(matrix[:, chosen].min()),
                                "max": float(matrix[:, chosen].max())},
            "features": {feature_names[i]: {"min": float(matrix[:, chosen][:, i].min()),
                                            "max": float(matrix[:, chosen][:, i].max())}
                         for i in range(len(feature_names))},
        },
        "referenceProfiles": profiles,
        "referenceProfilesNote": (
            "Per-class mean of the training expression across the selected genes. These "
            "are class centroids computed from NASA OSD-46 data, NOT individual measured "
            "samples, and using one as model input is a synthetic input that must be "
            "labelled as such."),
        "limitations": spec["limitations"],
        "recommendedUse": spec["recommendedUse"],
    }
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS / f"{spec['id']}"
    safedata.dump(payload, path)
    import hashlib
    digest = hashlib.sha256(safedata.bytes(path)).hexdigest()
    print(f"   wrote {path.name} ({path.stat().st_size:,} B), sha256 {digest[:16]}...")
    return {"artifact": str(path.relative_to(ROOT)), "sha256": digest,
            "size": path.stat().st_size}


def main() -> int:
    matrix, genes, annotation = load()
    groups = group_key(annotation)
    quality = annotation["radiation"].map(CONDITION).to_numpy()
    exposure = np.where(annotation["radiation"] == "non-irradiated",
                        "control", "irradiated")

    print(f"OSD-46: {matrix.shape[0]} arrays x {matrix.shape[1]} genes, "
          f"{len(np.unique(groups))} biological groups")
    print(f"  quality classes: {dict(pd.Series(quality).value_counts())}")
    print(f"  groups per quality class: "
          f"{dict(pd.Series(quality).groupby(groups).first().value_counts())}")

    tasks = {
        "quality": ("radiation-quality-osd46-v1", quality,
                    "radiation quality (control / 100 Gy gamma / 30 Gy Fe-56)"),
        "exposure": ("radiation-exposure-osd46-v1", exposure,
                     "radiation exposure (control / irradiated)"),
    }
    report = {"study": "OSD-46", "phase": 9, "seed": H.SEED,
              "arrays": int(matrix.shape[0]), "genes": int(matrix.shape[1]),
              "biologicalGroups": int(len(np.unique(groups))),
              "unitNote": ("Two replicate arrays per group are biological "
                           "replicates and are never split across folds."),
              "tasks": {}}

    for key, (model_id, labels, description) in tasks.items():
        print(f"\n== {model_id}: {description}")
        learners = H.evaluate_all_learners(matrix, labels, groups)
        for name, score in learners.items():
            print(f"   {name:26s} acc {score['accuracy']:.3f}  "
                  f"bal {score['balancedAccuracy']:.3f}  f1 {score['macroF1']:.3f}")

        best_name = max((n for n in learners if n != "baseline_majority"),
                        key=lambda n: learners[n]["balancedAccuracy"])
        best = learners[best_name]
        baseline = learners["baseline_majority"]
        improvement = best["balancedAccuracy"] - baseline["balancedAccuracy"]

        permutation = H.permutation_test(
            matrix, labels, groups, H.classification_learners()[best_name],
            best["balancedAccuracy"], n_permutations=100)
        print(f"   best={best_name} bal={best['balancedAccuracy']:.3f} "
              f"baseline={baseline['balancedAccuracy']:.3f} "
              f"p={permutation['pValue']:.4f}")

        report["tasks"][key] = {
            "modelId": model_id,
            "description": description,
            "classLabels": best["classLabels"],
            "learners": learners,
            "bestLearner": best_name,
            "baselineBalancedAccuracy": baseline["balancedAccuracy"],
            "improvementOverBaseline": improvement,
            "permutation": permutation,
            "beatsBaseline": bool(improvement > 0 and permutation["pValue"] <= 0.05),
        }

    written = {}
    print("\nWriting artifacts for the tasks that beat their baseline:")
    for key, (model_id, labels, _) in tasks.items():
        if report["tasks"][key]["beatsBaseline"]:
            written[model_id] = write_artifact(key, matrix, genes, annotation,
                                               groups, labels, report)
        else:
            print(f"   skipped {model_id}: did not beat baseline")

    report["artifacts"] = written
    EVAL.mkdir(parents=True, exist_ok=True)
    save_json(EVAL / "phase9_osd46_radiation", report)
    print("\nwrote ml/evaluation/phase9_osd46_radiation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
