"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'phase': 11,
 'promotionMargin': 0.02,
 'models': {'radiation-quality-osd46-v1': {'arrays': 44,
                                           'groups': 22,
                                           'classes': ['Fe-56 ion radiation', 'gamma radiation',
                                                       'non-irradiated'],
                                           'candidates': {'shipped': {'candidate': 'shipped',
                                                                      'accuracy': 0.9318,
                                                                      'balancedAccuracy': 0.8981,
                                                                      'macroF1': 0.9063,
                                                                      'folds': 22,
                                                                      'foldBalancedAccuracySd': 0.2284,
                                                                      'foldsBelowChance': 1,
                                                                      'permutation': {'observed': 0.8981,
                                                                                      'null95': [0.2037,
                                                                                                 0.4769],
                                                                                      'exceedances': 0,
                                                                                      'permutations': 2000,
                                                                                      'pCorrected': 0.0005}},
                                                          'sparse': {'candidate': 'sparse',
                                                                     'accuracy': 0.7955,
                                                                     'balancedAccuracy': 0.6481,
                                                                     'macroF1': 0.5833,
                                                                     'folds': 22,
                                                                     'foldBalancedAccuracySd': 0.389,
                                                                     'foldsBelowChance': 4,
                                                                     'permutation': {'observed': 0.6481,
                                                                                     'null95': [0.2222,
                                                                                                0.4444],
                                                                                     'exceedances': 0,
                                                                                     'permutations': 2000,
                                                                                     'pCorrected': 0.0005},
                                                                     'perGroupVersusShipped': {'wins': 1,
                                                                                               'losses': 4,
                                                                                               'ties': 17},
                                                                     'deltaVersusShipped': -0.25,
                                                                     'meetsPromotionBar': False,
                                                                     'promotionDecision': 'rejected: below '
                                                                                          'the 0.02 '
                                                                                          'balanced-accuracy '
                                                                                          'margin'},
                                                          'linear_svm': {'candidate': 'linear_svm',
                                                                         'accuracy': 0.8864,
                                                                         'balancedAccuracy': 0.8611,
                                                                         'macroF1': 0.8543,
                                                                         'folds': 22,
                                                                         'foldBalancedAccuracySd': 0.2989,
                                                                         'foldsBelowChance': 2,
                                                                         'permutation': {'observed': 0.8611,
                                                                                         'null95': [0.2037,
                                                                                                    0.4815],
                                                                                         'exceedances': 0,
                                                                                         'permutations': 2000,
                                                                                         'pCorrected': 0.0005},
                                                                         'perGroupVersusShipped': {'wins': 0,
                                                                                                   'losses': 2,
                                                                                                   'ties': 20},
                                                                         'deltaVersusShipped': -0.037,
                                                                         'meetsPromotionBar': False,
                                                                         'promotionDecision': 'rejected: '
                                                                                              'below the '
                                                                                              '0.02 '
                                                                                              'balanced-accuracy '
                                                                                              'margin'},
                                                          'shallow_25genes': {'candidate': 'shallow_25genes',
                                                                              'accuracy': 0.9545,
                                                                              'balancedAccuracy': 0.9167,
                                                                              'macroF1': 0.9348,
                                                                              'folds': 22,
                                                                              'foldBalancedAccuracySd': 0.2083,
                                                                              'foldsBelowChance': 1,
                                                                              'permutation': {'observed': 0.9167,
                                                                                              'null95': [0.2037,
                                                                                                         0.4769],
                                                                                              'exceedances': 0,
                                                                                              'permutations': 2000,
                                                                                              'pCorrected': 0.0005},
                                                                              'perGroupVersusShipped': {'wins': 1,
                                                                                                        'losses': 0,
                                                                                                        'ties': 21},
                                                                              'deltaVersusShipped': 0.0186,
                                                                              'meetsPromotionBar': False,
                                                                              'promotionDecision': 'rejected: '
                                                                                                   'below '
                                                                                                   'the 0.02 '
                                                                                                   'balanced-accuracy '
                                                                                                   'margin'},
                                                          'coexpression_modules': {'candidate': 'coexpression_modules',
                                                                                   'accuracy': 0.2727,
                                                                                   'balancedAccuracy': 0.2222,
                                                                                   'macroF1': 0.2,
                                                                                   'folds': 22,
                                                                                   'foldBalancedAccuracySd': 0.249,
                                                                                   'foldsBelowChance': 10,
                                                                                   'permutation': {'observed': 0.2222,
                                                                                                   'null95': [0.2222,
                                                                                                              0.4444],
                                                                                                   'exceedances': 1973,
                                                                                                   'permutations': 2000,
                                                                                                   'pCorrected': 0.98651},
                                                                                   'perGroupVersusShipped': {'wins': 0,
                                                                                                             'losses': 20,
                                                                                                             'ties': 2},
                                                                                   'deltaVersusShipped': -0.6759,
                                                                                   'meetsPromotionBar': False,
                                                                                   'promotionDecision': 'rejected: '
                                                                                                        'below '
                                                                                                        'the '
                                                                                                        '0.02 '
                                                                                                        'balanced-accuracy '
                                                                                                        'margin'},
                                                          'auto_selected_nested': {'candidate': 'auto_selected_nested',
                                                                                   'accuracy': 0.8864,
                                                                                   'balancedAccuracy': 0.8611,
                                                                                   'macroF1': 0.8543,
                                                                                   'folds': 22,
                                                                                   'foldBalancedAccuracySd': 0.2989,
                                                                                   'foldsBelowChance': 2,
                                                                                   'configurationsChosenInsideFolds': {'perFold': ['k=25/l2',
                                                                                                                                   'k=150/svm',
                                                                                                                                   'k=150/svm',
                                                                                                                                   'k=25/l2',
                                                                                                                                   'k=150/svm',
                                                                                                                                   'k=25/l2',
                                                                                                                                   'k=150/svm',
                                                                                                                                   'k=25/l2',
                                                                                                                                   'k=25/l2',
                                                                                                                                   'k=25/l2',
                                                                                                                                   'k=150/svm',
                                                                                                                                   'k=150/l2',
                                                                                                                                   'k=25/l2',
                                                                                                                                   'k=25/l2',
                                                                                                                                   'k=25/l2',
                                                                                                                                   'k=25/l2',
                                                                                                                                   'k=150/svm',
                                                                                                                                   'k=25/l2',
                                                                                                                                   'k=25/l2',
                                                                                                                                   'k=25/l2',
                                                                                                                                   'k=150/svm',
                                                                                                                                   'k=150/l2'],
                                                                                                                       'tally': {'k=25/l2': 10,
                                                                                                                                 'k=75/l2': 6,
                                                                                                                                 'k=150/svm': 5,
                                                                                                                                 'k=150/l2': 1},
                                                                                                                       'note': 'which '
                                                                                                                               '(gene '
                                                                                                                               'count, '
                                                                                                                               'learner) '
                                                                                                                               'pair '
                                                                                                                               'the '
                                                                                                                               'inner '
                                                                                                                               'loop '
                                                                                                                               'picked '
                                                                                                                               'for '
                                                                                                                               'each '
                                                                                                                               'held-out '
                                                                                                                               'group. '
                                                                                                                               'A '
                                                                                                                               'preponderance '
                                                                                                                               'of '
                                                                                                                               'one '
                                                                                                                               'configuration '
                                                                                                                               'means '
                                                                                                                               'the '
                                                                                                                               'inner '
                                                                                                                               'loop '
                                                                                                                               'is '
                                                                                                                               'stable; '
                                                                                                                               'a '
                                                                                                                               'spread '
                                                                                                                               'means '
                                                                                                                               'the '
                                                                                                                               'outer '
                                                                                                                               'score '
                                                                                                                               'is '
                                                                                                                               'averaging '
                                                                                                                               'over '
                                                                                                                               'disagreement.'},
                                                                                   'permutation': {'observed': 0.8611,
                                                                                                   'null95': [0.2037,
                                                                                                              0.4815],
                                                                                                   'exceedances': 0,
                                                                                                   'permutations': 2000,
                                                                                                   'pCorrected': 0.0005},
                                                                                   'perGroupVersusShipped': {'wins': 0,
                                                                                                             'losses': 2,
                                                                                                             'ties': 20},
                                                                                   'deltaVersusShipped': -0.037,
                                                                                   'meetsPromotionBar': False,
                                                                                   'promotionDecision': 'rejected: '
                                                                                                        'below '
                                                                                                        'the '
                                                                                                        '0.02 '
                                                                                                        'balanced-accuracy '
                                                                                                        'margin'}},
                                           'fidelity': {'phase9CommittedBalancedAccuracy': 0.8981,
                                                        'phase11ReproducedBalancedAccuracy': 0.8981,
                                                        'difference': 0.0,
                                                        'verdict': 'reproduced',
                                                        'note': 'The shipped row must reproduce the '
                                                                'committed Phase 9 number before any '
                                                                'candidate is compared against it; a '
                                                                'lookalike baseline makes every delta '
                                                                'meaningless.'},
                                           'nestedSelection': {'nestedBalancedAccuracy': 0.8611,
                                                               'shippedBalancedAccuracy': 0.8981,
                                                               'deltaVersusShipped': -0.037,
                                                               'beatsShippedAtTheNestedLevel': False,
                                                               'statement': 'Choosing the configuration '
                                                                            'inside each outer fold does not '
                                                                            'beat the shipped model, so the '
                                                                            'fixed-k gains below are '
                                                                            'attributed to comparing six '
                                                                            'candidates on the same 22 folds '
                                                                            'rather than to a better '
                                                                            'learner.'},
                                           'bestCandidate': 'shallow_25genes',
                                           'shippedBalancedAccuracy': 0.8981,
                                           'shippedPermutationP': 0.0005,
                                           'anyPromoted': False,
                                           'promotionBasis': 'auto_selected_nested only (fixed-k rows are '
                                                             'exploratory)',
                                           'registryChange': None},
            'radiation-exposure-osd46-v1': {'arrays': 44,
                                            'groups': 22,
                                            'classes': ['control', 'irradiated'],
                                            'candidates': {'shipped': {'candidate': 'shipped',
                                                                       'accuracy': 0.9318,
                                                                       'balancedAccuracy': 0.9097,
                                                                       'macroF1': 0.8906,
                                                                       'folds': 22,
                                                                       'foldBalancedAccuracySd': 0.2284,
                                                                       'foldsBelowChance': 1,
                                                                       'permutation': {'observed': 0.9097,
                                                                                       'null95': [0.375,
                                                                                                  0.6806],
                                                                                       'exceedances': 0,
                                                                                       'permutations': 2000,
                                                                                       'pCorrected': 0.0005},
                                                                       'calibration': {'expectedCalibrationError': 0.0489,
                                                                                       'brier': 0.0394,
                                                                                       'logLoss': 0.1208,
                                                                                       'bins': [{'bin': '0.0-0.2',
                                                                                                 'n': 6,
                                                                                                 'meanPredicted': 0.063,
                                                                                                 'observedRate': 0.0},
                                                                                                {'bin': '0.2-0.4',
                                                                                                 'n': 2,
                                                                                                 'meanPredicted': 0.278,
                                                                                                 'observedRate': 0.5},
                                                                                                {'bin': '0.4-0.6',
                                                                                                 'n': 3,
                                                                                                 'meanPredicted': 0.522,
                                                                                                 'observedRate': 0.667},
                                                                                                {'bin': '0.6-0.8',
                                                                                                 'n': 2,
                                                                                                 'meanPredicted': 0.662,
                                                                                                 'observedRate': 1.0},
                                                                                                {'bin': '0.8-1.0',
                                                                                                 'n': 31,
                                                                                                 'meanPredicted': 0.993,
                                                                                                 'observedRate': 1.0}],
                                                                                       'note': 'single-logit '
                                                                                               'models on 44 '
                                                                                               'arrays. The '
                                                                                               'ECE is '
                                                                                               'descriptive: '
                                                                                               'five bins '
                                                                                               'over 44 '
                                                                                               'samples '
                                                                                               'cannot '
                                                                                               'validate a '
                                                                                               'calibration '
                                                                                               'curve.'}},
                                                           'sparse': {'candidate': 'sparse',
                                                                      'accuracy': 0.7727,
                                                                      'balancedAccuracy': 0.4722,
                                                                      'macroF1': 0.4359,
                                                                      'folds': 22,
                                                                      'foldBalancedAccuracySd': 0.4191,
                                                                      'foldsBelowChance': 5,
                                                                      'permutation': {'observed': 0.4722,
                                                                                      'null95': [0.4722,
                                                                                                 0.625],
                                                                                      'exceedances': 2000,
                                                                                      'permutations': 2000,
                                                                                      'pCorrected': 1.0},
                                                                      'calibration': {'expectedCalibrationError': 0.227,
                                                                                      'brier': 0.2095,
                                                                                      'logLoss': 0.6109,
                                                                                      'bins': [{'bin': '0.4-0.6',
                                                                                                'n': 22,
                                                                                                'meanPredicted': 0.559,
                                                                                                'observedRate': 0.909},
                                                                                               {'bin': '0.6-0.8',
                                                                                                'n': 22,
                                                                                                'meanPredicted': 0.623,
                                                                                                'observedRate': 0.727}],
                                                                                      'note': 'single-logit '
                                                                                              'models on 44 '
                                                                                              'arrays. The '
                                                                                              'ECE is '
                                                                                              'descriptive: '
                                                                                              'five bins '
                                                                                              'over 44 '
                                                                                              'samples '
                                                                                              'cannot '
                                                                                              'validate a '
                                                                                              'calibration '
                                                                                              'curve.'},
                                                                      'perGroupVersusShipped': {'wins': 0,
                                                                                                'losses': 4,
                                                                                                'ties': 18},
                                                                      'deltaVersusShipped': -0.4375,
                                                                      'meetsPromotionBar': False,
                                                                      'promotionDecision': 'rejected: below '
                                                                                           'the 0.02 '
                                                                                           'balanced-accuracy '
                                                                                           'margin'},
                                                           'linear_svm': {'candidate': 'linear_svm',
                                                                          'accuracy': 0.9318,
                                                                          'balancedAccuracy': 0.9583,
                                                                          'macroF1': 0.8993,
                                                                          'folds': 22,
                                                                          'foldBalancedAccuracySd': 0.2284,
                                                                          'foldsBelowChance': 1,
                                                                          'permutation': {'observed': 0.9583,
                                                                                          'null95': [0.3472,
                                                                                                     0.6528],
                                                                                          'exceedances': 0,
                                                                                          'permutations': 2000,
                                                                                          'pCorrected': 0.0005},
                                                                          'calibration': None,
                                                                          'perGroupVersusShipped': {'wins': 1,
                                                                                                    'losses': 1,
                                                                                                    'ties': 20},
                                                                          'deltaVersusShipped': 0.0486,
                                                                          'meetsPromotionBar': False,
                                                                          'promotionDecision': 'rejected: '
                                                                                               'did not win '
                                                                                               'on more than '
                                                                                               'half of the '
                                                                                               'groups'},
                                                           'shallow_25genes': {'candidate': 'shallow_25genes',
                                                                               'accuracy': 0.9545,
                                                                               'balancedAccuracy': 0.9722,
                                                                               'macroF1': 0.9302,
                                                                               'folds': 22,
                                                                               'foldBalancedAccuracySd': 0.2083,
                                                                               'foldsBelowChance': 1,
                                                                               'permutation': {'observed': 0.9722,
                                                                                               'null95': [0.3611,
                                                                                                          0.6667],
                                                                                               'exceedances': 0,
                                                                                               'permutations': 2000,
                                                                                               'pCorrected': 0.0005},
                                                                               'calibration': {'expectedCalibrationError': 0.1025,
                                                                                               'brier': 0.0575,
                                                                                               'logLoss': 0.2175,
                                                                                               'bins': [{'bin': '0.0-0.2',
                                                                                                         'n': 4,
                                                                                                         'meanPredicted': 0.109,
                                                                                                         'observedRate': 0.5},
                                                                                                        {'bin': '0.2-0.4',
                                                                                                         'n': 6,
                                                                                                         'meanPredicted': 0.279,
                                                                                                         'observedRate': 0.0},
                                                                                                        {'bin': '0.6-0.8',
                                                                                                         'n': 2,
                                                                                                         'meanPredicted': 0.779,
                                                                                                         'observedRate': 1.0},
                                                                                                        {'bin': '0.8-1.0',
                                                                                                         'n': 32,
                                                                                                         'meanPredicted': 0.974,
                                                                                                         'observedRate': 1.0}],
                                                                                               'note': 'single-logit '
                                                                                                       'models '
                                                                                                       'on '
                                                                                                       '44 '
                                                                                                       'arrays. '
                                                                                                       'The '
                                                                                                       'ECE '
                                                                                                       'is '
                                                                                                       'descriptive: '
                                                                                                       'five '
                                                                                                       'bins '
                                                                                                       'over '
                                                                                                       '44 '
                                                                                                       'samples '
                                                                                                       'cannot '
                                                                                                       'validate '
                                                                                                       'a '
                                                                                                       'calibration '
                                                                                                       'curve.'},
                                                                               'perGroupVersusShipped': {'wins': 1,
                                                                                                         'losses': 0,
                                                                                                         'ties': 21},
                                                                               'deltaVersusShipped': 0.0625,
                                                                               'meetsPromotionBar': False,
                                                                               'promotionDecision': 'rejected: '
                                                                                                    'meets '
                                                                                                    'the '
                                                                                                    'fixed-k '
                                                                                                    'bar but '
                                                                                                    'the '
                                                                                                    'nested '
                                                                                                    're-selection '
                                                                                                    'does '
                                                                                                    'not '
                                                                                                    'reproduce '
                                                                                                    'it, so '
                                                                                                    'the '
                                                                                                    'gain is '
                                                                                                    'a '
                                                                                                    'selection '
                                                                                                    'effect'},
                                                           'coexpression_modules': {'candidate': 'coexpression_modules',
                                                                                    'accuracy': 0.8182,
                                                                                    'balancedAccuracy': 0.5,
                                                                                    'macroF1': 0.45,
                                                                                    'folds': 22,
                                                                                    'foldBalancedAccuracySd': 0.3857,
                                                                                    'foldsBelowChance': 4,
                                                                                    'permutation': {'observed': 0.5,
                                                                                                    'null95': [0.5,
                                                                                                               0.5],
                                                                                                    'exceedances': 2000,
                                                                                                    'permutations': 2000,
                                                                                                    'pCorrected': 1.0},
                                                                                    'calibration': {'expectedCalibrationError': 0.111,
                                                                                                    'brier': 0.1669,
                                                                                                    'logLoss': 0.5915,
                                                                                                    'bins': [{'bin': '0.8-1.0',
                                                                                                              'n': 44,
                                                                                                              'meanPredicted': 0.929,
                                                                                                              'observedRate': 0.818}],
                                                                                                    'note': 'single-logit '
                                                                                                            'models '
                                                                                                            'on '
                                                                                                            '44 '
                                                                                                            'arrays. '
                                                                                                            'The '
                                                                                                            'ECE '
                                                                                                            'is '
                                                                                                            'descriptive: '
                                                                                                            'five '
                                                                                                            'bins '
                                                                                                            'over '
                                                                                                            '44 '
                                                                                                            'samples '
                                                                                                            'cannot '
                                                                                                            'validate '
                                                                                                            'a '
                                                                                                            'calibration '
                                                                                                            'curve.'},
                                                                                    'perGroupVersusShipped': {'wins': 1,
                                                                                                              'losses': 4,
                                                                                                              'ties': 17},
                                                                                    'deltaVersusShipped': -0.4097,
                                                                                    'meetsPromotionBar': False,
                                                                                    'promotionDecision': 'rejected: '
                                                                                                         'below '
                                                                                                         'the '
                                                                                                         '0.02 '
                                                                                                         'balanced-accuracy '
                                                                                                         'margin'},
                                                           'auto_selected_nested': {'candidate': 'auto_selected_nested',
                                                                                    'accuracy': 0.9318,
                                                                                    'balancedAccuracy': 0.9097,
                                                                                    'macroF1': 0.8906,
                                                                                    'folds': 22,
                                                                                    'foldBalancedAccuracySd': 0.2284,
                                                                                    'foldsBelowChance': 1,
                                                                                    'configurationsChosenInsideFolds': {'perFold': ['k=25/l2',
                                                                                                                                    'k=150/svm',
                                                                                                                                    'k=150/svm',
                                                                                                                                    'k=25/l2',
                                                                                                                                    'k=150/svm',
                                                                                                                                    'k=25/l2',
                                                                                                                                    'k=150/svm',
                                                                                                                                    'k=25/l2',
                                                                                                                                    'k=25/l2',
                                                                                                                                    'k=25/l2',
                                                                                                                                    'k=150/svm',
                                                                                                                                    'k=150/l2',
                                                                                                                                    'k=25/l2',
                                                                                                                                    'k=25/l2',
                                                                                                                                    'k=25/l2',
                                                                                                                                    'k=25/l2',
                                                                                                                                    'k=150/svm',
                                                                                                                                    'k=25/l2',
                                                                                                                                    'k=25/l2',
                                                                                                                                    'k=25/l2',
                                                                                                                                    'k=150/svm',
                                                                                                                                    'k=150/l2'],
                                                                                                                        'tally': {'k=25/l2': 13,
                                                                                                                                  'k=150/svm': 7,
                                                                                                                                  'k=150/l2': 2},
                                                                                                                        'note': 'which '
                                                                                                                                '(gene '
                                                                                                                                'count, '
                                                                                                                                'learner) '
                                                                                                                                'pair '
                                                                                                                                'the '
                                                                                                                                'inner '
                                                                                                                                'loop '
                                                                                                                                'picked '
                                                                                                                                'for '
                                                                                                                                'each '
                                                                                                                                'held-out '
                                                                                                                                'group. '
                                                                                                                                'A '
                                                                                                                                'preponderance '
                                                                                                                                'of '
                                                                                                                                'one '
                                                                                                                                'configuration '
                                                                                                                                'means '
                                                                                                                                'the '
                                                                                                                                'inner '
                                                                                                                                'loop '
                                                                                                                                'is '
                                                                                                                                'stable; '
                                                                                                                                'a '
                                                                                                                                'spread '
                                                                                                                                'means '
                                                                                                                                'the '
                                                                                                                                'outer '
                                                                                                                                'score '
                                                                                                                                'is '
                                                                                                                                'averaging '
                                                                                                                                'over '
                                                                                                                                'disagreement.'},
                                                                                    'permutation': {'observed': 0.9097,
                                                                                                    'null95': [0.375,
                                                                                                               0.6806],
                                                                                                    'exceedances': 0,
                                                                                                    'permutations': 2000,
                                                                                                    'pCorrected': 0.0005},
                                                                                    'calibration': None,
                                                                                    'perGroupVersusShipped': {'wins': 0,
                                                                                                              'losses': 0,
                                                                                                              'ties': 22},
                                                                                    'deltaVersusShipped': 0.0,
                                                                                    'meetsPromotionBar': False,
                                                                                    'promotionDecision': 'rejected: '
                                                                                                         'below '
                                                                                                         'the '
                                                                                                         '0.02 '
                                                                                                         'balanced-accuracy '
                                                                                                         'margin'}},
                                            'fidelity': {'phase9CommittedBalancedAccuracy': 0.9097,
                                                         'phase11ReproducedBalancedAccuracy': 0.9097,
                                                         'difference': 0.0,
                                                         'verdict': 'reproduced',
                                                         'note': 'The shipped row must reproduce the '
                                                                 'committed Phase 9 number before any '
                                                                 'candidate is compared against it; a '
                                                                 'lookalike baseline makes every delta '
                                                                 'meaningless.'},
                                            'nestedSelection': {'nestedBalancedAccuracy': 0.9097,
                                                                'shippedBalancedAccuracy': 0.9097,
                                                                'deltaVersusShipped': 0.0,
                                                                'beatsShippedAtTheNestedLevel': False,
                                                                'statement': 'Choosing the configuration '
                                                                             'inside each outer fold does '
                                                                             'not beat the shipped model, so '
                                                                             'the fixed-k gains below are '
                                                                             'attributed to comparing six '
                                                                             'candidates on the same 22 '
                                                                             'folds rather than to a better '
                                                                             'learner.'},
                                            'bestCandidate': 'shallow_25genes',
                                            'shippedBalancedAccuracy': 0.9097,
                                            'shippedPermutationP': 0.0005,
                                            'anyPromoted': False,
                                            'promotionBasis': 'auto_selected_nested only (fixed-k rows are '
                                                              'exploratory)',
                                            'registryChange': None}},
 'protocol': {'outerLoop': 'leave-one-biological-group-out, 22 folds',
              'selection': 'ANOVA on training rows only, inside each outer fold',
              'hyperparameters': 'fixed a priori; no inner search, so nothing is tuned on test',
              'promotionRule': 'beat the shipped model by 0.02 balanced accuracy, win on more than half the '
                               'groups, and keep permutation p below 0.05',
              'whySoStrict': '44 arrays over 22 groups; 0.02 balanced accuracy is about one array, so a '
                             'smaller margin is noise with a number attached',
              'candidateSelectionTrap': 'five configurations compared on the same 22 folds makes the '
                                        'best-looking row optimistic. auto_selected_nested redoes the choice '
                                        'of configuration inside every outer fold, so it is the only row '
                                        'whose score is not inflated by our having picked the winner '
                                        'ourselves'},
 'verdict': 'no-candidate-meets-the-promotion-bar'}
