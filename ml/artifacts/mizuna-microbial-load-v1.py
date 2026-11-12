"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'id': 'mizuna-microbial-load-v1',
 'name': 'Mizuna edible-leaf microbial load (VEG-04A/B)',
 'version': '1.0.0',
 'status': 'trained-exploratory',
 'trainedAt': '2026-11-07T14:30:58.930043+00:00',
 'task': 'Culturable aerobic microbial load regression on edible leaf tissue',
 'sourceStudy': 'OSD-780',
 'sourceUrl': 'https://osdr.nasa.gov/bio/repo/data/studies/OSD-780',
 'sourceType': 'NASA OSDR ALSDA plate-count measurement tables (LSDS-128)',
 'crop': 'mizuna',
 'method': 'NASA-data-trained exploratory regression (ridge / random forest comparison)',
 'samples': 123,
 'groups': 35,
 'features': ['flight', 'blueLight', 'isVEG04B', 'sanitised', 'freshWeightG', 'harvestIndex'],
 'target': 'log10(1 + CFU per gram fresh leaf weight)',
 'unit': 'log10 CFU/g fresh weight',
 'metrics': {'MAE': 1.0865849313520286, 'RMSE': 1.4040103119054692, 'R2': 0.5489527281649196},
 'baselineMetrics': {'MAE': 1.718346225785013, 'RMSE': 2.098104470338046, 'R2': -0.0072463063573193764},
 'forestMetrics': {'MAE': 1.1361504943695615, 'RMSE': 1.4607720546616367, 'R2': 0.5117453711703475},
 'beatsBaselineMAE': True,
 'beatsBaselineR2': True,
 'leaveOneExperimentOut': {'VEG04A': {'MAE': 1.7766254095559593,
                                      'RMSE': 2.097268916276685,
                                      'R2': -0.5547731771401376,
                                      'nTest': 20},
                           'VEG04B': {'MAE': 2.364543976617508,
                                      'RMSE': 2.6002105160987354,
                                      'R2': -0.5800397306959184,
                                      'nTest': 103}},
 'evidenceStatus': 'experimental',
 'evidenceBasis': {'beatsBaselineWithinPooledData': True,
                   'transfersToHeldOutExperiment': False,
                   'intervalsEmpiricallyCalibrated': False,
                   'rule': 'validated-exploratory requires beating the baseline, positive R2 on every '
                           'leave-one-experiment-out holdout, and conformal empirical coverage within 5 '
                           'points of nominal. Otherwise the model is reported as experimental.'},
 'recommendedUse': 'Descriptive in-campaign microbial-load stratification only. Do NOT use to predict a new '
                   'mission, a different cultivar or a different hardware configuration: '
                   'leave-one-experiment-out R2 is negative for both campaigns.',
 'validation': '4-fold GroupKFold grouped by pillow (biological replicate), with a nested 3-fold grouped '
               'alpha search. Gene-to-fold leakage is impossible because all samples from one pillow stay in '
               'one fold. A separate leave-one-experiment-out diagnostic holds out an entire VEG-04A or '
               'VEG-04B campaign.',
 'uncertainty': {'method': 'group-level cross-conformal',
                 'radius': 3.555489,
                 'nominalCoverage': 0.9,
                 'achievedCoverage': 0.9919,
                 'calibrationGroups': 35,
                 'calibrationResiduals': 35,
                 'exchangeabilityUnit': 'biological group (worst residual within group)',
                 'rowLevelRadiusForComparison': 2.764619,
                 'groupLevelRadiusForComparison': 3.555489,
                 'empiricallyCalibrated': True,
                 'evidence': 'ml/evaluation/phase10_conformal',
                 'caveat': 'Coverage within the two observed campaigns. The model still does not transfer to '
                           "an unseen campaign's absolute level."},
 'interval': {'radius': 3.555489,
              'kind': '90% group-level cross-conformal interval, measured held-out coverage 0.992',
              'nominalCoverage': 0.9,
              'empiricalCoverage': 0.9919,
              'empiricallyCalibrated': True,
              'calibrationGroups': 35,
              'caveat': 'Coverage within the two observed campaigns. The model still does not transfer to an '
                        "unseen campaign's absolute level.",
              'supersedes': 'Phase 9 split conformal, which measured 0.849 and 0.811 against a nominal 0.90',
              'crossCampaign': {'campaigns': ['VEG04A', 'VEG04B'],
                                'method': '90th percentile of |residual| on the calibration campaign, '
                                          'applied unchanged to the other campaign; both directions '
                                          'reported, then pooled',
                                'directions': {'calibratedOnVEG04A/evaluatedOnVEG04B': {'radius': 2.2603,
                                                                                        'covered': 87,
                                                                                        'observations': 103,
                                                                                        'achievedCoverage': 0.8447},
                                               'calibratedOnVEG04B/evaluatedOnVEG04A': {'radius': 2.5883,
                                                                                        'covered': 20,
                                                                                        'observations': 20,
                                                                                        'achievedCoverage': 1.0}},
                                'covered': 107,
                                'observations': 123,
                                'pooledAchievedCoverage': 0.8699,
                                'evidence': 'ml/evaluation/phase34_cross_campaign_coverage',
                                'statement': 'Within-campaign coverage over both VEG-04 campaigns is 0.9919. '
                                             'Calibrating the 90 % radius on one campaign and evaluating it '
                                             'on the other covers 107 of 123 samples (pooled 0.8699 across '
                                             'both directions). The campaign offset is not a function of the '
                                             'features, so this is the bound that matters when the model '
                                             'meets a third campaign.'}},
 'measuredContrast': {'VEG04A': {'flightMean': 5.61662668086303,
                                 'flightN': 5,
                                 'groundMean': 2.5539849355814583,
                                 'groundN': 15,
                                 'difference': 3.0626417452815717,
                                 'foldDifference': 1155.1589446074104},
                      'VEG04B': {'flightMean': 3.6146518797314253,
                                 'flightN': 31,
                                 'groundMean': 0.9754322703681536,
                                 'groundN': 72,
                                 'difference': 2.6392196093632716,
                                 'foldDifference': 435.73215433630645}},
 'hyperparameters': {'linear__alpha': 10.0},
 'seed': 42,
 'domain': {'flight': {'min': 0.0, 'max': 1.0},
            'blueLight': {'min': 0.0, 'max': 1.0},
            'isVEG04B': {'min': 0.0, 'max': 1.0},
            'sanitised': {'min': 0.0, 'max': 1.0},
            'freshWeightG': {'min': 1.1, 'max': 10.8},
            'harvestIndex': {'min': 1.0, 'max': 3.0}},
 'limitations': ['Plate counts capture only culturable aerobic organisms; total microbial load is higher and '
                 'unmeasured.',
                 'The target is microbial load on leaf tissue. It is NOT biomass, yield, growth rate or '
                 'shelf life.',
                 'freshWeightG is the mass of the tissue subsample taken for the assay, not harvest biomass.',
                 'VEG-04A and VEG-04B differ in design; the leave-one-experiment-out errors show how poorly '
                 'the effect transfers and must be read before use.',
                 'Two experimental campaigns only, both VEG-04 mizuna on ISS. No lettuce, tomato or radish '
                 'transfer.',
                 'Flight/ground differences may reflect cabin environment, payload handling or sampling '
                 'protocol, not gravity per se. Causality is not established.',
                 'Not a food-safety clearance tool. Do not use for consumption decisions.'],
 'linear': {'mean': [0.2926829268292683, 0.4878048780487805, 0.8373983739837398, 0.34146341463414637,
                     3.720325203252033, 1.829268292682927],
            'scale': [0.45499410015067393, 0.49985125687607784, 0.3690018119645598, 0.47420053890789216,
                      1.9067257658812307, 0.8333234185410577],
            'coefficients': [0.9606604991499315, 0.11873896256583684, -0.6566999625358607,
                             -0.44764093792121856, 0.31865014494882393, 0.7569361549605401],
            'intercept': 2.021774302245677},
 'phase10': {'uncertaintyRecalibratedAt': '2026-11-07T20:23:00.769833+00:00',
             'method': 'group-level cross-conformal'},
 'license': 'Public OSDR access; retain study attribution and comply with OSDR terms; do not assume every '
            'contributed file is public domain.',
 'sourceLicense': 'Public OSDR access; retain study attribution and comply with OSDR terms; do not assume '
                  'every contributed file is public domain.',
 'sourceLicenseUrl': 'https://science.nasa.gov/reference/osdr-help-terms-and-conditions/',
 'sourceCitation': 'NASA Open Science Data Repository, OSD-780: VEG-04A mizuna microbial load (plate '
                   'counts).',
 'sourceRetrieved': '2026-11-09',
 'servedScope': 'Relative microbial load within the two measured VEG-04 campaigns (VEG-04A and VEG-04B in '
                'OSD-780). The model predicts a within-campaign contrast, not an absolute colony count: the '
                "campaign offset is not a function of the features and must come from that campaign's own "
                'baseline samples.',
 'operationalForecast': False,
 'harvestForecastClaim': 'none',
 'note': 'No operational forecast. This card describes what the model reproduces inside the measured domain; '
         'it is not a prediction of a future or unmeasured crop.'}
