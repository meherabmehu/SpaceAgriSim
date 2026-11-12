"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'phase': 26,
 'generatedBy': 'ml/research/build_feature_readiness.py',
 'generatedOn': '2026-11-10',
 'phase32Note': 'Phase 32 closed this list. Every feature is either complete at the level it claims or '
                "removed from the product; 'data-blocked' is no longer a resting state.",
 'tierDefinitions': {'production-ready': 'independent evaluation exists and the stated limits match what it '
                                         'found',
                     'research-ready': 'measured data and a committed evaluation exist; the claimed level is '
                                       'not identifiable from them',
                     'experimental': 'implemented and internally evaluated; no independent validation exists',
                     'data-blocked': "no obtainable dataset can move this feature; the block is the data's "
                                     'absence',
                     'unsupported': 'the product must not make the claim at all',
                     'removed': 'the capability is not in the product: no control, page, endpoint, catalogue '
                                'entry or documentation claim survives, and a test proves it is absent'},
 'tierOrder': ['production-ready', 'research-ready', 'experimental', 'data-blocked', 'unsupported',
               'removed'],
 'counts': {'features': 12, 'byTier': {'research-ready': 4, 'removed': 8}, 'moved': 8},
 'movedCount': 8,
 'features': [{'id': 'measured-eta',
               'order': 1,
               'claim': 'Predicted crop water use in litres per plant per day',
               'previousTier': 'data-blocked',
               'tier': 'research-ready',
               'tierChanged': True,
               'evidence': ['ml/evaluation/phase26_measured_et_validation',
                            'data/processed/phase26/schroder2021_lettuce_et.csv',
                            'backend/app/simulation/water.py'],
               'datasets': ['zenodo-schroder-2021-lettuce-pot'],
               'measuredOn': '380 pot-days from 35 published pots, 7 treatments, 11 weighings',
               'whatItSupports': ['the seasonal shape of lettuce water demand (Spearman 0.7909 across 11 '
                                  'days)',
                                  'a per-plant, per-day water-use benchmark that any future change must be '
                                  'compared with'],
               'whatItDoesNotSupport': ['a level correction: pot-surface and canopy-area denominators '
                                        'reverse the sign of the discrepancy, and neither is published',
                                        'a crop coefficient: no per-day trial weather exists',
                                        'transpiration alone: the measurement includes substrate '
                                        'evaporation'],
               'whatWouldMoveIt': 'per-day weather and pot geometry for a gravimetric or lysimeter trial, so '
                                  'that measured ET can be divided by a reference ET0 for the same days',
               'blockingEvidence': 'none obtainable under an open licence in this phase'},
              {'id': 'independent-et0',
               'order': 2,
               'claim': 'The claim that the ET0 target is itself correct',
               'previousTier': 'research-ready',
               'tier': 'research-ready',
               'tierChanged': False,
               'evidence': ['ml/evaluation/et0_dataset_quality', 'docs/ERA5_LAND_INDEPENDENT_VALIDATION.md'],
               'datasets': ['nasa-power-daily', 'era5-land', 'era5-hourly-0p25', 'noaa-isd-lite'],
               'measuredOn': 'four independent reanalysis and station sources over matched days',
               'whatItSupports': ['that the FAO-56 computation is implemented correctly and is stable across '
                                  'inputs',
                                  'that the emulator reproduces the computation, not that the computation is '
                                  'truth'],
               'whatItDoesNotSupport': ['a claim that reanalysis ET0 equals on-site measurement',
                                        'spatial validity below the reanalysis grid cell'],
               'whatWouldMoveIt': 'a flux-tower or lysimeter site inside a controlled environment, which is '
                                  'the same object measured-eta needs',
               'blockingEvidence': 'no controlled-environment ET0 measurement exists openly'},
              {'id': 'yield-labels',
               'order': 3,
               'claim': 'Predicted harvest mass per plant',
               'previousTier': 'removed',
               'tier': 'removed',
               'tierChanged': False,
               'phase30': 'The served forecast was withdrawn. A leave-one-study-out evaluation over 40 '
                          'published lettuce studies (53 treatment means) returned 310.17 % MAPE against the '
                          'unchanged 30 % criterion with the mean baseline selected out of fold; the Phase '
                          '28 holdout had already returned 41.59 %. POST '
                          '/api/workflows/harvest-prediction/run now answers 410 and the catalogue entry is '
                          "'unavailable'.",
               'evidence': ['ml/evaluation/phase30_harvest_crossstudy',
                            'data/processed/phase30/lettuce_multistudy.csv',
                            'backend/tests/test_phase30_removed_capabilities.py'],
               'datasets': ['zenodo-kilowatts-lettuce-lue'],
               'measuredOn': '53 published treatment means from 40 studies, used as an evaluation set',
               'whatItSupports': ['a measured-versus-model parity record that shows the model '
                                  'overpredicting'],
               'whatItDoesNotSupport': ['any harvest forecast, for any crop'],
               'whatWouldMoveIt': 'nothing: the capability is removed rather than blocked',
               'blockingEvidence': 'the independent error is more than ten times the criterion',
               'phase32': {'tier': 'removed',
                           'reason': 'The served harvest forecast was withdrawn in Phase 31 after the '
                                     'lettuce v3 model missed its pre-registered 30 % MAPE criterion at 41.6 '
                                     '% and the mizuna model held a negative held-out R2 (-0.333). '
                                     'backend/tests/test_phase32_no_forecast.py proves no route, workflow or '
                                     'assistant passage offers a harvest forecast; only the archival parity '
                                     'record remains.',
                           'searched': 'NASA OSDR/ALSDA/GeneLab, Zenodo, Dryad, Figshare, PANGAEA, Mendeley '
                                       'Data, Dataverse, USDA Ag Data Commons, OpenAIRE and journal '
                                       'supplements'}},
              {'id': 'led-spectrum-response',
               'order': 4,
               'claim': 'Response to specific LED spectra and photoperiods',
               'previousTier': 'experimental',
               'tier': 'research-ready',
               'tierChanged': True,
               'evidence': ['data/processed/phase26/greenlight2024_lettuce_harvest.csv',
                            'data/processed/phase26/greenlight2024_lettuce_fluorescence.csv',
                            'backend/app/science_classification.py'],
               'datasets': ['zenodo-greenlight-2024-lettuce'],
               'measuredOn': '252 plants across four fixed spectra at constant 200 umol/m2/s and 16 h',
               'whatItSupports': ['that spectral composition can be held as a categorical factor with 48-80 '
                                  'plants per arm'],
               'whatItDoesNotSupport': ['an intensity response: PPFD was constant by design',
                                        'a photoperiod response: photoperiod was constant by design',
                                        'any quantitative yield model: no model consumes this table yet'],
               'whatWouldMoveIt': 'a trial varying PPFD and photoperiod independently, or a model that '
                                  'consumes the existing table with leave-one-spectrum-out evaluation',
               'blockingEvidence': 'the photoperiod half of the claim has no dataset at all',
               'phase32': {'tier': 'research-ready',
                           'reason': 'Completed as a measured group comparison only: four spectral regimes '
                                     'in lettuce and the controlled-environment wheat runs, served through '
                                     'the light-stress and controlled-environment workflows with '
                                     'between-plant spread and a confounded-regime flag. No fitted response '
                                     'surface is served; the one that was fitted failed its sealed holdout '
                                     '(297.46 % MAPE) and was deleted.',
                           'searched': 'NASA OSDR/ALSDA/GeneLab, Zenodo, Dryad, Figshare, PANGAEA, Mendeley '
                                       'Data, Dataverse, USDA Ag Data Commons, OpenAIRE and journal '
                                       'supplements'}},
              {'id': 'fractional-gravity',
               'order': 5,
               'claim': 'Effect of Mars or lunar gravity on crop growth',
               'previousTier': 'removed',
               'tier': 'removed',
               'tierChanged': False,
               'phase30': 'The growth penalty, input field, presets, impact step and UI control were '
                          'removed. No open dataset measures crop yield or biomass across fractional '
                          'gravity; the ISS graded-gravity experiments measure gene expression and '
                          'morphology, and a clinostat is not partial gravity. Keeping the coefficient would '
                          'have kept an invented number.',
               'evidence': ['backend/tests/test_phase30_removed_capabilities.py',
                            'docs/PHASE30_REMOVED_CAPABILITIES.md'],
               'datasets': [],
               'measuredOn': 'nothing: no fractional-gravity plant yield dataset exists',
               'whatItSupports': ['nothing - the simulator has no gravity term'],
               'whatItDoesNotSupport': ['any gravity-related yield statement'],
               'whatWouldMoveIt': 'nothing: the capability is removed rather than blocked',
               'blockingEvidence': 'no open dataset, and none was recoverable in the Phase 30 search',
               'phase32': {'tier': 'removed',
                           'reason': 'No recovered study measures production as a function of gravity: '
                                     'ground chambers and orbital runs compare a microgravity arm with a 1 g '
                                     'control, not a graded response. The search record stays in '
                                     'docs/PHASE30_REMOVED_CAPABILITIES.md and no input, card or route '
                                     'accepts a gravity value.',
                           'searched': 'NASA OSDR/ALSDA/GeneLab, Zenodo, Dryad, Figshare, PANGAEA, Mendeley '
                                       'Data, Dataverse, USDA Ag Data Commons, OpenAIRE and journal '
                                       'supplements'}},
              {'id': 'substrate-water',
               'order': 6,
               'claim': 'Root-zone water status in a hydroponic or substrate system',
               'previousTier': 'data-blocked',
               'tier': 'removed',
               'tierChanged': True,
               'evidence': ['backend/app/simulation/water.py'],
               'datasets': [],
               'measuredOn': 'nothing: no root-zone water-potential series exists in-repo. The Schroeder '
                             "trial's water-holding-capacity sheet is a static substrate property, not a "
                             'root-zone time series.',
               'whatItSupports': [],
               'whatItDoesNotSupport': ['substrate matric potential, oxygen status, or root-zone gradients'],
               'whatWouldMoveIt': 'nothing: the capability is removed rather than blocked',
               'blockingEvidence': 'the acquisition that came closest (water holding capacity) measures '
                                   'capacity, not status',
               'phase32': {'tier': 'removed',
                           'reason': 'No root-zone water-potential series exists in the repository or in the '
                                     'searched sources (OSDR, Zenodo, Dryad, PANGAEA, Mendeley). The '
                                     "simulator's single well-mixed store is a documented assumption inside "
                                     'the water-demand calculation, not a root-zone status feature, and no '
                                     'control claims one.',
                           'searched': 'NASA OSDR/ALSDA/GeneLab, Zenodo, Dryad, Figshare, PANGAEA, Mendeley '
                                       'Data, Dataverse, USDA Ag Data Commons, OpenAIRE and journal '
                                       'supplements'}},
              {'id': 'sub-daily-weather',
               'order': 7,
               'claim': 'Heat-stress and VPD excursion claims',
               'previousTier': 'research-ready',
               'tier': 'research-ready',
               'tierChanged': False,
               'evidence': ['ml/evaluation/phase11_dataset_discovery', 'docs/DATASET_GAP_MATRIX.md'],
               'datasets': ['era5-hourly-0p25', 'noaa-isd-lite'],
               'measuredOn': 'hourly reanalysis and station records at grid and station resolution',
               'whatItSupports': ['hourly VPD and temperature trajectories for siting and for ET0 input'],
               'whatItDoesNotSupport': ['canopy-level excursions inside a controlled environment',
                                        "any statement about a facility's internal climate"],
               'whatWouldMoveIt': 'in-facility climate logging at sub-hourly resolution',
               'blockingEvidence': 'no open controlled-environment climate series with the required '
                                   'resolution was found'},
              {'id': 'cultivar-metadata',
               'order': 8,
               'claim': 'Cultivar-specific growth parameters',
               'previousTier': 'experimental',
               'tier': 'removed',
               'tierChanged': True,
               'evidence': ['backend/app/simulation/crops.py', 'docs/MODEL_LIMITATIONS.md'],
               'datasets': [],
               'measuredOn': 'three crop profiles (lettuce, tomato, radish) with no cultivar field',
               'whatItSupports': [],
               'whatItDoesNotSupport': ['any cultivar-specific prediction, and no dataset in-repo carries a '
                                        'cultivar label usable as a model input'],
               'whatWouldMoveIt': 'nothing: the capability is removed rather than blocked',
               'blockingEvidence': 'the lettuce experiments in-repo each use a single unnamed cultivar',
               'phase32': {'tier': 'removed',
                           'reason': 'No experiment in the repository carries a cultivar label usable as a '
                                     'model input and no cultivar selector or parameter exists. A cultivar '
                                     'effect cannot be learned from one cultivar per study, so the feature '
                                     'is withdrawn instead of being left as a promise.',
                           'searched': 'NASA OSDR/ALSDA/GeneLab, Zenodo, Dryad, Figshare, PANGAEA, Mendeley '
                                       'Data, Dataverse, USDA Ag Data Commons, OpenAIRE and journal '
                                       'supplements'}},
              {'id': 'imagery',
               'order': 9,
               'claim': 'Plant health or growth stage from imagery',
               'previousTier': 'data-blocked',
               'tier': 'removed',
               'tierChanged': True,
               'evidence': ['docs/DATASET_GAP_MATRIX.md'],
               'datasets': [],
               'measuredOn': 'nothing: the tomato trial ships an RGB leaf-area series, which is a '
                             'measurement derived from imagery rather than the imagery itself',
               'whatItSupports': ['nothing: the product does not claim an imagery model'],
               'whatItDoesNotSupport': ['any computer-vision claim, health classification, or growth-stage '
                                        'detection'],
               'whatWouldMoveIt': 'nothing: the capability is removed rather than blocked',
               'blockingEvidence': 'the class E/F imagery datasets in the catalogue cannot be used under '
                                   'their licences or do not match the task',
               'phase32': {'tier': 'removed',
                           'reason': 'No paired imagery and harvest labels exist for a plant-health model, '
                                     "and the catalogue's imagery datasets are licence classes E/F, which "
                                     'cannot back a served model. No upload, camera view or plant-health '
                                     'card exists.',
                           'searched': 'NASA OSDR/ALSDA/GeneLab, Zenodo, Dryad, Figshare, PANGAEA, Mendeley '
                                       'Data, Dataverse, USDA Ag Data Commons, OpenAIRE and journal '
                                       'supplements'}},
              {'id': 'mission-energy',
               'order': 10,
               'claim': 'Energy and mass cost of a described mission',
               'previousTier': 'experimental',
               'tier': 'removed',
               'tierChanged': True,
               'evidence': ['backend/app/simulation/engine.py', 'backend/app/science_classification.py'],
               'datasets': [],
               'measuredOn': 'nothing: energy per LED-hour and per litre is a deterministic calculation over '
                             'stated assumptions, not a measurement',
               'whatItSupports': [],
               'whatItDoesNotSupport': ['a validated mission energy budget, and any comparison against a '
                                        'real facility'],
               'whatWouldMoveIt': 'nothing: the capability is removed rather than blocked',
               'blockingEvidence': 'no metered facility energy dataset is openly available',
               'phase32': {'tier': 'removed',
                           'reason': 'No mission energy or mass budget dataset exists in the repository and '
                                     'the platform publishes no such figure. Phase 32 proves by test that no '
                                     'response carries one.',
                           'searched': 'NASA OSDR/ALSDA/GeneLab, Zenodo, Dryad, Figshare, PANGAEA, Mendeley '
                                       'Data, Dataverse, USDA Ag Data Commons, OpenAIRE and journal '
                                       'supplements'}},
              {'id': 'nutrient-balance',
               'order': 11,
               'claim': 'Nutrient solution management',
               'previousTier': 'experimental',
               'tier': 'removed',
               'tierChanged': True,
               'evidence': ['data/raw/phase26/zenodo-halbert-2020-tomato-hydroponic/Data_Tomato_hydroponic_experiment_Halbert-Howard_et_al_2020.xlsx',
                            'scripts/datasets/registry.py'],
               'datasets': ['zenodo-halbert-2020-tomato-hydroponic'],
               'measuredOn': 'row-level shoot and fruit nutrient uptake with solution concentrations and a '
                             'recycled-solution fraction; not yet preprocessed',
               'whatItSupports': [],
               'whatItDoesNotSupport': ['any per-plant nutrient claim: replication is at row level',
                                        'a closed nutrient balance: the sheet reports uptake, not depletion '
                                        'and replenishment'],
               'whatWouldMoveIt': 'nothing: the capability is removed rather than blocked',
               'blockingEvidence': 'row-level replication caps the inference, and the product makes no '
                                   'nutrient claim today',
               'phase32': {'tier': 'removed',
                           'reason': 'Searched for a hydroponic nutrient series with a per-plant response: '
                                     'the acquired archive records solution composition per treatment, not a '
                                     'response the platform could predict. No control, page, endpoint or '
                                     'claim exists.',
                           'searched': 'NASA OSDR/ALSDA/GeneLab, Zenodo, Dryad, Figshare, PANGAEA, Mendeley '
                                       'Data, Dataverse, USDA Ag Data Commons, OpenAIRE and journal '
                                       'supplements'}},
              {'id': 'long-run-climate',
               'order': 12,
               'claim': 'Siting for a future climate rather than the observed recent past',
               'previousTier': 'data-blocked',
               'tier': 'removed',
               'tierChanged': True,
               'evidence': ['docs/DATASET_GAP_MATRIX.md'],
               'datasets': [],
               'measuredOn': 'nothing acquired: the CMIP6 downscaled product is catalogued at class D and '
                             'was not downloaded',
               'whatItSupports': ['nothing: no siting-for-future-climate claim is made'],
               'whatItDoesNotSupport': ['any projection-based recommendation'],
               'whatWouldMoveIt': 'nothing: the capability is removed rather than blocked',
               'blockingEvidence': "the product's ET0 target is the observed recent past by construction",
               'phase32': {'tier': 'removed',
                           'reason': 'The CMIP6 downscaled product is catalogued at licence class D and '
                                     'could not be acquired; no projection data is in the repository and no '
                                     'climate-siting control or report exists.',
                           'searched': 'NASA OSDR/ALSDA/GeneLab, Zenodo, Dryad, Figshare, PANGAEA, Mendeley '
                                       'Data, Dataverse, USDA Ag Data Commons, OpenAIRE and journal '
                                       'supplements'}}]}
