"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'phase': 11,
 'task': 'separate the OSD-346 gravity signal from its flight-run structure',
 'studies': {'osd314': {'columns': 100,
                        'runOrBatchColumns': [],
                        'hasRunIdentifier': False,
                        'statement': 'OSD-314 has no run, batch, lane or date column at all, so the Phase 10 '
                                     'claim that neither deposit carries a run identifier was right for '
                                     'OSD-314 and wrong for OSD-346. Its 1.000 can therefore be neither '
                                     'attributed to biology nor cleared of batch: the structure is simply '
                                     'unrecorded.'},
             'osd346': {'runs': 6,
                        'runByCommandedGravity': {'SG1 Run 1': {'0.00g': 6},
                                                  'SG1 Run 2': {'0.10g': 6},
                                                  'SG1 Run 3': {'0.25g': 2, '0.30g': 2, '0.38g': 2},
                                                  'SG1 Run 4': {'0.64g': 1, '0.65g': 1, '1.00g': 4},
                                                  'SG2 Run 1': {'0.38g': 2,
                                                                '0.50g': 2,
                                                                '0.64g': 1,
                                                                '0.65g': 1},
                                                  'SG2 Run 2': {'0.64g': 1, '0.65g': 1, '1.00g': 4}},
                        'gravityLevelsObservedInMoreThanOneRun': ['0.38g', '0.64g', '0.65g', '1.00g'],
                        'gravityLevelsTotal': 9,
                        'fullGravityRangeG': 1.05,
                        'meanWithinRunGravityRangeG': 0.192,
                        'withinRunRangeAsFractionOfFull': 0.183,
                        'pc1VarianceExplainedByRun': 0.297,
                        'statement': 'Each flight run carried one gravity band, so gravity is nested inside '
                                     'run and run is nested inside mission year. Only 4 of 9 commanded '
                                     'levels appear in more than one run, and the mean within-run gravity '
                                     'range is 18% of the full 0-1 g range.'}},
 'B1_confound': {'runs': 6,
                 'runByCommandedGravity': {'SG1 Run 1': {'0.00g': 6},
                                           'SG1 Run 2': {'0.10g': 6},
                                           'SG1 Run 3': {'0.25g': 2, '0.30g': 2, '0.38g': 2},
                                           'SG1 Run 4': {'0.64g': 1, '0.65g': 1, '1.00g': 4},
                                           'SG2 Run 1': {'0.38g': 2, '0.50g': 2, '0.64g': 1, '0.65g': 1},
                                           'SG2 Run 2': {'0.64g': 1, '0.65g': 1, '1.00g': 4}},
                 'gravityLevelsObservedInMoreThanOneRun': ['0.38g', '0.64g', '0.65g', '1.00g'],
                 'gravityLevelsTotal': 9,
                 'fullGravityRangeG': 1.05,
                 'meanWithinRunGravityRangeG': 0.192,
                 'withinRunRangeAsFractionOfFull': 0.183,
                 'pc1VarianceExplainedByRun': 0.297,
                 'statement': 'Each flight run carried one gravity band, so gravity is nested inside run and '
                              'run is nested inside mission year. Only 4 of 9 commanded levels appear in '
                              'more than one run, and the mean within-run gravity range is 18% of the full '
                              '0-1 g range.'},
 'B2_batchEffectStrength': {'task': 'identify the flight run from expression, folds are genotype x light '
                                    'treatment so no shortcut exists',
                            'runAccuracy': 0.6944,
                            'balancedAccuracy': 0.6944,
                            'interpretation': 'A high out-of-sample run accuracy means runs are strongly '
                                              'separable in expression, so any label nested inside run can '
                                              'be predicted from the batch effect alone.'},
 'B3_runRemoval': {'rawFeatures': {'permutationIsInformative': True,
                                   'meanFractionOfLabelsChanged': 0.603,
                                   'nullStandardDeviation': 0.0219,
                                   'observedSpearman': 0.7521,
                                   'null95': [0.6891, 0.7743],
                                   'exceedances': 391,
                                   'pCorrected': 0.1959,
                                   'pIsTrustworthy': True,
                                   'permutations': 2000,
                                   'scheme': 'gravity shuffled within flight run'},
                   'runCentredFeatures': {'permutationIsInformative': True,
                                          'meanFractionOfLabelsChanged': 0.603,
                                          'nullStandardDeviation': 0.0255,
                                          'observedSpearman': -0.7981,
                                          'null95': [-0.8234, -0.7244],
                                          'exceedances': 1640,
                                          'pCorrected': 0.82009,
                                          'pIsTrustworthy': True,
                                          'permutations': 2000,
                                          'scheme': 'gravity shuffled within flight run'},
                   'betweenRunComponent': {'runs': 6,
                                           'spearmanOfRunMeans': 0.8286,
                                           'p': 0.0416,
                                           'runMeanGravity': {'SG1 Run 1': 0.0,
                                                              'SG1 Run 2': 0.1,
                                                              'SG1 Run 3': 0.305,
                                                              'SG1 Run 4': 0.78,
                                                              'SG2 Run 1': 0.512,
                                                              'SG2 Run 2': 0.822},
                                           'runMeanPredictedG': {'SG1 Run 1': 0.195,
                                                                 'SG1 Run 2': 0.085,
                                                                 'SG1 Run 3': 0.357,
                                                                 'SG1 Run 4': 0.685,
                                                                 'SG2 Run 1': 0.319,
                                                                 'SG2 Run 2': 0.562}},
                   'withinRunComponent': {'permutationIsInformative': True,
                                          'meanFractionOfLabelsChanged': 0.603,
                                          'nullStandardDeviation': 0.1761,
                                          'observedSpearman': 0.2291,
                                          'null95': [-0.3352, 0.3554],
                                          'exceedances': 220,
                                          'pCorrected': 0.11044,
                                          'pIsTrustworthy': True,
                                          'permutations': 2000,
                                          'scheme': 'gravity shuffled within flight run'},
                   'accuracyOnRealisedG': {'raw': 0.1737, 'runCentred': 0.9919},
                   'predictionSpread': {'rawStandardDeviationG': 0.26,
                                        'runCentredStandardDeviationG': 0.967}},
 'B4_identifiability': {'question': 'after removing all between-run variation, is enough gravity range left?',
                        'remainingRangeG': 0.192,
                        'originalRangeG': 1.05,
                        'fraction': 0.183,
                        'identifiable': False,
                        'verdict': 'Run removal leaves only a small fraction of the 0-1 g range, so the '
                                   'study cannot test the wide-range gravity question once the batch is '
                                   'removed. The wide-range graded signal and the flight run are the same '
                                   'variable.'},
 'C_phase10Correction': {'phase10Claim': {'observedSpearman': 0.571,
                                          'pCorrected': 0.0015,
                                          'nullScheme': 'gravity shuffled within light treatment'},
                         'phase11Reanalysis': {'observedSpearman': 0.7521,
                                               'pCorrected': 0.1959,
                                               'nullScheme': 'gravity shuffled within flight run'},
                         'whyTheyDiffer': 'Every light treatment spans all six flight runs, so shuffling '
                                          'within treatment destroys the run structure and centres the null '
                                          'on zero. A correlation measured across runs then looks '
                                          'overwhelming. Shuffling within run preserves the structure the '
                                          'label is nested in, and the same correlation lands inside that '
                                          'null.',
                         'statement': "Phase 10's graded-gravity result (rho 0.571, p 0.0015) does not "
                                      'survive a null that respects the run nesting. The number is '
                                      'unchanged; the null it was compared against was wrong. Phase 10 '
                                      'correctly reported that the 0 g versus partial contrast did not '
                                      'replicate, so no served claim depended on this.',
                         'supersedes': 'phase10_partial_gravity_replication.P2_gradedRegression.correlation'},
 'decisionRule': 'The graded gravity signal counts as separable from the batch if the run-centred regression '
                 'keeps a positive Spearman correlation with within-run-permutation p below 0.05. Fixed '
                 'before the run.',
 'signalSurvivesRunRemoval': False,
 'conclusion': 'osd346-gravity-signal-is-not-separable-from-flight-run',
 'whatThisDoesNotSay': ['It does not say gravity has no effect on the transcriptome.',
                        'It does not say the OSD-314 result was a batch artefact; OSD-314 records no batch '
                        'structure to check.',
                        'It does not rehabilitate the Phase 10 graded signal either: that signal is measured '
                        'across runs as well as across gravity.'],
 'researcherRequest': "OSD-346's ISA table already contains the run identifier, so no request is needed "
                      'there. OSD-314 does need one: its archive records no run, batch or harvest date, and '
                      "without it the 1.000 cannot be attributed. A request for OSD-314's sequencing run and "
                      'library prep batch identifiers has NOT been sent and no reply is claimed.',
 'registryChange': None}
