# Phase 33 — production bundle: removing the oversized chunk at the source

Phase 32 fixed the circular-chunk diagnostic and left the size warning in place with a measurement
explaining why it could not be fixed (`docs/PHASE32_FRONTEND_BUNDLE.md`). This phase removes the
cause instead of the symptom: the growth chamber is no longer a three.js scene.

Nothing in this phase raises `chunkSizeWarningLimit`, adds a warning filter, or introduces a
success check that can pass while a warning is printed. The verification below reads the raw
`vite build` output.

---

## 1. Before and after, measured on the same machine

Both columns come from a clean `npm ci && npm run build` in a fresh checkout. "Before" is
`bcd4ec506b2319c7b37a90459428c951f46f965a` (verified remote `main`); "after" is this branch.

| Chunk | Before — minified | Before — gzip | After — minified | After — gzip | Load |
| --- | --- | --- | --- | --- | --- |
| `vendor-three` | **753.06 kB** | 193.74 kB | *removed* | *removed* | lazy |
| `vendor-r3f` | **155.15 kB** | 49.50 kB | *removed* | *removed* | lazy |
| `GrowthChamberScene` | 12.35 kB | 4.36 kB | *removed* | *removed* | lazy |
| `vendor-charts` | 402.68 kB | 116.00 kB | 402.65 kB | 115.99 kB | lazy |
| `vendor-react` | 192.95 kB | 60.55 kB | 192.91 kB | 60.52 kB | initial |
| `index` | 34.33 kB | 11.95 kB | 34.32 kB | 11.94 kB | initial |
| `vendor-icons` | 18.31 kB | 6.56 kB | 18.31 kB | 6.56 kB | initial |
| `DigitalTwin3D` | 11.12 kB | 4.64 kB | 25.64 kB | 9.64 kB | lazy |
| `Evidence` | 23.20 kB | 7.65 kB | 23.20 kB | 7.65 kB | lazy |
| `GuidedWorkflows` | 29.91 kB | 8.69 kB | 29.91 kB | 8.69 kB | lazy |
| `ScientificWorkflow` | 11.63 kB | 4.02 kB | 11.63 kB | 4.02 kB | lazy |
| `Laboratory` | 10.73 kB | 3.78 kB | 10.73 kB | 3.78 kB | lazy |
| **Total JavaScript** | **1667.35 kB** | **480.20 kB** | **782.47 kB** | **244.37 kB** | — |

* **884.88 kB of minified JavaScript removed (−53.1 %)**; 235.83 kB less over the wire (−49.1 %).
* **Initial request: 240 kB across 3 modules, unchanged.** Nothing was added to the first paint.
* `DigitalTwin3D` grows from 11.12 kB to 25.64 kB: that is the entire chamber view living in the
  chunk it already owned, plus the code that used to be in `GrowthChamberScene` and the boundary.
  Net change for the twin as a whole: `11.12 + 12.35 + 753.06 + 155.15 = 931.68 kB` before,
  `25.64 kB` after.

## 2. The two build diagnostics, verbatim

**Before** (`npm run build`, exit 0):

```
(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
```

**After** (`npm run build`, exit 0): the warning is **absent**. `grep` over the full build log for
`(!)`, `warning`, `circular` and `larger than` returns nothing. No circular-chunk diagnostic is
reported either.

`vite.config.js` sets no `build.chunkSizeWarningLimit`; the value is Vite's default 500 kB.

## 3. `npm run build:check`, before and after

The Phase 32 script asserted that any chunk above 500 kB was reachable *only* through a dynamic
import, and reported the oversized chunk as a **note**. Phase 33 had the property it was actually
protecting — so the script is tightened rather than relaxed:

| | Phase 32 script | Phase 33 script |
| --- | --- | --- |
| oversized chunk, statically reachable | failure | failure |
| oversized chunk, lazy-reachable only | **note, exit 0** | **failure** |
| initial budget | 260 kB (240 kB measured + padding for the pending work) | **240 kB** (the Phase 32 target, now enforced) |
| circular chunk | failure | failure |

Wall-clock output on this branch:

```
production bundle:
  vendor-charts-B89hi3F6.js             393 kB  lazy
  vendor-react-Bl4wyysX.js              188 kB  INITIAL
  index-B7A70U3l.js                      34 kB  INITIAL
  ...
  initial request (index.html static graph): 240 kB across 3 module(s)
bundle check passed: no cycles, no oversized chunk anywhere, initial request within budget
```

Exit code 0. With the Phase 32 build in place the same script would have failed on
`vendor-three` (753 kB), which is the intended behaviour: the guard is now strict enough to have
caught the state this phase inherited.

## 4. Dependencies removed

| Package | Version | Why it existed | Size in the bundle |
| --- | --- | --- | --- |
| `three` | ^0.185.1 | WebGL renderer, geometries, materials | 753.06 kB in `vendor-three` |
| `@react-three/fiber` | ^9.7.0 | React renderer for three.js | part of `vendor-r3f` |
| `@react-three/drei` | ^9.x (via fiber) | `OrbitControls` and helpers | part of `vendor-r3f` |

`package.json` and `package-lock.json` no longer mention any of them:

```
$ grep -c "three\|react-three" package-lock.json
0
$ npm ls three
spaceagrisim-frontend@0.1.0 /frontend
`-- (empty)
```

`vite.config.js` no longer declares the `vendor-three` and `vendor-r3f` manual-chunk groups; the
remaining named groups (`vendor-react`, `vendor-icons`, `vendor-charts`) are unchanged, and the
catch-all bucket that caused the Phase 32 cycle is still absent.

## 5. Why the feature could not stay in three.js

Measured in Phase 32 and re-stated here because it is the reason for the rewrite:

| Build | Output |
| --- | --- |
| a module importing only `{ WebGLRenderer, Scene }` from `three` | 807 kB |
| the eighteen classes the chamber scene used, plus `OrbitControls` | 917 kB |
| this application's `vendor-three` chunk | 753 kB |

`three@0.185.1` does not tree-shake per class, and subpath imports
(`three/src/...`) do not change the floor. There is no chunking that puts a real three.js scene
under 500 kB. The choice was therefore: delete the chamber, hide the warning, or rebuild the
chamber without the renderer. Only the third keeps the feature and the guarantee.

## 6. What the chamber view costs instead

`frontend/src/components/GrowthChamberView.jsx` — plain SVG, no canvas, no WebGL, no animation
loop. It draws with the same primitives the rest of the UI uses and is driven by the same
`deriveTwinState()` contract the 3D scene consumed, so no API, response field or scientific
statement changed. Animation is SMIL, mounted only when the panel is in view and the user has not
asked for reduced motion, so a scrolled-out twin costs nothing per frame.

## 7. Reproducing this table

```bash
cd frontend
npm ci
rm -rf dist
npm run build            # read the chunk table; confirm no "(!)" lines
npm run build:check      # load-graph + size guard
```

For the "before" column:

```bash
git worktree add ../p33base bcd4ec506b2319c7b37a90459428c951f46f965a
cd ../p33base/frontend && npm ci && npm run build
```
