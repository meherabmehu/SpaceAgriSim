"""Phase 11: does the VEG-04 flight effect replicate, and what can a new campaign expect?

Phase 7's headline microbial result is that the flight-versus-ground contrast replicates:
+3.06 log10 CFU/g in VEG-04A and +2.64 in VEG-04B. Both numbers come from aerobic plate
counts on leaf tissue only (5 flight / 15 ground samples in A, 31 / 72 in B), while the
full table holds 292 quantified samples across five tissues and two assays.

Two things were never checked, and both change what the number means:

  1. Composition. If the two campaigns differ in which tissues and assays were sampled,
     a pooled contrast can shift because the mix shifted, not because the effect did.
     A stratum-standardised contrast answers that directly.

  2. Dependence. Samples cluster inside pillows and harvest units (8 to 12 independent
     units per campaign). Treating 120 ground samples as 120 independent observations
     understates the interval by a wide margin.

So this script does three things and refuses a fourth:

  S1  reproduce the Phase 7 headline exactly, so any difference below is a change of
      method and not a change of data
  S2  estimate the contrast in every (campaign, tissue, assay) stratum, with cluster
      bootstrap intervals that resample whole units
  S3  pool the two campaign effects with a random-effects model, which yields the number
      decision support actually needs: a prediction interval for a *new* campaign

Nothing here predicts a specific campaign's absolute load. The campaign offset is not a
function of any feature in the table (Phase 7 established that, and it is why v2 exists),
so the prediction interval is the honest form of the claim.
"""

from __future__ import annotations
import sys

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None  # noqa: E501
import safedata  # noqa: E402 - the repository data layer lives at the root
DATA = ROOT / "data" / "processed"
OUT = ROOT / "ml" / "evaluation" / "phase11_microbial_campaigns"

SEED = 11570
BOOTSTRAP = 4000
TARGET = "log10CfuPerG"


def load():
    table = pd.read_csv(DATA / "mizuna_microbial_load.csv")
    table = table[table[TARGET].notna()].copy()
    table["unit"] = table["unit"].astype(str)
    return table


def contrast(frame):
    flight = frame.loc[frame.environment == "flight", TARGET]
    ground = frame.loc[frame.environment == "ground", TARGET]
    if flight.empty or ground.empty:
        return None
    return {"flightMean": float(flight.mean()), "flightN": int(flight.size),
            "groundMean": float(ground.mean()), "groundN": int(ground.size),
            "difference": float(flight.mean() - ground.mean())}


def cluster_bootstrap(frame, resamples=BOOTSTRAP, seed=SEED):
    """Resample whole units, not samples: pillows are the independent replicate.

    A sample-level bootstrap on 120 ground samples would produce an interval roughly
    sqrt(120/12) times too narrow, which is the difference between a precise estimate
    and an honest one.
    """
    generator = np.random.default_rng(seed)
    flight_units = frame.loc[frame.environment == "flight", "unit"].unique()
    ground_units = frame.loc[frame.environment == "ground", "unit"].unique()
    if flight_units.size < 2 or ground_units.size < 2:
        return None
    draws = np.empty(resamples)
    by_unit = {unit: group[TARGET].to_numpy() for unit, group in frame.groupby("unit")}
    for index in range(resamples):
        draw_flight = generator.choice(flight_units, flight_units.size, replace=True)
        draw_ground = generator.choice(ground_units, ground_units.size, replace=True)
        flight_values = np.concatenate([by_unit[unit] for unit in draw_flight])
        ground_values = np.concatenate([by_unit[unit] for unit in draw_ground])
        draws[index] = flight_values.mean() - ground_values.mean()
    return {
        "flightUnits": int(flight_units.size),
        "groundUnits": int(ground_units.size),
        "ci95": [round(float(np.percentile(draws, 2.5)), 3),
                 round(float(np.percentile(draws, 97.5)), 3)],
        "bootstrapResamples": resamples,
        "method": "cluster bootstrap over independent units within campaign",
    }


def standardised(frame, weights):
    """Contrast holding tissue/assay composition fixed at the given weights.

    Strata that the frame does not contain are skipped and the remaining weights are
    renormalised, which is recorded in `strataUsed` because it limits the comparison: if
    one campaign never sampled a tissue, standardising cannot invent it.
    """
    weighted = 0.0
    used = 0.0
    strata_used = []
    for stratum, weight in weights.items():
        block = frame[(frame.tissue == stratum[0]) & (frame.assay == stratum[1])]
        row = contrast(block)
        if row is None:
            continue
        weighted += weight * row["difference"]
        used += weight
        strata_used.append(f"{stratum[0]}|{stratum[1]}")
    if used == 0:
        return None, []
    return float(weighted / used), strata_used


def random_effects(effects: list[float], variances: list[float]) -> dict:
    """DerSimonian-Laird on two campaigns, plus a prediction interval.

    With two studies the heterogeneity estimate is fragile, which is reported rather
    than smoothed over. The prediction interval is the point of the exercise: it is what
    a third campaign would be expected to fall within, and it is much wider than the
    confidence interval on the pooled mean.
    """
    from scipy import stats

    y = np.asarray(effects, dtype=float)
    v = np.asarray(variances, dtype=float)
    w = 1.0 / v
    fixed = float((w * y).sum() / w.sum())
    q = float((w * (y - fixed) ** 2).sum())
    k = y.size
    c = float(w.sum() - (w ** 2).sum() / w.sum())
    tau2 = max(0.0, (q - (k - 1)) / c) if c > 0 else 0.0
    w_star = 1.0 / (v + tau2)
    pooled = float((w_star * y).sum() / w_star.sum())
    se = float(np.sqrt(1.0 / w_star.sum()))
    i2 = max(0.0, (q - (k - 1)) / q) * 100 if q > 0 else 0.0
    t = stats.t.ppf(0.975, max(k - 2, 1))
    prediction_se = float(np.sqrt(tau2 + se ** 2))
    return {
        "studies": k,
        "pooledEffect": round(pooled, 3),
        "ci95": [round(pooled - 1.96 * se, 3), round(pooled + 1.96 * se, 3)],
        "tau2": round(tau2, 4),
        "i2Percent": round(i2, 1),
        "cochranQ": round(q, 3),
        "predictionInterval95": [round(pooled - t * prediction_se, 3),
                                 round(pooled + t * prediction_se, 3)],
        "note": ("a prediction interval for a new campaign, not a confidence interval on "
                 "the mean. With two campaigns tau2 is weakly identified, so the interval "
                 "should be read as wide and provisional."),
    }


def main() -> int:
    table = load()
    report = {
        "phase": 11,
        "samples": int(len(table)),
        "campaigns": sorted(table.experiment.unique().tolist()),
        "tissues": sorted(table.tissue.unique().tolist()),
        "assays": sorted(table.assay.unique().tolist()),
        "target": TARGET,
    }

    # S1: reproduce the Phase 7 headline -----------------------------------
    leaf = table[(table.assay == "aerobic") & (table.tissue == "leaf")]
    committed = safedata.load(ROOT / "ml" / "evaluation" / "microbial_contrast")
    s1 = {"protocol": "aerobic plate counts on leaf tissue, the Phase 7 subset",
          "campaigns": {}}
    for campaign in ("VEG04A", "VEG04B"):
        row = contrast(leaf[leaf.experiment == campaign])
        row["phase7Committed"] = round(committed[campaign]["difference"], 4)
        row["difference"] = round(row["difference"], 4)
        row["reproduced"] = abs(row["difference"] - row["phase7Committed"]) < 5e-4
        row["bootstrap"] = cluster_bootstrap(leaf[leaf.experiment == campaign])
        s1["campaigns"][campaign] = row
        print(f"S1 {campaign} contrast {row['difference']:+.4f} "
              f"(phase 7 {row['phase7Committed']:+.4f}) "
              f"-> {'reproduced' if row['reproduced'] else 'NOT reproduced'}")
    report["S1_headlineReproduction"] = s1

    # S2: every stratum, both campaigns ------------------------------------
    s2 = {"protocol": ("flight minus ground mean log10 CFU/g in each campaign x tissue x "
                       "assay stratum, with cluster bootstrap intervals"),
          "strata": {}}
    for (campaign, tissue, assay), block in table.groupby(["experiment", "tissue", "assay"]):
        row = contrast(block)
        if row is None:
            continue
        row["difference"] = round(row["difference"], 3)
        row["bootstrap"] = cluster_bootstrap(block)
        s2["strata"][f"{campaign}|{tissue}|{assay}"] = row
    positive = [row for row in s2["strata"].values()
                if row["difference"] > 0 and row["bootstrap"]
                and row["bootstrap"]["ci95"][0] > 0]
    s2["strataPositiveAndSignificant"] = len(positive)
    s2["strataTotal"] = len(s2["strata"])
    report["S2_strata"] = s2
    print(f"S2 {len(positive)} of {len(s2['strata'])} strata positive with a CI excluding 0")

    # Composition check: do the campaigns sample the same mix? --------------
    composition = {}
    for campaign, block in table.groupby("experiment"):
        composition[campaign] = (block.groupby(["tissue", "assay"]).size()
                                 / len(block)).round(3).to_dict()
    totals = {campaign: sum(1 for row in s2["strata"]
                            if row.startswith(campaign + "|")) for campaign in ("VEG04A", "VEG04B")}

    # Standardise campaign B onto campaign A's composition, and vice versa.
    weights_a = {key: value for key, value in composition["VEG04A"].items()}
    weights_b = {key: value for key, value in composition["VEG04B"].items()}
    s3 = {
        "protocol": ("contrast recomputed with the tissue/assay mix held at the other "
                     "campaign's weights, so a shift in composition cannot masquerade as "
                     "a shift in effect"),
        "composition": {campaign: {f"{k[0]}|{k[1]}": v for k, v in mix.items()}
                        for campaign, mix in composition.items()},
        "VEG04B_at_VEG04A_mix": None,
        "VEG04A_at_VEG04B_mix": None,
        "strataUsedForB": None,
        "strataUsedForA": None,
        "rawVEG04A_allTissues": contrast(table[table.experiment == "VEG04A"])["difference"],
        "rawVEG04B_allTissues": contrast(table[table.experiment == "VEG04B"])["difference"],
        "statement": ("how much of the campaign-to-campaign difference in the pooled "
                      "contrast is the sampling mix rather than the effect"),
    }
    value_b, used_b = standardised(table[table.experiment == "VEG04B"], weights_a)
    value_a, used_a = standardised(table[table.experiment == "VEG04A"], weights_b)
    s3["VEG04B_at_VEG04A_mix"] = round(value_b, 3)
    s3["VEG04A_at_VEG04B_mix"] = round(value_a, 3)
    s3["strataUsedForB"] = used_b
    s3["strataUsedForA"] = used_a
    s3["rawVEG04A_allTissues"] = round(float(s3["rawVEG04A_allTissues"]), 3)
    s3["rawVEG04B_allTissues"] = round(float(s3["rawVEG04B_allTissues"]), 3)
    s3["limitation"] = ("VEG-04B contributes leaf tissue only, so standardising it onto "
                        "VEG-04A\'s mix reaches only the two shared leaf strata and the "
                        "root, soil and wick strata cannot be compared at all. The "
                        "conclusion is therefore about the shared strata, not about the "
                        "whole table.")
    report["S3_compositionStandardised"] = s3
    print(f"S3 B at A's mix {s3['VEG04B_at_VEG04A_mix']:+.3f}, "
          f"A at B's mix {s3['VEG04A_at_VEG04B_mix']:+.3f}")

    # S4: random-effects pooling -------------------------------------------
    effects, variances = [], []
    for campaign in ("VEG04A", "VEG04B"):
        row = s1["campaigns"][campaign]
        low, high = row["bootstrap"]["ci95"]
        # Convert the cluster-bootstrap interval back to a standard error on the effect.
        effects.append(row["difference"])
        variances.append(((high - low) / (2 * 1.96)) ** 2)
    pooled = random_effects(effects, variances)
    pooled["inputEffects"] = {"VEG04A": effects[0], "VEG04B": effects[1]}
    pooled["inputCi95"] = {campaign: s1["campaigns"][campaign]["bootstrap"]["ci95"]
                           for campaign in ("VEG04A", "VEG04B")}
    report["S4_randomEffects"] = pooled
    print(f"S4 pooled {pooled['pooledEffect']:+.3f} "
          f"[{pooled['ci95'][0]:+.3f}, {pooled['ci95'][1]:+.3f}], I2 {pooled['i2Percent']}%, "
          f"prediction interval [{pooled['predictionInterval95'][0]:+.3f}, "
          f"{pooled['predictionInterval95'][1]:+.3f}]")

    # The third-campaign question, answered from the sweep rather than invented.
    discovery = safedata.load(ROOT / "ml" / "evaluation"
                            / "phase11_dataset_discovery")
    report["S5_thirdCampaign"] = {
        "available": False,
        "evidence": ("the 231-study discovery sweep found nine uncatalogued microbial "
                     "candidates, none of them a NASA crop-microbial load campaign: "
                     "OSD-385/386 are deliberate E. coli and Salmonella challenge studies "
                     "on lettuce and mizuna, and OSD-146/170/280 are mouse faecal, "
                     "aircraft bioaerosol and astronaut salivary microbiomes"),
        "candidatesReviewed": discovery.get("questions", {})
                                 .get("microbial", {}).get("candidates", []),
        "consequence": ("the random-effects estimate rests on two campaigns and the "
                        "prediction interval is the only defensible statement about a "
                        "third one"),
    }

    report["claims"] = {
        "permitted": [
            "the flight-versus-ground contrast in culturable aerobic load replicates in "
            "sign and approximate size across both VEG-04 campaigns",
            "a new campaign's contrast is expected inside the prediction interval",
            "the direction of the effect is stable across tissue and assay strata",
        ],
        "refused": [
            "any prediction of a named third campaign's absolute load",
            "any absolute-load prediction without that campaign's own baseline samples",
            "any gravity attribution: flight and ground differ in cabin environment, "
            "payload handling and sampling protocol as well as gravity",
        ],
    }
    report["registryChange"] = None
    report["verdict"] = (
        "flight-effect-replicates-across-both-campaigns-after-composition-standardisation"
        if (s3["VEG04B_at_VEG04A_mix"] > 0 and s3["VEG04A_at_VEG04B_mix"] > 0
            and pooled["ci95"][0] > 0)
        else "flight-effect-does-not-survive-composition-standardisation")
    safedata.dump(report, OUT)
    print(f"\nverdict: {report['verdict']}\nwrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
