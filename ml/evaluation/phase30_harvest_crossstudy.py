"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'schema': 'spaceagrisim.phase30_harvest_crossstudy/1',
 'generatedAt': '2026-11-10T17:29:22.611385+00:00',
 'purpose': 'measure lettuce harvest-model generalisation across genuinely independent studies, which the '
            'four-experiment training set could not do',
 'dataset': {'id': 'lettuce-multistudy-lue',
             'doi': '10.5281/zenodo.14640245',
             'license': 'CC BY 4.0',
             'file': 'data/processed/phase30/lettuce_multistudy.csv',
             'observationKind': 'published-treatment-mean',
             'rowsUsed': 47,
             'studiesUsed': 35,
             'target': 'shoot dry mass per plant (g), as published',
             'exclusions': {'missing core feature after the daily-light-integral derivation': 5,
                            'published dry mass of zero (cannot enter a log target)': 1},
             'imputedDefaults': {'co2Ppm': 420.0,
                                 'photoperiodHours': 16.0,
                                 'why': 'a study that did not report CO2 or photoperiod cannot drop out of a '
                                        'cross-study comparison without biasing it toward the studies that '
                                        'reported everything. A single declared default is applied and the '
                                        'affected count is reported; no value is fitted or drawn from the '
                                        'target.',
                                 'affectedRows': {'co2Ppm': 0, 'photoperiodHours': 1}}},
 'protocol': {'split': 'leave-one-study-out over the development studies',
              'groupingKey': 'study',
              'targetTransform': 'log10(shoot dry mass g per plant)',
              'features': ['co2Ppm', 'photoperiodHours', 'ppfdUmolPerM2S', 'dailyLightIntegralMolPerM2Day',
                           'plantDensityPerM2', 'plantAgeDays'],
              'featureUnits': {'co2Ppm': 'ppm',
                               'photoperiodHours': 'h/day',
                               'ppfdUmolPerM2S': 'umol/m2/s',
                               'dailyLightIntegralMolPerM2Day': 'mol/m2/day',
                               'plantDensityPerM2': 'plant/m2',
                               'plantAgeDays': 'day'},
              'holdoutStudies': ['Carotti', 'Hytönen', 'Kook', 'Nguyen', 'Saengtharatip', 'Tosti',
                                 'Voutsinos', 'Wang'],
              'holdoutUsedForSelection': False,
              'holdoutSelectionMethod': 'SHA-256 of the study key, eight lowest',
              'selectionRule': 'lowest out-of-fold MAE; within 2 % prefer the structurally simpler model '
                               '(light-limited, ridge, baseline over gbm)',
              'candidateOrder': ['baseline-mean', 'light-limited-structure', 'ridge-log', 'gbm-log'],
              'selectionRuleWrittenBeforeScoring': True,
              'acceptanceCriterionPct': 30.0,
              'criterionSource': 'unchanged project criterion, not set by this phase',
              'seed': 20261110,
              'noRandomSplit': 'a random split across treatment means would put sibling treatments of one '
                               'study on both sides; it is not used and its result is not reported'},
 'candidates': {'baseline-mean': {'n': 39,
                                  'MAEgPerPlant': 1.9834,
                                  'RMSEgPerPlant': 2.8947,
                                  'MAPE': 211.423,
                                  'medianAPE': 40.628,
                                  'meanBiasErrorGPerPlant': -1.1475,
                                  'R2': -0.2395,
                                  'spearman': -0.797},
                'light-limited-structure': {'n': 39,
                                            'MAEgPerPlant': 1.9723,
                                            'RMSEgPerPlant': 2.9013,
                                            'MAPE': 223.584,
                                            'medianAPE': 40.328,
                                            'meanBiasErrorGPerPlant': -1.1582,
                                            'R2': -0.2452,
                                            'spearman': -0.1481},
                'ridge-log': {'n': 39,
                              'MAEgPerPlant': 2.2763,
                              'RMSEgPerPlant': 4.5162,
                              'MAPE': 98.743,
                              'medianAPE': 43.016,
                              'meanBiasErrorGPerPlant': 0.0435,
                              'R2': -2.0171,
                              'spearman': 0.3821},
                'gbm-log': {'n': 39,
                            'MAEgPerPlant': 2.2088,
                            'RMSEgPerPlant': 2.8235,
                            'MAPE': 123.867,
                            'medianAPE': 61.59,
                            'meanBiasErrorGPerPlant': -0.4942,
                            'R2': -0.1793,
                            'spearman': 0.2262}},
 'selected': 'baseline-mean',
 'selectedOutOfFold': {'n': 39,
                       'MAEgPerPlant': 1.9834,
                       'RMSEgPerPlant': 2.8947,
                       'MAPE': 211.423,
                       'medianAPE': 40.628,
                       'meanBiasErrorGPerPlant': -1.1475,
                       'R2': -0.2395,
                       'spearman': -0.797},
 'interval': {'method': 'split conformal on out-of-fold log10 residuals, 90 % two-sided',
              'logLow': -0.8936,
              'logHigh': 0.5701,
              'multiplicativeWidth': 29.0892,
              'nResiduals': 39,
              'coverageNote': 'an in-sample coverage figure from the same residuals the interval was built '
                              'on; descriptive, not a guarantee for a new study'},
 'holdout': {'studies': 8,
             'treatments': 8,
             'records': [{'studyKey': 'Carotti',
                          'citation': 'Carotti, L., Graamans, L., Puksic, F., Butturini, M., Meinen, E., '
                                      'Heuvelink, E., & Stanghellini, C. (2021). Plant Factories Are Heating '
                                      'Up: Hunting for the Best Combination of Light Intensity, Air '
                                      'Temperature and Root-Zone Temperature in Lettuce Production. '
                                      'Frontiers in Plant Science, 11(January). '
                                      'https://doi.org/10.3389/fpls.2020.592171',
                          'measuredGPerPlant': 16.5,
                          'predictedGPerPlant': 2.2263,
                          'apePct': 86.51},
                         {'studyKey': 'Hytönen',
                          'citation': 'Hytönen, T., Pinho, P., Rantanen, M., Kariluoto, S., Lampi, A., '
                                      'Edelmann, M., Joensuu, K., Kauste, K., Mouhu, K., Piironen, V., '
                                      'Halonen, L., & Elomaa, P. (2018). Effects of LED light spectra on '
                                      'lettuce growth and nutritional composition. Lighting Research and '
                                      'Technology, 50(6), 880–893. https://doi.org/10.1177/1477153517701300',
                          'measuredGPerPlant': 4.7,
                          'predictedGPerPlant': 2.2263,
                          'apePct': 52.63},
                         {'studyKey': 'Kook',
                          'citation': 'Kook, H. S., Park, S. H., Jang, Y. J., Lee, G. W., Kim, J. S., Kim, '
                                      'H. M., Oh, B. T., Chae, J. C., & Lee, K. J. (2013). Blue LED '
                                      '(light-emitting diodes)-mediated growth promotion and control of '
                                      'Botrytis disease in lettuce. Acta Agriculturae Scandinavica Section '
                                      'B: Soil and Plant Science, 63(3), 271–277. '
                                      'https://doi.org/10.1080/09064710.2012.756118',
                          'measuredGPerPlant': 0.2,
                          'predictedGPerPlant': 2.2263,
                          'apePct': 1013.16},
                         {'studyKey': 'Nguyen',
                          'citation': 'Nguyen, T. K. L., Cho, K. M., Lee, H. Y., Cho, D. Y., Lee, G. O., '
                                      'Jang, S. N., Lee, Y., Kim, D., & Son, K.-H. (2021). Effects of White '
                                      'LED Lighting with Specific Shorter Blue and/or Green Wavelength on '
                                      'the Growth and Quality of Two Lettuce Cultivars in a Vertical Farming '
                                      'System. Agronomy, 11(11), 2111. '
                                      'https://doi.org/10.3390/agronomy11112111',
                          'measuredGPerPlant': 1.1,
                          'predictedGPerPlant': 2.2263,
                          'apePct': 102.39},
                         {'studyKey': 'Saengtharatip',
                          'citation': 'Saengtharatip, S., Joshi, J., Zhang, G., Takagaki, M., Kozai, T., & '
                                      'Yamori, W. (2021). Optimal light wavelength for a novel cultivation '
                                      'system with a supplemental upward lighting in plant factory with '
                                      'artificial lighting. Environmental Control in Biology, 59(1), 21–27. '
                                      'https://doi.org/10.2525/ECB.59.21',
                          'measuredGPerPlant': 12.7,
                          'predictedGPerPlant': 2.2263,
                          'apePct': 82.47},
                         {'studyKey': 'Tosti',
                          'citation': 'Tosti, G., Benincasa, P., Cortona, R., Falcinelli, B., Farneselli, '
                                      'M., Guiducci, M., Onofri, A., Pannacci, E., Tei, F., & Giulietti, M. '
                                      '(2018). Growing lettuce under multispectral light-emitting diodes '
                                      'lamps with adjustable light intensity. Italian Journal of Agronomy, '
                                      '13(1), 57–62. https://doi.org/10.4081/ija.2017.883',
                          'measuredGPerPlant': 0.2,
                          'predictedGPerPlant': 2.2263,
                          'apePct': 1013.16},
                         {'studyKey': 'Voutsinos',
                          'citation': 'Voutsinos, O., Mastoraki, M., Ntatsi, G., Liakopoulos, G., & Savvas, '
                                      'D. (2021). Comparative assessment of hydroponic lettuce production '
                                      'either under artificial lighting, or in a mediterranean greenhouse '
                                      'during wintertime. Agriculture (Switzerland), 11(6). '
                                      'https://doi.org/10.3390/agriculture11060503',
                          'measuredGPerPlant': 8.8,
                          'predictedGPerPlant': 2.2263,
                          'apePct': 74.7},
                         {'studyKey': 'Wang',
                          'citation': 'Wang, J., Tong, Y., Yang, Q., & Xin, M. (2016). Performance of '
                                      'introducing outdoor cold air for cooling a plant production system '
                                      'with artificial light. Frontiers in Plant Science, 7(MAR2016), 1–10. '
                                      'https://doi.org/10.3389/fpls.2016.00270',
                          'measuredGPerPlant': 5.1,
                          'predictedGPerPlant': 2.2263,
                          'apePct': 56.35}],
             'metrics': {'n': 8,
                         'MAEgPerPlant': 5.2309,
                         'RMSEgPerPlant': 6.8966,
                         'MAPE': 310.17,
                         'medianAPE': 84.489,
                         'meanBiasErrorGPerPlant': -3.9362,
                         'R2': -0.4831,
                         'spearman': None},
             'medianStudyAPE': 84.489,
             'acceptanceCriterionPct': 30.0,
             'passed': False},
 'promoted': False,
 'promotionBlockedBy': ['the holdout error is more than five times the criterion',
                        'the fitted interval spans a factor of 29.1',
                        'the corpus is published treatment means, so within-study variance is unknown'],
 'limitations': ['Published treatment means: one row is a mean another author reported, so the residual mix '
                 'inside a study is invisible and a weighted fit is impossible.',
                 'Study-level choices (cultivar, substrate, harvest definition, dry versus fresh basis) move '
                 'yield by more than the environment the model sees.',
                 'The holdout is eight studies; one unusual study moves the metric a long way.',
                 'No extrapolation to a cultivar, a facility or a light regime outside these studies.'],
 'priorHoldoutInspection': 'no study in this table was inspected before the sealed holdout was chosen; the '
                           'split was fixed by SHA-256 and scored once.'}
