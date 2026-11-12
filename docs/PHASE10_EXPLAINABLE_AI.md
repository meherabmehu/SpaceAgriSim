# Phase 10 — explainable AI

Both served transcriptomic models are linear-softmax evaluators: a per-class weight
vector, a per-gene standardisation, an intercept, and a softmax. For that model class
an explanation does not need a surrogate. The contribution of gene *j* to the logit
of class *c* is exactly

```
contribution(c, j) = weight[c][j] * (x[j] - mean[j]) / scale[j]
logit(c) = intercept[c] + sum_j contribution(c, j)
```

`ml/training/explain.py` computes that and then **asserts the identity to 1e-9**. If
the reconstruction fails it raises instead of returning a table, because an
explanation that does not reconstruct the served logits is an explanation of
something else.

**SHAP is deliberately not used.** On a linear model it would compute the same
numbers more slowly and with an added layer of approximation. The interesting
questions here are ones SHAP would not answer anyway.

## What is served

`GET /api/models/{id}/explanation`, for the two radiation classifiers only. Every
other model returns **404** rather than a surrogate's guess: fitting a mimic and
presenting its importances as the model's would be exactly the failure mode this
phase is meant to prevent.

Each response carries:

| Field | Meaning |
| --- | --- |
| `method` | exact linear attribution of the served evaluator |
| `identityResidual` | reconstruction error — 8.9e-16 for quality, 0.0 for exposure |
| `notASurrogate` | statement that the numbers come from the shipped weights |
| `explainedInput` | the control-class centroid, i.e. a synthetic mean |
| `perClass` | per-class logits and top contributions |
| `selectionStability` | fold-by-fold selection frequency for all 150 genes |
| `permutationImportance` | group-held-out, model refit per fold |
| `singleGeneDependence` | whether any one gene is individually necessary |
| `interpretationLimits` | what the numbers do not mean |

## The two numbers that matter more than the top-gene list

### 1. No single gene is necessary

Permutation importance with the model **refit inside each held-out fold**:

| Model | Held-out baseline | Largest single-gene drop |
| --- | --- | --- |
| `radiation-quality-osd46-v1` | 0.958 balanced accuracy | **0.0037** |
| `radiation-exposure-osd46-v1` | 0.986 balanced accuracy | **0.0000** |

Removing any one of the 150 deployed genes barely moves the decision. The signal is
distributed across the selected set. So these genes are a **signature, not
biomarkers**, and none of them should be reported as one. That conclusion is now
computed and surfaced rather than left as an editorial caveat.

### 2. Selection stability separates findings from accidents

Selection frequency, measured by re-running the *exact* deployed selection over all
22 leave-one-group-out folds:

| Model | Chosen in every fold | Chosen in under half |
| --- | --- | --- |
| quality | **75** of 150 deployed (of 21,267 considered) | 6 |
| exposure | **95** of 150 deployed | 9 |

A gene with a large coefficient in the final fit but a selection frequency of 0.14 is
the weakest part of any explanation built on it, and the payload says how many such
genes there are.

## Three things the first implementation got wrong

All three were found by testing rather than by review, and all three are now guarded:

1. **The binary model stores an all-zero coefficient row for class 0.** A per-class
   attribution would have reported "control contributes nothing", which is an artefact
   of the encoding. It is now explained as its single decision function, and the
   encoding is stated in the payload.
2. **Permutation importance was in-sample.** It scored a model fitted on every row and
   reported 1.000 balanced accuracy. It now refits inside each fold and scores only
   held-out groups.
3. **The binary model was scored against three-class labels**, producing a balanced
   accuracy of 0.333 that is arithmetically impossible for a binary task. Labels are
   now derived per model.

## One knowingly optimistic number

The permutation baseline reuses the deployed gene set, which was selected on all 44
arrays, so its 0.958 / 0.986 is optimistic against the honest group-held-out figures
of 0.898 / 0.910. The importances are *differences* against that baseline and are
reported for ranking genes, not as evidence of performance. The artifact says this in
`selectionLeakageNote`.

## What an explanation here does not mean

- It is not causal. A large contribution means the gene separated these conditions
  **in this study**.
- It is not a biomarker claim. See the distributed-signal result above.
- Contributions are additive on the logit scale, so a sign is relative to the other
  classes; it does not mean "up-regulated".
- Two genotypes, one laboratory, one microarray platform, 44 arrays.

## Where it lives

Explanations are stored **beside** the models (`ml/artifacts/<id>-explanation.py`),
not inside them, so a model artifact's checksum keeps meaning "the trained model" and
the explanation carries its own provenance and its own regeneration script
(`ml/training/phase10_explain_radiation.py`).
