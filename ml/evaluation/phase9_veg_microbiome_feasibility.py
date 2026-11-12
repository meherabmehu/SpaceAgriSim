"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'phase': 9,
 'task': 'crop microbiome feasibility (Priority C)',
 'generatedAt': '2026-11-07T16:56:45.884949+00:00',
 'seed': 20261107,
 'discovery': 'A systematic sweep of 587 studies found 231 with processed matrices; 6 publish processed '
              'taxonomic count tables. OSD-267 (VEG-01A) and OSD-269 (VEG-03A) are ISS-grown red romaine '
              'lettuce microbiome studies and are the only crop-microbiome candidates in the repository.',
 'transformation': 'host chloroplast and mitochondrial reads removed, aggregated to genus, CLR-transformed '
                   'for ordination',
 'studies': [{'study': 'OSD-267',
              'mission': 'VEG-01A',
              'samples': 11,
              'generaAfterHostRemoval': 66,
              'reads': 743434,
              'generaUsedLeaf': 10,
              'leafDesign': {'ground': 5, 'flight': 2},
              'leafCompositionTest': {'observedDistance': 2.3914449949717866,
                                      'nPermutations': 5000,
                                      'nullMean': 3.2588843706978987,
                                      'nullP95': 4.481746712815741,
                                      'pValue': 0.9038192361527695,
                                      'correction': 'finite-sample corrected: (1 + #{null >= observed}) / (1 '
                                                    '+ B)'},
              'leafTopGeneraByClass': {'flight': ['unclassified_nan 0.584', 'Acinetobacter 0.227',
                                                  'Ralstonia 0.060', 'Corynebacterium 0.037',
                                                  'Pseudomonas 0.031', 'Cloacibacterium 0.022'],
                                       'ground': ['unclassified_nan 0.717', 'Acinetobacter 0.114',
                                                  'Cloacibacterium 0.032', 'Pseudomonas 0.030',
                                                  'Ralstonia 0.029', 'Corynebacterium 0.028']},
              'rootDesign': {'flight': 2, 'ground': 2},
              'verdict': 'descriptive-only-not-a-prediction-model',
              'whyNotModelled': ["Leaf samples per class are {'ground': 5, 'flight': 2}: one class has too "
                                 'few independent plants to train on.',
                                 'Each plant contributes leaf and root samples, so those are repeated '
                                 'measures rather than independent observations.',
                                 'Pooling VEG-01A and VEG-03A would confound mission with condition.',
                                 'Abundance is compositional and is never converted to CFU or absolute '
                                 'counts.']},
             {'study': 'OSD-269',
              'mission': 'VEG-03A',
              'samples': 15,
              'generaAfterHostRemoval': 97,
              'reads': 304235,
              'generaUsedLeaf': 3,
              'leafDesign': {'flight': 6, 'ground': 5},
              'leafCompositionTest': {'observedDistance': 0.6896244022678926,
                                      'nPermutations': 5000,
                                      'nullMean': 1.2559666021161495,
                                      'nullP95': 2.4993350395411427,
                                      'pValue': 0.7944411117776444,
                                      'correction': 'finite-sample corrected: (1 + #{null >= observed}) / (1 '
                                                    '+ B)'},
              'leafTopGeneraByClass': {'flight': ['unclassified_nan 0.782', 'Ralstonia 0.139',
                                                  'Cloacibacterium 0.079'],
                                       'ground': ['unclassified_nan 0.830', 'Ralstonia 0.116',
                                                  'Cloacibacterium 0.054']},
              'rootDesign': {'flight': 2, 'ground': 2},
              'verdict': 'descriptive-only-not-a-prediction-model',
              'whyNotModelled': ["Leaf samples per class are {'flight': 6, 'ground': 5}: one class has too "
                                 'few independent plants to train on.',
                                 'Each plant contributes leaf and root samples, so those are repeated '
                                 'measures rather than independent observations.',
                                 'Pooling VEG-01A and VEG-03A would confound mission with condition.',
                                 'Abundance is compositional and is never converted to CFU or absolute '
                                 'counts.']}],
 'registration': 'Not registered. A descriptive compositional result is not a predictor, and Phase 9 does '
                 'not ship a model that cannot be validated on held-out biological units.',
 'cannotSay': ['No absolute abundance, CFU count or total microbial load follows from this.',
               'No food-safety verdict follows from this.',
               'No yield or biomass consequence follows from this.',
               'This is not a partial-gravity or Mars-gravity result; the comparison is ISS flight versus '
               'ground control.']}
