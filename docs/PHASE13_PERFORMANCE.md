# Phase 13 — Performance: Measured, Not Assumed

Artifact: `ml/evaluation/phase13_performance`
Runner: `python3 scripts/benchmark_api.py --write`
Environment: in-process Starlette `TestClient`, single sandbox CPU, 25 iterations per route after
one warm-up.

> **These are not production latency figures.** No network, TLS, container, cold start, shared
> database or multi-tenant load is involved. They exist to detect accidental per-request cost and
> to make a before/after comparison reproducible. The artifact says so in its own `caveat` field,
> because a number copied out of a JSON file loses its context faster than a document does.

---

## 1. Baseline measurement (before any change)

| Route | median | p95 | response |
|---|---|---|---|
| `GET /api/health` | 3.5 ms | 4.0 ms | 62 B |
| `POST /api/assistant/ask` (direct) | 5.4 ms | 5.9 ms | 5.9 KB |
| `POST /api/assistant/ask` (comparison) | 7.4 ms | 8.8 ms | 4.4 KB |
| `POST /api/assistant/ask` (multi-hop) | 6.3 ms | 6.8 ms | 3.3 KB |
| `POST /api/assistant/ask` (refusal) | 4.8 ms | 5.5 ms | 1.0 KB |
| `GET /api/assistant/corpus` | 3.6 ms | 4.9 ms | 211 B |
| `GET /api/workflow/models` | 4.7 ms | 5.9 ms | 12.6 KB |
| `POST /api/workflow/validate` | 3.7 ms | 4.0 ms | 487 B |
| `POST /api/workflow/run` | 7.1 ms | 7.9 ms | 8.0 KB |
| `POST /api/simulate` | 5.7 ms | 7.6 ms | 27.1 KB |
| `GET /api/datasets` | **17.1 ms** | **23.1 ms** | 62.2 KB |
| `POST /api/explorer/independent-set` | 3.9 ms | 5.2 ms | 544 B |

`/api/health` at 3.5 ms is the floor: that is TestClient and framework overhead on this machine,
so the interesting quantity is the difference from it.

## 2. The one change that was made

`/api/datasets` was the only route far above the floor. The route rebuilt 20 dataset rows — string
joins, per-row file counting, duplicate-safeguard lookups — from the manifest on **every** request.
Measured in isolation: 9.45 ms to rebuild, 0.001 ms from cache.

The rows are now cached per query string (`lru_cache`), which is safe because the assembled rows are
read-only and the manifest underneath is already cached. The response is identical — the existing
explorer tests pass unchanged.

| Route | before | after |
|---|---|---|
| `GET /api/datasets` | 17.1 ms median / 23.1 ms p95 | **13.9 ms median / 19.1 ms p95** |

## 3. What the measurement then said — and what was not done

After the cache, `/api/datasets` is still the slowest route at 13.9 ms median. Of that, ~3.6 ms is
framework overhead and ~0.001 ms is the rebuild, so **the remaining cost is serialising a 62 KB
response**, not computing it.

That cannot be fixed without changing what the endpoint returns: pagination or field selection. That
is a product decision with real consequences (a client that expects all 20 datasets would break),
so it is recorded as the next step rather than done quietly during a hardening phase. The honest
summary is that the route was doing repeated work, that work is gone, and the rest of its cost is
the response itself.

## 4. Where the assistant's cost is

The assistant's own benchmark (`ml/evaluation/phase13_assistant_eval`) times the composer
without HTTP: **median 1.24 ms, p95 3.28 ms** across 32 questions. Through the API the same class
of question costs 5–12 ms, i.e. framework and serialisation dominate retrieval and composition.
This is why there is no index, no vector store and no cache in the assistant: at 47 passages,
retrieval is not the bottleneck, and adding infrastructure would trade a measurable simplicity for
an unmeasurable speed-up.

Comparison questions are the most expensive (11.8 ms through the API, 3.5 ms in-process before the
llm commit) because they run three retrievals instead of one. That is the cost of not answering half
a question.

## 5. Frontend

`npm run build` output on this branch:

| Asset | size | gzip |
|---|---|---|
| `index-*.js` | 599.5 kB | 183.8 kB |
| `GrowthChamberScene-*.js` (lazy) | 922.2 kB | 247.8 kB |

The 3D scene is already a lazy route chunk, so it is not on the critical path for any page that
does not open the greenhouse. Vite warns that both chunks exceed 500 kB — a real observation, and
not fixed here, because splitting further means restructuring `three`/recharts usage rather than
moving a boundary. Recorded, not claimed as done.

## 6. Reproducing

```bash
python3 scripts/benchmark_api.py --write              # 12 routes, raw samples in the artifact
python3 scripts/evaluate_assistant.py --write        # assistant latency, 32 items
cd frontend && npm run build                         # chunk sizes
```

The artifact keeps the raw per-iteration samples, so a later run can be compared sample-to-sample
rather than against a remembered median. Note that the script raises the in-process rate limit for
its own run (recorded as `rateLimitRaisedForBenchmark: true`); without that it would measure 429
responses instead of routes.
