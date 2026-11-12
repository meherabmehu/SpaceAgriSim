"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'phase': 10,
 'generatedAt': '2026-11-07T21:13:51.994026+00:00',
 'seed': 42,
 'task': 'irradiated versus non-irradiated, cross-study',
 'trainStudy': 'OSD-46 (Affymetrix ATH1 microarray, Wild Type + atm-1)',
 'testStudy': 'OSD-782 (Illumina RNA-seq, Col-0, GeneLab VST)',
 'sharedGeneModels': 17997,
 'harmonisations': {'zscore': {'genesUsed': 150,
                               'accuracy': 0.6666666666666666,
                               'balancedAccuracy': 0.5,
                               'recallControl': 0.0,
                               'recallIrradiated': 1.0,
                               'predictedClasses': ['irradiated'],
                               'collapsedToSingleClass': True},
                    'rank': {'genesUsed': 150,
                             'accuracy': 0.6666666666666666,
                             'balancedAccuracy': 0.5,
                             'recallControl': 0.0,
                             'recallIrradiated': 1.0,
                             'predictedClasses': ['irradiated'],
                             'collapsedToSingleClass': True},
                    'quantile_map': {'genesUsed': 150,
                                     'accuracy': 0.6666666666666666,
                                     'balancedAccuracy': 0.5,
                                     'recallControl': 0.0,
                                     'recallIrradiated': 1.0,
                                     'predictedClasses': ['irradiated'],
                                     'collapsedToSingleClass': True},
                    'pathway': {'genesUsed': 50,
                                'accuracy': 0.6666666666666666,
                                'balancedAccuracy': 0.5,
                                'recallControl': 0.0,
                                'recallIrradiated': 1.0,
                                'predictedClasses': ['irradiated'],
                                'collapsedToSingleClass': True}},
 'withinStudyReference': {'scheme': 'leave-one-biological-group-out within OSD-782',
                          'accuracy': 0.5277777777777778,
                          'balancedAccuracy': 0.4375,
                          'recallControl': 0.16666666666666666,
                          'recallIrradiated': 0.7083333333333334,
                          'bootstrapCi95': [0.3, 0.5911],
                          'indistinguishableFromChance': True,
                          'practicalMeaning': "The 95% interval spans chance, so this study's own "
                                              'irradiated-vs-control contrast is not learnable by this '
                                              'pipeline. A cross-study negative against such a target cannot '
                                              'distinguish a harmonisation failure from the absence of a '
                                              'signal to transfer.',
                          'protocolSensitivity': {'cellHeldOut': 0.4375,
                                                  'timepointHeldOut': 0.8125,
                                                  'designMatched': {'scheme': 'leave-one-timepoint-out '
                                                                              'within OSD-782 '
                                                                              '(design-matched)',
                                                                    'balancedAccuracy': 0.8125,
                                                                    'recallControl': 0.9167,
                                                                    'recallIrradiated': 0.7083,
                                                                    'permutation': {'scheme': 'labels '
                                                                                              'permuted '
                                                                                              'within '
                                                                                              'timepoint '
                                                                                              '(design-preserving '
                                                                                              'null)',
                                                                                    'permutations': 2000,
                                                                                    'exceedances': 1,
                                                                                    'pCorrected': 0.001},
                                                                    'practicalMeaning': 'Under the '
                                                                                        'design-matched '
                                                                                        'protocol the target '
                                                                                        'contrast is '
                                                                                        'learnable, so '
                                                                                        'OSD-782 does carry '
                                                                                        'an '
                                                                                        'irradiated-versus-control '
                                                                                        'signal. The '
                                                                                        'cell-held-out '
                                                                                        'reference is lower '
                                                                                        'because each cell '
                                                                                        'is one sequencing '
                                                                                        'batch and holding a '
                                                                                        'cell out also asks '
                                                                                        'for generalization '
                                                                                        'across a batch. A '
                                                                                        'cross-study '
                                                                                        'transfer faces the '
                                                                                        'harder condition, '
                                                                                        'so the transfer '
                                                                                        'negative stands; '
                                                                                        'what has to change '
                                                                                        "is the phrase 'the "
                                                                                        'target has no '
                                                                                        "signal', which is "
                                                                                        'now known to be '
                                                                                        'false.'},
                                                  'statement': 'Two within-study references differ by '
                                                               'protocol. Held-out cells give 0.438 '
                                                               '(interval spans chance); held-out timepoints '
                                                               'give 0.812 (p=0.001). The target study does '
                                                               'carry a learnable contrast; it does not '
                                                               'survive generalization to an unseen (dose, '
                                                               'timepoint) cell, which is the closer '
                                                               'analogue of a cross-study transfer. Both '
                                                               'numbers are required to make either claim.'}},
 'decisionRule': 'adopt only if held-out balanced accuracy > 0.5 with non-zero recall for both classes; '
                 'beating 0.667 accuracy by predicting one class is not a result',
 'adopted': [],
 'best': 'zscore',
 'bestBalancedAccuracy': 0.5,
 'verdict': 'transfer-failed-under-every-harmonisation',
 'phase9ResultPreserved': {'balancedAccuracy': 0.5,
                           'accuracy': 0.667,
                           'note': "Phase 9's 16-setting sweep remains the reference for the z-score "
                                   'harmonisation and is not superseded.'},
 'interpretation': 'Rank and quantile mappings discard scale but keep ordering; pathway modules discard gene '
                   'identity entirely. If none of the three recovers control recall, the failure is not a '
                   'transform artefact but a difference in what the two experiments measured.'}
