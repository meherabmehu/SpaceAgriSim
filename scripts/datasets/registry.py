"""Phase 26 discovery registry: every candidate dataset, with what was actually verified.

Two rules govern this file, and both are tested:

1. A candidate is only marked ``acquired`` after the bytes were downloaded, hashed and parsed.
2. A candidate that was *found* is not a candidate that is *usable*. ``discovery``, ``probe``,
   ``acquired``, ``inspected`` and ``preprocessed`` are separate fields, so a repository listing
   can never masquerade as data.

Evidence categories stay separate throughout:

    reanalysis                     model-derived from assimilated observations
    station observation            a point measurement instrument
    crop water-use measurement     water actually consumed by a crop, measured
    controlled-environment         a growth chamber / greenhouse / hydroponic experiment
    ground-based space analog      clinostat, RPM, or analog habitat
    actual spaceflight-microgravity
    reference-context              literature, statistics, climate normals

Never mix ``reanalysis`` with ``station observation``, never call a reference ET0 a crop water
use, and never present a terrestrial result as microgravity validation.
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------------------
# Classification vocabulary (mirrors ml/research/build_catalog.py; asserted by tests)
# ---------------------------------------------------------------------------------------
USABILITY_CLASSES = {
    "A": "acquired and usable training data",
    "B": "usable after preprocessing",
    "C": "independent validation only - wrong task, environment or sensor for training",
    "D": "reference or contextual data",
    "E": "access or licensing decision required",
    "F": "unusable or incompatible data",
}

EVIDENCE_CATEGORIES = (
    "reanalysis",
    "station observation",
    "crop water-use measurement",
    "controlled-environment experiment",
    "ground-based space analog",
    "actual spaceflight-microgravity",
    "reference-context",
)

ENVIRONMENTS = (
    "controlled-environment greenhouse",
    "controlled-environment growth chamber",
    "hydroponic",
    "open field",
    "spaceflight",
    "not applicable",
)

# ---------------------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------------------
CANDIDATES: list[dict[str, Any]] = [
    # ---------------------------------------------------------------- acquired + processed
    {
        "id": "zenodo-schroder-2021-lettuce-pot",
        "fileEndpoint": "5550230",
        "name": "Lettuce pot trial: vermicompost and thermophilic compost (greenhouse)",
        "publisher": "Leibniz Institute of Vegetable and Ornamental Crops (IGZ); TU Berlin",
        "doi": "10.5281/zenodo.5550230",
        "landingUrl": "https://zenodo.org/records/5550230",
        "publication": ("Schröder C, Häfner F, Larsen OC, Krause A (2021). Urban Organic Waste for "
                        "Urban Farming: Growing Lettuce Using Vermicompost and Thermophilic "
                        "Compost. Agronomy 11(6):1175. https://doi.org/10.3390/agronomy11061175"),
        "license": "CC BY 4.0",
        "licenseUrl": "https://creativecommons.org/licenses/by/4.0/",
        "licenseEvidence": "verified",
        "commercialUse": "permitted with attribution",
        "files": [
            {"key": "Data_lettuce_pot_experiment_Schröder et al. 2021.xlsx",
             "sheetCount": 9},
        ],
        "species": ["lettuce (Lactuca sativa)"],
        "cultivar": "not stated in the dataset (commercial butterhead type)",
        "environment": "controlled-environment greenhouse",
        "evidenceCategory": "crop water-use measurement",
        "measurementBasis": (
            "gravimetric evapotranspiration of individual pots, weighed several times per week; "
            "irrigation was set each day to the measured water loss. This is measured water "
            "consumption of a plant + substrate system, not sap flow and not transpiration alone."
        ),
        "independentExperiments": 1,
        "replicatesPerTreatment": 5,
        "treatments": 7,
        "observations": 35,
        "temporalCoverage": "2019-06-24 to 2019-07-22 (37-day growth period)",
        "spatialCoverage": "single greenhouse, Großbeeren/Berlin, Germany",
        "variables": [
            "per-pot evapotranspiration (mL per interval) on 13 measurement dates",
            "shoot and root fresh and dry mass per pot",
            "shoot and root nutrient concentrations",
            "substrate water-holding capacity per pot",
            "greenhouse air temperature and relative humidity (summary statistics only)",
        ],
        "targetLabels": ["daily crop water use (mL per plant per day)", "final shoot fresh mass (g)"],
        "measuredOrDerived": "measured",
        "usabilityClass": "B",
        "classReason": (
            "Measured per-plant water use with matched biomass is the label the water feature has "
            "never had. It is class B rather than A because the trial is a single greenhouse, a "
            "peat-free sand/compost substrate, five replicates, and evapotranspiration rather than "
            "transpiration, so it validates magnitude and shape but cannot be a universal training "
            "set for a space-crop water model."
        ),
        "intendedMapping": [
            "water: measured crop water use benchmark for the simulation water path",
            "water: measured shoot fresh mass for the same pots, so water per gram of biomass is "
            "computable without a cross-experiment assumption",
            "nutrient: shoot nutrient concentration by compost treatment (contextual)",
        ],
        "limitations": [
            "Evapotranspiration includes substrate evaporation; it is an upper bound on transpiration.",
            "Greenhouse, not a controlled-environment chamber and not spaceflight.",
            "Air temperature and humidity are published only as summary statistics, so a reference "
            "ET0 cannot be recomputed for the trial days and no crop coefficient may be derived.",
            "Pot surface area is not published, so a mm-depth conversion requires a stated assumption.",
        ],
        "inspection": {"status": "inspected", "method": "openpyxl, all 9 sheets, header rows read",
                       "sheetsRead": ["legend", "lettuce biomass", "lettuce nutrient contents",
                                      "nutrient uptakes per shoot", "fertilization",
                                      "heavy metal contents composts", "calculation pot filling",
                                      "water holding capacity", "evapotranspiration"]},
        "acquisition": {"status": "acquired", "manifestKey": "data/metadata/phase26_acquisition_manifest"},
        "preprocessing": {"status": "processed",
                          "outputs": ["schroder2021_lettuce_et.csv",
                                      "schroder2021_lettuce_biomass.csv"]},
    },
    {
        "id": "zenodo-greenlight-2024-lettuce",
        "fileEndpoint": "20394352",
        "name": "Green-light spectral composition in hydroponic lettuce",
        "publisher": "Zenodo record (see landing page for the author list)",
        "doi": "10.5281/zenodo.20394352",
        "landingUrl": "https://zenodo.org/records/20394352",
        "publication": ("Optimising Spectral Composition in Hydroponic Lettuce Cultivation: The "
                        "Role of Green Light (dataset record 20394352)"),
        "license": "CC BY 4.0",
        "licenseUrl": "https://creativecommons.org/licenses/by/4.0/",
        "licenseEvidence": "verified",
        "commercialUse": "permitted with attribution",
        "files": [{"key": "green_light_lettuce_open_data (1).xlsx",
                   "sheetCount": 4}],
        "species": ["lettuce (red Batavia)"],
        "cultivar": "red Batavia",
        "environment": "hydroponic",
        "evidenceCategory": "controlled-environment experiment",
        "measurementBasis": (
            "destructive harvest of 40 plants per treatment at 35 days after sowing, with leaf "
            "length, width, rosette width, leaf number, fresh mass, dry mass and leaf area; "
            "MultispeQ chlorophyll-fluorescence measurements per plant per sampling day."
        ),
        "independentExperiments": 1,
        "replicatesPerTreatment": 40,
        "treatments": 4,
        "observations": 160,
        "temporalCoverage": "35 days after sowing (single crop cycle)",
        "spatialCoverage": "single indoor hydroponic system",
        "variables": ["PPFD 200 umol m-2 s-1", "16 h photoperiod", "green spectral fraction "
                      "(5.08 % control, 24 % fixed, 16-32 % ramped)",
                      "per-plant destructive harvest measurements",
                      "FvP/FmP, LEF, NPQt, ECS (chlorophyll fluorescence, not gas exchange)"],
        "targetLabels": ["per-plant fresh mass (g)", "per-plant dry mass (g)", "leaf area (mm2)"],
        "measuredOrDerived": "measured",
        "usabilityClass": "B",
        "classReason": (
            "Replicated controlled-environment harvest data (40 plants per arm) that can test "
            "whether spectral composition changes yield. Class B because PPFD and photoperiod are "
            "held constant, so it constrains a spectrum dimension the platform does not model "
            "rather than the light-intensity response it does."
        ),
        "intendedMapping": [
            "light: measured spectrum effect size on fresh and dry mass",
            "light: per-plant harvest distribution at a fixed PPFD and photoperiod",
        ],
        "limitations": [
            "Only four spectral arms in one system; not a spectral response curve.",
            "Fluorescence indices are not photosynthetic rates and are not treated as such.",
            "One cultivar, one cycle, no independent replication of the whole experiment.",
        ],
        "inspection": {"status": "inspected", "method": "openpyxl, all 4 sheets",
                       "sheetsRead": ["Treatment_metadata", "MultispeQ", "Destructive_harvest",
                                      "Postharvest_assays"]},
        "acquisition": {"status": "acquired", "manifestKey": "data/metadata/phase26_acquisition_manifest"},
        "preprocessing": {"status": "processed",
                          "outputs": ["greenlight2024_lettuce_harvest.csv"]},
    },
    {
        "id": "zenodo-ledphotoperiod-2025-tomato",
        "fileEndpoint": "23759737",
        "name": "Supplemental LED photoperiod extension: tomato growth and harvest",
        "publisher": "Zenodo record (see landing page for the author list)",
        "doi": "10.5281/zenodo.23759737",
        "landingUrl": "https://zenodo.org/records/23759737",
        "publication": ("Supplemental LED Lighting for Photoperiod Extension in Open-Field "
                        "Cultivation Using a Portable Platform (dataset record 23759737)"),
        "license": "CC BY 4.0",
        "licenseUrl": "https://creativecommons.org/licenses/by/4.0/",
        "licenseEvidence": "verified",
        "commercialUse": "permitted with attribution",
        "files": [{"key": "Minimal_Dataset_Plants.xlsx", "sheetCount": 8}],
        "species": ["tomato (Solanum lycopersicum)", "marigold (Calendula)"],
        "cultivar": "multiple varieties recorded per plant",
        "environment": "open field",
        "evidenceCategory": "controlled-environment experiment",
        "measurementBasis": ("weekly non-destructive growth of 20 tagged plants (height, leaf "
                             "number, stem number, stem diameter, RGB leaf area) plus destructive "
                             "harvest of shoot and root fresh and dry mass"),
        "independentExperiments": 1,
        "replicatesPerTreatment": 20,
        "treatments": 2,
        "observations": 20,
        "temporalCoverage": "weekly from week 0 to harvest (single season)",
        "spatialCoverage": "single open-field site (portable LED platform)",
        "variables": ["weekly height, leaf number, stem number, stem diameter",
                      "RGB leaf area (pixels, converted by the authors)",
                      "shoot/root fresh and dry mass at harvest",
                      "supplemental LED treatment group"],
        "targetLabels": ["weekly plant height (cm)", "shoot fresh mass at harvest (g)"],
        "measuredOrDerived": "measured",
        "usabilityClass": "C",
        "classReason": (
            "Measured weekly growth and harvest for tomato, but in an open field with ambient "
            "weather: the environment is not the closed or controlled system the platform models, "
            "so it can validate the shape of a growth curve and nothing about controlled "
            "environments."
        ),
        "intendedMapping": ["growth: shape of a measured weekly growth curve for tomato"],
        "limitations": [
            "Open-field ambient conditions, not controlled environment.",
            "Twenty plants, two groups, one season.",
            "Leaf area is derived from RGB imagery, not a destructive leaf-area measurement.",
        ],
        "inspection": {"status": "inspected", "method": "openpyxl, all 8 sheets",
                       "sheetsRead": ["README", "Tomato_weekly", "Tomato_leaf_area_RGB",
                                      "Tomato_harvest_roots", "Calendula_production",
                                      "Light_flat_grid", "Light_mockup", "Tomato_environment"]},
        "acquisition": {"status": "acquired", "manifestKey": "data/metadata/phase26_acquisition_manifest"},
        "preprocessing": {"status": "processed",
                          "outputs": ["ledphotoperiod2025_tomato_growth.csv",
                                      "ledphotoperiod2025_tomato_harvest.csv"]},
    },
    # ------------------------------------------------------- acquired, inspected, not parsed
    {
        "id": "zenodo-halbert-2020-tomato-hydroponic",
        "fileEndpoint": "5084389",
        "name": "Recycling fertilizers for tomato in hydroponics: biomass, yield, nutrient uptake",
        "publisher": "Leibniz Institute of Vegetable and Ornamental Crops (IGZ)",
        "doi": "10.5281/zenodo.5084389",
        "landingUrl": "https://zenodo.org/records/5084389",
        "publication": ("Halbert-Howard A, Häfner F, Karlowsky S, Schwarz D, Krause A (2020). "
                        "Evaluating recycling fertilizers for tomato cultivation in hydroponics, "
                        "and their impact on greenhouse gas emissions. Environ Sci Pollut Res. "
                        "https://doi.org/10.1007/s11356-020-10461-4"),
        "license": "CC BY 4.0",
        "licenseUrl": "https://creativecommons.org/licenses/by/4.0/",
        "licenseEvidence": "verified",
        "commercialUse": "permitted with attribution",
        "files": [{"key": "Data_Tomato hydroponic experiment_Halbert-Howard et al 2020.xlsx",
                   "sheetCount": 11}],
        "species": ["tomato (Solanum lycopersicum)"],
        "cultivar": "not stated in the dataset",
        "environment": "hydroponic",
        "evidenceCategory": "controlled-environment experiment",
        "measurementBasis": ("per-row destructive biomass and yield, shoot and fruit nutrient "
                             "concentrations and nutrient uptake by treatment"),
        "independentExperiments": 1,
        "replicatesPerTreatment": 1,
        "treatments": 6,
        "observations": 123,
        "temporalCoverage": "one crop cycle",
        "spatialCoverage": "single greenhouse hydroponic system",
        "variables": ["shoot and fruit fresh/dry mass per row", "fruit count and ripe fruit mass",
                      "shoot and fruit nutrient concentrations", "recycled nutrient share"],
        "targetLabels": ["shoot dry mass per row (g)", "ripe fruit mass per row (g)"],
        "measuredOrDerived": "measured",
        "usabilityClass": "B",
        "classReason": (
            "Measured hydroponic biomass, yield and nutrient uptake, the first real label set for "
            "nutrient-balance. Class B because it is aggregated per row (replication is per row, "
            "not per plant) and the workbook uses two-row hierarchical headers, so preprocessing "
            "is required before it can be used."
        ),
        "intendedMapping": ["nutrient: measured nutrient uptake per unit biomass for tomato"],
        "limitations": [
            "Row-level aggregates, so within-treatment variance is not plant-level.",
            "Tomato only; no leafy-green nutrient uptake.",
            "Not preprocessed yet: the header structure is hierarchical and parsing it is a "
            "deliberate deferred step rather than a silent assumption.",
        ],
        "inspection": {"status": "inspected", "method": "openpyxl, legend and Biomass&Yield",
                       "sheetsRead": ["legend and infos", "Biomass&Yield", "shoot_uptake",
                                      "Fruit_uptake", "uptake_summary"]},
        "acquisition": {"status": "acquired", "manifestKey": "data/metadata/phase26_acquisition_manifest"},
        "preprocessing": {"status": "not-processed",
                          "reason": ("two-row hierarchical header; per-row aggregation limits its "
                                     "use to a nutrient-uptake prior, not to a fitted model")},
    },
    {
        "id": "zenodo-marri-2021-gasexchange",
        "fileEndpoint": "5130624",
        "name": "Leaf gas exchange (A-Ci and light response) across temperature",
        "publisher": "Zenodo record (see landing page for the author list)",
        "doi": "10.5281/zenodo.5130624",
        "landingUrl": "https://zenodo.org/records/5130624",
        "publication": "Marri A-Ci x temperature dataset (record 5130624)",
        "license": "CC BY 4.0",
        "licenseUrl": "https://creativecommons.org/licenses/by/4.0/",
        "licenseEvidence": "verified",
        "commercialUse": "permitted with attribution",
        "files": [{"key": "marri_gasex_data.csv"}],
        "species": ["Corymbia calophylla (marri), a tree"],
        "cultivar": "wild-type trees",
        "environment": "not applicable",
        "evidenceCategory": "controlled-environment experiment",
        "measurementBasis": ("LI-6400-style infrared gas analyser records: net photosynthesis "
                             "(Photo), stomatal conductance (Cond), intercellular CO2 (Ci), "
                             "transpiration (Trans), leaf temperature and PAR inside the chamber"),
        "independentExperiments": 1,
        "replicatesPerTreatment": None,
        "treatments": None,
        "observations": 2454,
        "temporalCoverage": "measurement campaign (single study)",
        "spatialCoverage": "single study",
        "variables": ["Photo (umol m-2 s-1)", "Cond (mol m-2 s-1)", "Ci", "Trans", "PARi",
                      "Tleaf", "CO2S", "VpdL"],
        "targetLabels": ["net photosynthesis (umol m-2 s-1)"],
        "measuredOrDerived": "measured",
        "usabilityClass": "D",
        "classReason": (
            "Reference and contextual only: 2 454 genuine leaf-level gas-exchange records, but "
            "from a sclerophyll tree, not a crop and not a controlled-environment vegetable. It "
            "can inform the shape of a light and CO2 response; it cannot validate a crop "
            "photosynthesis model, and it is never mixed into crop training data."
        ),
        "intendedMapping": ["gas exchange: reference for the form of an A-Ci / light response"],
        "limitations": [
            "Tree species; no crop, no controlled environment, no edible yield.",
            "Leaf-level cuvette measurements cannot be scaled to a canopy without a model.",
            "Not parsed: it is used to bound the shape of a response, not to fit a coefficient.",
        ],
        "inspection": {"status": "inspected", "method": "pandas, 2 454 rows, 62 columns",
                       "sheetsRead": ["csv: marri_gasex_data.csv"]},
        "acquisition": {"status": "acquired", "manifestKey": "data/metadata/phase26_acquisition_manifest"},
        "preprocessing": {"status": "not-processed",
                          "reason": "reference-only; deliberately not used for fitting"},
    },
    # --------------------------------------------------- verified as reachable, not acquired
    {
        "id": "fao-faostat-bulk",
        "name": "FAOSTAT crop production and yield statistics (bulk download)",
        "publisher": "Food and Agriculture Organization of the United Nations",
        "landingUrl": "https://bulks-faostat.fao.org/production/",
        "publication": "FAOSTAT, Food and Agriculture Organization of the United Nations",
        "license": "CC BY 4.0 (FAOSTAT terms of use)",
        "licenseUrl": "https://www.fao.org/contact-us/terms/en/",
        "licenseEvidence": "documented-secondary",
        "evidenceCategory": "reference-context",
        "environment": "not applicable",
        "species": ["national crop aggregates, not per-plant"],
        "variables": ["national harvested area, production, yield"],
        "measuredOrDerived": "reported national statistics",
        "usabilityClass": "D",
        "classReason": ("Country-level statistics: reference context for siting and scale, never a "
                        "per-plant label and never a training set."),
        "acquisition": {"status": "not-acquired",
                        "reason": ("reachable (HTTP 200 on the Production_Crops_Livestock bulk "
                                   "archive) but no per-plant or per-experiment label exists in "
                                   "it, so downloading a multi-hundred-megabyte archive would "
                                   "add bytes without adding evidence")},
        "inspection": {"status": "not-inspected",
                       "method": "none: no file was downloaded, so no column was read"},
        "preprocessing": {"status": "not-processed", "reason": "not acquired"},
        "limitations": ["Aggregate statistics cannot support a controlled-environment claim."],
    },
    {
        "id": "copernicus-cds-era5-land",
        "name": "ERA5-Land hourly reanalysis via the Copernicus Climate Data Store",
        "publisher": "Copernicus Climate Change Service (C3S)",
        "landingUrl": "https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land",
        "license": "Copernicus licence (attribution, no endorsement)",
        "licenseEvidence": "documented-secondary",
        "evidenceCategory": "reanalysis",
        "environment": "not applicable",
        "usabilityClass": "E",
        "classReason": ("Already catalogued as class C for its temperature field through the "
                        "credential-free route. The hourly radiation and wind fields still need a "
                        "personal CDS token, which remains the licence/access decision."),
        "acquisition": {"status": "not-acquired",
                        "reason": ("ERS/API reachable (HTTP 202 at the API root) but every request "
                                   "needs CDSAPI_URL and CDSAPI_KEY, which are not present in this "
                                   "environment. No data were fabricated.")},
        "inspection": {"status": "not-inspected",
                       "method": "none: no file was downloaded"},
        "preprocessing": {"status": "not-processed", "reason": "credential-blocked"},
    },
    {
        "id": "fao-wapor",
        "name": "FAO WaPOR water productivity through open access of remotely sensed data",
        "publisher": "Food and Agriculture Organization of the United Nations",
        "landingUrl": "https://wapor.apps.fao.org/",
        "license": "CC BY 4.0 with attribution (WaPOR terms)",
        "licenseEvidence": "documented-secondary",
        "evidenceCategory": "reanalysis",
        "environment": "open field",
        "usabilityClass": "E",
        "classReason": ("Gridded water productivity and evapotranspiration at field scale. It is a "
                        "remote-sensing product for open-field agriculture, so it can never "
                        "validate a controlled-environment claim, and its portal requires account "
                        "access for bulk retrieval."),
        "acquisition": {"status": "not-acquired",
                        "reason": "portal reachable (HTTP 200); bulk API needs an FAO account"},
        "inspection": {"status": "not-inspected",
                       "method": "none: no file was downloaded"},
        "preprocessing": {"status": "not-processed", "reason": "credential-blocked"},
    },
    {
        "id": "neon-terrestrial-observations",
        "name": "NEON terrestrial ecosystem observations and eddy-covariance fluxes",
        "publisher": "National Ecological Observatory Network (Battelle / NSF)",
        "landingUrl": "https://data.neonscience.org/",
        "license": "CC BY 4.0 (NEON data policy)",
        "licenseEvidence": "verified",
        "evidenceCategory": "station observation",
        "environment": "open field",
        "usabilityClass": "C",
        "classReason": ("Genuine station measurements including latent-heat flux, but for wildland "
                        "and agricultural field sites: no controlled-environment crop, no per-plant "
                        "water use. Useful only as an independent open-field flux reference."),
        "acquisition": {"status": "not-acquired",
                        "reason": ("API reachable (HTTP 200, site list returned) but no NEON data "
                                   "product measures per-plant water use in a controlled "
                                   "environment, so it cannot close a SpaceAgriSim gap")},
        "inspection": {"status": "not-inspected",
                       "method": "none: no file was downloaded"},
        "preprocessing": {"status": "not-processed", "reason": "no compatible product"},
    },
    {
        "id": "icos-carbon-portal",
        "name": "ICOS Carbon Portal ecosystem fluxes and meteorological observations",
        "publisher": "Integrated Carbon Observation System (ICOS ERIC)",
        "landingUrl": "https://data.icos-cp.eu/",
        "license": "ICOS data licence: CC BY 4.0 for most collections, per-collection restrictions",
        "licenseEvidence": "documented-secondary",
        "evidenceCategory": "station observation",
        "environment": "open field",
        "usabilityClass": "E",
        "classReason": ("An access/licensing decision is required: ICOS licences are per collection "
                        "and the flux products are open-field ecosystem scale, so they could only "
                        "ever be a validation reference."),
        "acquisition": {"status": "not-acquired",
                        "reason": "portal reachable (HTTP 200); per-collection licence review "
                                  "needed before any download"},
        "inspection": {"status": "not-inspected",
                       "method": "none: no file was downloaded"},
        "preprocessing": {"status": "not-processed", "reason": "licence decision pending"},
    },
    {
        "id": "usda-nal-catalog",
        "name": "USDA National Agricultural Library data catalogue",
        "publisher": "United States Department of Agriculture",
        "landingUrl": "https://data.nal.usda.gov/",
        "license": "U.S. Government work, generally public domain (per dataset)",
        "licenseEvidence": "verified",
        "evidenceCategory": "reference-context",
        "environment": "not applicable",
        "usabilityClass": "E",
        "classReason": ("Catalogue reachable and searchable, but the searches performed found no "
                        "per-plant controlled-environment water-use dataset; what exists is field "
                        "agronomy and survey data."),
        "acquisition": {"status": "not-acquired",
                        "reason": "searched (HTTP 200 CKAN API); no compatible per-plant dataset"},
        "inspection": {"status": "not-inspected",
                       "method": "none: no file was downloaded"},
        "preprocessing": {"status": "not-processed", "reason": "no compatible product"},
    },
    {
        "id": "worldclim-2-1",
        "name": "WorldClim 2.1 climate normals",
        "publisher": "University of California, Davis (Fick & Hijmans)",
        "landingUrl": "https://www.worldclim.org/data/worldclim21.html",
        "license": "CC BY 4.0",
        "licenseEvidence": "verified",
        "evidenceCategory": "reference-context",
        "environment": "open field",
        "usabilityClass": "D",
        "classReason": ("Climate normals for siting context only; already covered functionally by "
                        "the Koppen-Geiger catalogue entry. No new label."),
        "acquisition": {"status": "not-acquired",
                        "reason": ("GeoTIFF archive reachable (HTTP 200/206) but it adds no label "
                                   "the platform can consume, and the Koppen-Geiger entry already "
                                   "covers climate-class siting")},
        "inspection": {"status": "not-inspected",
                       "method": "none: no file was downloaded"},
        "preprocessing": {"status": "not-processed", "reason": "duplicate role"},
    },
    {
        "id": "esa-copernicus-data-space",
        "name": "Copernicus Data Space Ecosystem (Sentinel) catalogue",
        "publisher": "European Space Agency / European Union Copernicus",
        "landingUrl": "https://dataspace.copernicus.eu/",
        "license": "Copernicus Sentinel data: free, open, attribution",
        "licenseEvidence": "verified",
        "evidenceCategory": "reanalysis",
        "environment": "open field",
        "usabilityClass": "E",
        "classReason": ("Sentinel imagery and derived products are open-field remote sensing at "
                        "10-60 m; there is no controlled-environment or per-plant label in them."),
        "acquisition": {"status": "not-acquired",
                        "reason": "catalogue reachable (HTTP 200 OData); download needs an account, "
                                  "and no product matches a SpaceAgriSim label"},
        "inspection": {"status": "not-inspected",
                       "method": "none: no file was downloaded"},
        "preprocessing": {"status": "not-processed", "reason": "no compatible product"},
    },
    {
        "id": "openet-ensemble",
        "name": "OpenET satellite-based evapotranspiration ensemble",
        "publisher": "OpenET partnership (NASA, USGS, EDF and others)",
        "landingUrl": "https://etdata.org/",
        "license": "OpenET data licence: open, attribution requested",
        "licenseEvidence": "documented-secondary",
        "evidenceCategory": "reanalysis",
        "environment": "open field",
        "usabilityClass": "E",
        "classReason": ("Field-scale satellite ET models for open-field agriculture. It is model "
                        "output, not a measurement of a crop's water use, and it needs an API key."),
        "acquisition": {"status": "not-acquired",
                        "reason": "portal reachable (HTTP 200); API key required"},
        "inspection": {"status": "not-inspected",
                       "method": "none: no file was downloaded"},
        "preprocessing": {"status": "not-processed", "reason": "credential-blocked"},
    },
    {
        "id": "dryad-repository",
        "name": "Dryad digital repository (searched for controlled-environment water use)",
        "publisher": "Dryad",
        "landingUrl": "https://datadryad.org/",
        "license": "CC0 for most records (per record)",
        "licenseEvidence": "verified",
        "evidenceCategory": "reference-context",
        "environment": "not applicable",
        "usabilityClass": "F",
        "classReason": ("Searched, not usable as found: the evapotranspiration and lysimeter queries "
                        "return single-study datasets for trees, soil columns and open-field crops. "
                        "Two records were opened and neither contains per-plant water use for a "
                        "controlled-environment vegetable."),
        "acquisition": {"status": "not-acquired",
                        "reason": ("API reachable (HTTP 200); queries 'lysimeter evapotranspiration' "
                                   "and 'hydroponic nutrient solution' returned no "
                                   "controlled-environment per-plant water-use dataset")},
        "inspection": {"status": "not-inspected",
                       "method": "none: no file was downloaded"},
        "preprocessing": {"status": "not-processed", "reason": "no compatible product"},
    },
    {
        "id": "cgiar-repositories",
        "name": "CGIAR research data repositories",
        "publisher": "CGIAR",
        "landingUrl": "https://data.cgiar.org/",
        "license": "CC BY 4.0 (per dataset)",
        "licenseEvidence": "unverified",
        "evidenceCategory": "reference-context",
        "environment": "open field",
        "usabilityClass": "F",
        "classReason": ("Unreachable from this environment: the hostname did not resolve, so no "
                        "claim about its contents is made in either direction."),
        "acquisition": {"status": "not-acquired",
                        "reason": "DNS resolution failed for data.cgiar.org during the audit"},
        "inspection": {"status": "not-inspected",
                       "method": "none: no file was downloaded"},
        "preprocessing": {"status": "not-processed", "reason": "unreachable"},
    },
    {
        "id": "figshare-repository",
        "name": "Figshare (searched for controlled-environment crop water use)",
        "publisher": "Figshare",
        "landingUrl": "https://figshare.com/",
        "license": "CC BY 4.0 for most records (per record)",
        "licenseEvidence": "verified",
        "evidenceCategory": "reference-context",
        "environment": "not applicable",
        "usabilityClass": "F",
        "classReason": ("Searched, not usable as found: results are figures and preprints rather "
                        "than row-level measurements; nothing with per-plant water use."),
        "acquisition": {"status": "not-acquired",
                        "reason": "API reachable (HTTP 200); no row-level controlled-environment "
                                  "water-use dataset in the results returned"},
        "inspection": {"status": "not-inspected",
                       "method": "none: no file was downloaded"},
        "preprocessing": {"status": "not-processed", "reason": "no compatible product"},
    },
]


# ---------------------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------------------
def by_id(dataset_id: str) -> dict[str, Any]:
    for candidate in CANDIDATES:
        if candidate["id"] == dataset_id:
            return candidate
    raise KeyError(dataset_id)


def acquired() -> list[dict[str, Any]]:
    return [c for c in CANDIDATES if c["acquisition"]["status"] == "acquired"]


def processed() -> list[dict[str, Any]]:
    return [c for c in CANDIDATES if c["preprocessing"]["status"] == "processed"]


def summary() -> dict[str, Any]:
    classes: dict[str, int] = {}
    for candidate in CANDIDATES:
        key = candidate["usabilityClass"]
        classes[key] = classes.get(key, 0) + 1
    return {
        "candidates": len(CANDIDATES),
        "acquired": len(acquired()),
        "inspected": sum(1 for c in CANDIDATES if c["inspection"]["status"] == "inspected"),
        "processed": len(processed()),
        "byClass": dict(sorted(classes.items())),
        "byEvidenceCategory": _count(c["evidenceCategory"] for c in CANDIDATES),
        "byEnvironment": _count(c["environment"] for c in CANDIDATES),
    }


def _count(values) -> dict[str, int]:
    out: dict[str, int] = {}
    for value in values:
        out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items()))
