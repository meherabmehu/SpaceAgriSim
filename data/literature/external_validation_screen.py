"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'schema': 'spaceagrisim.external_validation_screen/1',
 'purpose': 'Decide whether the served lettuce model can be validated against a source it was not trained '
            'on. Each candidate is recorded with what it actually publishes, what the model would need, and '
            'a verdict. Nothing here is used to fit or tune anything.',
 'requirement': {'inputs': ['daysAfterTransplant', 'airTemperature', 'rootTemperature', 'ppfd'],
                 'target': 'freshShootMassG per plant',
                 'domain': {'daysAfterTransplant': [2.0, 29.0],
                            'airTemperature': [20.0, 32.0],
                            'rootTemperature': [20.0, 32.0],
                            'ppfd': [200.0, 750.0]},
                 'note': 'A candidate must report all four inputs per observation, not study averages, or '
                         'the comparison would mix one PPFD with a yield averaged over several PPFDs.'},
 'trainingSource': {'id': 'WUR-lettuce',
                    'title': 'Plant Factories Are Heating Up: lettuce growth dataset',
                    'doi': '10.4121/5a7472f0-8a67-4ec0-84c9-9d032990d654.v1',
                    'reason': 'This is the dataset the model was trained on (1,648 observations over 4 '
                              'experiments). It cannot also be the external validation.'},
 'candidates': [{'id': 'peerj-17085',
                 'title': 'Vertical farming for lettuce production in limited space: a case study in '
                          'Northern Thailand',
                 'authors': 'Wicharuck, Khongdee, Man, Syahputra, Yalangkan, Chaiphak, Chaichana',
                 'publication': 'PeerJ 12:e17085, 2024',
                 'doi': '10.7717/peerj.17085',
                 'license': 'CC BY 4.0',
                 'dataAvailability': 'Raw data supplied as Supplemental File (supp-1).',
                 'reported': {'cultivars': ['Baby Cos', 'Green Oak'],
                              'daysAfterTransplant': 28,
                              'airTemperatureC': 27.5,
                              'relativeHumidityPct': 62,
                              'ppfdUmol': [322, 391, 697],
                              'photoperiodHours': 12,
                              'plantDensityPerM2': 16,
                              'freshWeightPerPlantG': {'Baby Cos': 100,
                                                       'Green Oak': 164,
                                                       'studyAverage': 132}},
                 'verdict': 'used-external-check-failed',
                 'reason': 'The per-level table was transcribed verbatim (see '
                           'external_lettuce_peerj17085.py) and the model was scored against all six '
                           'observations. It overpredicts every one, by 1.7x to 5.4x. The study is now spent '
                           'as a validation source: it has been used, and the model failed it.',
                 'blocking': '',
                 'blockingNote': 'None. Transcription complete; the check runs live in GET '
                                 '/api/external-validation.',
                 'transcription': {'file': 'data/literature/external_lettuce_peerj17085.py',
                                   'observations': 6,
                                   'sourceTable': 'Table 1 (fresh yield at 28 DAT) and Results text '
                                                  '(PPFD/DLI per level)',
                                   'sourceSha256': '69f082439d17f95eef052de4dc3354f9e43cf6e9791f31556973ac9e9a9d27bb'}},
                {'id': 'touliatos-2016',
                 'title': 'Vertical farming increases lettuce yield per unit area compared to conventional '
                          'horizontal hydroponics',
                 'authors': 'Touliatos, Dodd, McAinsh',
                 'publication': 'Food and Energy Security 5(3):184-191, 2016',
                 'doi': '10.1002/fes3.83',
                 'license': 'open access (Wiley, CC BY)',
                 'dataAvailability': 'Open Science Framework, doi 10.17605/OSF.IO/MRVXG',
                 'reported': {'shootFreshWeightG': {'horizontalHydroponics': '138 +/- 6 (mean +/- SE, n=40)',
                                                    'verticalFarm': '95 +/- 6'},
                              'ppfdUmol': {'horizontalHydroponics': [340, 570], 'verticalFarm': [134, 491]},
                              'airTemperatureC': [16, 18],
                              'photoperiodHours': 16},
                 'verdict': 'out-of-domain',
                 'reason': "Air temperature 16-18 C sits below the model's declared 20-32 C applicability "
                           'domain, and a mother-and-daughter per-day observation series with root-zone '
                           'temperature is not published in the accessible text. The model must decline this '
                           'source rather than extrapolate into it.',
                 'blocking': 'Below the declared domain; harvest day and root-zone temperature also not '
                             'reported in the accessible text.'},
                {'id': 'ntrs-20160006559',
                 'title': 'Comparative Study of Lettuce and Radish Grown Under Red and Blue LEDs and White '
                          'Fluorescent Lamps',
                 'authors': 'Mickens, Massa, Newsham, Wheeler, Birmele',
                 'publication': 'NASA Kennedy Space Center poster, 2016',
                 'ntrsId': '20160006559',
                 'license': 'NASA public domain',
                 'reported': {'note': 'Equal-PPF comparison of red+blue LED against white fluorescent for '
                                      "lettuce and radish, with n and SD printed on the poster's Table 1."},
                 'verdict': 'not-usable',
                 'reason': 'The measurement table is an image on a one-page poster, not machine-readable '
                           'text, and the design varies light spectrum at fixed PPFD. The served lettuce '
                           'model has no spectrum input, so even a perfect transcription would test an input '
                           'the model does not accept.',
                 'blocking': 'No spectrum input in the model; table not machine-readable.'}],
 'conclusion': {'externalValidationAvailable': True,
                'externalValidationPassed': False,
                'statement': 'An external check was run against one independent study it was not trained on. '
                             'The model overpredicts mature fresh weight by a median of 3.2x, and by 1.7x to '
                             '5.4x across six observations. It fails the check.',
                'whatThisDoesNotMean': "It does not mean the model's internal cross-validation was wrong: "
                                       'that number measures interpolation within four experiments by one '
                                       'group. It means those four experiments do not transfer to a '
                                       'greenhouse trial in another country, at a different density, under '
                                       'sunlight.',
                'consequence': 'The model stays exploratory and must not be used to forecast harvest weight, '
                               'size a farm, or compare cropping systems.'}}
