"""Workflow C — environmental stress and growth response under light quality, measured.

What this workflow is, stated first because it decides everything else
---------------------------------------------------------------------
It is a **measured-evidence** workflow. A user picks one of four spectral regimes and a trait, and
the API returns what was actually measured on plants grown under that regime, with its replicate
spread, its effect against the control, and the photophysiological stress indicators that go with it.

It is **not** a simulation and **not** a response surface. PPFD was 200 umol/m2/s and the photoperiod
16 h in every regime, so nothing here identifies a light-intensity or daily-light-integral response;
and the green-light fraction takes only three distinct values, one of which is the control, so nothing
here identifies a continuous spectrum surface either. Those limits are returned in every response
rather than kept in a report.

Why this evidence was chosen
----------------------------
Phase 28 left this workflow blocked because the platform had no validated environmental response
surface. The search for one is recorded in `docs/PHASE29_ENVIRONMENTAL_STRESS_RESEARCH_REPORT.md`.
What was found is a licensed, hash-verified, replicated spectrum experiment with per-plant harvest
data, per-plant chlorophyll-fluorescence measurements at two growth stages, and per-sample pigment
assays. That supports a comparison workflow with real statistics. It does not support a predictive
surface, and the workflow says so in its title, its capability document and its response.

The statistics, and their one honest weakness
---------------------------------------------
Each regime is summarised with its mean, standard deviation, standard error and a seeded bootstrap
confidence interval for the mean. Each treatment is compared with the control by a Welch t-test
(unequal variances, which is what replicate pots look like) plus Hedges' g for effect size, and a
bootstrap confidence interval on the difference in means.

The weakness is pseudo-replication: replicate plants inside one chamber are not independent draws of
"the treatment", so a p-value here describes variability between plants in one experiment, not
variability a grower would see repeating the treatment. Every response states that the interval and
the p-value are within-experiment quantities.

What is deliberately not computed
---------------------------------
No composite "stress score". Weighting PhiNO against NPQ against Fv/Fm would be an invented choice
with no source behind it, so the four indicators are returned separately, each with its own units and
its own comparison, and the response explains what each one means physiologically.
"""

from __future__ import annotations

import json
import math
import random
import statistics
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.workflows import units

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "processed" / "phase29"
DESIGN = DATA / "light_spectrum_treatments.csv"
HARVEST = DATA / "light_stress_harvest.csv"
PHOTOSYNTHESIS = DATA / "light_stress_photosynthesis.csv"
PIGMENTS = DATA / "light_stress_pigments.csv"
QUALITY = DATA / "light_stress_quality.json"

SOURCE = {
    "dataset": "zenodo-greenlight-2024-lettuce",
    "doi": "10.5281/zenodo.20394352",
    "license": "CC BY 4.0",
    "citation": ("'Optimising Spectral Composition in Hydroponic Lettuce Cultivation: The Role of "
                 "Green Light, Open Data', Zenodo record 20394352"),
    "measurementBasis": ("destructive harvest of whole plants, MultispeQ chlorophyll fluorescence "
                         "on intact leaves, and leaf pigment assays"),
}

CONTROL = "control"
MAX_SCENARIOS = 4
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 20261107

# Each trait: human label, biological meaning, and whether a higher value is the more stressed
# direction. `higherIsWorse` is only used to phrase the interpretation, never to compute a score.
TRAITS: dict[str, dict[str, Any]] = {
    "freshWeightG": {"label": "Fresh weight", "unit": "g/plant", "group": "growth",
                     "means": "edible fresh biomass per plant at harvest",
                     "higherIsWorse": None},
    "dryWeightG": {"label": "Dry weight", "unit": "g/plant", "group": "growth",
                   "means": "structural biomass per plant; insensitive to leaf water content",
                   "higherIsWorse": None},
    "leafAreaMm2": {"label": "Leaf area", "unit": "mm2", "group": "growth",
                    "means": "light-intercepting surface per plant",
                    "higherIsWorse": None},
    "leafNumber": {"label": "Leaf number", "unit": "count", "group": "growth",
                   "means": "leaves per plant at harvest", "higherIsWorse": None},
    "fvPOverFmP": {"label": "PSII maximum efficiency (Fv'/Fm')", "unit": "fraction",
                   "group": "stress", "higherIsWorse": True,
                   "means": ("the fraction of absorbed light energy the photosystem can still use; "
                             "a fall relative to the control is the standard early stress signal")},
    "npqT": {"label": "Non-photochemical quenching (NPQt)", "unit": "dimensionless",
             "group": "stress", "higherIsWorse": None,
             "means": ("energy dissipated safely as heat; rising NPQ can be healthy "
                       "photoprotection or the first sign of excess light, so it is reported "
                       "without a verdict")},
    "phiNO": {"label": "Fraction of energy lost to non-regulated processes (PhiNO)", "unit": "fraction",
              "group": "stress", "higherIsWorse": True,
              "means": ("energy neither used in photochemistry nor dissipated in a regulated way; "
                        "the fraction most closely tied to photoinhibition")},
    "phiNPQ": {"label": "Fraction dissipated as regulated heat (PhiNPQ)", "unit": "fraction",
               "group": "stress", "higherIsWorse": None,
               "means": "the photoprotective, regulated share of energy dissipation"},
    "phi2": {"label": "Effective quantum yield of PSII (Phi2)", "unit": "fraction",
             "group": "stress", "higherIsWorse": True,
             "means": "the operating efficiency of electron transport in the light"},
    "spad": {"label": "Chlorophyll index (SPAD)", "unit": "spad-index", "group": "stress",
             "higherIsWorse": True,
             "means": ("relative leaf chlorophyll; a fall means chlorosis or pigment "
                       "acclimation")},
}
PIGMENT_TRAITS = {
    "chlorophyllAMgPerGFw": {"label": "Chlorophyll a", "unit": "mg/g fresh weight",
                             "group": "pigment", "higherIsWorse": True,
                             "means": "the main light-harvesting pigment"},
    "chlorophyllBMgPerGFw": {"label": "Chlorophyll b", "unit": "mg/g fresh weight",
                             "group": "pigment", "higherIsWorse": True,
                             "means": "accessory pigment of the light-harvesting antenna"},
    "totalCarotenoidsMgPerGFw": {"label": "Total carotenoids", "unit": "mg/g fresh weight",
                                 "group": "pigment", "higherIsWorse": None,
                                 "means": ("photoprotective pigments; a rise is an acclimation "
                                           "response, not necessarily damage")},
    "totalChlorophyllMgPerGFw": {"label": "Total chlorophyll", "unit": "mg/g fresh weight",
                                 "group": "pigment", "higherIsWorse": True,
                                 "means": "chlorophyll a + b"},
    "totalFlavonoidsMgQePerGFw": {"label": "Total flavonoids", "unit": "mg quercetin equiv/g FW",
                                  "group": "pigment", "higherIsWorse": None,
                                  "means": "antioxidant secondary metabolites"},
    "totalPolyphenolsMgGaePerGFw": {"label": "Total polyphenols", "unit": "mg gallic acid equiv/g FW",
                                    "group": "pigment", "higherIsWorse": None,
                                    "means": "antioxidant secondary metabolites"},
    "antioxidantActivityUmQe": {"label": "Antioxidant activity", "unit": "umol quercetin equiv",
                                "group": "pigment", "higherIsWorse": None,
                                "means": "in vitro radical-scavenging capacity of the leaf extract"},
}

# The factor map the UI renders. Every environmental factor a user could reasonably ask about is
# listed as supported or unsupported, with the reason, so a control that cannot move an outcome is
# never presented as if it could.
FACTORS = [
    {"factor": "greenLightFractionPct", "label": "Green-light fraction of the spectrum",
     "supported": True,
     "evidence": ("measured across four spectral regimes at a fixed 200 umol/m2/s and 16 h; three "
                  "distinct green fractions including the control"),
     "rangeCovered": "5.08, 24 and 24 (incremental 16-24-32) % green",
     "limitation": ("three levels, one experiment; t3 also changes planting density by 1.25x, and "
                    "t2/t3 vary the spectrum during the experiment")},
    {"factor": "ppfdUmolPerM2S", "label": "PPFD",
     "supported": False,
     "evidence": "held at 200 umol/m2/s in every regime of this experiment",
     "rangeCovered": "200 only",
     "limitation": ("no light-intensity contrast exists in this dataset, so no PPFD response can "
                    "be estimated from it")},
    {"factor": "photoperiodHours", "label": "Photoperiod",
     "supported": False, "evidence": "held at 16 h in every regime",
     "rangeCovered": "16 only",
     "limitation": "no photoperiod contrast, so no photoperiod or DLI response can be estimated"},
    {"factor": "airTemperatureC", "label": "Air temperature",
     "supported": False,
     "evidence": "not varied by this experiment and not reported per regime",
     "rangeCovered": "none",
     "limitation": ("a temperature stress response would have to come from a different dataset; "
                    "for lettuce the only measured temperature grid in this repository is the WUR "
                    "plant-factory experiment, which the harvest workflow already uses")},
    {"factor": "co2Ppm", "label": "CO2 concentration",
     "supported": False,
     "evidence": "not varied and not reported by this experiment",
     "rangeCovered": "none",
     "limitation": ("no measured CO2 contrast exists anywhere in this repository, so this "
                    "workflow refuses to move an outcome on CO2 rather than scaling an assumption")},
    {"factor": "relativeHumidityPct", "label": "Relative humidity / VPD",
     "supported": False, "evidence": "not varied and not reported",
     "rangeCovered": "none",
     "limitation": "no humidity contrast exists in the stress dataset"},
]

LIMITATIONS = [
    "One experiment, one cultivar (Red Batavia), one light level (200 umol/m2/s) and one "
    "photoperiod (16 h). Results compare spectral regimes; they do not establish a general lettuce "
    "spectrum response.",
    "t3 changes two things at once: the incremental green spectrum and a 25 % higher planting "
    "density. Any difference between t3 and the control cannot be attributed to spectrum.",
    "t2 and t3 change the green fraction during the experiment (16 %, 24 %, 32 % by week), so their "
    "'24 %' is a mid-point, not a constant treatment level.",
    "Replicate plants share a chamber and a nutrient system. The confidence intervals and p-values "
    "describe variation between plants within this experiment; they are not a prediction of how the "
    "treatment would repeat.",
    "The control's green fraction (5.08 %) is the source's own approximation, not a measured "
    "spectral power distribution.",
    "CO2, PPFD, photoperiod and humidity were not varied, so no response is offered for them.",
    "No composite stress score is computed. The indicators are returned separately because "
    "combining them would require weights no source provides.",
]


@lru_cache(maxsize=1)
def _design() -> list[dict[str, Any]]:
    import csv

    with DESIGN.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@lru_cache(maxsize=1)
def _tables() -> dict[str, list[dict[str, str]]]:
    import csv

    loaded = {}
    for name, path in (("harvest", HARVEST), ("photosynthesis", PHOTOSYNTHESIS),
                       ("pigments", PIGMENTS)):
        if not path.is_file():
            loaded[name] = []
            continue
        with path.open(newline="", encoding="utf-8") as handle:
            loaded[name] = list(csv.DictReader(handle))
    return loaded


@lru_cache(maxsize=1)
def _quality() -> dict[str, Any]:
    return json.loads(QUALITY.read_text()) if QUALITY.is_file() else {}


def _values(trait: str, regime: str, day: int | None = None,
            leaf_position: str | None = None) -> list[float]:
    tables = _tables()
    if trait in {key for key in TRAITS if key in ("fvPOverFmP", "npqT", "phiNO", "phiNPQ",
                                                  "phi2", "spad")}:
        rows = tables["photosynthesis"]
        selected = [row for row in rows if row["trait"] == trait and row["regime"] == regime]
        if day is not None:
            selected = [row for row in selected if int(row["daysAfterSowing"]) == day]
    elif trait in PIGMENT_TRAITS:
        rows = tables["pigments"]
        selected = [row for row in rows if row["trait"] == trait and row["regime"] == regime]
        if leaf_position:
            selected = [row for row in selected if row["leafPosition"] == leaf_position]
    else:
        rows = tables["harvest"]
        selected = [row for row in rows if row["trait"] == trait and row["regime"] == regime]
    return [float(row["value"]) for row in selected]


def _bootstrap_ci(values: list[float], resamples: int = BOOTSTRAP_RESAMPLES) -> tuple[float, float]:
    if len(values) < 3:
        return (float("nan"), float("nan"))
    # Seeded Mersenne Twister for a percentile bootstrap. Determinism is the requirement here (the
    # interval must be a function of the data, not of when it ran), and nothing secret is drawn.
    generator = random.Random(BOOTSTRAP_SEED + len(values))  # nosec B311
    means = [statistics.fmean(generator.choices(values, k=len(values))) for _ in range(resamples)]
    means.sort()
    return (means[int(0.025 * resamples)], means[int(0.975 * resamples)])


def _bootstrap_difference(a: list[float], b: list[float],
                          resamples: int = BOOTSTRAP_RESAMPLES) -> tuple[float, float]:
    if len(a) < 3 or len(b) < 3:
        return (float("nan"), float("nan"))
    # Same seeded, non-cryptographic generator as `_bootstrap_ci`.
    generator = random.Random(BOOTSTRAP_SEED + len(a) * 7 + len(b))  # nosec B311
    differences = []
    for _ in range(resamples):
        differences.append(statistics.fmean(generator.choices(b, k=len(b)))
                           - statistics.fmean(generator.choices(a, k=len(a))))
    differences.sort()
    return (differences[int(0.025 * resamples)], differences[int(0.975 * resamples)])


def _welch(a: list[float], b: list[float]) -> dict[str, Any]:
    """Welch's unequal-variance t-test: a -> control, b -> treatment."""
    if len(a) < 2 or len(b) < 2:
        return {"t": None, "degreesOfFreedom": None, "pValue": None}
    var_a, var_b = statistics.variance(a), statistics.variance(b)
    denominator = math.sqrt(var_a / len(a) + var_b / len(b))
    if denominator == 0:
        return {"t": None, "degreesOfFreedom": None, "pValue": None}
    t = (statistics.fmean(b) - statistics.fmean(a)) / denominator
    df = ((var_a / len(a) + var_b / len(b)) ** 2 /
          ((var_a / len(a)) ** 2 / (len(a) - 1) + (var_b / len(b)) ** 2 / (len(b) - 1)))
    p_value = None
    try:  # scipy is a declared runtime dependency; the fallback keeps the response well-formed.
        from scipy import stats as scipy_stats
        p_value = float(2 * scipy_stats.t.sf(abs(t), df))
    except Exception:  # noqa: BLE001 - a missing scipy must not break the endpoint
        p_value = None
    return {"t": round(float(t), 3), "degreesOfFreedom": round(float(df), 2),
            "pValue": (round(p_value, 6) if p_value is not None else None)}


def _hedges_g(a: list[float], b: list[float]) -> float | None:
    if len(a) < 2 or len(b) < 2:
        return None
    pooled = math.sqrt(((len(a) - 1) * statistics.variance(a)
                        + (len(b) - 1) * statistics.variance(b)) / (len(a) + len(b) - 2))
    if pooled == 0:
        return None
    correction = 1 - 3 / (4 * (len(a) + len(b)) - 9)
    return round(float((statistics.fmean(b) - statistics.fmean(a)) / pooled * correction), 3)


def summarise(trait: str, regime: str, day: int | None = None) -> dict[str, Any]:
    values = _values(trait, regime, day)
    meta = TRAITS.get(trait) or PIGMENT_TRAITS.get(trait) or {}
    if not values:
        return {"trait": trait, "regime": regime, "available": False, "n": 0,
                "reason": "no observations for this trait in this regime"}
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if len(values) > 1 else None
    low, high = _bootstrap_ci(values)
    return {
        "trait": trait, "regime": regime, "available": True,
        "n": len(values),
        "mean": round(mean, 5 if abs(mean) < 1 else 2),
        "median": round(statistics.median(values), 5 if abs(mean) < 1 else 2),
        "standardDeviation": round(sd, 5 if sd and sd < 1 else 2) if sd is not None else None,
        "standardError": round(sd / math.sqrt(len(values)), 5) if sd is not None else None,
        "minimum": round(min(values), 5) if abs(mean) < 1 else round(min(values), 2),
        "maximum": round(max(values), 5) if abs(mean) < 1 else round(max(values), 2),
        "meanCiLow": round(low, 5) if abs(mean) < 1 else round(low, 2),
        "meanCiHigh": round(high, 5) if abs(mean) < 1 else round(high, 2),
        "ciKind": "bootstrap percentile interval on the mean, seeded, within-experiment",
        "unit": meta.get("unit"), "label": meta.get("label"), "group": meta.get("group"),
        "means": meta.get("means"),
        # Whether a percentage change against this group is worth printing. Kept on the summary so
        # the comparison table does not recompute it from a mean alone.
        "relativeDifferenceMeaningful": bool(
            abs(mean) >= 0.25 * (sd or 0.0) and abs(mean) > 1e-9),
        "daysAfterSowing": day,
    }


def compare_with_control(trait: str, regime: str, day: int | None = None) -> dict[str, Any]:
    if regime == CONTROL:
        return {"applies": False, "reason": "this is the control"}
    control = _values(trait, CONTROL, day)
    treatment = _values(trait, regime, day)
    if len(control) < 2 or len(treatment) < 2:
        return {"applies": False, "reason": "insufficient replicates for a comparison"}
    difference = statistics.fmean(treatment) - statistics.fmean(control)
    control_mean = statistics.fmean(control)
    # A relative change is only meaningful when the control mean is large compared with the
    # between-plant spread. NPQt has a control mean near zero by construction (unstressed leaves do
    # not dissipate regulated heat), so dividing by it produced a −1018 % "change" that was pure
    # arithmetic. Where that happens the relative figure is withheld rather than printed.
    control_sd = statistics.pstdev(control) if len(control) > 1 else 0.0
    relative_is_meaningful = abs(control_mean) >= 0.25 * control_sd and abs(control_mean) > 1e-9
    relative = difference / control_mean if relative_is_meaningful else None
    low, high = _bootstrap_difference(control, treatment)
    test = _welch(control, treatment)
    return {
        "applies": True,
        "controlMean": round(statistics.fmean(control), 5 if abs(difference) < 1 else 2),
        "treatmentMean": round(statistics.fmean(treatment), 5 if abs(difference) < 1 else 2),
        "difference": round(difference, 5 if abs(difference) < 1 else 2),
        "relativeDifference": round(relative, 4) if relative is not None else None,
        "relativeDifferenceMeaningful": relative_is_meaningful,
        "relativeDifferenceNote": None if relative_is_meaningful else (
            "the control mean is not large compared with the between-plant spread, so a percentage "
            "change would be arithmetic rather than a finding; the absolute difference and the "
            "effect size carry the comparison"),
        "differenceCiLow": round(low, 5) if abs(difference) < 1 else round(low, 2),
        "differenceCiHigh": round(high, 5) if abs(difference) < 1 else round(high, 2),
        "welch": test,
        "hedgesG": _hedges_g(control, treatment),
        "nControl": len(control), "nTreatment": len(treatment),
        "withinExperimentOnly": True,
        "reading": ("A p-value here tests whether plants under this regime differ from plants under "
                    "the control in one experiment. It is not a claim about repeating the "
                    "treatment."),
    }


def scenario(request: dict[str, Any]) -> dict[str, Any]:
    regime = request["regime"]
    design = {row["regime"]: row for row in _design()}
    if regime not in design:
        raise KeyError(f"unknown regime: {regime}")
    entry = design[regime]
    day = request.get("daysAfterSowing")
    traits = request.get("traits") or ["freshWeightG", "fvPOverFmP", "phiNO", "npqT"]

    summaries = []
    for trait in traits:
        if trait not in TRAITS and trait not in PIGMENT_TRAITS:
            continue
        summary = summarise(trait, regime, day if trait in TRAITS and TRAITS[trait]["group"] == "stress" else None)
        summary["versusControl"] = compare_with_control(
            trait, regime, day if trait in TRAITS and TRAITS[trait]["group"] == "stress" else None)
        summaries.append(summary)

    return {
        "label": request.get("label") or f"{entry['sourceLabel']}: {entry['description']}",
        "regime": regime,
        "design": {
            "sourceLabel": entry["sourceLabel"],
            "description": entry["description"],
            "greenFractionPct": float(entry["greenFractionPct"]),
            "greenFractionIsApproximate": entry["greenFractionIsApproximate"] == "True",
            "greenRegimeFixed": entry["greenRegimeFixed"] == "True",
            "relativePlantingDensity": float(entry["relativePlantingDensity"]),
            "confoundsSpectrumWithDensity": entry["confoundsSpectrumWithDensity"] == "True",
            "ppfdUmolPerM2S": float(entry["ppfdUmolPerM2S"]),
            "photoperiodHours": float(entry["photoperiodHours"]),
            "dailyLightIntegralMolPerM2Day": float(entry["dailyLightIntegralMolPerM2Day"]),
            "harvestDaysAfterSowing": int(float(entry["harvestDaysAfterSowing"])),
        },
        "traits": summaries,
        "isMeasurement": True,
        "isModelPrediction": False,
    }


def compare(requests: list[dict[str, Any]]) -> dict[str, Any]:
    scenarios = [scenario(item) for item in requests]
    rows = []
    for item in scenarios:
        for trait in item["traits"]:
            rows.append({
                "label": item["label"], "regime": item["regime"], "trait": trait["trait"],
                "traitLabel": trait["label"], "unit": trait["unit"],
                "n": trait["n"], "mean": trait["mean"],
                "ciLow": trait["meanCiLow"], "ciHigh": trait["meanCiHigh"],
                "greenFractionPct": item["design"]["greenFractionPct"],
                "relativePlantingDensity": item["design"]["relativePlantingDensity"],
            })

    deltas = []
    baseline = scenarios[0]
    for item in scenarios[1:]:
        for trait in item["traits"]:
            match = next((t for t in baseline["traits"] if t["trait"] == trait["trait"]), None)
            if match is None or not match["available"] or not trait["available"]:
                continue
            difference = trait["mean"] - match["mean"]
            deltas.append({
                "comparedWith": baseline["label"],
                "label": item["label"],
                "trait": trait["trait"],
                "traitLabel": trait["label"],
                "difference": round(difference, 5 if abs(difference) < 1 else 2),
                "relativeDifference": (round(difference / match["mean"], 4)
                                       if match.get("relativeDifferenceMeaningful", True)
                                       and match["mean"] else None),
                "relativeDifferenceMeaningful": bool(
                    match.get("relativeDifferenceMeaningful", True)
                    and trait.get("relativeDifferenceMeaningful", True)),
                "unit": trait["unit"],
                "meansAreSeparated": (trait["meanCiLow"] > match["meanCiHigh"]
                                      or trait["meanCiHigh"] < match["meanCiLow"]),
                "note": ("Bootstrap intervals on the two means do not overlap, so the difference "
                         "is larger than the within-experiment spread. This is still one "
                         "experiment."
                         if (trait["meanCiLow"] > match["meanCiHigh"]
                             or trait["meanCiHigh"] < match["meanCiLow"]) else
                         "The bootstrap intervals overlap; the two regimes are not separated by "
                         "this experiment's between-plant spread."),
            })

    quality = _quality()
    return {
        "workflow": "light-stress",
        "status": "complete",
        "evidenceClass": "measured-observation",
        "isSimulation": False,
        "title": "Environmental stress and growth response under light quality — measured",
        "scenarios": scenarios,
        "comparison": {"rows": rows, "deltas": deltas,
                       "baseline": baseline["label"],
                       "note": ("All differences are differences between measured groups in one "
                                "experiment, in the unit stated per row. They are not model "
                                "outputs and they are not predictions.")},
        "factors": FACTORS,
        "supportedFactors": [factor["factor"] for factor in FACTORS if factor["supported"]],
        "unsupportedFactors": [factor["factor"] for factor in FACTORS if not factor["supported"]],
        "provenance": {
            "source": SOURCE,
            "rawFileSha256": (quality.get("source", {}).get("file", {}).get("sha256")),
            "verifiedAgainstManifest": (quality.get("source", {})
                                        .get("file", {}).get("verifiedAgainstManifest")),
            "processedFiles": ["data/processed/phase29/light_spectrum_treatments.csv",
                               "data/processed/phase29/light_stress_harvest.csv",
                               "data/processed/phase29/light_stress_photosynthesis.csv",
                               "data/processed/phase29/light_stress_pigments.csv"],
            "recordCounts": quality.get("records"),
            "exclusions": quality.get("exclusions"),
        },
        "evidence": {
            "layers": [
                {"kind": "measured-observation", "isMeasurement": True,
                 "what": "per-plant destructive harvest traits under four spectral regimes",
                 "provenance": f"{SOURCE['citation']} · {SOURCE['doi']} · {SOURCE['license']}"},
                {"kind": "measured-observation", "isMeasurement": True,
                 "what": "per-plant chlorophyll fluorescence at 28 and 35 days after sowing",
                 "provenance": "MultispeQ sheet of the same Zenodo record"},
                {"kind": "measured-observation", "isMeasurement": True,
                 "what": "per-sample leaf pigment and antioxidant assays",
                 "provenance": "Postharvest_assays sheet of the same Zenodo record"},
                {"kind": "derived-statistic", "isMeasurement": False,
                 "what": "group means, bootstrap intervals, Welch tests and Hedges' g",
                 "provenance": "computed at request time from the rows above; seeded and "
                               "recomputable"},
            ],
            "distinction": ("Every number in this workflow is either a measured value or a statistic "
                            "of measured values. None of it is a model prediction, and the "
                            "workflow never extrapolates to a regime that was not grown."),
        },
        "limitations": LIMITATIONS,
        "designLimits": quality.get("design", {}),
        "method": {
            "name": "measured comparison with bootstrap intervals and Welch tests",
            "bootstrapResamples": BOOTSTRAP_RESAMPLES,
            "bootstrapSeed": BOOTSTRAP_SEED,
            "test": "Welch's t-test (unequal variances), two-sided",
            "effectSize": "Hedges' g with the small-sample correction",
            "pseudoReplication": ("replicate plants share a chamber; intervals and p-values are "
                                  "within-experiment quantities"),
            "compositeScore": "none computed, deliberately",
        },
        "units": units.block(
            freshWeightG="g/plant", dryWeightG="g/plant", leafNumber="count", leafAreaMm2="mm2",
            fvPOverFmP="fraction", npqT="dimensionless", phiNO="fraction", phiNPQ="fraction",
            phi2="fraction", spad="spad-index", chlorophyllAMgPerGFw="mg/g fresh weight",
            chlorophyllBMgPerGFw="mg/g fresh weight", totalCarotenoidsMgPerGFw="mg/g fresh weight",
            totalChlorophyllMgPerGFw="mg/g fresh weight",
            totalFlavonoidsMgQePerGFw="mg quercetin equiv/g FW",
            totalPolyphenolsMgGaePerGFw="mg gallic acid equiv/g FW",
            antioxidantActivityUmQe="umol quercetin equiv", greenFractionPct="%",
            ppfdUmolPerM2S="umol/m2/s", photoperiodHours="h/day",
            dailyLightIntegralMolPerM2Day="mol/m2/day", relativePlantingDensity="dimensionless",
        ),
    }


def capability() -> dict[str, Any]:
    design = _design()
    return {
        "workflow": "light-stress",
        "title": "Environmental stress and growth response under light quality — measured",
        "evidenceClass": "measured-observation",
        "isSimulation": False,
        "crop": {"name": "lettuce", "cultivar": "Red Batavia"},
        "regimes": [
            {"regime": row["regime"], "label": f"{row['sourceLabel']}: {row['description']}",
             "greenFractionPct": float(row["greenFractionPct"]),
             "relativePlantingDensity": float(row["relativePlantingDensity"]),
             "confoundsSpectrumWithDensity": row["confoundsSpectrumWithDensity"] == "True",
             "isControl": row["regime"] == CONTROL}
            for row in design
        ],
        "fixedConditions": {
            "ppfdUmolPerM2S": float(design[0]["ppfdUmolPerM2S"]),
            "photoperiodHours": float(design[0]["photoperiodHours"]),
            "dailyLightIntegralMolPerM2Day": float(design[0]["dailyLightIntegralMolPerM2Day"]),
            "note": ("held constant across every regime, which is why this workflow offers no "
                     "PPFD or photoperiod response"),
        },
        "fields": [
            {"name": "regime", "label": "Spectral regime", "kind": "select",
             "options": [row["regime"] for row in design],
             "why": ("The only factor this experiment varied. Each regime is a measured group, not "
                     "a modelled level.")},
            {"name": "traits", "label": "Traits to report", "kind": "multiselect",
             "options": [{"value": key, "label": meta["label"], "unit": meta["unit"],
                          "group": meta["group"]} for key, meta in
                         {**TRAITS, **PIGMENT_TRAITS}.items()],
             "why": ("Growth traits answer what the plant produced; stress indicators answer what "
                     "the light did to its photochemistry. They are different questions.")},
            {"name": "daysAfterSowing", "label": "Measurement day for stress indicators",
             "kind": "select", "options": [28, 35], "unit": "day",
             "why": ("Fluorescence was measured twice. Day 28 is mid-cycle; day 35 is harvest. A "
                     "stress signal that appears only at harvest is a different finding from one "
                     "present mid-cycle.")},
        ],
        "maxScenarios": MAX_SCENARIOS,
        "supportedFactors": [factor["factor"] for factor in FACTORS if factor["supported"]],
        "unsupportedFactors": [factor for factor in FACTORS if not factor["supported"]],
        "factors": FACTORS,
        "notes": ("Measured comparison only. No response surface, no CO2 response, no light-"
                  "intensity response, no simulation."),
        "units": units.block(freshWeightG="g/plant", fvPOverFmP="fraction", phiNO="fraction",
                             npqT="dimensionless", greenFractionPct="%"),
    }
