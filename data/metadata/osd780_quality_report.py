"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'source': 'NASA OSDR OSD-780 (LSDS-128 VEG-04A/B plate counts)',
 'files': ['LSDS-128_Plate Count_Aerobic_Plate_Count_TRANSFORMED.csv',
           'LSDS-128_Plate Count_Yeast_Mold_Plate_Count_Transformed.csv'],
 'rowsWritten': 356,
 'byAssay': {'aerobic': 195, 'yeast_mould': 161},
 'unparsedSampleNames': {'aerobic': 8, 'yeast_mould': 8},
 'missingTarget': 64,
 'target': 'colony_forming_unit_per_gram_fresh_weight_per_swab (CFU per g fresh weight)',
 'alternateTarget': 'colony_forming_units_per_swab (CFU per swab) - a DIFFERENT unit, not interchangeable '
                    'with CFU/g',
 'tissueLevels': ['leaf', 'root', 'soil', 'swab', 'wick'],
 'targetTransform': 'log10(1 + CFU per g); measured zero counts retained as 0',
 'groupingVariable': 'unit = experiment + environment + pillow (biological replicate)',
 'factorLevels': {'assay': ['aerobic', 'yeast_mould'],
                  'experiment': ['VEG04A', 'VEG04B'],
                  'environment': ['flight', 'ground'],
                  'tissue': ['leaf', 'root', 'soil', 'swab', 'wick'],
                  'spectrum': ['blue', 'red'],
                  'treatment': ['clean', 'unclean', 'unspecified']},
 'unitsNote': 'freshWeightG is the mass of the tissue subsample taken for the assay. It is NOT harvest '
              'biomass, standing biomass or yield and must never be used as a biomass label.',
 'limitations': ['Plate counts measure culturable aerobic / yeast-mould load only; they are a lower bound on '
                 'total microbial load.',
                 'Swab and leaf samples are different sampling geometries and are not interchangeable '
                 'measurements.',
                 'VEG04A and VEG04B are separate experiments; cross-experiment generalisation must be tested '
                 'explicitly.',
                 'clean vs unclean is a sample-preparation state (sanitised vs unsanitised leaf), not a '
                 'plant-health label.']}
