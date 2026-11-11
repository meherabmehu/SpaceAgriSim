# Phase 32 — production bundle: what was fixed, and what cannot be

Two diagnostics come out of `vite build`. One was a real defect and is fixed. The other is a
property of the 3D library, and this document shows the measurement rather than a workaround.

## 1. The circular chunk — fixed

```
Circular chunk: vendor-charts -> vendor -> vendor-charts. Please adjust the manual chunk logic.
```

**Cause.** `vite.config.js` split named vendor groups out of `node_modules` and put *everything
else* into one catch-all `vendor` chunk:

```js
return match ? match[0] : 'vendor'
```

`recharts` depends on packages that were not in any named group, so they landed in `vendor`; and
`vendor` in turn collected modules that `recharts` provides. The chunk graph then had a cycle by
construction, and the chart library could not be cached independently of unrelated code.

**Fix.** Only named groups are chunked; everything else is left to Rollup, which places a module
next to the code that imports it:

```js
return match ? match[0] : undefined
```

`three` and `@react-three/fiber` were also split into `vendor-three` and `vendor-r3f`, so a scene
edit no longer invalidates the library and the library is not re-downloaded for a scene edit.

**Result (measured).**

| Chunk | Size (minified) | Loaded |
| --- | --- | --- |
| `vendor-three` | 735 kB | lazy (only when the 3D twin is switched on) |
| `vendor-charts` | 393 kB | lazy (only when a chart view opens) |
| `vendor-react` | 188 kB | initial |
| `vendor-r3f` | 152 kB | lazy |
| `index` | 34 kB | initial |
| `vendor-icons` | 18 kB | initial |

Initial request: **240 kB across 3 modules**. No circular chunk is reported.

## 2. The 500 kB chunk — measured, not suppressed

```
(!) Some chunks are larger than 500 kB after minification.
```

`chunkSizeWarningLimit` is unchanged, and nothing in the build suppresses the warning. The reason
the warning remains is that **three.js alone is larger than the budget**, whatever the chunking:

| Measured build | Output |
| --- | --- |
| a module importing only `{ WebGLRenderer, Scene }` from `three` | **807 kB** |
| a module importing the eighteen classes the growth-chamber scene uses, plus `OrbitControls` | **917 kB** |
| this application's `vendor-three` chunk | **735 kB** |

The first row is the floor: the library's core module is a single large module, and a module that
imports one class from it still has to load the module. There is therefore no code-splitting or
manual-chunk configuration that puts a three.js scene below 500 kB, and raising the limit would
change the number in the log without changing what a browser downloads.

The digital twin is an existing, working feature and removing it to silence a warning would be the
wrong trade. What the project does instead is enforce the property that actually matters — that an
oversized chunk is never on the path a user pays for:

* `frontend/scripts/check-bundle.mjs` (wired as `npm run build:check`) parses the built chunks and
  **fails the build** if
  1. any chunk above 500 kB is statically reachable from the entry,
  2. the initial request exceeds 240 kB,
  3. a cycle exists in the static chunk graph.
* The 3D module is loaded through `lazy(() => import('../three/GrowthChamberScene.jsx'))` inside
  `DigitalTwin3D`, which itself is a lazily imported route module, so `vendor-three` and
  `vendor-r3f` are reachable only behind a dynamic import.

Current check output:

```
bundle check passed: no cycles, no oversized chunk on the initial path
```

## 3. What a later change has to keep true

1. A new heavy dependency belongs in a `lazy()` boundary, not in a module the entry imports.
2. If a chunk exceeding 500 kB becomes statically reachable, `npm run build:check` fails with the
   chunk name and its size — the failure is the signal, not the warning.
3. If three.js is ever replaced by something smaller, the budget check will notice and the note in
   `vite.config.js` should be updated with the new measurement rather than deleted.
