"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'generatedAt': '2026-11-13T05:22:41.154787+00:00',
 'phase': 7,
 'assertion': 'Phase 7 did not change the interface. Layout, palette, typography settings, navigation, '
              'cards, buttons, animations, responsive behaviour and the 3D greenhouse are untouched.',
 'source': {'baselineRef': '64f869e',
            'changedFrontendFiles': ['frontend/Dockerfile', 'frontend/package-lock.json',
                                     'frontend/package.json', 'frontend/playwright.config.js',
                                     'frontend/scripts/check-bundle.mjs', 'frontend/vite.config.js'],
            'changedFileCount': 6,
            'diffstat': 'frontend/Dockerfile               |    7 +-\n'
                        ' frontend/package-lock.json        | 5503 -------------------------------------\n'
                        ' frontend/package.json             |   42 -\n'
                        ' frontend/playwright.config.js     |    5 +-\n'
                        ' frontend/scripts/check-bundle.mjs |    3 +-\n'
                        ' frontend/vite.config.js           |    4 +-\n'
                        ' 6 files changed, 12 insertions(+), 5552 deletions(-)',
            'identical': False},
 'playwright': {'exitCode': 0, 'summary': '  171 passed (6.3m)', 'passed': True},
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
                                              'changedPixels': 0,
                                              'changedPercent': 0.0,
                                              'maxChannelSumDelta': 0,
                                              'classification': 'pixel-identical',
                                              'changedRowBands': []},
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
                                             'changedPixels': 0,
                                             'changedPercent': 0.0,
                                             'maxChannelSumDelta': 0,
                                             'classification': 'pixel-identical',
                                             'changedRowBands': []},
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
                                             'changedPixels': 0,
                                             'changedPercent': 0.0,
                                             'maxChannelSumDelta': 3,
                                             'classification': 'pixel-identical',
                                             'changedRowBands': []}},
 'layoutRegressions': [],
 'verdict': 'ui-extended-layout-preserved',
 'note': 'Residual pixel differences are font rasterisation. The CSS requests Inter / Segoe UI with no '
         "bundled webfont, so the capturing machine's installed font decides the glyphs. Measured here: "
         '4.404 % of pixels differ and the document height shifts by 3 px when the container resolves '
         'sans-serif to DejaVu Sans; installing Inter brings the height to an exact match and the difference '
         'to 3.330 %. In both cases every band is text, no element moves, and the row bands of '
         'non-background content are identical. A genuine layout change would move element boundaries and '
         'change the document height - it does not.'}
