# Phase 12 — scientific AI workflows

The brief asks for a complete workflow: **select evidence → choose a compatible model →
validate input → run inference → interpret → review limitations → save or export**. This
document describes how that is implemented, and the four refusals that make it safe.

The implementation is additive. Every `/predict/*` endpoint still exists and still behaves
exactly as before; `/workflow/*` is a registry-driven surface over the same evaluators.

---

## 1. The endpoints

| Endpoint | Auth | What it does |
| --- | --- | --- |
| `GET /api/workflow/models` | none | Every served model with its input family, feature count, scientific category, run status, calibration block, explanation availability and retirement reason |
| `POST /api/workflow/compatible` | none | Which models accept a given feature set (`exact` / `superset` / `subset` match), so a form never has to hard-code model ids |
| `POST /api/workflow/validate` | none | Validate without inferring; returns the checks applied and the category. No number is produced |
| `POST /api/workflow/run` | optional | Validate → infer → interpret → attach limitations and provenance. Anonymous callers may run; only an authenticated caller may `save` |
| `POST /api/workflow/run-and-save` | required | Same, always persisting |
| `GET /api/analyses` | required | The caller's saved analyses |
| `GET /api/analyses/{id}` | required | One analysis, with its stored payload |
| `DELETE /api/analyses/{id}` | required | Delete; 204, then 404 on a repeat |
| `GET /api/analyses/{id}/export/{json,csv,md}` | required | Export the stored payload unchanged |

---

## 2. Input families — the central safety property

A gene-expression vector and a set of environmental descriptors are both "numbers", which
is exactly why feeding one to the wrong model is an easy mistake to make and a hard one to
notice. Each model is therefore assigned exactly one input family:

| Model | Family | Features | Status |
| --- | --- | --- | --- |
| `lettuce-earth-growth-v1` | `environment` | 4 | runnable |
| `lettuce-earth-growth-v2` | `environment` | 4 | runnable |
| `mizuna-harvest-v1` | `harvest` | 4 | runnable |
| `mizuna-microbial-load-v1` | `microbial` | 6 | **retired** (category 6) |
| `mizuna-microbial-relative-load-v2` | `microbial` | 5 | runnable |
| `radiation-exposure-osd46-v1` | `gene-expression` | 150 | runnable |
| `radiation-quality-osd46-v1` | `gene-expression` | 150 | runnable |
| `tomato-flight-response-v1` | `gene-expression` | 64 | runnable |

The workflow infers the family of the *supplied* feature names from the registry's own
feature map, and compares it with the model's family. A gene identifier can therefore never
be mistaken for a temperature because both arrive as numbers:

```
POST /api/workflow/run
{"modelId": "radiation-quality-osd46-v1",
 "inputs": {"daysAfterTransplant": 20, "airTemperature": 24,
            "rootTemperature": 22, "ppfd": 400}}

HTTP 422 {"error": "family-mismatch",
          "expectedFamily": "gene-expression", "providedFamily": "environment",
          "missing": [ ... 20 gene features ... ]}
```

The reverse direction is refused identically: a 64-gene vector cannot be run through the
lettuce model. Nothing is imputed, and nothing is silently dropped.

---

## 3. Validation: schema, then physics, then domain

Five checks, applied in this order, all reported in `validation.checksApplied`:

1. **`schema-exact-feature-set`** — missing and unexpected features are both errors. A model
   requires exactly its recorded feature vector.
2. **`finite-values`** — `NaN` and infinity are rejected, not clamped.
3. **`physically-plausible-range`** — absolute limits per quantity, independent of any
   model's recorded domain: `airTemperature` ∈ [−40, 60] °C, `ppfd` ∈ [0, 2500]
   µmol/m²/s, `daysAfterTransplant` ∈ [0, 400], fractions ∈ [0, 1]. A value outside these is
   a bug even if a model's stored domain would admit it.
4. **`training-domain-range`** — the model's own recorded domain. Outside it, the response
   carries `insideTrainingDomain: false` and the warning, and the run still proceeds,
   **labelled as extrapolation** rather than blocked silently.
5. **`scientific-category-not-6`** — see the next section.

```
900 °C air temperature -> HTTP 422 {"error": "physically-impossible",
                                    "feature": "airTemperature", "limits": [-40, 60]}
```

**No out-of-distribution threshold is claimed.** Phase 11 tested two novelty scores against
three controls (a verified duplicate that must look ordinary, a platform shift that must
look different, and a held-out study) and neither passed; `thresholdValidated` is `false` in
`ml/evaluation/phase11_ood_uncertainty.json`. Phase 12 therefore does schema and physical
plausibility checks and reports the training-domain position, and says in the response that
this is not a novelty detector.

---

## 4. The four refusals

| Refusal | Status | Trigger |
| --- | --- | --- |
| `retired-model` | **410** | Category 6. `mizuna-microbial-load-v1` stays registered for reproducibility and returns the evidence that retired it |
| `family-mismatch` | 422 | Input family ≠ model family |
| `physically-impossible` | 422 | Value outside the absolute physical range |
| `missing-features` / `unexpected-features` | 422 | Schema is not exactly the recorded feature vector |
| insufficient evidence (assistant) | 200 + `refusal` | Nothing in the corpus above the evidence floor |

`retired-model` is a 410 rather than a 422 on purpose: the model existed, it answered once,
and the honest statement is "gone", not "bad request".

---

## 5. What every run returns

```json
{
  "workflow": ["validate-input", "run-inference", "interpret",
               "attach-limitations", "attach-provenance"],
  "inputs": {...},
  "validation": {"schemaExact": true, "insideTrainingDomain": true, "checksApplied": [...]},
  "output": {"kind": "regression", "prediction": 191.36,
             "unit": "g fresh shoot mass/plant", "isMeasurement": false,
             "calibrated": false, "interval": {...}, "note": "..."},
  "interpretation": "The model estimates 191.4 g fresh shoot mass/plant. This is a model
                     output, not a measurement of a real plant.",
  "limitations": ["Only Batavia Othilie lettuce on Earth; not calibrated for partial
                   gravity or radiation.", "..."],
  "provenance": {"sourceStudy": "WUR-lettuce", "sourceUrl": "...",
                 "sourceType": "external scientific data (not NASA)",
                 "artifactSha256": "9931f375…", "validationProtocol": "...",
                 "samples": ..., "groups": ...},
  "scientificClassification": {"category": 3, "categoryName": "...", "serviceAllowed": "..."},
  "calibration": {"calibrated": false, "nominalCoverage": 0.9,
                  "measuredCoverage": 0.9606, "statement": "..."},
  "explanationAvailable": false,
  "evidence": {"claims": [...], "citations": [...]},
  "reproducible": {"artifactPinnedBySha256": true, "deterministic": true}
}
```

Three properties are worth stating explicitly:

* **`isMeasurement: false`** on every output, and the interpretation sentence says so in
  words. A classifier's class probability is labelled `calibrated: false` with the note that
  softmax output must not be read as confidence.
* **Limitations come from the registry**, not from the route, so a model's own recorded
  caveats travel with its number.
* **The artifact is pinned by SHA-256**, so the same inputs and the same artifact produce the
  same output — which `scripts/demo_phase12.py` and the tests both check.

---

## 6. Saved analyses

`analyses` stores `id`, `owner_id` (NOT NULL, indexed), `model_id`, `title`, `created_at`,
`payload`. Four helpers — `save_analysis`, `list_analyses`, `get_analysis`, `delete_analysis`
— take `owner_id` as their first argument; there is no unscoped read.

* Another account's id returns **404, not 403**, so the API is not an existence oracle.
* A run that is refused (410/422) is never saved, and an anonymous caller cannot save
  (`401` before inference runs).
* The payload is capped at 200 000 bytes.

Exports serialise the **stored** payload:

| Format | Contents |
| --- | --- |
| `json` | The stored analysis, re-indented |
| `csv` | `field,value` rows: id, title, model, created, prediction, kind, calibrated, category, every input, and each citation |
| `md` | Title, model, category, prediction and unit, calibrated flag, interpretation, limitations, claims, citations, and the closing statement that the output is a model interpretation |

A test asserts that the CSV's `prediction` parses to exactly the float the API returned, and
that the "not a measurement" disclaimer is inside the file. The disclaimer lives in the
export, not only in the UI, because an exported file is what gets pasted into a slide.
