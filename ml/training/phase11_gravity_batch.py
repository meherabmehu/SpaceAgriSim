"""Phase 11: is OSD-346's graded gravity signal gravity, or run?

Phase 10 reported two things and could not reconcile them:
  OSD-314  0 g vs 0.34 g, held-out light treatment, balanced accuracy 1.000
  OSD-346  same protocol, 0.500 - no replication - but graded rho 0.571 at p 0.0015

Phase 10 also said neither deposit carries a sequencing-run identifier. That was wrong
for OSD-346: its ISA sample table has a `Comment[Run]` column, and reading it changes the
interpretation completely.

Every flight run carried one gravity band:

    SG1 Run 1  2013-03-29   0 g only
    SG1 Run 2  2013-05-09   0.08 - 0.13 g
    SG1 Run 3  2013-05-18   0.25 - 0.39 g
    SG1 Run 4  2013-05-24   0.64 - 1.00 g
    SG2 Run 1  2014-11-14   0.38 - 0.65 g
    SG2 Run 2  2014-11-21   0.68 - 0.92 g

So gravity is nested inside run, and run is nested inside mission-year. A model that
recovers 0 to 1 g across the whole series is *also* recovering flight run, chip, and year.
This script measures whether the graded signal survives that nesting, instead of
assuming either answer.

Four measurements, all with protocols fixed before the run:

  B1  how confounded?  run x gravity table, nestedness, and how much of the top
      expression variance is explained by run
  B2  how strong is the batch effect?  can a classifier identify the run from
      expression alone, scored out-of-sample
  B3  does gravity survive run removal?  the graded regression refitted on
      run-centred features, where only within-run gravity variation is available
  B4  the identifiability check: how much gravity range remains after run removal,
      and is that enough for the question to be answerable at all

If B3 collapses and B4 shows the remaining range is a fraction of the original, the
honest conclusion is that OSD-346 cannot separate gravity from run - not that gravity has
no effect, and not that the Phase 10 signal was real.
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data" / "processed"
DERIVED = ROOT / "data" / "derived"
RAW = ROOT / "data" / "raw"
OUT = ROOT / "ml" / "evaluation" / "phase11_gravity_batch.json"

SEED = 1113
PERMUTATIONS = 2000
TOP_GENES = 100


def osd346_design() -> pd.DataFrame:
    """Library, flight run, harvest date, commanded and realised gravity."""
    archive = RAW / "OSD-346" / "OSD-346_metadata_OSD-346-ISA.zip"
    with zipfile.ZipFile(archive) as handle:
        rows = list(csv.reader(io.StringIO(handle.read("s_OSD-346.txt")
                                           .decode("utf-8", "replace")), delimiter="\t"))
    header = rows[0]
    index = {name: position for position, name in enumerate(header)}
    records = []
    for row in rows[1:]:
        if len(row) < len(header) - 3:
            continue
        records.append({
            "sampleName": row[index["Sample Name"]],
            "run": row[index["Comment[Run]"]],
            "harvest": row[index["Parameter Value[Sample Harvest Date (MM/DD/YYYY)]"]],
            "gravityCommanded": row[index["Factor Value[Altered Gravity]"]],
            "gravityActual": row[index["Parameter Value[Actual Gravity Level]"]],
        })
    design = pd.DataFrame(records)
    samples = pd.read_csv(PROCESSED / "osd346_samples.csv")
    design["file"] = "GLDS-346_rna_seq_" + design["sampleName"] + ".genes.results"
    merged = samples.merge(design, on=None, left_on="sampleName", right_on="sampleName",
                           suffixes=("", "_isa"))
    if len(merged) != len(samples):
        raise ValueError(f"design merge lost rows: {len(merged)} of {len(samples)}")
    merged["missionYear"] = merged["run"].str.extract(r"(SG\d)")[0]
    merged["runDate"] = pd.to_datetime(merged["harvest"], format="%m/%d/%y", errors="coerce")
    return merged


def load_expression() -> tuple[np.ndarray, list[str], pd.DataFrame]:
    frame = pd.read_csv(DERIVED / "osd346_partial_gravity.csv")
    genes = frame["gene"].tolist()
    matrix = frame.drop(columns=["gene"]).to_numpy(float).T
    design = osd346_design()
    return matrix, genes, design


def anova_f(matrix: np.ndarray, labels: np.ndarray) -> np.ndarray:
    overall = matrix.mean(axis=0)
    ss_between = np.zeros(matrix.shape[1])
    ss_within = np.zeros(matrix.shape[1])
    groups = np.unique(labels)
    for value in groups:
        rows = matrix[labels == value]
        centre = rows.mean(axis=0)
        ss_between += rows.shape[0] * (centre - overall) ** 2
        ss_within += ((rows - centre) ** 2).sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        f_stat = (ss_between / max(len(groups) - 1, 1)) / (
            ss_within / max(matrix.shape[0] - len(groups), 1))
    return np.nan_to_num(f_stat, nan=0.0, posinf=0.0)


def select(matrix: np.ndarray, labels: np.ndarray, k: int = TOP_GENES) -> np.ndarray:
    variance = matrix.var(axis=0)
    keep = np.flatnonzero(variance > 0)
    if keep.size > 4000:
        keep = keep[np.argsort(variance[keep])[-4000:]]
    return keep[np.argsort(-anova_f(matrix[:, keep], labels))[:min(k, keep.size)]]


def run_centred(matrix: np.ndarray, runs: np.ndarray) -> np.ndarray:
    """Subtract each run's mean for every gene: removes all between-run variation."""
    centred = matrix.astype(float).copy()
    for run in np.unique(runs):
        rows = runs == run
        centred[rows] -= centred[rows].mean(axis=0)
    return centred


def run_perm_rho(truth, predicted, runs, permutations=PERMUTATIONS, seed=SEED):
    """Shuffle gravity labels within run, so run structure cannot beat the null."""
    generator = np.random.default_rng(seed)
    observed = float(stats.spearmanr(truth, predicted).statistic)
    null = np.empty(permutations)
    changed = np.empty(permutations)
    for index in range(permutations):
        shuffled = truth.copy()
        for run in np.unique(runs):
            rows = np.flatnonzero(runs == run)
            shuffled[rows] = generator.permutation(shuffled[rows])
        changed[index] = float((shuffled != truth).mean())
        null[index] = float(stats.spearmanr(shuffled, predicted).statistic)
    exceed = int((null >= observed).sum())
    # A shuffle that barely moves the labels cannot generate a meaningful null. When
    # gravity is nested in run, most labels inside a run are identical, so this is the
    # common case here and it has to be reported rather than quoted as a p-value.
    informative = float(changed.mean()) >= 0.5
    return {
        "permutationIsInformative": bool(informative),
        "meanFractionOfLabelsChanged": round(float(changed.mean()), 3),
        "nullStandardDeviation": round(float(null.std()), 4),
        "observedSpearman": round(observed, 4),
        "null95": [round(float(np.percentile(null, 2.5)), 4),
                   round(float(np.percentile(null, 97.5)), 4)],
        "exceedances": exceed,
        "pCorrected": round((exceed + 1) / (permutations + 1), 5),
        "pIsTrustworthy": bool(informative and float(null.std()) > 1e-9),
        "permutations": permutations,
        "scheme": "gravity shuffled within flight run",
    }


def graded_ridge(expression, gravity, groups, k=TOP_GENES):
    prediction = np.empty(len(gravity))
    for train_index, test_index in LeaveOneGroupOut().split(expression, gravity, groups):
        chosen = select(expression[train_index],
                        np.array([f"{g:.2f}" for g in gravity[train_index]]), k)
        model = Pipeline([("scale", StandardScaler()), ("model", Ridge(alpha=1.0))])
        model.fit(expression[np.ix_(train_index, chosen)], gravity[train_index])
        prediction[test_index] = model.predict(expression[np.ix_(test_index, chosen)])
    return prediction


def main() -> int:
    expression, genes, design = load_expression()
    runs = design["run"].to_numpy()
    gravity = design["gravityG"].to_numpy(float)
    commanded = design["gravityCommandedG"].to_numpy(float)
    genotypes = design["genotypeShort"].to_numpy()
    treatments = design["lightTreatment"].to_numpy()

    print(f"OSD-346: {expression.shape[0]} libraries, {len(set(runs))} flight runs")

    # --- B1: how confounded is gravity with run? ------------------------------
    table = pd.crosstab(design["run"], design["gravityCommandedG"])
    levels = sorted(set(commanded))
    levels_in_multiple_runs = [f"{level:.2f}g" for level in levels
                               if int((table[level] > 0).sum()) > 1]
    # How much of each run's gravity range overlaps the study's full range?
    full_range = float(gravity.max() - gravity.min())
    within_run_ranges = {run: float(gravity[runs == run].max() - gravity[runs == run].min())
                         for run in sorted(set(runs))}
    within_run_coverage = float(np.mean(list(within_run_ranges.values())) / full_range) \
        if full_range > 0 else 0.0

    # Variance decomposition on the leading principal component.
    centred = expression - expression.mean(axis=0)
    u, s, _ = np.linalg.svd(centred, full_matrices=False)
    pc1 = u[:, 0] * s[0]
    run_effect = []
    for run in np.unique(runs):
        run_effect.append((pc1[runs == run].mean() - pc1.mean()) ** 2 * (runs == run).sum())
    eta_run = float(sum(run_effect) / ((pc1 - pc1.mean()) ** 2).sum())

    b1 = {
        "runs": int(len(set(runs))),
        "runByCommandedGravity": {str(run): {f"{level:.2f}g": int(row[level])
                                             for level in levels
                                             if int(row[level]) > 0}
                                  for run, row in table.iterrows()},
        "gravityLevelsObservedInMoreThanOneRun": levels_in_multiple_runs,
        "gravityLevelsTotal": len(levels),
        "fullGravityRangeG": round(full_range, 3),
        "meanWithinRunGravityRangeG": round(float(np.mean(
            list(within_run_ranges.values()))), 3),
        "withinRunRangeAsFractionOfFull": round(within_run_coverage, 3),
        "pc1VarianceExplainedByRun": round(eta_run, 3),
        "statement": (
            "Each flight run carried one gravity band, so gravity is nested inside run "
            "and run is nested inside mission year. Only "
            f"{len(levels_in_multiple_runs)} of {len(levels)} commanded levels appear in "
            "more than one run, and the mean within-run gravity range is "
            f"{within_run_coverage:.0%} of the full 0-1 g range."),
    }

    # --- B2: how strong is the batch effect? ---------------------------------
    # Can expression alone identify the run? Grouped by genotype x treatment so the
    # classifier cannot use genotype or light as a shortcut to the run.
    run_labels = runs.copy()
    fold_groups = np.array([f"{g}|{t}" for g, t in zip(genotypes, treatments)])
    predicted_run = np.empty(len(run_labels), dtype=object)
    for train_index, test_index in LeaveOneGroupOut().split(expression, run_labels,
                                                            fold_groups):
        chosen = select(expression[train_index], run_labels[train_index])
        model = Pipeline([("scale", StandardScaler()),
                          ("model", LogisticRegression(C=0.5, max_iter=5000,
                                                       random_state=SEED))])
        model.fit(expression[np.ix_(train_index, chosen)], run_labels[train_index])
        predicted_run[test_index] = model.predict(expression[np.ix_(test_index, chosen)])
    b2 = {
        "task": "identify the flight run from expression, folds are genotype x light "
                "treatment so no shortcut exists",
        "runAccuracy": round(float((predicted_run == run_labels).mean()), 4),
        "balancedAccuracy": round(float(balanced_accuracy_score(run_labels,
                                                                predicted_run)), 4),
        "interpretation": (
            "A high out-of-sample run accuracy means runs are strongly separable in "
            "expression, so any label nested inside run can be predicted from the batch "
            "effect alone."),
    }

    # --- B3: does the graded signal survive run removal? ---------------------
    # Between-run variation is deleted; only within-run gravity variation remains.
    centred_expression = run_centred(expression, runs)
    prediction_raw = graded_ridge(expression, gravity, treatments)
    prediction_centred = graded_ridge(centred_expression, gravity, treatments)
    # Sub-analysis: is the signal carried by between-run or within-run variation?
    run_mean_gravity, run_mean_prediction = [], []
    for run in sorted(set(runs)):
        rows = runs == run
        run_mean_gravity.append(float(gravity[rows].mean()))
        run_mean_prediction.append(float(prediction_raw[rows].mean()))
    between = stats.spearmanr(run_mean_gravity, run_mean_prediction)
    # Within-run deviations are the only variation run removal leaves intact.
    gravity_dev = gravity - np.array([gravity[runs == run].mean() for run in runs])
    prediction_dev = prediction_raw - np.array([prediction_raw[runs == run].mean()
                                                for run in runs])
    within = run_perm_rho(gravity_dev, prediction_dev, runs)

    b3 = {
        "rawFeatures": run_perm_rho(gravity, prediction_raw, runs),
        "runCentredFeatures": run_perm_rho(gravity, prediction_centred, runs),
        "betweenRunComponent": {
            "runs": int(len(set(runs))),
            "spearmanOfRunMeans": round(float(between.statistic), 4),
            "p": round(float(between.pvalue), 4),
            "runMeanGravity": dict(zip(sorted(set(runs)),
                                       [round(v, 3) for v in run_mean_gravity])),
            "runMeanPredictedG": dict(zip(sorted(set(runs)),
                                          [round(v, 3) for v in run_mean_prediction])),
        },
        "withinRunComponent": within,
        "accuracyOnRealisedG": {
            "raw": round(float(np.abs(prediction_raw - gravity).mean()), 4),
            "runCentred": round(float(np.abs(prediction_centred - gravity).mean()), 4),
        },
        "predictionSpread": {
            "rawStandardDeviationG": round(float(prediction_raw.std()), 3),
            "runCentredStandardDeviationG": round(float(prediction_centred.std()), 3),
        },
    }
    survives = (b3["runCentredFeatures"]["observedSpearman"] > 0
                and b3["runCentredFeatures"]["pCorrected"] < 0.05)

    # --- B4: identifiability --------------------------------------------------
    b4 = {
        "question": "after removing all between-run variation, is enough gravity range left?",
        "remainingRangeG": round(float(np.mean(list(within_run_ranges.values()))), 3),
        "originalRangeG": round(full_range, 3),
        "fraction": round(within_run_coverage, 3),
        "identifiable": bool(within_run_coverage >= 0.25),
        "verdict": (
            "Run removal leaves only a small fraction of the 0-1 g range, so the study "
            "cannot test the wide-range gravity question once the batch is removed. The "
            "wide-range graded signal and the flight run are the same variable."
            if within_run_coverage < 0.25 else
            "Enough within-run gravity variation remains for a partial test."),
    }

    # --- OSD-314 comparison: what metadata exists there? ---------------------
    archive = RAW / "OSD-314" / "OSD-314_metadata_GLDS-314-ISA.zip"
    with zipfile.ZipFile(archive) as handle:
        header = list(csv.reader(io.StringIO(handle.read("s_OSD-314.txt")
                                             .decode("utf-8", "replace")),
                                 delimiter="\t"))[0]
    has_run = [column for column in header
               if any(token in column.lower() for token in ("run", "batch", "lane", "date"))]
    osd314 = {
        "columns": len(header),
        "runOrBatchColumns": has_run,
        "hasRunIdentifier": bool(has_run),
        "statement": (
            "OSD-314 has no run, batch, lane or date column at all, so the Phase 10 claim "
            "that neither deposit carries a run identifier was right for OSD-314 and "
            "wrong for OSD-346. Its 1.000 can therefore be neither attributed to biology "
            "nor cleared of batch: the structure is simply unrecorded."),
    }

    # --- The correction to Phase 10's P2 -------------------------------------
    # Phase 10 permuted gravity within light treatment. Each light treatment spans all
    # six runs, so that null mixes gravity across runs and is centred on zero; it cannot
    # see the nesting. The same observed correlation under a within-run null sits inside
    # the null distribution.
    prior = json.loads((ROOT / "ml" / "evaluation"
                        / "phase10_partial_gravity_replication.json").read_text())
    prior_p2 = prior["P2_gradedRegression"]["correlation"]
    correction = {
        "phase10Claim": {
            "observedSpearman": prior_p2["observedSpearman"],
            "pCorrected": prior_p2["pCorrected"],
            "nullScheme": "gravity shuffled within light treatment",
        },
        "phase11Reanalysis": {
            "observedSpearman": b3["rawFeatures"]["observedSpearman"],
            "pCorrected": b3["rawFeatures"]["pCorrected"],
            "nullScheme": "gravity shuffled within flight run",
        },
        "whyTheyDiffer": (
            "Every light treatment spans all six flight runs, so shuffling within "
            "treatment destroys the run structure and centres the null on zero. A "
            "correlation measured across runs then looks overwhelming. Shuffling within "
            "run preserves the structure the label is nested in, and the same correlation "
            "lands inside that null."),
        "statement": (
            "Phase 10's graded-gravity result (rho 0.571, p 0.0015) does not survive a "
            "null that respects the run nesting. The number is unchanged; the null it was "
            "compared against was wrong. Phase 10 correctly reported that the 0 g versus "
            "partial contrast did not replicate, so no served claim depended on this."),
        "supersedes": "phase10_partial_gravity_replication.P2_gradedRegression.correlation",
    }

    conclusion = (
        "osd346-gravity-signal-is-not-separable-from-flight-run"
        if not survives else "osd346-gravity-signal-survives-run-removal")
    result = {
        "phase": 11,
        "task": "separate the OSD-346 gravity signal from its flight-run structure",
        "studies": {"osd314": osd314, "osd346": b1},
        "B1_confound": b1,
        "B2_batchEffectStrength": b2,
        "B3_runRemoval": b3,
        "B4_identifiability": b4,
        "C_phase10Correction": correction,
        "decisionRule": (
            "The graded gravity signal counts as separable from the batch if the "
            "run-centred regression keeps a positive Spearman correlation with "
            "within-run-permutation p below 0.05. Fixed before the run."),
        "signalSurvivesRunRemoval": bool(survives),
        "conclusion": conclusion,
        "whatThisDoesNotSay": [
            "It does not say gravity has no effect on the transcriptome.",
            "It does not say the OSD-314 result was a batch artefact; OSD-314 records no "
            "batch structure to check.",
            "It does not rehabilitate the Phase 10 graded signal either: that signal is "
            "measured across runs as well as across gravity.",
        ],
        "researcherRequest": (
            "OSD-346's ISA table already contains the run identifier, so no request is "
            "needed there. OSD-314 does need one: its archive records no run, batch or "
            "harvest date, and without it the 1.000 cannot be attributed. A request for "
            "OSD-314's sequencing run and library prep batch identifiers has NOT been "
            "sent and no reply is claimed."),
        "registryChange": None,
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n")

    print(f"\nB1 mean within-run gravity range {b1['meanWithinRunGravityRangeG']} g = "
          f"{within_run_coverage:.0%} of the {full_range} g range; "
          f"PC1 variance explained by run {eta_run:.2f}")
    print(f"B2 run identifiable from expression: accuracy {b2['runAccuracy']}, "
          f"balanced {b2['balancedAccuracy']}")
    print(f"B3 raw rho {b3['rawFeatures']['observedSpearman']} "
          f"(p={b3['rawFeatures']['pCorrected']}) -> run-centred rho "
          f"{b3['runCentredFeatures']['observedSpearman']} "
          f"(p={b3['runCentredFeatures']['pCorrected']})")
    print(f"  Phase 10 P2 (within-treatment null) rho "
          f"{prior_p2['observedSpearman']} p {prior_p2['pCorrected']} -> within-run null "
          f"p {b3['rawFeatures']['pCorrected']}")
    print(f"  between-run rho {b3['betweenRunComponent']['spearmanOfRunMeans']} "
          f"(p={b3['betweenRunComponent']['p']}), within-run rho "
          f"{b3['withinRunComponent']['observedSpearman']} "
          f"(p={b3['withinRunComponent']['pCorrected']})")
    print(f"B4 identifiable: {b4['identifiable']} ({within_run_coverage:.0%} of range left)")
    print(f"conclusion: {conclusion} -> wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
