# Phase 9 AI integration

How the two OSD-46 classifiers are served and shown, and what the integration
deliberately refuses to do.

## API surface

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/predict/radiation-quality-osd46-v1` | control / gamma / HZE |
| `POST` | `/api/predict/radiation-exposure-osd46-v1` | control / irradiated |
| `GET` | `/api/models/{id}/reference-profiles` | per-class centroid vectors |

Both classifiers appear in `GET /api/models` beside the six existing models, so they
are discovered through the generic registry rather than a bespoke path.

### Request contract

```json
{ "expression": { "AT1G01010": 6.42, "AT1G01020": 5.81, "...": 0.0 } }
```

The feature set is **strict**:

- every one of the 150 genes must be present;
- no extra genes are accepted;
- a missing or extra gene returns **422** with counts and the first 20 offenders.

Partial vectors are rejected rather than zero-filled. Zero-filling a microarray
model silently invents measurements, which is the single easiest way to produce a
confident, meaningless prediction.

```json
{
  "detail": {
    "error": "expression-feature-mismatch",
    "missingGeneCount": 149,
    "unexpectedGeneCount": 0,
    "requiredGeneCount": 150
  }
}
```

Non-numeric values such as `"NaN"` are also rejected with 422.

### Response contract

Each prediction carries its own limitations, so a consumer cannot quote the number
without the caveat:

| Field | Content |
| --- | --- |
| `prediction`, `probabilities` | class label and softmax scores |
| `validation` | scheme, accuracy, balanced accuracy, macro F1, baseline, **permutation p-value**, samples, biological groups |
| `batchConfound` | full cross-tabulation plus Cramér's V |
| `supplementaryEvaluation` | batch-controlled re-evaluation where one exists |
| `interval` | `{kind: "none", calibrated: false}` with an explanation |
| `outOfDomain` | true when any gene is outside its observed training range |
| `warnings` | the model caveat, per-gene domain warnings, and every stated limitation |

`outOfDomain` is computed **per gene** against observed training ranges stored in
the artifact, not against one global bound, and the warning names the gene.

### Runtime independence

The model is evaluated by a JSON-encoded linear scorer in
`backend/app/research.py`, not by loading sklearn at request time. The evaluator is
arithmetically verified against sklearn's `predict_proba` to ~1e-16, and a test
asserts the served evaluator agrees with itself: `predict_values` must return the
argmax of `predict_probabilities`.

## Frontend

`frontend/src/pages/modules/RadiationTranscriptomicPrediction.jsx` renders the two
cards on the existing AI prediction page, guarded by the same
`artifactExists` pattern used for the tomato and lettuce cards.

**Absolute UI preservation.** The component composes existing pieces only —
`Card`, `Limitations`, `prose`, `warning-box`, `comparison-value`, `module-actions`,
`secondary-button`, `wide-link`. No layout, palette, typography, spacing, animation,
navigation or 3D asset was touched. This is measured, not asserted: see the visual
regression section below.

**What a user can do.** Load a class centroid and see the predicted class, the
probabilities, the hold-out balanced accuracy, the permutation p-value, the group
count, Cramér's V and — for the exposure model — the batch-controlled figure, with
the source dataset linked.

**What a user cannot do.** Type arbitrary expression values. The only input is a
training-set centroid, labelled on screen as *"synthetic input — class centroid of
the training data, not a measured sample"*. Exposing a free-text gene box for a
150-gene microarray model would invite confident nonsense, and the tomato card's
existing precedent is a measured training example for exactly this reason.

## Dataset explorer

The models are not useful if a reader cannot reach their source. Two endpoints were
repaired in the audit:

- `GET /api/datasets` now lists **17 datasets** (18 entries through the API, which
  also surfaces the external Earth lettuce source). The four Phase 9 studies —
  OSD-46, OSD-782, OSD-411 and OSD-780 — were added by
  `scripts/catalog_phase9_studies.py` from the verified manifest, and a test asserts
  that every registered model's `sourceStudy` resolves here.
- `GET /api/datasets/{id}/preview` returns the sample-to-condition tables for the new
  studies. Each table's note states that the rows are design factors rather than
  measured outcomes, because the measurements themselves are expression matrices.

## Tests

`backend/tests/test_phase9_models.py` — 46 tests covering registry presence,
checksum verification, unreachability of excluded models, baseline comparison on the
correct metric, finite permutation p-values, group-held-out validation, batch-confound
disclosure, synthetic labelling, centroid round-trips, 422 handling for missing and
extra genes, out-of-domain detection, evaluator/binary-encoding correctness, and the
classification register.

`frontend/e2e/radiation.spec.js` — 9 tests across three viewports: cards render and
answer, every class centroid is classified as its own class, an API error surfaces
as an alert with no result, and every sentence mentioning yield is checked to be a
negation rather than a claim.

## Visual regression

`frontend/e2e/mission.spec.js` previously wrote screenshots **into**
`docs/screenshots/`, the directory holding the committed baselines — so any
comparison compared a file with itself and always passed. Captures now go to the
gitignored `frontend/test-results/screenshots/`, and
`scripts/visual_regression.py` compares them against the committed files.

Gate: canvas size must match exactly; at most 2 % of pixels may differ beyond a
channel delta of 16 (a tolerance that exists because text rasterisation differs
between machines, not because a layout change would be forgiven).

Measured result (`ml/evaluation/phase9_visual_regression`):

| Capture | Differing pixels |
| --- | --- |
| mission-desktop | 0.000 % |
| mission-tablet | 0.001 % |
| mission-mobile | 0.000 % |
| radiation-{desktop,tablet,mobile} × {quality,exposure} | first baselines created |

The three existing viewports are unchanged. The six new captures establish baselines
for the new cards so later phases can prove they did not drift.

## One configuration change, and why

The full browser suite started failing on **unrelated** assertions in later tests.
The cause was the app's own request guard: three viewports of page loads exceed the
180 requests/minute per-address budget, and the app then correctly returned 429.

The guard is a real protection, so it was not disabled. The general budget became
operator-configurable via `SPACEAGRISIM_GENERAL_RATE_LIMIT_PER_MINUTE`:

- shipped default **180/min — unchanged**;
- auth budget **30/min — unchanged and still tight**;
- the Playwright `webServer` sets 5000 for the test run only;
- an explicit constructor value still wins, so a test can pin a tight budget;
- a test pins all three facts.

## Authorization regressions

No auth code was modified in Phase 9. The existing suite's 401/403 paths for
scenario reads and writes are part of the 261 passing backend tests, and the browser
suite still exercises registration and scenario save end to end.

## Not done, on purpose

- **No deployment.** Nothing was published to Render or any host. No result here
  claims production verification.
- **No new UI surface.** No page, route, navigation entry or style was added.
- **No fabricated demo data.** The centroids are labelled synthetic everywhere they
  appear, and no measured NASA result is presented as a prediction.
