"""
Human-readable description of the Phase 1 model, built from the constants.

The dashboard shows a collapsible "model assumptions" panel. Rather than
hard-coding the numbers a second time in the frontend, the backend describes
its own model here, so a change in `simulation_constants.py` is reflected in
the UI automatically and the constants stay the single source of truth.
"""

from __future__ import annotations

from app.config import simulation_constants as constants

MODEL_STATUS = {
    "phase": "Phase 1",
    "kind": "Mathematical prototype",
    "dataSource": "Documented simulation assumptions (no measured datasets)",
    "validation": "Not validated against NASA or experimental data",
    "planned": [
        "Phase 2 - NASA open-science calibration (GeneLab / OSDR) and model expansion: "
        "climate and nutrient controls (temperature, relative humidity, nutrients, pressure) "
        "and crew-atmosphere balance (human metabolic demand, closed-loop crop + crew life support)",
        "Phase 3 - ML / model fitting: replacing assumed response curves with fitted parameters",
        "Phase 4 - full mission digital twin built on the calibrated model",
    ],
}


def _normalise(entries: list[dict]) -> list[dict]:
    for entry in entries:
        entry.setdefault("evidence", None)
        entry.setdefault("sources", [])
        # `/api/config` serialises through a response model and `/api/assumptions` does not, so a
        # key that only one path emits makes the two answers disagree. Every component states it.
        entry.setdefault("validation", None)
    return entries


def reference_et0_component() -> dict:
    """The optional reference-flux water path, described like every other component.

    It is listed among the assumptions rather than hidden in the API docs because it changes what
    the litres mean: `crop-relative` is the simulator's own peak demand, `et0-reference` is a
    flux-driven demand that is only as good as the ET0 fed into it.
    """
    from app import et0

    status = et0.physics_status()
    return {
        "key": "reference-et0",
        "title": "Reference-flux water demand (optional)",
        "formula": "demand(day) = ET0 [mm/day] x Kc x area [m2] x canopyScale(day)",
        "note": (
            "Only used when a caller supplies et0MmPerDay. 1 mm over 1 m2 is 1 litre, so the flux "
            "converts directly and no constant is invented. The light and VPD scales are NOT "
            "applied on this path: ET0 already contains the site's radiation and humidity. "
            "Kc defaults to 1.0, which is the reference grass surface, not a crop."
        ),
        "constants": {
            "defaultCropCoefficient": constants.DEFAULT_CROP_COEFFICIENT,
            "litresPerMmPerM2": constants.ET0_MM_PER_M2_TO_LITRES,
            "plausibleMinMmPerDay": constants.ET0_PLAUSIBLE_RANGE_MM_PER_DAY[0],
            "plausibleMaxMmPerDay": constants.ET0_PLAUSIBLE_RANGE_MM_PER_DAY[1],
        },
        "sources": [
            "FAO-56 Penman-Monteith daily reference evapotranspiration (computed here, "
            "checked against the manual's worked examples)",
            "NASA POWER daily agroclimatology, community AG (reanalysis, citation requested)",
        ],
        "evidence": (
            "ET0 is a computed standard for a hypothetical reference surface, not a measurement "
            "of the modelled crop's water use. It is implemented as FAO-56 Penman-Monteith, "
            "checked against the manual's worked examples, with Hargreaves-Samani when radiation "
            "or wind is absent. The fitted emulator that used to be offered beside it was removed "
            "in Phase 31: it was trained on derived ET0 and lost to Hargreaves on an unseen site."
        ),
        "validation": {
            "workedExamplesWithinTolerance": status.get("allExamplesWithinTolerance"),
            "measuredEt0Benchmark": status.get("measuredEt0Validation"),
        },
    }


def describe_assumptions() -> list[dict]:
    """One entry per model component: formula, constants and a plain-language note.

    `evidence` and `sources` are filled in for every component, empty where nothing backs it, so
    `/api/config` (validated through `ModelAssumption`) and `/api/assumptions` (served raw) return
    the same objects. A component with no source says so instead of omitting the field.
    """
    entries = [
        reference_et0_component(),
        {"key": "intensity", "title": "PPFD response (assumed)",
         "formula": "factor = [I/(I+200)] / [300/(300+200)]",
         "note": "Uncalibrated saturating response. Spectrum is annotation only; DLI = I * hours * 0.0036 mol/m?/day.",
         "constants": {"referencePPFD": 300.0, "halfSaturationPPFD": 200.0}},
        {"key": "temperature", "title": "Temperature response (assumed)",
         "formula": "factor = exp(-((T-22)/12)^2)",
         "note": "Generic assumed Gaussian response, not crop-specific measured physiology.",
         "constants": {"referenceCelsius": 22.0, "widthCelsius": 12.0}},
        {"key": "humidity", "title": "Humidity response and water scaling (assumed)",
         "formula": "factor = exp(-((RH-60)/50)^2); demand *= VPD(T,RH)/VPD(22,60)",
         "note": "VPD uses the FAO saturation vapor pressure relationship. Proportional water scaling is uncalibrated; not full Penman-Monteith.",
         "constants": {"referenceRH": 60.0, "widthRH": 50.0}},
        {
            "key": "growth",
            "title": "Growth curve",
            "formula": "biomass(day) = harvestBiomass × combinedFactor × area × logistic(day / cycleLength)",
            "note": (
                "Each crop follows a normalised logistic (S-shaped) curve over its cycle and is "
                "harvested and replanted when the cycle ends. Biomass that has not reached the end "
                "of a cycle is standing biomass, not harvested yield."
            ),
            "constants": {"logisticSteepness": constants.LOGISTIC_STEEPNESS},
        },
        {
            "key": "radiation",
            "title": "Radiation response",
            "formula": "factor = exp(−decay × sensitivity × (dose − earthBackground))",
            "note": (
                "Exponential decline of growth with chronic dose rate above Earth background. Plants "
                "tolerate radiation far better than animals; the steepness is chosen so the effect is "
                "visible on the slider, not measured."
            ),
            "constants": {
                "decayPerMgyPerDay": constants.RADIATION_DECAY_PER_MGY_PER_DAY,
                "earthBackgroundMgyPerDay": constants.EARTH_BACKGROUND_RADIATION_MGY_PER_DAY,
            },
        },
        {
            "key": "water",
            "title": "Water response",
            "formula": "factor = (availability / 100) ^ exponent",
            "note": "Growth scales with the share of demand that is actually supplied (linear by default).",
            "constants": {"responseExponent": constants.WATER_RESPONSE_EXPONENT},
        },
        {
            "key": "light",
            "title": "Light response",
            "formula": "factor = [h/(h+K)] / [opt/(opt+K)] * (1 - excessPenalty * max(h-opt,0))",
            "note": (
                "Saturating photoperiod response normalised to the crop's optimal light hours, with a "
                "mild penalty for every hour beyond it (plants need a dark period)."
            ),
            "constants": {
                "saturationHours": constants.LIGHT_SATURATION_HOURS,
                "excessPenaltyPerHour": constants.EXCESS_LIGHT_PENALTY_PER_HOUR,
            },
        },
        {
            "key": "co2",
            "title": "CO₂ response",
            "formula": "factor = [c / (c + K)] / [ambient / (ambient + K)]",
            "note": "Rectangular hyperbola normalised so Earth ambient CO₂ gives 1.0; enrichment saturates.",
            "constants": {
                "halfSaturationPpm": constants.CO2_HALF_SATURATION_PPM,
                "ambientPpm": constants.EARTH_AMBIENT_CO2_PPM,
            },
        },
        {
            "key": "waterLoop",
            "title": "Water demand, supply and recovery",
            "formula": (
                "demand = peakWater × area × lightFactor × (seedling + (1 − seedling) × growthFraction); "
                "supplied = demand × availability; deficit = demand − supplied; recovered = supplied × recovery"
            ),
            "note": (
                "Demand follows the canopy. Water the crop uses is mostly transpired and can be "
                "condensed back; the recovery share is a closed-loop assumption, not a measured "
                "hardware figure."
            ),
            "constants": {
                "recoveryEfficiency": constants.WATER_RECOVERY_EFFICIENCY,
                "seedlingActivityFraction": constants.SEEDLING_ACTIVITY_FRACTION,
            },
        },
        {
            "key": "gasExchange",
            "title": "CO₂ removal and O₂ production",
            "formula": (
                "co2 = (edibleGain / harvestIndex) × dryMatter × carbonFraction × 44/12; o2 = co2 × 32/44"
            ),
            "note": (
                "Gas exchange is derived from the biomass actually put on each day, so it always "
                "moves with growth. Crew-day equivalents are a reference scale only; crew metabolism "
                "and the full atmospheric balance are not modelled."
            ),
            "constants": {
                "carbonFractionOfDryMass": constants.CARBON_FRACTION_OF_DRY_MASS,
                "co2PerCarbon": round(constants.CO2_PER_CARBON_MASS_RATIO, 4),
                "o2PerCo2": round(constants.O2_PER_CO2_MASS_RATIO, 4),
                "crewO2KgPerDay": constants.CREW_MEMBER_O2_KG_PER_DAY,
                "crewCo2KgPerDay": constants.CREW_MEMBER_CO2_KG_PER_DAY,
            },
        },
        {
            "key": "closedLoop",
            "title": "Ethylene and water closure",
            "formula": "not applied to growth; served as measured reference (GET /api/closed-loop)",
            "note": (
                "Two questions this simulator used to answer with a caveat now have measured NASA "
                "numbers beside it. Ethylene: 20 m² stands reached 40–120 ppb in NASA's Biomass "
                "Production Chamber, and controlled chamber work on lettuce measured 1–25 % dry "
                "weight loss at 55 nL L⁻¹ and 25–50 % at 120 nL L⁻¹. Ethylene is deliberately not a "
                "term in the growth equations — no scrubbing, leakage or uptake kinetics were "
                "measured in a form that would support one, so inventing the term would be worse "
                "than omitting it. Water: the ISS recovers 98 % of the water it brings aboard "
                "(93–94 % before the brine processor), so that is where the recycling control's "
                "upper bound comes from."
            ),
            "constants": {},
        },
        {
            "key": "earthReference",
            "title": "Earth reference run",
            "formula": "Earth run = background radiation; matched keeps your resources, baseline resets them",
            "note": (
                "Matched resources isolates radiation by giving the Earth run the same "
                "water, light and CO₂. Earth baseline compares against reference resources instead "
                "(full water, the crop's optimal photoperiod, ambient CO₂)."
            ),
            "constants": {
                "earthBackgroundMgyPerDay": constants.EARTH_BACKGROUND_RADIATION_MGY_PER_DAY,
                "referenceWaterPercent": constants.EARTH_REFERENCE_WATER_AVAILABILITY,
                "ambientCo2Ppm": constants.EARTH_AMBIENT_CO2_PPM,
            },
        },
    ]
    return _normalise(entries)
