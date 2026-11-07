# Phase 9 baseline

Recorded before any Phase 9 change, so every claim later in this phase can be
compared against a fixed starting point.

## Repository state

| Item | Value |
| --- | --- |
| Branch point | `9669553` (`main` after the Phase 8 merge) |
| Phase 9 branch | `feat/phase9-nasa-ai-expansion` |
| Registered models | 6 |
| Backend tests | **212 passed** |
| Frontend | lint, `tsc --noEmit` and `vite build` clean |
| Browser suite | 15 tests green on desktop, tablet and mobile |
| PostgreSQL | 17, local cluster on port 55432, test database `spaceagrisim_test` |

## Registered models at baseline

| Model | Source | Task |
| --- | --- | --- |
| `lettuce-earth-growth-v1` | WUR / 4TU Earth chamber data | fresh shoot mass regression |
| `lettuce-earth-growth-v2` | same, gradient-boosted successor | fresh shoot mass regression |
| `mizuna-harvest-v1` | VEG-04A/B | harvest mass regression |
| `mizuna-microbial-load-v1` | NASA OSD-780 plate counts | microbial load regression |
| `mizuna-microbial-relative-load-v2` | NASA OSD-780, within-campaign | relative load regression |
| `tomato-flight-response-v1` | NASA OSD-767 | flight/ground context classification |

Every one is a plant- or plate-level measurement model. None of them is a
transcriptomic model, which is the gap Phase 9 was asked to close.

## What was already known to be weak

These were carried into Phase 9 as open problems rather than accepted limits:

1. **No molecular-response model existed.** The only classification model
   (`tomato-flight-response-v1`) separates experiment context, not a biological
   response, and its own metrics are modest.
2. **OSDR REST access was believed blocked.** Prior phases used hand-placed files;
   there was no repeatable, checksum-verified acquisition path.
3. **Dataset claims were not systematically evidenced.** The candidate list came
   from prior inspection of roughly 25 studies, not from a sweep.
4. **No leakage tests existed.** Group-aware splitting was implemented inside
   training scripts but never asserted by the test suite.
5. **Browser screenshots overwrote their own baselines**, so visual regression was
   structurally impossible: the capture step wrote into `docs/screenshots/`, the
   same directory holding the committed baselines.

## Requirements Phase 9 was measured against

From the phase brief, in the order they gate work:

- discover and verify NASA datasets across four priorities, with a **ranked
  eligibility table** and exact rejection reasons;
- build **only scientifically defensible models**, with group-aware splits,
  in-fold feature selection, experiment-held-out testing, baselines, confidence
  intervals, calibration and finite-sample corrected permutation p-values;
- **model count is not a success metric** — fewer, well-validated models preferred;
- expose models through the existing registry and prediction UI with **no visual
  redesign**;
- answer the eleven competition questions and provide a reproducible demo;
- test scientific invariants, checksums, registry integrity and UI visual
  regression;
- **no deployment** to Render or any production host.

The last point is a scope boundary, not a limitation: nothing in Phase 9 is
deployed, and no result here claims production verification.
