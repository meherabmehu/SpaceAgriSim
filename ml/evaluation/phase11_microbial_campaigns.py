"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'phase': 11,
 'samples': 292,
 'campaigns': ['VEG04A', 'VEG04B'],
 'tissues': ['leaf', 'root', 'soil', 'wick'],
 'assays': ['aerobic', 'yeast_mould'],
 'target': 'log10CfuPerG',
 'S1_headlineReproduction': {'protocol': 'aerobic plate counts on leaf tissue, the Phase 7 subset',
                             'campaigns': {'VEG04A': {'flightMean': 5.61662668086303,
                                                      'flightN': 5,
                                                      'groundMean': 2.5539849355814583,
                                                      'groundN': 15,
                                                      'difference': 3.0626,
                                                      'phase7Committed': 3.0626,
                                                      'reproduced': True,
                                                      'bootstrap': {'flightUnits': 5,
                                                                    'groundUnits': 7,
                                                                    'ci95': [2.32, 3.828],
                                                                    'bootstrapResamples': 4000,
                                                                    'method': 'cluster bootstrap over '
                                                                              'independent units within '
                                                                              'campaign'}},
                                           'VEG04B': {'flightMean': 3.6146518797314253,
                                                      'flightN': 31,
                                                      'groundMean': 0.9754322703681536,
                                                      'groundN': 72,
                                                      'difference': 2.6392,
                                                      'phase7Committed': 2.6392,
                                                      'reproduced': True,
                                                      'bootstrap': {'flightUnits': 11,
                                                                    'groundUnits': 12,
                                                                    'ci95': [1.942, 3.246],
                                                                    'bootstrapResamples': 4000,
                                                                    'method': 'cluster bootstrap over '
                                                                              'independent units within '
                                                                              'campaign'}}}},
 'S2_strata': {'protocol': 'flight minus ground mean log10 CFU/g in each campaign x tissue x assay stratum, '
                           'with cluster bootstrap intervals',
               'strata': {'VEG04A|leaf|aerobic': {'flightMean': 5.61662668086303,
                                                  'flightN': 5,
                                                  'groundMean': 2.5539849355814583,
                                                  'groundN': 15,
                                                  'difference': 3.063,
                                                  'bootstrap': {'flightUnits': 5,
                                                                'groundUnits': 7,
                                                                'ci95': [2.32, 3.828],
                                                                'bootstrapResamples': 4000,
                                                                'method': 'cluster bootstrap over '
                                                                          'independent units within '
                                                                          'campaign'}},
                          'VEG04A|leaf|yeast_mould': {'flightMean': 4.184882474955072,
                                                      'flightN': 5,
                                                      'groundMean': 1.9431239801864848,
                                                      'groundN': 15,
                                                      'difference': 2.242,
                                                      'bootstrap': {'flightUnits': 5,
                                                                    'groundUnits': 7,
                                                                    'ci95': [1.344, 2.957],
                                                                    'bootstrapResamples': 4000,
                                                                    'method': 'cluster bootstrap over '
                                                                              'independent units within '
                                                                              'campaign'}},
                          'VEG04A|root|aerobic': {'flightMean': 7.296699405865185,
                                                  'flightN': 2,
                                                  'groundMean': 7.419593109297805,
                                                  'groundN': 4,
                                                  'difference': -0.123,
                                                  'bootstrap': {'flightUnits': 2,
                                                                'groundUnits': 4,
                                                                'ci95': [-0.28, 0.024],
                                                                'bootstrapResamples': 4000,
                                                                'method': 'cluster bootstrap over '
                                                                          'independent units within '
                                                                          'campaign'}},
                          'VEG04A|root|yeast_mould': {'flightMean': 4.730308415456349,
                                                      'flightN': 4,
                                                      'groundMean': 3.9744863828754515,
                                                      'groundN': 4,
                                                      'difference': 0.756,
                                                      'bootstrap': {'flightUnits': 4,
                                                                    'groundUnits': 4,
                                                                    'ci95': [0.088, 1.42],
                                                                    'bootstrapResamples': 4000,
                                                                    'method': 'cluster bootstrap over '
                                                                              'independent units within '
                                                                              'campaign'}},
                          'VEG04A|soil|aerobic': {'flightMean': 7.077207845678091,
                                                  'flightN': 16,
                                                  'groundMean': 6.923172742789063,
                                                  'groundN': 12,
                                                  'difference': 0.154,
                                                  'bootstrap': {'flightUnits': 4,
                                                                'groundUnits': 4,
                                                                'ci95': [-0.183, 0.47],
                                                                'bootstrapResamples': 4000,
                                                                'method': 'cluster bootstrap over '
                                                                          'independent units within '
                                                                          'campaign'}},
                          'VEG04A|soil|yeast_mould': {'flightMean': 4.658107728941352,
                                                      'flightN': 12,
                                                      'groundMean': 4.262988669767789,
                                                      'groundN': 12,
                                                      'difference': 0.395,
                                                      'bootstrap': {'flightUnits': 4,
                                                                    'groundUnits': 4,
                                                                    'ci95': [-0.095, 0.887],
                                                                    'bootstrapResamples': 4000,
                                                                    'method': 'cluster bootstrap over '
                                                                              'independent units within '
                                                                              'campaign'}},
                          'VEG04A|wick|aerobic': {'flightMean': 8.156817967948278,
                                                  'flightN': 2,
                                                  'groundMean': 7.6041123329499225,
                                                  'groundN': 4,
                                                  'difference': 0.553,
                                                  'bootstrap': {'flightUnits': 2,
                                                                'groundUnits': 4,
                                                                'ci95': [-0.054, 1.148],
                                                                'bootstrapResamples': 4000,
                                                                'method': 'cluster bootstrap over '
                                                                          'independent units within '
                                                                          'campaign'}},
                          'VEG04A|wick|yeast_mould': {'flightMean': 6.460345267892542,
                                                      'flightN': 4,
                                                      'groundMean': 4.098913902920678,
                                                      'groundN': 4,
                                                      'difference': 2.361,
                                                      'bootstrap': {'flightUnits': 4,
                                                                    'groundUnits': 4,
                                                                    'ci95': [1.648, 3.189],
                                                                    'bootstrapResamples': 4000,
                                                                    'method': 'cluster bootstrap over '
                                                                              'independent units within '
                                                                              'campaign'}},
                          'VEG04B|leaf|aerobic': {'flightMean': 3.6146518797314253,
                                                  'flightN': 31,
                                                  'groundMean': 0.9754322703681536,
                                                  'groundN': 72,
                                                  'difference': 2.639,
                                                  'bootstrap': {'flightUnits': 11,
                                                                'groundUnits': 12,
                                                                'ci95': [1.942, 3.246],
                                                                'bootstrapResamples': 4000,
                                                                'method': 'cluster bootstrap over '
                                                                          'independent units within '
                                                                          'campaign'}},
                          'VEG04B|leaf|yeast_mould': {'flightMean': 2.034622658564433,
                                                      'flightN': 21,
                                                      'groundMean': 0.0641970087247678,
                                                      'groundN': 48,
                                                      'difference': 1.97,
                                                      'bootstrap': {'flightUnits': 11,
                                                                    'groundUnits': 12,
                                                                    'ci95': [1.59, 2.336],
                                                                    'bootstrapResamples': 4000,
                                                                    'method': 'cluster bootstrap over '
                                                                              'independent units within '
                                                                              'campaign'}}},
               'strataPositiveAndSignificant': 6,
               'strataTotal': 10},
 'S3_compositionStandardised': {'protocol': 'contrast recomputed with the tissue/assay mix held at the other '
                                            "campaign's weights, so a shift in composition cannot masquerade "
                                            'as a shift in effect',
                                'composition': {'VEG04A': {'leaf|aerobic': 0.167,
                                                           'leaf|yeast_mould': 0.167,
                                                           'root|aerobic': 0.05,
                                                           'root|yeast_mould': 0.067,
                                                           'soil|aerobic': 0.233,
                                                           'soil|yeast_mould': 0.2,
                                                           'wick|aerobic': 0.05,
                                                           'wick|yeast_mould': 0.067},
                                                'VEG04B': {'leaf|aerobic': 0.599, 'leaf|yeast_mould': 0.401}},
                                'VEG04B_at_VEG04A_mix': 2.305,
                                'VEG04A_at_VEG04B_mix': 2.733,
                                'strataUsedForB': ['leaf|aerobic', 'leaf|yeast_mould'],
                                'strataUsedForA': ['leaf|aerobic', 'leaf|yeast_mould'],
                                'rawVEG04A_allTissues': 1.675,
                                'rawVEG04B_allTissues': 2.366,
                                'statement': 'how much of the campaign-to-campaign difference in the pooled '
                                             'contrast is the sampling mix rather than the effect',
                                'limitation': 'VEG-04B contributes leaf tissue only, so standardising it '
                                              "onto VEG-04A's mix reaches only the two shared leaf strata "
                                              'and the root, soil and wick strata cannot be compared at all. '
                                              'The conclusion is therefore about the shared strata, not '
                                              'about the whole table.'},
 'S4_randomEffects': {'studies': 2,
                      'pooledEffect': 2.82,
                      'ci95': [2.327, 3.314],
                      'tau2': 0.0,
                      'i2Percent': 0.0,
                      'cochranQ': 0.693,
                      'predictionInterval95': [-0.377, 6.018],
                      'note': 'a prediction interval for a new campaign, not a confidence interval on the '
                              'mean. With two campaigns tau2 is weakly identified, so the interval should be '
                              'read as wide and provisional.',
                      'inputEffects': {'VEG04A': 3.0626, 'VEG04B': 2.6392},
                      'inputCi95': {'VEG04A': [2.32, 3.828], 'VEG04B': [1.942, 3.246]}},
 'S5_thirdCampaign': {'available': False,
                      'evidence': 'the 231-study discovery sweep found nine uncatalogued microbial '
                                  'candidates, none of them a NASA crop-microbial load campaign: OSD-385/386 '
                                  'are deliberate E. coli and Salmonella challenge studies on lettuce and '
                                  'mizuna, and OSD-146/170/280 are mouse faecal, aircraft bioaerosol and '
                                  'astronaut salivary microbiomes',
                      'candidatesReviewed': [],
                      'consequence': 'the random-effects estimate rests on two campaigns and the prediction '
                                     'interval is the only defensible statement about a third one'},
 'claims': {'permitted': ['the flight-versus-ground contrast in culturable aerobic load replicates in sign '
                          'and approximate size across both VEG-04 campaigns',
                          "a new campaign's contrast is expected inside the prediction interval",
                          'the direction of the effect is stable across tissue and assay strata'],
            'refused': ["any prediction of a named third campaign's absolute load",
                        "any absolute-load prediction without that campaign's own baseline samples",
                        'any gravity attribution: flight and ground differ in cabin environment, payload '
                        'handling and sampling protocol as well as gravity']},
 'registryChange': None,
 'verdict': 'flight-effect-replicates-across-both-campaigns-after-composition-standardisation'}
