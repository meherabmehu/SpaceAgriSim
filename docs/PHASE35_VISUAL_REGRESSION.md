# Phase 35 — Visual regression

The gate now covers **18 captures** (was 12) and passes at **0.000 % differing pixels** on every one.
No tolerance was increased: canvas size must still match exactly and the pixel budget is still 2 % at
a channel threshold of 16.

## Method

1. The parent commit `0f01f31` was rebuilt in a separate worktree (`/home/user/p35-parent`).
2. The identical Playwright suite ran against both trees, with `CI=1` so neither run could silently
   reuse a server belonging to the other tree — a mistake that was caught and corrected during this
   phase, and which had made an earlier "parent" run actually talk to the candidate's API.
3. Captures land in `docs/screenshots/phase35/{parent,candidate}/`; `ml/research/phase35_visual_drift.py`
   compares baseline → parent, parent → candidate and baseline → candidate with the gate's own metric.

## Result

| Capture set | baseline → parent | parent → candidate |
|---|---|---|
| mission desktop / tablet / mobile | 0.000 % | **0.000 %** |
| water-evidence desktop / tablet / mobile | 0.000 % | **0.000 %** |
| benchmarks desktop / tablet | 0.000 % | **0.000 %** |
| benchmarks mobile | 0.000 % | 0.99 % — citation reflows after the overflow fix |
| predictions desktop / tablet / mobile | (new) | 5.73 % / 5.41 % / 3.94 % — badge + verdict sentence |
| radiation ×6 | (re-captured) | size +2 px and content changed — the verdict line |

Every non-zero difference is attributable and intended. The captures that carry the scientific
change (predictions, radiation) moved; every capture that does not carries 0.000 %.

## Capture determinism

`locator.screenshot()` rounds a fractional CSS box using the element's resting scroll position. A
panel measured at 626.61 px produced a 627-pixel image on one run and a 628-pixel image on the next,
which the exact-size rule correctly treats as a layout change. `captureElement()` now rounds the clip
once, at page coordinates, so the image is a function of layout alone. The gate kept both of its
rules unchanged.

## Baseline policy

* The 12 previous baselines are archived to `docs/screenshots/historical/phase34/`.
* All 18 current baselines were installed from the **verified candidate**, after the parent had been
  captured identically first. This is the same policy Phase 34 used for its new captures: a baseline
  is only regenerated once the difference that invalidates it is understood and attributed.
* No baseline was ever overwritten with the output of a failing run. The parent run failed only the
  assertions for features this phase adds (the evidence badge, and the overflow check on the page
  that still has the bug), and captures are separate tests precisely so that a failed assertion
  cannot delete the evidence of itself.

## Gate output

```
PASS  mission-desktop.png              0.000% differing   within tolerance
PASS  mission-tablet.png               0.000% differing   within tolerance
PASS  mission-mobile.png               0.000% differing   within tolerance
PASS  radiation-desktop-*.png (×6)     0.000% differing   within tolerance
PASS  water-evidence-*.png (×3)        0.000% differing   within tolerance
PASS  predictions-*.png (×3)           0.000% differing   within tolerance
PASS  benchmarks-*.png (×3)            0.000% differing   within tolerance

wrote ml/evaluation/phase9_visual_regression
18/18 PASS, exit 0
```
