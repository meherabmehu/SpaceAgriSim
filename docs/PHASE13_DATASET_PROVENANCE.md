# Phase 13 — Dataset Provenance and Scientific Safeguards

The evidence corpus the research assistant answers from, the provenance of the models built on it,
and the three safeguards from Phases 11–12 that Phase 13 must not weaken.

Everything here is verifiable from the repository: `python3 scripts/audit_models.py` re-checks the
model-side claims, `GET /api/assistant/corpus` reports the corpus, and
`backend/tests/test_phase13_model_audit.py` enforces the dataset invariants in CI.

---

## 1. Where the evidence comes from

The assistant retrieves over **47 curated passages** built from repository artifacts:

| Kind | Count | Source |
|---|---|---|
| Datasets | 20 | NASA OSDR study records (OSD-7 … OSD-895) |
| Models | 8 | the served model artifacts in `ml/artifacts/` |
| Findings | 10 | Phase 10–12 audits |
| Methodology | 6 | documented procedures (`method-*`) |

Every dataset passage carries its accession, an OSDR URL, the local artifact it was derived from,
an evidence class, and its limitations. Nothing is retrieved from the network at request time:
retrieval is BM25 over verified local artifacts, so the answer to the same question cannot change
because a remote service did.

**Registered versus accessible.** 19 studies appear in the packaged dataset manifest and 26
accessions are browsable in the explorer; those are different sets and the interface does not
conflate them. A study being listed in OSDR does not mean its measurement table was downloaded,
and a dataset passage says which it is.

## 2. The OSD-320 duplication safeguard (Phase 11, still enforced)

> OSD-320 holds the same Affymetrix arrays as OSD-46 under a second accession. 44 arrays and 22,810
> probesets were compared: minimum Pearson correlation 1.000000 and maximum absolute difference
> 0.0. OSD-320 must therefore never be used as independent validation of a radiation model trained
> on OSD-46.

This is the single most consequential provenance finding in the repository. Two accessions, one
dataset. Before Phase 11 an analyst could reasonably have trained on OSD-46 and "validated" on
OSD-320 and reported an independent replication that does not exist.

Three things keep it enforced:

1. the finding is a corpus passage the assistant retrieves and cites;
2. `scripts/audit_models.py` fails if the finding disappears, if its wording stops stating the
   prohibition, or if **any** artifact mentions OSD-320 without a duplicate or independence
   caveat in the surrounding text;
3. the benchmark includes "Is OSD-320 an independent replication of OSD-46?" and expects a
   grounded answer that cites the audit finding.

### The two distinctions that must survive

**Shared samples are not duplicate measurements.** Overlapping arrays mean the *same measurement*
appears twice. Overlapping *biological material* — seedlings from one harvest split across two
assays — means two different measurements of the same samples. Only the first invalidates
independence. The corpus states which case applies rather than treating "overlap" as one thing.

**Unverified overlap is not independence.** When nobody has checked whether two studies share
material, the correct position is "unknown", not "independent". Absence of a found duplicate is
not evidence of independence, and no passage in this corpus treats it as such.

## 3. Other safeguards asserted by the audit

**Retired models stay retired.** `mizuna-microbial-load-v1` is category 6 and not runnable: its
leave-one-experiment-out R² is −0.55 and −0.58, i.e. worse than predicting the training mean.
`radiation-dose-osd782-v1` (0.361 balanced accuracy against 0.333 chance, permutation p = 0.353)
and `gravity-reorientation-osd411-v1` (0.500 at chance, p = 0.517) were never served. All three are
documented as exclusions with their numbers, not quietly dropped. Each was excluded rather than
tuned until it appeared to work.

**Negative results are recorded as results.** The 231-study sweep that found zero harvest or
biomass datasets, the failed OSD-46 → OSD-782 transfer (0.5 balanced accuracy under every
harmonisation attempted), the OSD-346 gravity signal that cannot be separated from flight run
(run-centred ρ = −0.798), and the nested-selection check showing no radiation learner beats the
served model (one won held-out group out of 22) are all first-class corpus passages. They are what
stops the assistant from inventing a dataset, a transfer or an improvement.

**Superseded artifacts are kept.** `lettuce-earth-growth-v1` and `mizuna-microbial-load-v1` remain
on disk unchanged beside their successors, so an older result can still be reproduced.

## 4. Provenance gaps, stated

The Phase 13 audit found and reports these; none is silently filled in.

| Gap | Models | Consequence |
|---|---|---|
| Licence not recorded per artifact | 5 of 8 | upstream terms exist (OSDR policy, WUR CC-BY-4.0 for v2) but are not captured; a redistribution question cannot be answered from the artifacts alone |
| Source URL and source type absent | `mizuna-harvest-v1` (OSD-655), `tomato-flight-response-v1` (OSD-767) | URL derivable from the accession; not written into validated artifacts |
| Calibration status undocumented | both radiation classifiers | the model cards do not say whether probabilities are calibrated |

Filling any of these in by writing a plausible value would convert a known gap into an undiscovered
error. See `docs/PHASE13_MODEL_RELIABILITY.md` §3 for the remediation path of each.

## 5. What the datasets do not support

* No dataset in this repository pairs a partial-gravity environment with a crop-production
  measurement. The Moon/Mars yield question has no evidence behind it, at any confidence.
* The molecular and radiation classifiers operate on Arabidopsis expression. They classify
  experimental context. They do not measure plant health, stress, yield or productivity.
* The lettuce and mizuna regressors are `trained-exploratory` with leave-one-experiment-out
  validation on a handful of campaigns. That is not cross-campaign generalisation.
* Registered-but-undownloaded studies are not evidence. The manifest says which is which.

## 6. Reproducing

```bash
python3 scripts/audit_models.py                                   # 114 checks, dataset safeguards included
python3 -m pytest -q backend/tests/test_phase13_model_audit.py    # 11 tests
curl -s localhost:8000/api/assistant/corpus                       # 47 passages, by kind
python3 scripts/evaluate_assistant.py                             # the OSD-320 question is item direct-02
```
