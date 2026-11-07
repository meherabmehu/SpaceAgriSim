# Phase 8 — Performance

One real defect was found and fixed. Everything else was measured and left alone,
including the slowest endpoint, because "slow" and "worth changing" are different
questions.

---

## The defect

`research.load_model` was decorated `@lru_cache(maxsize=4)` while the registry held
**five** models. Demonstrated on the baseline commit, in a fresh process:

```
after one GET /api/models:  CacheInfo(hits=0, misses=5, maxsize=4, currsize=4)
after two GET /api/models:  CacheInfo(hits=0, misses=10, maxsize=4, currsize=4)
```

`hits=0` after two full passes. Every request re-read and re-hashed about 1 MB of
JSON artifacts, evicted an entry it had just inserted, and never reused anything.
The cache was not merely undersized; it could not reach a working set, so it did
nothing at all while still paying the bookkeeping cost.

Phase 7 caused this by raising the registry from four models to five and not
revisiting the decorator.

### Fix

The size is now derived from the data rather than hard-coded:

```python
@lru_cache(maxsize=len(MODEL_IDS))
def load_model(model_id):
```

Adding a model can no longer silently reintroduce the thrash; the size follows the
registry on its own. A test asserts `maxsize >= len(MODEL_IDS)`, that a second full
pass produces only hits and no misses, and that `/api/models` twice in a row does
not increase the miss count.

## Measured effect

Isolated A/B on the same machine — `git worktree` at `fe6bbe2` versus the Phase 8
branch, fresh process per tree, one warm-up call, 40 iterations:

| | Baseline `fe6bbe2` | After `266c200` |
|---|---|---|
| `GET /api/models` median | **17.97 ms** | **4.55 ms** |
| Cache after two calls | `hits=0, misses=10` | `hits=6, misses=6` |

**3.9× faster**, and the attribution is direct: the counter that was broken is the
counter that changed.

## What was deliberately not optimised

| Endpoint | Median | Disposition |
|---|---|---|
| `POST /api/optimize` | 148 ms | **Left alone.** It evaluates a fixed 81-candidate grid over the engine across three objectives. 148 ms for 81 full simulations is consistent; every optimisation idea available here (caching, approximation, pruning the grid) would change what the endpoint *reports*, not just how fast it reports it. That is a scientific change disguised as a performance change, and it is not authorised. |
| `POST /api/compare` | ~21 ms | Four scenarios, each a full simulation. Linear in scenario count. Fine. |
| `POST /api/simulate` | ~5 ms | Fine. |
| `GET /api/datasets` | ~8 ms | Reads and merges the manifest and candidate list. Not user-facing hot path. |
| `GET /api/science/measurements` | ~4 ms | Fine. |

### A measurement trap worth recording

An early full-sequence run appeared to show `/api/compare` improving from
21.9 ms to 2.6 ms and `/api/simulate` from 5.3 ms to 2.4 ms — an eight-fold
speedup that would have been a great line in a report and was **not real**.
Re-measuring each endpoint in a fresh process on both trees gave 20.73 vs 21.87 ms
for compare and 5.33 vs 5.14 ms for simulate: no change, within noise.

The apparent improvement was an ordering artefact of the harness. Those endpoints
are not reported as improved, and the numbers above are the isolated ones. The
general lesson: an endpoint benchmark that runs many endpoints in one process
measures the process as much as the endpoint.

## Memory and concurrency notes

- The model cache now holds six parsed artifacts plus their trees. The v2 boosting
  artifact is 100 KB on disk, materially smaller than the random forest it sits
  beside, so the cached working set did not grow as much as the model count did.
- `lru_cache` is thread-safe for the CPython builds in use, and the cached values
  are treated as read-only. `predict_tvalues` / `predict_values` do not mutate the
  artifact, so concurrent requests share one parsed model safely.
- No new global mutable state was introduced. `science_classification.FEATURES` is
  module-level and read-only; `classifier_response()` builds fresh dicts per call
  (~2.4 ms, and it is not on any hot path).

## Reproduce

```bash
# baseline
git worktree add /tmp/base fe6bbe2
cd /tmp/base && python -c "..."   # or see docs/phase8/performance_ab.json
# current
cd backend && python -m pytest tests/test_phase8_scientific_integrity.py -q
```

Raw numbers: `docs/phase8/performance_baseline.json`,
`docs/phase8/performance_after.json`, `docs/phase8/performance_ab.json`.
