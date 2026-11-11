# Phase 35 — Accessibility report

Accessibility was previously asserted structurally (one `h1`, named controls, a skip link, no
horizontal overflow on `/#workflow`) at three viewports. This phase measured the three properties
that were claimed but never tested, and fixed the one real responsive failure the new tests found.

## What was added — `frontend/e2e/accessibility35.spec.js`

| Test | What it measures | Result (desktop / tablet / mobile) |
|---|---|---|
| Text contrast | Computed foreground against the first opaque ancestor background, walking through transparent parents; every visible text-bearing element on five routes (`dashboard`, `predictions`, `benchmarks`, `datasets`, `laboratory`) must reach 4.5:1 | **pass, 12/12** — worst measured ratio 4.97:1 (`nav-label`, 11 px) |
| Reduced motion | Under an emulated `prefers-reduced-motion: reduce`, no element may keep a non-`none` animation or a non-zero transition; the SVG chamber must still render | **pass, 12/12** |
| Keyboard-only journey | Skip link is the first tab stop; a sidebar route is reachable with focus and changes the page on `Enter`; the focused element paints an outline ≥ 1 px | **pass, 12/12** |
| Chart and chamber semantics | `role="img"` with an accessible name on the growth plot and the chamber | **pass, 12/12** |

These same tests were run against the parent commit in its worktree and also pass 12/12, which is the
honest finding: **the accessibility properties were already satisfied and were simply unmeasured.**
No product change was needed for them.

## The responsive failure that was found

The new route assertions in `e2e/screens.spec.js` found a real defect on `/#benchmarks`:

| Viewport | Document width | Viewport | Overflow |
|---|---|---|---|
| desktop 1440 | 1440 | 1440 | none |
| tablet 820 | **903** | 820 | +83 px, page scrolled sideways |
| mobile 412 | **526** | 412 | +114 px |

Cause: a benchmark row's citation is 118 characters long; grid items default to `min-width: auto`, so
the first track refused to shrink below its longest content, and a long DOI token then refused to
break. Fix in `frontend/src/styles/platform.css`:

```css
.bench-row > *,
.bench-legend > * { min-width: 0; overflow-wrap: anywhere; }
```

Both properties are required and that was measured in the browser, not assumed: `min-width: 0` alone
left the document at 903 px; `overflow-wrap: anywhere` alone left it at 903 px; the pair returns
820 px and 412 px. The defect existed on the parent commit as well.

## Carried forward

* **No automated WCAG conformance claim.** No axe-core or equivalent was added — a rule engine is a
  new dependency and a new supply-chain surface for a project whose accessibility checks are
  deliberately hand-written. This report therefore describes measures, not conformance.
* **Focus-visible styling** is asserted as an outline on one navigation control, not on every
  interactive element.
* **Screen-reader narration** of the new verdict sentence is plain text inside a `role="note"`
  paragraph; it has not been tested with a real screen reader in this environment, and this report
  does not claim it was.
