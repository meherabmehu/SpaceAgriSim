# Phase 8 — UI Preservation

The standing constraint is absolute: no change to layout, palette, typography,
navigation, cards, buttons, animations, responsive behaviour, the 3D greenhouse, or
visual assets. This document records the evidence rather than the promise.

---

## 1. Zero frontend source changes

```
$ git diff --stat fe6bbe2 -- frontend/
(empty)
```

Not one file under `frontend/` differs from the baseline commit. `scripts/compare_ui_screenshots.py`
independently reports `changedFrontendFiles: []`, `changedFileCount: 0`.

The new API surface (retired endpoint, classification endpoint, lettuce v2) required
no frontend work because the existing components are generic:

- `Evidence.jsx` builds predicate cards by mapping `/api/models`, so the v2 artifact
  appears as an additional card with no code change.
- `EarthLettucePrediction.jsx` continues to call the v1 endpoint, which still
  returns 200. Deprecating it in OpenAPI does not break the panel.
- No panel ever called the retired absolute-load endpoint (both microbial models
  remain API-only), so withdrawing it removed nothing from the interface.

## 2. Functional verification at three breakpoints

```
npx playwright test
  15 passed (37.9s)
```

Five scenarios × three viewports (desktop 1440×1100, tablet 820×1180, mobile
Pixel 7), including "mission shell, real controls, and responsive navigation",
"saved models use real artifacts and reject unsupported scientific scope", and
"API outages are explicit and retry recovers".

Lint and production build both succeed.

## 3. Pixel comparison, and an honest reading of it

`scripts/compare_ui_screenshots.py --baseline fe6bbe2` reports a residual
difference on tablet and mobile (up to 17 px and 126 px of vertical drift). That
number is real and it is **not** claimed as "no change":

```
frontend source changes vs fe6bbe2: 0
  mission-desktop    layout-identical-height-drift    maxDrift=3px
  mission-tablet     layout-difference                maxDrift=17px
  mission-mobile     layout-difference                maxDrift=126px
verdict: ui-changed
```

Phase 7 already attributed this class of drift to font rasterisation: the CSS
requests Inter / Segoe UI with no bundled webfont, so the capturing machine's
installed fonts decide the glyph metrics. Phase 8 adds a second, independent test
of that attribution rather than relying on the previous note.

### A/B test of the attribution

The v2 artifact was temporarily removed from the runtime bundle registry — the only
change in the system that could plausibly add UI content — and the capture repeated:

| Capture | desktop | tablet | mobile |
|---|---|---|---|
| With v2 present | 3 px | 17 px | 126 px |
| With v2 removed | 3 px | 17 px | 126 px |

Byte-identical drift in both conditions. The differing pixels are not attributable
to anything Phase 8 changed; they are environmental, and they are the same drift
Phase 7 recorded on this capture environment. The bundle was restored afterwards and
the registry re-verified at six models.

Note also that the screenshots capture the mission shell, which does not contain
the model-card list — so the cards a data change could affect are not in the
compared image at all.

## 4. Commit hygiene

Regenerated PNGs and regenerated `docs/phase7/*.py` verification reports were
**not committed**. Those files change on every verification run (timestamps and
random row ids) and committing them would present churn as work. They were restored
to the committed baseline with `git checkout --` after each run.
