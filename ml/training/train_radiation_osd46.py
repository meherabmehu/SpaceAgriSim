"""Phase 9 Models A1/A2: radiation response classifiers from OSD-46.

Two distinct scientific questions are trained and registered separately, because
they carry very different amounts of batch confound and must not be reported as
one number.

A1  radiation quality  (control / gamma / HZE, 3 classes)
    Different ionising qualities deposit energy differently: Cs-137 gamma gives a
    sparse diffuse track, while 30 Gy of Fe-56 ions gives a dense track of local
    damage. Asking whether the transcriptional state retains a signature of *which*
    quality was received is a real question.

    Crucially, gamma and Fe-56 are **balanced across array batches** in this study
    (8 each on batch 0806A, 10 each on 1006A). A classifier that separates them
    therefore cannot be doing so by reading the array batch, which is what makes
    this the strongest result in Phase 9.

A2  irradiated vs non-irradiated  (2 classes)
    A simpler and operationally more interesting question, but *confounded*: the
    eight non-irradiated controls appear only on batches 0706A (4) and 0806A (4)
    and never on 1006A, which holds 20 of the 44 arrays. Cramer's V between batch
    and condition is 0.506. A batch-blind classifier separating control from
    irradiated could be reading sample handling.

    So A2 is reported twice: on all 44 arrays (flagging the confound) and on the
    0806A batch alone, the only batch containing all three conditions, where the
    confound is removed by construction.

Neither model predicts yield, biomass, survival or crop productivity: no such
measurement exists in this study.

Run: python ml/training/train_radiation_osd46.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "ml" / "training"))
from nasa_pipeline import save_json, stamp  # noqa: E402
import phase9_harness as H  # noqa: E402

RAW = ROOT / "data" / "raw" / "OSD-46"
PROCESSED = ROOT / "data" / "processed"
EVAL = ROOT / "ml" / "evaluation"
ARTIFACTS = ROOT / "ml" / "artifacts"

RADIATION_LABELS = {
    "non-irradiated": "control",
    "gamma radiation": "gamma",
    "Fe-56 ion radiation": "hze",
}


def load_matrix() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    expression = pd.read_csv(RAW / "GLDS-46_array_normalized_expression_probeset_GLmicroarray.csv")
    annotation = pd.read_csv(PROCESSED / "osd46_radiation_samples.csv", dtype=str)
    batch = pd.read_csv(PROCESSED / "osd46_array_batch.csv", dtype=str)
    columns = [c for c in expression.columns if c.startswith("GSM")]
    annotation = annotation.set_index("sample").loc[columns]
    batch = batch.set_index("sample").loc[columns]
    expression = expression.set_index("ProbesetID")
    names = expression["TAIR"].fillna(expression.index.to_series()).astype(str)
    matrix = expression[columns].astype(float)
    matrix.index = pd.Index(names, name="gene")
    # Collapse probesets mapping to the same gene model, so one gene cannot be
    # counted five times and dominate the variance filter.
    matrix = matrix.groupby(level=0).mean()
    if matrix.isna().any().any():
        raise SystemExit("Missing expression values; refusing to impute blindly")
    return matrix, annotation, batch


def group_key(annotation: pd.DataFrame) -> np.ndarray:
    """The biological unit: genotype x condition x age x collection time.

    `hoursAfterIrradiation` is genuinely absent for the eight non-irradiated
    controls; filling it explicitly prevents NaN from collapsing separate batches
    into one group.
    """
    return (
        annotation["genotype"].fillna("NA").astype(str) + "|"
        + annotation["radiation"].fillna("NA").astype(str) + "|"
        + annotation["ageDays"].fillna("NA").astype(str) + "|"
        + annotation["hoursAfterIrradiation"].fillna("no-timepoint").astype(str)
    ).to_numpy()


def batch_confound(batch: pd.DataFrame, labels: np.ndarray) -> dict:
    """Cramer's V between array batch and the label, plus the cross-tabulation.

    Reported because a classifier is only as trustworthy as its weakest confound,
    and this makes the size of that confound a number rather than a caveat.
    """
    table = pd.crosstab(batch["arrayBatch"], labels)
    observed = table.to_numpy().astype(float)
    total = observed.sum()
    expected = np.outer(observed.sum(axis=1), observed.sum(axis=0)) / total
    with np.errstate(divide="ignore", invalid="ignore"):
        chi2 = float(np.nansum((observed - expected) ** 2 / np.where(expected == 0, np.nan, expected)))
    v = float(np.sqrt((chi2 / total) / (min(observed.shape) - 1)))
    return {
        "cramersV": round(v, 4),
        "chiSquare": round(chi2, 3),
        "contingency": {str(i): {str(c): int(observed[r, j]) for j, c in enumerate(table.columns)}
                        for r, i in enumerate(table.index)},
        "interpretation": ("batch and label are independent" if v < 0.1 else
                           "moderate association - batch cannot be ruled out as a partial explanation"
                           if v < 0.5 else
                           "strong association - batch is a plausible alternative explanation"),
    }


def train_and_register(x, y, groups, genes, *, model_id, name, task, class_description,
                       limitations, recommended_use, batch, confound, extra_metrics=None):
    print(f"\n=== {model_id}: {x.shape[0]} samples x {x.shape[1]} genes, "
          f"{len(np.unique(groups))} groups, {len(np.unique(y))} classes")
    learners = H.classification_learners()
    results = H.summarize_learners(x, y, groups, genes)
    for lname, report in results.items():
        print(f"   {lname:20s} acc {report['accuracy']:.3f}  "
              f"bal {report['balancedAccuracy']:.3f}  macroF1 {report['macroF1']:.3f}")

    # Balanced accuracy ranks the learners, not raw accuracy: with an unbalanced
    # task a model can win on accuracy by always predicting the majority class.
    ranked = sorted(((n, r) for n, r in results.items() if n != "baseline_majority"),
                    key=lambda kv: kv[1]["balancedAccuracy"], reverse=True)
    best_name, best = ranked[0]

    # Only the linear models can be serialised into the dependency-free JSON
    # evaluator, so the shipped artifact is the best *deployable* learner. When a
    # tree ensemble wins overall that is reported as-is; it is not silently dropped.
    DEPLOYABLE = ("logistic_l2", "logistic_l1")
    deployable = [(n, r) for n, r in ranked if n in DEPLOYABLE]
    if not deployable:
        raise SystemExit("No deployable linear learner available")
    shipped_name, shipped = deployable[0]

    permutation = H.permutation_test(x, y, groups, learners[shipped_name],
                                     observed=shipped["accuracy"], n_permutations=100)
    print(f"   best overall {best_name}: bal {best['balancedAccuracy']:.3f}")
    print(f"   shipped (deployable) {shipped_name}: acc {shipped['accuracy']:.3f}, "
          f"bal {shipped['balancedAccuracy']:.3f}, "
          f"permutation p = {permutation['pValue']:.4f} (floor 0.0099)")

    baseline_bal = results["baseline_majority"]["balancedAccuracy"]
    beats = shipped["balancedAccuracy"] > baseline_bal
    significant = permutation["pValue"] <= 0.05
    status = "experimental" if (beats and significant) else "insufficient-evidence"

    chosen = H.select_features(x, y, genes)
    final = learners[shipped_name]().fit(x[:, chosen], y)
    evaluator = H.extract_linear_evaluator(final, [genes[i] for i in chosen])

    artifact = {
        "id": model_id,
        "name": name,
        "version": "1.0.0",
        # Kept alongside evidenceStatus for schema consistency with the Phase 6-8
        # artifacts, which all carry a training status plus a separate evidence label.
        "status": "trained-exploratory",
        "trainedAt": stamp(),
        "sourceStudy": "OSD-46",
        "sourceUrl": "https://osdr.nasa.gov/bio/repo/data/studies/OSD-46",
        "sourceType": "NASA OSDR microarray (GeneLab GLDS-46)",
        "platform": "Affymetrix ATH1 Arabidopsis Genome Array",
        "organism": "Arabidopsis thaliana (Wassilewskija background)",
        "task": task,
        "classLabels": [str(c) for c in np.unique(y)],
        "classDescription": class_description,
        "samples": int(x.shape[0]),
        "groups": int(len(np.unique(groups))),
        "genesAvailable": int(x.shape[1]),
        "genesSelected": len(chosen),
        "features": [genes[i] for i in chosen],
        "expressionUnits": "log2 normalised Affymetrix intensities, gene-model collapsed by mean",
        "method": f"{shipped_name} with in-fold ANOVA gene selection",
        "validation": ("Leave-one-biological-group-out cross-validation over "
                       f"{len(np.unique(groups))} groups. Gene filtering and ANOVA "
                       "selection fitted inside each training fold only. Labels "
                       "permuted between groups for the null."),
        "evidenceStatus": status,
        "metrics": shipped,
        "baselineMetrics": results["baseline_majority"],
        "bestOverallLearner": {
            "name": best_name,
            "balancedAccuracy": best["balancedAccuracy"],
            "accuracy": best["accuracy"],
            "note": ("Best learner among all five families. Tree ensembles cannot be "
                     "serialised into the dependency-free evaluator, so the shipped "
                     "artifact is the best linear learner instead."),
        },
        "allLearners": {n: {k: r[k] for k in ("accuracy", "balancedAccuracy", "macroF1",
                                              "perGroupRecall", "singleClassHeldOutGroups")}
                        for n, r in results.items()},
        "permutationTest": permutation,
        "beatsBaseline": bool(beats),
        "batchConfound": confound,
        "batchOfEachSample": [str(b) for b in batch["arrayBatch"]],
        "seed": H.SEED,
        "environment": {"python": sys.version.split()[0], "numpy": np.__version__,
                        "pandas": pd.__version__, "sklearn": sklearn.__version__},
        "evaluator": evaluator,
        "domain": {
            "note": ("Supply log2 normalised expression for every gene in 'features'. "
                     "Partial vectors are rejected rather than zero-filled."),
            "expressionRange": {"min": float(x[:, chosen].min()), "max": float(x[:, chosen].max())},
            # Per-gene observed range, used by the API to flag out-of-domain inputs
            # gene by gene rather than only against one global bound.
            "features": {
                genes[i]: {"min": float(x[:, i].min()), "max": float(x[:, i].max())}
                for i in chosen
            },
        },
        # Per-class mean expression over the selected genes, in the artifact's own
        # units. Exposed so a demonstration can run on a real training centroid
        # while being labelled exactly as what it is - a centroid, not a specimen.
        "referenceProfiles": {
            str(label): [float(v) for v in x[y == label][:, chosen].mean(axis=0)]
            for label in np.unique(y)
        },
        "referenceProfilesNote": (
            "Per-class mean of the training expression across the selected genes. "
            "These are class centroids computed from NASA OSD-46 data, NOT individual "
            "measured samples, and using one as model input is a synthetic input that "
            "must be labelled as such."
        ),
        "limitations": limitations,
        "recommendedUse": recommended_use,
    }
    if extra_metrics:
        artifact["supplementaryEvaluation"] = extra_metrics

    body = json.dumps(artifact, separators=(",", ":"), allow_nan=False)
    (ARTIFACTS / f"{model_id}.json").write_text(body + "\n", encoding="utf-8")
    digest = hashlib.sha256((body + "\n").encode()).hexdigest()

    registry_path = ARTIFACTS / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["models"] = [m for m in registry["models"] if m["id"] != model_id]
    registry["models"].append({"id": model_id,
                               "artifact": f"ml/artifacts/{model_id}.json",
                               "sha256": digest})
    registry["trainedAt"] = stamp()
    registry_path.write_text(json.dumps(registry, indent=1) + "\n", encoding="utf-8")
    print(f"   wrote {model_id}.json ({len(body):,} B), status={status}, sha256 {digest[:16]}...")

    return {"modelId": model_id, "study": "OSD-46", "samples": int(x.shape[0]),
            "groups": int(len(np.unique(groups))), "learners": results,
            "bestOverall": best_name, "shipped": shipped_name,
            "permutationTest": permutation,
            "batchConfound": confound, "evidenceStatus": status,
            "supplementaryEvaluation": extra_metrics, "artifactSha256": digest}


def main() -> None:
    matrix, annotation, batch = load_matrix()
    genes = list(matrix.index)
    x_all = matrix.to_numpy().T
    groups_all = group_key(annotation)
    if len(np.unique(groups_all)) != 22:
        raise SystemExit(f"Expected 22 biological groups, found {len(np.unique(groups_all))}")

    # ---------------- A1: radiation quality, three classes ----------------
    y_quality = np.array([RADIATION_LABELS[r] for r in annotation["radiation"]])
    confound_quality = batch_confound(batch, y_quality)
    print("A1 batch confound:", confound_quality["cramersV"],
          "-", confound_quality["interpretation"])
    evaluation_a1 = train_and_register(
        x_all, y_quality, groups_all, genes,
        model_id="radiation-quality-osd46-v1",
        name="Arabidopsis radiation-quality classifier (OSD-46)",
        task="Three-class radiation quality classification from seedling expression",
        class_description={
            "control": "non-irradiated",
            "gamma": "100 Gy Cs-137 gamma radiation",
            "hze": "30 Gy Fe-56 ion (HZE) radiation",
        },
        limitations=[
            "Ground-based irradiation of Arabidopsis seedlings, not spaceflight and not a crop.",
            "Three discrete conditions from a single study; not a continuous dose-response surface.",
            "100 Gy gamma and 30 Gy Fe-56 differ in BOTH quality and absorbed dose, so a classifier separating them cannot attribute the difference to radiation quality alone.",
            "Gamma and HZE are balanced across array batches, so batch cannot explain this discrimination - but the control class is not batch-balanced.",
            "The design is unbalanced: atm-1 lacks a 3 hour timepoint and controls carry no collection time.",
            "Never predicts yield, biomass, survival or crop productivity; no such measurement exists in this study.",
        ],
        recommended_use=("Demonstrating that radiation quality leaves a recoverable molecular "
                         "signature that generalises to held-out biological groups and across "
                         "array batches. Not a dosimeter and not a crop-performance predictor."),
        batch=batch, confound=confound_quality,
    )

    # ---------------- A2: irradiated vs control, with batch control ----------------
    y_binary = np.array(["control" if r == "non-irradiated" else "irradiated"
                         for r in annotation["radiation"]])
    confound_binary = batch_confound(batch, y_binary)
    print("\nA2 batch confound:", confound_binary["cramersV"],
          "-", confound_binary["interpretation"])

    # Batch-controlled supplementary test: only the 0806A batch, the one batch that
    # contains all three conditions, so control vs irradiated is no longer
    # confounded with array processing.
    single = (batch["arrayBatch"] == "0806A-10").to_numpy()
    if single.sum() < 12:
        raise SystemExit("Insufficient arrays on the single batch")
    x_sub, y_sub = x_all[single], y_binary[single]
    groups_sub = groups_all[single]
    print(f"   batch-controlled subset: {single.sum()} arrays on 0806A-10, "
          f"{len(np.unique(groups_sub))} groups, "
          f"labels {dict(zip(*np.unique(y_sub, return_counts=True)))}")
    learners = H.classification_learners()
    sub_scores = {n: H.grouped_cv_score(x_sub, y_sub, groups_sub, f, column_names=genes)
                  for n, f in learners.items()}
    for n, r in sub_scores.items():
        print(f"     {n:20s} acc {r['accuracy']:.3f}  bal {r['balancedAccuracy']:.3f}")
    sub_best = max(((n, r) for n, r in sub_scores.items() if n != "baseline_majority"),
                   key=lambda kv: kv[1]["balancedAccuracy"])
    supplementary = {
        "name": "batch-controlled irradiated-vs-control",
        "rationale": ("Controls never appear on array batch 1006A-03, so on the full "
                      "dataset condition and array batch are associated (Cramer's V "
                      f"{confound_binary['cramersV']}). Restricting to batch 0806A-10, which "
                      "contains all three conditions, removes that confound by construction."),
        "arraysUsed": int(single.sum()),
        "batch": "0806A-10",
        "groups": int(len(np.unique(groups_sub))),
        "learners": {n: {k: r[k] for k in ("accuracy", "balancedAccuracy", "macroF1", "perGroupRecall")}
                     for n, r in sub_scores.items()},
        "best": sub_best[0],
        "bestBalancedAccuracy": sub_best[1]["balancedAccuracy"],
    }

    evaluation_a2 = train_and_register(
        x_all, y_binary, groups_all, genes,
        model_id="radiation-exposure-osd46-v1",
        name="Arabidopsis radiation exposure classifier (OSD-46)",
        task="Binary irradiated-versus-control classification from seedling expression",
        class_description={
            "control": "non-irradiated",
            "irradiated": "either 100 Gy Cs-137 gamma or 30 Gy Fe-56 ion radiation",
        },
        limitations=[
            "Ground-based irradiation of Arabidopsis seedlings, not spaceflight and not a crop.",
            "Non-irradiated controls appear on only two of the three array batches and never on the batch holding 20 of the 44 arrays, so condition is associated with array batch (Cramer's V 0.506 on the full set).",
            "The batch-controlled evaluation on batch 0806A-10 alone is reported in supplementaryEvaluation and should be preferred over the full-set figure.",
            "Mixes two radiation qualities and two absorbed doses into one 'irradiated' label; it does not distinguish quality or dose.",
            "Never predicts yield, biomass, survival or crop productivity; no such measurement exists in this study.",
        ],
        recommended_use=("Evidence that an irradiation-exposure signature is recoverable, "
                         "reported alongside a batch-controlled evaluation because the "
                         "control class is not batch-balanced."),
        batch=batch, confound=confound_binary, extra_metrics=supplementary,
    )
    print(f"   batch-controlled balanced accuracy: {sub_best[1]['balancedAccuracy']:.3f} "
          f"({sub_best[0]})")

    save_json(EVAL / "phase9_osd46_radiation.json", {
        "phase": 9, "study": "OSD-46",
        "samples": int(x_all.shape[0]), "genes": int(x_all.shape[1]),
        "groups": int(len(np.unique(groups_all))),
        "validationScheme": "leave-one-biological-group-out",
        "models": [evaluation_a1, evaluation_a2],
    })
    print("\nwrote ml/evaluation/phase9_osd46_radiation.json")


if __name__ == "__main__":
    main()
