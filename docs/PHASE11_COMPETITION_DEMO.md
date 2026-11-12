# Phase 11 — competition demo

One command, seven steps, and the last four numbers are negative on purpose. The demo is
built for someone with five minutes and a healthy suspicion.

```bash
./scripts/demo_phase9.sh          # full: verifies sources, retrains, checks checksums, live API
./scripts/demo_phase9.sh --fast   # skips retraining, reads the committed state (~5 s)
```

The script keeps its old name because earlier documents reference that command line; its
content is now Phase 11.

---

## 1. Measured timing

| Run | Wall clock | What it does |
| --- | --- | --- |
| `--fast` | **~5 s** | checksums of pinned source files, metric assertions, 47 targeted tests, all evidence steps, live API |
| full | **~11 min** | everything above plus a deterministic retrain of both served models |

The full run is slower for one reason only: it refits the radiation models from the pinned
NASA matrices. Nothing else in the demo trains.

---

## 2. The pipeline-order bug this phase found and fixed

The full run **failed** before Phase 11, and the failure was instructive:

```
== 4/7 Verify registry checksums and run the scientific test suite
ValueError: Model checksum verification failed: radiation-quality-osd46-v1
```

Every metric had reproduced. The gate still refused, because the retrain step wrote fresh
artifacts but:

1. `train_radiation_osd46.py` does not write the Phase 10 explanation metadata, so
   retraining **silently dropped** `explanationMethod`, `explanationArtifact`,
   `explanationAvailable` and `explanationIsSurrogate` from both artifacts;
2. the registry was never rebuilt, so its checksums described files that no longer existed.

The fix is an ordering, not a metric: **train → explain → build_registry → verify**. With
that order the full run passes and the diff between committed and regenerated artifacts is
exactly two things — `trainedAt`/`generatedAt` timestamps and the resulting SHA-256 values.
Every measured number is bit-identical:

| Artifact | Fields that differ after a full retrain |
| --- | --- |
| `ml/evaluation/phase9_osd46_radiation` | 2 — the two artifact SHA-256s |
| `ml/evaluation/phase10_explanations` | 1 — `generatedAt` |
| `ml/artifacts/radiation-quality-osd46-v1` | `trainedAt` only |
| `ml/artifacts/radiation-exposure-osd46-v1` | `trainedAt` only |

This is the difference between "the demo works on my machine" and "the demo works from a
clean checkout": a competition judge who runs the full path now gets a passing gate instead
of a checksum error.

---

## 3. What each step shows

**1. Provenance.** Every NASA source file is matched against a pinned SHA-256. Failure here
means the data is not the data.

**2. Retrain** (full mode only), in the order above.

**3. Committed metrics still hold.** Balanced accuracy 0.898 (quality) and 0.910 (exposure)
with p = 0.0099 over 22 biological groups, asserted against the artifact rather than trusted.

**4. Registry checksums and 47 scientific tests**, including the claims-guard tests that
fail if a served model starts claiming something it cannot support.

**5. The Phase 10 audit trail**: interval coverage, the corrected cross-study reading, the
dose exclusions, and the OSD-314 partial-gravity signal that is deliberately **not** served.

**6. The Phase 11 evidence** — the step that exists to show honest negatives:

```
OSD-346 gravity: osd346-gravity-signal-is-not-separable-from-flight-run
  signal survives removing the flight run: False
dataset sweep: 231 of 231 studies with a usable matrix, 0 metadata failures
  harvest or biomass candidates: 0 (zero, so the mizuna harvest gap cannot be closed)
  new microbial candidates: 9, none a crop load campaign
  OSD-320 is a second deposit of OSD-46: 44 arrays, 22810 probesets,
  minimum r 1.000000, maximum |diff| 0.0
radiation-quality-osd46-v1: shipped 0.8981 reproduced exactly ->
  nested re-selection 0.8611 (delta -0.0370), promoted False
radiation-exposure-osd46-v1: shipped 0.9097 reproduced exactly ->
  nested re-selection 0.9097 (delta +0.0000), promoted False
OSD-782 dose: dose-is-not-recoverable-at-this-sample-size
  within-timepoint rho +0.2240 (p=0.15792), sign flips at 3 h
microbial flight effect: pooled +2.820 (95% CI +2.327 to +3.314),
  prediction interval for a NEW campaign -0.377 to +6.018 - it includes zero, on purpose
OOD novelty score: ood-score-not-validated-by-any-available-control
  mahalanobis_pca                passes 1 of 3 controls
  nearest_neighbour_correlation  passes 2 of 3 controls
  threshold validated: False
```

**7. Live API**, ending on the refusals:

```
partial vector -> HTTP 422 (expression-feature-mismatch, missing 149 genes)
lettuce explanation -> HTTP 404 (no valid method, no stub)
```

Those two lines are the demo's best moment. A system that answers everything is not
verifiable; one that refuses a partial gene vector and refuses to invent an explanation for a
tree ensemble is.

---

## 4. Why the negatives are the pitch

A judge who has seen many demo pipelines expects every panel to be green. The four negatives
here — no promotion, dose unrecoverable, prediction interval spanning zero, OOD unvalidated —
are the evidence that the positive claims were earned rather than asserted.

The strongest single line in the demo is the one that costs the project a model:

> **`OSD-320` is a second deposit of `OSD-46` — 44 arrays, 22,810 probesets, minimum r
> 1.000000, maximum |diff| 0.0.**

A pipeline that accepted OSD-320 as an independent radiation study would have reported a
perfect-score cross-study replication from a study compared against itself. Phase 11 found
it, excluded it, and built a duplicate detector so the next one is caught automatically.

---

## 5. Status

| Item | Classification |
| --- | --- |
| Single-command demo, seven steps | **Completed** |
| Committed metrics asserted rather than trusted | **Completed** |
| Full-retrain path passes its own checksum gate | **Completed** (was failing; ordering fixed) |
| Phase 11 evidence exposed in the demo | **Completed** |
| Deployment | **None** — the demo never deploys and the phase does not deploy |
| Network use | Local API only |
