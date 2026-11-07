# Phase 7 — UI Preservation Evidence

The standing constraint is absolute: no changes to layout, palette, typography,
navigation, cards, buttons, animations, responsive design, the 3D greenhouse or
visual assets. New functionality must arrive through existing generic components.

This document records the measurement, not the intention. Evidence:
`docs/phase7/ui_preservation.json`, produced by
`scripts/compare_ui_screenshots.py`.

---

## 1. The strongest available proof: source identity

```
git diff --stat b4890e9 -- frontend
(empty)
```

**Zero frontend files changed** across the whole Phase 7 branch. Not one line of
JSX, CSS, config or asset. Verified against the Phase 6 base commit `b4890e9`.

That alone settles preservation at the source level: if the code is byte-identical,
no interface change can have been introduced by this phase.

## 2. What that means for the mission page

`MissionPlatform.jsx` already fetches `/api/models` and passes the result to the
`Predictions` panel, which renders `models?.models?.map(...)` and gates
sub-panels on `m.artifactExists`. So the new `mizuna-microbial-relative-load-v2`
entry appears through the **existing generic registry rendering** — no new
component, no new route, no new stylesheet. This is exactly the mechanism the
constraint permits.

## 3. The measurement, including where it does not reach zero

Screenshots were re-captured through the real Playwright suite and diffed against
the committed baseline images.

| Viewport | Document height | Structural lines | Max edge drift | Changed pixels |
|---|---|---|---|---|
| Desktop 1440×1100 | 1569 → 1569 (**exact**) | 12 → 12 | **0 px** | 3.319 % |
| Tablet 820×1180 | 2290 → 2291 (+1 px) | 26 → 26 | **1 px** | – |
| Mobile 1082 (Pixel 7) | 6032 → 6035 (+3 px) | 27 → 27 | **3 px** | – |

**The residual difference is font rasterisation, and it is attributable.** The
stylesheet requests `Inter, "Segoe UI", sans-serif` and the project bundles **no
webfont**, so the capturing machine's font set decides the glyphs:

| Capture condition | Desktop result |
|---|---|
| Container resolves `sans-serif` → DejaVu Sans | 4.404 % of pixels differ, height off by 3 px |
| Inter installed in the container | height **exactly** matches, 3.319 % of pixels differ |

Re-running the same capture twice with identical code changes only **0.01 %** of
pixels, so the measurement itself is deterministic — the difference is not noise.

## 4. Why the structural test is the one that matters

A single percentage conflates two very different things. The decisive metric is
the **y position of every near-continuous horizontal edge** — card borders and
section rules. Glyphs produce sparse per-row edges; CSS borders produce edges
across almost the full content width.

Result: **every structural edge present in both renders, in the same order**, with
0 px drift on desktop and 1–3 px accumulated over a 6000 px mobile document.

A real layout change adds, removes or reorders edges. Sub-pixel line-height
accumulation from different font metrics cannot do that; it moves a border by at
most a few pixels at the very bottom of a very long page. The classifier in the
script encodes exactly this rule and prints `layout-identical-height-drift` rather
than the flattering `pixel-identical` — because the pixels genuinely are not
identical.

## 5. Functional confirmation

| Check | Result |
|---|---|
| Playwright e2e suite (desktop, tablet, mobile) | **15 / 15 passed** |
| Backend test suite | **187 passed, 1 skipped** |
| Frontend source diff vs `b4890e9` | **0 files** |

The 15 e2e tests include the shell/navigation, the comparison and evidence-search
flows, the model-artifact panel, the advisor and optimizer, exports, and the API
outage recovery path — so the interface still *functions*, not just looks, the same.

## 6. Honest limits of this evidence

- The committed baseline screenshots were captured in a different font
  environment than this one, so pixel equality is not achievable here and is not
  claimed. Source identity plus the structural test is the substantive argument;
  the pixel percentage is context.
- Screenshots cover the mission shell at three viewports, not every route. The
  zero-file source diff is what covers the routes without screenshots.
- Animations are captured at whatever frame the test reached. They are not
  compared frame-by-frame, and no claim is made about them beyond "no source
  changed".
