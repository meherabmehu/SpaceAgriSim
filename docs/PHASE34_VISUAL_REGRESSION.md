# Phase 34 — visual regression repair

Phase 33 changed the chamber view and reported a diff between its parent commit and its branch.
That told a reader what moved, but not *when* it moved, and the committed baselines in
`docs/screenshots` had not been compared against a run since the dashboard grew. This phase
measures the drift at three points instead of asserting it, and repairs the gate.

## 1. What was rebuilt, and how

| tree | commit | how it was produced |
|---|---|---|
| parent | `e7ee85582bfc4224e9f94a4f0d3e85672dcc95fa` | `git worktree add /home/user/p34-parent e7ee855` from the Phase 34 clone |
| candidate | `phase34/evidence` on top of `e7ee855` | the working branch |

Both trees were built and served the same way (`npm run build && npm run preview`, backend under
uvicorn), and the **identical Playwright suite** ran against each with the identical three
viewports (desktop 1440×1100, tablet 820×1180, mobile Pixel 7). Each run reports 123 passed.
Twelve captures are written per run by the suite itself:

```
mission-{desktop,tablet,mobile}.png
radiation-{desktop,tablet,mobile}-{radiation-quality-osd46-v1,radiation-exposure-osd46-v1}.png
water-evidence-{desktop,tablet,mobile}.png
```

All three sets are kept, because a comparison whose inputs are deleted cannot be re-checked:

```
docs/screenshots/*.png                    the committed baselines (gated)
docs/screenshots/phase34/parent/*.png     e7ee855 rebuilt
docs/screenshots/phase34/candidate/*.png  phase 34 head
docs/screenshots/historical/phase9/*.png  the pre-repair baselines, archived
```

## 2. The three-point measurement

`ml/research/phase34_visual_drift.py` → `ml/evaluation/phase34_visual_drift`. It uses the
gate's own metric: identical canvas size, plus the share of pixels whose largest channel delta
exceeds 16.

| comparison | captures | median | max |
|---|---|---|---|
| baseline → parent | 9 gated | — (every canvas size differs) | — (every canvas size differs) |
| parent → candidate | 12 | 0.0 % | see below |
| baseline → candidate | 9 gated | — (every canvas size differs) | — |

### Pre-existing drift (inherited, not introduced here)

Every committed baseline had a different canvas size from the tree this phase starts on:

| capture | baseline | parent / candidate |
|---|---|---|
| mission-desktop | 1440×1569 | 1440×1649 |
| mission-tablet | 820×2290 | 820×2468 |
| mission-mobile | 1082×6032 | 1082×6641 |
| radiation-desktop-exposure | 1128×695 | 1104×627 |
| radiation-desktop-quality | 1128×718 | 1104×628 |
| radiation-tablet-exposure | 580×829 | 580×712 |
| radiation-tablet-quality | 580×851 | 580×744 |
| radiation-mobile-exposure | 992×2748 | 992×2378 |
| radiation-mobile-quality | 992×2935 | 992×2412 |

A size change is the gate's own definition of a moved layout, so this gate **could not pass** for
as long as those baselines stood: the dashboard gained sections after the baselines were last
taken, and the radiation cards were re-laid-out. That is a pre-existing failure, and it is why the
gate was not being run rather than evidence of a Phase 34 change.

### Phase 34's own change

None. After the capture-determinism repair described in §4, parent and candidate are identical:
12 of 12 captures at 0.000 % differing pixels, canvas size unchanged. A phase that only adds
measurement and card text should look like this.

## 3. Replacement decision

The baselines were **replaced**, deliberately:

* the replacements are the **parent-commit** captures, not the candidate's own output, so the
  gate still compares two independently produced things;
* the originals are archived under `docs/screenshots/historical/phase9/` with a table of both
  sizes, so the history is auditable rather than erased;
* no baseline was written from failing output, no tolerance was changed (`PIXEL_BUDGET = 0.02`,
  `CHANNEL_THRESHOLD = 16` are untouched), and `build:check` was not weakened;
* the three `water-evidence-*` captures, which the suite has produced since Phase 20 but no
  comparison ever read, were added to `ALL_CAPTURES` and given first baselines from the same
  parent commit. A layout change on that panel would previously have passed unnoticed.

After the refresh, `python scripts/visual_regression.py` (which refuses to compare against
uncommitted baselines) reports:

```
PASS mission-desktop.png                     0.000% differing
PASS mission-tablet.png                      0.000% differing
PASS mission-mobile.png                      0.000% differing
PASS radiation-desktop-…-quality             0.000% differing
PASS radiation-desktop-…-exposure            0.000% differing
PASS radiation-tablet-…-quality              0.000% differing
PASS radiation-tablet-…-exposure             0.000% differing
PASS radiation-mobile-…-quality              0.000% differing
PASS radiation-mobile-…-exposure             0.000% differing
PASS water-evidence-desktop.png              0.000% differing
PASS water-evidence-tablet.png               0.000% differing
PASS water-evidence-mobile.png               0.000% differing
```

`ml/evaluation/phase9_visual_regression` therefore records twelve genuine passes against
twelve committed baselines, all captured from the tree this phase started on.

## 4. A flaky capture, repaired rather than tolerated

The first parent → candidate comparison showed 1.86 % on
`radiation-mobile-radiation-exposure-osd46-v1` while the other eleven captures sat at or below
0.0013 %. The difference was not layout: it was the focus/hover ring on the *Load control
centroid* button, still lit when the panel screenshot was taken because the test clicks it
immediately before. The same page captured twice then differed by whatever the pointer happened
to be over.

Repair 1: the three capture sites now call a shared `settleForCapture(page)` helper that blurs
the active element and parks the pointer at (0, 0) before the screenshot. The residual dropped to
0.94 % on one panel — still not zero, because those controls animate their tint and the capture
was sampling the transition.

Repair 2: the helper waits 300 ms after the blur. Both trees were then re-captured with the same
patched spec, and the regenerated baselines were taken from that settled parent run. Parent and
candidate are now identical at 0.000 % on all twelve captures.

No assertion was relaxed in either round, and no tolerance was changed.

## 5. Responsive verification

Desktop 1440×1100, tablet 820×1180 and mobile Pixel 7 were all captured for every gated surface.
The suite's own assertions for horizontal overflow
(`document.scrollWidth <= innerWidth`) pass on all three viewports, and no capture changed canvas
width, which is what a responsive break would produce.

## 6. What is not claimed

* Twelve captures are not a design review. They cover the mission dashboard, the two radiation
  prediction cards and the water-use evidence panel; other routes are covered by behaviour tests,
  not pixels.
* The repaired baselines are a property of this Chromium build and font set. A different browser
  or a missing font will move text rasterisation; the tolerance absorbs that, the canvas-size rule
  does not.
* Archiving the old baselines does not retroactively pass any earlier phase: no earlier phase ran
  this gate successfully against them.
