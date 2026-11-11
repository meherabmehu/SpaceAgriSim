# Historical screenshots

These files are not compared by any gate. They are kept because the record of what a page
looked like at a given commit is evidence, and deleting it would leave a later reader unable to
tell whether a baseline moved because the design changed or because the baseline was stale.

## phase9/

The nine captures that `ml/evaluation/phase9_visual_regression.json` compared against from
Phase 9 until Phase 33. They were archived in Phase 34, not deleted, when the baselines were
regenerated, because every one of them had the wrong canvas size:

| capture | archived size | Phase 33 size |
|---|---|---|
| mission-desktop | 1440x1569 | 1440x1649 |
| mission-tablet | 820x2290 | 820x2468 |
| mission-mobile | 1082x6032 | 1082x6641 |
| radiation-desktop-exposure | 1128x695 | 1104x627 |
| radiation-desktop-quality | 1128x718 | 1104x628 |
| radiation-tablet-exposure | 580x829 | 580x712 |
| radiation-tablet-quality | 580x851 | 580x744 |
| radiation-mobile-exposure | 992x2748 | 992x2378 |
| radiation-mobile-quality | 992x2935 | 992x2412 |

A canvas-size change is the gate's own definition of a moved layout, so from the moment the
dashboard grew (long before Phase 33) this gate could not pass. That is why it was not run: the
drift was inherited, not introduced by Phase 34, and
`ml/evaluation/phase34_visual_drift.json` measures it at three points rather than asserting it.

The replacements were captured from the Phase 33 parent commit `e7ee855`, built in a separate
worktree and photographed with the identical Playwright suite and viewports. Phase 34 itself
changes no visual output: parent to candidate is a median 0.0 % and a maximum of 1.86 % on one
mobile radiation panel, which is a pointer-hover ring on a button, not a layout change.
