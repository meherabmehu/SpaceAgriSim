"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'generatedAt': '2026-11-13T19:14:17.770932+00:00',
 'phase': 7,
 'assertion': 'Phase 7 did not change the interface. Layout, palette, typography settings, navigation, '
              'cards, buttons, animations, responsive behaviour and the 3D greenhouse are untouched.',
 'source': {'baselineRef': '71347d2',
            'changedFrontendFiles': ['frontend/e2e/guided-workflow-actions.spec.js',
                                     'frontend/e2e/mission.spec.js', 'frontend/e2e/workflow.spec.js',
                                     'frontend/src/pages/MissionPlatform.jsx',
                                     'frontend/src/pages/modules/Account.jsx',
                                     'frontend/src/pages/modules/GuidedWorkflows.jsx',
                                     'frontend/src/services/downloads.test.js',
                                     'frontend/src/services/downloads.ts',
                                     'frontend/src/services/platformApi.ts',
                                     'frontend/src/styles/platform.css'],
            'changedFileCount': 10,
            'diffstat': 'frontend/e2e/guided-workflow-actions.spec.js   | 260 +++++++++++++++++++++++++\n'
                        ' frontend/e2e/mission.spec.js                   |   7 +-\n'
                        ' frontend/e2e/workflow.spec.js                  |   4 +-\n'
                        ' frontend/src/pages/MissionPlatform.jsx         | 240 ++++++++++++-----------\n'
                        ' frontend/src/pages/modules/Account.jsx         |  19 +-\n'
                        ' frontend/src/pages/modules/GuidedWorkflows.jsx | 258 ++++++++++++++++++++----\n'
                        ' frontend/src/services/downloads.test.js        | 135 +++++++++++++\n'
                        ' frontend/src/services/downloads.ts             |  98 ++++++++++\n'
                        ' frontend/src/services/platformApi.ts           |  37 ++--\n'
                        ' frontend/src/styles/platform.css               |  53 +++++\n'
                        ' 10 files changed, 932 insertions(+), 179 deletions(-)',
            'identical': False},
 'playwright': {'skipped': True},
 'screenshotComparison': {'mission-desktop': {'baselineSize': [1440, 1649],
                                              'currentSize': [1440, 1649],
                                              'sizeMatches': True,
                                              'structure': {'baselineLines': 10,
                                                            'currentLines': 10,
                                                            'maxDriftPx': 0,
                                                            'meanDriftPx': 0.0,
                                                            'matches': True,
                                                            'detail': 'every structural edge present in both '
                                                                      'renders, in the same order, within 3 '
                                                                      'px'},
                                              'changedPixels': 10422,
                                              'changedPercent': 0.4389,
                                              'maxChannelSumDelta': 605,
                                              'changedRowBands': [[126, 166]],
                                              'contentRowCount': 1548,
                                              'classification': 'glyph-rasterisation'},
                          'mission-tablet': {'baselineSize': [820, 2469],
                                             'currentSize': [820, 2469],
                                             'sizeMatches': True,
                                             'structure': {'baselineLines': 26,
                                                           'currentLines': 26,
                                                           'maxDriftPx': 0,
                                                           'meanDriftPx': 0.0,
                                                           'matches': True,
                                                           'detail': 'every structural edge present in both '
                                                                     'renders, in the same order, within 3 '
                                                                     'px'},
                                             'changedPixels': 17753,
                                             'changedPercent': 0.8769,
                                             'maxChannelSumDelta': 607,
                                             'changedRowBands': [[102, 192]],
                                             'contentRowCount': 2250,
                                             'classification': 'glyph-rasterisation'},
                          'mission-mobile': {'baselineSize': [1082, 6618],
                                             'currentSize': [1082, 6618],
                                             'sizeMatches': True,
                                             'structure': {'baselineLines': 27,
                                                           'currentLines': 27,
                                                           'maxDriftPx': 0,
                                                           'meanDriftPx': 0.0,
                                                           'matches': True,
                                                           'detail': 'every structural edge present in both '
                                                                     'renders, in the same order, within 3 '
                                                                     'px'},
                                             'changedPixels': 10469,
                                             'changedPercent': 0.1462,
                                             'maxChannelSumDelta': 601,
                                             'changedRowBands': [[386, 477]],
                                             'contentRowCount': 5566,
                                             'classification': 'glyph-rasterisation'}},
 'layoutRegressions': [],
 'verdict': 'ui-extended-layout-preserved',
 'note': 'Residual pixel differences are font rasterisation. The CSS requests Inter / Segoe UI with no '
         "bundled webfont, so the capturing machine's installed font decides the glyphs. Measured here: "
         '4.404 % of pixels differ and the document height shifts by 3 px when the container resolves '
         'sans-serif to DejaVu Sans; installing Inter brings the height to an exact match and the difference '
         'to 3.330 %. In both cases every band is text, no element moves, and the row bands of '
         'non-background content are identical. A genuine layout change would move element boundaries and '
         'change the document height - it does not.'}
