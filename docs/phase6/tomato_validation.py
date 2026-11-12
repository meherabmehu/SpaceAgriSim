"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'sourceStudy': 'OSD-767',
 'samples': 36,
 'plantGroups': 21,
 'featuresAfterZeroFilter': 28001,
 'Q1_batchConfounding': {'sequencingLanes': ['L008'],
                         'laneCount': 1,
                         'allSamplesOneLane': True,
                         'interpretation': 'Every one of the 36 libraries carries the same lane suffix, so '
                                           'flight status cannot be aliased to a sequencing lane. Note this '
                                           'also means a lane-level batch effect could not be estimated even '
                                           'if one existed; the design is confounded with respect to lane by '
                                           'construction.',
                         'spectrumByEnvironment': {'blue': {'flight': 8, 'ground': 9},
                                                   'red': {'flight': 10, 'ground': 9}},
                         'tissueByEnvironment': {'leaf': {'flight': 9, 'ground': 12},
                                                 'root': {'flight': 9, 'ground': 6}},
                         'note': 'Spectrum is near-balanced (flight 8 blue / 10 red; ground 9 / 9). Tissue '
                                 'is NOT balanced (ground 12 leaf vs 6 root).'},
 'Q2_leakageControlled': {'macroF1': 0.916083916083916,
                          'accuracy': 0.9166666666666666,
                          'rocAUC': 0.9845679012345678,
                          'foldGeneSetOverlap': {'pairs': 6,
                                                 'meanSharedGenes': 29.666666666666668,
                                                 'maxSharedGenes': 37,
                                                 'k': 64}},
 'Q3_permutationTest': {'permutations': 200,
                        'observedMacroF1': 0.916083916083916,
                        'nullMean': 0.46575447039418677,
                        'nullP95': 0.6497402597402596,
                        'nullMax': 0.7498069498069498,
                        'empiricalPValue': 0.004975124378109453,
                        'grouping': 'labels permuted at the PLANT level, so the null preserves the '
                                    'biological replicate structure'},
 'Q4_tissueScope': {'leaf': {'macroF1': 0.8558352402745995,
                             'accuracy': 0.8571428571428571,
                             'rocAUC': 0.9814814814814815,
                             'n': 21,
                             'groupedCV': '4-fold stratified group CV within tissue only'},
                    'root': {'macroF1': 0.7963800904977376,
                             'accuracy': 0.8,
                             'rocAUC': 0.9444444444444445,
                             'n': 15,
                             'groupedCV': '4-fold stratified group CV within tissue only'},
                    'tissueAlonePredictsLabel': False}}
