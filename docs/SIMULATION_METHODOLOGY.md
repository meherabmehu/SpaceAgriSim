# Simulation methodology

SpaceAgriSim retains the original deterministic mathematical engine and adds environmental controls. It is an educational scenario model, not a validated crop or spacecraft controller. NASA dataset provenance does not imply that simulator coefficients were fitted to NASA measurements.

## Units and state

Fresh edible biomass is in grams, cultivated area in m², water in litres, gases in grams, gravity in Earth g, absorbed dose rate in mGy/day, CO2 in ppm, photoperiod in hours/day, PPFD in µmol/m²/s, temperature in °C and relative humidity in percent. The water recycling input is a percentage and is converted once to a fraction internally.

Lettuce, tomato and radish cycle lengths and reference harvest masses remain explicit assumptions in `backend/app/config/simulation_constants.py`. They are not universal cultivar parameters or observations. Crop cycle timing is fixed: stress scales biomass, not maturation dates. Consecutive identical cycles assume immediate replanting and unchanged conditions.

## Growth

An endpoint-normalized logistic curve describes each cycle. Potential edible fresh biomass = reference mass per m² × area × product of environmental response factors. Total production = harvested biomass + standing biomass. A harvest-day curve can show the pre-cut crop, while the summary standing biomass is zero after cutting; cumulative production is continuous.

Original factors are retained: linear reduced/hypergravity penalty, exponential radiation penalty above the assumed Earth background, saturating photoperiod with an excess-light penalty, water supply fraction, and saturating CO2 enrichment. Their coefficients are illustrative and uncalibrated. A matched Earth comparison retains resources; baseline comparison resets reference resources.

New factors are also assumptions:

- PPFD factor: `[I/(I+200)] / [300/(300+200)]`, normalized at 300 µmol/m²/s; zero PPFD produces zero modeled growth.
- Temperature factor: `exp(-((T-22)/12)^2)`.
- Humidity factor: `exp(-((RH-60)/50)^2)`.

These generic curves deliberately avoid claiming crop-specific physiological calibration. Spectrum is saved as an annotation only; changing it does not invent a yield response. Light integral is `PPFD × hours × 0.0036` mol/m²/day.

## Water

Daily demand follows canopy fraction, crop reference peak demand, area and the original photoperiod response. It is additionally scaled by air vapor pressure deficit relative to 22 °C/60 % RH. Saturation vapor pressure uses `0.6108 exp(17.27T/(T+237.3))` kPa and VPD = saturation × `(1-RH/100)`, following the [FAO reference equation](https://www.fao.org/fileadmin/user_upload/faowater/docs/ReferenceManualV32.pdf). The proportional mapping from VPD to crop water demand is an uncalibrated approximation, not the full Penman–Monteith evapotranspiration model. There is no airflow, stomatal conductance, leaf temperature, nutrient solution or substrate hydraulic model. At saturated RH the simplified transpiration estimate reaches zero; biomass-bound water and leakage are not modeled.

Supplied = demand × availability fraction; deficit = demand − supplied; recovered = supplied × configured recovery fraction; make-up = supplied − recovered. Capture efficiency has no growth effect and does not represent a measured ECLSS performance guarantee. Neither hydroponic reservoir sizing nor nutrient solution circulation is equivalent to water consumption.

## Gas exchange

Daily positive cumulative edible fresh biomass gain is divided by harvest index, multiplied by dry matter fraction and assumed carbon fraction. CO2 fixed = carbon mass × 44/12; O2 released = CO2 × 32/44. These are biomass carbon accounting estimates. They omit independent measurements of nighttime respiration, microbial respiration, gas transfer, pressure and equipment losses. Crew equivalent days are illustrative ratios, not life support certification.

## Comparison, advisor and optimization

Earth/Moon/Mars share user resources; only gravity and hypothetical absorbed dose rates differ. These presets do not encode shielding or measured crop exposure. The custom habitat preserves all user settings. A product-factor waterfall explains the mathematical ratio; contributions depend on presentation order and are not causal attribution.

The deterministic advisor reads the same simulation response and quotes exact water-balance outputs. It has no LLM or invented citations. Optimization evaluates 81 bounded combinations of photoperiod, PPFD, water supply and CO2. It holds hazards, crop, area, mission length, temperature, humidity and capture efficiency fixed. The Pareto objectives are maximum biomass, minimum make-up water and minimum daily light integral. Light integral is a photon-input proxy, not electrical power. Recommendation prioritizes highest modeled biomass, then lower water and light among ties. The grid frontier is not a global or operational optimum. Sensitivity evaluates explicit local input changes, not empirical uncertainty.

## Evidence and uncertainty

Each response exposes `provenance.mode`, `modelVersion`, `nasaValidated=false`, `confidenceInterval=null`, warnings, stress-factor deficits and environmental derived quantities. There is no statistical confidence score for the simulator. Molecular classification, if present in the separate research registry, does not validate crop biomass, water or gas outputs. Never interpret an interval from another task as crop forecast coverage.
