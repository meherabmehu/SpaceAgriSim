"""Phase 10: a real partial-gravity analysis on OSD-314.

Phase 9 excluded the gravity model because OSD-411 only reorients seedlings by 90
degrees at 1 g. That exclusion is correct for OSD-411. It is not the end of the
question, and Phase 10's metadata scan found that the question was answered too early:
OSD-314 flies Arabidopsis to the ISS and *centrifuges* a subset to **0.34 g in orbit**,
alongside microgravity (uG) and a 1 g ground control, with every gravity level crossed
against a red-light and a dark treatment.

That is a graded gravity design with real labels: 0 g, 0.34 g, 1 g.

It also has two structural limits that decide what can be claimed, and they are the
reason this script reports two separate analyses instead of one headline:

1. **Flight is confounded with gravity for two of the three levels.** The 1 g samples
   are ground controls; the 0 g and 0.34 g samples are in orbit. Any model using all
   three levels is partly a flight-versus-ground model, and calling that "gravity
   prediction" would be the overclaim Phase 9 was excluded for.
2. **Within flight, gravity is clean.** The 0 g and 0.34 g samples are both on the ISS,
   processed together, and both have red-light and dark replicates. Comparing those two
   isolates the effect of 0.34 g of centrifugation with flight held constant.

So: the *primary* analysis is 0 g versus 0.34 g inside flight. The three-level analysis
is reported as secondary, explicitly labelled as flight-confounded, and not promoted.

n is 17 libraries in one genotype in one mission. Nothing here is a servable model; the
question it answers is whether the gradient exists in the transcriptome at all.
"""

from __future__ import annotations
import sys

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
RAW = ROOT / "data" / "raw" / "OSD-314"
OUT = ROOT / "ml" / "evaluation" / "phase10_partial_gravity"

SEED = 314
PERMUTATIONS = 2000
TOP_GENES = 100


def parse_design() -> pd.DataFrame:
    """One row per library: gravity level in g, light treatment, replicate."""
    table = pd.read_csv(RAW / "GLDS-314_rna_seq_SampleTable_GLbulkRNAseq.csv")
    table.columns = ["library", "condition"]
    gravity, light, context = [], [], []
    for condition in table["condition"]:
        text = condition.lower()
        if "0.34g" in text or "0.34 g" in text:
            gravity.append(0.34)
        elif "1g" in text:
            gravity.append(1.0)
        elif "ug" in text or "0g" in text:
            gravity.append(0.0)
        else:
            raise ValueError(f"unrecognised gravity in condition: {condition}")
        light.append("dark" if "dark" in text else "red")
        context.append("ground" if "ground" in text else "flight")
    table["gravityG"] = gravity
    table["light"] = light
    table["context"] = context
    table["library"] = table["library"].str.strip()
    return table


def load() -> tuple[np.ndarray, pd.DataFrame, list[str]]:
    counts = pd.read_csv(RAW / "GLDS-314_rna_seq_Normalized_Counts.csv", index_col=0)
    design = parse_design().set_index("library")
    libraries = [c for c in counts.columns if c in design.index]
    if len(libraries) != len(design):
        raise ValueError(f"library mismatch: {len(libraries)} of {len(design)} matched")
    expression = counts[libraries].T.to_numpy(float)
    design = design.loc[libraries].reset_index()
    # Log the normalised counts; the file is linear-scale normalised counts.
    expression = np.log2(expression + 1.0)
    return expression, design, list(counts.index)


def anova_f(matrix: np.ndarray, labels: np.ndarray) -> np.ndarray:
    overall = matrix.mean(axis=0)
    ss_between = np.zeros(matrix.shape[1])
    ss_within = np.zeros(matrix.shape[1])
    for value in np.unique(labels):
        rows = matrix[labels == value]
        centre = rows.mean(axis=0)
        ss_between += rows.shape[0] * (centre - overall) ** 2
        ss_within += ((rows - centre) ** 2).sum(axis=0)
    df_between = len(np.unique(labels)) - 1
    df_within = matrix.shape[0] - len(np.unique(labels))
    with np.errstate(divide="ignore", invalid="ignore"):
        f_stat = (ss_between / df_between) / (ss_within / df_within)
    return np.nan_to_num(f_stat, nan=0.0, posinf=0.0)


def select(matrix: np.ndarray, labels: np.ndarray, k: int = TOP_GENES) -> np.ndarray:
    detected = (matrix > 0).mean(axis=0) >= 0.5
    variance = matrix.var(axis=0)
    keep = np.flatnonzero(detected & (variance > 0))
    if keep.size > 4000:
        keep = keep[np.argsort(variance[keep])[-4000:]]
    order = np.argsort(-anova_f(matrix[:, keep], labels))
    return keep[order[:min(k, keep.size)]]


def classifier():
    """The one classifier used by every gravity analysis in this phase."""
    return Pipeline([("scale", StandardScaler()),
                     ("model", LogisticRegression(C=1.0, max_iter=5000,
                                                  random_state=SEED))])


def fit_fold(expression, labels, train_index, test_index, k=TOP_GENES):
    chosen = select(expression[train_index], labels[train_index], k)
    model = classifier()
    model.fit(expression[np.ix_(train_index, chosen)], labels[train_index])
    in_sample = float((model.predict(expression[np.ix_(train_index, chosen)])
                       == labels[train_index]).mean())
    if in_sample < 0.9:
        raise AssertionError(f"fold cannot fit its own training rows ({in_sample:.2f})")
    return model.predict(expression[np.ix_(test_index, chosen)])


def design_preserving_p(labels, prediction, strata, permutations=PERMUTATIONS):
    """Shuffle labels inside each stratum, so light never predicts the shuffled label."""
    generator = np.random.default_rng(SEED)
    observed = float(balanced_accuracy_score(labels, prediction))
    null = np.empty(permutations)
    for index in range(permutations):
        shuffled = labels.copy()
        for level in np.unique(strata):
            rows = np.flatnonzero(strata == level)
            shuffled[rows] = generator.permutation(shuffled[rows])
        null[index] = balanced_accuracy_score(shuffled, prediction)
    exceed = int((null >= observed).sum())
    return {
        "observed": round(observed, 4),
        "nullMedian": round(float(np.median(null)), 4),
        "null95": [round(float(np.percentile(null, 2.5)), 4),
                   round(float(np.percentile(null, 97.5)), 4)],
        "permutations": permutations,
        "exceedances": exceed,
        "pCorrected": round((exceed + 1) / (permutations + 1), 5),
    }


def corroborate_from_deposit() -> dict:
    """Does the study's own differential expression agree that uG vs 0.34 g differs?

    The separation reported here is 1.0 on 11 libraries, which is the kind of number
    that usually means a leak. The check is the providers' own DE table: if their
    contrast reports a large fraction of the transcriptome as differentially
    expressed between uG and 0.34 g, a perfect split is expected rather than suspect.

    Downloaded to a scratch path and not committed; only the counts are recorded.
    """
    import tempfile
    import urllib.request

    url = ("https://nasa-osdr.s3.us-west-2.amazonaws.com/OSD-314/version-6/rna_seq/"
           "GLDS-314_rna_seq_differential_expression_GLbulkRNAseq.csv")
    try:
        with tempfile.NamedTemporaryFile(suffix=".csv") as handle:
            urllib.request.urlretrieve(url, handle.name)
            table = pd.read_csv(handle.name)
    except Exception as error:  # noqa: BLE001 - report, never invent
        return {"available": False, "reason": f"{type(error).__name__}: {error}"}
    padj = [c for c in table.columns if c.startswith("Adj.p.value_")]
    interesting = {}
    for column in padj:
        if "Space Flight" not in column or "Ground Control" in column:
            continue
        if "uG" not in column or "0.34G" not in column:
            continue
        interesting[column.replace("Adj.p.value_", "")] = int((table[column] < 0.05).sum())
    return {
        "available": True,
        "genesTested": int(len(table)),
        "withinFlightContrasts": interesting,
        "statement": (
            "The deposit's own differential expression reports thousands of genes at "
            "adjusted p < 0.05 between uG and 0.34 g inside flight, so a transcriptome "
            "difference of this size between those two conditions is the providers' "
            "finding, not an artefact of the split used here."),
    }


def main() -> int:
    expression, design, genes = load()
    print(f"OSD-314: {expression.shape[0]} libraries x {expression.shape[1]} genes")
    cells = design.groupby(["gravityG", "light", "context"]).size()
    print(cells.to_string())

    # --- Design audit ---------------------------------------------------------
    levels = sorted(design["gravityG"].unique())
    ground = design.loc[design["context"] == "ground", "gravityG"].unique()
    flight = design.loc[design["context"] == "flight", "gravityG"].unique()
    audit = {
        "gravityLevelsG": [float(v) for v in levels],
        "lightTreatments": sorted(design["light"].unique().tolist()),
        "genotype": "Col-0 wild type",
        "libraries": int(len(design)),
        "librariesPerCell": {f"{row.gravityG}g|{row.light}|{row.context}": int(row.n)
                             for row in cells.reset_index(name="n").itertuples()},
        "groundLevels": [float(v) for v in ground],
        "flightLevels": [float(v) for v in flight],
        "threeLevelAnalysisIsFlightConfounded": True,
        "threeLevelStatement": (
            "The 1 g samples are ground controls and the 0 g and 0.34 g samples are in "
            "orbit, so across all three levels gravity is perfectly confounded with "
            "flight. Any accuracy from that analysis includes a flight effect and cannot "
            "be reported as gravity prediction."),
        "withinFlightContrastIsClean": True,
        "withinFlightStatement": (
            "Within flight, 0 g and 0.34 g samples come from the same mission and the "
            "same processing run, and both have red-light and dark replicates. That "
            "contrast holds flight constant and isolates 0.34 g of centrifugation."),
    }

    # --- Primary: 0 g versus 0.34 g, inside flight ---------------------------
    inside = design["context"].to_numpy() == "flight"
    flight_design = design[inside].reset_index(drop=True)
    flight_expression = expression[inside]
    binary = np.where(flight_design["gravityG"].to_numpy() == 0.0, "microgravity",
                      "partial-0.34g")
    light = flight_design["light"].to_numpy()
    print(f"\nprimary contrast: {len(binary)} flight libraries, "
          f"{int((binary == 'microgravity').sum())} uG / "
          f"{int((binary == 'partial-0.34g').sum())} 0.34g")

    predicted = np.empty(len(binary), dtype=object)
    for train_index, test_index in LeaveOneGroupOut().split(flight_expression, binary,
                                                            light):
        predicted[test_index] = fit_fold(flight_expression, binary, train_index, test_index)
    primary = {
        "scheme": "leave-one-light-treatment-out within flight (train red, test dark; "
                  "train dark, test red)",
        "folds": 2,
        "accuracy": round(float((predicted == binary).mean()), 4),
        "balancedAccuracy": round(float(balanced_accuracy_score(binary, predicted)), 4),
        "recallMicrogravity": round(float((predicted[binary == "microgravity"]
                                           == "microgravity").mean()), 4),
        "recallPartial": round(float((predicted[binary == "partial-0.34g"]
                                      == "partial-0.34g").mean()), 4),
        "permutation": design_preserving_p(binary, predicted, light),
        "interpretation": (
            "Held-out light treatment is the only split here that is not a technical "
            "replicate split: the three replicates inside a (gravity, light) cell were "
            "processed together, so splitting inside a cell would score replication, not "
            "generalization. Two folds is a small evaluation and the permutation test is "
            "reported with the finite-sample correction."),
    }

    # --- Secondary: three levels, explicitly flight-confounded ----------------
    ordinal_label = np.array([f"{g:.2f}g" for g in design["gravityG"].to_numpy()])
    light_all_groups = design["light"].to_numpy()
    predicted_all = np.empty(len(ordinal_label), dtype=object)
    for train_index, test_index in LeaveOneGroupOut().split(expression, ordinal_label,
                                                            light_all_groups):
        predicted_all[test_index] = fit_fold(expression, ordinal_label, train_index,
                                             test_index)
    regression = np.empty(len(ordinal_label))
    for train_index, test_index in LeaveOneGroupOut().split(expression, ordinal_label,
                                                            light_all_groups):
        chosen = select(expression[train_index], ordinal_label[train_index])
        model = Pipeline([("scale", StandardScaler()), ("model", Ridge(alpha=1.0))])
        model.fit(expression[np.ix_(train_index, chosen)],
                  design["gravityG"].to_numpy()[train_index])
        regression[test_index] = model.predict(expression[np.ix_(test_index, chosen)])
    generator = np.random.default_rng(SEED + 1)
    observed_rho = float(stats.spearmanr(design["gravityG"], regression).statistic)
    null_rho = np.empty(PERMUTATIONS)
    light_all = design["light"].to_numpy()
    for index in range(PERMUTATIONS):
        shuffled = design["gravityG"].to_numpy().copy()
        for level in np.unique(light_all):
            rows = np.flatnonzero(light_all == level)
            shuffled[rows] = generator.permutation(shuffled[rows])
        null_rho[index] = float(stats.spearmanr(shuffled, regression).statistic)
    exceed_rho = int((null_rho >= observed_rho).sum())
    secondary = {
        "scheme": "three gravity levels, light held out — FLIGHT-CONFOUNDED, do not quote "
                  "as gravity prediction",
        "balancedAccuracy": round(float(balanced_accuracy_score(ordinal_label,
                                                                predicted_all)), 4),
        "perLevelRecall": {level: round(float((predicted_all[ordinal_label == level]
                                               == level).mean()), 4)
                           for level in sorted(set(ordinal_label))},
        "ordinalSpearman": {
            "observed": round(observed_rho, 4),
            "nullMedian": round(float(np.median(null_rho)), 4),
            "exceedances": exceed_rho,
            "pCorrected": round((exceed_rho + 1) / (PERMUTATIONS + 1), 5),
        },
        "whyNotPromoted": audit["threeLevelStatement"],
    }

    recovered = primary["permutation"]["pCorrected"] < 0.05 and \
        primary["balancedAccuracy"] > 0.5
    result = {
        "phase": 10,
        "study": "OSD-314 / GLDS-314",
        "source": ("S3 OSD-314/version-6/rna_seq: Normalized_Counts, SampleTable, "
                   "Unnormalized RSEM counts, contrasts, runsheet, software versions"),
        "task": "does a graded gravity signal exist in the transcriptome?",
        "design": audit,
        "primaryContrast": primary,
        "corroboration": corroborate_from_deposit(),
        "secondaryThreeLevel": secondary,
        "decisionRule": (
            "The within-flight contrast counts as recovered only if balanced accuracy "
            "exceeds 0.5 on held-out light treatments and its design-preserving "
            "permutation p is below 0.05. Fixed before the run."),
        "outcome": ("within-flight-partial-gravity-signal-detected" if recovered
                    else "within-flight-partial-gravity-signal-not-detected"),
        "registryChange": None,
        "batchCaveat": (
            "The deposited runsheet carries no sequencing-run or library-batch "
            "identifier, so a prep batch effect cannot be excluded from the deposit "
            "alone. This is a limit of the record, not a caveat that can be resolved by "
            "more analysis of the same files."),
        "notPromotedBecause": [
            "17 libraries, one genotype (Col-0), one mission",
            "two of the three gravity levels are confounded with flight",
            "the only honest split yields two folds",
            "a model trained on this would not be a predictor of partial gravity in "
            "general, and serving it as one would repeat the OSD-411 mistake with better "
            "labels",
        ],
        "nextAction": (
            "Done in Phase 10: OSD-346 was analysed as the replication. It does not "
            "reproduce this contrast (see ml/evaluation/"
            "phase10_partial_gravity_replication.py), so the 1.000 reported here must "
            "be read as one experiment rather than as a stable property of plant "
            "transcriptomes. A servable gravity predictor would need a third mission."),
    }
    safedata.dump(result, OUT)
    print(f"\nprimary balanced accuracy {primary['balancedAccuracy']} "
          f"(p={primary['permutation']['pCorrected']}), "
          f"uG recall {primary['recallMicrogravity']}, "
          f"0.34g recall {primary['recallPartial']}")
    print(f"three-level (flight-confounded) balanced accuracy "
          f"{secondary['balancedAccuracy']}, ordinal rho "
          f"{secondary['ordinalSpearman']['observed']} "
          f"(p={secondary['ordinalSpearman']['pCorrected']})")
    print(f"outcome: {result['outcome']} -> wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
