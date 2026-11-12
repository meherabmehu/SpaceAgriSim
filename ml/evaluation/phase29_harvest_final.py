"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'schema': 'spaceagrisim.phase29_harvest_final/1',
 'generatedAt': '2026-11-10T15:40:58.034248+00:00',
 'candidateUnderTest': 'monotone-gbm',
 'whyThisCandidate': 'lowest leave-one-experiment-out MAE in g fresh mass per m2',
 'holdout': {'study': 'Touliatos D, Dodd IC, McAinsh M (2016) Vertical farming increases lettuce yield per '
                      'unit area compared to conventional horizontal hydroponics. Food and Energy Security '
                      '5(3):184-191, doi:10.1002/fes3.83',
             'license': 'publisher open access; values transcribed, not redistributed as data',
             'observations': [{'id': 'hhs-50',
                               'system': 'horizontal hydroponic',
                               'density': 50.0,
                               'measuredG': 138.0,
                               'measuredSeG': 6.0,
                               'n': 40,
                               'predictedG': 192.2,
                               'intervalLowG': 84.0,
                               'intervalHighG': 442.3,
                               'ratio': 1.393,
                               'percentageError': 39.28,
                               'domainViolations': ['daysAfterTransplant=35 outside [2, 29]',
                                                    'airTemperature=17.5 outside [20, 32]',
                                                    'rootTemperature=17.5 outside [20, 32]']}],
             'nObservations': 1,
             'MAPE': 39.28,
             'acceptanceCriterionPct': 30.0,
             'passed': False,
             'interval': {'logLow': -0.8279, 'logHigh': 0.8335, 'coversTheObservation': True},
             'priorResultPhase19_v3': 41.59,
             'changeVsV3PercentagePoints': -2.31},
 'holdoutProvenance': {'usedInFitting': False,
                       'usedInModelSelection': False,
                       'usedInFeatureSelection': False,
                       'timesReadAcrossPhases': ['Phase 19: scored once against v3 (41.6 %).',
                                                 'Phase 28: quoted from the artifact when building the '
                                                 'workflow UI; no new inspection of the observation itself.',
                                                 'Phase 29: read once here, after the candidate was fixed.'],
                       'pristineClaim': 'This is NOT an untouched final test set. Its value has been known '
                                        'since Phase 19, and a one-observation holdout cannot be called '
                                        'untouched in any meaningful statistical sense.'},
 'domainOfTheHoldout': {'violations': ['daysAfterTransplant=35 outside [2, 29]',
                                       'airTemperature=17.5 outside [20, 32]',
                                       'rootTemperature=17.5 outside [20, 32]'],
                        'reading': 'Three of the four inputs lie outside the declared applicability domain, '
                                   'so this is an extrapolation test. A failure here is evidence about '
                                   'transfer beyond the domain, and is not by itself evidence that the model '
                                   'interpolates badly inside it.'},
 'outcome': 'B-fail',
 'promotion': {'rule': 'register a new artifact only if the candidate beats the served v3 on this holdout '
                       'and passes the 30 % criterion',
               'beatsV3': True,
               'promoted': False,
               'reason': 'holdout MAPE 39.3 % against a 30 % criterion; the candidate stays an experiment '
                         'and no artifact is registered'},
 'notChanged': ['the 30 % acceptance criterion', 'the holdout observations', 'the evaluation metric']}
