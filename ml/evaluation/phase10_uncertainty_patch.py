"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'alpha': 0.1,
 'seed': 42,
 'models': {'mizuna-microbial-relative-load-v2': {'path': 'ml/artifacts/mizuna-microbial-relative-load-v2',
                                                  'radius': 1.678817,
                                                  'method': 'group-level cross-conformal',
                                                  'achievedCoverage': 0.9919},
            'mizuna-microbial-load-v1': {'path': 'ml/artifacts/mizuna-microbial-load-v1',
                                         'radius': 3.555489,
                                         'method': 'group-level cross-conformal',
                                         'achievedCoverage': 0.9919},
            'lettuce-earth-growth-v1': {'path': 'ml/artifacts/lettuce-earth-growth-v1',
                                        'radius': 112.943259,
                                        'method': 'cross-conformal (CV+)',
                                        'achievedCoverage': 0.9393},
            'lettuce-earth-growth-v2': {'path': 'ml/artifacts/lettuce-earth-growth-v2',
                                        'radius': 91.199429,
                                        'method': 'cross-conformal (CV+)',
                                        'achievedCoverage': 0.9606}},
 'note': 'Radii calibrated on every available biological group by cross-conformal. Achieved coverage is the '
         'measured held-out value from phase10_conformal, not a re-measurement on the same data the radius '
         'was fit to.'}
