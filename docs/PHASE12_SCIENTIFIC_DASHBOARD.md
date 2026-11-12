# Phase 12 — scientific dashboard

The dashboard is a panel inside the existing **AI prediction center** page. It answers, for
every served model, the questions a judge should ask before believing a number:

> what is this, what data is it trained on, may it answer, are its probabilities calibrated,
> and can it explain itself?

It is served by `GET /api/workflow/models` and rendered by
`frontend/src/pages/modules/sciencePanels.jsx` → `ScientificStatusPanel`.

---

## 1. What each card shows

| Field | Source | Why |
| --- | --- | --- |
| Scientific category and name | `app/science_classification.py` | Category 6 means "unsupported scientific prediction"; that model may not answer |
| Run status | registry + category | `runnable` / `retired` / `unavailable` |
| Input family and required feature count | `app/workflow.py` | Tells the user that a molecular model needs 150 genes, not a temperature |
| Training source | registry `sourceType` | Distinguishes NASA OSDR data from external data from unstated |
| Calibrated probabilities | registry `calibration.calibrated` | `false` on all eight models |
| Nominal vs measured coverage | registry `calibration` | Two different numbers, shown as two |
| Explanation available | registry `explanationAvailable` | True only for the two OSD-46 linear models |
| Retirement reason | classification evidence | A retired model shows the finding that retired it |

The panel header states plainly how many models are NASA-trained:

```
4 of 8 models were trained on NASA OSDR data. The rest record a different or
unstated source and are labelled as such: not every served model is NASA-trained.
```

The four are `mizuna-microbial-load-v1` (retired), `mizuna-microbial-relative-load-v2`,
`radiation-quality-osd46-v1` and `radiation-exposure-osd46-v1`. The two lettuce models are
external WUR data; `mizuna-harvest-v1` and `tomato-flight-response-v1` use NASA OSDR studies
but record no source-type string, so the panel says "source type not recorded (OSD-655)"
rather than promoting them to the NASA-trained count.

---

## 2. Calibration, presented without overclaiming

Every model is `calibrated: false`. The panel shows measured coverage beside nominal coverage
because those are different claims:

| Model | Nominal | Measured | Method |
| --- | --- | --- | --- |
| `lettuce-earth-growth-v1` | 0.90 | 0.9393 | cv_plus, held-out biological groups |
| `lettuce-earth-growth-v2` | 0.90 | 0.9606 | cv_plus, held-out biological groups |
| `mizuna-microbial-load-v1` | 0.90 | 0.9919 | cv_plus, held-out biological groups |
| `mizuna-microbial-relative-load-v2` | 0.90 | 0.9919 | cv_plus, held-out biological groups |

Measured coverage is an evaluation result on held-out groups. It is not a guarantee for a
future campaign, and the registry's own `statement` field says exactly that. The classifiers
have no interval at all, so their softmax output is labelled "not calibrated" in the workflow
response instead of being dressed up as a confidence.

---

## 3. Explainability, stated per model

* `radiation-quality-osd46-v1` and `radiation-exposure-osd46-v1` ship an exact linear
  attribution of the served linear-softmax evaluator: identity residual 8.88e-16, 75 genes
  chosen in all 22 folds, and a largest single-gene permutation drop of 0.0037 — i.e. the
  signal is distributed, not carried by one gene.
* No other model reports a valid explanation method, and
  `GET /api/models/{id}/explanation` returns **404** for them rather than a surrogate. The
  panel shows "not available" for six of eight models.

Phase 11 also found that the *method* choice matters: top-5 overlap between learners was
0.80–1.00 but panel Spearman was 0.016, with 90–100 % zero-drops. The dashboard does not
present feature importance as a ranking of biological importance.

---

## 4. Where the numbers come from

Nothing on the panel is computed in the browser. The category, the calibration block, the
explanation flag and the source string all come from the API, which reads
`ml/artifacts/registry` and `ml/evaluation/*.py`. The UI restates no threshold and
derives no metric; it also does not paraphrase the category names, so it cannot drift from
`app/science_classification.py`.

A browser test (`frontend/e2e/assistant.spec.js`) asserts the panel renders, that a
`retired` badge is visible, and that the calibration label appears on every card.
