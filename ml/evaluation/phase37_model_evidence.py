"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'schema': 'spaceagrisim.phase37.model_evidence/1',
 'generatedAt': '2026-11-12',
 'generatedBy': 'ml/research/audit_models_phase37.py',
 'policy': {'noDomainExpansion': True,
            'noThresholdMoves': True,
            'noRetraining': True,
            'noRelabelling': True,
            'note': 'Artifacts were not retrained, thresholds were not moved, and no verdict was changed. '
                    'Models are audited against the evidence rather than the evidence being shaped around '
                    'the models.'},
 'newEvidence': {'zenodo-green-light-lettuce': {'doi': '10.5281/zenodo.20394352',
                                                'note': 'Photoperiod 16 h and a targeted 200 umol m-2 s-1 '
                                                        'are stated by the authors, but no measured PPFD '
                                                        'column is deposited and no temperature is measured '
                                                        'at all. The destructive harvest is a single '
                                                        'endpoint at 35 days, outside the declared 2-29 day '
                                                        'domain.'},
                 'zenodo-nutrient-dosing': {'doi': '10.5281/zenodo.17794636',
                                            'note': 'Ion concentrations, electrical conductivity and one '
                                                    'destructive harvest. No temperature, no light and no '
                                                    'time series of mass, so every growth feature is '
                                                    'absent.'}},
 'models': {'lettuce-earth-growth-v1': {'artifactSha256': '37a822bfff18df954ebf769a37f9279d47c3ff15077b10b18d0fbe940fadf835',
                                        'registrySha256Matches': True,
                                        'artifactUnchangedFromPhase36': True,
                                        'cardMissingObligations': ['trainingCode', 'trainingDataHash'],
                                        'cardSatisfiedBy': {'identity': 'id',
                                                            'task': 'task',
                                                            'organism': 'crop',
                                                            'provenance': 'sourceStudy',
                                                            'licence': 'sourceLicense',
                                                            'method': 'method',
                                                            'features': 'features',
                                                            'outcome': 'target',
                                                            'units': 'unit',
                                                            'metrics': 'metrics',
                                                            'baseline': 'baselineMetrics',
                                                            'uncertainty': 'interval',
                                                            'domain': 'domain',
                                                            'validation': 'validation',
                                                            'limitations': 'limitations',
                                                            'seed': 'seed',
                                                            'samples': 'samples',
                                                            'groups': 'groups'},
                                        'cardComplete': False,
                                        'domainDeclared': True,
                                        'domainFeatureCount': 4,
                                        'featureCount': 4,
                                        'hasInterval': True,
                                        'hasUncertainty': True,
                                        'uncertaintyKind': 'prediction-interval',
                                        'calibrationRecorded': False,
                                        'intervalMethod': '90% cross-conformal (CV+) interval, measured '
                                                          'held-out coverage 0.939',
                                        'intervalCoverage': None,
                                        'intervalCoverageIsIndependent': True,
                                        'samples': 1648,
                                        'groups': 4,
                                        'splitIsGrouped': True,
                                        'metrics': {'MAE': 38.93942129910151,
                                                    'RMSE': 71.73248433299133,
                                                    'R2': 0.8119836421675193},
                                        'baselineMetrics': {'MAE': 125.82608582930726,
                                                            'RMSE': 169.85514939756476,
                                                            'R2': -0.054195908898403866},
                                        'status': 'trained-exploratory',
                                        'evidenceVerdictInArtifact': {'verdict': 'fails-independent-check',
                                                                      'decisionGrade': False,
                                                                      'decisionScope': None,
                                                                      'reason': '0 of 6 independent '
                                                                                'treatment means covered, '
                                                                                'prediction/measurement '
                                                                                'ratio median 3.655 '
                                                                                '(1.905-5.493)',
                                                                      'checks': [{'check': 'cross-campaign '
                                                                                           'interval '
                                                                                           'coverage',
                                                                                  'criterion': 'no '
                                                                                               'observation '
                                                                                               'may fall '
                                                                                               'outside a '
                                                                                               'nominal 90 % '
                                                                                               'interval '
                                                                                               'that is '
                                                                                               'offered as a '
                                                                                               '90 % '
                                                                                               'interval; '
                                                                                               "the study's "
                                                                                               'six '
                                                                                               'treatment '
                                                                                               'means are '
                                                                                               'independent '
                                                                                               'of the fit',
                                                                                  'measured': 0.0,
                                                                                  'unit': 'coverage of a '
                                                                                          'nominal 90 % '
                                                                                          'interval',
                                                                                  'passed': False,
                                                                                  'groups': 6,
                                                                                  'detail': '0 of 6 '
                                                                                            'independent '
                                                                                            'treatment means '
                                                                                            'covered, '
                                                                                            'prediction/measurement '
                                                                                            'ratio median '
                                                                                            '3.655 '
                                                                                            '(1.905-5.493)',
                                                                                  'evidence': 'ml/evaluation/phase34_cross_campaign_coverage'}]},
                                        'verdictBefore': 'fails-independent-check',
                                        'decisionGradeBefore': False,
                                        'newEvidenceTest': {'testable': False,
                                                            'requiredFeatures': ['daysAfterTransplant',
                                                                                 'airTemperature',
                                                                                 'rootTemperature', 'ppfd'],
                                                            'datasets': {'zenodo-green-light-lettuce': {'supplied': [],
                                                                                                        'absent': ['airTemperature',
                                                                                                                   'rootTemperature',
                                                                                                                   'ppfd'],
                                                                                                        'outOfDomain': [{'feature': 'daysAfterTransplant',
                                                                                                                         'values': [28,
                                                                                                                                    35],
                                                                                                                         'domain': [2.0,
                                                                                                                                    29.0]}]},
                                                                         'zenodo-nutrient-dosing': {'supplied': [],
                                                                                                    'absent': ['daysAfterTransplant',
                                                                                                               'airTemperature',
                                                                                                               'rootTemperature',
                                                                                                               'ppfd'],
                                                                                                    'outOfDomain': []}},
                                                            'reason': 'Neither dataset supplies every '
                                                                      'required feature inside the declared '
                                                                      'domain, so no prediction can be '
                                                                      "scored without violating the model's "
                                                                      'own contract.'},
                                        'retrained': False,
                                        'thresholdsChanged': False,
                                        'completionCard': {'present': True,
                                                           'path': 'ml/artifacts/cards/lettuce-earth-growth-v1',
                                                           'complete': True,
                                                           'checks': '15/15',
                                                           'trainingDataStatus': 'committed-file',
                                                           'trainingDataSha256': '0b6072cc4ff65ef6bcc9fd33481d96c76b710945b81e4452a78dd605349feb43',
                                                           'codeCommit': '0e1ab21773f58d87a37575cd3b8820007012672a',
                                                           'codeImmutable': True,
                                                           'artifactHashPreserved': True,
                                                           'exceptions': []},
                                        'reproductionScript': 'ml/training/train_lettuce.py',
                                        'reproductionScriptExists': True,
                                        'embedsTrainingScript': False,
                                        'embedsTrainingDataHash': False,
                                        'verdictAfter': 'fails-independent-check',
                                        'decisionGradeAfter': False,
                                        'promoted': False,
                                        'classification': 'FAILS-INDEPENDENT-CHECK',
                                        'newEvidenceOutcome': 'NOT-TESTED',
                                        'why': 'Neither dataset supplies every required feature inside the '
                                               'declared domain, so no prediction can be scored without '
                                               "violating the model's own contract."},
            'lettuce-earth-growth-v2': {'artifactSha256': '1dc8057a0511c5080357ecc93529f6989a7e932c19f954c91948cdf0584601d2',
                                        'registrySha256Matches': True,
                                        'artifactUnchangedFromPhase36': True,
                                        'cardMissingObligations': ['trainingCode', 'trainingDataHash'],
                                        'cardSatisfiedBy': {'identity': 'id',
                                                            'task': 'task',
                                                            'organism': 'crop',
                                                            'provenance': 'sourceStudy',
                                                            'licence': 'sourceLicense',
                                                            'method': 'method',
                                                            'features': 'features',
                                                            'outcome': 'target',
                                                            'units': 'unit',
                                                            'metrics': 'metrics',
                                                            'baseline': 'baselineMetrics',
                                                            'uncertainty': 'interval',
                                                            'domain': 'domain',
                                                            'validation': 'validation',
                                                            'limitations': 'limitations',
                                                            'seed': 'seed',
                                                            'samples': 'samples',
                                                            'groups': 'groups'},
                                        'cardComplete': False,
                                        'domainDeclared': True,
                                        'domainFeatureCount': 4,
                                        'featureCount': 4,
                                        'hasInterval': True,
                                        'hasUncertainty': True,
                                        'uncertaintyKind': 'prediction-interval',
                                        'calibrationRecorded': False,
                                        'intervalMethod': '90% cross-conformal (CV+) interval, measured '
                                                          'held-out coverage 0.961',
                                        'intervalCoverage': None,
                                        'intervalCoverageIsIndependent': True,
                                        'samples': 1648,
                                        'groups': 4,
                                        'splitIsGrouped': True,
                                        'metrics': {'MAE': 34.915619043397,
                                                    'RMSE': 59.67964765866537,
                                                    'R2': 0.8698583249949963},
                                        'baselineMetrics': {'MAE': 125.82608582930726,
                                                            'RMSE': 169.85514939756476,
                                                            'R2': -0.054195908898403866},
                                        'status': 'trained-exploratory',
                                        'evidenceVerdictInArtifact': {'verdict': 'fails-independent-check',
                                                                      'decisionGrade': False,
                                                                      'decisionScope': None,
                                                                      'reason': '0 of 6 independent '
                                                                                'treatment means covered, '
                                                                                'prediction/measurement '
                                                                                'ratio median 3.212 '
                                                                                '(1.674-5.375)',
                                                                      'checks': [{'check': 'cross-campaign '
                                                                                           'interval '
                                                                                           'coverage',
                                                                                  'criterion': 'no '
                                                                                               'observation '
                                                                                               'may fall '
                                                                                               'outside a '
                                                                                               'nominal 90 % '
                                                                                               'interval '
                                                                                               'that is '
                                                                                               'offered as a '
                                                                                               '90 % '
                                                                                               'interval; '
                                                                                               "the study's "
                                                                                               'six '
                                                                                               'treatment '
                                                                                               'means are '
                                                                                               'independent '
                                                                                               'of the fit',
                                                                                  'measured': 0.0,
                                                                                  'unit': 'coverage of a '
                                                                                          'nominal 90 % '
                                                                                          'interval',
                                                                                  'passed': False,
                                                                                  'groups': 6,
                                                                                  'detail': '0 of 6 '
                                                                                            'independent '
                                                                                            'treatment means '
                                                                                            'covered, '
                                                                                            'prediction/measurement '
                                                                                            'ratio median '
                                                                                            '3.212 '
                                                                                            '(1.674-5.375)',
                                                                                  'evidence': 'ml/evaluation/phase34_cross_campaign_coverage'}]},
                                        'verdictBefore': 'fails-independent-check',
                                        'decisionGradeBefore': False,
                                        'newEvidenceTest': {'testable': False,
                                                            'requiredFeatures': ['daysAfterTransplant',
                                                                                 'airTemperature',
                                                                                 'rootTemperature', 'ppfd'],
                                                            'datasets': {'zenodo-green-light-lettuce': {'supplied': [],
                                                                                                        'absent': ['airTemperature',
                                                                                                                   'rootTemperature',
                                                                                                                   'ppfd'],
                                                                                                        'outOfDomain': [{'feature': 'daysAfterTransplant',
                                                                                                                         'values': [28,
                                                                                                                                    35],
                                                                                                                         'domain': [2.0,
                                                                                                                                    29.0]}]},
                                                                         'zenodo-nutrient-dosing': {'supplied': [],
                                                                                                    'absent': ['daysAfterTransplant',
                                                                                                               'airTemperature',
                                                                                                               'rootTemperature',
                                                                                                               'ppfd'],
                                                                                                    'outOfDomain': []}},
                                                            'reason': 'Neither dataset supplies every '
                                                                      'required feature inside the declared '
                                                                      'domain, so no prediction can be '
                                                                      "scored without violating the model's "
                                                                      'own contract.'},
                                        'retrained': False,
                                        'thresholdsChanged': False,
                                        'completionCard': {'present': True,
                                                           'path': 'ml/artifacts/cards/lettuce-earth-growth-v2',
                                                           'complete': True,
                                                           'checks': '15/15',
                                                           'trainingDataStatus': 'committed-file',
                                                           'trainingDataSha256': '0b6072cc4ff65ef6bcc9fd33481d96c76b710945b81e4452a78dd605349feb43',
                                                           'codeCommit': '0e1ab21773f58d87a37575cd3b8820007012672a',
                                                           'codeImmutable': True,
                                                           'artifactHashPreserved': True,
                                                           'exceptions': []},
                                        'reproductionScript': 'ml/training/train_lettuce_v2.py',
                                        'reproductionScriptExists': True,
                                        'embedsTrainingScript': False,
                                        'embedsTrainingDataHash': False,
                                        'verdictAfter': 'fails-independent-check',
                                        'decisionGradeAfter': False,
                                        'promoted': False,
                                        'classification': 'FAILS-INDEPENDENT-CHECK',
                                        'newEvidenceOutcome': 'NOT-TESTED',
                                        'why': 'Neither dataset supplies every required feature inside the '
                                               'declared domain, so no prediction can be scored without '
                                               "violating the model's own contract."},
            'lettuce-earth-growth-v3': {'artifactSha256': 'e57e0490d5c319368c31ae4cb818630109c5300aa62df8da5ed10f9065838d99',
                                        'registrySha256Matches': True,
                                        'artifactUnchangedFromPhase36': True,
                                        'cardMissingObligations': [],
                                        'cardSatisfiedBy': {'identity': 'id',
                                                            'task': 'task',
                                                            'organism': 'crop',
                                                            'provenance': 'sourceStudy',
                                                            'licence': 'sourceLicense',
                                                            'method': 'method',
                                                            'features': 'features',
                                                            'outcome': 'target',
                                                            'units': 'unit',
                                                            'metrics': 'metrics',
                                                            'baseline': 'baselineMetrics',
                                                            'uncertainty': 'interval',
                                                            'domain': 'domain',
                                                            'validation': 'validation',
                                                            'limitations': 'limitations',
                                                            'trainingCode': 'trainingScript',
                                                            'trainingDataHash': 'trainingDataSha256',
                                                            'seed': 'seed',
                                                            'samples': 'samples',
                                                            'groups': 'groups'},
                                        'cardComplete': True,
                                        'domainDeclared': True,
                                        'domainFeatureCount': 4,
                                        'featureCount': 4,
                                        'hasInterval': True,
                                        'hasUncertainty': True,
                                        'uncertaintyKind': 'prediction-interval',
                                        'calibrationRecorded': False,
                                        'intervalMethod': 'conformal residual quantiles on the log target '
                                                          '(5% / 95%)',
                                        'intervalCoverage': 0.8992718446601942,
                                        'intervalCoverageIsIndependent': True,
                                        'samples': 1648,
                                        'groups': 4,
                                        'splitIsGrouped': True,
                                        'metrics': {'MAE': 835.5101616419312,
                                                    'RMSE': 1539.769266234756,
                                                    'MAPE': 41.68343427964123,
                                                    'meanBiasError': -249.31002468932155,
                                                    'R2': 0.8613898072115063,
                                                    'n': 1648},
                                        'baselineMetrics': {'MAE': 2797.719012503388,
                                                            'RMSE': 4668.2978449323955,
                                                            'MAPE': 459.1540328330944,
                                                            'meanBiasError': -2132.1197045195636,
                                                            'R2': -0.2740925836030792,
                                                            'n': 1648},
                                        'status': 'trained-exploratory',
                                        'evidenceVerdictInArtifact': {'verdict': 'fails-independent-check',
                                                                      'decisionGrade': False,
                                                                      'decisionScope': None,
                                                                      'reason': 'Touliatos D, Dodd IC, '
                                                                                'McAinsh M (2016) Vertical '
                                                                                'farming increases lettuce '
                                                                                'yield per unit area '
                                                                                'compared to conventional '
                                                                                'horizontal hydroponics. '
                                                                                'Food and Energy Security '
                                                                                '5(3):184-191, '
                                                                                'doi:10.1002/fes3.83: 41.594 '
                                                                                '% MAPE against 30.0 %',
                                                                      'checks': [{'check': 'independent '
                                                                                           'holdout error',
                                                                                  'criterion': 'MAPE <= 30.0 '
                                                                                               '% fixed '
                                                                                               'before the '
                                                                                               'measurement',
                                                                                  'measured': 41.59420289855073,
                                                                                  'unit': '% MAPE',
                                                                                  'passed': False,
                                                                                  'groups': 1,
                                                                                  'detail': 'Touliatos D, '
                                                                                            'Dodd IC, '
                                                                                            'McAinsh M '
                                                                                            '(2016) Vertical '
                                                                                            'farming '
                                                                                            'increases '
                                                                                            'lettuce yield '
                                                                                            'per unit area '
                                                                                            'compared to '
                                                                                            'conventional '
                                                                                            'horizontal '
                                                                                            'hydroponics. '
                                                                                            'Food and Energy '
                                                                                            'Security '
                                                                                            '5(3):184-191, '
                                                                                            'doi:10.1002/fes3.83: '
                                                                                            '41.594 % MAPE '
                                                                                            'against 30.0 %',
                                                                                  'evidence': 'ml/artifacts/lettuce-earth-growth-v3#validation.independent'},
                                                                                 {'check': 'cross-campaign '
                                                                                           'interval '
                                                                                           'coverage',
                                                                                  'criterion': 'no '
                                                                                               'observation '
                                                                                               'may fall '
                                                                                               'outside a '
                                                                                               'nominal 90 % '
                                                                                               'interval '
                                                                                               'that is '
                                                                                               'offered as a '
                                                                                               '90 % '
                                                                                               'interval; '
                                                                                               "the study's "
                                                                                               'six '
                                                                                               'treatment '
                                                                                               'means are '
                                                                                               'independent '
                                                                                               'of the fit',
                                                                                  'measured': 1.0,
                                                                                  'unit': 'coverage of a '
                                                                                          'nominal 90 % '
                                                                                          'interval',
                                                                                  'passed': True,
                                                                                  'groups': 6,
                                                                                  'detail': '6 of 6 '
                                                                                            'independent '
                                                                                            'treatment means '
                                                                                            'covered, '
                                                                                            'prediction/measurement '
                                                                                            'ratio median '
                                                                                            '1.163 '
                                                                                            '(0.606-1.863)',
                                                                                  'evidence': 'ml/evaluation/phase34_cross_campaign_coverage'}]},
                                        'verdictBefore': 'fails-independent-check',
                                        'decisionGradeBefore': False,
                                        'newEvidenceTest': {'testable': False,
                                                            'requiredFeatures': ['daysAfterTransplant',
                                                                                 'airTemperature',
                                                                                 'rootTemperature',
                                                                                 'dailyLightIntegral'],
                                                            'datasets': {'zenodo-green-light-lettuce': {'supplied': [],
                                                                                                        'absent': ['airTemperature',
                                                                                                                   'rootTemperature',
                                                                                                                   'dailyLightIntegral'],
                                                                                                        'outOfDomain': [{'feature': 'daysAfterTransplant',
                                                                                                                         'values': [28,
                                                                                                                                    35],
                                                                                                                         'domain': [2.0,
                                                                                                                                    29.0]}]},
                                                                         'zenodo-nutrient-dosing': {'supplied': [],
                                                                                                    'absent': ['daysAfterTransplant',
                                                                                                               'airTemperature',
                                                                                                               'rootTemperature',
                                                                                                               'dailyLightIntegral'],
                                                                                                    'outOfDomain': []}},
                                                            'reason': 'Neither dataset supplies every '
                                                                      'required feature inside the declared '
                                                                      'domain, so no prediction can be '
                                                                      "scored without violating the model's "
                                                                      'own contract.'},
                                        'retrained': False,
                                        'thresholdsChanged': False,
                                        'completionCard': {'present': True,
                                                           'path': 'ml/artifacts/cards/lettuce-earth-growth-v3',
                                                           'complete': True,
                                                           'checks': '15/15',
                                                           'trainingDataStatus': 'committed-file',
                                                           'trainingDataSha256': '0b6072cc4ff65ef6bcc9fd33481d96c76b710945b81e4452a78dd605349feb43',
                                                           'codeCommit': '0e1ab21773f58d87a37575cd3b8820007012672a',
                                                           'codeImmutable': True,
                                                           'artifactHashPreserved': True,
                                                           'exceptions': []},
                                        'reproductionScript': 'ml/training/train_lettuce_v3.py',
                                        'reproductionScriptExists': True,
                                        'embedsTrainingScript': True,
                                        'embedsTrainingDataHash': True,
                                        'verdictAfter': 'fails-independent-check',
                                        'decisionGradeAfter': False,
                                        'promoted': False,
                                        'classification': 'FAILS-INDEPENDENT-CHECK',
                                        'newEvidenceOutcome': 'NOT-TESTED',
                                        'why': 'Neither dataset supplies every required feature inside the '
                                               'declared domain, so no prediction can be scored without '
                                               "violating the model's own contract."},
            'mizuna-microbial-relative-load-v2': {'artifactSha256': '489cafe7b5d978fd0dfd3503e37eb8473a4a30bb2cedfaa02f397483124cb3c8',
                                                  'registrySha256Matches': True,
                                                  'artifactUnchangedFromPhase36': True,
                                                  'cardMissingObligations': ['trainingCode',
                                                                             'trainingDataHash'],
                                                  'cardSatisfiedBy': {'identity': 'id',
                                                                      'task': 'task',
                                                                      'organism': 'crop',
                                                                      'provenance': 'sourceStudy',
                                                                      'licence': 'sourceLicense',
                                                                      'method': 'method',
                                                                      'features': 'features',
                                                                      'outcome': 'target',
                                                                      'units': 'unit',
                                                                      'metrics': 'metrics',
                                                                      'baseline': 'baselineMetrics',
                                                                      'uncertainty': 'interval',
                                                                      'domain': 'domain',
                                                                      'validation': 'transfer',
                                                                      'limitations': 'limitations',
                                                                      'seed': 'seed',
                                                                      'samples': 'samples',
                                                                      'groups': 'groups'},
                                                  'cardComplete': False,
                                                  'domainDeclared': True,
                                                  'domainFeatureCount': 5,
                                                  'featureCount': 5,
                                                  'hasInterval': True,
                                                  'hasUncertainty': True,
                                                  'uncertaintyKind': 'prediction-interval',
                                                  'calibrationRecorded': False,
                                                  'intervalMethod': '90% group-level cross-conformal '
                                                                    'interval, measured held-out coverage '
                                                                    '0.992',
                                                  'intervalCoverage': None,
                                                  'intervalCoverageIsIndependent': True,
                                                  'samples': 123,
                                                  'groups': 35,
                                                  'splitIsGrouped': True,
                                                  'metrics': {'MAE': 0.5392828108720046,
                                                              'RMSE': 0.6952351873046808,
                                                              'R2': 0.5086587456447216},
                                                  'baselineMetrics': {'MAE': 0.8303342083753683,
                                                                      'RMSE': 0.9982749907043629,
                                                                      'R2': -0.013024906769362854},
                                                  'status': 'trained-exploratory',
                                                  'evidenceVerdictInArtifact': {'verdict': 'passes-independent-check',
                                                                                'decisionGrade': True,
                                                                                'decisionScope': 'Relative '
                                                                                                 'microbial '
                                                                                                 'load '
                                                                                                 'within the '
                                                                                                 'two '
                                                                                                 'measured '
                                                                                                 'VEG-04 '
                                                                                                 'campaigns '
                                                                                                 '(VEG-04A '
                                                                                                 'and '
                                                                                                 'VEG-04B in '
                                                                                                 'OSD-780), '
                                                                                                 'with a '
                                                                                                 'conformal '
                                                                                                 'interval '
                                                                                                 'measured '
                                                                                                 'in both '
                                                                                                 'directions '
                                                                                                 'across '
                                                                                                 'them: '
                                                                                                 'covering '
                                                                                                 'one '
                                                                                                 "campaign's "
                                                                                                 'radius and '
                                                                                                 'evaluating '
                                                                                                 'it on the '
                                                                                                 'other '
                                                                                                 'covers 110 '
                                                                                                 'of 123 '
                                                                                                 'samples '
                                                                                                 '(pooled '
                                                                                                 '0.894 '
                                                                                                 'against a '
                                                                                                 'nominal '
                                                                                                 '0.90). Two '
                                                                                                 'campaigns '
                                                                                                 'are not a '
                                                                                                 'sample of '
                                                                                                 'campaigns, '
                                                                                                 'so a third '
                                                                                                 "campaign's "
                                                                                                 'offset '
                                                                                                 'still has '
                                                                                                 'to come '
                                                                                                 'from its '
                                                                                                 'own '
                                                                                                 'baseline '
                                                                                                 'samples.',
                                                                                'reason': 'pooled R2 0.509 '
                                                                                          'against a '
                                                                                          'training-mean '
                                                                                          'baseline; '
                                                                                          'held-out R2 '
                                                                                          'positive on every '
                                                                                          'campaign (VEG04A '
                                                                                          '0.444, VEG04B '
                                                                                          '0.373); '
                                                                                          'permutation p = '
                                                                                          '0.0, 0.0 over 200 '
                                                                                          'permutations; '
                                                                                          'cross-campaign '
                                                                                          'interval coverage '
                                                                                          'measured; 110 of '
                                                                                          '123 samples '
                                                                                          'covered, pooled '
                                                                                          'across both '
                                                                                          'calibration '
                                                                                          'directions',
                                                                                'checks': [{'check': 'pre-registered '
                                                                                                     'evidence '
                                                                                                     'rule',
                                                                                            'criterion': 'validated-exploratory '
                                                                                                         'requires '
                                                                                                         'beating '
                                                                                                         'the '
                                                                                                         'baseline, '
                                                                                                         'positive '
                                                                                                         'R2 '
                                                                                                         'on '
                                                                                                         'every '
                                                                                                         'held-out '
                                                                                                         'campaign, '
                                                                                                         'a '
                                                                                                         'permutation '
                                                                                                         'p '
                                                                                                         '< '
                                                                                                         '0.05 '
                                                                                                         'on '
                                                                                                         'both '
                                                                                                         'campaigns, '
                                                                                                         'and '
                                                                                                         'conformal '
                                                                                                         'coverage '
                                                                                                         'within '
                                                                                                         '5 '
                                                                                                         'points '
                                                                                                         'of '
                                                                                                         'nominal.',
                                                                                            'measured': {'beatsBaselineWithinPooledData': 0.5086587456447216,
                                                                                                         'positiveR2OnEveryHeldOutCampaign': {'VEG04A': 0.44444629403166147,
                                                                                                                                              'VEG04B': 0.3727689645413145},
                                                                                                         'transferSignificantUnderPermutation': {'VEG04A': {'observedR2': 0.44444629403166147,
                                                                                                                                                            'nullMeanR2': -0.1742437130542411,
                                                                                                                                                            'nullSdR2': 0.20331855561919207,
                                                                                                                                                            'empiricalPValue': 0.0,
                                                                                                                                                            'permutations': 200},
                                                                                                                                                 'VEG04B': {'observedR2': 0.3727689645413145,
                                                                                                                                                            'nullMeanR2': -0.14919413080990798,
                                                                                                                                                            'nullSdR2': 0.14286647223689422,
                                                                                                                                                            'empiricalPValue': 0.0,
                                                                                                                                                            'permutations': 200}}},
                                                                                            'unit': 'mixed: '
                                                                                                    'R2, '
                                                                                                    'held-out '
                                                                                                    'R2 per '
                                                                                                    'campaign, '
                                                                                                    'permutation '
                                                                                                    'p',
                                                                                            'passed': True,
                                                                                            'groups': 35,
                                                                                            'detail': 'pooled '
                                                                                                      'R2 '
                                                                                                      '0.509 '
                                                                                                      'against '
                                                                                                      'a '
                                                                                                      'training-mean '
                                                                                                      'baseline; '
                                                                                                      'held-out '
                                                                                                      'R2 '
                                                                                                      'positive '
                                                                                                      'on '
                                                                                                      'every '
                                                                                                      'campaign '
                                                                                                      '(VEG04A '
                                                                                                      '0.444, '
                                                                                                      'VEG04B '
                                                                                                      '0.373); '
                                                                                                      'permutation '
                                                                                                      'p = '
                                                                                                      '0.0, '
                                                                                                      '0.0 '
                                                                                                      'over '
                                                                                                      '200 '
                                                                                                      'permutations; '
                                                                                                      'cross-campaign '
                                                                                                      'interval '
                                                                                                      'coverage '
                                                                                                      'measured',
                                                                                            'evidence': 'ml/artifacts/mizuna-microbial-relative-load-v2#evidenceBasis',
                                                                                            'ruleTerms': {'beatsBaselineWithinPooledData': True,
                                                                                                          'positiveR2OnEveryHeldOutCampaign': True,
                                                                                                          'transferSignificantUnderPermutation': True,
                                                                                                          'intervalsEmpiricallyCalibrated': True}},
                                                                                           {'check': 'cross-campaign '
                                                                                                     'conformal '
                                                                                                     'coverage',
                                                                                            'criterion': 'pooled '
                                                                                                         'achieved '
                                                                                                         'coverage '
                                                                                                         'within '
                                                                                                         '0.05 '
                                                                                                         'of '
                                                                                                         'the '
                                                                                                         'nominal '
                                                                                                         '0.90 '
                                                                                                         '(the '
                                                                                                         'rule '
                                                                                                         'the '
                                                                                                         'card '
                                                                                                         'recorded '
                                                                                                         'for '
                                                                                                         'itself)',
                                                                                            'measured': 0.8943,
                                                                                            'unit': 'coverage '
                                                                                                    'of a '
                                                                                                    'nominal '
                                                                                                    '90 % '
                                                                                                    'interval',
                                                                                            'passed': True,
                                                                                            'groups': 123,
                                                                                            'detail': '110 '
                                                                                                      'of '
                                                                                                      '123 '
                                                                                                      'samples '
                                                                                                      'covered, '
                                                                                                      'pooled '
                                                                                                      'across '
                                                                                                      'both '
                                                                                                      'calibration '
                                                                                                      'directions',
                                                                                            'evidence': 'ml/evaluation/phase34_cross_campaign_coverage'}]},
                                                  'verdictBefore': 'passes-independent-check',
                                                  'decisionGradeBefore': True,
                                                  'newEvidenceTest': {'testable': False,
                                                                      'reason': 'It predicts from flight '
                                                                                'microclimate and microbiome '
                                                                                'covariates recorded in '
                                                                                'VEG-04. Neither dataset is '
                                                                                'a VEG-04 experiment, so no '
                                                                                'independent prediction is '
                                                                                'possible. Untested rather '
                                                                                'than failed.'},
                                                  'retrained': False,
                                                  'thresholdsChanged': False,
                                                  'completionCard': {'present': True,
                                                                     'path': 'ml/artifacts/cards/mizuna-microbial-relative-load-v2',
                                                                     'complete': True,
                                                                     'checks': '15/15',
                                                                     'trainingDataStatus': 'committed-file',
                                                                     'trainingDataSha256': '9dfffb0eddc011cd593ce11b63f5dfeeb8594e8fc8d9466df9e61eed207509c0',
                                                                     'codeCommit': '0e1ab21773f58d87a37575cd3b8820007012672a',
                                                                     'codeImmutable': True,
                                                                     'artifactHashPreserved': True,
                                                                     'exceptions': []},
                                                  'reproductionScript': 'ml/training/train_microbial_v2.py',
                                                  'reproductionScriptExists': True,
                                                  'embedsTrainingScript': False,
                                                  'embedsTrainingDataHash': False,
                                                  'verdictAfter': 'passes-independent-check',
                                                  'decisionGradeAfter': True,
                                                  'promoted': False,
                                                  'classification': 'PASS decision-grade',
                                                  'newEvidenceOutcome': 'NOT-TESTED',
                                                  'why': 'It predicts from flight microclimate and '
                                                         'microbiome covariates recorded in VEG-04. Neither '
                                                         'dataset is a VEG-04 experiment, so no independent '
                                                         'prediction is possible. Untested rather than '
                                                         'failed.'},
            'radiation-exposure-osd46-v1': {'artifactSha256': '08c1009fb18412b39f0a9a21bbc25a49986caeed556f06083f9ae43d3bef1047',
                                            'registrySha256Matches': True,
                                            'artifactUnchangedFromPhase36': True,
                                            'cardMissingObligations': [],
                                            'cardSatisfiedBy': {'identity': 'id',
                                                                'task': 'task',
                                                                'organism': 'organism',
                                                                'provenance': 'sourceStudy',
                                                                'licence': 'sourceLicense',
                                                                'method': 'method',
                                                                'features': 'features',
                                                                'outcome': 'classLabels',
                                                                'units': 'expressionUnits',
                                                                'metrics': 'metrics',
                                                                'baseline': 'baselineMetrics',
                                                                'uncertainty': 'probabilityCalibration',
                                                                'domain': 'domain',
                                                                'validation': 'validation',
                                                                'limitations': 'limitations',
                                                                'trainingCode': 'evaluator',
                                                                'trainingDataHash': 'sourceChecksum',
                                                                'seed': 'seed',
                                                                'samples': 'samples',
                                                                'groups': 'groups'},
                                            'cardComplete': True,
                                            'domainDeclared': True,
                                            'domainFeatureCount': 2,
                                            'featureCount': 150,
                                            'hasInterval': False,
                                            'hasUncertainty': True,
                                            'uncertaintyKind': 'probability-calibration',
                                            'calibrationRecorded': True,
                                            'intervalMethod': None,
                                            'intervalCoverage': None,
                                            'intervalCoverageIsIndependent': False,
                                            'samples': 44,
                                            'groups': 22,
                                            'splitIsGrouped': True,
                                            'metrics': {'accuracy': 0.9318181818181818,
                                                        'balancedAccuracy': 0.9097222222222222,
                                                        'macroF1': 0.8906379453189726,
                                                        'nSamples': 44,
                                                        'nGroups': 22,
                                                        'confusionMatrix': [[7, 1], [2, 34]],
                                                        'classLabels': ['control', 'irradiated'],
                                                        'perClassRecall': {'control': 0.875,
                                                                           'irradiated': 0.9444444444444444},
                                                        'bootstrapCi': {'metric': 'balancedAccuracy',
                                                                        'lower': 0.7708333333333333,
                                                                        'upper': 1.0,
                                                                        'confidence': 0.95,
                                                                        'method': 'stratified percentile '
                                                                                  'bootstrap over held-out '
                                                                                  'predictions'},
                                                        'genesSharedAcrossFolds': 95,
                                                        'singleClassHeldOutGroups': ['irradiated',
                                                                                     'irradiated',
                                                                                     'irradiated',
                                                                                     'irradiated',
                                                                                     'irradiated',
                                                                                     'irradiated',
                                                                                     'irradiated',
                                                                                     'irradiated',
                                                                                     'irradiated',
                                                                                     'irradiated', 'control',
                                                                                     'control', 'irradiated',
                                                                                     'irradiated',
                                                                                     'irradiated',
                                                                                     'irradiated',
                                                                                     'irradiated',
                                                                                     'irradiated',
                                                                                     'irradiated',
                                                                                     'irradiated', 'control',
                                                                                     'control'],
                                                        'validationScheme': 'leave-one-biological-group-out'},
                                            'baselineMetrics': {'accuracy': 0.8181818181818182,
                                                                'balancedAccuracy': 0.5,
                                                                'macroF1': 0.45,
                                                                'nSamples': 44,
                                                                'nGroups': 22,
                                                                'confusionMatrix': [[0, 8], [0, 36]],
                                                                'classLabels': ['control', 'irradiated'],
                                                                'perClassRecall': {'control': 0.0,
                                                                                   'irradiated': 1.0},
                                                                'validationScheme': 'leave-one-biological-group-out'},
                                            'status': 'trained-exploratory',
                                            'evidenceVerdictInArtifact': {'verdict': 'no-independent-check',
                                                                          'decisionGrade': False,
                                                                          'decisionScope': None,
                                                                          'reason': 'Only within-study or '
                                                                                    'within-campaign '
                                                                                    'performance is '
                                                                                    'recorded; no '
                                                                                    'independent campaign '
                                                                                    'has scored this model.',
                                                                          'checks': []},
                                            'verdictBefore': 'no-independent-check',
                                            'decisionGradeBefore': False,
                                            'newEvidenceTest': {'testable': False,
                                                                'reason': 'Transcriptomic model. It consumes '
                                                                          'a normalised expression vector, '
                                                                          'not environmental measurements, '
                                                                          'and neither dataset deposits '
                                                                          'expression. Untested rather than '
                                                                          'failed.'},
                                            'retrained': False,
                                            'thresholdsChanged': False,
                                            'completionCard': {'present': True,
                                                               'path': 'ml/artifacts/cards/radiation-exposure-osd46-v1',
                                                               'complete': True,
                                                               'checks': '15/15',
                                                               'trainingDataStatus': 'recorded-checksum',
                                                               'trainingDataSha256': 'f15c4179dbbebdfd39c53ffb906f6251ed1fc3fa3c926efc3c71c4736eefda27',
                                                               'codeCommit': '0e1ab21773f58d87a37575cd3b8820007012672a',
                                                               'codeImmutable': True,
                                                               'artifactHashPreserved': True,
                                                               'exceptions': []},
                                            'reproductionScript': 'ml/training/train_radiation_osd46.py',
                                            'reproductionScriptExists': True,
                                            'embedsTrainingScript': False,
                                            'embedsTrainingDataHash': True,
                                            'verdictAfter': 'no-independent-check',
                                            'decisionGradeAfter': False,
                                            'promoted': False,
                                            'classification': 'NO-INDEPENDENT-CHECK',
                                            'newEvidenceOutcome': 'NOT-TESTED',
                                            'why': 'Transcriptomic model. It consumes a normalised '
                                                   'expression vector, not environmental measurements, and '
                                                   'neither dataset deposits expression. Untested rather '
                                                   'than failed.'},
            'radiation-quality-osd46-v1': {'artifactSha256': '16a7b0f0b2ee69e89525215964b32380fd7d8aa3e5a1e4e91f9f7ea730b7352e',
                                           'registrySha256Matches': True,
                                           'artifactUnchangedFromPhase36': True,
                                           'cardMissingObligations': [],
                                           'cardSatisfiedBy': {'identity': 'id',
                                                               'task': 'task',
                                                               'organism': 'organism',
                                                               'provenance': 'sourceStudy',
                                                               'licence': 'sourceLicense',
                                                               'method': 'method',
                                                               'features': 'features',
                                                               'outcome': 'classLabels',
                                                               'units': 'expressionUnits',
                                                               'metrics': 'metrics',
                                                               'baseline': 'baselineMetrics',
                                                               'uncertainty': 'probabilityCalibration',
                                                               'domain': 'domain',
                                                               'validation': 'validation',
                                                               'limitations': 'limitations',
                                                               'trainingCode': 'evaluator',
                                                               'trainingDataHash': 'sourceChecksum',
                                                               'seed': 'seed',
                                                               'samples': 'samples',
                                                               'groups': 'groups'},
                                           'cardComplete': True,
                                           'domainDeclared': True,
                                           'domainFeatureCount': 2,
                                           'featureCount': 150,
                                           'hasInterval': False,
                                           'hasUncertainty': True,
                                           'uncertaintyKind': 'probability-calibration',
                                           'calibrationRecorded': True,
                                           'intervalMethod': None,
                                           'intervalCoverage': None,
                                           'intervalCoverageIsIndependent': False,
                                           'samples': 44,
                                           'groups': 22,
                                           'splitIsGrouped': True,
                                           'metrics': {'accuracy': 0.9318181818181818,
                                                       'balancedAccuracy': 0.8981481481481483,
                                                       'macroF1': 0.9063063063063064,
                                                       'nSamples': 44,
                                                       'nGroups': 22,
                                                       'confusionMatrix': [[6, 0, 2], [0, 18, 0], [1, 0, 17]],
                                                       'classLabels': ['control', 'gamma', 'hze'],
                                                       'perClassRecall': {'control': 0.75,
                                                                          'gamma': 1.0,
                                                                          'hze': 0.9444444444444444},
                                                       'bootstrapCi': {'metric': 'balancedAccuracy',
                                                                       'lower': 0.7916666666666666,
                                                                       'upper': 1.0,
                                                                       'confidence': 0.95,
                                                                       'method': 'stratified percentile '
                                                                                 'bootstrap over held-out '
                                                                                 'predictions'},
                                                       'genesSharedAcrossFolds': 75,
                                                       'singleClassHeldOutGroups': ['hze', 'hze', 'hze',
                                                                                    'hze', 'hze', 'gamma',
                                                                                    'gamma', 'gamma', 'gamma',
                                                                                    'gamma', 'control',
                                                                                    'control', 'hze', 'hze',
                                                                                    'hze', 'hze', 'gamma',
                                                                                    'gamma', 'gamma', 'gamma',
                                                                                    'control', 'control'],
                                                       'validationScheme': 'leave-one-biological-group-out'},
                                           'baselineMetrics': {'accuracy': 0.0,
                                                               'balancedAccuracy': 0.0,
                                                               'macroF1': 0.0,
                                                               'nSamples': 44,
                                                               'nGroups': 22,
                                                               'confusionMatrix': [[0, 8, 0], [0, 0, 18],
                                                                                   [0, 18, 0]],
                                                               'classLabels': ['control', 'gamma', 'hze'],
                                                               'perClassRecall': {'control': 0.0,
                                                                                  'gamma': 0.0,
                                                                                  'hze': 0.0},
                                                               'validationScheme': 'leave-one-biological-group-out'},
                                           'status': 'trained-exploratory',
                                           'evidenceVerdictInArtifact': {'verdict': 'no-independent-check',
                                                                         'decisionGrade': False,
                                                                         'decisionScope': None,
                                                                         'reason': 'Only within-study or '
                                                                                   'within-campaign '
                                                                                   'performance is recorded; '
                                                                                   'no independent campaign '
                                                                                   'has scored this model.',
                                                                         'checks': []},
                                           'verdictBefore': 'no-independent-check',
                                           'decisionGradeBefore': False,
                                           'newEvidenceTest': {'testable': False,
                                                               'reason': 'Transcriptomic model. It consumes '
                                                                         'a normalised expression vector, '
                                                                         'not environmental measurements, '
                                                                         'and neither dataset deposits '
                                                                         'expression. Untested rather than '
                                                                         'failed.'},
                                           'retrained': False,
                                           'thresholdsChanged': False,
                                           'completionCard': {'present': True,
                                                              'path': 'ml/artifacts/cards/radiation-quality-osd46-v1',
                                                              'complete': True,
                                                              'checks': '15/15',
                                                              'trainingDataStatus': 'recorded-checksum',
                                                              'trainingDataSha256': 'f15c4179dbbebdfd39c53ffb906f6251ed1fc3fa3c926efc3c71c4736eefda27',
                                                              'codeCommit': '0e1ab21773f58d87a37575cd3b8820007012672a',
                                                              'codeImmutable': True,
                                                              'artifactHashPreserved': True,
                                                              'exceptions': []},
                                           'reproductionScript': 'ml/training/train_radiation_osd46.py',
                                           'reproductionScriptExists': True,
                                           'embedsTrainingScript': False,
                                           'embedsTrainingDataHash': True,
                                           'verdictAfter': 'no-independent-check',
                                           'decisionGradeAfter': False,
                                           'promoted': False,
                                           'classification': 'NO-INDEPENDENT-CHECK',
                                           'newEvidenceOutcome': 'NOT-TESTED',
                                           'why': 'Transcriptomic model. It consumes a normalised expression '
                                                  'vector, not environmental measurements, and neither '
                                                  'dataset deposits expression. Untested rather than '
                                                  'failed.'},
            'tomato-flight-response-v1': {'artifactSha256': '674de9f1cc06b001b52da356fe37822d159d5b86fc7f508d5ffe2b6b2d2f708d',
                                          'registrySha256Matches': True,
                                          'artifactUnchangedFromPhase36': True,
                                          'cardMissingObligations': ['trainingCode', 'trainingDataHash'],
                                          'cardSatisfiedBy': {'identity': 'id',
                                                              'task': 'task',
                                                              'organism': 'crop',
                                                              'provenance': 'sourceStudy',
                                                              'licence': 'sourceLicense',
                                                              'method': 'method',
                                                              'features': 'features',
                                                              'outcome': 'target',
                                                              'units': 'unit',
                                                              'metrics': 'metrics',
                                                              'baseline': 'metrics.baselineMacroF1',
                                                              'uncertainty': 'probabilityCalibration',
                                                              'domain': 'domain',
                                                              'validation': 'validation',
                                                              'limitations': 'limitations',
                                                              'seed': 'seed',
                                                              'samples': 'samples',
                                                              'groups': 'groups'},
                                          'cardComplete': False,
                                          'domainDeclared': True,
                                          'domainFeatureCount': 64,
                                          'featureCount': 64,
                                          'hasInterval': False,
                                          'hasUncertainty': True,
                                          'uncertaintyKind': 'probability-calibration',
                                          'calibrationRecorded': True,
                                          'intervalMethod': None,
                                          'intervalCoverage': None,
                                          'intervalCoverageIsIndependent': False,
                                          'samples': 36,
                                          'groups': 21,
                                          'splitIsGrouped': True,
                                          'metrics': {'accuracy': 0.9166666666666666,
                                                      'macroF1': 0.916083916083916,
                                                      'precision': 1.0,
                                                      'recall': 0.8333333333333334,
                                                      'ROC_AUC': 0.9753086419753086,
                                                      'confusionMatrix': [[18, 0], [3, 15]],
                                                      'baselineMacroF1': 0.4444444444444444},
                                          'baselineMetrics': 0.4444444444444444,
                                          'status': 'trained-exploratory',
                                          'evidenceVerdictInArtifact': {'verdict': 'no-independent-check',
                                                                        'decisionGrade': False,
                                                                        'decisionScope': None,
                                                                        'reason': 'Only within-study or '
                                                                                  'within-campaign '
                                                                                  'performance is recorded; '
                                                                                  'no independent campaign '
                                                                                  'has scored this model.',
                                                                        'checks': []},
                                          'verdictBefore': 'no-independent-check',
                                          'decisionGradeBefore': False,
                                          'newEvidenceTest': {'testable': False,
                                                              'reason': 'Transcriptomic model. It consumes a '
                                                                        'normalised expression vector, not '
                                                                        'environmental measurements, and '
                                                                        'neither dataset deposits '
                                                                        'expression. Untested rather than '
                                                                        'failed.'},
                                          'retrained': False,
                                          'thresholdsChanged': False,
                                          'completionCard': {'present': True,
                                                             'path': 'ml/artifacts/cards/tomato-flight-response-v1',
                                                             'complete': True,
                                                             'checks': '15/15',
                                                             'trainingDataStatus': 'reconstructed-derived',
                                                             'trainingDataSha256': '88b335847f4a7d342c8c948c5369c8de990c3870f95b455ac2cd7418b2aa56b1',
                                                             'codeCommit': '0e1ab21773f58d87a37575cd3b8820007012672a',
                                                             'codeImmutable': True,
                                                             'artifactHashPreserved': True,
                                                             'exceptions': []},
                                          'reproductionScript': 'ml/training/train_models.py',
                                          'reproductionScriptExists': True,
                                          'embedsTrainingScript': False,
                                          'embedsTrainingDataHash': False,
                                          'verdictAfter': 'no-independent-check',
                                          'decisionGradeAfter': False,
                                          'promoted': False,
                                          'classification': 'NO-INDEPENDENT-CHECK',
                                          'newEvidenceOutcome': 'NOT-TESTED',
                                          'why': 'Transcriptomic model. It consumes a normalised expression '
                                                 'vector, not environmental measurements, and neither '
                                                 'dataset deposits expression. Untested rather than '
                                                 'failed.'}},
 'counts': {'served': 7,
            'retainedNotServed': 3,
            'scored': 0,
            'classification': {'DOMAIN-REFUSED': 0,
                               'FAILS-INDEPENDENT-CHECK': 3,
                               'INSUFFICIENT-EVIDENCE': 0,
                               'NO-INDEPENDENT-CHECK': 3,
                               'PASS decision-grade': 1},
            'notTestedByNewEvidence': 7,
            'decisionGradeBefore': 1,
            'decisionGradeAfter': 1,
            'artifactHashesVerified': 7,
            'cardsComplete': 3,
            'domainsDeclared': 7,
            'withInterval': 4,
            'withUncertainty': 7,
            'groupedSplits': 7,
            'withBaseline': 7,
            'reproductionScriptResolvable': 7,
            'completionCardsPresent': 7,
            'completionCardsComplete': 7,
            'completionCardsWithTrainingDataHash': 7,
            'completionCardsWithImmutableCode': 7,
            'embedTrainingDataHash': 3}}
