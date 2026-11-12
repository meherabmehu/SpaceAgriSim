"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'schema': 'spaceagrisim.phase29_environmental_stress_search/1',
 'generatedOn': '2026-11-10',
 'purpose': 'Record the search for data that could support an environmental-stress response surface. It is '
            'recorded so the absence of a surface is an auditable finding rather than an assertion: what was '
            'looked for, where, what came back, and why nothing new was acquired.',
 'endpoints': [{'name': 'zenodo',
                'url': 'https://zenodo.org/api/records',
                'auth': 'none',
                'outcome': 'reachable'},
               {'name': 'dryad',
                'url': 'https://datadryad.org/api/v2/search',
                'auth': 'none',
                'outcome': 'reachable'},
               {'name': 'figshare',
                'url': 'https://api.figshare.com/v2/articles',
                'auth': 'none',
                'outcome': 'reachable; search endpoint rejects the /v2/articles/search path used earlier'}],
 'queries': [{'query': 'lettuce light spectrum growth open data',
              'returned': 8,
              'verdict': 'no dataset; the hits are museum-collection records whose text matches on '
                         'individual words'},
             {'query': 'lettuce photoperiod daily light integral dataset',
              'returned': 8,
              'verdict': 'one relevant record (zenodo 16271245, pak choi photoperiod at constant DLI) and '
                         'one unrelated proteomics set'},
             {'query': 'controlled environment lettuce PPFD response data',
              'returned': 8,
              'verdict': 'two relevant records, neither carrying a yield-versus-PPFD surface (zenodo '
                         '20759414, 22004997)'}],
 'candidates': [{'id': 'zenodo-16271245',
                 'doi': '10.5281/zenodo.16271245',
                 'license': 'cc-by-4.0',
                 'resourceType': 'dataset',
                 'publicationDate': '2025-07-21',
                 'title': 'Extended Photoperiod Improves Growth and Nutritional Quality of Pak Choi Under '
                          'Constant Daily Light Integral',
                 'file': 'Kartika_Supplementary_data_Table_S3.xlsx',
                 'bytes': 4392940,
                 'relevance': 'a genuine photoperiod axis, but at constant DLI and in pak choi, not lettuce',
                 'acquired': False,
                 'whyNotAcquired': 'acquiring it would extend the crop set rather than close the gap: the '
                                   "platform's light claims are lettuce claims, and a pak-choi photoperiod "
                                   'trial at constant DLI cannot validate a lettuce photoperiod response. It '
                                   'is recorded here as the most promising next acquisition, not as '
                                   'evidence.'},
                {'id': 'zenodo-20759414',
                 'doi': '10.5281/zenodo.20759414',
                 'license': 'cc-by-4.0',
                 'resourceType': 'dataset',
                 'publicationDate': '2026-06-19',
                 'title': 'Multi-Sensor High-Throughput Phenotyping Dataset of Hydroponic Lettuce under '
                          'Variable Fertigation Conditions',
                 'file': 'IoT4Lettuce.zip',
                 'bytes': 39149276870,
                 'relevance': 'lettuce phenotyping, but the varied factor is fertigation, not light',
                 'acquired': False,
                 'whyNotAcquired': '39 GB for a factor this workflow does not offer; the light conditions '
                                   'are not the treatment variable, so it cannot support a light-stress '
                                   'surface. The size is also outside what this repository stores.'},
                {'id': 'zenodo-22004997',
                 'doi': '10.5281/zenodo.22004997',
                 'license': 'cc-by-4.0',
                 'resourceType': 'dataset',
                 'publicationDate': '2026-08-19',
                 'title': 'Dataset for Multispectral PPFD and DLI Monitoring under Dynamic Plant-Factory '
                          'Lighting',
                 'file': 'Final Dataset_PPFD Monitoring_Dataset_v1.0.xlsx',
                 'bytes': 33672643,
                 'relevance': 'instrument-level PPFD/DLI measurements under dynamic lighting, no plant '
                              'response',
                 'acquired': False,
                 'whyNotAcquired': 'it measures the light, not the crop. It could calibrate a light-delivery '
                                   'model, which is not the missing quantity: the missing quantity is the '
                                   "plant's response."}],
 'conclusion': {'surfaceFitted': False,
                'why': 'A response surface needs a design that varies the factor over at least three levels '
                       'with the other factors held or recorded. No openly licensed dataset found in this '
                       'search varies PPFD, photoperiod, CO2 or temperature over a yield response in '
                       'lettuce. The Greenlight 2024 trial in hand varies spectral composition at one PPFD '
                       'and one photoperiod, which supports a four-regime measured comparison and nothing '
                       'continuous.',
                'whatWouldCloseIt': 'A controlled-environment trial reporting yield at three or more PPFD '
                                    'levels and three or more photoperiods, with the other factors recorded, '
                                    'under an open licence.'}}
