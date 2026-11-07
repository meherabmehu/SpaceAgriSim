"""Scientific evidence classification for every prediction surface in the API.

Phase 8 requires that each existing prediction or optimisation feature be
classified into exactly one of six categories, and that anything landing in
category 6 - unsupported scientific prediction - is removed or disabled as a
predictive feature.

The taxonomy lives here, in one place, so the classification cannot drift between
the API, the documentation and the tests. `app.routes.research` serves it and
`backend/tests/test_phase8_scientific_integrity.py` asserts it stays complete and
internally consistent.

Categories
----------
1  NASA-measured and directly supported      - measured quantity, same crop, same unit
2  NASA-calibrated with compatible data      - measured elsewhere, defensible transfer
3  Experimentally supported by non-NASA data - external measured dataset
4  Mechanistic calculation with assumptions  - documented physics/stoichiometry
5  Hypothetical scenario exploration         - clearly framed what-if output
6  Unsupported scientific prediction         - must not be served as a prediction
"""
from __future__ import annotations

from dataclasses import dataclass, field

CATEGORY_NAMES = {
    1: "NASA-measured and directly supported",
    2: "NASA-calibrated with compatible measurements",
    3: "Experimentally supported by non-NASA data",
    4: "Mechanistic calculation with explicit assumptions",
    5: "Hypothetical scenario exploration",
    6: "Unsupported scientific prediction",
}

# Services the API is allowed to make at each category. Category 6 has no
# entry: nothing may be served as a prediction at that level.
SERVICE_ALLOWED = {
    1: "Measured-value prediction within the measured domain",
    2: "Calibrated prediction with stated transfer assumptions",
    3: "Experimental prediction within the external dataset's domain",
    4: "Mechanistic estimate; assumptions stated with the number",
    5: "Hypothetical exploration; must never be labelled a forecast",
    6: "MUST NOT BE SERVED AS A PREDICTION",
}


@dataclass(frozen=True)
class Feature:
    id: str
    name: str
    surface: str
    category: int
    status: str
    evidence: str
    user_facing: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "surface": self.surface,
            "category": self.category,
            "categoryName": CATEGORY_NAMES[self.category],
            "serviceAllowed": SERVICE_ALLOWED[self.category],
            "status": self.status,
            "evidence": self.evidence,
            "userFacing": self.user_facing,
            "notes": self.notes,
        }


FEATURES: list[Feature] = [
    # ------------------------- category 3: external measured -----------------
    Feature(
        id="lettuce-earth-growth-v1",
        name="Earth lettuce fresh shoot mass (random forest)",
        surface="POST /api/predict/lettuce-earth-growth-v1",
        category=3,
        status="served-superseded",
        evidence=(
            "WUR lettuce dataset, 1648 plants across 4 experiments, held-out-"
            "experiment R2 0.880. External data, not NASA."
        ),
        user_facing=(
            "Still served and still disclosed as an Earth-only experimental model, but "
            "marked deprecated in OpenAPI in favour of v2, which beat it on every "
            "held-out experiment."
        ),
        notes=[
            "Earth-only domain: 2-29 days after transplant, air/root 20-32 C, PPFD 200-750.",
            "Tip-burn treatment combinations were omitted from the source analysis and are refused.",
        ],
    ),
    Feature(
        id="lettuce-earth-growth-v2",
        name="Earth lettuce fresh shoot mass (gradient boosting)",
        surface="POST /api/predict/lettuce-earth-growth-v2",
        category=3,
        status="served",
        evidence=(
            "Same WUR dataset and identical leave-one-experiment-out folds as v1. "
            "Gradient boosting R2 0.8699 / MAE 34.9 g versus the registered random "
            "forest's 0.8131 / 39.1 g, winning on MAE in 4 of 4 held-out experiments."
        ),
        user_facing=(
            "Served as the current Earth-only model; v1 remains callable and remains "
            "registered so the Phase 7 result stays reproducible."
        ),
        notes=[
            "Model class chosen by measurement on the platform's own benchmark, not by preference.",
            "Serialised ensemble reproduces sklearn exactly (max abs difference 0.0).",
            "Predictions are clamped at zero because fresh mass cannot be negative.",
            "Still external Earth data, not NASA data, and still not space-crop calibrated.",
        ],
    ),
    Feature(
        id="mizuna-microbial-load-v1",
        name="Mizuna absolute leaf microbial load (VEG-04A/B)",
        surface="POST /api/predict/mizuna-microbial-load-v1",
        category=6,
        status="retired-as-prediction",
        evidence=(
            "NASA OSD-780 measured plate counts, but leave-one-experiment-out R2 is "
            "-0.55 and -0.58: worse than predicting the training mean."
        ),
        user_facing=(
            "The predictive endpoint now returns HTTP 410 with the measured transfer "
            "failure. The artifact stays registered so the Phase 6 result remains "
            "reproducible."
        ),
        notes=[
            "Absolute load for an unseen campaign is not identifiable from the features.",
            "Phase 7 showed the campaign offset, not the flight/ground effect, is what fails to transfer.",
            "Superseded for prediction by mizuna-microbial-relative-load-v2.",
        ],
    ),
    # ---------------------- category 4/5: mechanistic ------------------------
    Feature(
        id="mizuna-microbial-relative-load-v2",
        name="Mizuna relative leaf microbial load",
        surface="POST /api/predict/mizuna-microbial-relative-load-v2",
        category=3,
        status="served-with-scope",
        evidence=(
            "NASA OSD-780; within-campaign standardised target; held-out R2 +0.444 / "
            "+0.373 with permutation p = 0.000 on both campaigns."
        ),
        user_facing=(
            "Returns standard deviations within a campaign. An absolute figure is "
            "emitted only when the caller supplies that campaign's own measured "
            "reference."
        ),
        notes=[
            "Conformal coverage 0.849 vs 0.90 nominal, so the interval is labelled uncalibrated.",
            "Evidence status remains 'experimental', never 'validated'.",
        ],
    ),
    Feature(
        id="mizuna-harvest-v1",
        name="Mizuna harvest fresh mass per pillow",
        surface="POST /api/predict/mizuna-harvest-v1",
        category=3,
        status="served-baseline-only",
        evidence=(
            "14 usable OSD-655 endpoints. The target definition differs between the "
            "two arms (DATA_HARMONIZATION.md H1)."
        ),
        user_facing="Labelled exploratory; the registry pins it at 'baseline-only' and never promotes it.",
        notes=["Cannot recommend irrigation and cannot infer causality."],
    ),
    Feature(
        id="tomato-flight-response-v1",
        name="Tomato flight-versus-ground molecular classification",
        surface="POST /api/predict/tomato-flight-response-v1",
        category=3,
        status="served-with-scope",
        evidence="36 samples over 21 groups from OSD-767 transcript abundance.",
        user_facing=(
            "Presented as a molecular-context discriminator only, with an explicit "
            "statement that it does not predict plant health, stress or yield."
        ),
        notes=[
            "Labels are recorded environment, not measured plant performance.",
            "Cannot be used as a gravity-response measurement.",
        ],
    ),
    Feature(
        id="simulation-engine",
        name="Habitat crop simulation (biomass, water, CO2, O2)",
        surface="POST /api/simulate, /api/compare, /api/advisor, /api/optimize",
        category=5,
        status="served-hypothetical",
        evidence=(
            "Transparent mathematical engine with documented constants. Phase 7 "
            "checked four parameters against measured data and changed none, because "
            "no recovered measurement is the same quantity on the same crop class."
        ),
        user_facing=(
            "Every response carries PHASE_1_DISCLAIMER and the assumptions list; the "
            "engine is described as hypothetical exploration, never a validated forecast."
        ),
        notes=[
            "gravity and radiation response coefficients remain unsupported assumptions.",
            "O2 is derived stoichiometrically from CO2 (6 CO2 + 6 H2O -> C6H12O6 + 6 O2), not measured.",
            "Water recovery 0.90 is conservative against a measured 0.924 lower bound from a leaking chamber.",
        ],
    ),
    Feature(
        id="optimizer-frontier",
        name="Bounded light/water/CO2 configuration search",
        surface="POST /api/optimize",
        category=5,
        status="served-hypothetical",
        evidence=(
            "Fixed 81-candidate search over the transparent engine; Pareto frontier on "
            "yield, make-up water and daily light integral."
        ),
        user_facing=(
            "Reports a frontier over assumed response curves, with a limitation stating "
            "that sensitivity is not uncertainty calibration."
        ),
        notes=[
            "Optimises assumed equations, not real spacecraft safety.",
            "Daily light integral is a proxy for light input, not electrical power.",
            "PPFD/photoperiod optimum is a property of the assumed curve, not a measured optimum.",
        ],
    ),
    Feature(
        id="oxygen-evolution",
        name="O2 production from crop growth",
        surface="simulate -> estimatedOxygenProduced",
        category=4,
        status="served-mechanistic",
        evidence=(
            "Photosynthesis stoichiometry applied to modelled carbon fixation. NASA "
            "never measured O2 evolution in the recovered corpus."
        ),
        user_facing=(
            "Named 'estimated' in the response and documented as a derived quantity, "
            "never presented as a measurement."
        ),
        notes=[
            "No measured O2 target exists, so this cannot be validated - only audited for stoichiometric consistency.",
            "Must not be described as 'measured' or 'validated' anywhere.",
        ],
    ),
    Feature(
        id="gravity-response",
        name="Microgravity growth penalty",
        surface="simulate -> gravity factor",
        category=5,
        status="served-assumed",
        evidence="Placeholder magnitude: 15 % growth lost at 0 g. No partial-gravity plant dataset was recovered.",
        user_facing="Listed among the model's assumptions with its constant value shown.",
        notes=["Blocked by unavailable scientific evidence; not calibratable from the current corpus."],
    ),
    Feature(
        id="radiation-response",
        name="Radiation growth penalty",
        surface="simulate -> radiation factor",
        category=5,
        status="served-assumed",
        evidence="Exponential decay placeholder. All 'radiation' hits in the corpus are lamp spectra, not absorbed dose.",
        user_facing="Listed among the model's assumptions with its constant value shown.",
        notes=["Blocked by unavailable scientific evidence."],
    ),
    Feature(
        id="ppfd-photoperiod-response",
        name="Light intensity and photoperiod response",
        surface="simulate -> light factor, optimize frontier",
        category=5,
        status="served-assumed",
        evidence=(
            "Saturating curve normalised to each crop's optimal photoperiod. Phase 7 "
            "rated the measured PPFD/photoperiod target 'insufficient' because its "
            "2-3 operating points are confounded with system phase and a copper deficiency."
        ),
        user_facing="Shown as an assumption; the optimizer result is framed as a property of the assumed curve.",
        notes=["No measured optimum exists to calibrate against."],
    ),
]


def by_category() -> dict[int, list[dict]]:
    groups: dict[int, list[dict]] = {c: [] for c in CATEGORY_NAMES}
    for feature in FEATURES:
        groups[feature.category].append(feature.to_dict())
    return groups


def summary() -> dict:
    counts = {c: 0 for c in CATEGORY_NAMES}
    for feature in FEATURES:
        counts[feature.category] += 1
    return {
        "features": len(FEATURES),
        "byCategory": counts,
        "servedAsPrediction": sorted(
            f.id for f in FEATURES if f.category != 6 and f.status.startswith("served")),
        "retiredAsPrediction": sorted(
            f.id for f in FEATURES if f.category == 6 or f.status.startswith("retired")),
        "unsupportedServicedCount": counts[6],
    }


def classifier_response() -> dict:
    return {
        "schemaVersion": 1,
        "purpose": (
            "Every prediction and optimisation surface in the API, classified against "
            "the Phase 8 scientific evidence policy. Category 6 is never served as a "
            "prediction."
        ),
        "categories": {str(k): v for k, v in CATEGORY_NAMES.items()},
        "serviceAllowed": {str(k): v for k, v in SERVICE_ALLOWED.items()},
        "features": [f.to_dict() for f in FEATURES],
        "byCategory": {str(k): v for k, v in by_category().items()},
        "summary": summary(),
    }
