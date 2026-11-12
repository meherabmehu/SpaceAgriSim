"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'table': 'schroder2021_lettuce_et_daily.csv',
 'rows': 121,
 'columns': ['treatment', 'date', 'dayNumber', 'etRateMlPerDayMean', 'etRateMlPerDaySd', 'pots'],
 'generatedAt': '2026-11-10T12:54:26.804907+00:00',
 'study': {'datasetId': 'zenodo-schroder-2021-lettuce-pot',
           'doi': '10.5281/zenodo.5550230',
           'citation': 'Schröder C, Häfner F, Larsen OC, Krause A (2021). Urban Organic Waste for Urban '
                       'Farming: Growing Lettuce Using Vermicompost and Thermophilic Compost. Agronomy '
                       '11(6):1175',
           'license': 'CC BY 4.0',
           'evidenceCategory': 'crop water-use measurement',
           'environment': 'controlled-environment greenhouse'},
 'source': {'datasetSha256': '5e0c4ccd729f27c76612ff4ca051ed320eecc0a648efbb6bcae824db2a8fbc95',
            'note': 'hash recorded by scripts/datasets/acquire.py at download time'},
 'units': {'etRateMlPerDayMean': 'mL per pot per day, treatment mean',
           'etRateMlPerDaySd': 'mL per pot per day, between-pot standard deviation'},
 'grouping': 'treatment x measurement date',
 'derivations': ['etRateMlPerDayMean', 'etRateMlPerDaySd'],
 'perPlant': True,
 'note': 'the shape a validation compares against; the per-pot table above is the raw one'}
