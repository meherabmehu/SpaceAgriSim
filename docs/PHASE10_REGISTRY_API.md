# Phase 10 — registry and API pass

A registry that drifts from its artifacts is the most dangerous failure mode in this
repository: a number in `registry` that no artifact backs survives every test that
only checks the endpoint returns 200.

`ml/training/phase10_registry_api_audit.py` therefore does not trust the registry. It
reads the artifact each entry points at and checks eight things per model:

| Check | What it catches |
| --- | --- |
| identity | artifact missing, or its SHA-256 no longer matching the recorded digest |
| metrics | a metric in the registry absent from the artifact, or differing from it |
| status | an excluded candidate being served, or a served model being a rejected one |
| intervals | a stated nominal coverage with a measured coverage far below it |
| explanations | an explanation whose contributions do not reconstruct the served logits |
| capability | an explanation artifact on disk that the registry does not advertise |
| catalogue | a model citing a study absent from the dataset manifest |
| API | `/api/models` disagreeing with the registry; an excluded model reachable; a surrogate explanation served for a tree ensemble |

Result: **8 models, 0 findings, 0 high severity.**
`ml/evaluation/phase10_registry_api_audit`.

## What the pass actually found

Two real gaps, both now fixed, both in the direction the audit was built to catch — the
registry understating what exists:

- **`phase10.explanationAvailable` was missing** from both radiation artifacts even
  though `ml/artifacts/<id>-explanation.py` has existed since `68833ac`. The registry
  therefore advertised no explanation capability for the only models that have one.
  Both artifacts now carry the field with `explanationIsSurrogate: false` and their
  recorded SHA-256 was updated in `ml/artifacts/registry`.
- **`verify_model_registry.py` counted explanation files as orphan models**, failing one
  of its 40 checks since the XAI commit. Explanation files live beside their models so
  a model checksum keeps meaning "the trained model"; the check now excludes them.
  It reports **40/40 passed**.

Neither fix touches a metric, an interval radius, or a status. Nothing was reconciled
silently: the audit fails on drift instead of repairing it, and the repairs above are
explicit committed changes.

## API surface, verified

| Surface | Result |
| --- | --- |
| `GET /api/models` | exactly the 8 registered models |
| `GET /api/models/{id}` for the two excluded candidates | **404** |
| `GET /api/models/radiation-*/explanation` | 200, exact attribution, identity residual ≤ 8.9e-16 |
| `GET /api/models/lettuce-earth-growth-v2/explanation` | **404** — no valid method, no surrogate |
| `POST /api/predict/{id}` with a partial gene vector | **422** with the missing gene count |
| `GET /api/models/{id}/reference-profiles` | 200, labelled as a synthetic centroid |
| `GET /api/datasets?q=OSD-314` | 200, `status: analysed-not-served`, `gravityLevelsG: [0.0, 0.34, 1.0]` |

## Guarded by test

`backend/tests/test_phase10_dose_gravity.py` asserts the audit stays clean and that the
two capability gaps remain fixed, so the audit cannot be regenerated against a drifted
registry without a test failing first.
