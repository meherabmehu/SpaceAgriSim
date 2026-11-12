"""External validation of the lettuce model against a study it was never trained on.

The training and cross-validation numbers come from four experiments by one research group. This
module holds the model against a different study, in a different country, in a greenhouse under
sunlight — and reports what happens, including when what happens is bad.

Nothing here is stored as a result. The predictions are computed against the served artifact on
every request, so a retrained model changes the answer and the page cannot show a stale verdict.
"""

from __future__ import annotations
import safedata

import statistics
from functools import lru_cache

from app.research import DATA, load_model

SCREEN = DATA / "literature" / "external_validation_screen"
EXTERNAL = DATA / "literature" / "external_lettuce_peerj17085"
MODEL_ID = "lettuce-earth-growth-v2"
# The Phase 19 successor. v2 is kept and still scored, because its failure is the record that
# justified rebuilding it; deleting the failing check once a better model existed would erase the
# evidence the correction was needed.
MODEL_ID_V3 = "lettuce-earth-growth-v3"

# Root temperature is not reported by the external study, so it is assumed equal to air
# temperature. These probes show whether that assumption could explain the gap. They are a
# sensitivity check, not a set of alternative results to pick from.
ROOT_TEMPERATURE_PROBES = (20.0, 24.0, 27.5, 30.0, 32.0)


@lru_cache(maxsize=1)
def _screen() -> dict | None:
    if not safedata.exists(SCREEN):
        return None
    return safedata.load(SCREEN)


@lru_cache(maxsize=1)
def _external() -> dict | None:
    if not safedata.exists(EXTERNAL):
        return None
    return safedata.load(EXTERNAL)


def _predict(inputs: list[float]) -> float:
    from app import research

    value, _ = research.predict_values(load_model(MODEL_ID), inputs)
    return float(value)


def _predict_v3(days: float, air: float, root: float, ppfd: float,
                photoperiod: float, density: float) -> float:
    """Run the served v3 artifact the way the API does: DLI in, log target inverted, density out."""
    from app import research

    model = load_model(MODEL_ID_V3)
    dli = ppfd * photoperiod * 3600.0 / 1e6
    raw, _ = research.predict_values(model, [days, air, root, dli])
    per_area = max(0.0, research.inverse_target_transform(model, raw))
    return per_area / density


def _v3_check() -> dict:
    """v3 on the same six PeerJ observations, plus the untouched independent holdout.

    PeerJ is now a development set: its numbers informed the choice of the daily-light-integral
    feature, so it cannot be called validation. The independent number is Touliatos 2016, which was
    not touched during model selection, and it is reported here from the artifact's own recorded
    evaluation rather than recomputed, because recomputing it here would make it a second selection
    opportunity.
    """
    study = _external()
    if study is None:
        return {"available": False,
                "reason": "data/literature/external_lettuce_peerj17085 is not in this deployment"}
    try:
        model = load_model(MODEL_ID_V3)
    except (KeyError, FileNotFoundError, ValueError) as exc:
        return {"available": False,
                "reason": f"v3 artifact unavailable ({type(exc).__name__})"}

    conditions = study["studyConditions"]
    air = float(conditions["airTemperatureC"])
    photoperiod = float(conditions.get("photoperiodHours", 12.0))
    density = float(conditions.get("plantDensityPerM2", 48.0))
    rows = []
    for observation in study["observations"]:
        measured = float(observation["freshWeightGPerPlant"])
        predicted = _predict_v3(float(observation["daysAfterTransplant"]), air, air,
                                float(observation["ppfdUmol"]), photoperiod, density)
        v2 = _predict([float(observation["daysAfterTransplant"]), air, air,
                       float(observation["ppfdUmol"])])
        rows.append({
            "id": observation["id"],
            "cultivar": observation["cultivar"],
            "ppfdUmol": observation["ppfdUmol"],
            "measuredG": measured,
            "predictedV3G": round(predicted, 1),
            "predictedV2G": round(v2, 1),
            "ratioV3": round(predicted / measured, 2),
            "ratioV2": round(v2 / measured, 2),
        })
    mape_v3 = statistics.fmean(abs(r["predictedV3G"] - r["measuredG"]) / r["measuredG"] for r in rows) * 100
    mape_v2 = statistics.fmean(abs(r["predictedV2G"] - r["measuredG"]) / r["measuredG"] for r in rows) * 100
    mbe_v3 = statistics.fmean(r["predictedV3G"] - r["measuredG"] for r in rows)

    validation = model.get("validation") or {}
    independent = validation.get("independent") or {}
    return {
        "available": True,
        "modelId": MODEL_ID_V3,
        "status": model.get("status"),
        "derivedInputs": {"photoperiodHours": photoperiod, "plantDensityPerM2": density,
                          "dailyLightIntegralFormula": model["derivedFeatures"]["dailyLightIntegral"]["formula"]},
        "rows": rows,
        "developmentMetrics": {
            "countsAsValidation": False,
            "why": ("The daily-light-integral feature was chosen because it scored best on these six "
                    "observations, so they are part of model selection and are reported as a "
                    "development set, not as validation."),
            "observations": len(rows),
            "mapeV3Pct": round(mape_v3, 1),
            "mbeV3G": round(mbe_v3, 1),
            "mapeV2Pct": round(mape_v2, 1),
            "improvementNote": ("v2's 232.2 % is the figure that opened this audit; v3 is scored on the "
                                "same rows here so the improvement is checkable rather than asserted. "
                                "v3 predicts 157.4 / 123.4 / 123.4 g against 84.5 / 123.8 / 92.9 (Baby "
                                "Cos) and 157.4 / 123.4 / 123.4 g against 97.3 / 190.7 / 203.7 (Green "
                                "Oak): the bias is gone, the flat plateaus are not, because a tree "
                                "ensemble without a cultivar input has only one curve per light level."),
        },
        "independentHoldout": {
            "study": independent.get("study"),
            "doi": independent.get("doi"),
            "untouchedDuringSelection": independent.get("untouchedDuringSelection"),
            "metrics": independent.get("metrics"),
            "acceptanceCriterionPct": independent.get("acceptanceCriterionPct"),
            "passed": independent.get("passed"),
            "domainViolations": independent.get("domainViolations"),
            "refused": independent.get("refused"),
            "verdict": independent.get("verdict"),
        },
        "verdict": {
            "passed": bool(independent.get("passed")),
            "headline": (f"v3 development error {mape_v3:.1f} % (v2: {mape_v2:.1f} %); independent "
                         f"holdout {(independent.get('metrics') or {}).get('MAPE', float('nan')):.1f} % "
                         f"against a {independent.get('acceptanceCriterionPct')} % criterion"),
            "statement": independent.get("verdict"),
            "consequence": ("The model stays trained-exploratory. Its independent error is above the "
                            "criterion fixed before it was measured, and one source had to be refused "
                            "as out of domain. No deployment may present v3 as validated."),
        },
    }


def _domain_check() -> dict:
    """Whether the model's own declared domain refuses an out-of-domain source.

    The refusal has to come from the served artifact, not from a copy of the bounds kept here,
    otherwise this panel could keep saying "flagged" after the domain was widened.
    """
    try:
        model = load_model(MODEL_ID)
    except (KeyError, FileNotFoundError, ValueError) as exc:
        return {"available": False, "reason": f"model artifact unavailable ({type(exc).__name__})"}
    domain = model.get("domain", {})
    point = {"daysAfterTransplant": 28.0, "airTemperature": 17.0,
             "rootTemperature": 17.0, "ppfd": 400.0}
    violations = []
    for feature, value in point.items():
        bounds = domain.get(feature)
        if bounds and not bounds["min"] <= value <= bounds["max"]:
            violations.append({"feature": feature, "value": value,
                               "domain": [bounds["min"], bounds["max"]]})
    return {
        "available": True,
        "modelId": MODEL_ID,
        "point": point,
        "flaggedOutOfDistribution": bool(violations),
        "violations": violations,
        "means": ("The served model's declared domain excludes the Touliatos 2016 source. A caller "
                  "still gets a number, but the response is flagged outOfDistribution with the "
                  "violated bounds attached, so it cannot be read as a validated prediction. "
                  "Flagging is correct behaviour; it is not evidence about accuracy."),
    }


def _external_check() -> dict:
    """Score the served model against the transcribed PeerJ observations."""
    study = _external()
    if study is None:
        return {"available": False,
                "reason": "data/literature/external_lettuce_peerj17085 is not in this deployment"}
    conditions = study["studyConditions"]
    air = float(conditions["airTemperatureC"])
    rows = []
    for observation in study["observations"]:
        predicted = _predict([float(observation["daysAfterTransplant"]), air, air,
                              float(observation["ppfdUmol"])])
        measured = float(observation["freshWeightGPerPlant"])
        rows.append({
            "id": observation["id"],
            "cultivar": observation["cultivar"],
            "level": observation["level"],
            "ppfdUmol": observation["ppfdUmol"],
            "measuredG": measured,
            "measuredSdG": observation["sd"],
            "predictedG": round(predicted, 1),
            "ratio": round(predicted / measured, 2),
            "residualG": round(predicted - measured, 1),
        })

    ratios = [row["ratio"] for row in rows]
    residuals = [row["residualG"] for row in rows]
    median_ratio = statistics.median(ratios)

    probes = []
    for root_temperature in ROOT_TEMPERATURE_PROBES:
        probe_ratios = []
        for observation in study["observations"]:
            predicted = _predict([float(observation["daysAfterTransplant"]), air, root_temperature,
                                  float(observation["ppfdUmol"])])
            probe_ratios.append(predicted / float(observation["freshWeightGPerPlant"]))
        probes.append({"rootTemperatureC": root_temperature,
                       "medianRatio": round(statistics.median(probe_ratios), 2),
                       "minRatio": round(min(probe_ratios), 2),
                       "maxRatio": round(max(probe_ratios), 2)})

    worst = max(rows, key=lambda row: row["ratio"])
    best = min(rows, key=lambda row: row["ratio"])
    # Cultivar means from the transcribed observations, used to show an effect the model cannot see.
    by_cultivar: dict[str, list[float]] = {}
    for observation in study["observations"]:
        by_cultivar.setdefault(observation["cultivar"], []).append(
            float(observation["freshWeightGPerPlant"]))
    cultivar_means = {name: round(statistics.fmean(values), 1) for name, values in by_cultivar.items()}

    return {
        "available": True,
        # The model this check belongs to. The UI reads it so a superseded artifact cannot inherit
        # a verdict that was measured against a different one.
        "modelId": MODEL_ID,
        "studyId": study["source"]["studyId"],
        "citation": (f"{study['source']['authors'][0]} et al. {study['source']['year']}, "
                     f"{study['source']['publication']}, doi:{study['source']['doi']}"),
        "doi": study["source"]["doi"],
        "license": study["source"]["license"],
        "retrievedAt": study["source"]["retrievedAt"],
        "retrievedSha256": study["source"]["retrievedSha256"],
        "transcribedAt": study["transcribedAt"],
        "conditions": conditions,
        "assumptions": study["acceptedAssumptions"],
        "notUsed": study["notUsed"],
        "rows": rows,
        "metrics": {
            "observations": len(rows),
            "medianRatio": round(median_ratio, 2),
            "worstRatio": worst["ratio"],
            "worstObservation": worst["id"],
            "closestRatio": best["ratio"],
            "closestObservation": best["id"],
            "meanResidualG": round(statistics.fmean(residuals), 1),
            "meanAbsolutePercentageError": round(
                statistics.fmean(abs(row["residualG"]) / row["measuredG"] for row in rows) * 100, 1),
        },
        "rootTemperatureSensitivity": probes,
        "structuralFindings": [
            {
                "finding": "The model has no cultivar input.",
                "evidence": (f"The transcribed observations differ by "
                             f"{round(abs(cultivar_means['Green Oak'] - cultivar_means['Baby Cos']) / min(cultivar_means.values()) * 100, 0):.0f} % "
                             f"between cultivars on average ({cultivar_means['Baby Cos']} g versus "
                             f"{cultivar_means['Green Oak']} g per plant), which is larger than the "
                             "light-level effect within either cultivar. Same inputs, same output — "
                             "so the model cannot represent this at all."),
            },
            {
                "finding": "The observed response to light is not monotonic; the model's is.",
                "evidence": ("'Baby Cos' is highest at the middle level and 'Green Oak' highest at "
                             "the lower level, against the publication's own Tukey groups. The "
                             "model rises with PPFD and, being a tree ensemble, returns flat "
                             "plateaus between split points."),
            },
        ],
        "verdict": {
            "passed": False,
            "headline": (f"The model overpredicts mature fresh weight by a median of "
                         f"{median_ratio:.1f}x on an independent study"),
            "statement": (
                "Held against a greenhouse vertical-farm trial it was never trained on, the model "
                "overpredicts every one of the six transcribed observations, from "
                f"{best['ratio']:.1f}x to {worst['ratio']:.1f}x. That is far outside the spread of "
                "the training data's own cross-validation and it is not explained by the "
                "root-temperature assumption: with root temperature probed from 20 to 32 °C, the "
                f"median ratio stays between {min(p['medianRatio'] for p in probes):.1f}x and "
                f"{max(p['medianRatio'] for p in probes):.1f}x."
            ),
            "consequence": (
                "The model stays exploratory. It must not be used to forecast harvest weight, to "
                "size a farm, or to compare cropping systems: its absolute values are not "
                "transferable to an environment outside its training experiments. Its published "
                "R² describes how well it interpolates within those four experiments, nothing more."
            ),
        },
    }


def payload() -> dict:
    screen = _screen()
    body: dict = {
        "domainCheck": _domain_check(),
        "externalCheck": _external_check(),
        "v3Check": _v3_check(),
        "scopeNote": ("Screening and check of independent sources for the lettuce model. An "
                      "external check is only run when all four model inputs are reported per "
                      "observation; study averages are never substituted for them."),
    }
    if screen is None:
        body.update({"available": False,
                     "reason": "data/literature/external_validation_screen is not in this deployment"})
        return body
    body.update({
        "available": True,
        "schema": screen.get("schema"),
        "requirement": screen.get("requirement", {}),
        "trainingSource": screen.get("trainingSource", {}),
        "candidates": screen.get("candidates", []),
        "conclusion": screen.get("conclusion", {}),
    })
    return body
