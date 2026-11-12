# Phase 27 — Integration Report

**Result: Phase 26 was already fully merged before this phase began. `main` is at `5800b9a`, and
every Phase 26 commit is an ancestor of it.** The verification is recorded here because the brief
asked for it, not because a merge was outstanding.

---

## 1. Remote state at the start of this phase

```
$ git ls-remote origin main phase26-dataset-expansion
5800b9aef52db60001eaa2d64df8f2a74f95901b   refs/heads/main
ccf2ca6571f58fe9a1f1f882e24b4e8e385efc3c   refs/heads/phase26-dataset-expansion
```

`5800b9a` is a documentation commit on top of the Phase 26 merge commit `0c1d4ae` (a `--no-ff` merge
of `phase26-dataset-expansion` into `main`). Phase 26 was merged in the previous turn, verified on
the remote ref and re-verified from a fresh clone.

## 2. Ancestry and contained commits

```
$ git merge-base --is-ancestor origin/phase26-dataset-expansion origin/main
YES - fully contained
```

Five Phase 26 commits, all reachable from `main`:

| SHA | Subject |
| --- | --- |
| `d3a4524` | phase26: acquire and preprocess verified non-NASA datasets |
| `6e8c49d` | phase26: compare platform water demand against measured lettuce ET |
| `d3b10d6` | phase26: catalogue 23 → 28 from hash-verified acquisitions |
| `bb6df81` | phase26: audited feature readiness with a builder that refuses to overclaim |
| `ccf2ca6` | phase26: dataset expansion, feature restoration and model reports |
| `0c1d4ae` | Merge branch 'phase26-dataset-expansion' into `main` |
| `5800b9a` | docs: record the phase 26 merge into main |

## 3. Changed-file review

Every file in the Phase 26 diff was opened. The review was not a rubber stamp: **it found an error
in the phase's own headline number**, which is corrected in `ce3fff0`.

| Group | Files | Verdict |
| --- | --- | --- |
| Acquisition scripts | `scripts/datasets/{registry,acquire,preprocess}.py` | verified: hashes, sizes, magic bytes, and the manifest's counts follow from files on disk |
| Raw downloads | 5 files, 2.5 MB | verified: SHA-256 recomputed, matches the manifest, sizes 94 KB–1.5 MB |
| Processed tables | 8 CSVs + 8 quality JSONs | **one defect found** — see §4 |
| Validation artefact | `ml/evaluation/phase26_measured_et_validation` | regenerated with corrected inputs |
| Catalogue | `dataset_catalog` + `DATASET_CATALOG.md` (28 datasets) | verified: counts match, `--check` clean, every class justified |
| Gap matrix | `dataset_gap_matrix` + `DATASET_GAP_MATRIX.md` (12 gaps) | verified: `--check` clean after regeneration |
| Readiness audit | `feature_readiness`, `build_feature_readiness.py`, coverage matrix | verified: validator rejects every fabricated tier it is given |
| Reports | 4 Phase 26 documents | corrected where they quoted the wrong numbers |
| Tests | `test_phase26_datasets.py`, `test_phase23_reference_et0.py` | verified: 40 tests, all passing |

**No scientific documentation or provenance was discarded.** The Phase 26 reports were amended in
place rather than replaced, so the record of what the phase claimed and what was later found wrong
about it both survive.

## 4. The defect found during integration

The Phase 26 water-use artefact reported its shape agreement across **10** measurement dates and its
prose claimed **13**. The trial has **11** weighing dates.

Cause: the recomputed whole-day evapotranspiration rate cannot exist for a pot's first weighing —
there is no previous interval to divide by. Using that column alone dropped 55 of 604 rows and an
entire measurement date from the daily aggregate.

The fix falls back to the workbook's own per-day column for each pot's first interval and records
which of the two produced each row (549 recomputed, 55 from the workbook column). Corrected and
regenerated, not retyped:

| Quantity | Phase 26 as delivered | Phase 27 corrected |
| --- | --- | --- |
| pot-days | 345 | **380** |
| measurement dates used | 10 | **11** |
| Spearman | 0.72 | **0.7909** |
| Pearson | 0.48 | **0.5631** |
| pooled predicted/measured | 0.143 | **0.1401** |
| fitted scale | 6.34 | **6.38** (LOO-treatment 5.93–6.65) |
| per-gram ratio | 0.145 | **0.1416** |
| pot-surface denominator | 0.24× | **0.247×** |
| canopy-area denominator | 2.75× | **2.871×** |

The scientific conclusion is unchanged — shape agrees, level is not identifiable — but the numbers
attached to it now match the data. Every document that quoted the old figures was regenerated from
the corrected artefact by script, and two new tests pin the coverage: every pot-day has a usable
rate, and the validation uses all 11 dates.

## 5. Conflict resolution

**There were no conflicts.** `origin/phase26-dataset-expansion` is a strict ancestor of `origin/main`,
so the merge had already completed cleanly and no work needed to be reconciled.

## 6. What was integrated in this phase

Phase 27 adds no new merge; it builds on `main` and fast-forwards it. The chain is in
`docs/PHASE27_DELIVERY_REPORT.md`.

## 7. Remote verification

Recorded in the delivery report, with the exact `git ls-remote` output for the final `main` SHA.
