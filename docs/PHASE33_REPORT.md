# Phase 33 — replacing the three.js growth chamber

**Goal:** remove the oversized-chunk warning by removing the oversized library, without hiding the
warning, deleting a feature, or weakening a check.

| | |
| --- | --- |
| Repository | `meherabmehu/SpaceAgriSim` |
| Branch | `phase33/frontend`, from verified remote `main` at `bcd4ec506b2319c7b37a90459428c951f46f965a` |
| Scope | the growth-chamber / digital-twin presentation only. No other screen, route, API contract, model, dataset or scientific statement was touched |
| Production deploy | **not performed by this phase.** No Render resource, setting, environment variable, migration or worker was read or written |

---

## 1. What the problem actually was

Phase 32 left two build diagnostics and a written explanation:

1. a **circular chunk**, fixed by dropping a catch-all `vendor` manual-chunk bucket;
2. `Some chunks are larger than 500 kB after minification`, **not** fixed, because it is a property
   of `three.js`: a module importing only `{ WebGLRenderer, Scene }` already measures 807 kB, and
   the classes the chamber scene used measure 917 kB. `three@0.185.1` does not tree-shake per class
   and subpath imports do not lower the floor.

Phase 32's answer was to prove the oversized chunk was lazy-loaded and keep the warning visible.
That was honest, but it left the requirement open: a bundle that ships a 753 kB library for one
panel is a real cost, and the only three ways out are to delete the panel, to suppress the warning,
or to rebuild the panel without the renderer. The first two were rejected. This phase does the
third.

## 2. What was verified before anything changed

* `git ls-remote` confirmed `main` at `bcd4ec5…`; the branch was cut from that commit, not from a
  working tree.
* The whole 3D surface was read before replacing it: `frontend/src/three/GrowthChamberScene.jsx`
  (546 lines: `Canvas`, `useFrame`, `useThree`, `OrbitControls`, instanced leaf/stem geometry,
  `GrowLights`, `WaterManifold`, `Sensors`, `IndicatorStrip`, `CameraRig`),
  `frontend/src/components/DigitalTwin3D.jsx` (284 lines: panel shell, legend, status tags,
  harvest caption, the existing 2D `SchematicTwin`, `SceneErrorBoundary`, the
  `spaceagrisim.twin3d` preference key), and `frontend/src/services/twinState.js` (the
  presentation contract both views read).
* `grep` showed the scene was referenced from exactly one place (`MissionPlatform.jsx`, a lazy
  route) and asserted by exactly one browser test (`mission.spec.js:147`, the 2D schematic).
* A clean `npm ci && npm run build` recorded the **before** bundle, so the comparison in
  `docs/PHASE33_FRONTEND_BUNDLE.md` is a measurement on this machine, not an estimate.

## 3. What replaced it

`frontend/src/components/GrowthChamberView.jsx` — an interactive **isometric SVG** view. Plain
markup, no `<canvas>`, no WebGL, no dependency, no render loop.

Everything the 3D scene communicated is still communicated, driven by the same `deriveTwinState()`
values:

| Preserved from the scene | How it is drawn now |
| --- | --- |
| Chamber enclosure, glazing, deck, back-wall grid, ceiling service panel | Polygons and frame bars under an oblique-parallel projection that rotates about the vertical axis and tilts with elevation |
| Tiered trays, one per crop row | `rows` trays placed along the chamber depth, each with a medium bed and legs |
| Crop placement | `rows × perRow` plants with deterministic per-plant jitter, so a re-render never reshuffles them |
| Crop archetypes | lettuce and radish **rosettes** (multi-whorl leaves, radish adds a bulb), tomato **vine** (tall stem, four leaflet tiers, fruit once the canopy passes half) |
| Growth stage | Canopy fraction drives leaf count, leaf size, leaf spread and stem height; outer whorls unfurl first, as the instanced version did |
| Health / stress colour | Leaf colour mixes between healthy green and stressed olive on the space-vs-Earth ratio; water deficit additionally droops leaves and desaturates them |
| LED light bars | Five ceiling bars with diode dots; diffuser opacity and beam intensity follow photoperiod |
| Water manifold and reservoir | Supply main plus per-tray branches, a droplet travelling the main, and a floor-standing tank whose fill height is the supplied share of demand — amber and a deficit tag when demand is not met |
| Radiation / CO₂ / O₂ indicator strips | Three segmented wall panels, six segments each, lit to the same normalised intensities |
| Sensor points | Six wall-mounted nodes that pulse when the panel is in view and motion is allowed |
| Stress tags | `NO GROWING AREA`, `NO GROWTH`, `WATER DEFICIT`, `HIGH RADIATION`, unchanged |
| Overlay caption | `DAY n · NEXT HARVEST …` / `n HARVESTS · LAST … · REGROWING`, unchanged |
| Legend, per-system text, footnote | Unchanged wording, including "configured setpoints, not sensor measurements" and "Animated flow is illustrative" |
| Preference | Same `localStorage` key and the same `on`/`off` values, so an existing user choice survives the redesign |

**Interaction.** Drag to orbit; wheel to zoom (with a non-passive listener so the page does not
scroll underneath); arrow keys to orbit, `+`/`−` to zoom and `Home` or a double-click to reset;
`←`/`→`/`+`/`−`/`RESET` buttons for pointer-free use; clicking a system — or its button in the
legend — selects it and swaps the explanation. The view has `role="img"` with an accessible name,
is focusable, and every control is a real `<button>` with a label. A click that ends a drag is
treated as an orbit, not a selection.

**The switch.** `3D VIEW ON/OFF` is now `CHAMBER VIEW / 2D SCHEMATIC`, which is what the two states
actually are. The 2D front-elevation schematic is retained verbatim and remains the fallback if the
chamber view ever throws.

**Motion.** SMIL only, mounted when the panel is in view (`IntersectionObserver`, as before) and the
user has not set `prefers-reduced-motion`. There is no per-frame JavaScript.

## 4. Bundle result

| | Before | After | Change |
| --- | --- | --- | --- |
| Total JavaScript | 1667.35 kB / 480.20 kB gzip | **782.47 kB / 244.37 kB gzip** | −884.88 kB minified (−53.1 %), −235.83 kB gzip (−49.1 %) |
| Largest chunk | `vendor-three` 753.06 kB | `vendor-charts` 402.65 kB | under the 500 kB budget |
| Initial request | 240 kB / 3 modules | 240 kB / 3 modules | unchanged |
| `vite build` warning | `(!) Some chunks are larger than 500 kB…` | none | removed at the source |
| `three`, `@react-three/fiber`, `@react-three/drei` | in `package.json` + lockfile | gone from both | deleted |

Full table, the verbatim diagnostics and the reproduction commands: `docs/PHASE33_FRONTEND_BUNDLE.md`.

Two guards were **tightened**, not relaxed:

* `scripts/check-bundle.mjs` now **fails** on an oversized chunk anywhere in the bundle. Previously
  an oversized but lazy chunk produced a note and exit 0. Run against the Phase 32 build, the new
  script fails on `vendor-three` — which is the point.
* The initial-request budget goes from 260 kB back to the **240 kB** Phase 32 target, now enforced.

`chunkSizeWarningLimit` is untouched (Vite's default 500 kB). Nothing filters or rewrites build
output; `npm run build` is still plain `vite build`.

## 5. Full regression

Every gate below was run on this branch, in this order, from a clean state.

| Gate | Command | Result |
| --- | --- | --- |
| Install | `npm ci` | clean, 0 vulnerabilities |
| Lint | `npm run lint` | 0 problems |
| Types | `npm run typecheck` | 0 errors |
| Production build | `npm run build` | exit 0, **no warnings of any kind** |
| Bundle guard | `npm run build:check` | passed: no cycles, no oversized chunk anywhere, initial 240 kB / 3 modules |
| Browser suite | `npx playwright test` (desktop 1440×1100, tablet 820×1180, mobile Pixel 7) | **123 passed** (41 tests × 3 viewports), 4.5 min |
| Backend, SQLite | `pytest backend/tests -q -p no:randomly` | **1212 passed, 24 skipped** |
| Backend, PostgreSQL 17.11 | same, with `SPACEAGRISIM_TEST_POSTGRES_URL` | **1236 passed, 0 skipped** |
| Model audit | `scripts/audit_models.py` | 161 checks, **0 failed**, 5 documented limitations, 0 high |
| Registry | `scripts/verify_model_registry.py` | **60/60** checks |
| Provenance | `ml/training/phase32_provenance.py --check` | complete for **9 artifacts** |
| Feature coverage | `ml/research/build_feature_coverage.py --check` | up to date (12 features) |
| Feature readiness | `ml/research/build_feature_readiness.py --check` | up to date (12 features) |
| Visual regression | `scripts/visual_regression.py` | see §6 |

The 24 SQLite skips are the same PostgreSQL-gated set Phase 32 documented
(`docs/PHASE32_SKIPPED_TESTS.md`); the PostgreSQL run exercises every one of them.

**New browser coverage.** `e2e/mission.spec.js` gains one test that runs on all three viewports and
proves the chamber view actually works, not just that it renders:

* it orbits and asserts the projection changed (the frame geometry is a pure function of
  azimuth/elevation/zoom, so an unchanged polygon means nothing moved);
* it zooms and asserts the geometry changed again;
* it resets and asserts it returns to the exact home geometry;
* it orbits from the keyboard (`ArrowRight`, then `Home`) on the focused SVG;
* it inspects `lighting` and `sensors` and asserts the legend text, including "configured setpoints,
  not sensor measurements";
* it switches to the 2D schematic and back and asserts both views;
* it fails on any `pageerror`.

No test was deleted, skipped or relaxed. The pre-existing assertion
(`img "Schematic of the growth chamber"` after toggling the switch off) still passes unchanged,
because the 2D schematic is still there and still what the switch turns off.

## 6. Visual change, measured

The layout is not supposed to move: same panel, same place, same legend, same caption. That is a
claim, so it was measured against a build of the parent commit.

* A worktree at `bcd4ec5` was built and served alongside this branch.
* The mission dashboard was captured at 1440 px on both builds: **identical canvas size,
  1440 × 1649**, and **0.0351 % of pixels differing** (833 pixels, all inside the chamber artwork).
  Leaf-level rasterisation, not layout.

The committed `docs/screenshots/mission-*.png` baselines are older than that and no longer match
the current layout — they were last written in a "restore cross-platform browser test execution"
commit and their canvases differ from what the suite produces today by hundreds of pixels of
height. That is pre-existing staleness, **not** something this phase introduced, and refreshing
those three baselines would have required claiming a layout change that did not happen. They were
therefore left alone, and the honest comparison is the parent-build one above.

The chamber itself is re-baselined deliberately, because the chamber is exactly what this phase
redesigned:

| File | What it shows |
| --- | --- |
| `docs/screenshots/digital-twin.png` | the chamber view at 1200 px, nominal scenario |
| `docs/screenshots/phase33/chamber-view-desktop.png` | same, full panel |
| `docs/screenshots/phase33/chamber-view-mobile.png` | 393 px mobile |
| `docs/screenshots/phase33/chamber-view-water-deficit.png` | water availability set to 25 % in the lab: amber manifold, low tank, `WATER DEFICIT` tag, stressed foliage |
| `docs/screenshots/phase33/schematic-view-desktop.png` | the retained 2D schematic |

## 7. Scientific and API regression

Nothing in this phase touches science, and that is checked rather than asserted:

* **No API change.** `deriveTwinState()` reads only fields the API already returned
  (`dailyGrowthData`, `harvest`, `lifeSupport.water`, `space.factors`, `inputs`, `comparison`); it
  was not extended. The backend test suites — including the OpenAPI/API-consistency tests, the
  FAO-56 and Hargreaves–Samani checks, the no-forecast invariant, the removed-feature absence
  checks, the water rank-only scope and the calibration-claim tests — pass unchanged on SQLite and
  on PostgreSQL.
* **No dataset, artifact, model or calibration change.** Checksums, registry (60/60) and provenance
  (9 artifacts) are identical to `bcd4ec5`. No retraining, no new data, no threshold moved.
* **No new claim in the UI.** The chamber still states, in the panel itself, that plant shapes are
  illustrative, that the animated flow is illustrative, and that the environmental numbers are
  configured setpoints rather than sensor measurements. The subtitle drops the word "3D" because the
  view is no longer 3D — it now reads "Digital-twin visualization · driven by the simulation
  outputs, not by a model of its own".
* **Navigation** keeps the same route and position; only the label `3D greenhouse` became
  `Growth chamber`, since the app no longer renders a 3D greenhouse. Historical phase documents
  that describe the 3D greenhouse are left as written — they are records of those phases, not
  current documentation.

## 8. Known limitations and honest gaps

* **The view is a projection, not a model.** Plant shapes, leaf counts and droplet motion are
  illustrative; nothing in `GrowthChamberView.jsx` computes growth, water or gas exchange. This is
  the same statement the 3D scene made and it is still printed in the panel.
* **No depth sorting beyond tray order.** Painter's ordering is by tray, far to near, which is
  correct for the fixed tier layout. A plant that leaned far outside its tray could be drawn over a
  nearer tray; nothing in the current data makes that happen.
* **SMIL, not CSS or JS animation.** Every current browser supports it and the e2e suite exercises
  the resulting DOM, but if a future engine drops SMIL the animation degrades to a still frame — the
  view itself keeps working, since no geometry depends on it.
* **The three committed dashboard baselines are stale** (§6). Left stale rather than refreshed,
  because refreshing them would record a layout change this phase did not make. Flagged here so the
  next phase decides deliberately.
* **`npm ci` needs network.** Stated because two earlier sandbox resets made an offline-install
  assumption look safe; it is not a property of the code.
* **Test environment re-created for this run.** The sandbox reset again, so the Python venv
  (including `openpyxl`, which two dataset-reproducibility tests need and which is not in
  `requirements*.txt`), PostgreSQL 17.11 and chromium were rebuilt from scratch before the suites
  ran. First SQLite run failed exactly those two tests for the missing `openpyxl`; after installing
  it, both passed and the full suite was re-run clean. Nothing in the repository changed for this.

## 9. Commits

| Commit | Contents |
| --- | --- |
| `feat(frontend): replace three.js growth chamber with an SVG chamber view` | `GrowthChamberView.jsx`, the rewired `DigitalTwin3D.jsx`, `twinState.js` capability helpers removed, `src/three/` deleted, `vite.config.js` chunk groups, `package.json` + lockfile, tightened `check-bundle.mjs`, the new browser test |

Further commits in this phase carry the layout polish, the documentation set and the baseline
refresh. The exact SHAs and the merged `main` SHA are recorded in `docs/PHASE33_DELIVERY.txt`.
