# Phase 26 delivery report — scientific dataset expansion and feature restoration

**Branch:** `phase26-dataset-expansion`, based on `main` at `34056cf` (Phase 25 delivery).
**Merged into `main`:** merge commit `0c1d4ae` (`--no-ff`), verified on the remote ref and
re-verified from a fresh `--depth 1` clone of `main` (988 passed / 24 skipped).
**Scope executed:** dataset discovery, acquisition with verification, preprocessing, one measured
water-use validation, catalogue and gap-matrix regeneration, a twelve-feature readiness audit,
tests and documentation. **No Render operation was performed and no Render configuration was
touched.** No production database was accessed and no migration was written.

---

## 1. Commits

| SHA | Subject |
| --- | --- |
| `d3a4524` | phase26: acquire and preprocess verified non-NASA datasets |
| `6e8c49d` | phase26: compare platform water demand against measured lettuce ET |
| `d3b10d6` | phase26: catalogue 23 → 28 from hash-verified acquisitions |
| `bb6df81` | phase26: audited feature readiness with a builder that refuses to overclaim |
| `ccf2ca6` | phase26: dataset expansion, feature restoration and model reports |
| `0c1d4ae` | Merge branch 'phase26-dataset-expansion' into `main` |

Every SHA above was verified against the remote ref with `git ls-remote` immediately after pushing.

## 2. The eleven deliverables

| # | Deliverable | Where |
| --- | --- | --- |
| 1 | Dataset expansion report | `docs/PHASE26_DATASET_EXPANSION_REPORT.md` |
| 2 | Feature restoration report | `docs/PHASE26_FEATURE_RESTORATION_REPORT.md` |
| 3 | Model improvement report | `docs/PHASE26_MODEL_IMPROVEMENT_REPORT.md` |
| 4 | Feature-to-dataset coverage matrix | `docs/PHASE26_FEATURE_COVERAGE_MATRIX.md` + `data/research/phase26/feature_readiness.json` |
| 5 | Acquisition scripts | `scripts/datasets/acquire.py` |
| 6 | Preprocessing scripts | `scripts/datasets/preprocess.py` |
| 7 | Discovery registry | `scripts/datasets/registry.py` (17 candidates, A–F) |
| 8 | Acquisition manifest with hashes | `data/metadata/phase26_acquisition_manifest.json` |
| 9 | Processed tables with quality files | `data/processed/phase26/` (8 tables, 8 quality files) |
| 10 | Measured-ET validation artefact | `ml/evaluation/phase26_measured_et_validation.json` |
| 11 | This delivery report | `docs/PHASE26_DELIVERY_REPORT.md` |

Supporting regeneration: `data/research/dataset_catalog.json` + `DATASET_CATALOG.md` (28 datasets),
`data/research/dataset_gap_matrix.json` + `docs/DATASET_GAP_MATRIX.md` (12 gaps, none closed).

## 3. Headline results

- **Catalogue 23 → 28.** Five datasets acquired, all hash-verified against the publisher's own
  declared size and MD5, all CC BY 4.0, all non-NASA. Classes A:2 B:7 C:9 D:4 E:5 F:1.
- **First measured crop water use in the repository.** 345 pot-days from 35 published greenhouse
  lettuce pots, compared against the unmodified platform water path.
- **Shape agrees, level does not.** Spearman 0.72 across 13 measurement days; the level discrepancy
  reverses sign between a pot-surface denominator (0.24×) and a canopy-area denominator (2.75×),
  and neither denominator is published. No constant was changed.
- **`measured-eta` stays `blocking`** and moves only to `partially-addressed`, with the one clause it
  closed and the four blockers that remain written into the gap matrix.
- **Feature readiness: 0 production-ready, 4 research-ready, 4 experimental, 4 data-blocked,
  0 unsupported.** Two of twelve moved, both from `data-blocked`.
- **No model retrained, no model card changed, no threshold touched.** The ET0 emulator remains
  `trained-exploratory` / `deployed: false`.
- **Tests: 988 passed, 24 skipped** (was 950/24). `scripts/audit_models.py`: 141 checks, 0 failed.

## 4. The failure this phase had, and its fix

The first acquisition run recorded five datasets as acquired when the files were 600–900-byte JSON
metadata documents. The manifest asserted five verified downloads and was wrong. The downloader now
verifies size, publisher MD5 and magic bytes, deletes payloads that fail, and the regression is
pinned by a test. Two parsing errors in the evapotranspiration and biomass sheets were found by
checking against the publication and corrected; both have regression tests.

This is recorded here rather than quietly fixed because a phase about not fabricating datasets had
to survive its own first attempt at exactly that failure mode.

## 5. What is still open

| Gap | Severity | Why it did not close |
| --- | --- | --- |
| `measured-eta` | blocking | no trial publishes the geometry needed to convert per-pot loss to a flux; ET includes evaporation |
| `fractional-gravity` | blocking | no open dataset exists |
| `yield-labels` | blocking | no controlled-environment tomato or mizuna harvest labels |
| `independent-et0` | major | no controlled-environment ET0 measurement |
| `led-spectrum-response` | major | no trial varying PPFD, photoperiod and spectrum independently |
| `substrate-water` | major | water-holding capacity is a property, not a time series |
| `cultivar-metadata` | major | every in-repo experiment uses one unnamed cultivar |
| 5 minor gaps | minor | unchanged |

## 6. Remaining manual steps

1. ~~Merge or review `phase26-dataset-expansion`.~~ **Done:** merged into `main` as `0c1d4ae`
   (fast-forward-able, merged with `--no-ff` so the phase is revertable as one unit). The branch
   ref is left in place and can be deleted whenever the owner prefers.
2. **Deployment is out of scope for this phase** and was not attempted. Any deployment decision
   belongs to the owner.
3. **PostgreSQL suite** still cannot run in this sandbox (no server on 5432); the 24 skips are
   unchanged.
4. **Commission the water-use trial** with published geometry — still the only route to closing the
   blocking gap, and the new validation artefact now says exactly which two numbers it would need.
5. **Do not** promote the weather-driven water path to default, and **do not** treat
   `phase26_measured_et_validation.json` as a validation score for any model.

## 6a. Merge record

`main` moved `34056cf` → `0c1d4ae`. The merge was a clean ancestor merge (no conflicts, no
resolution needed), the full backend suite was run **before** pushing and again from a fresh clone
**after**, and the eleven deliverables were confirmed present on the merged tree. No force-push, no
history rewrite, and the branch was not deleted.

## 7. Verification commands

```
python3 -m pytest backend -q                          # 988 passed, 24 skipped
python3 scripts/audit_models.py                       # 141 checks, 0 failed
python3 scripts/datasets/acquire.py                   # re-download and re-verify all five
python3 scripts/datasets/preprocess.py                # rebuild the eight processed tables
python3 ml/research/validate_measured_et.py           # rebuild the ET validation artefact
python3 ml/research/build_catalog.py --check          # catalogue freshness
python3 ml/research/build_gap_matrix.py --check       # gap matrix freshness
python3 ml/research/build_feature_readiness.py --check # readiness audit freshness
```
