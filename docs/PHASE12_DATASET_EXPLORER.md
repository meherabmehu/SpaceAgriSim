# Phase 12 — dataset explorer

The explorer answers one question honestly: **how many independent studies is that?**
Counting accessions is the wrong answer and it is the answer most tools give.

Served by `/api/explorer/*`, computed by `backend/app/explorer.py`, rendered by
`IndependencePanel` inside the existing **NASA data explorer** page.

---

## 1. The relation vocabulary (closed on purpose)

Every dataset pair is classified into exactly one of four relations, and each relation
carries a plain-language meaning in the API response — so the caller is not left to guess
what "overlap" meant.

| Relation | Meaning stated in the response |
| --- | --- |
| `duplicate-measurement` | The same physical measurements, deposited twice. Correlations between the two accessions are not evidence: they measure nothing but the duplicate. |
| `shared-sample-different-assay` | Different assays measured on the same biological material. Two accessions, but not two independent samples of plants: treating them as replicates inflates the effective sample size. |
| `unverified-overlap` | Sample identifiers appear in both accessions, or no overlap audit has covered this pair. It must not be assumed independent until a numeric check is run. |
| `independent` | No shared sample identifiers in the identifier audit, and no numeric-equivalence proof links the two accessions. |

`independent` is only ever returned for a pair where **both** accessions have a completed
identifier audit. Absence of a detected overlap is not evidence of independence, so an
unaudited accession is `unverified-overlap`, never `independent`.

---

## 2. What the counts actually are

```
26 accessions  ->  25 independent studies
  1 duplicate-measurement   (OSD-46 / OSD-320)
  1 shared-sample-different-assay (OSD-655 / OSD-780, 45 shared identifiers)
 31 unverified pairs (shared identifiers without a numeric check, or an unaudited accession)
```

### OSD-320 is OSD-46

Phase 11 compared the two deposits directly:

| Measure | Value |
| --- | --- |
| Arrays compared | 44 |
| Probesets compared | 22,810 |
| Minimum correlation | 1.000000 |
| Maximum absolute difference | 0.0 |

OSD-320 is a **second deposit**, not an independent radiation study. It stays listed — the
data is real and usable — but `countsAsIndependentStudy: false`, and it is excluded from
every independent count. The explorer's warning box quotes the numeric proof rather than
asserting equality by name, and cites
`ml/evaluation/phase11_duplicate_audit#numericProof`.

The consequence is stated too: OSD-320 must not be used as a validation study for OSD-46 or
for any radiation model trained on it. Cross-study validation needs a deposit of *different*
arrays; using the duplicate would have produced a perfect-score "replication" from a study
compared against itself.

### OSD-655 and OSD-780 share material

45 sample identifiers appear in both accessions with disjoint assays (elemental analysis and
ORAC versus microbiome sequencing). These are different measurements of the same plants, so
they are `shared-sample-different-assay`: real data, but not independent replicates.

### OSD-267 / OSD-268 / OSD-269 stay unverified

They share 5–9 sample identifiers and OSD-269 is a 16S subset of the other two. No numeric
equivalence check has been run, so they are `unverified-overlap` with
`auditClassification: shared-sample-needs-numeric-check` attached — not merged into either
"duplicate" or "independent".

---

## 3. The endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /api/explorer/datasets?q=` | Rows with species, assays, sample counts, `identifierAudited`, `redundantDeposit`, `countsAsIndependentStudy`, `usedByModels`, and an `independentStudyCount` for the filtered set |
| `GET /api/explorer/overlaps` | Relation counts, every non-independent relation, the meaning of each class, the redundant deposits with their proof, and the independent study count |
| `GET /api/explorer/datasets/{id}` | One accession with its relations and a 404 for an unknown id |
| `POST /api/explorer/independent-set` | Reduce a requested study list to a defensible set |

`POST /api/explorer/independent-set` is the one that changes behaviour: it is greedy and
order-preserving (first accession wins, so the result is reproducible for a given input
order), reports every drop with the relation that caused it, reports unknown ids separately
instead of ignoring them, and lists pairs whose independence is merely unverified rather
than pretending the set is fully clean.

```
POST /api/explorer/independent-set
{"ids": ["OSD-46", "OSD-320", "OSD-655", "OSD-780"]}

-> independent: ["OSD-46", "OSD-655"], independentCount: 2, requested: 4
   drop OSD-320: duplicate-measurement (conflicts with OSD-46)
   drop OSD-780: shared-sample-different-assay (conflicts with OSD-655)
```

---

## 4. The safeguard that reaches existing clients

`GET /api/datasets` now also returns, per row, `countsAsIndependentStudy` and
`redundantWith`. These are additive fields: a client that already counts accessions can see
that one of them does not count as a study **without changing its request**, and any future
accession that duplicates another is picked up by the same field rather than by a client-side
patch.

---

## 5. Limits of what this proves

* The relation table is only as complete as the Phase 11 identifier audit: 25 of 26
  accessions are audited, and the rest are reported as unverified rather than assumed clean.
* Sample-identifier overlap is evidence of shared material, not proof of bit-identical
  values; only OSD-320/OSD-46 has numeric proof.
* The audit canonicalises identifiers by stripping a trailing array suffix
  (`GSM1506014_1` ≡ `GSM1506014`); a deposit numbered differently would not be detected, and
  the docs say so rather than implying exhaustive duplicate detection.
* Nothing here changes any model. No served model claims to be trained on OSD-320; the
  arrays are reachable only through OSD-46.
