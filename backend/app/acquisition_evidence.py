"""What the Phase 36 acquisition actually bought, served rather than filed.

Why this module exists
----------------------
Phase 36 acquired five datasets and produced four analyses. All of it was written to
``data/research/phase36/`` and described in a report, which is the right place for the argument and
the wrong place for the numbers: a reader of the running product cannot check a claim that only
exists in a Markdown file. This module serves the numbers that survived adjudication, with the
label that says what kind of number each one is.

The three labels, and why they are not decoration
-------------------------------------------------
Every value returned here carries one of:

``measured``   read off an instrument by somebody else, at a stated place and time.
``derived``    computed from measurements by an arithmetic step this repository performs and can
               reproduce, so it is only as good as that step.
``predicted``  produced by a model. Never a measurement, and never to be read as one.

The distinction is the whole point. An implied crop coefficient of 0.958 computed from measured
lysimeter drainage and modelled reference ET is ``derived``, not ``measured``, because half of the
ratio is a model. A 1.27 K warming delta over Dhaka is ``predicted``, because it comes from one
climate model's response, not from an observation of the future.

What this module refuses to do
------------------------------
* It does not rank the gaps or summarise them into a score. Two closed by data and two closed by
  removing a capability are not two of the same thing, and a single percentage would say they were.
* It does not hide the open ones. Six gaps are open and each comes with the reason, because a list
  that showed only what was fixed would be a marketing page, not an evidence surface.
* It does not invent a value for a missing artefact. A file that is absent produces an explicit
  ``unavailable`` block naming the script that would rebuild it.
"""

from __future__ import annotations
import safedata

import json
from functools import lru_cache
from pathlib import Path

from app.research import DATA, ROOT

PHASE36 = ROOT / "data" / "research" / "phase36"
PHASE37 = ROOT / "data" / "research" / "phase37"
# The runtime bundle carries the inference assets, and it does not carry data/research. Resolving
# these two records through the bundle first and the checkout second means a bundle that omits
# them cannot silently empty the endpoint - which is what a bare `DATA / ...` path did.
GAP_MATRIX = ((DATA / "research" / "dataset_gap_matrix")
              if safedata.exists(DATA / "research" / "dataset_gap_matrix")
              else (ROOT / "data" / "research" / "dataset_gap_matrix"))
CATALOGUE = ((DATA / "research" / "dataset_catalog")
             if safedata.exists(DATA / "research" / "dataset_catalog")
             else (ROOT / "data" / "research" / "dataset_catalog"))
REEVALUATION = ROOT / "ml" / "evaluation" / "phase36_model_reevaluation"
MODEL_EVIDENCE_37 = ROOT / "ml" / "evaluation" / "phase37_model_evidence"

# Gap decisions are recorded per phase. The surface serves the newest decision that exists for each
# gap, and says which phase it came from - a reader must be able to tell whether a status is four
# phases old or today's.
DECISION_BLOCKS = ("phase37Decision", "phase36Decision")

# The status vocabulary of the gap matrix. Phase 36 counts closures three ways because closing a
# gap with a measurement and closing it by withdrawing a feature are different results, and adding
# them together would report progress the product does not have.
STATUS_KEYS = ("CLOSED", "PARTIALLY CLOSED", "OPEN")


def _load(path: Path) -> dict:
    if not safedata.exists(path):
        return {}
    try:
        return safedata.load(path)
    except (OSError, json.JSONDecodeError):
        return {}


@lru_cache(maxsize=1)
def _gap_matrix() -> dict:
    return _load(GAP_MATRIX)


@lru_cache(maxsize=1)
def _catalogue() -> dict:
    return _load(CATALOGUE)


@lru_cache(maxsize=1)
def _reevaluation() -> dict:
    return _load(REEVALUATION)


def _unavailable(name: str, rebuild: str) -> dict:
    return {"available": False, "name": name, "rebuildWith": rebuild}


def gaps() -> dict:
    """The fourteen recorded gaps, their final status and the evidence behind each one.

    The counts are recomputed from the status tokens rather than read from the stored summary, so
    a hand-edit to the summary cannot make the served totals disagree with the entries above them.
    """
    matrix = _gap_matrix()
    entries = matrix.get("gaps") or []
    rows = []
    for entry in entries:
        decision, decided_in = {}, None
        for key in DECISION_BLOCKS:
            if entry.get(key):
                decision, decided_in = entry[key], int(key[5:7])
                break
        token = entry.get("statusToken") or "OPEN"
        rows.append({
            "id": entry.get("id"),
            "capability": entry.get("capability"),
            "severity": entry.get("severity"),
            "status": token,
            # Only the Phase 36 adjudication is served as the current state. An entry with no
            # adjudication is reported as open, because nothing in this phase established otherwise.
            "whatChanged": decision.get("what"),
            "evidence": decision.get("evidence") or [],
            "remainingWork": decision.get("remainingWork"),
            "decidedInPhase": decided_in,
        })
    counts = {key: sum(1 for row in rows if row["status"] == key) for key in STATUS_KEYS}
    # Which closures were achieved by withdrawing a capability rather than by finding a dataset.
    # Taken from the entries themselves so a new phase cannot leave the split pointing at an old
    # summary block.
    # A gap is closed by decision, not by data, when an earlier phase removed the capability rather
    # than finding a measurement. Those entries record it as a decision of kind B with no residual
    # capability, which is a property of the entry rather than of a summary block.
    by_decision = sum(1 for entry in entries
                      if entry.get("statusToken") == "CLOSED"
                      and str((entry.get("phase30Decision") or {}).get("decision", "")).startswith("B"))
    return {
        "total": len(rows),
        "closed": counts["CLOSED"],
        "closedByData": max(counts["CLOSED"] - by_decision, 0),
        "closedByDecision": by_decision,
        "partiallyClosed": counts["PARTIALLY CLOSED"],
        "open": counts["OPEN"],
        "note": (
            "Closed counts include the gaps closed by withdrawing a capability rather than by "
            "finding a dataset; those are counted separately because they are not the same result. "
            "Each row names the phase whose decision it reports."
        ),
        "gaps": rows,
        "source": "data/research/dataset_gap_matrix",
    }


def measured_water_use() -> dict:
    """The two measured-evapotranspiration results, with the label on every number."""
    payload = _load(PHASE36 / "et0_measurement_validation")
    if not payload:
        return _unavailable("measured ET against modelled ET0",
                            "python ml/research/validate_et0_against_measurement.py")
    formulation = payload.get("terenoFormulationTest") or {}
    lysimeter = payload.get("lysimeterLevelTest") or {}
    return {
        "available": True,
        "formulation": {
            "label": "derived",
            "what": ("FAO-56 reference ET0 evaluated on measured available energy, temperature, "
                     "vapour pressure and wind, held against eddy-covariance latent heat."),
            "siteDays": formulation.get("dayCount"),
            "correlation": formulation.get("r"),
            "biasMmPerDay": formulation.get("biasMmDay"),
            "rmseMmPerDay": formulation.get("rmseMmDay"),
            "medianMeasuredOverModelled": (formulation.get("ratioMeasuredOverModelled") or {})
            .get("median"),
            "sites": {
                site: {"r": block.get("r"), "days": block.get("days")}
                for site, block in (formulation.get("bySite") or {}).items()
            },
            "reading": ("A meadow transpires less than the reference sward the equation defines, "
                        "so the level is expected to sit below one. The correlation is what tests "
                        "the formulation; the level tests the reference assumption."),
        },
        "level": {
            "label": "derived",
            "what": ("Measured daily ET from six weighable lysimeters divided by modelled ET0 for "
                     "the same days - an implied crop coefficient."),
            "lysimeterDays": lysimeter.get("dayCount"),
            "activeDays": (lysimeter.get("impliedKcActiveDays") or {}).get("n"),
            "medianImpliedKc": (lysimeter.get("impliedKc") or {}).get("median"),
            "negativeEtaDays": lysimeter.get("negativeEtaDays"),
            "medianImpliedKcActiveDays": (lysimeter.get("impliedKcActiveDays") or {}).get("median"),
            "annualCompleteYears": (lysimeter.get("levelTest") or {}).get("completeYearKc") or {},
            "testPassed": (lysimeter.get("levelTest") or {}).get("passed"),
            "criterion": (lysimeter.get("levelTest") or {}).get("criterion"),
        },
        "limitation": payload.get("limitation") or (
            "The measurement sites are not the six siting sites, and the crop is not lettuce."),
        "source": "data/research/phase36/et0_measurement_validation",
    }


def projected_climate() -> dict:
    """The single-model warming and light response at each reference site."""
    payload = _load(PHASE36 / "projected_climate")
    if not payload:
        return _unavailable("projected environment",
                            "python ml/research/analyze_projected_climate.py")
    sites = {}
    for site, block in (payload.get("sites") or {}).items():
        delta = block.get("delta") or {}
        sites[site] = {
            "meanTasC": delta.get("meanTasC"),
            "meanTasmaxC": delta.get("meanTasmaxC"),
            "meanVpdKpa": delta.get("meanVpdKpa"),
            "meanDliMolM2D": delta.get("meanDliMolM2D"),
            "daysAbove30C": delta.get("daysAbove30C"),
            "annualPrecipMm": delta.get("annualPrecipMm"),
        }
    source = payload.get("source") or {}
    windows = source.get("windows") or {}
    return {
        "available": True,
        "label": "predicted",
        "product": source.get("product"),
        "model": source.get("model"),
        "scenario": source.get("scenario"),
        "baselineWindow": windows.get("baseline"),
        "futureWindow": windows.get("midCentury"),
        "gridResolution": source.get("gridResolution"),
        "limitations": payload.get("limitations") or [],
        "sites": sites,
        "caveat": ("One climate model, one scenario. The spread across models is the uncertainty "
                   "and it is not characterised here, so these are a response to a scenario, not a "
                   "forecast of a season."),
        "source": "data/research/phase36/projected_climate",
    }


def cultivar_and_water() -> dict:
    """The lettuce trial: a measured cultivar contrast and a measured irrigation null."""
    payload = _load(PHASE36 / "iot4lettuce_water_cultivar")
    if not payload:
        return _unavailable("lettuce cultivar and irrigation trial",
                            "python ml/research/analyze_iot4lettuce.py")
    harvest = payload.get("harvestFreshWeight") or {}
    irrigation = payload.get("irrigationContrast") or {}
    cultivar = payload.get("cultivarContrast") or {}
    return {
        "available": True,
        "harvest": {
            "label": "measured",
            "groups": {
                name: {"n": block.get("n"), "meanG": block.get("meanG"), "sdG": block.get("sdG")}
                for name, block in harvest.items()
            },
        },
        "irrigation": {
            "label": "measured",
            "differenceG": irrigation.get("differenceOfMeans"),
            "permutationP": irrigation.get("permutationP"),
            "permutationPFloor": irrigation.get("permutationPFloor"),
            "bootstrap95": irrigation.get("bootstrap95"),
            "reading": ("Not distinguishable from zero. The trial bounds the yield response over "
                        "this application range; it does not establish a slope."),
        },
        "cultivar": {
            "label": "measured",
            "differenceG": cultivar.get("differenceOfMeans"),
            "permutationP": cultivar.get("permutationP"),
            "bootstrap95": cultivar.get("bootstrap95"),
            "ratio": cultivar.get("ratioGrandRapidOverLolloRossa"),
        },
        "ky": {
            "label": "derived",
            "conditional": True,
            "scenarios": [
                {"assumedEtRatio": block.get("assumedEtRatio50over75"),
                 "impliedKy": block.get("impliedKy")}
                for block in ((payload.get("kyAccounting") or {}).get("scenarios") or [])
            ],
            "whyConditional": ("No per-treatment evapotranspiration was measured, so the water-use "
                               "axis is a design assumption and not a measurement."),
        },
        "source": "data/research/phase36/iot4lettuce_water_cultivar",
    }


def hourly_information_loss() -> dict:
    """What a daily mean hides, measured rather than argued."""
    payload = _load(PHASE36 / "hourly_environment")
    if not payload:
        return _unavailable("hourly environment",
                            "python ml/research/analyze_hourly_environment.py")
    sites = {}
    for site, block in (payload.get("sites") or {}).items():
        sites[site] = {
            "dliMolM2D": block.get("dliMeanMolM2D"),
            "meanVpdKpa": block.get("vpdMeanKpa"),
            "hoursAbove2500PaVpd": (block.get("hoursAboveKpa") or {}).get("2.5"),
            "shareDliWithin2hOfNoon": (block.get("dliFractionAroundNoon") or {}).get("meanFraction"),
            "meanDiurnalRangeC": block.get("diurnalRangeMeanC"),
            "daysWith400PlusAbove2500Pa": block.get("daysWith400PlusAbove2p5"),
        }
    loss = payload.get("informationLossTest") or {}
    return {
        "available": True,
        "label": "measured",
        "period": payload.get("period"),
        "sites": sites,
        "claim": payload.get("claim"),
        "informationLossTest": {
            "ambiguousDailyMeanBins": loss.get("dailyMeanVpdBinsWithAmbiguity"),
            "maxSpreadHoursWithinOneBin": loss.get("maxSpreadHoursWithinOneBin"),
            "reading": ("Days that share a daily-mean VPD can differ by this many hours of "
                        "above-threshold exposure. A controller sized on the daily mean cannot "
                        "see that difference, which is what the hourly acquisition buys."),
        },
        "source": "data/research/phase36/hourly_environment",
    }


def model_outcomes() -> dict:
    """What the independent campaign did to each model - including where it proved nothing."""
    payload = _reevaluation()
    if not payload:
        return _unavailable("model re-evaluation",
                            "python ml/research/phase36_model_reevaluation.py")
    models = payload.get("models") or {}
    counts = payload.get("counts") or {}
    return {
        "available": True,
        "counts": {
            "served": counts.get("served"),
            "scored": counts.get("scored"),
            "domainRefused": counts.get("domainRefused"),
            "noNewEvidence": counts.get("noNewEvidence"),
            "decisionGradeBefore": counts.get("decisionGradeBefore"),
            "decisionGradeAfter": counts.get("decisionGradeAfter"),
        },
        "models": [
            {
                "id": model_id,
                "outcome": block.get("outcome"),
                "reason": block.get("reason"),
                "artifactUnchanged": block.get("artifactUnchanged"),
            }
            for model_id, block in models.items()
        ],
        "policy": payload.get("policy"),
        "note": (
            "A DOMAIN-REFUSED outcome means the independent campaign falls outside the model's own "
            "declared input domain, so it cannot score the model without contradicting the card. "
            "That is a refusal to answer, not evidence that the model is right."),
        "source": "ml/evaluation/phase36_model_reevaluation",
    }


def spectrum_response() -> dict:
    """What the constant-PPFD spectrum trial measured, and what was derived from it.

    The platform's radiation-quality surface has always carried the assumption that green photons
    are largely wasted. This trial is the first evidence in the repository that can test it,
    because light quantity was held fixed and only composition changed.
    """
    payload = _load(PHASE37 / "led_spectrum_response")
    if not payload:
        return _unavailable("constant-PPFD spectrum response",
                            "python ml/research/analyze_led_spectrum.py")
    design = payload.get("design") or {}
    harvest = (payload.get("harvest") or {}).get("summary") or {}
    fresh = harvest.get("Fresh weight") or {}
    contrasts = {}
    for name, block in ((payload.get("freshWeightContrasts") or {}).get("contrasts") or {}).items():
        if not block.get("available"):
            continue
        contrasts[name] = {
            "label": "derived",
            "differenceGramsPerPlant": block.get("differenceOfMeans"),
            "relativeChange": block.get("relativeChange"),
            "permutationP": block.get("permutationP"),
            "permutations": block.get("permutations"),
            "bootstrap95": block.get("bootstrap95"),
            "note": ("Derived by permutation and bootstrap from the destructively harvested "
                     "plants; the comparison is valid only because every arm targeted the same "
                     "PPFD and shared the same photoperiod."),
        }
    confound = payload.get("densityConfound") or {}
    return {
        "available": bool(fresh),
        "sourceStudy": (payload.get("source") or {}).get("title"),
        "doi": (payload.get("source") or {}).get("doi"),
        "license": (payload.get("source") or {}).get("license"),
        "design": {
            "crop": design.get("crop"),
            "ppfdTargetUmolPerM2PerS": design.get("ppfdTargetUmolPerM2PerS"),
            "photoperiod": design.get("photoperiod"),
            "harvestDayAfterSowing": design.get("harvestDayAfterSowing"),
            "arms": len(design.get("treatments") or []),
        },
        "freshWeightByArm": {
            arm: {"label": "measured", "plants": block.get("n"),
                  "meanGrams": block.get("mean"), "sdGrams": block.get("sd")}
            for arm, block in fresh.items()
        },
        "contrasts": contrasts,
        "excludedArm": {
            "arm": confound.get("treatment"),
            "reason": confound.get("whyExcluded"),
            "label": "unavailable",
        } if confound else None,
        "whatThisShows": (
            "Adding green light to a fixed photon budget did not reduce yield: no arm was worse than "
            "the red-blue control, and an incremental green regime yielded more. The assumption "
            "that green photons are wasted is not supported by this trial."),
        "whatThisDoesNotShow": payload.get("limitations"),
        "source": "data/research/phase37/led_spectrum_response",
    }


def nutrient_solution() -> dict:
    """Measured ion concentrations and EC - and the uptake rate that is deliberately absent."""
    payload = _load(PHASE37 / "nutrient_solution")
    if not payload:
        return _unavailable("hydroponic nutrient-solution chemistry",
                            "python ml/research/analyze_nutrient_balance.py")
    measured = payload.get("measuredConcentrations") or {}
    harvest = payload.get("harvest") or {}
    not_derivable = payload.get("whatIsNotDerivable") or {}
    return {
        "available": True,
        "sourceStudy": (payload.get("source") or {}).get("title"),
        "doi": (payload.get("source") or {}).get("doi"),
        "license": (payload.get("source") or {}).get("license"),
        "ionsMeasured": (measured.get("ions") or []),
        "electricalConductivityMeasured": True,
        "phMeasured": bool((payload.get("source") or {}).get("phMeasured")),
        "harvest": {
            "label": "measured",
            "endpoint": harvest.get("endpoint"),
            "byTreatment": {
                name: {"plants": block.get("n"),
                       "freshWeightGrams": (block.get("freshWeightG") or {}).get("mean")}
                for name, block in (harvest.get("byTreatment") or {}).items()
            },
        },
        "uptakeRate": {
            "label": "unavailable",
            "value": None,
            "reason": not_derivable.get("reason"),
            "whatWouldCloseIt": not_derivable.get("whatWouldCloseIt"),
        },
        "source": "data/research/phase37/nutrient_solution",
    }


def model_evidence_phase37() -> dict:
    """The five-way classification of every served model, unchanged from before this phase."""
    payload = _load(MODEL_EVIDENCE_37)
    if not payload:
        return _unavailable("model evidence audit",
                            "python ml/research/audit_models_phase37.py")
    counts = payload.get("counts") or {}
    return {
        "available": True,
        "counts": {
            "served": counts.get("served"),
            "scoredOnNewEvidence": counts.get("scored"),
            "notTestedByNewEvidence": counts.get("notTestedByNewEvidence"),
            "decisionGradeBefore": counts.get("decisionGradeBefore"),
            "decisionGradeAfter": counts.get("decisionGradeAfter"),
        },
        "classification": {
            model_id: {"verdict": block.get("classification"),
                       "why": block.get("why")}
            for model_id, block in (payload.get("models") or {}).items()
        },
        "policy": payload.get("policy"),
        "source": "ml/evaluation/phase37_model_evidence",
    }


def catalogue_summary() -> dict:
    """The published catalogue, by usability class, for the surface that shows what was acquired."""
    payload = _catalogue()
    datasets = payload.get("datasets") or []
    classes: dict[str, int] = {}
    for item in datasets:
        key = item.get("usabilityClass") or "?"
        classes[key] = classes.get(key, 0) + 1
    return {
        "available": bool(datasets),
        "total": len(datasets),
        "byClass": dict(sorted(classes.items())),
        # Four datasets were newly acquired in Phase 36. NEX-GDDP-CMIP6 was already in the
        # catalogue as class D and moved to class A once it was actually imported, so it is listed
        # separately: calling a promotion an acquisition would inflate the count.
        "acquiredThisPhase": [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "license": item.get("license"),
                "licenseEvidence": item.get("licenseEvidence"),
                "classReason": item.get("classReason"),
            }
            for item in datasets
            if item.get("id") in {
                "nasa-power-hourly", "zenodo-agroscope-lysimeter-2026",
                "zenodo-tereno-graswang-fendt", "zenodo-iot4lettuce",
            }
        ],
        "promotedThisPhase": [
            {"id": item.get("id"), "name": item.get("name"), "usabilityClass": item.get("usabilityClass")}
            for item in datasets
            if item.get("id") == "nasa-nex-gddp-cmip6"
        ],
        "source": "data/research/dataset_catalog",
    }


def _interpretation() -> str:
    gap_counts = gaps()
    closed = gap_counts["closed"]
    open_ = gap_counts["open"]
    partial = gap_counts["partiallyClosed"]
    decision_grade = ((_load(MODEL_EVIDENCE_37).get("counts") or {}).get("decisionGradeAfter")
                      if safedata.exists(MODEL_EVIDENCE_37) else None)
    return (
        f"Of fourteen gaps, {closed} are closed, {partial} are partially closed and {open_} remain "
        f"open. {decision_grade if decision_grade is not None else 'No'} model is decision-grade, "
        "and none became so in this phase: the two datasets acquired here fall outside every served "
        "model's declared input domain, so they could test none of them. The acquisition added "
        "measurement where the record had none; it did not make the platform validated, and nothing "
        "here should be read as if it had.")


def payload() -> dict:
    """Everything above, plus the sentence that stops it being read as a scorecard."""
    return {
        "schemaVersion": 1,
        "phase": 36,
        "title": "Scientific data acquisition and evidence completion",
        "labels": {
            "measured": "Read off an instrument by somebody else, at a stated place and time.",
            "derived": "Computed from measurements by an arithmetic step this repository performs.",
            "predicted": "Produced by a model; never a measurement.",
        },
        "gaps": gaps(),
        "waterUse": measured_water_use(),
        "projectedClimate": projected_climate(),
        "cultivarAndWater": cultivar_and_water(),
        "hourly": hourly_information_loss(),
        "models": model_outcomes(),
        "catalogue": catalogue_summary(),
        "spectrumLight": spectrum_response(),
        "nutrientSolution": nutrient_solution(),
        "modelEvidence": model_evidence_phase37(),
        "latestPhase": 37,
        "decisionGradeCount": (((_load(MODEL_EVIDENCE_37).get("counts") or {}).get(
            "decisionGradeAfter"))
            if safedata.exists(MODEL_EVIDENCE_37)
            else ((_reevaluation().get("counts") or {}).get("decisionGradeAfter"))),
        # Recomputed rather than written as prose. The sentence said six were open for four phases
        # after that stopped being true, which is exactly the drift a served number prevents.
        "interpretation": _interpretation(),
        "report": "docs/FINAL_PROJECT_COMPLETION_REPORT.md",
    }
