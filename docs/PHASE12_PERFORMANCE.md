# Phase 12 — performance

Measured on the sandbox that built Phase 12 (in-process TestClient, so the numbers are
application time and exclude network). They are reported to show that the new layer is not
expensive, not to claim a production SLA.

---

## 1. Endpoint latency

25 iterations per endpoint after one warm-up call; median and p95 in milliseconds.

| Endpoint | Median | p95 | Note |
| --- | --- | --- | --- |
| `POST /api/assistant/ask` | 4.3 ms | 4.8 ms | BM25 over 47 passages, corpus cached |
| `POST /api/workflow/run` (lettuce v2) | 4.8 ms | 5.4 ms | validate + infer + interpret + evidence |
| `GET /api/workflow/models` | 4.0 ms | 4.6 ms | 8 models, registry cached |
| `GET /api/explorer/overlaps` | 4.6 ms | 5.4 ms | 325 pairwise relations |
| `GET /api/explorer/datasets/{id}` | 4.1 ms | 4.8 ms | row + its relations |
| `GET /api/models` (pre-existing) | 10.4 ms | 13.3 ms | unchanged baseline |
| `POST /api/simulate` (pre-existing) | 5.6 ms | 8.1 ms | unchanged baseline |

The new endpoints sit in the same range as the pre-existing read paths. No Phase 12 endpoint
is slower than `/api/models`, which it also calls.

---

## 2. One real performance defect, found and fixed

`GET /api/explorer/overlaps` initially took **67 ms** (median), roughly 15× the rest of the
API. The cause was not the pairwise scan itself but that `dataset_rows()` rebuilt the
manifest rows, the registry lookup and the `usedByModels` search **for every pair**, i.e.
325 times per request.

Fix: memoise the row set (`lru_cache` over a tuple) and reuse it for the relation table.

```
before: median 67.4 ms   p95 70.2 ms
after:  median  4.6 ms   p95  5.4 ms
```

The cache is keyed on nothing because the underlying data is committed artifacts that cannot
change at runtime; a test asserts the relation counts are still correct after the change
(1 duplicate, 1 shared-sample, 31 unverified over 26 accessions).

---

## 3. Corpus build

| Operation | Cost |
| --- | --- |
| Cold build of the 47-passage corpus (first call, includes JSON reads) | **43 ms** |
| Subsequent calls | 0.001 ms (memoised) |
| Quarantine screening | included in the cold build; 0 documents quarantined |

The corpus is built once per process, on first use, not at import: a cold start does not pay
for it unless someone asks the assistant something.

---

## 4. What is bounded, by design

| Bound | Value | Why |
| --- | --- | --- |
| Question length | 400 characters | Bounds retrieval work and prevents document-sized input |
| Claims per answer | 5 | Keeps an answer readable and each sentence checkable |
| Quote length | 400 characters | Prevents one passage dominating a response |
| Passages | 47 | The corpus is the repository's verified artifacts, not a crawl |
| Saved analysis payload | 200 000 bytes | Bounds storage per record |
| Request body | 64 KiB | Pre-existing guard |
| Requests | 180/min/IP general, 30/min auth, 12/min optimize | Pre-existing guard |
| Missing/unexpected feature names echoed | 20 each | Bounds error payloads for a 30 000-gene input |

---

## 5. Test-suite cost

| Suite | Time | Count |
| --- | --- | --- |
| Backend `pytest -q` | ~13 s | 377 passed, 1 skipped |
| Browser `playwright test` (desktop, tablet, mobile) | ~78 s | 39 passed |
| `scripts/verify_model_registry.py` | <1 s | 40/40 checks |
| `scripts/demo_phase12.py` | ~1.2 s | 4 refusals + citation trail |

Phase 12 added 87 backend tests and 12 browser tests. Backend runtime grew by roughly 2 s and
the browser run by roughly 25 s (the new spec is 12 tests over three viewports); nothing in
the suite became slow enough to discourage running it.

---

## 6. Frontend

`npm run build` completes in ~6.3 s with the existing chunk-size warning (unchanged from the
Phase 11 baseline: the bundle was already above 500 kB before Phase 12). The new modules are
lazily imported through the existing `PlatformModules` `lazyExport` path, so
`ResearchAssistant.jsx` and the two new panels do not enter the initial bundle.
