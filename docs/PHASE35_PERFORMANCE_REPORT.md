# Phase 35 — Performance report

The budget did not move. `build:check` enforces the same limits as in Phase 34: initial request
≤ 240 kB, no chunk above the configured ceiling, no import cycles. Nothing was suppressed, no
`chunkSizeWarningLimit` value was touched, and no warning was filtered.

## Initial load — before and after

Measured with `npm run build` on the parent commit (`0f01f31`, rebuilt in a worktree) and on this
branch, same Node and Vite versions.

| Module | Parent (0f01f31) | This branch | Δ |
|---|---|---|---|
| initial request (index.html static graph) | 240 kB, 3 modules | 240 kB, 3 modules | 0 |
| `index-*.js` | 34 324 B (11.94 kB gzip) | 34 324 B (11.94 kB gzip) | 0 |
| `vendor-react-*.js` | 192.91 kB (60.52 kB gzip) | 192.91 kB (60.52 kB gzip) | 0 |
| `vendor-icons-*.js` | 18.31 kB (6.56 kB gzip) | 18.31 kB (6.56 kB gzip) | 0 |
| `index-*.css` | 54.53 kB (12.99 kB gzip) | 54.53 kB (12.99 kB gzip) | 0 |

## Lazy chunks

| Chunk | Parent | This branch | Δ | Why |
|---|---|---|---|---|
| `vendor-charts` | 402.65 kB (115.99 kB gzip) | 402.65 kB (115.99 kB gzip) | 0 | untouched, still lazy |
| `Evidence` | 23 204 B (7.6 kB gzip) | 25 580 B (8.19 kB gzip) | **+2 376 B** | the evidence badge, the measured-reason sentence and the computed status prose |
| `DigitalTwin3D` | 25.64 kB | 25.64 kB | 0 | the dependency-free SVG chamber is unchanged |

The entire Phase 35 interface change costs **2.4 kB**, and it is in a lazily-loaded chunk, so the
first paint is byte-for-byte the same size as before.

## Chart dependency

Investigated again, no change made. `vendor-charts` (Recharts plus its d3 subtree) is loaded only by
routes that plot data, and the dependency-free SVG chamber means the dashboard does not need it. It
is already a separate chunk reached through a dynamic import; the only way to reduce it further is to
drop a chart type the product uses. That would remove functionality to move a number, which the
phase's rules forbid. The 240 kB initial figure is therefore a real budget, not a shim: it covers the
shell, React, icons and the route code.

## Runtime

* No new network request was added on any route. The verdict travels inside the existing prediction
  and `/api/workflow/models` responses.
* One request was *removed* in effect: the status panel no longer needs a separate call to know a
  model's calibration, because the verdict block already carries it.
* The benchmark page fix (`min-width: 0` + `overflow-wrap: anywhere`) removes a horizontal scroll
  container that was forcing layout of a 903 px document inside an 820 px viewport on every resize.
* No render-hot-path change: the badge is computed once per card from data already fetched.

## Verification commands

```
cd frontend && npm run build          # bundle table above
cd frontend && npm run build:check    # "initial request within budget"
```
