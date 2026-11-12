"""Data record. Generated - the generator is named inside the record itself."""

DATA = {'generatedAt': '2026-11-12T21:32:16.692044+00:00',
 'phase': 7,
 'assertion': 'Phase 7 did not change the interface. Layout, palette, typography settings, navigation, '
              'cards, buttons, animations, responsive behaviour and the 3D greenhouse are untouched.',
 'source': {'baselineRef': 'b4890e9',
            'changedFrontendFiles': [],
            'changedFileCount': 0,
            'diffstat': '(none)',
            'identical': True},
 'playwright': {'exitCode': 1, 'summary': '  170 passed (5.6m)', 'passed': False},
 'screenshotComparison': {},
 'layoutRegressions': [],
 'verdict': 'ui-unchanged',
 'note': 'Residual pixel differences are font rasterisation. The CSS requests Inter / Segoe UI with no '
         "bundled webfont, so the capturing machine's installed font decides the glyphs. Measured here: "
         '4.404 % of pixels differ and the document height shifts by 3 px when the container resolves '
         'sans-serif to DejaVu Sans; installing Inter brings the height to an exact match and the difference '
         'to 3.330 %. In both cases every band is text, no element moves, and the row bands of '
         'non-background content are identical. A genuine layout change would move element boundaries and '
         'change the document height - it does not.'}
