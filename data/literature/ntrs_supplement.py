"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'schema': 'spaceagrisim.ntrs_supplement/1',
 'purpose': 'NASA records evaluated for the platform outside the Biomass Production Chamber report set: '
            'measured endpoints for the crops the simulator models, a closed-chamber trace-gas study that '
            'defines a risk the model does not carry, a supraoptimal-CO2 study that shows a limit the CO2 '
            "factor ignores, and NASA's own space-crop reference document with planning-level productivity "
            'numbers.',
 'reports': {'20160006559': {'id': '20160006559',
                             'label': 'NASA/KSC light-quality study',
                             'title': 'Comparative Study of Lettuce and Radish Grown Under Red and Blue LEDs '
                                      'and White Fluorescent Lamps',
                             'stiType': 'PRESENTATION · NASA KSC poster (2016)',
                             'authors': 'M. A. Mickens, G. Massa, G. Newsham, R. Wheeler, M. Birmele',
                             'publication': 'NASA Kennedy Space Center, 22 May 2016',
                             'url': 'https://ntrs.nasa.gov/citations/20160006559',
                             'pdf': 'data/raw/NTRS/20160006559.pdf',
                             'pdf_sha256': 'c05ab77561c72b53be3e9e7913f2e2e7edd4aac96d5dc4ad7833c3656ae912d9',
                             'pages': 1,
                             'dataNature': 'Ground-based growth-chamber experiment at equal PPF; measured '
                                           'endpoints for lettuce and radish, the two crops the platform '
                                           'simulates. Not a spaceflight experiment.',
                             'whyItMatters': "Answers the platform's weakest evidence row (light spectrum is "
                                             'recorded as an annotation). It gives an equal-PPF comparison '
                                             'of red+blue LEDs against white fluorescent light for the same '
                                             'crops, from NASA, with n and SD printed.',
                             'abstract': 'Two short-cycle crops, red romaine lettuce (Lactuca sativa cv. '
                                         'Outredgeous) and radish (Raphanus sativa cv. Cherry Bomb), were '
                                         'grown under either red (630 nm) + blue (450 nm) LEDs or daylight '
                                         'tri-phosphor fluorescent lamps at equal photosynthetic photon '
                                         'flux, and compared for fresh biomass, morphology, leaf area, '
                                         "chlorophyll and ATP. Measured endpoints are on the poster's Table "
                                         '1, not machine-readable text.',
                             'measurementPages': [{'page': 1,
                                                   'terms': ['PPF 200 umol m-2 s-1', '18 h light / 6 h dark',
                                                             '23 C', '70 % RH', 'RB 8:1 red:blue',
                                                             'FL CCT ~5000 K'],
                                                   'excerpt': 'PPF was maintained at ~200 umol m-2 s-1 for '
                                                              'both crops. The photoperiod was 18 h of '
                                                              'active light, and 6 h of darkness. Chamber '
                                                              'air temperature, relative humidity, and CO2 '
                                                              'levels were maintained at 23 C, 70 %, and '
                                                              '1200 umol mol-1, respectively.'},
                                                  {'page': 1,
                                                   'terms': ['lettuce', 'radish',
                                                             'total fresh mass not different',
                                                             'biomass distribution'],
                                                   'excerpt': 'In FL light, lettuce exhibited increased '
                                                              'shoot dimensions, leaf area, and fresh '
                                                              'biomass in comparison to the RB treatment, '
                                                              'but there were no significant differences in '
                                                              'lettuce chlorophyll content. For radish, the '
                                                              'RB treatment appeared to enhance leaf/root '
                                                              'growth while the additional wavelengths from '
                                                              'the FL treatment triggered more biomass '
                                                              'accumulation in the root storage... Although '
                                                              'the total fresh mass was not significantly '
                                                              'different under either treatment, the light '
                                                              'quality affected how the biomass was '
                                                              'distributed in the plant.'}],
                             'structured': {'label': 'Table 1 (poster p.1) - effects of light quality on '
                                                     'shoot length, diameter, fresh mass, leaf area and '
                                                     'chlorophyll content, n = 20, +/- = SD',
                                            'read_from': 'rendered poster page, not a text layer',
                                            'region': {'pdf_page': 1,
                                                       'dpi': 300,
                                                       'clip_pt': [192.8, 463.3, 397.8, 582.1],
                                                       'pixels_sha256': 'a11dda7fca63e85f776e15bca76b11f94a9f857af0091bbc1d49a0e7725d812f'},
                                            'crops': {'lettuce': [{'parameter': 'shoot length',
                                                                   'unit': 'mm',
                                                                   'rb': 150.6,
                                                                   'rb_sd': 3.145,
                                                                   'fl': 178.0,
                                                                   'fl_sd': 2.956,
                                                                   'significance': '***'},
                                                                  {'parameter': 'shoot diameter',
                                                                   'unit': 'mm',
                                                                   'rb': 261.7,
                                                                   'rb_sd': 5.843,
                                                                   'fl': 314.1,
                                                                   'fl_sd': 4.061,
                                                                   'significance': '***'},
                                                                  {'parameter': 'total fresh mass',
                                                                   'unit': 'g',
                                                                   'rb': 13.09,
                                                                   'rb_sd': 0.579,
                                                                   'fl': 16.58,
                                                                   'fl_sd': 0.919,
                                                                   'significance': '**'},
                                                                  {'parameter': 'leaf area',
                                                                   'unit': 'cm2',
                                                                   'rb': 343.5,
                                                                   'rb_sd': 14.9,
                                                                   'fl': 462.7,
                                                                   'fl_sd': 18.23,
                                                                   'significance': '***'},
                                                                  {'parameter': 'chlorophyll',
                                                                   'unit': 'g m-2',
                                                                   'rb': 27.77,
                                                                   'rb_sd': 0.553,
                                                                   'fl': 27.94,
                                                                   'fl_sd': 0.549,
                                                                   'significance': 'NS'}],
                                                      'radish': [{'parameter': 'shoot length',
                                                                  'unit': 'mm',
                                                                  'rb': 145.8,
                                                                  'rb_sd': 4.093,
                                                                  'fl': 119.0,
                                                                  'fl_sd': 2.8,
                                                                  'significance': '***'},
                                                                 {'parameter': 'shoot diameter',
                                                                  'unit': 'mm',
                                                                  'rb': 272.5,
                                                                  'rb_sd': 7.226,
                                                                  'fl': 220.0,
                                                                  'fl_sd': 4.023,
                                                                  'significance': '***'},
                                                                 {'parameter': 'leaf fresh mass',
                                                                  'unit': 'g',
                                                                  'rb': 4.645,
                                                                  'rb_sd': 0.221,
                                                                  'fl': 3.62,
                                                                  'fl_sd': 0.126,
                                                                  'significance': '***'},
                                                                 {'parameter': 'root fresh mass',
                                                                  'unit': 'g',
                                                                  'rb': 20.5,
                                                                  'rb_sd': 0.925,
                                                                  'fl': 23.25,
                                                                  'fl_sd': 0.961,
                                                                  'significance': '*'},
                                                                 {'parameter': 'total fresh mass',
                                                                  'unit': 'g',
                                                                  'rb': 25.14,
                                                                  'rb_sd': 1.103,
                                                                  'fl': 26.87,
                                                                  'fl_sd': 1.065,
                                                                  'significance': 'NS'},
                                                                 {'parameter': 'leaf area',
                                                                  'unit': 'cm2',
                                                                  'rb': 139.9,
                                                                  'rb_sd': 7.453,
                                                                  'fl': 103.6,
                                                                  'fl_sd': 4.314,
                                                                  'significance': '**'},
                                                                 {'parameter': 'chlorophyll',
                                                                  'unit': 'g m-2',
                                                                  'rb': 47.97,
                                                                  'rb_sd': 1.103,
                                                                  'fl': 53.88,
                                                                  'fl_sd': 0.828,
                                                                  'significance': '***'}]},
                                            'quality_notes': ['Significance symbols are reproduced as '
                                                              'printed (*** ** * NS); the poster does not '
                                                              'print the alpha levels.',
                                                              'Poster text is a raster image: there is no '
                                                              'text layer to quote from, so the values were '
                                                              'read off the rendered page and the rendered '
                                                              'region is hash-pinned instead '
                                                              '(region.pixels_sha256).',
                                                              'n = 20 plants per crop per treatment; two '
                                                              'replications of pots.']},
                             'limits': ['One chamber, one cultivar per crop, one campaign; two treatments '
                                        'only (no green-only or far-red arm).',
                                        'Ground-based; says nothing about reduced gravity, the Moon or Mars.',
                                        'Endpoints are fresh mass and morphology at harvest, not a spectral '
                                        'response curve: there is no measured yield-versus-wavelength '
                                        'surface to fit.',
                                        'The poster prints significance symbols but not alpha levels or the '
                                        'test used.']},
             '20040087496': {'id': '20040087496',
                             'label': 'Ethylene sensitivity study',
                             'title': 'Sensitivity of wheat and rice to low levels of atmospheric ethylene',
                             'stiType': 'REPRINT · peer-reviewed (2002)',
                             'authors': 'S. P. Klassen, B. Bugbee',
                             'publication': 'Crop Science 42(3), May 2002',
                             'url': 'https://ntrs.nasa.gov/citations/20040087496',
                             'pdf': None,
                             'pdf_sha256': None,
                             'pages': 0,
                             'dataNature': 'Peer-reviewed closed-chamber study of a trace gas that '
                                           'accumulates in sealed plant growth chambers. NTRS lists no '
                                           'downloadable full text, so only the published abstract is used.',
                             'whyItMatters': 'SpaceAgriSim models a sealed habitat and has no ethylene term '
                                             'at all. This record quantifies how large that omission can be '
                                             '(36-63 % yield loss at 50 ppb), which is a gap the platform '
                                             'must disclose rather than silently ignore.',
                             'abstract': 'Ethylene (C2H4) is produced throughout the life cycle of plants '
                                         'and can accumulate in closed growth chambers to levels 100 times '
                                         'higher than outside. Continuous C2H4 from 0 to 1000 nmol mol-1 was '
                                         'applied over whole life cycles: yield was reduced by 36 % in wheat '
                                         'and 63 % in rice at 50 nmol mol-1, and both species were virtually '
                                         'sterile at 1000 nmol mol-1. Exposure stopped at anthesis reduced '
                                         'yield much less, so the damage is concentrated around seed set. In '
                                         'two further greenhouse studies at 50 nmol mol-1 and 350/1200/5000 '
                                         'micromol mol-1 CO2, USU-Apogee wheat was not significantly '
                                         'affected while Super Dwarf was reduced by 60 %, and elevated CO2 '
                                         'did not change ethylene sensitivity.',
                             'measurementPages': [],
                             'structured': {'abstract_statements': [{'statement': 'yield reduced 36 % in '
                                                                                  'wheat at 50 ppb '
                                                                                  'continuous ethylene',
                                                                     'value': 36,
                                                                     'unit': '%'},
                                                                    {'statement': 'yield reduced 63 % in '
                                                                                  'rice at 50 ppb continuous '
                                                                                  'ethylene',
                                                                     'value': 63,
                                                                     'unit': '%'},
                                                                    {'statement': 'both species virtually '
                                                                                  'sterile at 1000 ppb '
                                                                                  'continuous',
                                                                     'value': 1000,
                                                                     'unit': 'ppb'},
                                                                    {'statement': 'exposure stopped at '
                                                                                  'anthesis gave much '
                                                                                  'smaller yield reductions',
                                                                     'value': None,
                                                                     'unit': None},
                                                                    {'statement': 'Super Dwarf wheat yield '
                                                                                  'reduced 60 % at 50 ppb in '
                                                                                  'the greenhouse',
                                                                     'value': 60,
                                                                     'unit': '%'},
                                                                    {'statement': 'USU-Apogee wheat not '
                                                                                  'significantly reduced at '
                                                                                  '50 ppb',
                                                                     'value': None,
                                                                     'unit': None},
                                                                    {'statement': 'elevated CO2 '
                                                                                  '(350/1200/5000 ppm) did '
                                                                                  'not change ethylene '
                                                                                  'sensitivity',
                                                                     'value': None,
                                                                     'unit': None}],
                                            'verified_against': 'https://ntrs.nasa.gov/citations/20040087496 '
                                                                'abstract field, retrieved 2026-11-07'},
                             'limits': ['Abstract only: NTRS exposes no full text for this record, so no '
                                        'page-level quote is possible.',
                                        'Wheat and rice in ground chambers/greenhouses - not lettuce, tomato '
                                        'or radish, and not a space habitat.',
                                        'The platform deliberately does NOT turn this into an ethylene yield '
                                        'factor: a single crop pair at one trace-gas range is not a '
                                        'transferable response surface.']},
             '20250001897': {'id': '20250001897',
                             'label': 'Space crop reference (NASA HRP)',
                             'title': 'Space Crop Considerations for Human Exploration',
                             'stiType': 'TECHNICAL_MEMORANDUM · NASA HRP (2024)',
                             'authors': 'R. Fritsche, N. Haveman, G. Massa, M. Mickens, T. Smith, et al.',
                             'publication': 'NASA, July 2024',
                             'url': 'https://ntrs.nasa.gov/citations/20250001897',
                             'pdf': 'data/raw/NTRS/20250001897.pdf',
                             'pdf_sha256': '2acbba91b60513d14257e2dcc9b9aaf8f5321545cb0fc73b23b9fc346f504cbe',
                             'pages': 82,
                             'dataNature': "NASA's own reference document on space crop production: which "
                                           "crops have passed Crop Readiness Level 9, what a crew's "
                                           'fresh-food requirement works out to in trays, area and volume, '
                                           'and the input/output terms a crop system has to account for. It '
                                           'reports planning arithmetic, not a growth experiment.',
                             'whyItMatters': 'It supplies the one number the platform was missing: an areal '
                                             "productivity anchor for leafy / pick-and-eat crops from NASA's "
                                             "own planning, which the simulator's lettuce baseline can be "
                                             'checked against. It also states how few crops are actually '
                                             'flight-qualified.',
                             'abstract': 'Why plants: a food system that sustains crew health and '
                                         'performance is required for exploration. ISS prepackaged food '
                                         'degrades over years at 21 C. The document sets out crop selection '
                                         'drivers, Crop Readiness Levels, food safety, hardware, and the '
                                         'inputs/outputs a crop growth system must account for, and gives '
                                         'worked planning arithmetic for leafy greens and microgreens per '
                                         'crew member.',
                             'measurementPages': [{'page': 44,
                                                   'terms': ['25 g microgreen serving', '0.030 m2 tray',
                                                             'approximately 14 days to grow',
                                                             '0.84 m2 per crew member',
                                                             '3.36 m2 for a four-person crew'],
                                                   'excerpt': 'A small, dedicated area of about 0.030 m2, '
                                                              'which is the size of a small tray (17.32 cm X '
                                                              '17.32 cm), is required to grow 25 g of '
                                                              'harvest mass of microgreens. Microgreens take '
                                                              'approximately 14 days to grow, and thus each '
                                                              'crew member would need two small trays per '
                                                              'day for 14 days, which is 28 trays per crew '
                                                              'member. Therefore, a total area of 0.84 m2 '
                                                              'would be needed per crew member or 3.36 m2 '
                                                              'for a four-person crew.'},
                                                  {'page': 45,
                                                   'terms': ['177 g m-3 day-1', '298 g day-1 m-3',
                                                             'nearly double that of mature leafy greens'],
                                                   'excerpt': 'each plant produces up to 3.6 g of fresh '
                                                              'harvest per day which would be 177 g m-3 '
                                                              'day-1. Based on 50 g of fresh microgreens per '
                                                              'crew member grown in a volume of 0.672m3 that '
                                                              'calculates to 298 g day-1 m-3 which is nearly '
                                                              'double that of mature leafy greens.'},
                                                  {'page': 24,
                                                   'terms': ['Crop Readiness Level 9', '9 crops passed',
                                                             '376 crops tested'],
                                                   'excerpt': 'Table A-3 Crops which have passed CRL 9 ... '
                                                              'Considering that the Growing Beyond Earth '
                                                              'program has tested 191 crops and KSC has '
                                                              'tested 204 crops listed above and in Appendix '
                                                              'E (total 376), but only 9 crops have passed '
                                                              'CRL 9, and 10 crops have failed to progress, '
                                                              'there remains a non-trivial amount of ground '
                                                              'and flight test activities needed'},
                                                  {'page': 21,
                                                   'terms': ['minimum crop numbers',
                                                             '3 crop species for vitamins',
                                                             'non-overlapping total of 31'],
                                                   'excerpt': 'Table A-1 Crop numbers and types for early '
                                                              'exploration missions ... Nutrition 3 crop '
                                                              'species/varieties for vitamin categories ... '
                                                              'Non-overlapping total 31'}],
                             'structured': {'areal_productivity_anchor': {'serving_fresh_mass_g': 25.0,
                                                                          'tray_area_m2': 0.03,
                                                                          'cycle_days': 14,
                                                                          'crew_member_daily_serving_g': 50.0,
                                                                          'trays_per_crew_member': 28,
                                                                          'area_per_crew_member_m2': 0.84,
                                                                          'area_four_crew_m2': 3.36,
                                                                          'derived_g_per_m2_day': 59.5,
                                                                          'derived_note': '25 g / 0.030 m2 / '
                                                                                          '14 days = 59.5 g '
                                                                                          'm-2 day-1 fresh; '
                                                                                          'identical to 50 '
                                                                                          'g/day over the '
                                                                                          '0.84 m2 planned '
                                                                                          'per crew member'},
                                            'volumetric_productivity': {'microgreens_g_per_m3_day': 177.0,
                                                                        'microgreens_50g_g_per_m3_day': 298.0,
                                                                        'note': 'as printed; microgreens are '
                                                                                'a volume-efficient crop, '
                                                                                'nearly double mature leafy '
                                                                                'greens'},
                                            'crop_readiness': {'crops_tested': 376,
                                                               'crops_at_crl9': 9,
                                                               'crops_failed': 10,
                                                               'crl9_list': ["'Outredgeous' lettuce "
                                                                             '(Asteraceae)',
                                                                             "'Waldmann's Green' lettuce "
                                                                             '(Asteraceae)',
                                                                             'Mizuna mustard (Brassicaceae)',
                                                                             "'Wasabi' mustard "
                                                                             '(Brassicaceae)',
                                                                             "'Amara' mustard (Brassicaceae)",
                                                                             "'Extra Dwarf' Pak Choi "
                                                                             '(Brassicaceae)',
                                                                             "'Red Russian' kale "
                                                                             '(Brassicaceae)',
                                                                             'Espanola Improved Pepper '
                                                                             '(Solanaceae)',
                                                                             "'Cherry Belle' Radish "
                                                                             '(Brassicaceae)'],
                                                               'note': 'no herb, microgreen or legume crop '
                                                                       'has reached CRL 9'}},
                             'limits': ['Planning arithmetic, not a measured growth experiment: the 59.5 g '
                                        'm-2 day-1 figure is derived from a tray allocation, not a harvest '
                                        'record.',
                                        'Microgreens are harvested young; the anchor is not directly '
                                        'transferable to a mature fruiting crop such as tomato.',
                                        'A document about space crop programmes, so it says nothing '
                                        'quantitative about lunar or Martian gravity.']},
             '20040090155': {'id': '20040090155',
                             'label': 'Supraoptimal CO2 study (soybean)',
                             'title': 'Supraoptimal carbon dioxide effects on growth of soybean [Glycine max '
                                      '(L.) Merr.]',
                             'stiType': 'REPRINT · peer-reviewed (1993)',
                             'authors': 'NASA/KSC life-support crop research (reprint)',
                             'publication': '1993',
                             'url': 'https://ntrs.nasa.gov/citations/20040090155',
                             'pdf': None,
                             'pdf_sha256': None,
                             'pages': 0,
                             'dataNature': 'Peer-reviewed study of what happens above the optimum CO2 '
                                           'partial pressure in a sealed life-support chamber. NTRS lists no '
                                           'downloadable full text for this record, so only the published '
                                           'abstract is used.',
                             'whyItMatters': "The simulator's CO2 response rises monotonically to 3000 ppm. "
                                             'This study found the opposite above about 1000 ppm for one '
                                             'soybean cultivar - exactly the range the platform lets a user '
                                             'select.',
                             'abstract': 'In tightly closed environments used for human life support in '
                                         'space, CO2 partial pressures can reach 500 to 1000 Pa, which may '
                                         'be supraoptimal or toxic to plants. Soybeans (cvs. McCall and '
                                         'Pixie) were grown for 90 days at 50, 100, 200 and 500 Pa CO2 (500, '
                                         '1000, 2000 and 5000 ppm) with recirculating nutrient film '
                                         'technique, a 12-h photoperiod, a 26/20 C thermoperiod and about '
                                         '300 micromol m-2 s-1 PPF. Seed yield and total biomass were '
                                         'greatest at 100 Pa for cv. McCall, suggesting that higher CO2 '
                                         'levels were supraoptimal; cv. Pixie showed little difference '
                                         'between CO2 treatments. Average stomatal conductance of upper '
                                         'canopy leaves at 50 Pa CO2 was approximately 500 Pa > 200 Pa > 100 '
                                         'Pa.',
                             'measurementPages': [],
                             'structured': {'co2_levels_pa': [50, 100, 200, 500],
                                            'co2_levels_ppm': [500, 1000, 2000, 5000],
                                            'cultivar_findings': [{'cultivar': 'McCall',
                                                                   'finding': 'seed yield and total biomass '
                                                                              'greatest at 100 Pa (1000 '
                                                                              'ppm); higher levels '
                                                                              'supraoptimal'},
                                                                  {'cultivar': 'Pixie',
                                                                   'finding': 'little difference in seed '
                                                                              'yield or total biomass '
                                                                              'between CO2 treatments'}],
                                            'stomatal_conductance_order': '50 Pa about equal to 500 Pa > 200 '
                                                                          'Pa > 100 Pa',
                                            'campaign': '90 days, nutrient film technique, 12 h photoperiod, '
                                                        '26/20 C, ~300 umol m-2 s-1 PPF',
                                            'verified_against': 'https://ntrs.nasa.gov/citations/20040090155 '
                                                                'abstract field, retrieved 2026-11-07'},
                             'limits': ['Abstract only: NTRS exposes no full text for this record, so no '
                                        'page-level quote and no per-plant data.',
                                        'Two soybean cultivars in a ground chamber - not lettuce, tomato or '
                                        'radish, and not a space habitat.',
                                        'The platform does NOT cap or bend its CO2 factor from this: one '
                                        'abstract is not a response surface. The gap is disclosed in the app '
                                        'instead.']}},
 'not_used': [{'id': '20160006559',
               'reason': 'The light-quality endpoints are recorded and citable, but no spectral response '
                         'coefficient is fitted: two treatments cannot define a wavelength-to-yield curve, '
                         'and the platform records spectrum as an annotation on purpose.'},
              {'id': '20040087496',
               'reason': 'Ethylene is disclosed as an unmodelled closed-chamber risk. Adding a factor from '
                         'one abstract would be a fabricated coefficient.'},
              {'id': '20250001897',
               'reason': 'Used as an areal-productivity anchor and as evidence for crop qualification, but '
                         'no crop model is fitted: the document reports planning arithmetic for microgreens, '
                         'which is not a per-sample training set.'},
              {'id': '20040090155',
               'reason': 'Used to disclose a limit of the CO2 factor (decline above ~1000 ppm in one '
                         'cultivar), not to fit it: the abstract carries no numeric yields per CO2 level, so '
                         'any fitted coefficient would be invented.'}]}
