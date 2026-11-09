# Scientific limitations

Consolidated, in one place, so no surface has to invent its own wording. Everything here is a
statement about what the system cannot do. None of it is a disclaimer bolted onto a result; each item
is the reason a particular number must be read a particular way.

## Status

Not one model in this repository is externally validated. One was tested externally in this audit and
failed (lettuce v3, 41.6 % against a pre-declared 30 % criterion). The labels are
`experimental` and `trained-exploratory` throughout, and `scripts/verify_model_registry.py` fails the
build if an artifact claims a stronger status than its own recorded metrics support.

## Lettuce fresh yield (v3)

1. **Fails its independent criterion.** 41.6 % MAPE on Touliatos et al. 2016 against a 30 %
   criterion declared in advance. Not usable for harvest forecasting or farm sizing.
2. **No cultivar input.** Baby Cos and Green Oak differ by 63.5 g on average in the development data,
   more than the light effect within either cultivar. The model has one curve per light level.
3. **Light response is monotonic; the data are not.** The development set's highest yields occur at
   the middle and lowest light levels; a tree ensemble cannot represent that.
4. **No CO₂, no nutrient, no water input.** The training source held these near-constant; ambient-CO₂
   greenhouse yields are therefore biased high by the model's plant-factory training system.
5. **Density enters as an identity, not a response.** `massPerPlant = yieldPerM2 / density` assumes
   per-area yield is density-independent. Above ~200 plants/m² (Touliatos measured 1000) that is
   false, so those inputs are flagged, and the source itself is refused rather than scored.
6. **One harvest per plant.** Growth trajectories and intermediate harvests are not modelled.
7. **Development ≠ validation.** The six PeerJ observations informed the choice of light feature; they
   are reported as a development set with `countsAsValidation: false`.
8. **Domain.** DAT 2–29, air and root 20–32 °C, DLI 11.5–34.5 mol m⁻² d⁻¹, density 10–200 plants/m².
   Outside it, the response is flagged `outOfDistribution` with the violated bounds attached.

## Lettuce fresh mass (v1, v2)

9. Same input gap as v3 for light (instantaneous PPFD, no photoperiod) and no density input.
10. **v2 overpredicts an independent study by a median 3.21× (MAPE 232.2 %).** Kept, callable and
    visible, because its failure is the evidence that motivated v3.
11. Trained on four experiments from one research group in one system.

## Mizuna (NASA VEG-04A)

12. `mizuna-harvest-v1` is **worse than the mean predictor** on held-out folds (R² −0.333). Fourteen
    measured harvests from a single experiment; exploratory only.
13. `mizuna-microbial-load-v1` / `-relative-load-v2`: predict culturable aerobic plate counts from
    assay context, not food safety. v1's absolute estimand did not transfer between campaigns, which
    is why v2 predicts within-campaign relative load.
14. Harvest and irrigation inputs are retrospective; not an early-harvest forecast and not a causal
    irrigation recommendation.

## Molecular classifiers (OSDR)

15. They classify the experimental condition a sample came from. They do not predict, improve or
    quantify crop yield, and no surface derives a yield from them.
16. OSD-46's 100 Gy gamma and 30 Gy Fe-56 conditions differ in both radiation quality and absorbed
    dose, so a classifier separating them cannot attribute the difference to either.
17. n is small (44 samples, 22 groups; CI 0.771–1.000 for balanced accuracy). Wide intervals are
    reported as measured.

## Deterministic simulation

18. **Gravity coefficient is an assumption** (15 % growth loss at 0 g). No crop biomass dataset exists
    across fractional gravity; the ISS fractional-gravity work measures gene expression and
    morphology, and published conclusions are that Mars-level gravity may not limit plant development.
19. **Radiation coefficient is an assumption** (exponential decay, 0.25 per mGy/day). No crop-yield
    dataset at habitat-relevant chronic dose rates exists in the corpus.
20. **CO₂ response is monotonic in the model but not in the literature.** Soybean yield peaked at
    1000 ppm and fell at 2000–5000 ppm (NTRS 20040090155); runs above 1000 ppm carry a warning.
21. **Water recovery is capped at the measured 98 % ceiling.** No loop recovers more than that.
22. The logistic growth curve and harvest index are scenario parameters, not fitted results.
23. Optimisation and scenario comparison inherit all of the above. An optimum computed from a
    scenario coefficient is an optimum *of that coefficient*.
24. Validation of the simulation is internal consistency only (mass, water and carbon balance,
    monotonicity, bounds, finiteness). There is no independent space-crop yield dataset to validate
    against, and none is claimed.

## Data

25. **No NASA fractional-gravity crop biomass dataset, no regolith yield surface, and no
    habitat-dose-rate crop yield dataset exist in this corpus.** Features that would have needed them
    were removed rather than filled with synthetic values.
26. Every dataset is pinned by SHA-256 and retrieval date; `docs/DATASET_REGISTRY.md` is generated
    from the files themselves, so a re-fetch that changes a byte shows up as a MISMATCH.
27. The only non-NASA experimental source used for training and validation (WUR, PeerJ, Touliatos) is
    controlled-environment Earth horticulture. Spaceflight crop growth is different, and nothing here
    bridges that gap.

## Not claimed, anywhere

No Moon or Mars crop yield. No mission-certified anything. No food-safety conclusion. No
"AI-validated" model. No extrapolation outside a declared domain. No accuracy figure from a training
set presented as evidence.
