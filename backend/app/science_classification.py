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
        id="radiation-quality-osd46-v1",
        name="Arabidopsis radiation-quality classifier (NASA OSD-46)",
        surface="POST /api/predict/radiation-quality-osd46-v1",
        category=3,
        status="served-with-scope",
        evidence=(
            "NASA OSD-46 Affymetrix ATH1 microarray, 44 arrays over 22 biological "
            "groups. Leave-one-biological-group-out: accuracy 0.932, balanced 0.898, "
            "macro F1 0.906 against 0.000 majority baseline; permutation p = 0.0099 "
            "(the floor at 100 permutations)."
        ),
        user_facing=(
            "Served with the full validation block, the batch confound statistic and "
            "the study's limitations attached to every response."
        ),
        notes=[
            "Gamma and HZE are balanced across array batches, so array batch cannot explain the discrimination.",
            "The control class is NOT batch-balanced; that limitation is stated in the response.",
            "Distinguishes 100 Gy gamma from 30 Gy Fe-56, which differ in both quality and dose.",
            "Never predicts yield, biomass, survival or crop productivity.",
        ],
    ),
    Feature(
        id="radiation-exposure-osd46-v1",
        name="Arabidopsis radiation-exposure classifier (NASA OSD-46)",
        surface="POST /api/predict/radiation-exposure-osd46-v1",
        category=3,
        status="served-with-scope",
        evidence=(
            "Same study and scheme: accuracy 0.932, balanced 0.910, permutation "
            "p = 0.0099. Batch-controlled evaluation on the single array batch "
            "containing all three conditions gives balanced accuracy 0.969."
        ),
        user_facing=(
            "Served with a batch-controlled supplementary evaluation, because controls "
            "never appear on one of the three array batches (Cramer's V 0.715)."
        ),
        notes=[
            "Irradiated-versus-control only; does not distinguish quality or dose.",
            "Full-set evaluation is batch-confounded; the batch-controlled number is the defensible one.",
            "Never predicts yield, biomass, survival or crop productivity.",
        ],
    ),
    Feature(
        id="lettuce-earth-growth-v3",
        name="Earth lettuce fresh yield per area (v3, daily light integral)",
        surface="POST /api/predict/lettuce-earth-growth-v3",
        category=3,
        status="served",
        evidence=(
            "Same WUR experiments as v1 and v2, but the target is fresh yield per square metre "
            "reconstructed from per-plant mass at the source's 25 plants/m2, and light enters as "
            "the daily light integral (PPFD x photoperiod) rather than instantaneous PPFD. "
            "Leave-one-experiment-out: MAE 835.5 g/m2, MAPE 41.7 %, R2 0.861, n=1648."
        ),
        user_facing=(
            "The current Earth lettuce yield model. It needs the photoperiod and the planting "
            "density the caller is asking about, and returns them with the prediction."
        ),
        notes=[
            "Development set (six PeerJ 17085 observations): MAPE 42.7 %, MBE +2.6 g. These "
            "observations informed the choice of the light feature, so they are not validation.",
            "Independent holdout (Touliatos et al. 2016, untouched during selection): MAPE 41.6 % "
            "against a 30 % criterion declared in advance. It fails, and the API says so.",
            "One source (1000 plants/m2 vertical farm) is refused rather than scored: the per-area "
            "identity that converts yield to per-plant mass breaks at that density.",
            "No cultivar input and no CO2 input. On the six development rows the model gives one "
            "curve per light level, while the measured response is non-monotonic and differs by "
            "cultivar by more than the light effect.",
            "Still Earth data, still trained-exploratory, still not a space-crop prediction.",
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
        id="radiation-dose-osd782-v1",
        name="Arabidopsis radiation dose classifier (NASA OSD-782)",
        surface="not served - excluded from the API",
        category=6,
        status="retired-as-prediction",
        evidence=(
            "36 libraries, 12 biological groups. Leave-one-group-out: best balanced "
            "accuracy 0.361 against a 0.333 chance rate; permutation p = 0.353."
        ),
        user_facing=(
            "No endpoint. Training script and evaluation remain in the repository as "
            "evidence."
        ),
        notes=[
            "Dose is completely confounded with sample processing order in this study.",
            "Excluded rather than tuned until it appeared to work.",
        ],
    ),
    Feature(
        id="gravity-reorientation-osd411-v1",
        name="Arabidopsis gravity reorientation classifier (NASA OSD-411)",
        surface="not served - excluded from the API",
        category=6,
        status="retired-as-prediction",
        evidence=(
            "63 libraries, 16 biological groups. Leave-one-group-out balanced accuracy "
            "0.500 at chance; permutation p = 0.517. Genotype transfer 0.531 / 0.419 "
            "and tissue transfer 0.375-0.562, all at chance."
        ),
        user_facing="No endpoint. Training script and evaluation remain as evidence.",
        notes=[
            "Failed in every transfer direction tested, not in one unlucky split.",
            "A 90-degree reorientation on the ground is not partial gravity.",
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
            "radiation response coefficients remain unsupported assumptions; the gravity "
            "coefficient was removed in Phase 30 rather than kept as a placeholder.",
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
    # ------------------------- category 4: mechanistic ----------------------
    Feature(
        id="et0-emulator-v1",
        name="Reference ET0 emulator (gradient-boosted surrogate of FAO-56)",
        surface="GET /api/reference-et0/estimate, POST /api/simulate (et0MmPerDay)",
        category=4,
        status="served-mechanistic",
        evidence=(
            "Category 4, not 1 or 3. The target it reproduces is FAO-56 Penman-Monteith "
            "reference ET0 computed from NASA POWER reanalysis weather - a standard, not a "
            "measurement - and its error is measured against that computed standard. It was "
            "never compared with a lysimeter, a sap-flow sensor or a flux tower. On a "
            "leave-one-site-out test it is about 14 % worse than Hargreaves-Samani, so the "
            "FAO-56 equation remains the primary number and the emulator is offered beside it."
        ),
        user_facing=(
            "Served with the physics alternatives, the acceptance gates it failed, a conformal "
            "interval, and an out-of-distribution flag when an input leaves its training range."
        ),
        notes=[
            "The label is computed from reanalysis, so a perfect score would prove it learned "
            "the equation, not that it predicts a crop's water use.",
            "Not validated for microgravity, low pressure or LED-lit interiors.",
            "Water demand from ET0 still needs a crop coefficient; Kc defaults to 1.0, which "
            "describes the reference surface rather than a crop.",
        ],
    ),
    Feature(
        id="gravity-response",
        name="Microgravity growth penalty (removed)",
        surface="none",
        category=5,
        status="removed",
        evidence=(
            "Removed in Phase 30. The penalty was a placeholder coefficient: no open dataset measures "
            "crop yield or biomass across fractional gravity, the ISS fractional-gravity work measures "
            "gene expression and morphology, and a ground reorientation is not partial gravity. A "
            "coefficient with no measurement behind it cannot stay in a served model."
        ),
        user_facing=(
            "There is no gravity input, no gravity control and no gravity factor. /api/simulate "
            "rejects a request that carries one and names this decision; the mission surface no "
            "longer offers gravity presets."
        ),
        notes=[
            "The dataset gap is recorded as 'fractional-gravity' in data/research/dataset_gap_matrix.json.",
            "Nothing in the simulator now changes with gravity, so an Earth/Moon/Mars comparison "
            "isolates radiation and resources only.",
        ],
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


def feature_by_id(feature_id: str) -> Feature | None:
    """Look up one classified surface.

    Added in Phase 12 so the model registry and the research assistant can attach
    the category of a surface instead of duplicating the taxonomy in a second
    place. There is exactly one source of truth for the classification.
    """
    for feature in FEATURES:
        if feature.id == feature_id:
            return feature
    return None


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
