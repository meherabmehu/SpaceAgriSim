"""Put the platform's crop-relative water demand against measured greenhouse lettuce ET.

    python3 ml/research/validate_measured_et.py

The measured side is Schröder et al. (2021): 35 published pots of lettuce, weighed repeatedly, with
per-pot evapotranspiration for 13 intervals over 35 days. The simulated side is the unmodified
platform path - ``water.daily_water_demand_l`` driven by ``growth.logistic_progress`` with the
lettuce crop profile. No constant is tuned to make the comparison look better; the one free
parameter that is fitted is reported with a leave-one-treatment-out estimate and with its own
dispersion, and the uncalibrated numbers are shown next to it.

Three questions, in the order that matters:

1. **Scale.** Does the platform's demand, spread over a pot's surface area, land anywhere near the
   measured water loss? If it does not, by how much does it miss?
2. **Shape.** Do the two grow through the season the same way? A model with the wrong magnitude but
   the right shape is fixable with one constant; a model with the wrong shape is not.
3. **Normalisation.** Pot surface area is not the surface that transpires. Re-normalising on
   harvested fresh mass asks the same question with a denominator the data actually supports.

What this cannot show is written into the artefact, not left to the reader: evapotranspiration is
not transpiration, one cultivar in one greenhouse is not a crop coefficient, and no field of this
table is a microgravity observation.
"""
from __future__ import annotations
import safedata

import json
import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[2]
for extra in (_REPO_ROOT, _REPO_ROOT / "backend"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from app.config import simulation_constants as constants  # noqa: E402
from app.simulation import crops, growth, water  # noqa: E402

PROCESSED = _REPO_ROOT / "data" / "processed" / "phase26"
OUTPUT = _REPO_ROOT / "ml" / "evaluation" / "phase26_measured_et_validation"

POT_AREA_M2 = 0.0112  # the stated assumption; the study does not publish pot diameter
POT_VOLUME_L = 2.2
HARVEST_DAY = 37
CYCLE_DAYS = 35
IRRIGATION_CEILING_ML_PER_DAY = 350.0


def _spearman(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3:
        return None
    return float(pd.Series(a).corr(pd.Series(b), method="spearman"))


def _pearson(a: list[float], b: list[float]) -> float | None:
    if len(a) < 3:
        return None
    return float(pd.Series(a).corr(pd.Series(b)))


def _metrics(measured: list[float], predicted: list[float]) -> dict[str, Any]:
    paired = [(m, p) for m, p in zip(measured, predicted) if m is not None and p is not None]
    if not paired:
        return {"n": 0}
    errors = [p - m for m, p in paired]
    absolute = [abs(e) for e in errors]
    mean_measured = sum(m for m, _ in paired) / len(paired)
    ss_tot = sum((m - mean_measured) ** 2 for m, _ in paired)
    ss_res = sum(e ** 2 for e in errors)
    return {
        "n": len(paired),
        "bias": round(sum(errors) / len(errors), 6),
        "mae": round(sum(absolute) / len(absolute), 6),
        "rmse": round(math.sqrt(ss_res / len(paired)), 6),
        "r2": round(1.0 - ss_res / ss_tot, 4) if ss_tot > 0 else None,
        "pearson": None if (value := _pearson(measured, predicted)) is None else round(value, 4),
        "measuredMean": round(mean_measured, 6),
        "predictedMean": round(sum(p for _, p in paired) / len(paired), 6),
        "ratioPredictedToMeasured": round(
            (sum(p for _, p in paired) / len(paired)) / mean_measured, 4) if mean_measured else None,
    }


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    et = pd.read_csv(PROCESSED / "schroder2021_lettuce_et.csv")
    et = et[(et["inPublication"]) & (~et["flagAboveIrrigationCeiling"])]
    # `etRateMlPerDay` is the recomputed whole-day rate, falling back to the workbook's own daily
    # column for each pot's first interval. Using the recomputed column alone silently dropped a
    # whole measurement date (day 7), which made an earlier version of this artefact report 10
    # dates where the trial has 11.
    et = et.dropna(subset=["dayNumber", "etRateMlPerDay"])
    biomass = pd.read_csv(PROCESSED / "schroder2021_lettuce_biomass.csv")
    return et, biomass


def main() -> int:
    et, biomass = load()
    lettuce = crops.get_crop("lettuce")

    per_treatment_mass = (biomass[biomass["organ"] == "shoot"]
                          .groupby("treatment")["freshG"].mean().to_dict())

    rows: list[dict[str, Any]] = []
    for _, record in et.iterrows():
        day = int(record["dayNumber"])
        progress = growth.logistic_progress(day, CYCLE_DAYS)
        demand_l = water.daily_water_demand_l(lettuce, progress, POT_AREA_M2, 1.0)
        rows.append({
            "potId": record["potId"],
            "treatment": record["treatment"],
            "dayNumber": day,
            "measuredMlPerDay": float(record["etRateMlPerDay"]),
            "simulatedMlPerDay": demand_l * 1000.0,
            "growthFraction": progress,
            "measuredMmPerDayOnPotArea": float(record["etRateMlPerDay"]) / POT_AREA_M2 / 1000.0,
            "simulatedMmPerDayOnPotArea": demand_l / POT_AREA_M2,
            "harvestFreshG": per_treatment_mass.get(record["treatment"]),
        })
    frame = pd.DataFrame(rows)

    # ---- 1. scale, per pot --------------------------------------------------------------
    pooled = _metrics(frame["measuredMlPerDay"].tolist(), frame["simulatedMlPerDay"].tolist())
    by_treatment = {
        treatment: _metrics(group["measuredMlPerDay"].tolist(),
                            group["simulatedMlPerDay"].tolist())
        for treatment, group in frame.groupby("treatment")
    }

    # ---- 2. shape, on treatment-mean trajectories ---------------------------------------
    trajectory = (frame.groupby("dayNumber", as_index=False)
                  .agg(measuredMlPerDay=("measuredMlPerDay", "mean"),
                       simulatedMlPerDay=("simulatedMlPerDay", "mean")))
    shape = {
        "points": int(len(trajectory)),
        "spearmanAcrossDays": None if (v := _spearman(trajectory["measuredMlPerDay"].tolist(),
                                                     trajectory["simulatedMlPerDay"].tolist())) is None
        else round(v, 4),
        "pearsonAcrossDays": None if (v := _pearson(trajectory["measuredMlPerDay"].tolist(),
                                                   trajectory["simulatedMlPerDay"].tolist())) is None
        else round(v, 4),
        "measuredTrendMlPerDayPerDay": None,
        "note": ("A high rank correlation with a large level error means the growth curve has the "
                 "right season but the wrong magnitude; the two findings must be read together."),
    }
    days = trajectory["dayNumber"].to_numpy(dtype=float)
    if len(days) > 2:
        x_mean = days.mean()
        sxx = ((days - x_mean) ** 2).sum()
        shape["measuredTrendMlPerDayPerDay"] = round(
            float(((days - x_mean) * (trajectory["measuredMlPerDay"].to_numpy() - trajectory[
                "measuredMlPerDay"].mean())).sum() / sxx), 4)

    # ---- 3a. one fitted scale, with leave-one-treatment-out ------------------------------
    measured_all = frame["measuredMlPerDay"].to_numpy()
    simulated_all = frame["simulatedMlPerDay"].to_numpy()
    denominator = float((simulated_all ** 2).sum())
    global_scale = float((measured_all * simulated_all).sum() / denominator)

    folds: dict[str, Any] = {}
    for treatment in sorted(frame["treatment"].unique()):
        train = frame["treatment"] != treatment
        test = ~train
        train_scale = float(
            (frame.loc[train, "measuredMlPerDay"] * frame.loc[train, "simulatedMlPerDay"]).sum()
            / (frame.loc[train, "simulatedMlPerDay"] ** 2).sum())
        held_out = _metrics(frame.loc[test, "measuredMlPerDay"].tolist(),
                            (frame.loc[test, "simulatedMlPerDay"] * train_scale).tolist())
        held_out["fittedScaleOnOtherTreatments"] = round(train_scale, 4)
        folds[treatment] = held_out
    fold_scales = [float(v["fittedScaleOnOtherTreatments"]) for v in folds.values()]

    # ---- 3b. renormalisation on harvested fresh mass ------------------------------------
    grams = frame.dropna(subset=["harvestFreshG"]).copy()
    grams["measuredMlPerDayPerG"] = grams["measuredMlPerDay"] / grams["harvestFreshG"]
    grams["simulatedMlPerDayPerG"] = grams["simulatedMlPerDay"] / grams["harvestFreshG"]
    per_gram = _metrics(grams["measuredMlPerDayPerG"].tolist(),
                        grams["simulatedMlPerDayPerG"].tolist())

    # ---- 3c. how much does the answer depend on the area we divide by? ----------------
    # The study does not publish pot diameter, pot spacing, or leaf area for its own pots. Any
    # "mm per day" for this trial is therefore a ratio whose denominator is a choice. This block
    # varies the denominator across the defensible options so the choice cannot hide.
    leaf_area_note = {
        "source": "data/processed/phase26/greenlight2024_lettuce_harvest.csv (different experiment, "
                  "different cultivar, so a cross-experiment order-of-magnitude check only)",
        "reportedColumn": "leafAreaMm2",
        "suspectedUnitError": (
            "the sheet's 'leafAreaMm2' mean is 1298, which read literally is 0.0013 m2 for a 48 g "
            "lettuce with 20 leaves of 158 x 123 mm. Reconstructing 20 leaves of the simultaneously "
            "reported dimensions gives ~1350 cm2, so the column is numerically consistent with cm2 "
            "and off by 100x against its own unit label. Treated here as cm2 and labelled as an "
            "inference, not as a correction of the publisher's file."
        ),
        "leafAreaM2": 0.130,
    }
    # The crop profile claims a peak water use per square metre of canopy. The measured side is a
    # water volume per plant per day. Converting one into the other needs an area, and the study
    # does not publish one. Comparing the profile's flux against the measured flux under each
    # candidate area is therefore the only honest way to report this - and it changes the sign of
    # the answer, which is the result.
    peak_flux = lettuce.peak_water_l_per_day  # L per m2 per day at full canopy
    measured_ml = float(frame["measuredMlPerDay"].mean())
    simulated_ml = float(frame["simulatedMlPerDay"].mean())

    def _basis(area_m2: float) -> dict[str, Any]:
        measured_flux = measured_ml / area_m2 / 1000.0
        return {
            "areaM2": area_m2,
            "measuredLPerM2PerDay": round(measured_flux, 3),
            "profilePeakLPerM2PerDay": peak_flux,
            "profileOverMeasured": round(peak_flux / measured_flux, 3),
            "profileIsHigher": peak_flux > measured_flux,
        }

    denominators = {
        "potSurfaceAssumption": {
            **_basis(POT_AREA_M2),
            "basis": "the 0.0112 m2 pot-surface assumption",
        },
        "canopyLeafArea": {
            **_basis(leaf_area_note["leafAreaM2"]),
            "basis": "cross-experiment leaf area (order-of-magnitude check only)",
        },
        "freshMass": {
            "unit": "mL per g fresh mass per day",
            "measured": round(measured_ml / 187.0, 4),
            "simulated": round(simulated_ml / 187.0, 4),
            "profileOverMeasured": per_gram["ratioPredictedToMeasured"],
            "basis": "fresh mass at harvest, no area needed",
        },
    }
    leaf_area_sensitivity = {
        "leafArea": leaf_area_note,
        "denominators": denominators,
        "conclusion": (
            "Against the platform's own 2.5 L/m2/day lettuce flux: on the pot-surface assumption "
            "measured water use is 4x the profile, and on a canopy-area assumption it is 0.37x the "
            "profile - the sign of the finding reverses with the denominator the study does not "
            "publish. The spread between those two readings is larger than either discrepancy. "
            "This dataset therefore cannot identify a level correction, and no constant may be "
            "changed on the strength of it. What does survive is the shape, which is "
            "denominator-free."
        ),
        "consequenceForThePlatform": [
            "water.profile peak_water_l_per_day left unchanged",
            "no crop coefficient published",
            "the demand path is documented as unvalidated in level and partially supported in shape",
        ],
    }

    report = {
        "phase": 26,
        "check": "measured-eta",
        "title": "Platform crop-relative water demand vs measured greenhouse lettuce evapotranspiration",
        "status": "evaluated",
        "generatedAt": pd.Timestamp.utcnow().isoformat(),
        "measuredSide": {
            "source": "data/processed/phase26/schroder2021_lettuce_et.csv",
            "doi": "10.5281/zenodo.5550230",
            "license": "CC BY 4.0",
            "records": int(len(frame)),
            "pots": int(frame["potId"].nunique()),
            "treatments": sorted(frame["treatment"].unique().tolist()),
            "days": sorted(int(d) for d in frame["dayNumber"].unique()),
            "measurementDates": int(frame["dayNumber"].nunique()),
            "rateSource": (frame.get("etRateSource").value_counts().to_dict()
                           if "etRateSource" in frame else {}),
            "measurementBasis": "gravimetric pot evapotranspiration (plant plus substrate)",
            "excluded": {
                "flagAboveIrrigationCeiling": "6 pot-days above the study's 350 mL/pot/day ceiling",
                "outOfPublication": "4 autoclaved treatments marked unused by the publication",
            },
        },
        "simulatedSide": {
            "path": "water.daily_water_demand_l(crop, growth_fraction, area_m2, light_scale)",
            "demandBasis": water.demand_basis(None),
            "crop": "lettuce",
            "peakWaterLPerM2PerDay": lettuce.peak_water_l_per_day,
            "growthCurve": f"growth.logistic_progress(day, {CYCLE_DAYS}), steepness "
                           f"{constants.LOGISTIC_STEEPNESS}",
            "seedlingActivityFraction": constants.SEEDLING_ACTIVITY_FRACTION,
            "potAreaAssumptionM2": POT_AREA_M2,
            "potVolumeL": POT_VOLUME_L,
            "constantsChanged": [],
        },
        "scalePerPot": {
            "pooled": pooled,
            "byTreatment": by_treatment,
            "fittedSingleScale": round(global_scale, 4),
            "fittedScaleDispersion": {
                "min": round(min(fold_scales), 4),
                "max": round(max(fold_scales), 4),
                "spread": round(max(fold_scales) - min(fold_scales), 4),
            },
            "leaveOneTreatmentOut": folds,
            "interpretation": (
                "On the pot-surface denominator the platform's crop-relative demand is about a "
                "seventh of the measured pot water use, and the fitted scale is consistent across "
                "treatments (a 0.73 spread over a 6.34 level), so it is not a per-treatment "
                "artefact - but see denominatorSensitivity, where the same data on a canopy-area "
                "denominator reverses the sign of the discrepancy. "
                "Note what the scaled fit cannot be read as: a fitted scale of N is not evidence "
                "that peak water use is N times the profile value, because the same constant also "
                "absorbs the pot-area assumption, the untranspiring substrate surface, and the "
                "fact that evapotranspiration includes evaporation."
            ),
        },
        "shape": shape,
        "perGramFreshMass": {
            **per_gram,
            "treatmentHarvestFreshG": {k: round(v, 2) for k, v in per_treatment_mass.items()},
            "interpretation": (
                "Fresh mass is the denominator the dataset actually supports: it is measured per "
                "plant, it is what the platform's growth model predicts, and it does not depend "
                "on the unpublished pot diameter. It does not remove the evaporation component."
            ),
        },
        "denominatorSensitivity": leaf_area_sensitivity,
        "canItCloseTheGap": {
            "gap": "measured-eta",
            "conclusion": "not closed",
            "why": [
                "evapotranspiration is measured; transpiration is not separated from substrate "
                "evaporation",
                "no per-day weather is published for the trial, so no reference ET0 and no crop "
                "coefficient can be derived",
                "one cultivar, one greenhouse, four weeks, pot culture: this is a benchmark, not "
                "an operating-condition dataset",
                "the trial ran on Earth; nothing here is a reduced-gravity observation",
            ],
            "blockedBy": "an unpublished geometric quantity (pot spacing / canopy area) that no "
                         "downstream analysis can recover from this file",
            "whatItDoesClose": (
                "the 'no measured crop water use exists anywhere in the repository' half of the "
                "gap. A per-plant, per-day, replicated measurement now exists in-repo with its "
                "licence and hash, and the platform's water demand is compared against it in a "
                "committed, reproducible artefact. The gap's remaining blockers are the ones "
                "listed above, and they are not addressable from this dataset."
            ),
        },
        "notClaimed": [
            "no crop coefficient is published or implied",
            "no validation accuracy: this is an out-of-sample comparison against a third-party "
            "measurement, not a model score",
            "no microgravity or spaceflight relevance",
            "no claim that the simulator was corrected: the profile constants are untouched",
        ],
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    safedata.dump(report, OUTPUT)

    print(f"records: {len(frame)} pot-days, {frame['potId'].nunique()} pots, "
          f"{len(report['measuredSide']['treatments'])} treatments")
    print(f"pooled scale   {pooled}")
    print(f"fitted scale   {global_scale:.3f} (LOO-treatment range "
          f"{min(fold_scales):.3f}-{max(fold_scales):.3f})")
    print(f"shape spearman {shape['spearmanAcrossDays']}  pearson {shape['pearsonAcrossDays']}")
    print(f"per gram       bias {per_gram['bias']:+.5f} ml/g/day, "
          f"ratio {per_gram['ratioPredictedToMeasured']}")
    print(f"-> {OUTPUT.relative_to(_REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
