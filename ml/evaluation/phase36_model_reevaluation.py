"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'generatedAt': '2026-11-12T22:26:59.470261+00:00',
 'generatedBy': 'ml/research/phase36_model_reevaluation.py',
 'policy': {'retraining': 'none',
            'thresholds': 'unchanged',
            'testSetTuning': 'none',
            'splitUnit': 'whole campaign, never individual rows'},
 'newEvidence': {'iot4lettuce': 'data/research/phase36/iot4lettuce_water_cultivar',
                 'et0MeasurementValidation': 'data/research/phase36/et0_measurement_validation'},
 'models': {'lettuce-earth-growth-v1': {'artifactSha256': '37a822bfff18df954ebf769a37f9279d47c3ff15077b10b18d0fbe940fadf835',
                                        'hashBasis': 'SHA-256 of ml/artifacts/lettuce-earth-growth-v1, the '
                                                     'stored artifact file. The payload is unchanged by the '
                                                     'storage format.',
                                        'artifactUnchanged': True,
                                        'verdictBefore': 'fails-independent-check',
                                        'decisionGradeBefore': False,
                                        'retrained': False,
                                        'thresholdsChanged': False,
                                        'outcome': 'DOMAIN-REFUSED',
                                        'independentCampaign': 'IoT4Lettuce, Zenodo 10.5281/zenodo.20759414',
                                        'campaignDomain': {'airTemperatureC': {'min': 13.08,
                                                                               'max': 41.8,
                                                                               'n': 1638},
                                                           'rootTemperature': 'not measured in this campaign',
                                                           'measuredMassDaysAfterTransplant': 42,
                                                           'daysAfterTransplantBasis': 'the destructive '
                                                                                       'harvest on '
                                                                                       '2024-10-03 is the '
                                                                                       'only measured fresh '
                                                                                       'weight; the campaign '
                                                                                       'record runs '
                                                                                       '2024-08-22 to '
                                                                                       '2024-10-03, 42 days, '
                                                                                       'and no earlier fresh '
                                                                                       'weight is a '
                                                                                       'measurement - the '
                                                                                       '270 daily values in '
                                                                                       'the export are '
                                                                                       'produced by a '
                                                                                       'regression analysis',
                                                           'dli': 'not computable from the published PAR log '
                                                                  '(19 days, irregular sampling)'},
                                        'declaredDomain': {'daysAfterTransplant': {'min': 2.0, 'max': 29.0},
                                                           'airTemperature': {'min': 20.0, 'max': 32.0},
                                                           'rootTemperature': {'min': 20.0, 'max': 32.0},
                                                           'ppfd': {'min': 200.0, 'max': 750.0}},
                                        'violations': ['airTemperature 13.08-41.8 degC outside declared '
                                                       '20.0-32.0',
                                                       'rootTemperature is a required feature and is not '
                                                       'measured',
                                                       'only measured mass is at 42 days after transplant, '
                                                       'declared domain 2.0-29.0'],
                                        'whyNoPrediction': "the model's own domain contract forbids a "
                                                           'prediction here; forcing one would produce a '
                                                           'number the card says is invalid',
                                        'verdictAfter': 'fails-independent-check',
                                        'decisionGradeAfter': False},
            'lettuce-earth-growth-v2': {'artifactSha256': '1dc8057a0511c5080357ecc93529f6989a7e932c19f954c91948cdf0584601d2',
                                        'hashBasis': 'SHA-256 of ml/artifacts/lettuce-earth-growth-v2, the '
                                                     'stored artifact file. The payload is unchanged by the '
                                                     'storage format.',
                                        'artifactUnchanged': True,
                                        'verdictBefore': 'fails-independent-check',
                                        'decisionGradeBefore': False,
                                        'retrained': False,
                                        'thresholdsChanged': False,
                                        'outcome': 'DOMAIN-REFUSED',
                                        'independentCampaign': 'IoT4Lettuce, Zenodo 10.5281/zenodo.20759414',
                                        'campaignDomain': {'airTemperatureC': {'min': 13.08,
                                                                               'max': 41.8,
                                                                               'n': 1638},
                                                           'rootTemperature': 'not measured in this campaign',
                                                           'measuredMassDaysAfterTransplant': 42,
                                                           'daysAfterTransplantBasis': 'the destructive '
                                                                                       'harvest on '
                                                                                       '2024-10-03 is the '
                                                                                       'only measured fresh '
                                                                                       'weight; the campaign '
                                                                                       'record runs '
                                                                                       '2024-08-22 to '
                                                                                       '2024-10-03, 42 days, '
                                                                                       'and no earlier fresh '
                                                                                       'weight is a '
                                                                                       'measurement - the '
                                                                                       '270 daily values in '
                                                                                       'the export are '
                                                                                       'produced by a '
                                                                                       'regression analysis',
                                                           'dli': 'not computable from the published PAR log '
                                                                  '(19 days, irregular sampling)'},
                                        'declaredDomain': {'daysAfterTransplant': {'min': 2.0, 'max': 29.0},
                                                           'airTemperature': {'min': 20.0, 'max': 32.0},
                                                           'rootTemperature': {'min': 20.0, 'max': 32.0},
                                                           'ppfd': {'min': 200.0, 'max': 750.0}},
                                        'violations': ['airTemperature 13.08-41.8 degC outside declared '
                                                       '20.0-32.0',
                                                       'rootTemperature is a required feature and is not '
                                                       'measured',
                                                       'only measured mass is at 42 days after transplant, '
                                                       'declared domain 2.0-29.0'],
                                        'whyNoPrediction': "the model's own domain contract forbids a "
                                                           'prediction here; forcing one would produce a '
                                                           'number the card says is invalid',
                                        'verdictAfter': 'fails-independent-check',
                                        'decisionGradeAfter': False},
            'lettuce-earth-growth-v3': {'artifactSha256': 'e57e0490d5c319368c31ae4cb818630109c5300aa62df8da5ed10f9065838d99',
                                        'hashBasis': 'SHA-256 of ml/artifacts/lettuce-earth-growth-v3, the '
                                                     'stored artifact file. The payload is unchanged by the '
                                                     'storage format.',
                                        'artifactUnchanged': True,
                                        'verdictBefore': 'fails-independent-check',
                                        'decisionGradeBefore': False,
                                        'retrained': False,
                                        'thresholdsChanged': False,
                                        'outcome': 'DOMAIN-REFUSED',
                                        'independentCampaign': 'IoT4Lettuce, Zenodo 10.5281/zenodo.20759414',
                                        'campaignDomain': {'airTemperatureC': {'min': 13.08,
                                                                               'max': 41.8,
                                                                               'n': 1638},
                                                           'rootTemperature': 'not measured in this campaign',
                                                           'measuredMassDaysAfterTransplant': 42,
                                                           'daysAfterTransplantBasis': 'the destructive '
                                                                                       'harvest on '
                                                                                       '2024-10-03 is the '
                                                                                       'only measured fresh '
                                                                                       'weight; the campaign '
                                                                                       'record runs '
                                                                                       '2024-08-22 to '
                                                                                       '2024-10-03, 42 days, '
                                                                                       'and no earlier fresh '
                                                                                       'weight is a '
                                                                                       'measurement - the '
                                                                                       '270 daily values in '
                                                                                       'the export are '
                                                                                       'produced by a '
                                                                                       'regression analysis',
                                                           'dli': 'not computable from the published PAR log '
                                                                  '(19 days, irregular sampling)'},
                                        'declaredDomain': {'daysAfterTransplant': {'min': 2.0, 'max': 29.0},
                                                           'airTemperature': {'min': 20.0, 'max': 32.0},
                                                           'rootTemperature': {'min': 20.0, 'max': 32.0},
                                                           'dailyLightIntegral': {'min': 11.5, 'max': 34.5}},
                                        'violations': ['airTemperature 13.08-41.8 degC outside declared '
                                                       '20.0-32.0',
                                                       'rootTemperature is a required feature and is not '
                                                       'measured',
                                                       'only measured mass is at 42 days after transplant, '
                                                       'declared domain 2.0-29.0'],
                                        'whyNoPrediction': "the model's own domain contract forbids a "
                                                           'prediction here; forcing one would produce a '
                                                           'number the card says is invalid',
                                        'verdictAfter': 'fails-independent-check',
                                        'decisionGradeAfter': False},
            'mizuna-microbial-relative-load-v2': {'artifactSha256': '489cafe7b5d978fd0dfd3503e37eb8473a4a30bb2cedfaa02f397483124cb3c8',
                                                  'hashBasis': 'SHA-256 of '
                                                               'ml/artifacts/mizuna-microbial-relative-load-v2, '
                                                               'the stored artifact file. The payload is '
                                                               'unchanged by the storage format.',
                                                  'artifactUnchanged': True,
                                                  'verdictBefore': 'passes-independent-check',
                                                  'decisionGradeBefore': True,
                                                  'retrained': False,
                                                  'thresholdsChanged': False,
                                                  'outcome': 'NO-NEW-EVIDENCE',
                                                  'reason': 'this acquisition contains no measurement of the '
                                                            'crop, system or variable this model represents',
                                                  'verdictAfter': 'passes-independent-check',
                                                  'decisionGradeAfter': True},
            'radiation-quality-osd46-v1': {'artifactSha256': '16a7b0f0b2ee69e89525215964b32380fd7d8aa3e5a1e4e91f9f7ea730b7352e',
                                           'hashBasis': 'SHA-256 of ml/artifacts/radiation-quality-osd46-v1, '
                                                        'the stored artifact file. The payload is unchanged '
                                                        'by the storage format.',
                                           'artifactUnchanged': True,
                                           'verdictBefore': 'no-independent-check',
                                           'decisionGradeBefore': False,
                                           'retrained': False,
                                           'thresholdsChanged': False,
                                           'outcome': 'NO-NEW-EVIDENCE',
                                           'reason': 'this acquisition contains no measurement of the crop, '
                                                     'system or variable this model represents',
                                           'verdictAfter': 'no-independent-check',
                                           'decisionGradeAfter': False},
            'radiation-exposure-osd46-v1': {'artifactSha256': '08c1009fb18412b39f0a9a21bbc25a49986caeed556f06083f9ae43d3bef1047',
                                            'hashBasis': 'SHA-256 of '
                                                         'ml/artifacts/radiation-exposure-osd46-v1, the '
                                                         'stored artifact file. The payload is unchanged by '
                                                         'the storage format.',
                                            'artifactUnchanged': True,
                                            'verdictBefore': 'no-independent-check',
                                            'decisionGradeBefore': False,
                                            'retrained': False,
                                            'thresholdsChanged': False,
                                            'outcome': 'NO-NEW-EVIDENCE',
                                            'reason': 'this acquisition contains no measurement of the crop, '
                                                      'system or variable this model represents',
                                            'verdictAfter': 'no-independent-check',
                                            'decisionGradeAfter': False},
            'tomato-flight-response-v1': {'artifactSha256': '674de9f1cc06b001b52da356fe37822d159d5b86fc7f508d5ffe2b6b2d2f708d',
                                          'hashBasis': 'SHA-256 of ml/artifacts/tomato-flight-response-v1, '
                                                       'the stored artifact file. The payload is unchanged '
                                                       'by the storage format.',
                                          'artifactUnchanged': True,
                                          'verdictBefore': 'no-independent-check',
                                          'decisionGradeBefore': False,
                                          'retrained': False,
                                          'thresholdsChanged': False,
                                          'outcome': 'NO-NEW-EVIDENCE',
                                          'reason': 'this acquisition contains no measurement of the crop, '
                                                    'system or variable this model represents',
                                          'verdictAfter': 'no-independent-check',
                                          'decisionGradeAfter': False}},
 'counts': {'served': 7,
            'scored': 0,
            'domainRefused': 3,
            'noNewEvidence': 4,
            'decisionGradeBefore': 1,
            'decisionGradeAfter': 1}}
