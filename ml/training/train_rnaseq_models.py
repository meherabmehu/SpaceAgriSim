"""Phase 9 Models B and C: RNA-seq classifiers for radiation dose and gravity.

Two independent NASA OSDR RNA-seq studies, each evaluated with the same harness
used for OSD-46 so the numbers are comparable across models.

Model B - OSD-782, radiation dose
    Wild-type Arabidopsis rosette, Cs-137 gamma at three *absorbed dose* levels
    (0 / 10 / 100 Gy) across four collection times. Unlike OSD-46, where the two
    irradiated arms differ in both quality and dose, here the radiation quality is
    held constant and only the dose changes. That makes it a cleaner test of
    "is dose level recoverable from expression", and it is the reason the two
    studies support different claims.

Model C - OSD-411, gravity reorientation
    Arabidopsis (Col-0) wild type and the starch-less pgm-1 mutant, four tissues,
    either reoriented by 90 degrees or held vertical. pgm-1 cannot sediment
    amyloplasts and is therefore the classical genetic control for gravity sensing,
    so this design asks whether a reorientation signature exists and whether it
    depends on the genotype known to be required for perception.

    A 90-degree reorientation on the ground is NOT partial gravity. The label is
    "was the seedling reoriented", and no Moon/Mars claim is made anywhere.

Run: python ml/training/train_rnaseq_models.py
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

PROCESSED = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
EVAL = ROOT / "ml" / "evaluation"
ARTIFACTS = ROOT / "ml" / "artifacts"


def load_counts(path: Path) -> pd.DataFrame:
    """Read an OSDR RSEM unnormalised count matrix as genes x samples."""
    frame = pd.read_csv(path, index_col=0)
    frame.index.name = "gene"
    frame = frame[~frame.index.duplicated(keep="first")]
    return frame


def cpm_log2(counts: pd.DataFrame) -> pd.DataFrame:
    """Library-size normalisation then log2.

    CPM is used rather than raw counts because the samples have visibly different
    sequencing depth (the study's own QC reports a wide range). log2(CPM+1) then
    stabilises the variance enough for a linear model. Both steps are unsupervised
    and use no labels, so computing them once up front cannot leak test information
    the way a supervised transform would.
    """
    library = counts.sum(axis=0)
    if (library <= 0).any():
        raise SystemExit("Empty library detected")
    cpm = counts.divide(library, axis=1) * 1e6
    return np.log2(cpm + 1.0)


# Samples with a library below this are excluded. Applied before any modelling and
# reported, so the exclusion cannot be confused with silent data loss.
MIN_LIBRARY_READS = 5_000_000


def qc_report(counts: pd.DataFrame, annotation: pd.DataFrame) -> tuple[list[str], dict]:
    """Library-depth QC. Returns (kept samples, report)."""
    library = counts.sum(axis=0)
    low = [str(s) for s in library.index[library < MIN_LIBRARY_READS]]
    return ([c for c in counts.columns if c not in low], {
        "thresholdReads": MIN_LIBRARY_READS,
        "excludedSamples": low,
        "excludedDetail": {
            str(s): {
                "libraryReads": int(library[s]),
                "genotype": str(annotation.loc[s, "genotype"]) if "genotype" in annotation else "",
                "condition": str(annotation.loc[s].to_dict()),
            } for s in low
        },
        "retainedSamples": int(len(counts.columns) - len(low)),
    })


def build_osd782() -> dict:
    # GeneLab's own variance-stabilising transform is used rather than a bespoke
    # CPM computation: it is the study's published processed product (DESeq2 VST),
    # so the input to the model is reproducible from the archive without re-deriving
    # a normalisation.
    counts = load_counts(RAW / "OSD-782" / "GLDS-679_rna_seq_VST_Counts_GLbulkRNAseq.csv")
    annotation = pd.read_csv(PROCESSED / "osd782_radiation_samples.csv", dtype=str)
    annotation = annotation.set_index("sample").loc[list(counts.columns)]
    raw_counts = load_counts(RAW / "OSD-782" / "GLDS-679_rna_seq_RSEM_Unnormalized_Counts_GLbulkRNAseq.csv")
    keep, qc = qc_report(raw_counts, annotation)
    expressed = counts[keep]
    expressed = expressed[expressed.var(axis=1) > 0]
    y = np.array([f"{int(float(d))} Gy" for d in annotation["absorbedDoseGy"]])
    groups = (annotation["absorbedDoseGy"].astype(str) + "|"
              + annotation["hoursAfterTreatment"].astype(str)).to_numpy()
    return {
        "x": expressed.to_numpy().T, "y": y, "groups": groups,
        "genes": list(expressed.index), "samples": list(expressed.columns),
        "annotation": annotation.loc[expressed.columns], "classes": ["0 Gy", "10 Gy", "100 Gy"],
        "normalisation": "GeneLab DESeq2 variance-stabilising transform (published processed product)",
        "qc": qc,
    }


def build_osd411() -> dict:
    counts = load_counts(RAW / "OSD-411" / "GLDS-411_rna_seq_RSEM_Unnormalized_Counts_GLbulkRNAseq.csv")
    annotation = pd.read_csv(PROCESSED / "osd411_gravity_samples.csv", dtype=str)
    annotation = annotation.set_index("sample").loc[list(counts.columns)]
    keep, qc = qc_report(counts, annotation)
    # One sample (14-4, WT cotyledon reoriented) has 0.26 M reads against a ~33 M
    # median. CPM cannot rescue a library that thin, so it is excluded and reported
    # rather than left in to distort the variance structure.
    expressed = cpm_log2(counts[keep])
    expressed = expressed[(expressed > 0).mean(axis=1) >= 0.25]
    annotation = annotation.loc[keep]
    y = np.array([("reoriented" if t == "Reoriented" else "vertical")
                  for t in annotation["treatment"]])
    # Biological group: genotype x tissue x treatment. The four replicate numbers
    # (e.g. 1-1..1-4) are the replicates; pooling tissues or genotypes into a group
    # would let the same plant's tissue types straddle the split.
    groups = (annotation["genotype"].fillna("NA").astype(str) + "|"
              + annotation["organismPart"].fillna("NA").astype(str) + "|"
              + annotation["treatment"].fillna("NA").astype(str)).to_numpy()
    return {
        "x": expressed.to_numpy().T, "y": y, "groups": groups,
        "genes": list(expressed.index), "samples": list(expressed.columns),
        "annotation": annotation, "classes": ["reoriented", "vertical"],
        "normalisation": "log2(CPM + 1), computed unsupervised before splitting",
        "qc": qc,
    }


def train(name: str, data: dict, model_id: str, study: str, study_url: str,
          task: str, limitations: list[str], recommended_use: str,
          n_splits: int) -> dict:
    x, y, groups, genes = data["x"], data["y"], data["groups"], data["genes"]
    print(f"\n=== {model_id} ({study}): {x.shape[0]} samples x {x.shape[1]} genes, "
          f"{len(np.unique(groups))} groups")
    print("   labels:", dict(zip(*[a.tolist() for a in np.unique(y, return_counts=True)])))

    learners = H.classification_learners()
    results = H.summarize_learners(x, y, groups, genes, n_splits=n_splits)
    for lname, report in results.items():
        print(f"   {lname:20s} acc {report['accuracy']:.3f}  "
              f"bal {report['balancedAccuracy']:.3f}  macroF1 {report['macroF1']:.3f}")

    baseline = results["baseline_majority"]["accuracy"]
    ranking = sorted(((n, r) for n, r in results.items() if n != "baseline_majority"),
                     key=lambda kv: kv[1]["balancedAccuracy"], reverse=True)
    best_name, best = ranking[0]
    permutation = H.permutation_test(x, y, groups, learners[best_name],
                                     observed=best["accuracy"], n_permutations=200,
                                     n_splits=n_splits)
    print(f"   best: {best_name} bal {best['balancedAccuracy']:.3f}; "
          f"permutation p = {permutation['pValue']:.4f}")

    beats = best["balancedAccuracy"] > results["baseline_majority"]["balancedAccuracy"]
    significant = permutation["pValue"] <= 0.05
    status = "experimental" if (beats and significant) else "insufficient-evidence"

    chosen = H.select_features(x, y, genes)
    final = learners[best_name]().fit(x[:, chosen], y)
    evaluator = H.extract_linear_evaluator(final, [genes[i] for i in chosen])

    artifact = {
        "id": model_id,
        "name": name,
        "version": "1.0.0",
        "trainedAt": stamp(),
        "sourceStudy": study,
        "sourceUrl": study_url,
        "sourceType": "NASA OSDR bulk RNA-seq (GeneLab)",
        "organism": "Arabidopsis thaliana",
        "platform": "Illumina bulk RNA-seq, RSEM unnormalised gene counts",
        "task": task,
        "classLabels": [str(c) for c in np.unique(y)],
        "samples": int(x.shape[0]),
        "groups": int(len(np.unique(groups))),
        "genesAvailable": int(x.shape[1]),
        "genesSelected": len(chosen),
        "features": [genes[i] for i in chosen],
        "normalisation": data.get("normalisation", "log2(CPM + 1)"),
        "qualityControl": data.get("qc"),
        "method": f"{best_name} with in-fold ANOVA gene selection",
        "evidenceStatus": status,
        "metrics": best,
        "baselineMetrics": results["baseline_majority"],
        "allLearners": {n: {k: r[k] for k in ("accuracy", "balancedAccuracy", "macroF1",
                                              "perGroupRecall")}
                        for n, r in results.items()},
        "permutationTest": permutation,
        "beatsBaseline": bool(beats),
        "validation": (f"Stratified group CV ({n_splits} folds) over "
                       f"{len(np.unique(groups))} biological groups with in-fold gene "
                       "selection. No independent study is used here."),
        "seed": H.SEED,
        "environment": {"python": sys.version.split()[0], "numpy": np.__version__,
                        "pandas": pd.__version__, "sklearn": sklearn.__version__},
        "evaluator": evaluator,
        "domain": {
            "note": ("Inputs are log2(CPM+1) values for the genes listed in 'features'. "
                     "All of them must be supplied."),
            "expressionRange": {"min": float(x[:, chosen].min()), "max": float(x[:, chosen].max())},
        },
        "limitations": limitations,
        "recommendedUse": recommended_use,
    }

    body = json.dumps(artifact, separators=(",", ":"), allow_nan=False)
    (ARTIFACTS / f"{model_id}.json").write_text(body + "\n", encoding="utf-8")
    digest = hashlib.sha256((body + "\n").encode()).hexdigest()

    save_json(EVAL / f"phase9_{study.lower().replace('-', '')}.json", {
        "phase": 9, "modelId": model_id, "study": study,
        "samples": int(x.shape[0]), "groups": int(len(np.unique(groups))),
        "learners": results, "best": best_name, "permutationTest": permutation,
        "evidenceStatus": status, "artifactSha256": digest,
    })
    print(f"   wrote {model_id}.json ({len(body):,} B) status={status}")

    # A model that failed to beat its baseline under the pre-specified scheme is
    # NOT registered. Keeping it out of the registry is the exclusion the brief
    # asks for: the artifact and its evaluation remain on disk as evidence of the
    # negative result, but no prediction endpoint is exposed for it.
    if status != "experimental":
        print(f"   NOT REGISTERED: status '{status}' - evidence retained only, "
              f"no prediction endpoint exposed")
        return artifact

    registry_path = ARTIFACTS / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["models"] = [m for m in registry["models"] if m["id"] != model_id]
    registry["models"].append({"id": model_id,
                               "artifact": f"ml/artifacts/{model_id}.json",
                               "sha256": digest})
    registry["trainedAt"] = stamp()
    registry_path.write_text(json.dumps(registry, indent=1) + "\n", encoding="utf-8")
    return artifact


def main() -> None:
    train(
        name="Arabidopsis radiation dose classifier (OSD-782)",
        data=build_osd782(), model_id="radiation-dose-osd782-v1", study="OSD-782",
        study_url="https://osdr.nasa.gov/bio/repo/data/studies/OSD-782",
        task="Three-class absorbed-dose classification (0 / 10 / 100 Gy) from rosette expression",
        limitations=[
            "Ground irradiation of Arabidopsis rosette tissue, not spaceflight and not a crop.",
            "Wild-type only; no genotype contrast is available in this study.",
            "Three discrete dose levels (0, 10, 100 Gy); this is NOT a continuous dose-response model and cannot interpolate between levels.",
            "Gamma only: no HZE arm, so nothing here transfers to heavy-ion exposure.",
            "Doses are far above any realistic habitat chronic exposure; this is acute high-dose biology.",
            "Predicts the applied dose class, not damage severity, survival, yield or biomass.",
        ],
        recommended_use=("Demonstrating that acute gamma dose level is recoverable from a "
                         "rosette expression profile across held-out biological groups."),
        n_splits=4,
    )
    train(
        name="Arabidopsis gravity reorientation classifier (OSD-411)",
        data=build_osd411(), model_id="gravity-reorientation-osd411-v1", study="OSD-411",
        study_url="https://osdr.nasa.gov/bio/repo/data/studies/OSD-411",
        task="Binary reoriented-versus-vertical classification across four tissues",
        limitations=[
            "90-degree ground reorientation is NOT partial gravity; no Moon or Mars inference is supported.",
            "Ground study using a custom rotation device; no spaceflight microgravity data in this study.",
            "Two genotypes only (Col-0 wild type and the starch-less pgm-1 mutant).",
            "Four tissues are pooled in the label; the model does not identify tissue-specific mechanisms.",
            "Predicts the applied reorientation treatment, not gravitropic curvature, growth rate or yield.",
            "A classifier separating reoriented from vertical tissue may be reading the handling/rotation procedure as much as the gravity response itself.",
        ],
        recommended_use=("Testing whether a reorientation molecular signature is recoverable "
                         "in held-out genotype x tissue groups, and whether it persists in the "
                         "pgm-1 perception mutant."),
        n_splits=4,
    )


if __name__ == "__main__":
    main()
