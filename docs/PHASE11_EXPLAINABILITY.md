# Phase 11 — explainability

Phase 10 shipped per-gene importances and reported that 75 of a 150-gene panel are chosen in
every fold. That is a claim about a large panel. A user reading an explanation sees *one
short list*, so Phase 11 measured the two things that decide whether that list may be
trusted: does it move between folds, and does it depend on which learner produced it.

Evidence: `ml/evaluation/phase11_explainability`.

```
python ml/training/phase11_explainability.py    # ~10 min
```

Method: the same leave-one-biological-group-out folds used for scoring, gene selection on
training rows only, and importance measured by permuting a gene's values in the **held-out**
group and recording the drop in balanced accuracy. Out-of-fold importance cannot reward a
gene the model merely memorised.

---

## 1. Fold stability of the short panel

Top-40 panel from each of the 22 folds, compared with the deployed panel:

| Model | Mean Jaccard | Range | Top gene present | Genes in every fold |
| --- | --- | --- | --- | --- |
| `radiation-quality-osd46-v1` | **0.704** | 0.482 – 0.905 | 100 % | 19 of 115 |
| `radiation-exposure-osd46-v1` | **0.828** | 0.702 – 0.905 | 100 % | 26 of 70 |

Read this as: **the number-one gene never moves, about four fifths of the short list is
stable, and the rest of the list rotates.** 115 different genes appear in at least one fold's
panel for the quality model, of which only 19 appear in all 22. A user shown genes 20–40 is
being shown a fold-dependent choice; a user shown the top five is not.

This is the opposite of the Phase 10 framing, and more useful. "75 of 150 stable" sounds
reassuring about the whole panel; the honest statement is that stability is **strong at the
top and weak in the tail**, so the platform should show a short list and say so.

---

## 2. Learner dependence: the sharper result

Out-of-fold permutation importance for four model classes, compared pairwise:

### `radiation-quality-osd46-v1`

| Pair | Spearman over 40 genes | Top-5 overlap |
| --- | --- | --- |
| logistic L2 ~ linear SVM | undefined | 0.8 |
| logistic L2 ~ random forest | −0.026 | 0.8 |
| logistic L2 ~ gradient boosting | +0.037 | 0.6 |
| linear SVM ~ random forest | undefined | 1.0 |
| linear SVM ~ gradient boosting | undefined | 0.8 |
| random forest ~ gradient boosting | +0.037 | 0.8 |
| **mean** | **+0.016** (3 of 6 defined) | **0.80** |

### `radiation-exposure-osd46-v1`

| Pair | Spearman over 40 genes | Top-5 overlap |
| --- | --- | --- |
| all six pairs | **undefined** (0 of 6) | **1.00** |

**Every pair agrees on the top five and disagrees about the rest.** The quality model's mean
rank correlation across the panel is +0.016, i.e. no better than reshuffling, while its top
five genes are nearly identical between a logistic regression, a support vector machine and
a random forest.

### Why six of the correlations are undefined

A pairwise Spearman is undefined when an importance vector is constant, and here that is not
a missing value — it is the result:

| Model | Fraction of the 40-gene panel with **zero** permutation drop |
| --- | --- |
| quality — logistic L2 | 0.975 |
| quality — linear SVM | 1.000 |
| quality — random forest | 0.975 |
| quality — gradient boosting | 0.950 |
| exposure — logistic L2 | 1.000 |
| exposure — linear SVM | 1.000 |
| exposure — random forest | 0.900 |
| exposure — gradient boosting | 1.000 |

**Permuting any one gene in the panel leaves the held-out prediction essentially unchanged.**
For exposure, all four model classes behave identically: no individual gene is necessary.
This is what a distributed signature looks like from the inside, and it independently
confirms the Phase 10 permutation result and the Phase 11 finding that compressing the
signature into modules destroys it.

---

## 3. What this changes about the product

The served explanation is a logistic-regression coefficient list. That remains valid — but
its scope narrows to exactly what the evidence supports:

| Claim | Status |
| --- | --- |
| "These are the genes the model weighs most heavily" | **Supported** — top five agree across four model classes |
| "This gene is the driver of the prediction" | **Rejected** — permuting it changes nothing (90–100 % zero-drop) |
| "This gene causes the radiation response" | **Rejected** — this is an attribution, not an intervention |
| "The ranked list 1–40 is meaningful" | **Rejected** — mean rank correlation +0.016 across learners |
| "The panel is stable across folds" | **Partially** — stable at the top (100 % for rank 1), rotating in the tail |

The user-facing wording that survives all five rows is: *"a distributed expression signature;
the model's most weighted genes are shown first, and no single gene carries the prediction."*

No UI change is made — the requirement to preserve theme, layout, typography and navigation
stands. What changes is the documentation and the served caveat text around the existing
explanation panel, not its presentation.

---

## 4. Status

| Item | Classification |
| --- | --- |
| Fold stability of the interpretable panel | **Completed** (new) |
| Cross-learner importance agreement | **Completed** (new) |
| Distributed-signature confirmation by permutation | **Completed** |
| Rank-1 driver-gene explanation | **Rejected by scientific evaluation** |
| Causal interpretation of any gene | **Rejected by scientific evaluation** |
| Registry change | **None** — `calibrated: false` and the existing caveats are unchanged |

This is the third independent line of evidence that the radiation signal is distributed:
Phase 10 found it by permutation, Phase 11 found it by module compression failing, and this
document finds it by single-gene permutation leaving out-of-fold accuracy untouched. Three
methods, one conclusion, and the conclusion is now stated as a scope limit on the
explanation rather than as an observation.
