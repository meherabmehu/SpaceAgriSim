"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'schema': 'spaceagrisim.model_evidence/1',
 'purpose': 'One machine-derived evidence verdict per registered model, read from committed evaluation files '
            'and model cards. No verdict is typed in by hand.',
 'criteria': {'coverageTolerance': 0.05,
              'decisionGrade': 'true only for passes-independent-check',
              'note': 'A model with no independent check is not failed, but it is not validated either, and '
                      'the verdict says exactly that.'},
 'models': {'lettuce-earth-growth-v1': {'verdict': 'fails-independent-check',
                                        'decisionGrade': False,
                                        'decisionScope': None,
                                        'reason': '0 of 6 independent treatment means covered, '
                                                  'prediction/measurement ratio median 3.655 (1.905-5.493)',
                                        'checks': [{'check': 'cross-campaign interval coverage',
                                                    'criterion': 'no observation may fall outside a nominal '
                                                                 '90 % interval that is offered as a 90 % '
                                                                 "interval; the study's six treatment means "
                                                                 'are independent of the fit',
                                                    'measured': 0.0,
                                                    'unit': 'coverage of a nominal 90 % interval',
                                                    'passed': False,
                                                    'groups': 6,
                                                    'detail': '0 of 6 independent treatment means covered, '
                                                              'prediction/measurement ratio median 3.655 '
                                                              '(1.905-5.493)',
                                                    'evidence': 'ml/evaluation/phase34_cross_campaign_coverage'}]},
            'lettuce-earth-growth-v2': {'verdict': 'fails-independent-check',
                                        'decisionGrade': False,
                                        'decisionScope': None,
                                        'reason': '0 of 6 independent treatment means covered, '
                                                  'prediction/measurement ratio median 3.212 (1.674-5.375)',
                                        'checks': [{'check': 'cross-campaign interval coverage',
                                                    'criterion': 'no observation may fall outside a nominal '
                                                                 '90 % interval that is offered as a 90 % '
                                                                 "interval; the study's six treatment means "
                                                                 'are independent of the fit',
                                                    'measured': 0.0,
                                                    'unit': 'coverage of a nominal 90 % interval',
                                                    'passed': False,
                                                    'groups': 6,
                                                    'detail': '0 of 6 independent treatment means covered, '
                                                              'prediction/measurement ratio median 3.212 '
                                                              '(1.674-5.375)',
                                                    'evidence': 'ml/evaluation/phase34_cross_campaign_coverage'}]},
            'lettuce-earth-growth-v3': {'verdict': 'fails-independent-check',
                                        'decisionGrade': False,
                                        'decisionScope': None,
                                        'reason': 'Touliatos D, Dodd IC, McAinsh M (2016) Vertical farming '
                                                  'increases lettuce yield per unit area compared to '
                                                  'conventional horizontal hydroponics. Food and Energy '
                                                  'Security 5(3):184-191, doi:10.1002/fes3.83: 41.594 % MAPE '
                                                  'against 30.0 %',
                                        'checks': [{'check': 'independent holdout error',
                                                    'criterion': 'MAPE <= 30.0 % fixed before the '
                                                                 'measurement',
                                                    'measured': 41.59420289855073,
                                                    'unit': '% MAPE',
                                                    'passed': False,
                                                    'groups': 1,
                                                    'detail': 'Touliatos D, Dodd IC, McAinsh M (2016) '
                                                              'Vertical farming increases lettuce yield per '
                                                              'unit area compared to conventional horizontal '
                                                              'hydroponics. Food and Energy Security '
                                                              '5(3):184-191, doi:10.1002/fes3.83: 41.594 % '
                                                              'MAPE against 30.0 %',
                                                    'evidence': 'ml/artifacts/lettuce-earth-growth-v3#validation.independent'},
                                                   {'check': 'cross-campaign interval coverage',
                                                    'criterion': 'no observation may fall outside a nominal '
                                                                 '90 % interval that is offered as a 90 % '
                                                                 "interval; the study's six treatment means "
                                                                 'are independent of the fit',
                                                    'measured': 1.0,
                                                    'unit': 'coverage of a nominal 90 % interval',
                                                    'passed': True,
                                                    'groups': 6,
                                                    'detail': '6 of 6 independent treatment means covered, '
                                                              'prediction/measurement ratio median 1.163 '
                                                              '(0.606-1.863)',
                                                    'evidence': 'ml/evaluation/phase34_cross_campaign_coverage'}]},
            'mizuna-harvest-v1': {'verdict': 'withdrawn',
                                  'decisionGrade': False,
                                  'reason': 'Not served. Retained as a documented negative result.',
                                  'checks': []},
            'mizuna-microbial-load-v1': {'verdict': 'withdrawn',
                                         'decisionGrade': False,
                                         'reason': 'Not served. Retained as a documented negative result.',
                                         'checks': [{'check': 'pre-registered evidence rule',
                                                     'criterion': 'validated-exploratory requires beating '
                                                                  'the baseline, positive R2 on every '
                                                                  'leave-one-experiment-out holdout, and '
                                                                  'conformal empirical coverage within 5 '
                                                                  'points of nominal. Otherwise the model is '
                                                                  'reported as experimental.',
                                                     'measured': {'beatsBaselineWithinPooledData': 0.5489527281649196,
                                                                  'positiveR2OnEveryHeldOutCampaign': None,
                                                                  'transferSignificantUnderPermutation': None},
                                                     'unit': 'mixed: R2, held-out R2 per campaign, '
                                                             'permutation p',
                                                     'passed': False,
                                                     'groups': 35,
                                                     'detail': 'pooled R2 0.549 against a training-mean '
                                                               'baseline; cross-campaign interval coverage '
                                                               'measured',
                                                     'evidence': 'ml/artifacts/mizuna-microbial-load-v1#evidenceBasis',
                                                     'ruleTerms': {'beatsBaselineWithinPooledData': True,
                                                                   'transfersToHeldOutExperiment': False,
                                                                   'intervalsEmpiricallyCalibrated': True}},
                                                    {'check': 'cross-campaign conformal coverage',
                                                     'criterion': 'pooled achieved coverage within 0.05 of '
                                                                  'the nominal 0.90 (the rule the card '
                                                                  'recorded for itself)',
                                                     'measured': 0.8699,
                                                     'unit': 'coverage of a nominal 90 % interval',
                                                     'passed': True,
                                                     'groups': 123,
                                                     'detail': '107 of 123 samples covered, pooled across '
                                                               'both calibration directions',
                                                     'evidence': 'ml/evaluation/phase34_cross_campaign_coverage'}]},
            'mizuna-microbial-relative-load-v2': {'verdict': 'passes-independent-check',
                                                  'decisionGrade': True,
                                                  'decisionScope': 'Relative microbial load within the two '
                                                                   'measured VEG-04 campaigns (VEG-04A and '
                                                                   'VEG-04B in OSD-780), with a conformal '
                                                                   'interval measured in both directions '
                                                                   "across them: covering one campaign's "
                                                                   'radius and evaluating it on the other '
                                                                   'covers 110 of 123 samples (pooled 0.894 '
                                                                   'against a nominal 0.90). Two campaigns '
                                                                   'are not a sample of campaigns, so a '
                                                                   "third campaign's offset still has to "
                                                                   'come from its own baseline samples.',
                                                  'reason': 'pooled R2 0.509 against a training-mean '
                                                            'baseline; held-out R2 positive on every '
                                                            'campaign (VEG04A 0.444, VEG04B 0.373); '
                                                            'permutation p = 0.0, 0.0 over 200 permutations; '
                                                            'cross-campaign interval coverage measured; 110 '
                                                            'of 123 samples covered, pooled across both '
                                                            'calibration directions',
                                                  'checks': [{'check': 'pre-registered evidence rule',
                                                              'criterion': 'validated-exploratory requires '
                                                                           'beating the baseline, positive '
                                                                           'R2 on every held-out campaign, a '
                                                                           'permutation p < 0.05 on both '
                                                                           'campaigns, and conformal '
                                                                           'coverage within 5 points of '
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
                                                              'unit': 'mixed: R2, held-out R2 per campaign, '
                                                                      'permutation p',
                                                              'passed': True,
                                                              'groups': 35,
                                                              'detail': 'pooled R2 0.509 against a '
                                                                        'training-mean baseline; held-out R2 '
                                                                        'positive on every campaign (VEG04A '
                                                                        '0.444, VEG04B 0.373); permutation p '
                                                                        '= 0.0, 0.0 over 200 permutations; '
                                                                        'cross-campaign interval coverage '
                                                                        'measured',
                                                              'evidence': 'ml/artifacts/mizuna-microbial-relative-load-v2#evidenceBasis',
                                                              'ruleTerms': {'beatsBaselineWithinPooledData': True,
                                                                            'positiveR2OnEveryHeldOutCampaign': True,
                                                                            'transferSignificantUnderPermutation': True,
                                                                            'intervalsEmpiricallyCalibrated': True}},
                                                             {'check': 'cross-campaign conformal coverage',
                                                              'criterion': 'pooled achieved coverage within '
                                                                           '0.05 of the nominal 0.90 (the '
                                                                           'rule the card recorded for '
                                                                           'itself)',
                                                              'measured': 0.8943,
                                                              'unit': 'coverage of a nominal 90 % interval',
                                                              'passed': True,
                                                              'groups': 123,
                                                              'detail': '110 of 123 samples covered, pooled '
                                                                        'across both calibration directions',
                                                              'evidence': 'ml/evaluation/phase34_cross_campaign_coverage'}]},
            'radiation-exposure-osd46-v1': {'verdict': 'no-independent-check',
                                            'decisionGrade': False,
                                            'decisionScope': None,
                                            'reason': 'Only within-study or within-campaign performance is '
                                                      'recorded; no independent campaign has scored this '
                                                      'model.',
                                            'checks': []},
            'radiation-quality-osd46-v1': {'verdict': 'no-independent-check',
                                           'decisionGrade': False,
                                           'decisionScope': None,
                                           'reason': 'Only within-study or within-campaign performance is '
                                                     'recorded; no independent campaign has scored this '
                                                     'model.',
                                           'checks': []},
            'tomato-flight-response-v1': {'verdict': 'no-independent-check',
                                          'decisionGrade': False,
                                          'decisionScope': None,
                                          'reason': 'Only within-study or within-campaign performance is '
                                                    'recorded; no independent campaign has scored this '
                                                    'model.',
                                          'checks': []}},
 'counts': {'passes-independent-check': 1,
            'fails-independent-check': 3,
            'no-independent-check': 3,
            'withdrawn': 2,
            'decisionGrade': 1}}
