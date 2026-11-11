# Final frontend report

The frontend was audited for behaviour under failure, not only for appearance. Two real defects were
found and fixed; the design language, the navigation, the route set and the Phase 33 dependency-free
SVG chamber are unchanged, and the initial bundle is unchanged at 240 kB.

## 1. UI states — every request now says what it is doing

The app has one data hook (`useResource`) and one visible-state component (`RequestState`). The audit
walked every page that issues a request and asked two questions: does a failure surface, and does a
loading state exist without displacing content?

| Page | Requests | Failure visible before | Failure visible now |
|---|---|---|---|
| `Benchmarks` | `/benchmarks` + `/external-validation` + `/closed-loop` | only the main one | all three (§2) |
| `ModelComparison` | `/models` + `/external-validation` | only the main one | both (§2) |
| `Account`, `Advisor`, `Analytics`, `Comparison`, `Evidence`, `GuidedWorkflows`, `ResearchAssistant`, `ScientificWorkflow`, `WaterEvidencePanel`, `sciencePanels` | all through `RequestState` | yes | unchanged |
| `EarthLettucePrediction`, `RadiationTranscriptomicPrediction`, `MissionPlatform` | user-triggered `api()` calls | yes — `try/catch`, error rendered in an alert region, `busy` resets in `finally` | unchanged |
| `MissionPlatform` shell | `/config`, `/simulate`, `/datasets` | yes, with `aria-busy` on `.simulation-content` | unchanged |

`RequestState` gained one prop, `secondary`. A secondary resource (one that annotates a page rather
than being its subject) stays quiet while it loads — otherwise a page would show two skeletons — and
still reports an error. That is the whole change; no other component's behaviour moved.

## 2. The defect: a failed request removed a panel silently

```jsx
{external.data && <ExternalValidation body={external.data} />}
```

`useResource` sets `data: null` when a request fails, so this pattern deleted the panel and left no
trace. On `/#benchmarks` and `/#models` the missing panel is the one that carries the **failed external
check** for the lettuce models. A network error therefore made a failed evaluation disappear from the
two pages whose job is to show it — the opposite of the product's own rule.

Fixed by rendering those three resources through `<RequestState … secondary />`. New
`frontend/e2e/degraded.spec.js` cuts `/api/external-validation` out of the network with
`page.route(..., route => route.abort())` and asserts:

1. the main benchmark card still renders (one bad endpoint must not take the page down);
2. a `role="alert"` banner is visible;
3. the interception fired, so the test cannot pass vacuously.

The counterfactual was run: removing the `<RequestState state={external} secondary />` line makes the
test fail on `expect(banner).toBeVisible()`. The test is load-bearing.

## 3. Bundle — before and after

Measured by `node scripts/check-bundle.mjs` after `npm run build`, on the starting tree and on the
delivered tree.

| | Starting tree (`44d863c`) | Delivered tree |
|---|---|---|
| initial request (index.html static graph) | 240 kB / 3 modules | **240 kB / 3 modules** |
| exact bytes / budget | — | **245 535 B of 245 760 B** (99.91 % of the budget) |
| initial chunks | `vendor-react`, `index`, `vendor-icons` | same three |
| gzip of the initial request | ≈ 79 kB | 78 957 B (`vendor-react` 60 378, `index` 11 997, `vendor-icons` 6 582) |
| largest chunk | `vendor-charts`, 393 kB, **lazy** | same, still lazy |
| chunks above the 500 kB budget | none | none |
| import cycles | none | none |

`chunkSizeWarningLimit` was not raised, no warning was suppressed, `build:check` was not relaxed, and
`vendor-charts` remains lazy. The new Playwright spec is 2.5 kB of test code — it is not part of any bundle.

The budget has 225 bytes of headroom. That is reported rather than fixed by adding a byte of padding:
the number is the requirement, and the next component that wants to grow the initial path has to be
lazy instead.

## 4. Accessibility

Measured, not asserted — `frontend/e2e/accessibility35.spec.js`, at desktop, tablet and mobile:

| Property | Result |
|---|---|
| Contrast, computed foreground against the first opaque ancestor background, on five routes | pass 12/12; worst measured ratio **4.97:1** (`nav-label`, 11 px) against a 4.5:1 requirement |
| `prefers-reduced-motion: reduce`: no non-`none` animation, no non-zero transition, SVG chamber still renders | pass 12/12 |
| Keyboard-only journey: skip link is the first tab stop; a sidebar route is reachable and activates on `Enter`; focused element paints an outline ≥ 1 px | pass 12/12 |
| Chart and chamber semantics: `role="img"` with an accessible name | pass 12/12 |

No accessibility change was needed in this pass and none is claimed. The properties were already true
and were made measurable in Phase 35; this pass re-ran them on the delivered tree.

The new degraded-network banner reuses the existing `.error-banner` element, which already has
`role="alert"` and is already contrast-tested on the routes above; the assertion in the new spec checks
the role explicitly rather than assuming it.

## 5. Responsive behaviour

`/#benchmarks` no longer scrolls sideways at 820 px or 412 px (fixed in Phase 35 with
`min-width: 0` + `overflow-wrap: anywhere`, both required and both measured). This pass re-asserts the
document-width invariant in `e2e/screens.spec.js` at all three viewports and it passes.

## 6. What did not change

* the design language, the navigation model, the route names and the hash URLs;
* the Phase 33 SVG growth chamber (no framework, no three.js, no new dependency);
* every API contract — the frontend consumes the same payload shapes, and no backend response field
  was renamed, removed or added in this pass;
* user data and scenario storage;
* the five-way labelling of numbers (measured / predicted / derived / setpoint / unavailable).

`npm ls --depth=0` shows no dependency added in this pass; `npm audit` reports 0 vulnerabilities across
312 dependencies (45 prod, 267 dev).
